#!/usr/bin/env bash
# release.sh — automated release pipeline for rig-remote
#
# Usage:  ./release.sh <stage>
#
# Stages (each includes all steps of the previous):
#   package       : build pip + .deb (with lintian) only; no tests, no
#                   upload. Used by CI, which runs the checks as separate jobs.
#   commit_push   : ruff fix + format, mypy, then unit + functional tests (in that
#                   order, so the tested code is the packaged code), build pip +
#                   .deb, twine check, local install smoke test. gqrx functional
#                   tests are reported NOT RUN when gqrx is unreachable.
#   release       : commit_push, then generate release_message.md and print
#                   the hand-off steps. Stops at built, verified artefacts.
#
# This script never uploads anything. Publishing to TestPyPI / PyPI is done
# only by .github/workflows/release.yml (Trusted Publishing / OIDC), which a
# human triggers by pushing a v<version> tag and approves through the "pypi"
# GitHub environment.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV_BIN=".venv/bin"
PACKAGE_NAME="rig-remote"
RELEASE_WORKFLOW=".github/workflows/release.yml"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${BLUE}==> $1${NC}"; }
ok()   { echo -e "${GREEN}  ✔  $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠  $1${NC}"; }
die()  { echo -e "${RED}  ✖  $1${NC}" >&2; exit 1; }

read_version() {
    grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/'
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
preflight() {
    [[ -f pyproject.toml ]] || die "Must be run from the directory containing pyproject.toml."
    [[ -d "${VENV_BIN}" ]]  || die "Virtual environment not found at ${VENV_BIN}/. Run 'uv sync --group dev' first."
}

# ---------------------------------------------------------------------------
# Stage 1 — step functions
# ---------------------------------------------------------------------------
check_lock() {
    # CI installs with `uv sync --locked`, which fails if uv.lock is stale —
    # e.g. after a version bump in pyproject.toml. Catch it before tagging.
    step "Lockfile — uv lock --check"
    uv lock --check \
        || die "uv.lock is out of date (did pyproject.toml change?). Run 'uv lock' and commit uv.lock."
    ok "uv.lock is current."
}

run_static_analysis() {
    # Runs BEFORE run_tests: ruff --fix / ruff format may rewrite sources, and
    # mypy + the tests must check the code that actually gets packaged.
    step "Static analysis — ruff lint (--fix)"
    "${RUFF}" check --fix ./src
    ok "ruff lint: no issues."

    step "Static analysis — ruff format"
    "${RUFF}" format ./src
    ok "ruff format: done."

    if ! git diff --quiet -- src; then
        warn "ruff changed files under src/ — commit them before tagging, so the tag matches what was tested:"
        git diff --stat -- src
    fi

    step "Static analysis — mypy"
    "${MYPY}" --config-file ./pyproject.toml ./src
    ok "mypy: no issues."
}

gqrx_reachable() {
    "${VENV_BIN}/python" -c 'import socket; socket.create_connection(("127.0.0.1", 7356), timeout=1).close()' \
        >/dev/null 2>&1
}

run_tests() {
    step "Tests — Running unit tests (parallel)"
    "${PYTEST}" tests/ -n auto --tb=short \
        --cov=rig_remote --cov-report=term-missing
    ok "Unit tests passed."

    step "Tests — Running functional tests (serial, -n 1, excluding gqrx)"
    "${PYTEST}" functional_tests/ -m "not gqrx" --tb=short -n 1
    ok "Functional tests passed."

    step "Tests — Running gqrx functional tests (need gqrx at 127.0.0.1:7356)"
    if gqrx_reachable; then
        "${PYTEST}" functional_tests/ -m gqrx --tb=short -n 1
        ok "gqrx functional tests passed."
    else
        warn "gqrx functional tests NOT RUN: gqrx is not reachable at 127.0.0.1:7356."
        warn "  Report them as 'not run', never as passed."
    fi
}

build_packages() {
    step "Build — Building sdist + wheel"
    rm -rf dist/ build/
    uv build
    ok "Build complete."
    echo ""
    ls -lh dist/
    check_wheel_contents
}

check_wheel_contents() {
    # Every .py file under src/ must be in the wheel. Guards against package
    # discovery silently dropping a subpackage (it once dropped rig_backends,
    # shipping a wheel that crashed on start). Stdlib only, so CI can run it.
    step "Verify — wheel contains every source module"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)
    "${VENV_BIN}/python" - "${whl}" <<'PYCHECK' || die "The wheel is missing source modules (see above)."
import sys, zipfile
from pathlib import Path

in_wheel = {n for n in zipfile.ZipFile(sys.argv[1]).namelist() if n.endswith(".py")}
in_src = {
    p.relative_to("src").as_posix()
    for p in Path("src").rglob("*.py")
    if not any(part.endswith(".egg-info") or part == "__pycache__" for part in p.parts)
}
missing = sorted(in_src - in_wheel)
for name in missing:
    print(f"  missing from wheel: {name}")
sys.exit(1 if missing else 0)
PYCHECK
    ok "Wheel contains all $(find src -name '*.py' -not -path '*.egg-info*' | wc -l) source modules."
}

build_deb() {
    step "Build — Building Debian package (.deb)"

    if ! command -v dpkg-deb >/dev/null 2>&1 \
       || ! command -v fakeroot >/dev/null 2>&1 \
       || ! command -v lintian  >/dev/null 2>&1; then
        warn "dpkg-deb/fakeroot/lintian not found — skipping .deb build (run on a Debian host)."
        return 0
    fi

    local version
    version=$(read_version)
    local deb_arch
    deb_arch=$(dpkg --print-architecture)
    local deb_staging="deb_staging"
    local deb_file="dist/${PACKAGE_NAME}_${version}_${deb_arch}.deb"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)
    local lib_dir="${deb_staging}/usr/lib/rig-remote"
    local doc_dir="${deb_staging}/usr/share/doc/rig-remote"

    rm -rf "${deb_staging}"
    mkdir -p "${deb_staging}/DEBIAN"
    mkdir -p "${lib_dir}"
    mkdir -p "${deb_staging}/usr/bin"
    mkdir -p "${doc_dir}"
    mkdir -p "${deb_staging}/usr/share/lintian/overrides"

    # Install package + all deps into a private lib dir so the system Python
    # does not need to find them in site-packages or dist-packages.
    uv pip install --target="${lib_dir}" "${whl}"

    # Remove __pycache__ directories (lintian: package-installs-python-pycache-dir)
    find "${lib_dir}" -depth -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    # Remove PySide6/pip-installed developer tools — they carry venv-relative
    # shebangs and are not needed at package runtime
    # (lintian: wrong-path-for-interpreter)
    rm -rf "${lib_dir}/bin"

    # Fix Python shebangs: patch venv-local path and bare 'python' to /usr/bin/python3
    # (lintian: wrong-path-for-interpreter, unusual-interpreter)
    find "${lib_dir}" -type f \( -name "*.py" -o -name "*.pyw" \) -print0 \
        | xargs -0r grep -lZ '^#!.*python' 2>/dev/null \
        | xargs -0r sed -i '1s|^#!.*|#!/usr/bin/python3|' 2>/dev/null \
        || true

    # Strip debug symbols from bundled shared libraries
    # (lintian: unstripped-binary-or-object)
    find "${lib_dir}" -type f -name "*.so*" -exec strip --strip-debug {} + 2>/dev/null || true

    # Write wrapper entry-point scripts that prepend the private lib dir to sys.path.
    cat > "${deb_staging}/usr/bin/rig_remote" <<'WRAPPER'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/usr/lib/rig-remote')
from rig_remote.rig_remote import cli
cli()
WRAPPER

    cat > "${deb_staging}/usr/bin/config_checker" <<'WRAPPER'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/usr/lib/rig-remote')
from config_checker.config_checker import cli
cli()
WRAPPER

    # Changelog (lintian: no-changelog)
    printf 'rig-remote (%s) unstable; urgency=low\n\n  * Release %s.\n\n -- Simone Marzona <marzona@knoway.info>  %s\n' \
        "${version}" "${version}" "$(date -R)" \
        | gzip -9 > "${doc_dir}/changelog.gz"

    # Copyright file (lintian: no-copyright-file)
    cat > "${doc_dir}/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: rig-remote
Upstream-Contact: Simone Marzona <marzona@knoway.info>
Source: https://github.com/Marzona/rig-remote

Files: *
Copyright: $(date +%Y) Simone Marzona <marzona@knoway.info>
License: GPL-3.0+
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 On Debian systems, the complete text of the GNU General Public
 License version 3 can be found in /usr/share/common-licenses/GPL-3.
EOF

    # Lintian overrides for issues inherent to bundling Qt6/PySide6.
    # These cannot be fixed without recompiling Qt from source.
    cat > "${deb_staging}/usr/share/lintian/overrides/rig-remote" <<'OVERRIDES'
# Qt6 embeds system libraries (freetype, lcms2, etc.) — unfixable without
# recompiling Qt from source
rig-remote: embedded-library
# PySide6 ships a private copy of libicu with no separate .so prerequisites
rig-remote: shared-library-lacks-prerequisites
# libicu* carries no strippable debug sections; strip --strip-debug is a no-op
rig-remote: unstripped-binary-or-object
OVERRIDES

    # Derive the Depends field from the shared libraries that the bundled ELF
    # files actually load at runtime.
    #
    # Strategy: run ldd with LD_LIBRARY_PATH pointing to the bundled Qt/PySide6
    # dirs so that internal Qt→Qt deps resolve inside the package and only true
    # system library paths appear in the output.  Then map each system library
    # path to its Debian package via "dpkg -S".  Paths are canonicalised with
    # realpath so that /lib → /usr/lib symlinks (usr-merge) don't confuse dpkg.
    #
    # Qt plugins (sqldrivers, imageformats) and QML compositor plugins are
    # excluded: they have optional system deps (libodbc, libpq, libtiff …) that
    # must not be made hard package requirements.
    local system_libs
    system_libs=$(
        LD_LIBRARY_PATH="${lib_dir}/PySide6:${lib_dir}/PySide6/Qt/lib:${lib_dir}/shiboken6" \
        find "${lib_dir}" -type f \
            ! -path "*/Qt/plugins/*" \
            ! -path "*/Qt/qml/*" \
            -name "*.so*" \
        | xargs ldd 2>/dev/null \
        | awk '{print $3}' \
        | grep -E '^/(lib|usr)' \
        | grep -v "^${lib_dir}" \
        | sort -u
    )
    local shlib_deps=""
    declare -A _seen_pkgs
    while IFS= read -r libpath; do
        [[ -z "${libpath}" ]] && continue
        local canonical
        canonical=$(realpath -q "${libpath}" 2>/dev/null || echo "${libpath}")
        local pkg
        pkg=$(dpkg -S "${canonical}" 2>/dev/null | head -1 | cut -d: -f1 || true)
        [[ -z "${pkg}" ]] && continue
        [[ -v _seen_pkgs["${pkg}"] ]] && continue
        _seen_pkgs["${pkg}"]=1
        shlib_deps="${shlib_deps:+${shlib_deps}, }${pkg}"
    done <<< "${system_libs}"
    unset _seen_pkgs
    [[ -n "${shlib_deps}" ]] || shlib_deps="libc6"

    # The Python Hamlib module (PyPI: Hamlib) is a SWIG wrapper that links
    # against the native libhamlib shared library at runtime.  The .so is not
    # bundled in the wheel, so the package must declare an explicit dependency
    # on the system libhamlib package; otherwise the import fails with a linker
    # error on the end-user machine even though all Python files are present.
    shlib_deps="${shlib_deps}, libhamlib4"

    cat > "${deb_staging}/DEBIAN/control" <<EOF
Package: rig-remote
Version: ${version}
Architecture: ${deb_arch}
Maintainer: Simone Marzona <marzona@knoway.info>
Depends: python3 (>= 3.13), ${shlib_deps}
Section: hamradio
Priority: optional
Homepage: https://github.com/Marzona/rig-remote
Description: Remote control for radio transceivers via RigCtl protocol
 A tool for remotely controlling a radio transceiver using RigCtl protocol
 over TCP/IP. Rig Remote provides frequency scanning, monitoring,
 and frequency bookmarks.
EOF

    # Normalise directory permissions across the entire staging tree
    # (lintian: non-standard-dir-perm, wrong-file-owner-uid-or-gid for dirs)
    find "${deb_staging}" -type d -exec chmod 755 {} +

    # Set all regular files to 644 — removes execute bit from .so files,
    # .lock files, and non-script Python modules
    # (lintian: shared-library-is-executable, non-standard-file-perm,
    #   odd-permissions-on-shared-library, executable-not-elf-or-script)
    find "${deb_staging}" -type f -exec chmod 644 {} +

    # Restore execute bit on the two entry-point wrapper scripts
    chmod 755 "${deb_staging}/usr/bin/rig_remote" "${deb_staging}/usr/bin/config_checker"

    # fakeroot ensures root:root ownership in the archive
    # (lintian: wrong-file-owner-uid-or-gid)
    fakeroot dpkg-deb --build "${deb_staging}" "${deb_file}"
    rm -rf "${deb_staging}"
    ok "Debian package: $(basename "${deb_file}")"

    # Verify the package — fail the build if lintian reports any errors
    step "Lintian — Checking $(basename "${deb_file}")"
    local lintian_output
    lintian_output=$(lintian --tag-display-limit 0 "${deb_file}" 2>&1) || true
    if [[ -n "${lintian_output}" ]]; then
        echo "${lintian_output}"
    fi
    if echo "${lintian_output}" | grep -q '^E:'; then
        die "Lintian reported errors in $(basename "${deb_file}")."
    fi
    ok "Lintian: no errors."
}

build_arch() {
    step "Build — Building Arch package (.pkg.tar.zst)"

    # Same skip-if-toolchain-absent contract as build_deb: one release.sh can run
    # on either a Debian or an Arch build host and produces whichever package the
    # host can build.
    if ! command -v makepkg >/dev/null 2>&1; then
        warn "makepkg not found — skipping Arch build (run on an Arch host)."
        return 0
    fi
    if ! python -c 'import build, installer' >/dev/null 2>&1; then
        warn "python-build/python-installer not found — skipping Arch build."
        warn "  sudo pacman -S --needed python-build python-installer python-wheel python-setuptools"
        return 0
    fi

    local version
    version=$(grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
    local arch_staging="arch_staging"

    rm -rf "${arch_staging}"
    mkdir -p "${arch_staging}"

    # Snapshot the committed tree for makepkg to build from — the same idea as
    # build_deb packaging the current checkout rather than a remote tag.
    git archive --format=tar.gz \
        --prefix="${PACKAGE_NAME}-${version}/" \
        -o "${arch_staging}/${PACKAGE_NAME}-${version}.tar.gz" HEAD

    # Generate the PKGBUILD programmatically — nothing Arch-specific is committed
    # to the repo (same philosophy as build_deb generating DEBIAN/control on the
    # fly).  Runtime deps are system packages rather than bundled: this is the
    # Arch counterpart to the .deb's "Depends: ... libhamlib4".
    #   hamlib  ships the Hamlib Python SWIG bindings (Hamlib.py + _Hamlib.so) in
    #           the system site-packages, which the app imports directly.  A venv
    #           cannot see them; a system package installs alongside them.
    #   pyside6 provides the Qt6 GUI bindings.
    cat > "${arch_staging}/PKGBUILD" <<PKGBUILD
# Generated by release.sh build_arch() — do not commit.
pkgname=${PACKAGE_NAME}
pkgver=${version}
pkgrel=1
pkgdesc="Remotely control a radio transceiver over RigCtl/Hamlib: scanning, monitoring, bookmarks"
arch=('any')
url="https://github.com/Marzona/rig-remote"
license=('MIT')
depends=('python' 'hamlib' 'pyside6')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("\$pkgname-\$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "\$srcdir/\$pkgname-\$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "\$srcdir/\$pkgname-\$pkgver"
    python -m installer --destdir="\$pkgdir" dist/*.whl
    install -Dm644 LICENSE "\$pkgdir/usr/share/licenses/\$pkgname/LICENSE"
}
PKGBUILD

    # Runtime deps (hamlib, pyside6) are not needed to build the pure-Python
    # wheel, so --nodeps keeps Qt off the build host; pacman resolves them at
    # install time from the depends=() array above.
    ( cd "${arch_staging}" && makepkg --nodeps --skipinteg --force )

    mkdir -p dist
    mv "${arch_staging}"/*.pkg.tar.zst dist/
    rm -rf "${arch_staging}"

    local pkg_file
    pkg_file=$(ls -1 dist/*.pkg.tar.zst | sort -V | tail -1)
    ok "Arch package: $(basename "${pkg_file}")"

    # Verify with namcap if available — the Arch analogue of the .deb's lintian.
    if command -v namcap >/dev/null 2>&1; then
        step "namcap — Checking $(basename "${pkg_file}")"
        namcap "${pkg_file}" || true
    else
        warn "namcap not installed — skipping package lint (sudo pacman -S namcap)."
    fi
}

install_local() {
    # Install the built wheel into a fresh, throwaway venv (not .venv, which
    # holds the editable dev install) and run both entry points, so the test
    # exercises the packaged files rather than src/.
    step "Local install — Installing wheel in a clean venv (smoke test)"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)
    SMOKE_VENV=$(mktemp -d)
    uv venv --quiet --python "$("${VENV_BIN}/python" -c 'import sys; print(sys.executable)')" "${SMOKE_VENV}"
    uv pip install --quiet --python "${SMOKE_VENV}/bin/python" "${whl}"
    QT_QPA_PLATFORM=offscreen "${SMOKE_VENV}/bin/rig_remote" --help >/dev/null \
        || die "Installed wheel: 'rig_remote --help' failed."
    "${SMOKE_VENV}/bin/config_checker" --help >/dev/null \
        || die "Installed wheel: 'config_checker --help' failed."
    ok "Installed $(basename "${whl}"); rig_remote and config_checker start."
}

uninstall_local() {
    step "Local install — Removing the smoke-test venv"
    rm -rf "${SMOKE_VENV:?}"
    ok "Smoke-test venv removed."
}

check_packages() {
    # Local metadata validation only (README rendering, required fields).
    # Same check CI runs before publishing; nothing is sent anywhere.
    step "Verify — twine check --strict"
    "${TWINE}" check --strict dist/*.whl dist/*.tar.gz
    ok "Package metadata is valid."
}

# ---------------------------------------------------------------------------
# Release — step functions (no network, no upload)
# ---------------------------------------------------------------------------
generate_release_notes() {
    step "Release notes — Generating release_message.md"
    local version
    version=$(read_version)
    local last_tag
    last_tag=$(git tag --sort=-version:refname 2>/dev/null | head -1 || echo "")

    {
        printf '# Release %s\n\n' "${version}"
        printf 'Released on %s\n\n' "$(date +%Y-%m-%d)"
        printf '## Changes\n\n'
        if [[ -n "${last_tag}" ]]; then
            git log "${last_tag}..HEAD" --pretty=format:"- %s" 2>/dev/null || git log --pretty=format:"- %s"
        else
            git log --pretty=format:"- %s"
        fi
        printf '\n\n## Packages\n\n'
        ls dist/ | sed 's/^/- /'
    } > release_message.md

    ok "Release notes written to release_message.md"
}

print_handoff() {
    local version
    version=$(read_version)
    step "Hand-off — publishing is done by CI, not by this script"
    echo -e "  Verified artefacts are in ${BOLD}dist/${NC}. To publish ${BOLD}${version}${NC}, a human:"
    echo -e "    1. reviews and pushes the release commit"
    echo -e "    2. ${BOLD}git tag v${version} && git push origin v${version}${NC}"
    if [[ "${version}" =~ \.dev[0-9]+$ ]]; then
        echo -e "  ${version} is a .devN version: CI publishes it to ${BOLD}TestPyPI only${NC}."
    else
        echo -e "    3. approves the ${BOLD}pypi${NC} deployment in GitHub Actions (${RELEASE_WORKFLOW})"
    fi
}

# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
stage_package() {
    echo -e "${BOLD}Stage: PACKAGE${NC}"
    build_packages
    build_deb
}

stage_commit_push() {
    echo -e "${BOLD}Stage: COMMIT_PUSH${NC}"
    check_lock
    run_static_analysis
    run_tests
    build_packages
    build_deb
    build_arch
    check_packages
    install_local
    uninstall_local
}

stage_release() {
    echo -e "${BOLD}Stage: RELEASE${NC}"
    stage_commit_push
    generate_release_notes
    print_handoff
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local stage="${1:-}"
    if [[ -z "${stage}" ]]; then
        die "Usage: $0 <stage>  (stages: package, commit_push, release)"
    fi

    preflight

    MYPY="${VENV_BIN}/mypy"
    RUFF="${VENV_BIN}/ruff"
    PYTEST="${VENV_BIN}/pytest"
    TWINE="${VENV_BIN}/twine"

    case "${stage}" in
        package)      stage_package ;;
        commit_push)  stage_commit_push ;;
        release)      stage_release ;;
        publish_test|publish)
            die "Stage '${stage}' was removed: release.sh no longer uploads. Run './release.sh release', then push a v<version> tag; ${RELEASE_WORKFLOW} publishes after human approval." ;;
        *) die "Unknown stage '${stage}'. Valid stages: package, commit_push, release" ;;
    esac

    echo ""
    echo -e "${GREEN}${BOLD}Stage '${stage}' complete.${NC}"
}

main "$@"

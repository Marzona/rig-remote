#!/usr/bin/env bash
# release.sh — automated release pipeline for rig-remote
#
# Usage:  ./release.sh <stage>
#
# Stages (each includes all steps of the previous):
#   commit_push   : tests, functional tests, lint, type check, format,
#                   build pip + .deb. No upload.
#   publish_test  : commit_push, then upload to TestPyPI.
#   publish       : publish_test, then upload to production PyPI and
#                   generate release_message.md.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV_BIN=".venv/bin"
PACKAGE_NAME="rig-remote"
TESTPYPI_URL="https://test.pypi.org/project/rig-remote/"
PYPI_URL="https://pypi.org/project/rig-remote/"

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

confirm() {
    local prompt="$1"
    local reply
    echo -e "${YELLOW}${prompt}${NC}"
    read -r -p "$(echo -e "${BOLD}[y/N]: ${NC}")" reply
    [[ "${reply,,}" == "y" ]]
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
run_tests() {
    step "Tests — Running unit tests (parallel)"
    "${PYTEST}" tests/ --tb=short \
        --cov=rig_remote --cov-report=term-missing
    ok "Unit tests passed."

    step "Tests — Running functional/integration tests (serial, -n 1)"
    "${PYTEST}" functional_tests/ --tb=short -n 1
    ok "Functional tests passed."
}

run_static_analysis() {
    step "Static analysis — mypy"
    "${MYPY}" --config-file ./pyproject.toml ./src
    ok "mypy: no issues."

    step "Static analysis — ruff lint"
    "${RUFF}" check --fix ./src/rig_remote/
    ok "ruff lint: no issues."

    step "Static analysis — ruff format"
    "${RUFF}" format ./src/rig_remote/
    ok "ruff format: done."
}

build_packages() {
    step "Build — Building sdist + wheel"
    rm -rf dist/ build/
    uv build
    ok "Build complete."
    echo ""
    ls -lh dist/
}

build_deb() {
    step "Build — Building Debian package (.deb)"

    command -v fakeroot >/dev/null 2>&1 \
        || die "fakeroot is required: sudo apt-get install fakeroot"
    command -v lintian  >/dev/null 2>&1 \
        || die "lintian is required: sudo apt-get install lintian"

    local version
    version=$(grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
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

install_local() {
    step "Local install — Installing wheel (smoke test)"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)
    uv pip install "${whl}"
    ok "Installed: $(basename "${whl}")"
}

uninstall_local() {
    step "Local install — Removing locally installed package"
    uv pip uninstall "${PACKAGE_NAME}"
    ok "Package '${PACKAGE_NAME}' uninstalled."
}

# ---------------------------------------------------------------------------
# Stage 2 — step functions
# ---------------------------------------------------------------------------
upgrade_twine() {
    step "Twine — Upgrading"
    uv pip install --upgrade twine
    ok "twine is up to date."
}

upload_testpypi() {
    step "TestPyPI — Uploading"
    "${TWINE}" upload --verbose --repository testpypi dist/*.whl dist/*.tar.gz
    echo ""
    echo -e "  ${BOLD}TestPyPI package URL:${NC}"
    echo -e "  ${BLUE}${TESTPYPI_URL}${NC}"
    ok "TestPyPI upload complete."
}

# ---------------------------------------------------------------------------
# Stage 3 — step functions
# ---------------------------------------------------------------------------
upload_pypi() {
    step "Production PyPI — Upload"
    echo ""
    echo -e "  Package : ${BOLD}${PACKAGE_NAME}${NC}"
    echo -e "  URL     : ${BLUE}${PYPI_URL}${NC}"
    echo ""

    if confirm "Upload to production PyPI?"; then
        "${TWINE}" upload dist/*.whl dist/*.tar.gz
        echo ""
        echo -e "  ${BOLD}PyPI package URL:${NC}"
        echo -e "  ${BLUE}${PYPI_URL}${NC}"
        ok "Production PyPI upload complete."
    else
        warn "Production upload skipped."
    fi
}

generate_release_notes() {
    step "Release notes — Generating release_message.md"
    local version
    version=$(grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
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

# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------
stage_commit_push() {
    echo -e "${BOLD}Stage: COMMIT_PUSH${NC}"
    run_tests
    run_static_analysis
    build_packages
    build_deb
    install_local
    uninstall_local
}

stage_publish_test() {
    echo -e "${BOLD}${YELLOW}Stage: PUBLISH_TEST${NC}"
    stage_commit_push
    upgrade_twine
    upload_testpypi
}

stage_publish() {
    echo -e "${BOLD}${YELLOW}Stage: PUBLISH${NC}"
    stage_publish_test
    upload_pypi
    generate_release_notes
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local stage="${1:-}"
    if [[ -z "${stage}" ]]; then
        die "Usage: $0 <stage>  (stages: commit_push, publish_test, publish)"
    fi

    preflight

    MYPY="${VENV_BIN}/mypy"
    RUFF="${VENV_BIN}/ruff"
    PYTEST="${VENV_BIN}/pytest"
    TWINE="${VENV_BIN}/twine"

    case "${stage}" in
        commit_push)  stage_commit_push ;;
        publish_test) stage_publish_test ;;
        publish)      stage_publish ;;
        *) die "Unknown stage '${stage}'. Valid stages: commit_push, publish_test, publish" ;;
    esac

    echo ""
    echo -e "${GREEN}${BOLD}Stage '${stage}' complete.${NC}"
}

main "$@"

#!/usr/bin/env bash
# release.sh — automated release pipeline for rig-remote
#
# Usage:  ./release.sh [--publish|-p]
#
# Without --publish: runs tests, lints, mypy, TestPyPI upload,
#                    local install/uninstall, and .deb generation.
# With    --publish: also uploads to production PyPI.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV_BIN=".venv/bin"
PACKAGE_NAME="rig-remote"
TESTPYPI_URL="https://test.pypi.org/project/rig-remote/"
PYPI_URL="https://pypi.org/project/rig-remote/"
PUBLISH=false

# ---------------------------------------------------------------------------
# Helpers
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
# Argument parsing
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --publish|-p) PUBLISH=true ;;
            *) die "Unknown argument: $1. Usage: $0 [--publish|-p]" ;;
        esac
        shift
    done
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
preflight() {
    [[ -f pyproject.toml ]] || die "Must be run from the directory containing pyproject.toml."
    [[ -d "${VENV_BIN}" ]]  || die "Virtual environment not found at ${VENV_BIN}/. Run 'uv sync --group dev' first."
}

# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------
run_tests() {
    step "Tests — Running unit tests (parallel)"
    "${PYTEST}" tests/ --tb=short
    ok "Unit tests passed."

    step "Tests — Running functional/integration tests (serial, -n 1)"
    "${PYTEST}" integration/ --tb=short -n 1
    ok "Functional tests passed."
}

run_static_analysis() {
    step "Static analysis — mypy"
    "${MYPY}" --config-file ./pyproject.toml ./src
    ok "mypy: no issues."

    step "Static analysis — ruff"
    "${RUFF}" check --fix ./src/rig_remote/
    ok "ruff: no issues."
}

update_requirements() {
    step "Requirements — Regenerating requirements.txt"
    uv pip compile pyproject.toml -o requirements.txt
    ok "requirements.txt regenerated."

    if ! git diff --quiet requirements.txt; then
        git add requirements.txt
        git commit -m "chore: update requirements.txt for release"
        ok "requirements.txt committed."
    else
        warn "requirements.txt unchanged — no commit needed."
    fi
}

build_packages() {
    step "Build — Building sdist + wheel"
    rm -rf dist/ build/
    "${PYTHON}" -m build
    ok "Build complete."
    echo ""
    ls -lh dist/
}

build_deb() {
    step "Build — Building Debian package (.deb)"

    local version
    version=$(grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
    local deb_arch
    deb_arch=$(dpkg --print-architecture)
    local deb_staging="deb_staging"
    local deb_file="dist/${PACKAGE_NAME}_${version}_${deb_arch}.deb"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)

    rm -rf "${deb_staging}"
    mkdir -p "${deb_staging}/DEBIAN"

    "${PIP}" install --prefix="${deb_staging}/usr" --no-deps "${whl}"

    cat > "${deb_staging}/DEBIAN/control" <<EOF
Package: rig-remote
Version: ${version}
Architecture: ${deb_arch}
Maintainer: Simone Marzona <marzona@knoway.info>
Depends: python3 (>= 3.13), python3-pyside6
Section: hamradio
Priority: optional
Homepage: https://github.com/Marzona/rig-remote
Description: Remote control for radio transceivers via RigCtl protocol
 A tool for remotely controlling a radio transceiver using RigCtl protocol
 over TCP/IP. Rig Remote provides frequency scanning, monitoring,
 and frequency bookmarks.
EOF

    dpkg-deb --build "${deb_staging}" "${deb_file}"
    rm -rf "${deb_staging}"
    ok "Debian package: $(basename "${deb_file}")"
}

install_local() {
    step "Local install — Installing wheel (smoke test)"
    local whl
    whl=$(ls dist/*.whl | sort -V | tail -1)
    "${PIP}" install "${whl}"
    ok "Installed: $(basename "${whl}")"
}

uninstall_local() {
    step "Local install — Removing locally installed package"
    "${PIP}" uninstall -y "${PACKAGE_NAME}"
    ok "Package '${PACKAGE_NAME}' uninstalled."
}

upgrade_twine() {
    step "Twine — Upgrading"
    "${PIP}" install --upgrade twine
    ok "twine is up to date."
}

upload_testpypi() {
    step "TestPyPI — Uploading"
    "${TWINE}" upload --repository testpypi dist/*
    echo ""
    echo -e "  ${BOLD}TestPyPI package URL:${NC}"
    echo -e "  ${BLUE}${TESTPYPI_URL}${NC}"
    ok "TestPyPI upload complete."
}

upload_pypi() {
    step "Production PyPI — Upload"
    echo ""
    echo -e "  Package : ${BOLD}${PACKAGE_NAME}${NC}"
    echo -e "  URL     : ${BLUE}${PYPI_URL}${NC}"
    echo ""

    if confirm "Upload to production PyPI?"; then
        "${TWINE}" upload dist/*
        echo ""
        echo -e "  ${BOLD}PyPI package URL:${NC}"
        echo -e "  ${BLUE}${PYPI_URL}${NC}"
        ok "Production PyPI upload complete."
    else
        warn "Production upload skipped."
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"
    preflight

    PYTHON="${VENV_BIN}/python3"
    PIP="${VENV_BIN}/pip"
    MYPY="${VENV_BIN}/mypy"
    RUFF="${VENV_BIN}/ruff"
    PYTEST="${VENV_BIN}/pytest"
    TWINE="${VENV_BIN}/twine"

    if "${PUBLISH}"; then
        echo -e "${BOLD}${YELLOW}Mode: PUBLISH (production PyPI upload enabled)${NC}"
    else
        echo -e "${BOLD}Mode: BETA (TestPyPI only)${NC}"
    fi

    run_tests
    run_static_analysis
    update_requirements
    build_packages
    build_deb
    install_local
    upgrade_twine
    upload_testpypi
    uninstall_local

    if "${PUBLISH}"; then
        upload_pypi
    fi

    echo ""
    echo -e "${GREEN}${BOLD}Release pipeline complete.${NC}"
}

main "$@"

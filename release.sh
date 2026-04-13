#!/usr/bin/env bash
# release.sh — automated release pipeline for rig-remote
#
# Usage:  ./release.sh
# Run from the directory that contains pyproject.toml.
#
# Steps:
#   1.  Run unit + functional tests
#   2.  Run mypy and ruff
#   3.  Regenerate requirements.txt and commit if changed
#   4.  Push local commits
#   5.  Build sdist + wheel
#   6.  Install the wheel locally (smoke-test the package)
#   7.  Upgrade twine
#   8.  Upload to TestPyPI
#   9.  Confirm, then upload to production PyPI
#   10. Remove the locally installed package

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV_BIN=".venv/bin"
PACKAGE_NAME="rig-remote"
TESTPYPI_URL="https://test.pypi.org/project/rig-remote/"
PYPI_URL="https://pypi.org/project/rig-remote/"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${BLUE}==> Step $1${NC}"; }
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

[[ -f pyproject.toml ]] || die "Must be run from the directory containing pyproject.toml."
[[ -d "${VENV_BIN}" ]]  || die "Virtual environment not found at ${VENV_BIN}/. Run 'uv sync --group dev' first."

PYTHON="${VENV_BIN}/python3"
PIP="${VENV_BIN}/pip"
MYPY="${VENV_BIN}/mypy"
RUFF="${VENV_BIN}/ruff"
PYTEST="${VENV_BIN}/pytest"
TWINE="${VENV_BIN}/twine"

# ---------------------------------------------------------------------------
# 1. Tests
# ---------------------------------------------------------------------------
step "1/10 — Running tests (unit + functional)"
"${PYTEST}" --tb=short
ok "All tests passed."

# ---------------------------------------------------------------------------
# 2. Static analysis
# ---------------------------------------------------------------------------
step "2/10 — Running mypy"
"${MYPY}" --config-file ./pyproject.toml ./src
ok "mypy: no issues."

step "2/10 — Running ruff"
"${RUFF}" check ./src/rig_remote/
ok "ruff: no issues."

# ---------------------------------------------------------------------------
# 3. Update requirements.txt
# ---------------------------------------------------------------------------
step "3/10 — Regenerating requirements.txt"
uv pip compile pyproject.toml -o requirements.txt
ok "requirements.txt regenerated."

if ! git diff --quiet requirements.txt; then
    git add requirements.txt
    git commit -m "chore: update requirements.txt for release"
    ok "requirements.txt committed."
else
    warn "requirements.txt unchanged — no commit needed."
fi

# ---------------------------------------------------------------------------
# 4. Push
# ---------------------------------------------------------------------------
step "4/10 — Pushing local commits"
git push
ok "Push complete."

# ---------------------------------------------------------------------------
# 5. Build
# ---------------------------------------------------------------------------
step "5/10 — Building distribution packages"
rm -rf dist/ build/
"${PYTHON}" -m build
ok "Build complete."
echo ""
ls -lh dist/

# ---------------------------------------------------------------------------
# 6. Install locally
# ---------------------------------------------------------------------------
step "6/10 — Installing wheel locally (smoke test)"
WHL=$(ls dist/*.whl | sort -V | tail -1)
"${PIP}" install "${WHL}"
ok "Installed: $(basename "${WHL}")"

# ---------------------------------------------------------------------------
# 7. Upgrade twine
# ---------------------------------------------------------------------------
step "7/10 — Upgrading twine"
"${PIP}" install --upgrade twine
ok "twine is up to date."

# ---------------------------------------------------------------------------
# 8. Upload to TestPyPI
# ---------------------------------------------------------------------------
step "8/10 — Uploading to TestPyPI"
"${TWINE}" upload --repository testpypi dist/*
echo ""
echo -e "  ${BOLD}TestPyPI package URL:${NC}"
echo -e "  ${BLUE}${TESTPYPI_URL}${NC}"
ok "TestPyPI upload complete."

# ---------------------------------------------------------------------------
# 9. Production PyPI (requires confirmation)
# ---------------------------------------------------------------------------
step "9/10 — Production PyPI upload"
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

# ---------------------------------------------------------------------------
# 10. Remove local installation
# ---------------------------------------------------------------------------
step "10/10 — Removing locally installed package"
"${PIP}" uninstall -y "${PACKAGE_NAME}"
ok "Package '${PACKAGE_NAME}' uninstalled."

echo ""
echo -e "${GREEN}${BOLD}Release pipeline complete.${NC}"

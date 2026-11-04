#!/usr/bin/env bash
# Run the verification suite for the uncommitted change in a disposable git
# worktree, so code from the diff never runs in the real checkout or with the
# developer's credentials. Layers: throwaway worktree, scrubbed environment
# (env -i), and no network for the test runs when `unshare -rn` works.
# `uv sync` needs network, so it runs first; tests run afterwards offline.
# Exit status is non-zero if any check fails.
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "${repo_root}"

work=$(mktemp -d "${TMPDIR:-/tmp}/rig-review.XXXXXX")
wt="${work}/wt"
home="${work}/home"
mkdir -p "${home}"

cleanup() {
    git -C "${repo_root}" worktree remove --force "${wt}" >/dev/null 2>&1 || true
    git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
    # ${work} now holds only the empty-ish home dir created above; guard the path.
    case "${work}" in
        */rig-review.*) [[ -d "${work}" ]] && rm -r -- "${work}/home" 2>/dev/null; rmdir -- "${work}" 2>/dev/null || true ;;
    esac
}
trap cleanup EXIT

git worktree add --detach "${wt}" HEAD >/dev/null

# Uncommitted tracked changes (staged and unstaged) ...
if ! git diff HEAD --binary --quiet; then
    git diff HEAD --binary | git -C "${wt}" apply --whitespace=nowarn
fi
# ... plus untracked, non-ignored files, copied deliberately.
if [[ -n "$(git ls-files --others --exclude-standard | head -n 1)" ]]; then
    git ls-files -z --others --exclude-standard | tar --null -T - -cf - | tar -C "${wt}" -xf -
fi

uv_cache=$(uv cache dir 2>/dev/null || true)
clean_env=(env -i "PATH=${PATH}" "HOME=${home}" "LANG=${LANG:-C.UTF-8}"
    "QT_QPA_PLATFORM=offscreen" "UV_CACHE_DIR=${uv_cache:-${home}/.uv-cache}")

echo "== uv sync --locked --group dev (network allowed) =="
(cd "${wt}" && "${clean_env[@]}" uv sync --locked --group dev)

# Offline runner: loopback is brought up inside the namespace because the
# functional tests use 127.0.0.1 fakes.
if unshare -rn true 2>/dev/null; then
    isolation="network namespace (unshare -rn)"
    run() {
        (cd "${wt}" && unshare -rn "${clean_env[@]}" bash -c \
            'command -v ip >/dev/null && ip link set lo up 2>/dev/null; exec "$@"' _ "$@")
    }
else
    isolation="NONE"
    echo "NOTICE: 'unshare -rn' is unavailable; tests run WITH network access" \
         "(credentials are still scrubbed via env -i)." >&2
    run() { (cd "${wt}" && "${clean_env[@]}" "$@"); }
fi
echo "== network isolation for test runs: ${isolation} =="

failed=()
check() {
    local name=$1
    shift
    echo "== ${name} =="
    if run "$@"; then
        echo "-- ${name}: PASS"
    else
        echo "-- ${name}: FAIL" >&2
        failed+=("${name}")
    fi
}

check "ruff check" .venv/bin/ruff check ./src
check "ruff format --check" .venv/bin/ruff format --check ./src
check "mypy" .venv/bin/mypy --config-file ./pyproject.toml ./src
check "pytest tests (coverage)" .venv/bin/pytest tests/ -n auto -p no:cacheprovider \
    --cov=rig_remote --cov=config_checker --cov-report=term-missing
check "functional (not gqrx)" .venv/bin/pytest functional_tests/ -n 1 -m "not gqrx" -p no:cacheprovider
# gqrx needs a live server, unreachable offline: skips are reported as NOT RUN.
check "functional (gqrx; skips = NOT RUN)" .venv/bin/pytest functional_tests/ -n 1 -m gqrx -rs -p no:cacheprovider

echo
if ((${#failed[@]})); then
    echo "FAILED: ${failed[*]}" >&2
    exit 1
fi
echo "All checks passed (isolation: ${isolation})."

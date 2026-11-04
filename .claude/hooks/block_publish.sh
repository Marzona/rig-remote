#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) — blocks package publishing from Claude Code.
#
# Publishing rig-remote is done only by .github/workflows/release.yml after a
# human pushes a v<version> tag and approves the "pypi" environment. Agents
# (including release_agent) must stop at built, verified artefacts in dist/.
#
# Reads the hook JSON on stdin; exit 2 blocks the call and shows stderr to
# the model. Fails closed: a missing jq or any unexpected error exits 2.
# Known limit: command matching cannot stop obfuscation such as
#   bash -c "tw""ine upload x"
# This is a guard rail, not a sandbox. The real controls are: no PyPI
# credentials on the machine, OIDC Trusted Publishing in CI, and the required
# reviewer on the "pypi" environment.
# Tests: tests/test_hooks.py
set -Eeuo pipefail
trap 'echo "block_publish.sh: internal error, blocking to stay safe." >&2; exit 2' ERR

if ! command -v jq >/dev/null 2>&1; then
    echo "block_publish.sh: jq is required to inspect commands; blocking until it is installed." >&2
    exit 2
fi

command=$(jq -r '.tool_input.command // empty')
[[ -z "${command}" ]] && exit 0

# Each entry: extended regex (matched case-insensitively) | reason.
rules=(
    'twine([^;&|]*[[:space:]])?upload([[:space:]]|$)|twine upload'
    '(^|[^[:alnum:]_-])(uv|poetry|hatch|flit|pdm)[[:space:]]+publish([[:space:]]|$)|package publish command'
    'gh-action-pypi-publish|PyPI publish action'
    '(upload|test)\.pypi\.org|/legacy/?([[:space:]"'"'"']|$)|direct PyPI upload endpoint'
    '\.pypirc|PyPI credentials file'
    '(TWINE_(USERNAME|PASSWORD|REPOSITORY)|UV_PUBLISH_|PYPI_(API_)?TOKEN)|PyPI credentials in environment'
    'release\.sh[[:space:]]+(publish|publish_test)([[:space:]]|$)|release.sh publish stage'
    'git[[:space:]].*push.*(--tags|--follow-tags|--mirror|refs/tags/|[[:space:]]v[0-9]|[[:space:]]tag[[:space:]])|pushing a release tag (triggers the publish workflow)'
    'gh[[:space:]]+(release[[:space:]]+create|workflow[[:space:]]+run)|creating a GitHub release / dispatching a workflow'
    '(gh[[:space:]]+api|api\.github\.com)[^;&|]*(/dispatches|/git/refs|/git/tags|/releases)|GitHub API call that creates tags or releases, or dispatches a workflow'
)

shopt -s nocasematch
for rule in "${rules[@]}"; do
    pattern="${rule%|*}"
    reason="${rule##*|}"
    if [[ "${command}" =~ ${pattern} ]]; then
        cat >&2 <<EOF
Blocked by .claude/hooks/block_publish.sh: ${reason}.
Agents must not publish packages. Stop at built, verified artefacts
(./release.sh release) and hand off to a human, who pushes the v<version>
tag and approves the "pypi" deployment of .github/workflows/release.yml.
EOF
        exit 2
    fi
done
exit 0

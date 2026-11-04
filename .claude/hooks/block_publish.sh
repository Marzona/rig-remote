#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) — blocks package publishing from Claude Code.
#
# Publishing rig-remote is done only by .github/workflows/release.yml after a
# human pushes a v<version> tag and approves the "pypi" environment. Agents
# (including release_agent) must stop at built, verified artefacts in dist/.
#
# Reads the hook JSON on stdin; exit 2 blocks the call and shows stderr to
# the model. This is a guard rail, not a sandbox: the real control is that no
# PyPI credentials exist on the machine (CI uses OIDC Trusted Publishing).
set -euo pipefail

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
    'git[[:space:]].*push.*(--tags|--follow-tags|refs/tags/|[[:space:]]v[0-9])|pushing a release tag (triggers the publish workflow)'
    'gh[[:space:]]+(release[[:space:]]+create|workflow[[:space:]]+run)|creating a GitHub release / dispatching a workflow'
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

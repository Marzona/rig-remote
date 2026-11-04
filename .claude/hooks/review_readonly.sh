#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) for code_review_agent — keeps the reviewer
# read-only in practice. Every command segment must start with an allowlisted
# read-only command; redirections, command substitution and in-place edits are
# rejected. Exit 2 blocks the call and shows stderr to the agent.
set -euo pipefail

command=$(jq -r '.tool_input.command // empty')
[[ -z "${command}" ]] && exit 0

block() {
    printf 'Blocked by .claude/hooks/review_readonly.sh: %s\nThe reviewer is read-only: report the finding with a before/after instead of changing anything.\n' "$1" >&2
    exit 2
}

# Command substitution can hide arbitrary commands, even inside double quotes.
[[ "${command}" == *'$('* || "${command}" == *'`'* ]] && block "command substitution"

# Drop quoted strings so patterns such as grep -E 'a|b' are not split below.
stripped=$(sed -E "s/'[^']*'/Q/g; s/\"[^\"]*\"/Q/g" <<< "${command}")

# Only harmless redirections: 2>&1, >/dev/null, 2>/dev/null.
no_ok_redirects=$(sed -E 's#[0-9]?>&[0-9]##g; s#[0-9]?>[[:space:]]*/dev/null##g' <<< "${stripped}")
[[ "${no_ok_redirects}" == *'>'* ]] && block "output redirection"

allowed='^(git[[:space:]]+(diff|log|show|status|blame|ls-files|rev-parse|merge-base|grep)'
allowed+='|((\.venv/bin/|uv[[:space:]]+run[[:space:]]+(--no-sync[[:space:]]+)?)?(mypy|pytest))'
allowed+='|((\.venv/bin/|uv[[:space:]]+run[[:space:]]+(--no-sync[[:space:]]+)?)?ruff[[:space:]]+(check|format[[:space:]].*--(check|diff)))'
allowed+='|xargs([[:space:]]+-[[:alnum:]]+)*[[:space:]]+(wc|grep|cat|head|tail|ls)'
allowed+='|grep|rg|cat|head|tail|wc|ls|find|sort|uniq|cut|tr|diff|echo|true|pwd|sed[[:space:]]+-n|cd)([[:space:]]|$)'

forbidden='(--fix|--unsafe-fixes|[[:space:]]-i([[:space:]]|$)|--in-place|-delete|-exec|-execdir|-fprint|-ok|--output)'

while IFS= read -r segment; do
    segment="${segment#"${segment%%[![:space:]]*}"}"
    [[ -z "${segment}" ]] && continue
    [[ "${segment}" =~ ${allowed} ]] || block "'${segment%% *}' is not on the reviewer's read-only allowlist"
    [[ "${segment}" =~ ${forbidden} ]] && block "a modifying flag in '${segment}'"
done < <(sed -E 's/(&&|\|\||;|\|)/\n/g' <<< "${stripped}")

exit 0

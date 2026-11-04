#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash) for code_review_agent — keeps the reviewer
# read-only in practice. Exit 2 blocks the call and shows stderr to the agent.
#
#  1. Lex the command: quoted text stays visible (so flags inside quotes are
#     still checked) but shell operators inside quotes are neutralised;
#     command substitution, backticks and process substitution are rejected.
#  2. Reject every output redirection except 2>&1-style dups and /dev/null.
#  3. Split on ; & | and newlines; every segment must start with an
#     allowlisted command and pass that command's own flag rules.
#
# Fails closed: a missing jq or any unexpected error exits 2.
# Known limits: this is a second layer, not a sandbox. pytest and mypy
# execute/import code from the diff by design, so run tests in the disposable
# worktree flow (scripts/review_worktree.sh). sed and uniq are not allowed at
# all (sed scripts can write/execute; uniq's 2nd operand is an output file):
# the reviewer has the Read and Grep tools instead.
# Tests: tests/test_hooks.py
set -Eeuo pipefail
trap 'echo "review_readonly.sh: internal error, blocking to stay safe." >&2; exit 2' ERR

if ! command -v jq >/dev/null 2>&1; then
    echo "review_readonly.sh: jq is required to inspect commands; blocking until it is installed." >&2
    exit 2
fi

command=$(jq -r '.tool_input.command // empty')
[[ -z "${command}" ]] && exit 0

block() {
    printf 'Blocked by .claude/hooks/review_readonly.sh: %s\nThe reviewer is read-only: report the finding with a before/after instead of changing anything.\n' "$1" >&2
    exit 2
}

# --- 1. Lex ---------------------------------------------------------------
neutral=""
quote=""
len=${#command}
i=0
while (( i < len )); do
    c="${command:i:1}"
    next="${command:i+1:1}"
    if [[ -n "${quote}" ]]; then
        if [[ "${c}" == "${quote}" ]]; then
            quote=""
        elif [[ "${quote}" == '"' && ( "${c}" == '`' || ( "${c}" == '$' && "${next}" == '(' ) ) ]]; then
            block "command substitution"
        elif [[ "${quote}" == '"' && "${c}" == '\' ]]; then
            neutral+="_"
            i=$((i + 1))
        elif [[ "${c}" == [\;\&\|\<\>\(\)] ]]; then
            neutral+=" "
        else
            neutral+="${c}"
        fi
    else
        case "${c}" in
            "'" | '"') quote="${c}" ;;
            '\') neutral+="_"; i=$((i + 1)) ;;
            '`') block "command substitution" ;;
            '$')
                if [[ "${next}" == '(' ]]; then block "command substitution"; fi
                neutral+="${c}" ;;
            '<' | '>')
                if [[ "${next}" == '(' ]]; then block "process substitution"; fi
                neutral+="${c}" ;;
            *) neutral+="${c}" ;;
        esac
    fi
    i=$((i + 1))
done
if [[ -n "${quote}" ]]; then block "unbalanced quotes"; fi

# --- 2. Redirections ------------------------------------------------------
without_ok=$(sed -E 's#&>>?[[:space:]]*/dev/null##g; s#[0-9]*>&[0-9-]+##g; s#[0-9]*>>?[[:space:]]*/dev/null##g' <<< "${neutral}")
if [[ "${without_ok}" == *'>'* ]]; then block "output redirection"; fi

# --- 3. Per-segment allowlist ---------------------------------------------
has_token() {  # has_token <extended-regex> <words...>: any word matches?
    local re="$1" w
    shift
    for w in "$@"; do
        if [[ "${w}" =~ ${re} ]]; then return 0; fi
    done
    return 1
}

check_segment() {
    local -a words
    read -ra words <<< "$1"
    (( ${#words[@]} == 0 )) && return 0

    # Optional runners: "uv run [--no-sync] <tool>".
    if [[ "${words[0]}" == "uv" && "${words[1]:-}" == "run" ]]; then
        words=("${words[@]:2}")
        if [[ "${words[0]:-}" == "--no-sync" ]]; then words=("${words[@]:1}"); fi
    fi
    local cmd="${words[0]:-}"
    # The isolated test runner: it works only inside a disposable worktree.
    if [[ "${cmd}" =~ ^(\./)?scripts/review_worktree\.sh$ ]]; then
        return 0
    fi
    # Only bare names or the project's own venv tools — never arbitrary paths.
    if [[ "${cmd}" == */* ]]; then
        [[ "${cmd}" =~ ^(\./)?\.venv/bin/[[:alnum:]_.-]+$ ]] || block "'${cmd}' is not on the reviewer's read-only allowlist"
        cmd="${cmd##*/}"
    fi
    local -a args=("${words[@]:1}")

    case "${cmd}" in
        git)
            [[ "${args[0]:-}" =~ ^(diff|log|show|status|blame|ls-files|rev-parse|merge-base|grep)$ ]] \
                || block "'git ${args[0]:-}' is not on the reviewer's read-only allowlist"
            if has_token '^(--output|--ext-diff|--open-files-in-pager|-O)' "${args[@]}"; then
                block "a git option that writes files or runs a program"
            fi ;;
        mypy)
            if has_token '^(--install-types|--non-interactive|--junit-xml|--[a-z-]*-report)' "${args[@]}"; then
                block "a mypy option that installs packages or writes reports"
            fi ;;
        pytest)
            if has_token '^(--junit-?xml|--basetemp|--result-?log|--cov-report=(html|xml|json|lcov|annotate))' "${args[@]}"; then
                block "a pytest option that writes report files"
            fi
            local k
            for (( k = 0; k < ${#args[@]}; k++ )); do
                if [[ "${args[k]}" == "--cov-report" && ! "${args[k+1]:-}" =~ ^term ]]; then
                    block "a pytest option that writes report files"
                fi
            done ;;
        ruff)
            case "${args[0]:-}" in
                check)
                    if has_token '^(--fix|--fix-only|--unsafe-fixes|--add-noqa|--output-file|--watch)(=|$)|^-[a-z]*[ow]' "${args[@]:1}"; then
                        block "a ruff option that modifies or writes files"
                    fi ;;
                format)
                    has_token '^--(check|diff)$' "${args[@]:1}" || block "'ruff format' without --check or --diff rewrites files" ;;
                *) block "'ruff ${args[0]:-}' is not on the reviewer's read-only allowlist" ;;
            esac ;;
        rg)
            if has_token '^--pre(-glob)?(=|$)' "${args[@]}"; then block "rg --pre runs a program"; fi ;;
        sort)
            if has_token '^(--output|--compress-program)|^-[^-]*o' "${args[@]}"; then
                block "a sort option that writes a file or runs a program"
            fi ;;
        find)
            if has_token '^-(exec|execdir|ok|okdir|delete|fls|fprint|fprint0|fprintf)$' "${args[@]}"; then
                block "a find action that writes, deletes or runs a program"
            fi ;;
        xargs)
            local target="" a
            local skip_value=0
            for a in "${args[@]}"; do
                if (( skip_value )); then skip_value=0; continue; fi
                case "${a}" in
                    -I | -n | -d | -L | -P | -s | -E | -a) skip_value=1 ;;
                    -*) ;;
                    *) target="${a}"; break ;;
                esac
            done
            [[ "${target}" =~ ^(wc|grep|cat|head|tail|ls)$ ]] \
                || block "xargs may only run wc, grep, cat, head, tail or ls" ;;
        grep | cat | head | tail | wc | ls | cut | tr | diff | echo | true | pwd | cd) ;;
        *) block "'${cmd}' is not on the reviewer's read-only allowlist" ;;
    esac
}

while IFS= read -r segment; do
    check_segment "${segment}"
done < <(tr ';&|' '\n\n\n' <<< "${without_ok}")

exit 0

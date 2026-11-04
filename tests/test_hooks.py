"""Unit tests for the Claude Code PreToolUse hooks in .claude/hooks/.

Each hook runs as a subprocess the way Claude Code runs it: hook JSON on
stdin, exit code 2 = blocked, 0 = allowed.

- block_publish.sh: agents must never publish packages.
- review_readonly.sh: code_review_agent must stay read-only.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
BASH = shutil.which("bash") or "/bin/bash"
HAS_JQ = shutil.which("jq") is not None
BLOCKED = 2
ALLOWED = 0
PUBLISH_HOOK = "block_publish.sh"
REVIEW_HOOK = "review_readonly.sh"

needs_jq = pytest.mark.skipif(not HAS_JQ, reason="jq not installed; the hooks block everything without it")


def _run_hook(
    hook: str, command: str | None = None, *, raw_stdin: str | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    if raw_stdin is None:
        raw_stdin = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [BASH, str(HOOKS_DIR / hook)],
        input=raw_stdin,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------
# Both hooks: fail closed
# --------------------------------------------------------------------------
@pytest.mark.parametrize("hook", [PUBLISH_HOOK, REVIEW_HOOK])
@pytest.mark.parametrize(
    ("raw_stdin", "env"),
    [
        pytest.param('{"tool_input": {"command": "git status"}}', {"PATH": "/nonexistent"}, id="jq-missing"),
        pytest.param("not json", None, id="malformed-json"),
    ],
)
def test_hook_fails_closed(hook: str, raw_stdin: str, env: dict[str, str] | None) -> None:
    if env is None and not HAS_JQ:
        pytest.skip("jq not installed")
    result = _run_hook(hook, raw_stdin=raw_stdin, env=env)
    assert result.returncode == BLOCKED, f"{hook} did not fail closed: rc={result.returncode}\n{result.stderr}"
    assert hook in result.stderr


# --------------------------------------------------------------------------
# block_publish.sh
# --------------------------------------------------------------------------
@needs_jq
@pytest.mark.parametrize(
    "command",
    [
        "twine upload dist/*",
        ".venv/bin/twine upload --verbose --repository testpypi dist/*.whl",
        "python -m twine upload dist/*",
        "uv run twine upload dist/*",
        "bash -c 'cd x && .venv/bin/twine   upload dist/*'",
        "TWINE upload dist/*",
        "uv publish",
        "cd foo; uv publish --token x",
        "poetry publish --build",
        "curl -F content=@x.whl https://upload.pypi.org/legacy/",
        "cat ~/.pypirc",
        "TWINE_PASSWORD=x twine check dist/*",
        "./release.sh publish",
        "./release.sh publish_test",
        "git push origin v3.2",
        "git push --tags",
        "git push origin refs/tags/v3.2",
        "git push origin tag v3.2",
        "git push --mirror origin",
        "gh release create v3.2",
        "gh workflow run release.yml",
        "gh api repos/Marzona/rig-remote/actions/workflows/release.yml/dispatches -f ref=master",
        "gh api -X POST repos/Marzona/rig-remote/git/refs -f ref=refs/tags/v9.9 -f sha=abc",
        "curl -X POST https://api.github.com/repos/Marzona/rig-remote/dispatches -d '{}'",
    ],
)
def test_block_publish_blocks_publishing_commands(command: str) -> None:
    result = _run_hook(PUBLISH_HOOK, command)
    assert result.returncode == BLOCKED, f"not blocked: {command!r}\n{result.stderr}"
    assert "Blocked by .claude/hooks/block_publish.sh" in result.stderr


@needs_jq
@pytest.mark.parametrize(
    "command",
    [
        ".venv/bin/twine check --strict dist/*.whl dist/*.tar.gz",
        "./release.sh release",
        "./release.sh commit_push",
        "uv build",
        "uv lock --check",
        "git push origin master",
        "git status",
        "gh api repos/Marzona/rig-remote/actions/runs",
        "grep -n upload release.sh",
        ".venv/bin/pytest tests/ -n auto",
    ],
)
def test_block_publish_allows_non_publishing_commands(command: str) -> None:
    result = _run_hook(PUBLISH_HOOK, command)
    assert result.returncode == ALLOWED, result.stderr


@needs_jq
@pytest.mark.xfail(
    strict=True,
    reason="Known limit (documented in the hook header and the invariants table): string matching "
    "cannot see through shell obfuscation. The real controls are no local credentials, Trusted "
    "Publishing and the required pypi reviewer. If this starts passing, update the docs.",
)
def test_block_publish_known_limit_obfuscated_command() -> None:
    result = _run_hook(PUBLISH_HOOK, 'bash -c "tw""ine upload x"')
    assert result.returncode == BLOCKED


# --------------------------------------------------------------------------
# review_readonly.sh
# --------------------------------------------------------------------------
@needs_jq
@pytest.mark.parametrize(
    "command",
    [
        # Spec B3: must stay allowed.
        "git diff",
        "git log --oneline -5",
        "git show HEAD",
        "grep -E 'a|b' README.md",
        "ruff check ./src",
        "ruff format --check ./src",
        ".venv/bin/mypy --config-file ./pyproject.toml ./src",
        ".venv/bin/pytest tests/ -n auto -p no:cacheprovider",
        "git diff 2>&1 | head",
        # Other read-only usage.
        "git diff master...HEAD",
        "git diff --stat HEAD~3 && git log --oneline -5",
        "git grep -n process_queue",
        "uv run --no-sync mypy --config-file ./pyproject.toml ./src",
        ".venv/bin/ruff check --output-format=github ./src",
        ".venv/bin/pytest tests/ -n auto --cov=rig_remote --cov=config_checker --cov-report=term-missing 2>&1 | tail",
        ".venv/bin/pytest functional_tests/ -n 1 -m 'not gqrx'",
        "find src -name '*.py' | xargs wc -l",
        "git diff --name-only | xargs -0 grep -n TODO",
        "sort README.md | head",
        "cat README.md 2>/dev/null",
        "cd src && ls",
        "rg -n Protocol src",
        "scripts/review_worktree.sh",
        "./scripts/review_worktree.sh 2>&1 | tail -40",
    ],
)
def test_review_readonly_allows_read_only_commands(command: str) -> None:
    result = _run_hook(REVIEW_HOOK, command)
    assert result.returncode == ALLOWED, result.stderr


@needs_jq
@pytest.mark.parametrize(
    "command",
    [
        # Spec B3: reported bypasses of the previous version.
        "ls & touch x",
        "sed -n 'w /tmp/x' README.md",
        "sort -o /tmp/x README.md",
        "find . -fls /tmp/x",
        "uniq README.md /tmp/x",
        # sed and uniq are not allowed at all.
        "sed -n 1,5p README.md",
        "sort README.md | uniq -c",
        # Fixers and writers.
        ".venv/bin/ruff check --fix ./src",
        ".venv/bin/ruff check --fix-only ./src",
        ".venv/bin/ruff check -o out.txt ./src",
        "ruff format ./src",
        "sed -i 's/a/b/' src/x.py",
        "sort -uo /tmp/x README.md",
        "sort --output=/tmp/x README.md",
        "sort '-o' /tmp/x README.md",
        "find . -fprint /tmp/x",
        "find . -fprintf /tmp/x %p",
        "find . -name '*.pyc' -delete",
        "find . -exec rm {} +",
        "git diff --output=patch.txt",
        "git grep -O vim foo",
        "rg --pre sh foo",
        ".venv/bin/mypy --install-types ./src",
        ".venv/bin/pytest --junitxml=out.xml tests/",
        ".venv/bin/pytest --cov-report html tests/",
        # Redirection, substitution, chaining.
        "echo x > src/x.py",
        "cat a >> b",
        "cat <(touch x)",
        'echo "$(touch x)"',
        "grep x $(touch y)",
        "grep x `touch y`",
        "(touch x)",
        "FOO=1 touch x",
        "ls; touch x",
        "ls || touch x",
        "ls\ntouch x",
        # Not on the allowlist.
        "git commit -am x",
        "git checkout -- src",
        "git stash",
        "rm -rf src",
        "cp a b",
        "tee src/x.py",
        'python -c \'open("x","w")\'',
        "uv sync",
        "/tmp/evil/pytest",
        "/tmp/scripts/review_worktree.sh",
        "scripts/other.sh",
        "find . | xargs rm",
        "ls | xargs -I{} sh -c 'rm {}'",
        "echo 'unterminated",
    ],
)
def test_review_readonly_blocks_modifying_commands(command: str) -> None:
    result = _run_hook(REVIEW_HOOK, command)
    assert result.returncode == BLOCKED, f"not blocked: {command!r}\n{result.stderr}"
    assert "review_readonly.sh" in result.stderr

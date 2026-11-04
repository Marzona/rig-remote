#!/usr/bin/env python3
"""Architecture-change gate.

Fails a change that touches architecture-relevant ("protected") source files unless the
author either updated ``.claude/architecture.md`` in the same range or declared, in the PR
body (pull_request) or in a commit message of the pushed range (push), a trailer line::

    ADR-impact: none, because <reason of at least 10 non-space characters>

Usage (stdlib only, run from the repo root)::

    ADR_GATE_EVENT=pull_request ADR_GATE_BASE_SHA=<sha> ADR_GATE_HEAD_SHA=<sha> \\
    ADR_GATE_PR_BODY="..." python3 scripts/check_adr_impact.py

Environment variables:
    ADR_GATE_EVENT     ``pull_request`` or ``push``
    ADR_GATE_BASE_SHA  PR base SHA, or the push ``before`` SHA (all zeros for a new branch)
    ADR_GATE_HEAD_SHA  PR head SHA, or the pushed SHA
    ADR_GATE_PR_BODY   PR description (optional; ignored on push)

Exit codes: 0 = pass, 1 = gate failed, 2 = usage/configuration/git error.

All-zero base SHA (push creating a branch): the base becomes
``git merge-base origin/master <head>``; if that fails, the head's first parent; if that
also fails (root commit), the empty tree, i.e. the whole history counts as changed.

Git is only invoked through ``subprocess.run`` with argument lists (never a shell), and the
SHAs are validated as hex before use.

Known limit: the gate proves the question was answered, not that the answer is right.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("check_adr_impact")

ARCHITECTURE_DOC = ".claude/architecture.md"
PROTECTED_PATTERNS: tuple[str, ...] = (
    "src/rig_remote/scanning.py",
    "src/rig_remote/scanner_core.py",
    "src/rig_remote/scanning_config.py",
    "src/rig_remote/*_scanner_strategy.py",
    "src/rig_remote/queue_comms.py",
    "src/rig_remote/stmessenger.py",
    "src/rig_remote/syncing.py",
    "src/rig_remote/app_config.py",
    "src/rig_remote/exceptions.py",
    "src/rig_remote/ui_qt.py",
    "src/rig_remote/models/**",
    "src/rig_remote/rig_backends/**",
)
MIN_REASON_CHARS = 10
ZERO_SHA_RE = re.compile(r"^0+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbbf4904"
TRAILER_RE = re.compile(r"^[ \t]*ADR-impact:[ \t]*none,[ \t]*because[ \t]+(?P<reason>\S.*)$", re.MULTILINE)
EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


class GateError(Exception):
    """Usage, configuration or git failure (exit code 2)."""


class GitReader(Protocol):
    """Reads change information from a repository."""

    def resolve_base(self, base: str, head: str) -> str:
        """Return a usable base revision (handles an all-zero SHA)."""

    def changed_paths(self, base: str, head: str, event: str) -> list[str]:
        """Return paths changed between base and head."""

    def commit_messages(self, base: str, head: str) -> list[str]:
        """Return full commit messages for base..head."""


@dataclass(frozen=True)
class Decision:
    """Outcome of the gate."""

    passed: bool
    reason: str
    protected_changed: tuple[str, ...] = ()


def is_protected(path: str) -> bool:
    """Return True if *path* (repo-relative, posix) matches a protected pattern."""
    for pattern in PROTECTED_PATTERNS:
        if pattern.endswith("/**"):
            if path.startswith(pattern[:-2]):
                return True
        elif fnmatch.fnmatchcase(path, pattern) and "/" not in path[len("src/rig_remote/") :]:
            return True
    return False


def has_valid_trailer(text: str) -> bool:
    """Return True if *text* has an ``ADR-impact: none, because <reason>`` line with a real reason."""
    for match in TRAILER_RE.finditer(text):
        if len("".join(match.group("reason").split())) >= MIN_REASON_CHARS:
            return True
    return False


def evaluate(changed_paths: Sequence[str], texts: Sequence[str]) -> Decision:
    """Pure gate decision.

    Args:
        changed_paths: paths changed in the range.
        texts: PR body (pull_request) or commit messages (push) to search for the trailer.
    """
    paths = [p.strip() for p in changed_paths if p.strip()]
    protected = tuple(sorted(p for p in paths if is_protected(p)))
    if not protected:
        return Decision(True, "no protected path changed")
    if ARCHITECTURE_DOC in paths:
        return Decision(True, f"{ARCHITECTURE_DOC} updated", protected)
    if any(has_valid_trailer(t) for t in texts):
        return Decision(True, "ADR-impact: none trailer with a reason found", protected)
    return Decision(False, "protected paths changed without an architecture answer", protected)


class SubprocessGit:
    """GitReader backed by the git CLI (argument lists only, no shell)."""

    def __init__(self, default_branch_ref: str = "origin/master") -> None:
        self._default_ref = default_branch_ref

    @staticmethod
    def _run(args: list[str]) -> str:
        try:
            result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)  # noqa: S603, S607
        except (subprocess.CalledProcessError, OSError) as exc:
            raise GateError(f"git {' '.join(args)} failed: {exc}") from exc
        return result.stdout

    def resolve_base(self, base: str, head: str) -> str:
        if not ZERO_SHA_RE.match(base):
            return base
        for args in (["merge-base", self._default_ref, head], ["rev-parse", f"{head}^"]):
            try:
                out = self._run(args).strip()
            except GateError:
                continue
            if out:
                return out
        return EMPTY_TREE

    def changed_paths(self, base: str, head: str, event: str) -> list[str]:
        sep = "..." if event == "pull_request" else ".."
        return self._run(["diff", "--name-only", f"{base}{sep}{head}"]).splitlines()

    def commit_messages(self, base: str, head: str) -> list[str]:
        rng = head if base == EMPTY_TREE else f"{base}..{head}"
        return [m for m in self._run(["log", "--format=%B%x00", rng]).split("\0") if m.strip()]


def run_gate(env: Mapping[str, str], git: GitReader) -> tuple[int, str]:
    """Run the gate for the given environment; return (exit code, message)."""
    event = env.get("ADR_GATE_EVENT", "").strip()
    base = env.get("ADR_GATE_BASE_SHA", "").strip()
    head = env.get("ADR_GATE_HEAD_SHA", "").strip()
    missing = [
        n for n, v in (("ADR_GATE_EVENT", event), ("ADR_GATE_BASE_SHA", base), ("ADR_GATE_HEAD_SHA", head)) if not v
    ]
    if missing:
        return EXIT_USAGE, f"missing environment variables: {', '.join(missing)}"
    if event not in ("pull_request", "push"):
        return EXIT_USAGE, f"ADR_GATE_EVENT must be 'pull_request' or 'push', got {event!r}"
    for name, sha in (("ADR_GATE_BASE_SHA", base), ("ADR_GATE_HEAD_SHA", head)):
        if not SHA_RE.match(sha):
            return EXIT_USAGE, f"{name} is not a hex SHA"
    try:
        base = git.resolve_base(base, head)
        paths = git.changed_paths(base, head, event)
        texts = [env.get("ADR_GATE_PR_BODY", "")] if event == "pull_request" else git.commit_messages(base, head)
    except GateError as exc:
        return EXIT_USAGE, str(exc)
    decision = evaluate(paths, texts)
    if decision.passed:
        return EXIT_PASS, f"ADR gate passed: {decision.reason}"
    listing = "\n".join(f"  - {p}" for p in decision.protected_changed)
    where = "PR description" if event == "pull_request" else "a commit message in the pushed range"
    return EXIT_FAIL, (
        "ADR gate FAILED: protected architecture files changed:\n"
        f"{listing}\n\n"
        "Satisfy the gate in one of two ways:\n"
        f"  1. Update {ARCHITECTURE_DOC} in the same change.\n"
        f"  2. Add this line to {where}:\n"
        "       ADR-impact: none, because <reason of at least 10 non-space characters>"
    )


def main() -> int:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    code, message = run_gate(os.environ, SubprocessGit())
    (logger.info if code == EXIT_PASS else logger.error)(message)
    return code


if __name__ == "__main__":
    sys.exit(main())

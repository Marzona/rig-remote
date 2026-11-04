"""Unit tests for scripts/check_adr_impact.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_adr_impact.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_adr_impact", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load()
SHA_A = "a" * 40
SHA_B = "b" * 40
ZERO = "0" * 40
GOOD = "ADR-impact: none, because purely internal refactor"


class FakeGit:
    """In-memory GitReader recording the arguments it receives."""

    def __init__(self, paths: list[str], messages: list[str] | None = None, fail: bool = False) -> None:
        self.paths = paths
        self.messages = messages or []
        self.fail = fail
        self.calls: list[tuple[str, str, str]] = []

    def resolve_base(self, base: str, head: str) -> str:
        return "resolved" if set(base) == {"0"} else base

    def changed_paths(self, base: str, head: str, event: str) -> list[str]:
        if self.fail:
            raise gate.GateError("boom")
        self.calls.append((base, head, event))
        return self.paths

    def commit_messages(self, base: str, head: str) -> list[str]:
        return self.messages


def _env(event: str = "pull_request", body: str = "", base: str = SHA_A, head: str = SHA_B) -> dict[str, str]:
    return {"ADR_GATE_EVENT": event, "ADR_GATE_BASE_SHA": base, "ADR_GATE_HEAD_SHA": head, "ADR_GATE_PR_BODY": body}


@pytest.mark.parametrize(
    "path",
    [
        "src/rig_remote/scanning.py",
        "src/rig_remote/scanner_core.py",
        "src/rig_remote/scanning_config.py",
        "src/rig_remote/queue_comms.py",
        "src/rig_remote/stmessenger.py",
        "src/rig_remote/syncing.py",
        "src/rig_remote/app_config.py",
        "src/rig_remote/exceptions.py",
        "src/rig_remote/ui_qt.py",
        "src/rig_remote/foo_scanner_strategy.py",
        "src/rig_remote/_scanner_strategy.py",
        "src/rig_remote/models/channel.py",
        "src/rig_remote/models/deep/x.py",
        "src/rig_remote/rig_backends/gqrx.py",
        "src/rig_remote/rig_backends/sub/x.py",
    ],
)
def test_is_protected_matches_protected_paths(path: str) -> None:
    assert gate.is_protected(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/rig_remote/utils.py",
        "src/rig_remote/scanning_helpers.py",
        "src/rig_remote/sub/foo_scanner_strategy.py",
        "src/rig_remote/modelsx/a.py",
        "tests/test_scanning.py",
        "README.md",
        ".claude/architecture.md",
    ],
)
def test_is_protected_rejects_unprotected_paths(path: str) -> None:
    assert not gate.is_protected(path)


@pytest.mark.parametrize(
    ("paths", "texts", "passed"),
    [
        ([], [], True),
        (["README.md", "src/rig_remote/utils.py"], [], True),
        (["src/rig_remote/scanning.py"], [], False),
        (["src/rig_remote/scanning.py", ".claude/architecture.md"], [], True),
        (["src/rig_remote/scanning.py"], [f"desc\n{GOOD}\n"], True),
        (["src/rig_remote/scanning.py"], ["fix", f"msg\n\n{GOOD}"], True),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none, because short"], False),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none, because a b c d e"], False),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none, because ab cd ef gh ij"], True),
        (["src/rig_remote/scanning.py"], ["ADR-impact: yes, because lots of reasons here"], False),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none because lots of reasons here"], False),
        (["src/rig_remote/scanning.py"], ["ADR impact none, because lots of reasons here"], False),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none, because"], False),
        (["src/rig_remote/scanning.py"], ["ADR-impact: none, because   "], False),
        (["src/rig_remote/scanning.py"], ["no trailer at all"], False),
    ],
)
def test_evaluate_decision_paths(paths: list[str], texts: list[str], passed: bool) -> None:
    assert gate.evaluate(paths, texts).passed is passed


def test_evaluate_lists_changed_protected_paths_on_fail() -> None:
    decision = gate.evaluate(["src/rig_remote/ui_qt.py", "x.py", "src/rig_remote/models/a.py"], [])
    assert decision.protected_changed == ("src/rig_remote/models/a.py", "src/rig_remote/ui_qt.py")


def test_run_gate_pull_request_passes_with_body_trailer() -> None:
    git = FakeGit(["src/rig_remote/scanning.py"], messages=["ignored"])
    code, _ = gate.run_gate(_env(body=GOOD), git)
    assert code == 0
    assert git.calls == [(SHA_A, SHA_B, "pull_request")]


def test_run_gate_pull_request_ignores_commit_messages() -> None:
    git = FakeGit(["src/rig_remote/scanning.py"], messages=[GOOD])
    code, _ = gate.run_gate(_env(body=""), git)
    assert code == 1


def test_run_gate_push_passes_with_commit_message_trailer() -> None:
    git = FakeGit(["src/rig_remote/scanning.py"], messages=["a", GOOD])
    code, _ = gate.run_gate(_env("push", body=""), git)
    assert code == 0


def test_run_gate_push_ignores_pr_body() -> None:
    git = FakeGit(["src/rig_remote/scanning.py"], messages=["plain"])
    code, _ = gate.run_gate(_env("push", body=GOOD), git)
    assert code == 1


def test_run_gate_fail_message_explains_both_remedies() -> None:
    code, msg = gate.run_gate(_env(), FakeGit(["src/rig_remote/syncing.py"]))
    assert code == 1
    assert "src/rig_remote/syncing.py" in msg
    assert ".claude/architecture.md" in msg
    assert "ADR-impact: none, because" in msg


def test_run_gate_passes_without_protected_change() -> None:
    code, _ = gate.run_gate(_env(), FakeGit(["src/rig_remote/utils.py"]))
    assert code == 0


def test_run_gate_passes_with_architecture_doc() -> None:
    code, _ = gate.run_gate(_env(), FakeGit(["src/rig_remote/ui_qt.py", ".claude/architecture.md"]))
    assert code == 0


def test_run_gate_zero_base_is_resolved_before_diff() -> None:
    git = FakeGit(["src/rig_remote/utils.py"])
    code, _ = gate.run_gate(_env("push", base=ZERO), git)
    assert code == 0
    assert git.calls == [("resolved", SHA_B, "push")]


@pytest.mark.parametrize("missing", ["ADR_GATE_EVENT", "ADR_GATE_BASE_SHA", "ADR_GATE_HEAD_SHA"])
def test_run_gate_missing_env_returns_usage_error(missing: str) -> None:
    env = _env()
    del env[missing]
    code, msg = gate.run_gate(env, FakeGit([]))
    assert code == 2
    assert missing in msg


@pytest.mark.parametrize(
    "env",
    [
        _env(event="release"),
        _env(base="not-a-sha"),
        _env(head="--output=x"),
    ],
)
def test_run_gate_invalid_env_returns_usage_error(env: dict[str, str]) -> None:
    assert gate.run_gate(env, FakeGit([]))[0] == 2


def test_run_gate_git_failure_returns_usage_error() -> None:
    assert gate.run_gate(_env(), FakeGit([], fail=True))[0] == 2


def test_run_gate_missing_pr_body_on_pull_request_fails_closed() -> None:
    env = _env()
    del env["ADR_GATE_PR_BODY"]
    assert gate.run_gate(env, FakeGit(["src/rig_remote/scanning.py"]))[0] == 1


class _Recorder(gate.SubprocessGit):
    """SubprocessGit with scripted git output (no real git)."""

    def __init__(self, outputs: dict[str, str | None]) -> None:
        super().__init__()
        self.outputs = outputs
        self.seen: list[list[str]] = []

    def _run(self, args: list[str]) -> str:  # type: ignore[override]
        self.seen.append(args)
        out = self.outputs.get(args[0])
        if out is None:
            raise gate.GateError("fail")
        return out


@pytest.mark.parametrize(
    ("outputs", "expected"),
    [
        ({"merge-base": "mb\n"}, "mb"),
        ({"rev-parse": "parent\n"}, "parent"),
        ({}, gate.EMPTY_TREE),
    ],
)
def test_resolve_base_zero_sha_fallback_chain(outputs: dict[str, str | None], expected: str) -> None:
    assert _Recorder(outputs).resolve_base(ZERO, SHA_B) == expected


def test_resolve_base_non_zero_is_unchanged() -> None:
    rec = _Recorder({})
    assert rec.resolve_base(SHA_A, SHA_B) == SHA_A
    assert rec.seen == []

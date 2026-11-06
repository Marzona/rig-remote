#!/usr/bin/env python3
"""Run the review-agent evals.

For each case in evals/cases/: create a throwaway snapshot repo of HEAD (no
evals, no history, so the reviewer cannot read the answer key), apply the
case's edits, optionally record whether CI's own checks would fail, ask the
review agent (``code_review_agent``) for a report, and score it.

    python3 evals/run_review_evals.py --measure-ci          # all cases, real review
    python3 evals/run_review_evals.py --dry-run --measure-ci  # no model calls
    python3 evals/run_review_evals.py --case infinite_passes_clamped

Results go to evals/results/<UTC timestamp>/: one report per case, plus
summary.md and summary.json. Each real review runs a full Claude Code
session, so a full run costs real usage; --dry-run makes no model calls.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import Case, CaseResult, Outcome, apply_edits, load_cases, score_case  # noqa: E402

logger = logging.getLogger("review_evals")

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = REPO_ROOT / "evals" / "cases"
RESULTS_DIR = REPO_ROOT / "evals" / "results"
VENV_BIN = REPO_ROOT / ".venv" / "bin"
HIDDEN_FROM_REVIEWER = ("evals", "tests/test_review_evals.py")
REVIEW_TIMEOUT_S = 45 * 60
CI_TIMEOUT_S = 15 * 60

PROMPT = """You are reviewing a pull request in this repository. The change is the uncommitted
diff against HEAD (`git diff HEAD`, plus untracked files).

Pull request description from the author:
---
{pr_description}
---

Follow your review procedure, then output only the final report in the documented
format (Summary, Findings table, Details)."""

DEFAULT_REVIEWER = (
    "claude --agent code_review_agent --output-format text --no-session-persistence "
    '--allowedTools "Read Grep Glob Bash" -p {prompt}'
)


@dataclass
class CaseRun:
    case: Case
    ci_detects: bool | None
    ci_detail: str
    report: str | None
    result: CaseResult | None
    error: str
    seconds: float


@contextmanager
def snapshot() -> Iterator[Path]:
    """A throwaway git repo holding HEAD's files minus the answer key, as one commit.

    The reviewer must not be able to read the expected findings (``evals/``)
    or the history of the fixes being re-broken (commit messages), so the
    snapshot has no evals and no history: a fresh repo with a single commit.
    """
    parent = Path(tempfile.mkdtemp(prefix="rig-remote-eval-"))
    path = parent / "repo"
    path.mkdir()
    try:
        archive = subprocess.run(
            ["git", "archive", "--format=tar", "HEAD"], cwd=REPO_ROOT, capture_output=True, check=True
        )
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(path, filter="data")
        for hidden in HIDDEN_FROM_REVIEWER:
            target = path / hidden
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        git = [
            "git",
            "-c",
            "user.name=review-eval",
            "-c",
            "user.email=review-eval@localhost",
            "-c",
            "commit.gpgsign=false",
        ]
        subprocess.run([*git, "init", "--quiet", "--initial-branch=master"], cwd=path, check=True)
        # --force: commit exactly HEAD's tracked files, even ones a global excludesfile ignores
        # (a global "*.md" or ".claude" rule would otherwise silently drop docs and agent config).
        subprocess.run([*git, "add", "--all", "--force"], cwd=path, check=True)
        subprocess.run([*git, "commit", "--quiet", "--message", "Base"], cwd=path, check=True)
        yield path
    finally:
        shutil.rmtree(parent)


def measure_ci(path: Path) -> tuple[bool, str]:
    """Run CI's lint, type and test gates in *path*; True if any fails."""
    checks = [
        ("ruff", [str(VENV_BIN / "ruff"), "check", "./src"]),
        ("ruff format", [str(VENV_BIN / "ruff"), "format", "--check", "./src"]),
        ("mypy", [str(VENV_BIN / "mypy"), "--config-file", "./pyproject.toml", "./src"]),
        (
            "pytest",
            [
                str(VENV_BIN / "python"),
                "-m",
                "pytest",
                "tests",
                "functional_tests",
                "-m",
                "not gqrx",
                "-q",
                "-n",
                "auto",
                "-p",
                "no:cacheprovider",
                "-o",
                "faulthandler_timeout=120",
            ],
        ),
    ]
    failed = []
    for name, command in checks:
        completed = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=CI_TIMEOUT_S)
        if completed.returncode != 0:
            failed.append(name)
    return bool(failed), ", ".join(failed) if failed else "all green"


def run_reviewer(path: Path, case: Case, reviewer_template: str) -> str:
    command = reviewer_template.format(prompt=shlex.quote(PROMPT.format(pr_description=case.pr_description)))
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TWINE_", "PYPI_", "UV_PUBLISH_"))}
    completed = subprocess.run(
        command, shell=True, cwd=path, capture_output=True, text=True, timeout=REVIEW_TIMEOUT_S, env=env
    )
    if completed.returncode != 0:
        logger.warning("%s: reviewer exited %d: %s", case.id, completed.returncode, completed.stderr[-500:])
    return completed.stdout


def run_case(case: Case, *, dry_run: bool, with_ci: bool, reviewer: str) -> CaseRun:
    start = time.monotonic()
    ci_detects: bool | None = None
    ci_detail = "not measured"
    report: str | None = None
    result: CaseResult | None = None
    error = ""
    try:
        with snapshot() as path:
            apply_edits(case, path)
            if with_ci:
                ci_detects, ci_detail = measure_ci(path)
            if not dry_run:
                report = run_reviewer(path, case, reviewer)
                result = score_case(case, report)
    except Exception as exc:  # report every case, even a broken one
        logger.exception("%s: %s", case.id, exc)
        error = f"{type(exc).__name__}: {exc}"
    return CaseRun(case, ci_detects, ci_detail, report, result, error, time.monotonic() - start)


def _summary_rows(runs: list[CaseRun]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs:
        matched = run.result.matched if run.result else None
        rows.append(
            {
                "case": run.case.id,
                "kind": run.case.kind,
                "title": run.case.title,
                "origin": run.case.origin,
                "ci_detects": run.ci_detects,
                "ci_detail": run.ci_detail,
                "outcome": run.result.outcome.value if run.result else ("error" if run.error else "not run"),
                "matched": f"{matched.severity.name} {matched.file}: {matched.rule}" if matched else "",
                "blocking_findings": len(run.result.blocking_findings) if run.result else None,
                "error": run.error,
                "seconds": round(run.seconds, 1),
            }
        )
    return rows


def write_summary(runs: list[CaseRun], out: Path) -> str:
    out.mkdir(parents=True, exist_ok=True)
    reports = out / "reports"
    reports.mkdir(exist_ok=True)
    for run in runs:
        if run.report is not None:
            (reports / f"{run.case.id}.md").write_text(run.report, encoding="utf-8")
    rows = _summary_rows(runs)
    (out / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    seeds = [r for r in runs if r.case.kind == "seed" and r.result]
    controls = [r for r in runs if r.case.kind == "control" and r.result]
    caught = [r for r in seeds if r.result and r.result.outcome is Outcome.CAUGHT]
    ci_silent = [r for r in seeds if r.ci_detects is False]
    caught_ci_silent = [r for r in ci_silent if r in caught]
    false_alarms = [r for r in controls if r.result and r.result.outcome is Outcome.FALSE_ALARM]

    def fmt(value: object) -> str:
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)

    lines = [
        f"# Review-agent eval — {out.name}",
        "",
        f"- Seeds caught at the expected severity: **{len(caught)}/{len(seeds)}**",
        f"- Seeds CI's own checks miss, caught by the reviewer: **{len(caught_ci_silent)}/{len(ci_silent)}**",
        f"- Controls with a false BLOCKER/MAJOR alarm: **{len(false_alarms)}/{len(controls)}**",
        "",
        "| Case | Kind | CI catches it? | Reviewer outcome | Best matching finding | Time (s) |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        outcome = str(row["outcome"]) + (f" ({row['error']})" if row["error"] else "")
        lines.append(
            f"| `{row['case']}` | {row['kind']} | {fmt(row['ci_detects'])} ({row['ci_detail']}) | {outcome} "
            f"| {row['matched']} | {row['seconds']} |"
        )
    markdown = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(markdown, encoding="utf-8")
    return markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", action="append", default=[], help="run only this case id (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="apply cases (and --measure-ci) without a model call")
    parser.add_argument("--measure-ci", action="store_true", help="record whether ruff/mypy/pytest catch each case")
    parser.add_argument("--reviewer-cmd", default=DEFAULT_REVIEWER, help="shell template; {prompt} is substituted")
    parser.add_argument("--out", type=Path, help="results directory (default: evals/results/<timestamp>)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cases = load_cases(CASES_DIR)
    if args.case:
        unknown = set(args.case) - {c.id for c in cases}
        if unknown:
            parser.error(f"unknown case(s): {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c.id in args.case]
    out = args.out or RESULTS_DIR / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    runs = []
    for case in cases:
        logger.info("case %s (%s)", case.id, case.kind)
        runs.append(run_case(case, dry_run=args.dry_run, with_ci=args.measure_ci, reviewer=args.reviewer_cmd))
    print(write_summary(runs, out))
    print(f"Results: {out}")
    return 1 if any(r.error for r in runs) else 0


if __name__ == "__main__":
    sys.exit(main())

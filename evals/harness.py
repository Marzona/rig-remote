"""Review-agent evals: case loading, seeding, report parsing and scoring.

Stdlib only. A *seed* case re-introduces a known bug (often one this project
really shipped) as exact text edits, and states what a good review must find.
A *control* case is a harmless change that should draw no BLOCKER/MAJOR
finding. The runner (``run_review_evals.py``) applies a case in a throwaway
worktree, asks the review agent for a report and scores it with this module.
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Severity(IntEnum):
    """Severity levels of .claude/review/procedure.md, ordered."""

    INFO = 0
    MINOR = 1
    MAJOR = 2
    BLOCKER = 3


class Outcome(Enum):
    CAUGHT = "caught"
    CAUGHT_LOW_SEVERITY = "caught (low severity)"
    MISSED = "missed"
    CLEAN = "clean"
    FALSE_ALARM = "false alarm"
    NO_REPORT = "no report"


class CaseError(Exception):
    """A case file is malformed."""


class StaleCaseError(Exception):
    """A case's edit no longer matches the code; regenerate the case."""


@dataclass(frozen=True)
class Edit:
    file: str
    old: str
    new: str


@dataclass(frozen=True)
class Expectation:
    files: tuple[str, ...]
    keywords: tuple[str, ...]
    min_severity: Severity


@dataclass(frozen=True)
class Case:
    id: str
    kind: str  # "seed" or "control"
    title: str
    pr_description: str
    origin: str
    edits: tuple[Edit, ...]
    expect: Expectation | None


@dataclass(frozen=True)
class Finding:
    severity: Severity
    file: str
    lines: str
    rule: str
    text: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    outcome: Outcome
    matched: Finding | None
    blocking_findings: tuple[Finding, ...]


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
def _fail(message: str) -> CaseError:
    logger.error(message)
    return CaseError(message)


def _str(data: dict[str, Any], key: str, source: Path, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise _fail(f"{source}: '{key}' must be a string")
    return value


def _str_list(data: dict[str, Any], key: str, source: Path) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise _fail(f"{source}: '{key}' must be a non-empty list of strings")
    return tuple(value)


def _load_expectation(data: dict[str, Any], path: Path) -> Expectation:
    raw = data.get("expect")
    if not isinstance(raw, dict):
        raise _fail(f"{path}: a seed needs an [expect] table")
    severity_name = _str(raw, "min_severity", path, default="MAJOR").upper()
    if severity_name not in Severity.__members__:
        raise _fail(f"{path}: unknown min_severity {severity_name!r}")
    return Expectation(
        files=_str_list(raw, "files", path),
        keywords=_str_list(raw, "keywords", path),
        min_severity=Severity[severity_name],
    )


def load_case(path: Path) -> Case:
    """Load and validate one case file."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    kind = _str(data, "kind", path)
    if kind not in ("seed", "control"):
        raise _fail(f"{path}: kind must be 'seed' or 'control', got {kind!r}")
    raw_edits = data.get("edit")
    if not isinstance(raw_edits, list) or not raw_edits:
        raise _fail(f"{path}: a case needs at least one [[edit]]")
    edits = []
    for raw in raw_edits:
        if not isinstance(raw, dict):
            raise _fail(f"{path}: every [[edit]] must be a table")
        edits.append(Edit(file=_str(raw, "file", path), old=_str(raw, "old", path), new=_str(raw, "new", path, "")))
    return Case(
        id=path.stem,
        kind=kind,
        title=_str(data, "title", path),
        pr_description=_str(data, "pr_description", path),
        origin=_str(data, "origin", path, ""),
        edits=tuple(edits),
        expect=_load_expectation(data, path) if kind == "seed" else None,
    )


def load_cases(cases_dir: Path) -> list[Case]:
    return [load_case(path) for path in sorted(cases_dir.glob("*.toml"))]


def apply_edits(case: Case, root: Path) -> None:
    """Apply *case*'s edits under *root*. Each ``old`` must occur exactly once."""
    for edit in case.edits:
        target = root / edit.file
        if not target.is_file():
            message = f"{case.id}: {edit.file} does not exist"
            logger.error(message)
            raise StaleCaseError(message)
        text = target.read_text(encoding="utf-8")
        count = text.count(edit.old)
        if count != 1:
            message = f"{case.id}: expected the old text exactly once in {edit.file}, found {count}"
            logger.error(message)
            raise StaleCaseError(message)
        target.write_text(text.replace(edit.old, edit.new), encoding="utf-8")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
_SEVERITY_RE = re.compile(r"\b(BLOCKER|MAJOR|MINOR|INFO)\b", re.IGNORECASE)
_DETAIL_RE = re.compile(r"^#{2,4}\s*Finding\s+(\d+)\b(.*)$", re.IGNORECASE)
_SECTION_RE = re.compile(r"^#{1,3}\s+\S")


def _clean_cell(cell: str) -> str:
    return cell.strip().strip("`*_ ").strip()


def _severity_of(text: str) -> Severity | None:
    match = _SEVERITY_RE.search(text)
    return Severity[match.group(1).upper()] if match else None


def _detail_sections(lines: list[str]) -> dict[int, str]:
    """Map finding number → text of its '### Finding N …' details section."""
    sections: dict[int, list[str]] = {}
    current: int | None = None
    for line in lines:
        detail = _DETAIL_RE.match(line.strip())
        if detail:
            current = int(detail.group(1))
            sections[current] = [line]
        elif current is not None and _SECTION_RE.match(line) and not detail:
            current = None
        elif current is not None:
            sections[current].append(line)
    return {number: "\n".join(body) for number, body in sections.items()}


def parse_report(report: str) -> list[Finding]:
    """Extract findings from a report in the format of .claude/review/procedure.md.

    Reads the findings table (``| # | Severity | File | Line(s) | Rule | Description |``)
    and appends each finding's details section to its text. Falls back to the
    details headings alone when there is no table.
    """
    lines = report.splitlines()
    details = _detail_sections(lines)
    findings: list[Finding] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_cell(c) for c in stripped.strip("|").split("|")]
        if len(cells) < 6 or not cells[0].isdigit():
            continue
        severity = _severity_of(cells[1])
        if severity is None:
            continue
        number = int(cells[0])
        text = " ".join([cells[4], " | ".join(cells[5:]), details.get(number, "")])
        findings.append(Finding(severity=severity, file=cells[2], lines=cells[3], rule=cells[4], text=text))
    if findings:
        return findings
    for heading_and_body in details.values():
        severity = _severity_of(heading_and_body.splitlines()[0])
        if severity is None:
            continue
        location = re.search(r"\(([^():\s]+)(?::([^)]*))?\)", heading_and_body.splitlines()[0])
        file = location.group(1) if location else ""
        findings.append(Finding(severity=severity, file=file, lines="", rule="", text=heading_and_body))
    return findings


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _normalise_path(path: str) -> str:
    path = path.strip().strip("`").split(":")[0].strip()
    return path[2:] if path.startswith("./") else path


def _file_matches(finding_file: str, expected: tuple[str, ...]) -> bool:
    found = _normalise_path(finding_file)
    if not found:
        return False
    return any(found.endswith(e) or e.endswith(found) for e in expected)


def _keyword_matches(finding: Finding, keywords: tuple[str, ...]) -> bool:
    haystack = f"{finding.file} {finding.rule} {finding.text}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def score_case(case: Case, report: str | None) -> CaseResult:
    """Score one report against *case*."""
    if not report or not report.strip():
        return CaseResult(case.id, Outcome.NO_REPORT, None, ())
    findings = parse_report(report)
    blocking = tuple(f for f in findings if f.severity >= Severity.MAJOR)
    if case.kind == "control":
        outcome = Outcome.FALSE_ALARM if blocking else Outcome.CLEAN
        return CaseResult(case.id, outcome, None, blocking)
    assert case.expect is not None
    relevant = [
        f for f in findings if _file_matches(f.file, case.expect.files) and _keyword_matches(f, case.expect.keywords)
    ]
    if not relevant:
        return CaseResult(case.id, Outcome.MISSED, None, blocking)
    best = max(relevant, key=lambda f: f.severity)
    outcome = Outcome.CAUGHT if best.severity >= case.expect.min_severity else Outcome.CAUGHT_LOW_SEVERITY
    return CaseResult(case.id, outcome, best, blocking)

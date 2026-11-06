"""Unit tests for the review-agent eval harness (evals/harness.py, evals/run_review_evals.py).

No model is called: these keep the cases applicable to the current code and
prove the report parser and the scoring rules.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = REPO_ROOT / "evals"
CASES_DIR = EVALS_DIR / "cases"


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, EVALS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve the module by name
    spec.loader.exec_module(module)
    return module


harness = _load("harness", "harness.py")
runner = _load("run_review_evals", "run_review_evals.py")
CASES = harness.load_cases(CASES_DIR)

REPORT = """\
## Summary
Two problems.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | MAJOR | `src/rig_remote/models/scanning_task.py` | 240-246 | ADR-5 | passes=0 is clamped to 1 |
| 2 | MINOR | tests/test_scanning.py | 10 | test-naming | name does not describe the scenario |

## Details

### Finding 1 — MAJOR: ADR-5 (src/rig_remote/models/scanning_task.py:240)
The UI labels 0 as Infinite and the default config uses it, so infinite scans stop after one pass.

### Finding 2 — MINOR: test-naming (tests/test_scanning.py:10)
Rename it.
"""


def _case(kind: str = "seed", files=("src/rig_remote/models/scanning_task.py",), keywords=("infinite",), sev="MAJOR"):
    expect = None
    if kind == "seed":
        expect = harness.Expectation(files=tuple(files), keywords=tuple(keywords), min_severity=harness.Severity[sev])
    edit = harness.Edit(file="x.py", old="a", new="b")
    return harness.Case(id="c", kind=kind, title="t", pr_description="p", origin="o", edits=(edit,), expect=expect)


# --------------------------------------------------------------------------
# The committed cases
# --------------------------------------------------------------------------
def test_review_evals_cases_exist_with_seeds_and_controls():
    kinds = [case.kind for case in CASES]
    assert kinds.count("seed") >= 5 and kinds.count("control") >= 2
    assert len({case.id for case in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_review_evals_case_applies_to_current_code(case, tmp_path):
    for edit in case.edits:
        target = tmp_path / edit.file
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / edit.file, target)
    harness.apply_edits(case, tmp_path)  # raises StaleCaseError when the code moved on
    for edit in case.edits:
        assert edit.new in (tmp_path / edit.file).read_text(encoding="utf-8")


@pytest.mark.parametrize("case", [c for c in CASES if c.kind == "seed"], ids=lambda c: c.id)
def test_review_evals_seed_expectation_targets_an_edited_file(case):
    edited = {edit.file for edit in case.edits}
    assert set(case.expect.files) & edited, "a seed must expect a finding in a file it changes"


# --------------------------------------------------------------------------
# Loading and applying
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "toml",
    [
        'kind = "other"\ntitle = "t"\npr_description = "p"\n[[edit]]\nfile = "f"\nold = "a"\n',
        'kind = "seed"\ntitle = "t"\npr_description = "p"\n[[edit]]\nfile = "f"\nold = "a"\n',
        'kind = "control"\ntitle = "t"\npr_description = "p"\nedit = []\n',
        'kind = "seed"\ntitle = "t"\npr_description = "p"\n[expect]\nfiles = ["f"]\nkeywords = ["k"]\n'
        'min_severity = "HUGE"\n[[edit]]\nfile = "f"\nold = "a"\n',
    ],
    ids=["bad-kind", "seed-without-expect", "no-edits", "bad-severity"],
)
def test_review_evals_load_case_rejects_malformed_files(toml, tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(harness.CaseError):
        harness.load_case(path)


@pytest.mark.parametrize(("content", "old"), [("nothing here", "missing"), ("dup dup", "dup")])
def test_review_evals_apply_edits_rejects_stale_edits(content, old, tmp_path):
    (tmp_path / "x.py").write_text(content, encoding="utf-8")
    case = harness.Case("c", "control", "t", "p", "o", (harness.Edit("x.py", old, "new"),), None)
    with pytest.raises(harness.StaleCaseError):
        harness.apply_edits(case, tmp_path)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def test_review_evals_parse_report_reads_table_and_details():
    findings = harness.parse_report(REPORT)
    assert [(f.severity.name, f.file, f.rule) for f in findings] == [
        ("MAJOR", "src/rig_remote/models/scanning_task.py", "ADR-5"),
        ("MINOR", "tests/test_scanning.py", "test-naming"),
    ]
    assert "Infinite" in findings[0].text, "the details section is attached to its finding"


def test_review_evals_parse_report_falls_back_to_detail_headings():
    report = REPORT.split("## Details", 1)[1]
    findings = harness.parse_report(report)
    assert [(f.severity.name, f.file) for f in findings] == [
        ("MAJOR", "src/rig_remote/models/scanning_task.py"),
        ("MINOR", "tests/test_scanning.py"),
    ]


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("case", "report", "outcome"),
    [
        (_case(), REPORT, "CAUGHT"),
        (_case(sev="BLOCKER"), REPORT, "CAUGHT_LOW_SEVERITY"),
        (_case(keywords=("socket",)), REPORT, "MISSED"),
        (_case(files=("src/rig_remote/scanner_core.py",)), REPORT, "MISSED"),
        (_case(), "", "NO_REPORT"),
        (_case(kind="control"), REPORT, "FALSE_ALARM"),
        (_case(kind="control"), REPORT.replace("| 1 | MAJOR", "| 1 | MINOR"), "CLEAN"),
    ],
    ids=["caught", "low-severity", "wrong-keyword", "wrong-file", "no-report", "control-false-alarm", "control-clean"],
)
def test_review_evals_score_case_outcomes(case, report, outcome):
    assert harness.score_case(case, report).outcome is harness.Outcome[outcome]


def test_review_evals_write_summary_counts_outcomes(tmp_path):
    seed, control = _case(), _case(kind="control")
    runs = [
        runner.CaseRun(seed, False, "all green", REPORT, harness.score_case(seed, REPORT), "", 1.0),
        runner.CaseRun(control, True, "pytest", REPORT, harness.score_case(control, REPORT), "", 1.0),
    ]
    markdown = runner.write_summary(runs, tmp_path)
    assert "**1/1**" in markdown  # seed caught; also the CI-silent seed caught
    assert "false BLOCKER/MAJOR alarm: **1/1**" in markdown
    assert (tmp_path / "summary.json").is_file() and (tmp_path / "reports" / "c.md").is_file()

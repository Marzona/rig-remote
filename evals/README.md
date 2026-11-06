# Review-agent evals

These evals answer one question: **what does the review agent (`code_review_agent`)
actually catch?**

Each case is a small pull request applied to the current code:

- **Seeds** reintroduce a known defect: most are bugs this project really shipped,
  the rest break rules that only review enforces. Several seeds also change the
  tests and docs so that CI stays green. That mirrors the infinite-passes bug, where
  the tests agreed with the wrong rule. Those are the cases where only reviewer
  judgement can help.
- **Controls** are harmless changes. A BLOCKER or MAJOR finding on a control is a
  false alarm.

## What a run measures

| Column | Meaning |
|---|---|
| CI catches it? | whether `ruff`, `mypy` and the non-gqrx test suites fail on the seeded change (no model involved) |
| Reviewer outcome | `caught`, `caught (low severity)` or `missed` for seeds; `clean` or `false alarm` for controls |

The headline numbers are:

- seeds caught at the expected severity
- seeds that CI misses but the reviewer catches, which is the reviewer's added value
- controls that drew a false BLOCKER or MAJOR alarm

## Running

From the repository root, with the dev environment installed (`uv sync --group dev`):

```bash
python3 evals/run_review_evals.py --dry-run               # apply every case, no model calls
python3 evals/run_review_evals.py --dry-run --measure-ci  # also record what CI catches
python3 evals/run_review_evals.py --measure-ci            # full run: CI baseline and real reviews
python3 evals/run_review_evals.py --case infinite_passes_clamped   # one case
```

- **Where the code runs:** every case runs in a throwaway snapshot repository built
  from `HEAD`, so your checkout is never touched. Commit before running, because
  uncommitted changes are not part of `HEAD`.
- **No answer key for the reviewer:** the snapshot leaves out `evals/` and its test,
  and is a single fresh commit with no history. The reviewer can't read the expected
  findings, or the commit messages of the fixes the seeds undo. An early run
  without this did both.
- **What it costs:** a full run starts one headless Claude Code session per case
  (`claude --agent code_review_agent -p ...`). Each review also runs the
  verification suite through `scripts/review_worktree.sh`, so expect several
  minutes and real model usage per case.
- **A different reviewer:** pass `--reviewer-cmd` with a shell template containing
  `{prompt}`.

Results go to `evals/results/<UTC timestamp>/`:

- `summary.md`
- `summary.json`
- one raw report per case in `reports/`

Commit the results you want to keep, so claims like "the reviewer caught 6 of 8" can
be traced to the exact reports.

## Cases

Each case is one TOML file in `cases/`:

```toml
kind = "seed"                       # or "control"
title = "Short description"
origin = "Where the defect comes from (commit, or synthetic)"
pr_description = '''
What the author claims the change does. It is shown to the reviewer.
'''

[expect]                            # seeds only
files = ["src/rig_remote/models/scanning_task.py"]   # a finding must name one of these files
keywords = ["infinite"]             # ...and mention one of these (case-insensitive)
min_severity = "MAJOR"              # below this the outcome is "caught (low severity)"

[[edit]]                            # one or more exact text replacements
file = "src/rig_remote/models/scanning_task.py"
old = '''...'''                     # must occur exactly once
new = '''...'''
```

- **Edits are exact text replacements, not patches.** When the code changes, a case
  fails loudly instead of applying fuzzily: `tests/test_review_evals.py` (which runs
  in CI) fails with `StaleCaseError`, naming the case to update.
- **Adding a case:** copy the `old` text straight from the file, so whitespace
  matches. Pick keywords a correct finding would have to use (the concept, such as
  `infinite`, not the line number). Add a matching control when a seed is
  realistic enough that a reviewer might over-flag similar harmless changes.

## Limits

Keep these in mind when quoting results:

- **Keyword scoring is approximate.** A finding can name the right file and keyword
  for the wrong reason, or describe the bug in words the keywords miss. Read the
  reports behind any number you quote.
- **Results vary between runs.** The same case can be caught in one run and missed in
  the next; run more than once before drawing conclusions.
- **The sample is small.** Eight seeds show what kinds of defects get caught, not a
  rate to two decimal places.
- **Don't tune the agent on these cases.** Prompt changes made by looking at these
  cases will overfit to them. Keep new cases aside as a holdout before changing
  `code_review_agent.md` or `.claude/review/`.
- **CI coverage differs.** The CI column covers lint, types and tests only, not CI's
  packaging jobs.

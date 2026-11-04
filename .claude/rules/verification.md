---
paths:
  - src/**/*.py
  - tests/**/*.py
  - functional_tests/**/*.py
  - pyproject.toml
---
## Verification

This file is the single home for the verification commands; agents and other
docs point here. Run from the repository root (the directory with
`pyproject.toml`), in this order — fixers first, so the code that is
type-checked and tested is the code that gets committed:

```bash
.venv/bin/ruff check --fix ./src
.venv/bin/ruff format ./src
.venv/bin/mypy --config-file ./pyproject.toml ./src
.venv/bin/pytest tests/ -n 13
.venv/bin/pytest functional_tests/ -n 1 -m "not gqrx"
.venv/bin/pytest functional_tests/ -n 1 -m gqrx -rs
```

- Unit tests (`tests/`) run in parallel; functional tests (`functional_tests/`) run serially.
- `tests/test_architecture.py` enforces the invariants marked "test" in
  `.claude/architecture.md`; a failure there means the change breaks an ADR,
  not that the test needs loosening.

### Reporting

- The first five commands must exit 0. Never report a task done otherwise.
- The last command needs a live gqrx at 127.0.0.1:7356. When gqrx is not
  reachable its tests are skipped: report them as **"gqrx functional tests:
  NOT RUN (gqrx unavailable)"** with the skip count — never as passed, and not
  as a failure. If gqrx is reachable, failures there are real failures.

Project constraints (no async, no ORM, no ABC, config flow, exception
taxonomy, clamping) are in `.claude/architecture.md`.

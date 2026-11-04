---
paths:
  - src/**/*.py
  - tests/**/*.py
  - functional_tests/**/*.py
---
## Verification

After any code change to `src/`, run all of the following and fix all reported
issues before reporting the task complete:

```bash
mypy --config-file ./pyproject.toml ./src
ruff check --fix ./src/
pytest tests/ -n 13
pytest functional_tests/ -n 1
```

- Unit tests live in `tests/`, run with parallelism 13.
- Functional/integration tests live in `functional_tests/`, run serially (`-n 1`).
- Skip the `pytest functional_tests/` step only if the `functional_tests/` directory does not exist yet.

Never report a task as done if any tool exits with errors.

## Constraints

- **No async.** The project is intentionally thread + `Queue` based. Do not introduce
  `asyncio`, `anyio`, or similar.
- **No ORM.** File I/O uses `configparser` (INI) and `csv` only.
- **No ABC inheritance.** Use `typing.Protocol` and composition instead.

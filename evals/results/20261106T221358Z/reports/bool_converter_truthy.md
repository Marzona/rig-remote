## Summary

This PR swaps `parse_bool` for the builtin `bool` as the converter for the `wait` and `record` queue events in `ScannerCore._QUEUE_EVENT_CONVERTERS`. **Assessment: needs changes.** The PR's reasoning doesn't hold. `bool()` on a string only checks whether the string is empty, so the `"false"` the UI sends (`stmessenger.encode_bool`) becomes `True`. Unchecking "wait" or "record" during a scan would then switch the setting on. The change breaks ADR-1's wire-format rule ("never `bool(str)`, which is `True` for `"False"`") and 15 unit tests fail, including both tests that enforce that invariant.

- **Coverage:** 99% → 99%, but uncovered lines go from 21 to 27. The 6 new uncovered lines are the body of `parse_bool`, which is now dead code (`scanner_core.py` 31-36).
- **How it was run:** both runs used `scripts/review_worktree.sh` with network isolation via `unshare -rn`. For the base run I made a temporary detached worktree of HEAD inside the session scratchpad, ran the script from there, then removed the worktree. `git worktree list` now shows only the main checkout.

**Verification after the change:**

| Step | Result |
|---|---|
| `ruff check` | pass |
| `ruff format --check` | pass |
| `mypy` | pass |
| unit tests (`tests/`) | **FAIL**: 15 failed, 6573 passed, 1 xfailed |
| functional tests (not gqrx) | 91 passed |
| gqrx functional tests | **NOT RUN** (gqrx unavailable), 48 skipped |

**Verification on the base:** everything green, 6588 passed and 1 xfailed in `tests/`, 91 functional tests passed.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | src/rig_remote/scanner_core.py | 58-59 | ADR-1 wire format: queue booleans parsed strictly, never `bool(str)` | `bool("false")`, `bool("False")` and `bool("0")` all return `True`, so turning wait/record off mid-scan turns them on. Invalid values (`"yes"`, `"maybe"`, `"2"`) are no longer skipped with a warning. `""` becomes `False` without a warning. |
| 2 | BLOCKER | tests/test_scanning.py | — | Tool errors introduced by the change | 15 unit tests fail, including the two ADR-1 invariant tests (`test_scanning_core_process_queue_bool_parsing_strict` and `..._bool_invalid_skipped_with_warning`), plus `..._valid_event_parametric[event7-record-False]` and `..._bad_event_does_not_delay_valid_events[bad_event2]`. |
| 3 | MAJOR | src/rig_remote/scanner_core.py | 26-36 | coverage-decrease | `parse_bool` is no longer called by anything, so its body (lines 31-36) loses coverage: 21 → 27 uncovered lines in total. |
| 4 | MAJOR | .claude/architecture.md | 62-66, 305 | adr-not-updated | ADR-1 and the invariants table row "Queue booleans are parsed strictly, never with `bool(str)`" still name `scanner_core.parse_bool` as the parser. Changing this invariant would need an ADR change approved by the owner, and the right fix is to keep the invariant (see Finding 1). |

## Details

### Finding 1 — BLOCKER: ADR-1 strict boolean parsing (src/rig_remote/scanner_core.py:58-59)
ADR-1's wire format says booleans travel as exactly `"true"` or `"false"`. The receiver parses them strictly with `parse_bool` and skips anything else with a warning, "never `bool(str)`, which is `True` for `"False"`". The `parse_bool` docstring says the same. The PR description's claim that `bool()` "already does" this for the UI's strings is wrong: the UI sends `"false"`, and `bool("false") is True`.

**Before:**
```python
    _QUEUE_EVENT_CONVERTERS: dict[str, Callable[[str], int | bool]] = {
        "wait": bool,
        "record": bool,
```
**After:**
```python
    _QUEUE_EVENT_CONVERTERS: dict[str, Callable[[str], int | bool]] = {
        "wait": parse_bool,
        "record": parse_bool,
```

### Finding 2 — BLOCKER: tool errors introduced by the change (tests/test_scanning.py)
`pytest tests/` passes on the base and fails on the change. The failing cases are:
- `test_scanning_core_process_queue_bool_parsing_strict` with `ckb_wait`: `false`, `False`, `0`; with `ckb_record`: `False`, `0`
- `test_scanning_core_process_queue_bool_invalid_skipped_with_warning` with `yes`, `""`, `maybe`, `2` for both `ckb_wait` and `ckb_record`
- `test_scanning_core_process_queue_valid_event_parametric[event7-record-False]`
- `test_scanning_core_process_queue_bad_event_does_not_delay_valid_events[bad_event2]`

These tests encode the invariant correctly and should not be loosened. Restoring the converters as in Finding 1 fixes all 15.

**Before:** `"wait": bool, "record": bool`
**After:** `"wait": parse_bool, "record": parse_bool`

### Finding 3 — MAJOR: coverage-decrease (src/rig_remote/scanner_core.py:26-36)
`parse_bool` is still defined, but nothing calls it now, so lines 31-36 are uncovered. Total missed lines go from 21 to 27. The fix in Finding 1 restores the coverage. Deleting `parse_bool` would not be acceptable, because the ADR names it as the strict parser.

**Before:** `"wait": bool, "record": bool` (parse_bool is never called)
**After:** `"wait": parse_bool, "record": parse_bool`

### Finding 4 — MAJOR: adr-not-updated (.claude/architecture.md:62-66, 305)
The diff changes behaviour that ADR-1 and its invariants-table row describe, but the docs are not updated in the same change. Changing an ADR or invariant also needs the owner's approval first under the project's "Stop and ask" rules. The right fix is to drop the code change (Finding 1), not to edit the ADR.

**Before:** ADR-1 says "`scanner_core.parse_bool` … never `bool(str)`" while the code uses `bool`.
**After:** No ADR edit; revert the converters to `parse_bool` so the code matches ADR-1 again.

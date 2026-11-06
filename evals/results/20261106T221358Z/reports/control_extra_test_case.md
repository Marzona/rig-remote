## Summary

This PR adds one case, `("delay", 0, "delay", 0)`, to the parametrised `test_apply_update_clamps_and_logs` in `tests/test_scanning_task.py`. No source, config or docs change. The new case tests the boundary of `ScanningTask._check_delay` (`src/rig_remote/models/scanning_task.py:178-182`): `0` is the smallest valid delay, so it must be kept unchanged and must not log. The fixture builds the task with `delay=1`, so the update really changes the value and doesn't pass by accident. The test's own check `(len(caplog.records) > 0) == clamped` confirms that nothing is logged. With this case, the `apply_update` delay clamp is tested below the range (`-1`), at its boundary (`0`) and inside it (`9`), as the project's validation-path rule asks.

I ran all checks through `scripts/review_worktree.sh` with network isolation active (`unshare -rn` worked). Results:
- ruff check, ruff format --check and mypy all pass.
- `tests/`: 6589 passed, 1 xfailed.
- `functional_tests/` without gqrx: 91 passed.
- **gqrx functional tests: NOT RUN (gqrx unavailable)**, 48 skipped.

Coverage after the change is 99% (2768 statements, 21 missed). I did not measure the baseline separately: the read-only setup doesn't let me check out a clean HEAD, and the script always applies the diff. Coverage cannot have dropped, though, because nothing under `src/` changed and the delay branch was already covered by the `-1` and `9` cases. So coverage is 99% → 99%.

No architecture-protected paths are touched and no ADR or invariant is affected. The test file is 287 lines, well under the 600-line limit. **Assessment: pass with comments** (INFO only).

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | INFO | tests/test_scanning_task.py | 231-233 | readability | The new boundary case is placed after the in-range case `9` instead of between `-1` and `9`. Every other field in the table is ordered from out-of-range to in-range, so the boundary would be easier to spot in that order. Optional. |
| 2 | INFO | tests/test_scanning_task.py | 278-279 | global rule: every clamp path tested inside and outside its range | At construction, `delay` is only tested with an out-of-range value (`-2` → `0`). Fixtures in `tests/test_scanning.py:44,68` build tasks with `delay=0`, but nothing asserts that construction with `delay=0` keeps the value and doesn't log. This gap existed before the PR and is outside its scope. It would make a natural follow-up next to this change. |

## Details

### Finding 1 — INFO: readability (tests/test_scanning_task.py:231-233)
**Before:**
```python
    ("delay", -1, "delay", 0),
    ("delay", 9, "delay", 9),
    ("delay", 0, "delay", 0),
```
**After:**
```python
    ("delay", -1, "delay", 0),
    ("delay", 0, "delay", 0),     # boundary: valid, not clamped
    ("delay", 9, "delay", 9),
```

### Finding 2 — INFO: global rule, every clamp path tested inside and outside its range (tests/test_scanning_task.py:278-279)
**Before:**
```python
def test_scanning_task_init_negative_delay_clamped():
    assert _apply_task(delay=-2).delay == 0
```
**After:**
```python
@pytest.mark.parametrize("delay,expected,logged", [
    (-2, 0, True),
    (0, 0, False),
    (5, 5, False),
])
def test_scanning_task_init_delay_clamped(delay, expected, logged, caplog):
    with caplog.at_level("ERROR"):
        task = _apply_task(delay=delay)
    assert task.delay == expected
    assert bool(caplog.records) == logged
```

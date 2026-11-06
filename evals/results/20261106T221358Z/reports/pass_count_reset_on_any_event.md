## Summary

The PR changes both scan strategies to reset `pass_count = task.passes` whenever `ScannerCore.process_queue()` returns True, i.e. whenever *any* queue update was applied. Before, they used `consume_passes_update()`, which is True only after a `passes` update. To keep CI green, the PR also deletes the functional test that guards that difference and the invariant row in `.claude/architecture.md`. ADR-5 itself still says the opposite. This is a behaviour regression presented as a simplification. **Assessment: needs changes.**

Verification ran through `scripts/review_worktree.sh` with network isolation in effect (`unshare -rn`):
- ruff check, ruff format --check, mypy: all PASS
- `tests/`: PASS
- functional tests (not gqrx): PASS
- gqrx functional tests: 48 skipped, so **NOT RUN** (gqrx not available at 127.0.0.1:7356)

**Coverage before → after: not measured → 99% (2766 statements, 19 missed).** I could not get a baseline. The script only runs HEAD plus the diff, and stashing or a second worktree would break the read-only rule. The diff does not touch `tests/` and only removes two lines of `src/` per strategy, so I don't expect a drop, but this is an inference, not a measurement.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | MAJOR | src/rig_remote/frequency_scanner_strategy.py, src/rig_remote/bookmark_scanner_strategy.py | 194–195; 53–54 | ADR-5 (Passes) / correctness | Any queue event (`txt_delay`, `txt_sgn_level`, `ckb_wait`, …) now restarts the remaining-pass count. A 2-pass scan that gets a delay change during pass 2 runs 3 passes. With frequent updates, a finite scan may never end. |
| 2 | MAJOR | same files (+ scanner_core.py:96–100; bookmark_scanner_strategy.py:78) | — | correctness | A `passes` update applied inside `queue_sleep()` (or the bookmark strategy's other `process_queue` call at line 78) no longer resets the count. Those calls throw away the return value, and the next call in the strategy loop finds the queue empty and returns False. `consume_passes_update()` handled this case; its docstring says so explicitly. |
| 3 | MAJOR | functional_tests/test_queue_updates_mid_scan_hamlib.py | 442–458 (deleted) | Project rule "Stop and ask before… deleting tests to make a change pass" | `test_non_passes_update_mid_scan_does_not_restart_pass_count` was deleted. This is the test that would fail on finding 1. The PR does not mention it or say it was approved. |
| 4 | MAJOR | .claude/architecture.md | 308 (deleted row); ADR-5 text ~L163–166 | adr-not-updated / invariant change without approval | The invariant row "Only a `passes` update restarts the remaining-pass count" was deleted. The ADR-5 prose ("updates to any other field do not") was left in place, so the docs now contradict the code. Changing an invariant also needs owner approval, which the PR does not mention. |
| 5 | MINOR | src/rig_remote/scanner_core.py | 77, 111–112, 161–162, 251–260 | dead code | `_passes_updated` and `consume_passes_update()` no longer have production callers. Only `tests/test_scanning.py:1512` still calls them, so the unit test now covers unused code, and the `process_queue` docstring still points to it. |
| 6 | INFO | — | — | ADR-impact gate | The PR touches protected paths (`*_scanner_strategy.py`) and does update `architecture.md`, so the gate passes. The update removes the guarantee rather than documenting a new one, which is covered in finding 4. |

## Details

### Finding 1 — MAJOR: ADR-5 pass-count invariant (frequency_scanner_strategy.py:194, bookmark_scanner_strategy.py:53)
`process_queue` returns True when *any* whitelisted event is applied (`processed = True` at scanner_core.py:163). So every delay, signal-level or wait toggle resets `pass_count` to `task.passes`. Restore the old code (or the fix below) in both strategies.

**Before (this PR):**
```python
if self._core.process_queue(task):
    pass_count = task.passes
```
**After:**
```python
self._core.process_queue(task)
if self._core.consume_passes_update():
    pass_count = task.passes
```

### Finding 2 — MAJOR: passes updates applied while sleeping are lost (scanner_core.py:96–100)
`queue_sleep()` and the bookmark strategy's call at line 78 both call `process_queue(task)` and ignore what it returns. When a `passes` update is drained there, the next `if self._core.process_queue(task):` in the loop returns False and `pass_count` keeps its old value. The flag-based design survives across calls; the return value does not. The fix is the same as finding 1: keep reading the sticky flag.

**Before (this PR):** `pass_count` is reset only if the update arrives on exactly the `process_queue` call inside the strategy loop.
**After:** use `consume_passes_update()`, which also catches updates drained in `queue_sleep()` or at bookmark_scanner_strategy.py:78.

### Finding 3 — MAJOR: guarding test deleted (functional_tests/test_queue_updates_mid_scan_hamlib.py:442)
**Before (this PR):** the test is gone.
**After:** restore it unchanged:
```python
@pytest.mark.parametrize("event", [("txt_delay", "0"), ("txt_sgn_level", "-30"), ("ckb_wait", "false")])
def test_non_passes_update_mid_scan_does_not_restart_pass_count(event):
    ...
    assert rig.set_frequency.call_count == 4, ...
```
I'd also add a case where a `passes` update arrives during `queue_sleep()`, to cover finding 2.

### Finding 4 — MAJOR: invariant removed, ADR left contradictory (.claude/architecture.md:308)
**Before (this PR):** the row is deleted. ADR-5 still says "A mid-scan `passes` update restarts the remaining-pass count; updates to any other field do not."
**After:** restore the row:
```
| Only a `passes` update restarts the remaining-pass count | ADR-5 | test — `test_scanning_core_consume_passes_update_only_for_passes_events`, `test_non_passes_update_mid_scan_does_not_restart_pass_count`, `test_passes_update_mid_scan_restarts_pass_count` |
```
If the owner really wants "any update restarts the count", that is an ADR change. It needs approval first, then ADR-5 text and the table updated together in the same change.

### Finding 5 — MINOR: dead flag API (scanner_core.py:77, 161–162, 251–260)
**Before (this PR):** `_passes_updated` is still set but never read in production code. The `process_queue` docstring still says "A ``passes`` update is recorded for ``consume_passes_update``."
**After:** fixing finding 1 makes this go away. If the PR's direction were approved instead, remove `_passes_updated`, `consume_passes_update()` and its unit test in the same change, and fix the docstring.

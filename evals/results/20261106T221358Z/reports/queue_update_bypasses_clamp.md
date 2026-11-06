## Summary
The PR changes one line in `ScannerCore.process_queue` (`src/rig_remote/scanner_core.py:145`). For the six fields with converters (`wait`, `record`, `sgn_level`, `passes`, `interval`, `delay`), the converted value is now written with `setattr(task, key, …)` instead of going through `ScanningTask.apply_update`. That skips every mid-scan check: passes ≥ 0, interval ≥ the minimum step, delay ≥ 0, the inner-scan parameter checks, and the bool/int type guard. This breaks the ADR-5 mid-scan rule, which says `process_queue` "never assigns task fields directly". It also breaks the invariant "Mid-scan queue updates are validated and clamped like construction", which tests enforce. Five unit tests and two functional tests that pass on HEAD now fail. In `functional_tests/test_queue_updates_mid_scan_hamlib.py::test_interval_zero_update_mid_scan_is_clamped_and_pass_terminates[0|-1]`, an `interval` of `0` or `-1` sent through the real queue leaves the frequency sweep unable to finish. A user typing 0 into the interval box mid-scan would hang the scan. The speed gain is too small to measure: queue events come from users editing widgets, and `apply_update` does a dict lookup plus one or two comparisons. **Assessment: needs changes.** Coverage before → after: **99% → 99%** (2768 statements, 21 missed, same per-file table both times; total measured only because the `tests/` run failed). Verification ran in `scripts/review_worktree.sh` with network isolation (`unshare -rn`) in effect. The baseline came from a clean detached worktree at HEAD, where everything passed. ruff, ruff format and mypy pass on both. **48 gqrx functional tests were NOT RUN** (skipped: gqrx not available at 127.0.0.1:7356), on both runs.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | src/rig_remote/scanner_core.py | 145 | ADR-5 mid-scan updates; invariant "Mid-scan queue updates are validated and clamped like construction" (test-enforced); tool errors introduced by the change | Direct `setattr` skips `apply_update`, so `interval`/`passes`/`delay` are no longer clamped and type-checked mid-scan. 5 unit + 2 functional tests that pass on HEAD now fail; interval `0`/`-1` leaves the frequency pass unable to terminate. |
| 2 | MAJOR | src/rig_remote/scanner_core.py | 145 | ADR-5 "passes = 0 is infinite, only negatives clamped to 1"; global rule "Clamp, don't reject… and log" | `passes="-1"` stays `-1` and nothing is logged (test asserts `-1 == 1`). Negative delay stays negative (`-1 == 0`). No clamp, no log. |
| 3 | MINOR | src/rig_remote/scanner_core.py | 154 | Comments explain WHY (global rule) | The `except` comment "clamping is done in apply_update" becomes false for these fields once the change lands. |
| 4 | INFO | .claude/architecture.md | 288 | adr-not-updated / doc drift (already present at HEAD) | The "Mid-Scan Parameter Update" data-flow diagram already shows `setattr(task, "sgn_level", −40)`, which contradicts the ADR-5 text and the code at HEAD. It may have prompted this PR. Fix the diagram to `task.apply_update("sgn_level", -40)` in a separate change. |

## Details

### Finding 1 — BLOCKER: ADR-5 mid-scan clamping invariant (src/rig_remote/scanner_core.py:145)
ADR-5 says: "`ScannerCore.process_queue` never assigns task fields directly; every queue event goes through `ScanningTask.apply_update(name, value)`". With the change, only `range_min`/`range_max` still go through it. Failures seen in the isolated run that pass on the baseline:

- `tests/test_scanning.py::test_scanning_core_process_queue_clamps_out_of_range`:
  - interval `"0"`, `"-1"`, `"999"`: got `0`, `-1`, `999`, expected `1000`
  - passes `"-1"`: got `-1`, expected `1`
  - delay `"-1"`: got `-1`, expected `0`
- `functional_tests/test_queue_updates_mid_scan_hamlib.py::test_interval_zero_update_mid_scan_is_clamped_and_pass_terminates[0]` and `[-1]`: "frequency pass did not terminate after interval update"

The direct `setattr` also skips `_check_inner_scan_params()` and the bool/int type guard in `apply_update`. If you need a faster path, change `apply_update` itself so the validation stays in one place, but no hot path is involved here.

**Before (this PR):**
```python
elif key in self._QUEUE_EVENT_CONVERTERS:
    converter = self._QUEUE_EVENT_CONVERTERS[key]
    setattr(task, key, converter(param_value))
```
**After (restore):**
```python
elif key in self._QUEUE_EVENT_CONVERTERS:
    converter = self._QUEUE_EVENT_CONVERTERS[key]
    task.apply_update(key, converter(param_value))
```

### Finding 2 — MAJOR: clamp-and-log policy lost for mid-scan passes/delay (src/rig_remote/scanner_core.py:145)
With direct assignment, a negative `passes` is stored as is. The loop's `passes == INFINITE_PASSES` / remaining-count logic then gets a value the domain model never allows, and nothing is logged. This contradicts ADR-5 ("Only negative values are invalid; they are clamped to `1`") and the owner's global rule "clamp… and log the event". A negative `delay` is also kept, which `queue_sleep` then uses as `remaining`. Restoring the code in Finding 1 fixes this too.

**Before:**
```python
setattr(task, key, converter(param_value))  # passes=-1 kept, no log
```
**After:**
```python
task.apply_update(key, converter(param_value))  # _check_passes() clamps to 1 and logs
```

### Finding 3 — MINOR: misleading comment (src/rig_remote/scanner_core.py:154)
After this change the comment no longer describes the scalar path. It becomes accurate again once Finding 1 is reverted; no edit is needed then.

**Before (with this PR):**
```python
except (ValueError, TypeError) as exc:  # parse failures; clamping is done in apply_update
```
**After (if direct assignment were kept, which it should not be):**
```python
except (ValueError, TypeError) as exc:  # parse failures only; scalar fields are NOT clamped here
```

### Finding 4 — INFO: data-flow diagram already wrong at HEAD (.claude/architecture.md:288)
This is not caused by the PR, but it contradicts ADR-5 and may have been the basis for the change. Correct it in a separate doc fix.

**Before:**
```
       → _QUEUE_EVENT_CONVERTERS["sgn_level"](value) → int(−40)
       → setattr(task, "sgn_level", −40)
```
**After:**
```
       → _QUEUE_EVENT_CONVERTERS["sgn_level"](value) → int(−40)
       → task.apply_update("sgn_level", −40)   (assign + ADR-5 clamps)
```

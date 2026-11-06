## Summary

This change makes `ScanningTask._check_passes` clamp `passes <= 0` to 1 instead of `< 0`. It also rewrites ADR-5 "Passes", deletes the invariants-table row "`passes` = 0 means infinite", and deletes the three tests that enforced it.

The PR description says a value of 0 "made the pass counter start at zero". The code shows otherwise: `ScannerCore.pass_count_update` handles 0 on purpose as `INFINITE_PASSES`, meaning scan until stopped. The UI labels it "0=Infinite", the default config ships `passes = "0"`, and the README advertises "Selectable infinite or fixed scan passes". So this is not a fix. It removes a user-facing feature and silently changes what the shipped default does.

The project's `CLAUDE.md` requires stopping to ask first before changing public behaviour or config defaults, changing an ADR or invariant, or deleting tests to make a change pass. This change does all three. The likely trigger is a gqrx functional test that already contradicts ADR-5 at HEAD; that test is what should be fixed.

**Verdict: needs changes.**

**Verification:** I ran `scripts/review_worktree.sh` on the change and, for the baseline, on a clean worktree at HEAD. Network isolation via `unshare -rn` was in effect both times.
- ruff, ruff format and mypy passed on both.
- Unit tests: 6588 passed at HEAD → 6586 passed with the change (2 tests deleted), 1 xfailed both times.
- Functional tests (not gqrx): 91 → 90 passed (1 deleted).
- gqrx functional tests: **NOT RUN**. All 48 skipped because gqrx was not reachable at 127.0.0.1:7356.
- Coverage: **99% → 99%** (2768 statements, 21 missed, both runs).

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | src/rig_remote/models/scanning_task.py | 239-243 | Project CLAUDE.md "Stop and ask" (public behaviour / config default); correctness | `passes=0` (shipped default, UI "0=Infinite") now becomes a single pass and logs an ERROR on every default scan. Users who rely on the default silently lose continuous scanning. The PR's premise is wrong: `pass_count_update` handles 0 as infinite. |
| 2 | BLOCKER | .claude/architecture.md; tests/test_scanning.py; tests/test_scanning_task.py; functional_tests/test_queue_updates_mid_scan_hamlib.py | arch 162-165 + removed table row; test_scanning.py 1491; test_scanning_task.py 228, 278-286; hamlib 409-439 | Project CLAUDE.md "Stop and ask" (changing an invariant/ADR; deleting tests to make a change pass) | A documented ADR-5 invariant and its three enforcing tests are deleted, and a parametrized expectation is flipped, all so the new behaviour passes. No sign the owner approved this. |
| 3 | MAJOR | src/rig_remote/scanner_core.py | 238-243 | Correctness / consistency | If the change stood, the `INFINITE_PASSES` branch in `pass_count_update` (and its docstring) is dead code, while `test_scanning_core_pass_count_update_infinite_stays_active_over_many_passes` still tests it. `ui_renderer.py:295` ("0=Infinite"), `app_config.py:145` (default `"0"`) and README.md:16 now describe behaviour that no longer exists. |
| 4 | MINOR | src/rig_remote/models/scanning_task.py | 241 | Naming | `self.passes <= INFINITE_PASSES` uses the "infinite" sentinel as a lower bound, which reads backwards. |
| 5 | MINOR | tests/test_scanning_task.py | 278 | Style | The file now ends without a trailing newline. |
| 6 | INFO | functional_tests/test_frequency_scanning_gqrx.py | 359 | Problem already at HEAD | `test_scanning_frequency_negative_passes_clamped_to_one` is parametrized with `0` and expects a clamp to 1. That contradicts ADR-5 at HEAD and would fail against a live gqrx. The gqrx tests always skip offline, so it went unnoticed. Fix this test, not the model. |

## Details

### Finding 1 — BLOCKER: unapproved public-behaviour change / wrong premise (src/rig_remote/models/scanning_task.py:239-243)
`ScannerCore.pass_count_update` (scanner_core.py:242) returns early when `pass_count == INFINITE_PASSES`, so 0 never "starts the counter at zero". It keeps the scan active until `terminate()`. The deleted test `test_infinite_passes_keep_scanning_until_terminate` checked exactly that against a real scan.

With this change, anyone using the default `passes = "0"` or typing 0 next to the "0=Infinite" label gets one pass plus an ERROR log line. This changes a config default's meaning and the UI's contract. The project rules require asking the owner before doing that. Revert the model change:

**Before:**
```python
    def _check_passes(self) -> None:
        """A scan needs at least one pass; clamp anything lower to 1."""
        if self.passes <= INFINITE_PASSES:
            logger.error("scan passes must be >= 1, got %i, updated to 1", self.passes)
            self.passes = 1
```
**After:**
```python
    def _check_passes(self) -> None:
        """Clamp negative pass counts; 0 (INFINITE_PASSES) means scan until stopped.

        A negative value is a typo, not a request to scan forever, so it is
        clamped to the smallest finite count (1) rather than to 0.
        """
        if self.passes < INFINITE_PASSES:
            logger.error("scan passes must be >= 0 (0 = infinite), got %i, updated to 1", self.passes)
            self.passes = 1
```
If the owner really wants to drop infinite scanning, that is a separate, approved change. It must also update the UI label, `DEFAULT_CONFIG` (or migrate existing INI files), the README and `scanner_core`.

### Finding 2 — BLOCKER: invariant and its tests deleted to fit the change (.claude/architecture.md, tests)
The invariants row "`passes` = 0 means infinite; only negatives are clamped (to 1)" and its three enforcing tests are removed, and the `("passes", 0, "passes", 0)` case is flipped to `1`. Updating the ADR in the same change avoids `adr-not-updated`. But changing an invariant and deleting tests both need owner approval first. Restore everything:

**Before (architecture.md, ADR-5):**
```
assigns and re-runs the same checks as construction (passes ≥ 1, interval ≥
...
**Passes:** a scan runs at least one pass; values below 1 are clamped to 1.
```
**After:**
```
assigns and re-runs the same checks as construction (passes ≥ 0, interval ≥
...
**Passes:** `0` is `INFINITE_PASSES` — scan until stopped. The UI labels it
"0=Infinite" and the default config uses it, so it is a valid value, never
clamped. Only negative values are invalid; they are clamped to `1` (a typo
must not silently become a scan that never ends). A mid-scan `passes` update
restarts the remaining-pass count; updates to any other field do not.
```
Also restore the table row `| `passes` = 0 means infinite; only negatives are clamped (to 1) | ADR-5 | test — ... |`. Restore `test_scanning_task_passes_zero_means_infinite`, `test_scanning_core_process_queue_passes_zero_means_infinite` and `test_infinite_passes_keep_scanning_until_terminate`. Revert the parametrize case:

**Before:** `("passes", 0, "passes", 1),`
**After:** `("passes", 0, "passes", 0),   # INFINITE_PASSES is valid, not clamped`

### Finding 3 — MAJOR: half-removed feature leaves dead code and stale UI/docs (src/rig_remote/scanner_core.py:238-243)
If the new semantics were kept, `pass_count_update` could never receive 0 from a validated task. That leaves the branch, its docstring and the surviving `..._infinite_stays_active_over_many_passes` test describing unreachable behaviour. The "0=Infinite" label, the `"passes": "0"` default and the README would all be wrong.

**Before:**
```python
        if pass_count == INFINITE_PASSES:
            return pass_count
```
**After:** reverting per Finding 1 fixes this. If the owner approves removing the feature, delete this branch and the `INFINITE_PASSES` constant, change the label and default, and add an INI migration note.

### Finding 4 — MINOR: sentinel used as a bound (src/rig_remote/models/scanning_task.py:241)
**Before:** `if self.passes <= INFINITE_PASSES:`
**After:** moot after reverting. Otherwise use `if self.passes < MIN_PASSES:` with `MIN_PASSES = 1`.

### Finding 5 — MINOR: missing final newline (tests/test_scanning_task.py:278)
**Before:** `    assert _apply_task(delay=-2).delay == 0\ No newline at end of file`
**After:** `    assert _apply_task(delay=-2).delay == 0` followed by `\n`.

### Finding 6 — INFO: gqrx test already contradicts ADR-5 at HEAD (functional_tests/test_frequency_scanning_gqrx.py:359)
This is probably what led to the PR. Fix it as a separate change that matches ADR-5:

**Before:**
```python
@pytest.mark.parametrize("passes", [-3, -1, 0])
def test_scanning_frequency_negative_passes_clamped_to_one(passes):
    """passes < 1 is silently clamped to 1; the scan executes exactly once."""
```
**After:**
```python
@pytest.mark.parametrize("passes", [-3, -1])
def test_scanning_frequency_negative_passes_clamped_to_one(passes):
    """Negative passes are clamped to 1; the scan executes exactly once (0 = infinite, ADR-5)."""
```

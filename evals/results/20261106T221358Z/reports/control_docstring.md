## Summary

This PR adds one docstring to `ScannerCore.should_stop` in `src/rig_remote/scanner_core.py:90`. Nothing else changes. `scanner_core.py` is a protected architecture path in `scripts/check_adr_impact.py:50`, so the author gave `ADR-impact: none, because this only adds a docstring and changes no behaviour`. That reason holds: the diff is a single docstring line, so no structure, invariant or extension point changes. ADR-1, 2, 3, 7 and 9 are not affected, and both "review only" invariants (the one-TCP-connection rule for the gqrx backend under ADR-4, and the ADR-9 exception taxonomy) are untouched.

The problem is that the docstring is incomplete. It lists two reasons the scan stops, but there are three. **Assessment: pass with comments.**

Verification ran in `scripts/review_worktree.sh` with network isolation in effect (`unshare -rn`):
- ruff check, ruff format --check and mypy: PASS
- `tests/`: 6588 passed, 1 xfailed
- functional tests without gqrx: 91 passed
- **gqrx functional tests: NOT RUN (gqrx unavailable)**, 48 skipped

**Coverage:** after the change it is 99% (2768 statements, 21 missed). I could not get a separate baseline run: the script always applies the uncommitted diff, and the read-only rules stop me from stashing. A docstring is not a statement for coverage.py, though, so the before figure has to be the same 2768 / 21 / 99%. Coverage does not decrease.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | MINOR | src/rig_remote/scanner_core.py | 90 | Global rule: comments/docstrings must be accurate | The docstring names two ways the scan stops (terminated, or last pass finished). It leaves out the third: `channel_tune` also clears `_scan_active` on a communications error (lines 188, 199). |
| 2 | INFO | (commit message) | — | ADR-impact gate (`scripts/check_adr_impact.py`) | The `ADR-impact: none, because …` trailer is only in the PR description so far. The CI `adr-impact` job reads it from the commit, so it must be in the commit message. The stated reason is believable. |

## Details

### Finding 1 — MINOR: docstring is incomplete (src/rig_remote/scanner_core.py:90)

`_scan_active` is set to `False` in four places:
- `terminate()` (line 87)
- `pass_count_update()` after the last pass (line 248)
- `channel_tune()` on `OSError` / `TimeoutError` / `Hamlib.error` while setting the frequency (line 188)
- `channel_tune()` on the same errors while setting the mode (line 199)

Both strategies call `should_stop()` to leave their loops (`bookmark_scanner_strategy.py:49`, `frequency_scanner_strategy.py:182`). Anyone reading the new docstring would conclude that a rig communications failure does not stop the scan, which is wrong.

**Before:**
```python
    def should_stop(self) -> bool:
        """Return True once the scan was terminated or finished its last pass."""
        return not self._scan_active
```

**After:**
```python
    def should_stop(self) -> bool:
        """Return True once the scan must end: terminated, last pass finished,
        or a rig communications error while tuning."""
        return not self._scan_active
```

### Finding 2 — INFO: the trailer must be in the commit (commit message)

**Before:** the trailer is only in the PR description; the change is not committed yet.

**After:** the commit message ends with:
```
ADR-impact: none, because this only adds a docstring and changes no behaviour.
```

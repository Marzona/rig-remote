## Summary

The PR adds one line to `RigRemoteScanHandlersMixin._process_entry` (`src/rig_remote/ui_scan_handlers.py:172`). It records the last successfully edited widget in `self._last_edited_widget`, to prepare for undo later. **Assessment: needs changes.** The mixin now sets an attribute it never declares, which breaks ADR-6 ("mixins must not own state"). The architecture test for that rule fails, so the unit suite no longer passes. mypy, ruff check and ruff format still pass, and so do the non-gqrx functional tests (91 passed). **Coverage before → after:** 99% → 99%. TOTAL went from 2768 statements with 21 missed to 2769 with 21 missed, so there is no decrease. I took the baseline by running `scripts/review_worktree.sh` in a clean clone of HEAD, because the script has no base-run option and I can't stash in this checkout. Network isolation was in effect for both runs (`unshare -rn`). **gqrx functional tests: NOT RUN (gqrx unavailable), 48 skipped.**

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | src/rig_remote/ui_scan_handlers.py | 172 | ADR-6 / tool error introduced by change | The mixin sets `self._last_edited_widget` without declaring it on the class, and `RigRemote.__init__` never sets it. `tests/test_architecture.py::test_mixins_hold_no_instance_state[rig_remote/ui_scan_handlers.py-RigRemoteScanHandlersMixin]` fails (1 failed, 6587 passed); on HEAD the suite passes (6588 passed). |
| 2 | MAJOR | src/rig_remote/ui_scan_handlers.py | 172 | missing-test (global rule: Tests) | Existing tests run the new line (the file stays at 100%), but nothing checks the value it stores. The attribute also stays unset until the first successful numeric edit, so later undo code reading it would hit `AttributeError`. |
| 3 | INFO | src/rig_remote/ui_scan_handlers.py | 150–172 | correctness note | The value is only recorded on the numeric success path. Hostname edits (early `return` at line 155), invalid input, and the empty-field "use default" path that sets `params_last_content` (lines 137–138) are not recorded. That is fine for now, but the undo design should decide whether this is intended. |

## Details

### Finding 1 — BLOCKER: ADR-6 mixin holds undeclared instance state (src/rig_remote/ui_scan_handlers.py:172)

ADR-6 says all instance attributes live on `RigRemote`, and each mixin declares the attributes it uses as class-level annotations. The test reports:

```
rig_remote/ui_scan_handlers.py:172: RigRemoteScanHandlersMixin._process_entry assigns
self._last_edited_widget, which is not annotated on the class; declare
'_last_edited_widget: <type>' on RigRemoteScanHandlersMixin or move the state to RigRemote
```

Fix it by declaring the attribute on the mixin and setting it in `RigRemote.__init__`, next to `params_last_content` in `ui_qt.py:78`. Don't loosen the test.

**Before:**
```python
# ui_scan_handlers.py — RigRemoteScanHandlersMixin
    ac: AppConfig
    params: dict[str, Any]
    params_last_content: dict[str, Any]
    ...
# ui_qt.py — RigRemote.__init__
        self.params_last_content: dict[str, Any] = {}
```
**After:**
```python
# ui_scan_handlers.py — RigRemoteScanHandlersMixin
    ac: AppConfig
    params: dict[str, Any]
    params_last_content: dict[str, Any]
    # Last widget whose value was accepted; groundwork for undo of scan parameters.
    _last_edited_widget: str | None
    ...
# ui_qt.py — RigRemote.__init__
        self.params_last_content: dict[str, Any] = {}
        self._last_edited_widget: str | None = None
```

This only follows the existing ADR-6 pattern, so neither ADR-6 nor the invariants table needs to change.

### Finding 2 — MAJOR: new state has no test (src/rig_remote/ui_scan_handlers.py:172)

No test checks what the new attribute holds, and before Finding 1's fix it isn't initialised. Add a parametrised test next to the existing `_process_entry` tests in `tests/test_ui_qt.py`. It should show that a valid numeric entry records the widget name, and that invalid input and hostname entries leave the previous value unchanged.

**Before:**
```python
# (no test)
```
**After:**
```python
@pytest.mark.parametrize(
    "widget_name, text, expected",
    [
        ("txt_sgn_level", "-40", "txt_sgn_level"),   # valid numeric → recorded
        ("txt_sgn_level", "abc", None),              # invalid → unchanged
        ("txt_hostname1", "localhost", None),        # hostname path → unchanged
    ],
)
def test_process_entry_records_last_edited_widget(rig_remote_window, widget_name, text, expected):
    widget = rig_remote_window.params[widget_name]
    widget.setText(text)
    rig_remote_window._process_entry(_WidgetEvent(widget, widget_name), silent=True)
    assert rig_remote_window._last_edited_widget == expected
```
Adapt the fixture name to whatever `tests/test_ui_qt.py` already uses. Another option is to keep this line out of the PR and add it with the undo feature, together with its first reader and tests.

### Finding 3 — INFO: which edits count as "last edited" (src/rig_remote/ui_scan_handlers.py:150–172)

No action needed. Only edits that parse as integers are recorded. The hostname branch returns before line 172, and the empty-field "use default" path changes `params_last_content` without updating `_last_edited_widget`. Worth deciding on purpose when undo is designed.

**Before:**
```python
        self.params_last_content[widget_name] = event_list_value
        self._last_edited_widget = widget_name
```
**After:** (unchanged; design note only)

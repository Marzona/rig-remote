## Summary
The change makes `BookmarksManager._detect_format` raise a bare `ValueError` instead of `BookmarkFormatError` when a bookmark file's format is not recognised, and updates the unit test to match. All checks pass: ruff, format, mypy, 6588 unit tests (plus 1 xfailed) and 91 functional tests. The 48 gqrx tests were **NOT RUN** because no gqrx was available, and network isolation (`unshare -rn`) was in effect. **Assessment: needs changes.** The pull request's reason for the change is false: the only caller (`ui_handlers._import_bookmarks`) does not catch `ValueError`. The change also removes the only raise site of an ADR-9 taxonomy exception without updating ADR-9 or `exceptions.py`. **Coverage:** after the change it is 99% total (2768 statements, 21 missed), with `bookmarksmanager.py` at 100% (107/107). I did not measure the before figure separately: `review_worktree.sh` always applies the diff, and the read-only hook stops me from getting a clean HEAD tree. The diff swaps one statement for another on a line the same parametrized test already covers, so the statement count is unchanged and I see no sign of a coverage drop.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | MAJOR | src/rig_remote/bookmarksmanager.py | 171-173 | ADR-9 (exception taxonomy) / `adr-not-updated` | Replaces the `RetriableError` subclass `BookmarkFormatError` with a bare `ValueError`. ADR-9 names a malformed bookmark as a retriable case and says a bare `ValueError` gives no such signal. `BookmarkFormatError` is now dead code in `exceptions.py`, and ADR-9 and the invariants table were not updated. |
| 2 | MAJOR | src/rig_remote/ui_handlers.py | 154-156 | correctness (error handling) | The PR says "callers already handle ValueError". The only caller, `_import_bookmarks`, has no `try`/`except`, so an unrecognised file still raises out of a Qt slot uncaught. The diff does not fix this, and its stated reason for the change is wrong. |
| 3 | MINOR | tests/test_bookmarksmanager.py | 9 | test hygiene | `from rig_remote.exceptions import BookmarkFormatError` is now unused. |
| 4 | INFO | tests/test_bookmarksmanager.py | 140 | test precision | `pytest.raises(ValueError)` is very broad: any `ValueError` raised later in import (for example from `Channel` parsing) would also pass the test. Add `match="No parser found"`. |

## Details

### Finding 1 — MAJOR: ADR-9 exception taxonomy / adr-not-updated (src/rig_remote/bookmarksmanager.py:171-173)
ADR-9 (`.claude/architecture.md:221-233`) says failure types live in `exceptions.py` as `NonRetriableError` / `RetriableError` subclasses. It names "a malformed bookmark row" as the retriable example and states that "Bare `Exception` / `ValueError` / `RuntimeError` give the loop no such signal". `BookmarkFormatError(RetriableError)` exists for exactly this case. After the diff, nothing in `src/` raises it.

The ADR scope says "scan-loop contexts", and `import_bookmarks` is currently reached only from the UI. So whether this is strictly in scope is debatable. Either way, the diff changes the taxonomy without touching ADR-9 or `exceptions.py`. Per `.claude/CLAUDE.md`, changing or making an exception to an ADR needs the owner to sign off first.

Two acceptable fixes:
- **(a) Preferred:** keep the domain exception and handle it at the caller (see Finding 2).
- **(b)** If the owner agrees the custom type is unnecessary: in the same change, delete `BookmarkFormatError` from `exceptions.py` and update ADR-9 (or its Scope paragraph) to say bookmark-file format detection is outside the taxonomy. `exceptions.py` is a protected path for `scripts/check_adr_impact.py`, so the gate will then require the `architecture.md` update.

**Before:**
```python
        message = f"No parser found for filename {filename}"
        logger.error(message)
        raise ValueError(message)
```
**After (option a):**
```python
        message = f"No parser found for filename {filename}"
        logger.error(message)
        raise BookmarkFormatError(message)
```

### Finding 2 — MAJOR: correctness, the PR's premise is false (src/rig_remote/ui_handlers.py:154-156)
The PR says "callers already handle ValueError for bad input". `grep import_bookmarks src/` finds exactly one caller, and it does not catch anything:
```python
    def _import_bookmarks(self, bookmarks_file_path: Path) -> None:
        bookmark_list = self.bookmarks.import_bookmarks(bookmarks_file_path)
```
If the user picks a non-bookmark CSV, the exception still escapes the Qt slot, both before and after this diff. Also, `_detect_format` opens the file with `open()`, so an unreadable file raises `OSError`, which is not handled either. Fix this at the caller, whichever exception type is chosen:

**Before:**
```python
        bookmark_list = self.bookmarks.import_bookmarks(bookmarks_file_path)
        if not bookmark_list:
            return
```
**After:**
```python
        try:
            bookmark_list = self.bookmarks.import_bookmarks(bookmarks_file_path)
        except (BookmarkFormatError, OSError) as err:
            logger.warning("Bookmark import failed for %s: %s", bookmarks_file_path, err)
            QMessageBox.warning(self._parent(), "Import bookmarks", str(err))
            return
        if not bookmark_list:
            return
```
Add a unit test in `tests/test_ui_qt.py` that sets `import_bookmarks = Mock(side_effect=BookmarkFormatError("x"))` and asserts that nothing is inserted.

### Finding 3 — MINOR: unused import (tests/test_bookmarksmanager.py:9)
**Before:**
```python
from rig_remote.exceptions import BookmarkFormatError
```
**After:** remove the line if option (b) is chosen. Under option (a), keep it and restore `pytest.raises(BookmarkFormatError)`.

### Finding 4 — INFO: broad exception assertion (tests/test_bookmarksmanager.py:140)
**Before:**
```python
    with pytest.raises(ValueError):
```
**After:**
```python
    with pytest.raises(BookmarkFormatError, match="No parser found"):
```

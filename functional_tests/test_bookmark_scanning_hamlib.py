"""
Functional tests for bookmark scanning.

Exercises the full bookmark scan pipeline end-to-end:
  1. Loads bookmarks from the project's test CSV file via BookmarksManager.
  2. Runs a bookmark scan via create_scanner() using a real RigCtl whose
     _send_message is replaced with a recording Mock (no network I/O).
  3. Asserts that every non-locked bookmark generates the correct rigctl
     commands (``F <freq>`` and ``M <mode>``).
  4. Asserts that the configured per-bookmark delay is honoured: total
     accumulated sleep time equals ``delay × non-locked-bookmark-count``.

Mock boundary: only ``RigCtl._send_message`` and ``STMessenger`` are mocked.
All internal objects (ScannerCore, BookmarkScannerStrategy, Scanning2) are
real instances.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from rig_remote.bookmarksmanager import BookmarksManager
from rig_remote.disk_io import LogFile
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.stmessenger import STMessenger


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BOOKMARK_FILE = (
    Path(__file__).parent.parent / "tests" / "test_files" / "test-rig_remote-bookmarks.csv"
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_bookmarks():
    """Load bookmarks from the project's test CSV file."""
    return BookmarksManager().load(str(BOOKMARK_FILE))


def _non_locked(bookmarks):
    """Return only the bookmarks that are not locked out."""
    return [bm for bm in bookmarks if bm.lockout != "L"]


def _make_rigctl() -> RigCtl:
    """Real RigCtl bound to localhost — _send_message will be replaced."""
    return RigCtl(endpoint=RigEndpoint(hostname="localhost", port=4532, number=1))


def _wire_send_message(rigctl: RigCtl, level: str = "-500.0"):
    """Replace RigCtl._send_message with a recording Mock.

    Returns a list that accumulates every request string passed to
    _send_message, in call order.  Level-query requests (``"l"``) return
    *level* so that ``get_level()`` can parse a float; all other requests
    return an empty string.

    The level default ``"-500.0"`` is well below any scan threshold
    (threshold = sgn_level × 10 = -40 × 10 = -400), so no signal is
    detected by default.
    """
    sent = []

    def _side_effect(request):
        sent.append(request)
        return level if request == "l" else ""

    rigctl._send_message = Mock(side_effect=_side_effect)
    return sent


def _make_queue() -> Mock:
    """STMessenger stub: queue is always empty (no UI events during scan)."""
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _fast_config(delay_seconds: int = 0) -> ScanningConfig:
    """ScanningConfig with zero sleeps for tune/signal; delay controls
    queue_sleep behaviour via the ScanningTask, not the config."""
    return ScanningConfig(
        time_wait_for_tune=0.0,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _bm_task(bookmarks, delay: int = 0) -> ScanningTask:
    return ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmarks_list=[],
        range_min=88_000_000,
        range_max=108_000_000,
        interval=1_000_000,
        delay=delay,
        passes=1,
        sgn_level=-40,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=bookmarks,
    )


# ---------------------------------------------------------------------------
# Test: all expected F commands are sent for every non-locked bookmark
# ---------------------------------------------------------------------------

def test_bookmark_scanning_all_frequencies_sent():
    """Every non-locked bookmark's frequency is sent as ``F <freq>`` exactly once."""
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()
    sent = _wire_send_message(rigctl)

    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_fast_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )
    scanner.scan(_bm_task(bookmarks))

    freq_commands_sent = [s for s in sent if s.startswith("F ")]
    expected_freq_commands = [f"F {bm.channel.frequency}" for bm in active]

    assert sorted(freq_commands_sent) == sorted(expected_freq_commands), (
        f"Frequency mismatch.\n"
        f"  Expected : {sorted(expected_freq_commands)}\n"
        f"  Got      : {sorted(freq_commands_sent)}"
    )


# ---------------------------------------------------------------------------
# Test: all expected M commands are sent for every non-locked bookmark
# ---------------------------------------------------------------------------

def test_bookmark_scanning_all_modes_sent():
    """Every non-locked bookmark's modulation is sent as ``M <mode>`` exactly once."""
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()
    sent = _wire_send_message(rigctl)

    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_fast_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )
    scanner.scan(_bm_task(bookmarks))

    mode_commands_sent = [s for s in sent if s.startswith("M ")]
    expected_mode_commands = [f"M {bm.channel.modulation}" for bm in active]

    assert sorted(mode_commands_sent) == sorted(expected_mode_commands), (
        f"Mode mismatch.\n"
        f"  Expected : {sorted(expected_mode_commands)}\n"
        f"  Got      : {sorted(mode_commands_sent)}"
    )


# ---------------------------------------------------------------------------
# Test: F then M order is preserved for each bookmark
# ---------------------------------------------------------------------------

def test_bookmark_scanning_frequency_before_mode_for_each_bookmark():
    """For every bookmark the ``F <freq>`` command is immediately followed by
    its ``M <mode>`` command in the _send_message call sequence.

    Uses the positions of all ``F`` commands to locate each bookmark's slot
    in the call list, avoiding false matches from shared mode strings (e.g.
    multiple bookmarks with ``M AM``).
    """
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()
    sent = _wire_send_message(rigctl)

    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_fast_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )
    scanner.scan(_bm_task(bookmarks))

    # channel_tune issues F then M back-to-back; locate each F by its index
    # in the full call list and verify the very next command is the matching M.
    f_indices = [i for i, s in enumerate(sent) if s.startswith("F ")]

    assert len(f_indices) == len(active), (
        f"Expected {len(active)} F commands, found {len(f_indices)}"
    )

    for bm, f_idx in zip(active, f_indices):
        freq_cmd = f"F {bm.channel.frequency}"
        mode_cmd = f"M {bm.channel.modulation}"

        assert sent[f_idx] == freq_cmd, (
            f"Bookmark {bm.id}: expected {freq_cmd!r} at position {f_idx}, "
            f"got {sent[f_idx]!r}"
        )
        assert sent[f_idx + 1] == mode_cmd, (
            f"Bookmark {bm.id}: expected {mode_cmd!r} immediately after "
            f"{freq_cmd!r}, got {sent[f_idx + 1]!r}"
        )


# ---------------------------------------------------------------------------
# Test: delay is applied between bookmarks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delay", [1, 2, 3])
def test_bookmark_scanning_delay_matches_config(delay):
    """Total accumulated sleep time equals ``delay × non-locked-bookmark-count``.

    ``queue_sleep`` calls ``_sleep(1)`` *delay* times per bookmark.
    With ``time_wait_for_tune=0`` and ``no_signal_delay=0`` all other
    sleep calls contribute zero, so the sum of all recorded sleep durations
    equals exactly ``delay × len(active_bookmarks)``.
    """
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()
    _wire_send_message(rigctl)

    sleep_calls = []

    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_fast_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda duration: sleep_calls.append(duration),
    )
    scanner.scan(_bm_task(bookmarks, delay=delay))

    # queue_sleep contributes `delay` calls of 1 second per active bookmark.
    queue_sleep_calls = [d for d in sleep_calls if d == 1]
    expected_total_sleep_calls = delay * len(active)

    assert len(queue_sleep_calls) == expected_total_sleep_calls, (
        f"Expected {expected_total_sleep_calls} one-second sleep calls "
        f"({delay}s delay × {len(active)} bookmarks), "
        f"got {len(queue_sleep_calls)}"
    )

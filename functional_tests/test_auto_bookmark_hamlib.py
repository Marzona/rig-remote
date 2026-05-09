"""
Functional tests for the auto-bookmark state machine in FrequencyScannerStrategy.

These tests exercise the full scan pipeline — ScanningConfig, ScannerCore,
FrequencyScannerStrategy, and Scanning2 — with auto_bookmark=True.  The only
mock boundary is the RigCtl interface.

Auto-bookmark behavior under test:
  - _autobookmark() — peak detection when two consecutive signal steps occur
  - _hold_bookmark path — bookmark emitted when signal drops after a single hit
  - No signal → no bookmarks
  - Bookmark frequency and modulation match the signal source
"""

import pytest
from unittest.mock import Mock, call

from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.disk_io import LogFile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SGN_LEVEL = -40          # threshold passed to ScanningTask
_THRESHOLD  = _SGN_LEVEL * 10   # -400 — internal units used by signal_check
_SIGNAL     = _THRESHOLD + 200  # -200 — clearly above threshold (signal present)
_NOISE      = _THRESHOLD - 200  # -600 — clearly below threshold (no signal)


def _make_queue() -> Mock:
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _make_config() -> ScanningConfig:
    return ScanningConfig(
        time_wait_for_tune=0.0,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _auto_task(
    range_min: int,
    range_max: int,
    interval: int,
    modulation: str = "FM",
    passes: int = 1,
    inner_band: int = 0,
    inner_interval: int = 0,
) -> ScanningTask:
    return ScanningTask(
        frequency_modulation=modulation,
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        delay=0,
        passes=passes,
        sgn_level=_SGN_LEVEL,
        wait=False,
        record=False,
        auto_bookmark=True,
        log=False,
        bookmarks=[],
        inner_band=inner_band,
        inner_interval=inner_interval,
    )


def _scanner_with_rig(rigctl: Mock) -> object:
    return create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )


# ---------------------------------------------------------------------------
# Test: no signal anywhere — no bookmarks created
# ---------------------------------------------------------------------------

def test_auto_bookmark_no_signal_produces_no_bookmarks():
    """No signal at any step → new_bookmarks_list stays empty."""
    rig = Mock(spec=RigCtl)
    rig.get_level.return_value = _NOISE
    rig.get_mode.return_value = "FM"

    task = _auto_task(range_min=88_000_000, range_max=91_000_000, interval=1_000_000)
    _scanner_with_rig(rig).scan(task)

    assert task.new_bookmarks_list == []
    rig.get_mode.assert_not_called()


# ---------------------------------------------------------------------------
# Test: single isolated signal step — bookmark emitted via hold path
# ---------------------------------------------------------------------------

def test_auto_bookmark_isolated_signal_bookmarked_via_hold_path():
    """Signal at one step then silence → _hold_bookmark fires on the next step
    and emits one bookmark at the signal frequency."""
    # Range: 88 M, 89 M, 90 M  (signal only at 89 M)
    RANGE_MIN  = 88_000_000
    SIGNAL_FREQ = 89_000_000
    RANGE_MAX  = 91_000_000
    INTERVAL   =  1_000_000

    levels = iter([_NOISE, _SIGNAL, _NOISE])  # 88M→noise, 89M→signal, 90M→noise
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = "FM"

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) == 1
    assert task.new_bookmarks_list[0].channel.frequency == SIGNAL_FREQ


def test_auto_bookmark_isolated_signal_bookmark_frequency_matches_signal_step():
    """The bookmark frequency is exactly the step at which the signal occurred."""
    RANGE_MIN   = 144_000_000
    SIGNAL_FREQ = 145_000_000
    RANGE_MAX   = 147_000_000
    INTERVAL    =   1_000_000

    levels = iter([_NOISE, _SIGNAL, _NOISE])
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = "USB"

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, modulation="USB")
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) >= 1
    assert task.new_bookmarks_list[0].channel.frequency == SIGNAL_FREQ


# ---------------------------------------------------------------------------
# Test: two consecutive signal steps — _autobookmark path bookmarks the first
# ---------------------------------------------------------------------------

def test_auto_bookmark_consecutive_signals_bookmarks_first_frequency():
    """Signal at two adjacent steps → autobookmark() stores the first as
    candidate and emits a bookmark for it on the second detection."""
    # Range: 88 M, 89 M, 90 M  (signal at 88 M and 89 M)
    RANGE_MIN = 88_000_000
    FIRST_FREQ = 88_000_000
    RANGE_MAX = 91_000_000
    INTERVAL  =  1_000_000

    levels = iter([_SIGNAL, _SIGNAL, _NOISE])  # 88M→signal, 89M→signal, 90M→noise
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = "FM"

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner_with_rig(rig).scan(task)

    # At least one bookmark must be produced
    assert len(task.new_bookmarks_list) >= 1
    # The first bookmark must be at the first signal frequency
    assert task.new_bookmarks_list[0].channel.frequency == FIRST_FREQ


# ---------------------------------------------------------------------------
# Test: signal only at the final step — hold path never fires, no bookmark
# ---------------------------------------------------------------------------

def test_auto_bookmark_signal_at_last_step_produces_no_bookmark():
    """Signal at the very last step of the range: the hold path can only fire
    on a *subsequent* step, which doesn't exist, so no bookmark is emitted."""
    # Range: 88 M, 89 M  (range_max=90 M is exclusive)
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000
    INTERVAL  =  1_000_000

    levels = iter([_NOISE, _SIGNAL])  # 88M→noise, 89M→signal (last step)
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = "FM"

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner_with_rig(rig).scan(task)

    assert task.new_bookmarks_list == []


# ---------------------------------------------------------------------------
# Test: bookmark modulation comes from get_mode(), not task.frequency_modulation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_mode", ["FM", "AM", "USB", "LSB", "CW"])
def test_auto_bookmark_bookmark_modulation_matches_get_mode(rig_mode):
    """_create_new_bookmark() queries get_mode() for the modulation; the resulting
    bookmark must reflect what the rig reported, regardless of task modulation."""
    RANGE_MIN  = 88_000_000
    RANGE_MAX  = 91_000_000
    INTERVAL   =  1_000_000

    levels = iter([_NOISE, _SIGNAL, _NOISE])
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = rig_mode

    # Task modulation is intentionally different from rig_mode to detect leakage
    task_modulation = "FM" if rig_mode != "FM" else "AM"
    task = _auto_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        modulation=task_modulation,
    )
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) >= 1
    assert task.new_bookmarks_list[0].channel.modulation == rig_mode


# ---------------------------------------------------------------------------
# Test: get_mode() is called exactly once per bookmark created
# ---------------------------------------------------------------------------

def test_auto_bookmark_get_mode_called_once_per_bookmark():
    """get_mode() is queried once per bookmark created, not once per scan step."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000
    INTERVAL  =  1_000_000

    levels = iter([_NOISE, _SIGNAL, _NOISE])  # one bookmark expected
    rig = Mock(spec=RigCtl)
    rig.get_level.side_effect = lambda: next(levels)
    rig.get_mode.return_value = "FM"

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner_with_rig(rig).scan(task)

    bookmark_count = len(task.new_bookmarks_list)
    assert bookmark_count >= 1
    assert rig.get_mode.call_count == bookmark_count

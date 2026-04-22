"""
Functional tests for disk-logging behaviour (task.log=True).

Exercises the full scan pipeline with task.log=True against a real LogFile
Mock so that every log.write() call can be inspected.  The scanner strategies
are real instances; only the RigCtl hardware interface and the LogFile are
mocked.

Behaviours under test:

Frequency scanner (record_type="F"):
  - log.write() called once per signal detection, never when no signal
  - record_type argument is always "F"
  - The Bookmark passed to write() carries the correct signal frequency
  - signal argument is always an empty list
  - log.write() never called when task.log=False, even when signal is present
  - log.open() and log.close() called exactly once when task.log=True

Bookmark scanner (record_type="B"):
  - log.write() called once per non-locked bookmark, unconditionally on signal
  - Locked bookmarks are completely skipped — no log.write()
  - record_type argument is always "B"
  - log.write() never called when task.log=False
"""

import pytest
from unittest.mock import Mock, call

from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.stmessenger import STMessenger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SGN_LEVEL = -40
_THRESHOLD  = _SGN_LEVEL * 10   # -400
_NOISE      = _THRESHOLD - 200  # -600
_SIGNAL     = _THRESHOLD + 200  # -200


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_queue() -> Mock:
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _make_config() -> ScanningConfig:
    return ScanningConfig(time_wait_for_tune=0.0, signal_checks=1, no_signal_delay=0.0)


def _make_log_mock() -> Mock:
    """LogFile mock whose write() / open() / close() calls are recorded."""
    return Mock(spec=LogFile)


def _make_freq_tracking_rig(level_map: dict[int, float], mode: str = "FM") -> Mock:
    """RigCtl mock that returns a per-frequency level keyed on last set_frequency()."""
    rig = Mock(spec=RigCtl)
    current_freq: list[int] = [0]
    rig.set_frequency.side_effect = lambda f: current_freq.__setitem__(0, f)
    rig.get_level.side_effect = lambda: level_map.get(current_freq[0], _NOISE)
    rig.get_mode.return_value = mode
    return rig


def _make_bm_rig() -> Mock:
    """RigCtl mock for bookmark scanning: all calls succeed, no signal."""
    rig = Mock(spec=RigCtl)
    rig.get_level.return_value = _NOISE
    rig.get_mode.return_value = "FM"
    return rig


def _freq_log_task(
    range_min: int,
    range_max: int,
    interval: int,
    log: bool = True,
    modulation: str = "FM",
    passes: int = 1,
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
        auto_bookmark=False,
        log=log,
        bookmarks=[],
    )


def _bm_log_task(bookmarks: list[Bookmark], log: bool = True) -> ScanningTask:
    return ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmarks_list=[],
        range_min=88_000_000,
        range_max=108_000_000,
        interval=1_000_000,
        delay=0,
        passes=1,
        sgn_level=_SGN_LEVEL,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=log,
        bookmarks=bookmarks,
    )


def _make_bookmarks(
    freqs_modes: list[tuple[int, str]],
    locked: list[bool] | None = None,
) -> list[Bookmark]:
    if locked is None:
        locked = [False] * len(freqs_modes)
    return [
        bookmark_factory(
            input_frequency=f,
            modulation=m,
            description=f"test bm {f}",
            lockout="L" if lk else "",
        )
        for (f, m), lk in zip(freqs_modes, locked)
    ]


def _scanner(scan_mode: str, rig: Mock, log_mock: Mock):
    return create_scanner(
        scan_mode=scan_mode,
        scan_queue=_make_queue(),
        log_filename="/tmp/test_scan.log",
        rigctl=rig,
        config=_make_config(),
        log=log_mock,
        sleep_fn=lambda _: None,
    )


# ===========================================================================
# Frequency scanner — log.write behaviour
# ===========================================================================

def test_freq_scan_log_write_called_once_per_signal_detection():
    """One signal detection → log.write() called exactly once."""
    level_map = {88_000_000: _NOISE, 89_000_000: _SIGNAL, 90_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=91_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    assert log.write.call_count == 1, (
        f"Expected 1 write call for 1 signal detection, got {log.write.call_count}"
    )


@pytest.mark.parametrize("signal_count", [1, 2, 3])
def test_freq_scan_log_write_count_matches_signal_detections(signal_count):
    """log.write() call count equals the number of steps where signal is detected."""
    # Range: 88M to (88M + signal_count+1 MHz) in 1 MHz steps
    # Signal at 89M, 90M, 91M … up to signal_count steps
    base = 88_000_000
    interval = 1_000_000
    range_max = base + (signal_count + 2) * interval  # extra quiet step at end

    signal_freqs = {base + i * interval for i in range(1, signal_count + 1)}
    level_map = {f: (_SIGNAL if f in signal_freqs else _NOISE)
                 for f in range(base, range_max, interval)}

    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=base, range_max=range_max, interval=interval)
    _scanner("frequency", rig, log).scan(task)

    assert log.write.call_count == signal_count, (
        f"Expected {signal_count} write calls, got {log.write.call_count}"
    )


def test_freq_scan_log_write_record_type_is_F():
    """Every log.write() call for the frequency scanner uses record_type='F'."""
    level_map = {88_000_000: _NOISE, 89_000_000: _SIGNAL, 90_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=91_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    for c in log.write.call_args_list:
        assert c.kwargs.get("record_type") == "F" or c.args[0] == "F", (
            f"Expected record_type='F', got call: {c}"
        )


def test_freq_scan_log_write_signal_arg_is_empty_list():
    """The signal keyword argument is always an empty list."""
    level_map = {88_000_000: _SIGNAL, 89_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=90_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    assert log.write.call_count == 1
    c = log.write.call_args
    signal_arg = c.kwargs.get("signal") if c.kwargs.get("signal") is not None else c.args[2]
    assert signal_arg == [], f"Expected signal=[], got {signal_arg!r}"


def test_freq_scan_log_write_bookmark_frequency_matches_detection():
    """The Bookmark record passed to log.write() carries the signal frequency."""
    SIGNAL_FREQ = 89_000_000
    level_map = {88_000_000: _NOISE, SIGNAL_FREQ: _SIGNAL, 90_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=91_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    assert log.write.call_count == 1
    c = log.write.call_args
    record = c.kwargs.get("record") if "record" in (c.kwargs or {}) else c.args[1]
    assert record.channel.frequency == SIGNAL_FREQ, (
        f"Expected bookmark frequency {SIGNAL_FREQ}, got {record.channel.frequency}"
    )


def test_freq_scan_log_not_called_when_no_signal():
    """No signal detected → log.write() is never called."""
    rig = _make_freq_tracking_rig({88_000_000: _NOISE, 89_000_000: _NOISE})
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=90_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    log.write.assert_not_called()


def test_freq_scan_log_not_called_when_log_flag_false():
    """task.log=False → log.write() never called even when signal is present."""
    level_map = {88_000_000: _SIGNAL, 89_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(
        range_min=88_000_000, range_max=90_000_000, interval=1_000_000, log=False
    )
    _scanner("frequency", rig, log).scan(task)

    log.write.assert_not_called()


def test_freq_scan_log_open_and_close_called_when_log_true():
    """When task.log=True, log.open() is called before the scan and
    log.close() is called after."""
    level_map = {88_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(range_min=88_000_000, range_max=89_000_000, interval=1_000_000)
    _scanner("frequency", rig, log).scan(task)

    log.open.assert_called_once()
    log.close.assert_called_once()


def test_freq_scan_log_open_not_called_when_log_false():
    """When task.log=False, log.open() and log.close() are never called."""
    level_map = {88_000_000: _NOISE}
    rig = _make_freq_tracking_rig(level_map)
    log = _make_log_mock()

    task = _freq_log_task(
        range_min=88_000_000, range_max=89_000_000, interval=1_000_000, log=False
    )
    _scanner("frequency", rig, log).scan(task)

    log.open.assert_not_called()
    log.close.assert_not_called()


# ===========================================================================
# Bookmark scanner — log.write behaviour
# ===========================================================================

def test_bm_scan_log_write_called_for_each_non_locked_bookmark():
    """log.write() is called once per non-locked bookmark, regardless of signal."""
    bookmarks = _make_bookmarks(
        [(88_000_000, "FM"), (90_000_000, "AM"), (92_000_000, "USB")],
        locked=[False, True, False],  # 2 unlocked, 1 locked
    )
    rig = _make_bm_rig()
    log = _make_log_mock()

    task = _bm_log_task(bookmarks)
    _scanner("bookmarks", rig, log).scan(task)

    assert log.write.call_count == 2, (
        f"Expected 2 write calls (2 non-locked bookmarks), got {log.write.call_count}"
    )


def test_bm_scan_log_write_record_type_is_B():
    """Every log.write() call for the bookmark scanner uses record_type='B'."""
    bookmarks = _make_bookmarks([(88_000_000, "FM"), (90_000_000, "AM")])
    rig = _make_bm_rig()
    log = _make_log_mock()

    task = _bm_log_task(bookmarks)
    _scanner("bookmarks", rig, log).scan(task)

    for c in log.write.call_args_list:
        record_type = c.kwargs.get("record_type") if c.kwargs.get("record_type") else c.args[0]
        assert record_type == "B", f"Expected record_type='B', got {record_type!r}"


def test_bm_scan_log_write_called_regardless_of_signal():
    """Bookmark scanner logs every non-locked bookmark unconditionally — even
    when no signal is detected at any bookmark frequency."""
    bookmarks = _make_bookmarks([(88_000_000, "FM"), (90_000_000, "AM")])
    rig = _make_bm_rig()
    rig.get_level.return_value = _NOISE  # no signal anywhere
    log = _make_log_mock()

    task = _bm_log_task(bookmarks)
    _scanner("bookmarks", rig, log).scan(task)

    # Both bookmarks should be logged even though no signal was detected
    assert log.write.call_count == 2, (
        f"Expected 2 write calls even with no signal, got {log.write.call_count}"
    )


def test_bm_scan_log_locked_bookmark_not_written():
    """Locked bookmarks are skipped entirely — log.write() is not called for them."""
    bookmarks = _make_bookmarks(
        [(88_000_000, "FM"), (90_000_000, "AM")],
        locked=[True, False],  # first locked, second active
    )
    rig = _make_bm_rig()
    log = _make_log_mock()

    task = _bm_log_task(bookmarks)
    _scanner("bookmarks", rig, log).scan(task)

    assert log.write.call_count == 1, (
        f"Expected 1 write call (1 non-locked bookmark), got {log.write.call_count}"
    )
    # The written record should be for the non-locked bookmark (90 MHz)
    c = log.write.call_args
    record = c.kwargs.get("record") if "record" in (c.kwargs or {}) else c.args[1]
    assert record.channel.frequency == 90_000_000


def test_bm_scan_log_not_called_when_log_flag_false():
    """task.log=False → log.write() never called for any bookmark."""
    bookmarks = _make_bookmarks([(88_000_000, "FM"), (90_000_000, "AM")])
    rig = _make_bm_rig()
    log = _make_log_mock()

    task = _bm_log_task(bookmarks, log=False)
    _scanner("bookmarks", rig, log).scan(task)

    log.write.assert_not_called()


def test_bm_scan_log_open_and_close_called_when_log_true():
    """When task.log=True, log.open() is called before the scan and
    log.close() is called after."""
    bookmarks = _make_bookmarks([(88_000_000, "FM")])
    rig = _make_bm_rig()
    log = _make_log_mock()

    task = _bm_log_task(bookmarks)
    _scanner("bookmarks", rig, log).scan(task)

    log.open.assert_called_once()
    log.close.assert_called_once()

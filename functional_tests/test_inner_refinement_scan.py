"""
Functional tests for the inner refinement scan in FrequencyScannerStrategy.

The inner scan is triggered when a signal is detected during a frequency sweep
and both task.inner_band > 0 and task.inner_interval > 0.  It sweeps
[freq_start, freq_start + inner_band) at inner_interval steps and bookmarks
the frequency with the highest measured signal level.

The full pipeline — ScanningConfig, ScannerCore, FrequencyScannerStrategy,
Scanning2 — is wired together via create_scanner().  The only mock boundary
is the RigCtl interface.

Behaviors under test:
  - Bookmark placed at sub-band peak, not at outer trigger frequency
  - All inner steps fall within the exclusive inner band
  - Single step emitted when inner_band == inner_interval
  - Fallback to trigger frequency when all inner tune steps raise OSError
  - Inner scan not activated when inner_band / inner_interval are zero
  - Multiple outer triggers each run an independent inner scan
"""

import pytest
from unittest.mock import Mock

from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.disk_io import LogFile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SGN_LEVEL = -40
_THRESHOLD  = _SGN_LEVEL * 10   # -400 — signal_check comparison threshold
_NOISE      = _THRESHOLD - 200  # -600 — clearly no signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_frequency_tracking_rig(
    level_map: dict[int, float],
    mode: str = "FM",
) -> Mock:
    """RigCtl mock whose get_level() returns a value keyed on the last
    set_frequency() argument, allowing per-frequency signal simulation."""
    rig = Mock(spec=RigCtl)
    current_freq: list[int] = [0]
    rig.set_frequency.side_effect = lambda f: current_freq.__setitem__(0, f)
    rig.get_level.side_effect = lambda: level_map.get(current_freq[0], _NOISE)
    rig.get_mode.return_value = mode
    return rig


def _inner_task(
    range_min: int,
    range_max: int,
    interval: int,
    inner_band: int,
    inner_interval: int,
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
        auto_bookmark=True,
        log=False,
        bookmarks=[],
        inner_band=inner_band,
        inner_interval=inner_interval,
    )


def _scanner_with_rig(rigctl: Mock):
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
# Test: bookmark is placed at the sub-band peak, not at the outer trigger
# ---------------------------------------------------------------------------

def test_inner_scan_bookmarks_peak_sub_frequency_not_trigger_frequency():
    """Outer scan detects signal at 88 MHz; inner sweep [88M, 88.5M) at 250 kHz
    steps finds a stronger signal at 88.25 MHz — bookmark must land there."""
    TRIGGER_FREQ  = 88_000_000
    PEAK_FREQ     = 88_250_000
    INNER_BAND    =    500_000
    INNER_INTERVAL =   250_000

    level_map = {
        TRIGGER_FREQ:  _THRESHOLD + 100,  # outer signal check passes; lower inner level
        PEAK_FREQ:     _THRESHOLD + 200,  # highest inner level → peak
        89_000_000:    _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map)

    task = _inner_task(
        range_min=88_000_000,
        range_max=90_000_000,
        interval=1_000_000,
        inner_band=INNER_BAND,
        inner_interval=INNER_INTERVAL,
    )
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) == 1
    assert task.new_bookmarks_list[0].channel.frequency == PEAK_FREQ, (
        f"Expected bookmark at sub-band peak {PEAK_FREQ} Hz, "
        f"got {task.new_bookmarks_list[0].channel.frequency} Hz"
    )


# ---------------------------------------------------------------------------
# Test: inner steps stay within [freq_start, freq_start + inner_band)
# ---------------------------------------------------------------------------

def test_inner_scan_all_steps_within_exclusive_inner_band():
    """set_frequency is called for each inner step but never at or beyond
    freq_start + inner_band (the exclusive upper bound)."""
    TRIGGER_FREQ   = 100_000_000
    INNER_BAND     =     500_000   # [100M, 100.5M)
    INNER_INTERVAL =     250_000   # steps: 100M, 100.25M

    level_map = {
        TRIGGER_FREQ:    _THRESHOLD + 100,
        100_250_000:     _THRESHOLD + 50,
        101_000_000:     _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map)

    task = _inner_task(
        range_min=100_000_000,
        range_max=102_000_000,
        interval=1_000_000,
        inner_band=INNER_BAND,
        inner_interval=INNER_INTERVAL,
    )
    _scanner_with_rig(rig).scan(task)

    inner_upper_bound = TRIGGER_FREQ + INNER_BAND  # 100.5 MHz
    tuned_freqs = [c.args[0] for c in rig.set_frequency.call_args_list]
    inner_freqs = [
        f for f in tuned_freqs
        if TRIGGER_FREQ <= f < TRIGGER_FREQ + INNER_BAND
    ]

    assert inner_freqs, "No inner-scan frequencies were tuned"
    assert all(f < inner_upper_bound for f in inner_freqs), (
        f"Inner step(s) {[f for f in inner_freqs if f >= inner_upper_bound]} "
        f"exceed exclusive upper bound {inner_upper_bound}"
    )
    assert inner_upper_bound not in tuned_freqs, (
        f"Upper bound {inner_upper_bound} was tuned — inner loop is not exclusive"
    )


# ---------------------------------------------------------------------------
# Test: exactly one inner step when inner_band == inner_interval
# ---------------------------------------------------------------------------

def test_inner_scan_single_step_when_inner_band_equals_inner_interval():
    """When inner_band == inner_interval only freq_start itself is sampled
    (the next step would equal inner_end, which is exclusive)."""
    TRIGGER_FREQ    = 145_000_000
    INNER_BAND      =     250_000
    INNER_INTERVAL  =     250_000   # equal → exactly one step

    level_map = {
        TRIGGER_FREQ: _THRESHOLD + 100,
        146_000_000:  _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map)

    task = _inner_task(
        range_min=145_000_000,
        range_max=147_000_000,
        interval=1_000_000,
        inner_band=INNER_BAND,
        inner_interval=INNER_INTERVAL,
    )
    _scanner_with_rig(rig).scan(task)

    tuned = [c.args[0] for c in rig.set_frequency.call_args_list]

    # The only sub-band step is TRIGGER_FREQ itself; the first sub-step beyond
    # it (TRIGGER_FREQ + INNER_INTERVAL) must never be tuned.
    next_inner_step = TRIGGER_FREQ + INNER_INTERVAL
    assert next_inner_step not in tuned, (
        f"Step {next_inner_step} Hz was tuned — expected inner loop to stop "
        f"after a single sample when inner_band == inner_interval"
    )
    assert len(task.new_bookmarks_list) == 1
    assert task.new_bookmarks_list[0].channel.frequency == TRIGGER_FREQ


# ---------------------------------------------------------------------------
# Test: all inner tune errors → bookmark falls back to trigger frequency
# ---------------------------------------------------------------------------

def test_inner_scan_all_tune_errors_bookmark_falls_back_to_trigger_frequency():
    """When every channel_tune inside the inner scan raises OSError the method
    returns (freq_start, -inf) and the bookmark is placed at the outer trigger
    frequency.  The scan also exits early because channel_tune sets
    _scan_active=False before re-raising."""
    TRIGGER_FREQ   = 88_000_000
    INNER_BAND     =    500_000
    INNER_INTERVAL =    250_000

    # Outer set_frequency(88M) succeeds (call index 0).
    # Inner set_frequency calls (indices 1, 2) raise OSError.
    call_idx: list[int] = [0]

    def set_frequency_side_effect(freq: int) -> None:
        idx = call_idx[0]
        call_idx[0] += 1
        if idx > 0:  # indices 1+ are inner scan calls
            raise OSError("simulated inner tune error")

    rig = Mock(spec=RigCtl)
    rig.set_frequency.side_effect = set_frequency_side_effect
    rig.get_level.return_value = _THRESHOLD + 100  # outer signal check must pass
    rig.get_mode.return_value = "FM"

    task = _inner_task(
        range_min=88_000_000,
        range_max=90_000_000,
        interval=1_000_000,
        inner_band=INNER_BAND,
        inner_interval=INNER_INTERVAL,
    )
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) == 1, (
        f"Expected 1 fallback bookmark, got {len(task.new_bookmarks_list)}"
    )
    assert task.new_bookmarks_list[0].channel.frequency == TRIGGER_FREQ, (
        f"Expected fallback bookmark at trigger {TRIGGER_FREQ} Hz, "
        f"got {task.new_bookmarks_list[0].channel.frequency} Hz"
    )


# ---------------------------------------------------------------------------
# Test: inner scan disabled when inner_band=0 → _autobookmark path used
# ---------------------------------------------------------------------------

def test_inner_scan_not_activated_when_inner_band_and_interval_are_zero():
    """With inner_band=0 and inner_interval=0 the strategy falls back to
    _autobookmark(); no sub-band tuning should occur between outer steps."""
    TRIGGER_FREQ = 89_000_000

    level_map = {
        88_000_000: _NOISE,
        TRIGGER_FREQ: _THRESHOLD + 100,   # signal at 89 MHz
        90_000_000: _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map)

    task = _inner_task(
        range_min=88_000_000,
        range_max=91_000_000,
        interval=1_000_000,
        inner_band=0,
        inner_interval=0,
    )
    _scanner_with_rig(rig).scan(task)

    tuned_freqs = [c.args[0] for c in rig.set_frequency.call_args_list]
    # Outer steps are exactly the 1 MHz grid; no sub-MHz frequencies should appear
    non_grid_freqs = [f for f in tuned_freqs if f % 1_000_000 != 0]
    assert non_grid_freqs == [], (
        f"Sub-MHz frequencies tuned despite inner_band=0: {non_grid_freqs}"
    )


# ---------------------------------------------------------------------------
# Test: two outer triggers produce two independent inner scans
# ---------------------------------------------------------------------------

def test_inner_scan_two_triggers_produce_two_independent_bookmarks():
    """Two signal detections in the outer sweep each launch their own inner
    scan; two bookmarks are emitted with the sub-band peak of each."""
    TRIGGER_1   = 88_000_000
    PEAK_1      = 88_250_000   # peak within [88M, 88.5M)
    TRIGGER_2   = 90_000_000
    PEAK_2      = 90_250_000   # peak within [90M, 90.5M)
    INNER_BAND  =    500_000
    INNER_INTV  =    250_000

    level_map = {
        TRIGGER_1: _THRESHOLD + 50,
        PEAK_1:    _THRESHOLD + 150,  # best in first inner band
        TRIGGER_2: _THRESHOLD + 50,
        PEAK_2:    _THRESHOLD + 150,  # best in second inner band
        89_000_000: _NOISE,
        91_000_000: _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map)

    task = _inner_task(
        range_min=88_000_000,
        range_max=92_000_000,
        interval=1_000_000,
        inner_band=INNER_BAND,
        inner_interval=INNER_INTV,
    )
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) == 2, (
        f"Expected 2 bookmarks (one per trigger), got {len(task.new_bookmarks_list)}"
    )
    bookmark_freqs = {bm.channel.frequency for bm in task.new_bookmarks_list}
    assert PEAK_1 in bookmark_freqs, f"Missing bookmark at first peak {PEAK_1}"
    assert PEAK_2 in bookmark_freqs, f"Missing bookmark at second peak {PEAK_2}"


# ---------------------------------------------------------------------------
# Test: bookmark modulation comes from get_mode(), not task modulation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_mode", ["FM", "AM", "USB", "LSB", "CW"])
def test_inner_scan_bookmark_modulation_comes_from_get_mode(rig_mode):
    """The bookmark created by the inner scan queries get_mode() for
    modulation; task.frequency_modulation does not bleed into the bookmark."""
    TRIGGER_FREQ = 88_000_000
    PEAK_FREQ    = 88_250_000

    level_map = {
        TRIGGER_FREQ: _THRESHOLD + 50,
        PEAK_FREQ:    _THRESHOLD + 150,
        89_000_000:   _NOISE,
    }
    rig = _make_frequency_tracking_rig(level_map, mode=rig_mode)

    task_modulation = "FM" if rig_mode != "FM" else "AM"
    task = _inner_task(
        range_min=88_000_000,
        range_max=90_000_000,
        interval=1_000_000,
        inner_band=500_000,
        inner_interval=250_000,
        modulation=task_modulation,
    )
    _scanner_with_rig(rig).scan(task)

    assert len(task.new_bookmarks_list) == 1
    assert task.new_bookmarks_list[0].channel.modulation == rig_mode, (
        f"Expected modulation {rig_mode!r} from get_mode(), "
        f"got {task.new_bookmarks_list[0].channel.modulation!r}"
    )

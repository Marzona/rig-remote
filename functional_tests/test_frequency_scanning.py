"""
Functional tests for the scanning composition.

These tests exercise the full scan pipeline end-to-end — ScanningConfig,
ScannerCore, FrequencyScannerStrategy, and Scanning2 — wired together via
create_scanner().  The only mock boundary is the RigCtl interface (radio
hardware) and the STMessenger queue (UI thread), so every internal object is
real.

Assertions target the rigctl call log so that:
  - every frequency step in the range is tuned exactly once per pass
  - the correct modulation mode is sent for every tune
"""

import pytest
from unittest.mock import Mock

from rig_remote.scanning import (
    ScanningConfig,
    create_scanner,
)
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.disk_io import LogFile


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl(level: float = -600.0, mode: str = "FM") -> Mock:
    """RigCtl mock: signal always absent (level below any threshold) by default."""
    rig = Mock(spec=RigCtl)
    rig.get_level.return_value = level
    rig.get_mode.return_value = mode
    return rig


def _make_queue() -> Mock:
    """STMessenger mock: queue is always empty (no UI events during scan)."""
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _make_config() -> ScanningConfig:
    """Fast ScanningConfig suitable for tests (no wall-time sleeps)."""
    return ScanningConfig(
        time_wait_for_tune=0.0,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _freq_task(
    range_min: int,
    range_max: int,
    interval: int,
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
        sgn_level=-40,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[],
    )


# ---------------------------------------------------------------------------
# Functional test: single pass, FM broadcast band
# ---------------------------------------------------------------------------

def test_scanning_frequency_all_steps_tuned_fm_broadcast():
    """Full frequency scan over the FM broadcast band (88–108 MHz, 1 MHz step).

    Verifies that set_frequency is called once per step and set_mode is called
    with "FM" for every step.
    """
    RANGE_MIN = 88_000_000   # 88 MHz
    RANGE_MAX = 108_000_000  # 108 MHz  (exclusive: while freq < range_max)
    INTERVAL  =  1_000_000   # 1 MHz steps

    expected_frequencies = list(range(RANGE_MIN, RANGE_MAX, INTERVAL))  # 20 steps

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    # --- frequency assertions ---
    actual_freq_calls = [c.args[0] for c in rigctl.set_frequency.call_args_list]
    assert actual_freq_calls == expected_frequencies, (
        f"Expected {len(expected_frequencies)} frequency calls, "
        f"got {len(actual_freq_calls)}: {actual_freq_calls}"
    )

    # --- modulation assertions ---
    assert rigctl.set_mode.call_count == len(expected_frequencies)
    for c in rigctl.set_mode.call_args_list:
        assert c.args[0] == "FM", f"Unexpected modulation: {c.args[0]}"


# ---------------------------------------------------------------------------
# Functional test: multiple passes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("passes", [1, 2, 3])
def test_scanning_frequency_multiple_passes_multiplies_tune_calls(passes):
    """Each additional pass repeats the full frequency sweep.

    set_frequency call count == steps_per_pass × passes.
    """
    RANGE_MIN = 100_000_000
    RANGE_MAX = 100_500_000
    INTERVAL  =  100_000       # 5 steps per pass: 100M, 100.1M, …, 100.4M

    steps_per_pass = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))  # 5

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    scanner.scan(_freq_task(
        range_min=RANGE_MIN,
        range_max=RANGE_MAX,
        interval=INTERVAL,
        passes=passes,
    ))

    assert rigctl.set_frequency.call_count == steps_per_pass * passes
    assert rigctl.set_mode.call_count == steps_per_pass * passes


# ---------------------------------------------------------------------------
# Functional test: modulation is applied uniformly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("modulation", ["FM", "AM", "USB", "LSB", "CW"])
def test_scanning_frequency_correct_modulation_sent_for_each_step(modulation):
    """set_mode is called with the task's modulation for every frequency step."""
    RANGE_MIN = 145_000_000
    RANGE_MAX = 145_500_000
    INTERVAL  =  100_000       # 5 steps

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl = _make_rigctl(mode=modulation)
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    scanner.scan(_freq_task(
        range_min=RANGE_MIN,
        range_max=RANGE_MAX,
        interval=INTERVAL,
        modulation=modulation,
    ))

    assert rigctl.set_mode.call_count == expected_steps
    for c in rigctl.set_mode.call_args_list:
        assert c.args[0] == modulation


# ---------------------------------------------------------------------------
# Functional test: frequency order
# ---------------------------------------------------------------------------

def test_scanning_frequency_steps_tuned_in_ascending_order():
    """Frequencies are tuned in strict ascending order from range_min upward."""
    RANGE_MIN = 144_000_000
    RANGE_MAX = 146_000_000
    INTERVAL  =  500_000       # 4 steps: 144M, 144.5M, 145M, 145.5M

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    actual = [c.args[0] for c in rigctl.set_frequency.call_args_list]
    assert actual == sorted(actual), "Frequencies not tuned in ascending order"
    assert actual[0] == RANGE_MIN
    assert actual[-1] == RANGE_MAX - INTERVAL


# ---------------------------------------------------------------------------
# Negative tests: invalid and boundary parameters
# ---------------------------------------------------------------------------

def test_scanning_frequency_range_min_equals_range_max_raises_value_error():
    """ScanningTask raises ValueError when range_min equals range_max."""
    with pytest.raises(ValueError):
        _freq_task(range_min=88_000_000, range_max=88_000_000, interval=1_000_000)


def test_scanning_frequency_range_min_greater_than_range_max_raises_value_error():
    """ScanningTask raises ValueError when range_min exceeds range_max."""
    with pytest.raises(ValueError):
        _freq_task(range_min=108_000_000, range_max=88_000_000, interval=1_000_000)


def test_scanning_frequency_invalid_scan_mode_raises_value_error():
    """ScanningTask raises ValueError for an unrecognised scan_mode."""
    with pytest.raises(ValueError):
        ScanningTask(
            frequency_modulation="FM",
            scan_mode="invalid",
            new_bookmarks_list=[],
            range_min=88_000_000,
            range_max=108_000_000,
            interval=1_000_000,
            delay=0,
            passes=1,
            sgn_level=-40,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=False,
            bookmarks=[],
        )


@pytest.mark.parametrize("passes", [-3, -1, 0])
def test_scanning_frequency_negative_passes_clamped_to_one(passes):
    """passes < 1 is silently clamped to 1; the scan executes exactly once."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000
    INTERVAL  =  1_000_000  # 2 steps: 88 MHz, 89 MHz

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=passes)
    assert task.passes == 1, f"Expected clamped passes=1, got {task.passes}"

    scanner.scan(task)

    assert rigctl.set_frequency.call_count == expected_steps, (
        f"Expected {expected_steps} tune calls, got {rigctl.set_frequency.call_count}"
    )


def test_scanning_frequency_interval_below_minimum_clamped_to_1000hz():
    """interval < 1000 Hz is clamped to 1000 Hz; steps are spaced 1 kHz apart."""
    RANGE_MIN        = 88_000_000
    RANGE_MAX        = 88_010_000
    INTERVAL_RAW     = 100        # below the 1 kHz floor
    INTERVAL_CLAMPED = 1_000

    expected_frequencies = list(range(RANGE_MIN, RANGE_MAX, INTERVAL_CLAMPED))  # 10 steps

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL_RAW)
    assert task.interval == INTERVAL_CLAMPED, (
        f"Expected clamped interval={INTERVAL_CLAMPED}, got {task.interval}"
    )

    scanner.scan(task)

    actual = [c.args[0] for c in rigctl.set_frequency.call_args_list]
    assert actual == expected_frequencies, (
        f"Expected frequencies at 1 kHz spacing, got {actual}"
    )


def test_scanning_frequency_zero_signal_checks_all_steps_tuned():
    """signal_checks=0 disables level sampling; every step is still tuned."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000
    INTERVAL  =  1_000_000  # 3 steps

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    config = ScanningConfig(
        time_wait_for_tune=0.0,
        signal_checks=0,
        no_signal_delay=0.0,
    )

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=config,
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    assert rigctl.set_frequency.call_count == expected_steps, (
        f"Expected {expected_steps} tune calls with signal_checks=0, "
        f"got {rigctl.set_frequency.call_count}"
    )


def test_scanning_frequency_negative_range_min_clamped_to_zero_aborts_scan():
    """range_min < 0 is clamped to 0; tuning 0 Hz is invalid so the pass aborts
    immediately with no frequency calls."""
    RANGE_MIN_RAW = -1_000_000
    RANGE_MAX     = 91_000_000
    INTERVAL      = 30_000_000

    rigctl = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )

    task = _freq_task(range_min=RANGE_MIN_RAW, range_max=RANGE_MAX, interval=INTERVAL)
    assert task.range_min == 0, f"Expected clamped range_min=0, got {task.range_min}"

    scanner.scan(task)

    # Channel rejects frequency=0 (must be >= 1 Hz), so the pass aborts before
    # any set_frequency call is issued.
    assert rigctl.set_frequency.call_count == 0, (
        f"Expected 0 tune calls (0 Hz is invalid), got {rigctl.set_frequency.call_count}"
    )

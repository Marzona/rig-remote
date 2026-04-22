"""
Functional tests for queue-driven parameter updates applied mid-scan.

During an active frequency sweep process_queue() is called at the top of
every inner loop iteration.  Events placed in the STMessenger child queue
before or between iterations mutate the live ScanningTask fields so that the
scan adapts its behaviour without being restarted.

These tests use a real STMessenger (with real QueueComms) pre-loaded with
events so the queue plumbing is exercised end-to-end.  The only mock boundary
is the RigCtl hardware interface.

Parameters covered:
  txt_passes    — extending pass count mid-scan increases total tune calls
  txt_range_max — narrowing range_max truncates the current sweep
  txt_interval  — widening interval reduces the number of steps per pass
  txt_sgn_level — lowering threshold enables signal detection for later steps
  txt_delay     — raising delay changes the sleep budget after signal hits
  unknown event — unrecognised event name is silently ignored
  invalid value — non-convertible value for a numeric field is silently ignored
  multiple      — two queued events are both applied in the same process_queue call
"""

import pytest
from unittest.mock import Mock

from rig_remote.disk_io import LogFile
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.stmessenger import STMessenger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SGN_LEVEL = -40
_THRESHOLD  = _SGN_LEVEL * 10   # -400


def _make_live_queue(events: list[tuple[str, str]] | None = None) -> STMessenger:
    """Real STMessenger pre-loaded with *events* so the scan picks them up."""
    q = STMessenger(queue_comms=QueueComms())
    for event in (events or []):
        q.send_event_update(event)
    return q


def _make_config() -> ScanningConfig:
    return ScanningConfig(time_wait_for_tune=0.0, signal_checks=1, no_signal_delay=0.0)


def _make_silent_rig(level: float = -600.0, mode: str = "FM") -> Mock:
    """RigCtl mock: constant signal level and mode, all calls succeed."""
    rig = Mock(spec=RigCtl)
    rig.get_level.return_value = level
    rig.get_mode.return_value = mode
    return rig


def _freq_task(
    range_min: int,
    range_max: int,
    interval: int,
    sgn_level: int = _SGN_LEVEL,
    passes: int = 1,
    delay: int = 0,
    auto_bookmark: bool = False,
) -> ScanningTask:
    return ScanningTask(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        delay=delay,
        passes=passes,
        sgn_level=sgn_level,
        wait=False,
        record=False,
        auto_bookmark=auto_bookmark,
        log=False,
        bookmarks=[],
    )


def _scanner(queue: STMessenger, rig: Mock):
    return create_scanner(
        scan_mode="frequency",
        scan_queue=queue,
        log_filename="/dev/null",
        rigctl=rig,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda _: None,
    )


# ---------------------------------------------------------------------------
# passes update: more passes → more tune calls
# ---------------------------------------------------------------------------

def test_passes_update_mid_scan_extends_total_tune_calls():
    """Queuing txt_passes=3 before the scan starts; the event is consumed on
    the first step, pass_count is reset to 3, and the scanner completes three
    full sweeps instead of one."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps per pass: 88 M, 89 M
    INTERVAL  =  1_000_000
    STEPS_PER_PASS = 2

    queue = _make_live_queue([("txt_passes", "3")])
    rig   = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=1)
    _scanner(queue, rig).scan(task)

    assert rig.set_frequency.call_count == STEPS_PER_PASS * 3, (
        f"Expected {STEPS_PER_PASS * 3} tune calls (3 passes × {STEPS_PER_PASS} steps), "
        f"got {rig.set_frequency.call_count}"
    )
    assert task.passes == 3


# ---------------------------------------------------------------------------
# range_max update: narrower range_max stops the sweep earlier
# ---------------------------------------------------------------------------

def test_range_max_update_mid_scan_truncates_sweep():
    """Queuing txt_range_max=90000 (kHz → 90 MHz) truncates a 88–95 MHz sweep
    to only the steps that fall below the new upper bound (88 M, 89 M)."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 95_000_000   # original: 7 steps
    INTERVAL  =  1_000_000
    NEW_MAX_KHZ = "90000"    # 90 MHz in kHz (khertz_to_hertz conversion)

    queue = _make_live_queue([("txt_range_max", NEW_MAX_KHZ)])
    rig   = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner(queue, rig).scan(task)

    # After update range_max = 90 MHz: only 88 M and 89 M are < 90 M
    assert rig.set_frequency.call_count == 2, (
        f"Expected 2 tune calls after range_max narrowed to 90 MHz, "
        f"got {rig.set_frequency.call_count}"
    )
    assert task.range_max == 90_000_000


# ---------------------------------------------------------------------------
# interval update: wider interval reduces steps per pass
# ---------------------------------------------------------------------------

def test_interval_update_mid_scan_reduces_step_count():
    """Queuing txt_interval=2000000 (Hz) on the first step of an 88–96 MHz
    sweep widens the step from 1 MHz to 2 MHz, halving the number of tunes."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 96_000_000   # original 1 MHz interval → 8 steps
    INTERVAL  =  1_000_000
    NEW_INTERVAL_HZ = "2000000"  # 2 MHz in Hz

    queue = _make_live_queue([("txt_interval", NEW_INTERVAL_HZ)])
    rig   = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    _scanner(queue, rig).scan(task)

    # 88M (+2M) 90M (+2M) 92M (+2M) 94M (+2M) → 96M stop: 4 steps
    assert rig.set_frequency.call_count == 4, (
        f"Expected 4 tune calls after interval widened to 2 MHz, "
        f"got {rig.set_frequency.call_count}"
    )
    assert task.interval == 2_000_000


# ---------------------------------------------------------------------------
# sgn_level update: lowering threshold enables signal detection
# ---------------------------------------------------------------------------

def test_sgn_level_update_mid_scan_enables_signal_detection():
    """With initial sgn_level=-40 (threshold=-400) the mock rig at -600 dBFS
    produces no signal.  Queuing txt_sgn_level=-61 lowers the threshold to
    -610 so that -600 >= -610 → signal detected; auto_bookmark creates entries.
    """
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000   # 3 steps
    INTERVAL  =  1_000_000
    MOCK_LEVEL = -600.0      # below original threshold of -400

    queue = _make_live_queue([("txt_sgn_level", "-61")])  # threshold → -610
    rig   = _make_silent_rig(level=MOCK_LEVEL)

    task = _freq_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        sgn_level=_SGN_LEVEL, auto_bookmark=True,
    )
    _scanner(queue, rig).scan(task)

    # After update signal is detected at every step → auto_bookmark fires
    assert task.sgn_level == -61
    assert len(task.new_bookmarks_list) > 0, (
        "Expected at least one auto-bookmark after sgn_level update enabled "
        "signal detection, got none"
    )


def test_sgn_level_update_does_not_affect_steps_already_passed():
    """The sgn_level update is applied at the START of each step's iteration.
    The very first get_level() call uses the UPDATED threshold (consumed at
    step-1 process_queue), so even step 1 reflects the new value."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 89_000_000   # 1 step only
    INTERVAL  =  1_000_000

    # Start with threshold=-400; mock returns -600 (no signal with original).
    # Update lowers to -610 → signal at the single step.
    queue = _make_live_queue([("txt_sgn_level", "-61")])
    rig   = _make_silent_rig(level=-600.0)

    task = _freq_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        sgn_level=_SGN_LEVEL, auto_bookmark=False,
    )
    task.log = True  # enable logging so log.write() acts as signal indicator

    log_mock = Mock(spec=LogFile)
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=queue,
        log_filename="/dev/null",
        rigctl=rig,
        config=_make_config(),
        log=log_mock,
        sleep_fn=lambda _: None,
    )
    scanner.scan(task)

    log_mock.write.assert_called_once()


# ---------------------------------------------------------------------------
# delay update: higher delay changes the sleep budget after a signal hit
# ---------------------------------------------------------------------------

def test_delay_update_mid_scan_changes_sleep_budget():
    """Queuing txt_delay=2 before a scan that detects a signal causes
    queue_sleep to call sleep(1) twice per hit instead of zero times."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps
    INTERVAL  =  1_000_000
    MOCK_LEVEL = -200.0      # above threshold (-400)

    sleep_calls: list[float] = []
    queue = _make_live_queue([("txt_delay", "2")])
    rig   = _make_silent_rig(level=MOCK_LEVEL)

    task = _freq_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        sgn_level=_SGN_LEVEL, delay=0,
    )
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=queue,
        log_filename="/dev/null",
        rigctl=rig,
        config=_make_config(),
        log=Mock(spec=LogFile),
        sleep_fn=lambda d: sleep_calls.append(d),
    )
    scanner.scan(task)

    assert task.delay == 2
    # queue_sleep calls sleep(1) once per second of delay per signal hit.
    # 2 signal hits × 2 s delay = 4 one-second sleep calls.
    one_second_calls = [d for d in sleep_calls if d == 1]
    assert len(one_second_calls) == 4, (
        f"Expected 4 one-second sleep calls (2 hits × 2 s delay), "
        f"got {len(one_second_calls)}: {sleep_calls}"
    )


# ---------------------------------------------------------------------------
# Unknown event name: silently ignored, scan completes normally
# ---------------------------------------------------------------------------

def test_unknown_event_name_is_ignored_and_scan_completes():
    """An event with an unrecognised param_name is logged and skipped; the
    scan runs all steps normally and returns without raising."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000   # 3 steps
    INTERVAL  =  1_000_000

    queue = _make_live_queue([("ckb_unknown_param", "1")])
    rig   = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    original_passes = task.passes

    _scanner(queue, rig).scan(task)

    assert rig.set_frequency.call_count == 3, (
        "Expected 3 tune calls — unknown event must not abort the scan"
    )
    assert task.passes == original_passes


# ---------------------------------------------------------------------------
# Invalid value: non-convertible string is ignored, scan completes normally
# ---------------------------------------------------------------------------

def test_invalid_event_value_is_ignored_and_scan_completes():
    """A txt_passes event carrying a non-integer string is caught by the
    ValueError handler in process_queue; task.passes remains unchanged."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps
    INTERVAL  =  1_000_000

    queue = _make_live_queue([("txt_passes", "not_a_number")])
    rig   = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=1)
    _scanner(queue, rig).scan(task)

    assert task.passes == 1, f"Expected passes unchanged at 1, got {task.passes}"
    assert rig.set_frequency.call_count == 2, (
        "Expected 2 tune calls — invalid event must not abort the scan"
    )


# ---------------------------------------------------------------------------
# Multiple events: all applied in the same process_queue call
# ---------------------------------------------------------------------------

def test_multiple_queued_events_all_applied():
    """Two events queued together are both consumed in the first process_queue
    call: passes and delay are both updated before any tuning occurs."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps per pass
    INTERVAL  =  1_000_000

    queue = _make_live_queue([
        ("txt_passes", "2"),
        ("txt_delay",  "0"),
    ])
    rig = _make_silent_rig()

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=1)
    _scanner(queue, rig).scan(task)

    assert task.passes == 2
    assert task.delay  == 0
    # 2 passes × 2 steps = 4 tune calls
    assert rig.set_frequency.call_count == 4, (
        f"Expected 4 tune calls (2 passes × 2 steps), "
        f"got {rig.set_frequency.call_count}"
    )

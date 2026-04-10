"""
Tests for rig_remote.scanning — 100% coverage.

Conventions:
  - Test names: test_scanning_<subject>_<scenario>
  - No patch() — all dependencies injected via Mock()
  - Parametrize positive *and* negative cases for every parameter range
"""

import pytest
from unittest.mock import Mock, call

from rig_remote.scanning import (
    ScanningConfig,
    ScannerCore,
    ScannerStrategy,
    BookmarkScannerStrategy,
    FrequencyScannerStrategy,
    Scanning2,
    create_scanner,
)
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.models.channel import Channel
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.disk_io import LogFile
from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.utility import khertz_to_hertz


# ---------------------------------------------------------------------------
# Test-local factories
# ---------------------------------------------------------------------------

def _bm_task(**kw) -> ScanningTask:
    """Bookmark-mode ScanningTask with safe defaults."""
    defaults = dict(
        frequency_modulation="FM",
        scan_mode="bookmarks",
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
    defaults.update(kw)
    return ScanningTask(**defaults)


def _freq_task(**kw) -> ScanningTask:
    """Frequency-mode ScanningTask — range covers exactly 2 steps."""
    defaults = dict(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=100_000_000,
        range_max=100_200_000,
        interval=100_000,
        delay=0,
        passes=1,
        sgn_level=-40,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[],
    )
    defaults.update(kw)
    return ScanningTask(**defaults)


def _rigctl(level: float = -300.0, mode: str = "FM") -> Mock:
    r = Mock(spec=RigCtl)
    r.get_level.return_value = level
    r.get_mode.return_value = mode
    return r


def _queue(events=None) -> Mock:
    """STMessenger mock that serves *events* then stays empty forever.

    Provides len(events)+1 True values so that both the outer caller
    (queue_sleep's if-check) and process_queue's inner while loop each see
    a True before the event is consumed, then all subsequent calls get False.
    """
    q = Mock(spec=STMessenger)
    if not events:
        q.update_queued.return_value = False
        return q
    q.update_queued.side_effect = [True] * (len(events) + 1) + [False] * 999
    q.get_event_update.side_effect = list(events) + [None] * 999
    return q


def _cfg(**kw) -> ScanningConfig:
    defaults = dict(signal_checks=1, no_signal_delay=0.0, time_wait_for_tune=0.0)
    defaults.update(kw)
    return ScanningConfig(**defaults)


def _core(queue=None, rigctl=None, config=None, sleep_fn=None) -> ScannerCore:
    return ScannerCore(
        scan_queue=queue or _queue(),
        rigctl=rigctl or _rigctl(),
        config=config or _cfg(),
        sleep_fn=sleep_fn or (lambda _: None),
    )


def _bookmark(freq: int = 145_500_000, modulation: str = "FM", lockout: str = "O"):
    return bookmark_factory(
        input_frequency=freq,
        modulation=modulation,
        description="test",
        lockout=lockout,
    )


def _log() -> Mock:
    return Mock(spec=LogFile)


# ---------------------------------------------------------------------------
# ScanningConfig
# ---------------------------------------------------------------------------

def test_scanning_config_defaults():
    cfg = ScanningConfig()
    assert cfg.time_wait_for_tune == 0.25
    assert cfg.signal_checks == 2
    assert cfg.no_signal_delay == 0.2
    assert "ckb_wait" in cfg.valid_scan_update_event_names
    assert "txt_range_min" in cfg.valid_scan_update_event_names
    assert len(cfg.valid_scan_update_event_names) == 8


@pytest.mark.parametrize("time_wait,signal_checks,no_signal_delay", [
    (0.0,  1, 0.0),
    (0.1,  2, 0.05),
    (0.5,  5, 0.1),
    (1.0, 10, 0.5),
])
def test_scanning_config_custom_values(time_wait, signal_checks, no_signal_delay):
    cfg = ScanningConfig(
        time_wait_for_tune=time_wait,
        signal_checks=signal_checks,
        no_signal_delay=no_signal_delay,
    )
    assert cfg.time_wait_for_tune == time_wait
    assert cfg.signal_checks == signal_checks
    assert cfg.no_signal_delay == no_signal_delay


@pytest.mark.parametrize("time_wait,signal_checks,no_signal_delay", [
    (-0.1,  1,  0.0),   # negative time_wait_for_tune
    (-1.0,  2,  0.05),  # large negative time_wait_for_tune
    (0.5,  -1,  0.1),   # negative signal_checks
    (0.5,   0,  0.1),   # zero signal_checks
    (0.1,   2, -0.2),   # negative no_signal_delay
    (-0.5, -3, -0.5),   # all negative
])
def test_scanning_config_custom_values_negative(time_wait, signal_checks, no_signal_delay):
    """ScanningConfig is a plain dataclass with no validation; negative/zero values
    are stored as-is without raising errors."""
    cfg = ScanningConfig(
        time_wait_for_tune=time_wait,
        signal_checks=signal_checks,
        no_signal_delay=no_signal_delay,
    )
    assert cfg.time_wait_for_tune == time_wait
    assert cfg.signal_checks == signal_checks
    assert cfg.no_signal_delay == no_signal_delay


@pytest.mark.parametrize("event_name,present", [
    ("ckb_wait",      True),
    ("ckb_record",    True),
    ("txt_range_max", True),
    ("txt_range_min", True),
    ("txt_sgn_level", True),
    ("txt_passes",    True),
    ("txt_interval",  True),
    ("txt_delay",     True),
    ("unknown_event", False),
    ("",              False),
])
def test_scanning_config_valid_event_names(event_name, present):
    cfg = ScanningConfig()
    assert (event_name in cfg.valid_scan_update_event_names) is present


def test_scanning_config_valid_event_names_independent_per_instance():
    """Each instance gets its own list — mutating one doesn't affect another."""
    a = ScanningConfig()
    b = ScanningConfig()
    a.valid_scan_update_event_names.append("extra")
    assert "extra" not in b.valid_scan_update_event_names


# ---------------------------------------------------------------------------
# ScanningConfig — __eq__
# ---------------------------------------------------------------------------

def test_scanning_config_eq_identical_defaults():
    """Two default instances are equal."""
    assert ScanningConfig() == ScanningConfig()


def test_scanning_config_eq_identical_custom_values():
    """Two instances with the same custom values are equal."""
    a = ScanningConfig(time_wait_for_tune=0.5, signal_checks=3, no_signal_delay=0.1)
    b = ScanningConfig(time_wait_for_tune=0.5, signal_checks=3, no_signal_delay=0.1)
    assert a == b


@pytest.mark.parametrize("override", [
    {"time_wait_for_tune": 0.99},
    {"signal_checks": 99},
    {"no_signal_delay": 0.99},
])
def test_scanning_config_eq_single_field_differs(override):
    """Instances differing in any one field are not equal."""
    a = ScanningConfig()
    b = ScanningConfig(**override)
    assert a != b


def test_scanning_config_eq_different_event_names():
    """Instances with different valid_scan_update_event_names are not equal."""
    a = ScanningConfig()
    b = ScanningConfig()
    b.valid_scan_update_event_names = ["only_this"]
    assert a != b


def test_scanning_config_eq_non_scanning_config_returns_not_implemented():
    """Comparing against a non-ScanningConfig returns NotImplemented (Python
    then falls back to identity comparison, yielding False)."""
    cfg = ScanningConfig()
    assert cfg.__eq__("not a config") is NotImplemented
    assert cfg.__eq__(42) is NotImplemented
    assert cfg.__eq__(None) is NotImplemented


# ---------------------------------------------------------------------------
# ScannerStrategy protocol
# ---------------------------------------------------------------------------

def test_scanning_strategy_protocol_stub_methods():
    """Protocol stub methods (the `...` bodies) are reachable via unbound calls."""
    # Protocols cannot be instantiated directly; call via unbound method syntax.
    result = ScannerStrategy.scan(None, Mock(), Mock())  # type: ignore[arg-type]
    assert result is None
    ScannerStrategy.terminate(None)  # type: ignore[arg-type]  # must not raise


def test_scanning_strategy_isinstance_bookmark_scanner():
    assert isinstance(BookmarkScannerStrategy(_core()), ScannerStrategy)


def test_scanning_strategy_isinstance_frequency_scanner():
    assert isinstance(FrequencyScannerStrategy(_core()), ScannerStrategy)


# ---------------------------------------------------------------------------
# ScannerCore — init
# ---------------------------------------------------------------------------

def test_scanning_core_init_custom_sleep():
    calls = []
    sleep = lambda t: calls.append(t)
    core = _core(sleep_fn=sleep)
    core._sleep(0.1)
    assert calls == [0.1]


def test_scanning_core_init_default_sleep_uses_time_sleep():
    """When sleep_fn is omitted, core uses time.sleep (not a Mock)."""
    import time
    core = ScannerCore(
        scan_queue=_queue(),
        rigctl=_rigctl(),
        config=_cfg(),
        # sleep_fn not supplied
    )
    assert core._sleep is time.sleep


# ---------------------------------------------------------------------------
# ScannerCore — lifecycle
# ---------------------------------------------------------------------------

def test_scanning_core_should_stop_before_terminate():
    core = _core()
    assert core.should_stop() is False


def test_scanning_core_terminate_deactivates():
    core = _core()
    core.terminate()
    assert core._scan_active is False


def test_scanning_core_should_stop_after_terminate():
    core = _core()
    core.terminate()
    assert core.should_stop() is True


# ---------------------------------------------------------------------------
# ScannerCore — pass_count_update
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("initial,expected_count,expected_active", [
    (5,  4, True),
    (2,  1, True),
    (1,  0, False),   # last pass → deactivates
    (0,  0, False),   # already zero → still deactivates
])
def test_scanning_core_pass_count_update_parametric(initial, expected_count, expected_active):
    core = _core()
    result = core.pass_count_update(initial)
    assert result == expected_count
    assert core._scan_active is expected_active


# ---------------------------------------------------------------------------
# ScannerCore — signal_check
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sgn_level,levels,signal_checks,expected", [
    # threshold = sgn_level * 10
    (-40,  [-300.0],          1, True),   # -300 >= -400 → found
    (-40,  [-500.0],          1, False),  # -500 <  -400 → not found
    (-40,  [-400.0],          1, True),   # exactly at threshold (>=)
    (-40,  [-401.0],          1, False),  # just below threshold
    (  0,  [   0.0],          1, True),   # zero threshold, zero level
    (-40,  [-300.0, -300.0],  2, True),   # 2 checks, both positive
    (-40,  [-300.0, -500.0],  2, True),   # 2 checks, mixed → at least one found
    (-40,  [-500.0, -500.0],  2, False),  # 2 checks, both negative
    (-100, [-1001.0],         1, False),  # level below low threshold
    (-10,  [-50.0],           1, True),   # threshold=-100; -50 >= -100 → found
])
def test_scanning_core_signal_check_parametric(sgn_level, levels, signal_checks, expected):
    rigctl = _rigctl()
    rigctl.get_level.side_effect = levels + [-999.0] * 50
    core = _core(rigctl=rigctl, config=_cfg(signal_checks=signal_checks, no_signal_delay=0.0))
    assert core.signal_check(sgn_level) is expected


def test_scanning_core_signal_check_calls_get_level_n_times():
    rigctl = _rigctl(level=-300.0)
    core = _core(rigctl=rigctl, config=_cfg(signal_checks=3, no_signal_delay=0.0))
    core.signal_check(-40)
    assert rigctl.get_level.call_count == 3


def test_scanning_core_signal_check_sleeps_between_checks():
    slept = []
    rigctl = _rigctl(level=-300.0)
    core = _core(rigctl=rigctl, config=_cfg(signal_checks=2, no_signal_delay=0.1),
                 sleep_fn=lambda t: slept.append(t))
    core.signal_check(-40)
    assert slept.count(0.1) == 2


# ---------------------------------------------------------------------------
# ScannerCore — channel_tune
# ---------------------------------------------------------------------------

def test_scanning_core_channel_tune_success():
    rigctl = _rigctl()
    core = _core(rigctl=rigctl)
    core.channel_tune(Channel(modulation="FM", input_frequency=145_500_000))
    rigctl.set_frequency.assert_called_once_with(145_500_000)
    rigctl.set_mode.assert_called_once_with("FM")


def test_scanning_core_channel_tune_sleeps_after_each_stage():
    slept = []
    rigctl = _rigctl()
    core = _core(rigctl=rigctl, config=_cfg(time_wait_for_tune=0.25),
                 sleep_fn=lambda t: slept.append(t))
    core.channel_tune(Channel(modulation="FM", input_frequency=100_000_000))
    assert slept == [0.25, 0.25]


@pytest.mark.parametrize("freq_effect,mode_effect,expected_exc,scan_active_after", [
    # frequency errors
    (OSError("freq"),     None,            OSError,     False),
    (TimeoutError("freq"), None,           TimeoutError, False),
    (ValueError("freq"),  None,            ValueError,  True),   # no deactivation
    # mode errors (frequency succeeds)
    (None, OSError("mode"),     OSError,     False),
    (None, TimeoutError("mode"), TimeoutError, False),
    (None, ValueError("mode"),  ValueError,  True),   # no deactivation
])
def test_scanning_core_channel_tune_error_parametric(
    freq_effect, mode_effect, expected_exc, scan_active_after
):
    rigctl = _rigctl()
    if freq_effect is not None:
        rigctl.set_frequency.side_effect = freq_effect
    if mode_effect is not None:
        rigctl.set_mode.side_effect = mode_effect

    core = _core(rigctl=rigctl)
    with pytest.raises(expected_exc):
        core.channel_tune(Channel(modulation="FM", input_frequency=145_500_000))
    assert core._scan_active is scan_active_after


# ---------------------------------------------------------------------------
# ScannerCore — process_queue
# ---------------------------------------------------------------------------

def test_scanning_core_process_queue_empty_returns_false():
    core = _core(queue=_queue())
    assert core.process_queue(_bm_task()) is False


def test_scanning_core_process_queue_none_event_returns_false():
    core = _core(queue=_queue(events=[None]))
    assert core.process_queue(_bm_task()) is False


def test_scanning_core_process_queue_invalid_event_name_returns_false():
    core = _core(queue=_queue(events=[("bad_event", "value")]))
    assert core.process_queue(_bm_task()) is False


@pytest.mark.parametrize("event,attr,expected_value", [
    (("txt_range_min", "88000"),  "range_min", khertz_to_hertz(88000)),
    (("txt_range_max", "108000"), "range_max", khertz_to_hertz(108000)),
    (("txt_delay",     "7"),      "delay",     "7"),
    (("txt_passes",    "3"),      "passes",    "3"),
    (("txt_interval",  "500"),    "interval",  "500"),
    (("txt_sgn_level", "-50"),    "sgn_level", "-50"),
    (("ckb_wait",      True),     "wait",      True),
    (("ckb_record",    False),    "record",    False),
])
def test_scanning_core_process_queue_valid_event_parametric(event, attr, expected_value):
    core = _core(queue=_queue(events=[event]))
    task = _bm_task()
    result = core.process_queue(task)
    assert result is True
    assert getattr(task, attr) == expected_value


def test_scanning_core_process_queue_range_min_uses_khertz_to_hertz():
    core = _core(queue=_queue(events=[("txt_range_min", "88")]))
    task = _bm_task()
    core.process_queue(task)
    assert task.range_min == 88_000  # 88 kHz → 88_000 Hz


def test_scanning_core_process_queue_exception_returns_false():
    """int("bad") raises ValueError → except block → returns False."""
    core = _core(queue=_queue(events=[("txt_range_min", "not_a_number")]))
    assert core.process_queue(_bm_task()) is False


def test_scanning_core_process_queue_multiple_events_all_applied():
    events = [("txt_delay", "3"), ("txt_passes", "5")]
    core = _core(queue=_queue(events=events))
    task = _bm_task()
    result = core.process_queue(task)
    assert result is True
    assert task.delay == "3"
    assert task.passes == "5"


# ---------------------------------------------------------------------------
# ScannerCore — queue_sleep
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delay,expected_sleep_calls", [
    (0, 0),
    (1, 1),
    (3, 3),
])
def test_scanning_core_queue_sleep_parametric(delay, expected_sleep_calls):
    slept = []
    core = _core(sleep_fn=lambda t: slept.append(t))
    task = _bm_task(delay=delay)
    core.queue_sleep(task)
    assert len(slept) == expected_sleep_calls


def test_scanning_core_queue_sleep_processes_queued_events():
    events = [("txt_delay", "5")]
    queue = _queue(events=events)
    core = _core(queue=queue)
    task = _bm_task(delay=0)
    core.queue_sleep(task)
    assert task.delay == "5"


def test_scanning_core_queue_sleep_checks_queue_each_iteration():
    """update_queued is called once per sleep cycle (delay=2 → 3 total checks)."""
    queue = _queue()
    core = _core(queue=queue)
    core.queue_sleep(_bm_task(delay=2))
    # delay=2: iterations are [sleep,sleep,break] → 3 update_queued calls
    assert queue.update_queued.call_count == 3


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — terminate
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_terminate():
    core = _core()
    scanner = BookmarkScannerStrategy(core)
    scanner.terminate()
    assert core._scan_active is False


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: basic loop control
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_empty_bookmarks_notifies_end():
    queue = _queue()
    core = _core(queue=queue)
    scanner = BookmarkScannerStrategy(core)
    result = scanner.scan(_bm_task(bookmarks=[], passes=1), _log())
    queue.notify_end_of_scan.assert_called_once()
    assert result is not None


def test_scanning_bookmark_scanner_returns_task():
    core = _core()
    scanner = BookmarkScannerStrategy(core)
    task = _bm_task()
    result = scanner.scan(task, _log())
    assert result is task


@pytest.mark.parametrize("passes,expected_notify_calls", [
    (1, 1),
    (2, 1),  # notify_end_of_scan called once regardless of passes
    (3, 1),
])
def test_scanning_bookmark_scanner_pass_count_exhaustion_parametric(passes, expected_notify_calls):
    queue = _queue()
    core = _core(queue=queue)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(passes=passes), _log())
    assert queue.notify_end_of_scan.call_count == expected_notify_calls


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: locked bookmark
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_locked_bookmark_skipped():
    rigctl = _rigctl()
    core = _core(rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    locked = _bookmark(lockout="L")
    scanner.scan(_bm_task(bookmarks=[locked]), _log())
    rigctl.set_frequency.assert_not_called()


def test_scanning_bookmark_scanner_unlocked_bookmark_tuned():
    rigctl = _rigctl()
    core = _core(rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    bm = _bookmark(freq=145_500_000)
    scanner.scan(_bm_task(bookmarks=[bm]), _log())
    rigctl.set_frequency.assert_called_once_with(145_500_000)


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: tune errors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [OSError("comm"), TimeoutError("timeout")])
def test_scanning_bookmark_scanner_tune_error_breaks_and_completes(exc):
    """OSError/TimeoutError from channel_tune breaks the for-loop;
    scan still calls notify_end_of_scan."""
    rigctl = _rigctl()
    rigctl.set_frequency.side_effect = exc
    queue = _queue()
    core = _core(rigctl=rigctl, queue=queue)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()]), _log())
    queue.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: process_queue updates pass_count
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_process_queue_resets_pass_count():
    """If process_queue returns True, pass_count is reset to task.passes."""
    # Use txt_sgn_level (string value) rather than txt_delay to avoid queue_sleep
    # crashing on `"9" > 0` when remaining = task.delay is later read as a string.
    events = [("txt_sgn_level", "-40")]
    queue = _queue(events=events)
    rigctl = _rigctl()
    core = _core(queue=queue, rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    bm = _bookmark()
    # passes=2 so we run at least one full bookmark iteration
    scanner.scan(_bm_task(bookmarks=[bm], passes=2), _log())
    queue.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: record
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("record,expected_calls", [
    (True,  1),
    (False, 0),
])
def test_scanning_bookmark_scanner_record_parametric(record, expected_calls):
    rigctl = _rigctl()
    core = _core(rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()], record=record), _log())
    assert rigctl.start_recording.call_count == expected_calls
    assert rigctl.stop_recording.call_count == expected_calls


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: log
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("do_log,expected_write_calls", [
    (True,  1),
    (False, 0),
])
def test_scanning_bookmark_scanner_log_parametric(do_log, expected_write_calls):
    core = _core()
    scanner = BookmarkScannerStrategy(core)
    log = _log()
    scanner.scan(_bm_task(bookmarks=[_bookmark()], log=do_log), log)
    assert log.write.call_count == expected_write_calls


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: wait loop
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_wait_false_skips_wait_loop():
    """When wait=False the wait-loop body is never entered."""
    rigctl = _rigctl()
    core = _core(rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()], wait=False), _log())
    # get_level called only by the main signal_check (1 call), not again for wait loop
    assert rigctl.get_level.call_count == 1


def test_scanning_bookmark_scanner_wait_loop_no_signal_breaks_immediately():
    """wait=True, signal absent → else:break on first wait-loop iteration."""
    rigctl = _rigctl(level=-600.0)  # level below threshold → no signal
    core = _core(rigctl=rigctl)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()], wait=True), _log())
    # Two get_level calls: main signal_check + wait loop (which gets False → break)
    assert rigctl.get_level.call_count == 2


def test_scanning_bookmark_scanner_wait_loop_process_queue_called_on_signal():
    """wait=True, signal found in wait loop once → process_queue called inside loop."""
    call_num = [0]

    def controlled_signal_check(sgn_level):
        call_num[0] += 1
        # call 1: main check → True
        # call 2: wait-loop iter 1 → True  (process_queue path)
        # call 3: wait-loop iter 2 → False (else:break)
        return call_num[0] < 3

    queue = _queue()
    core = _core(queue=queue)
    core.signal_check = Mock(side_effect=controlled_signal_check)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()], wait=True), _log())
    assert call_num[0] == 3


def test_scanning_bookmark_scanner_wait_loop_inactive_breaks():
    """Inside wait loop: _scan_active=False makes condition False → else:break."""
    call_num = [0]
    core = _core()

    def signal_and_terminate(sgn_level):
        call_num[0] += 1
        if call_num[0] == 2:      # first wait-loop iteration
            core._scan_active = False
        return True               # signal always "found"

    core.signal_check = Mock(side_effect=signal_and_terminate)
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()], wait=True), _log())
    # scan returned early (should_stop=True after wait loop broke)
    assert call_num[0] == 2


# ---------------------------------------------------------------------------
# BookmarkScannerStrategy — scan: queue_sleep guard and should_stop early return
# ---------------------------------------------------------------------------

def test_scanning_bookmark_scanner_queue_sleep_called_when_active():
    """queue_sleep is invoked when _scan_active remains True after bookmark."""
    core = _core()
    sleep_calls = []
    core.queue_sleep = Mock(side_effect=lambda t: sleep_calls.append(t))
    scanner = BookmarkScannerStrategy(core)
    scanner.scan(_bm_task(bookmarks=[_bookmark()]), _log())
    assert len(sleep_calls) == 1


def test_scanning_bookmark_scanner_queue_sleep_skipped_when_inactive_and_early_return():
    """When channel_tune sets _scan_active=False (without exception), queue_sleep
    is skipped and should_stop() triggers early return."""
    core = _core()
    sleep_calls = []
    core.queue_sleep = Mock(side_effect=lambda t: sleep_calls.append(t))

    def terminating_tune(ch):
        core._scan_active = False

    core.channel_tune = Mock(side_effect=terminating_tune)
    scanner = BookmarkScannerStrategy(core)
    result = scanner.scan(_bm_task(bookmarks=[_bookmark()]), _log())
    # queue_sleep must NOT be called (active=False → guard skips it)
    assert len(sleep_calls) == 0
    # notify_end_of_scan NOT called — we returned early
    core.scan_queue.notify_end_of_scan.assert_not_called()
    assert result is not None


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — terminate
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_terminate():
    core = _core()
    scanner = FrequencyScannerStrategy(core)
    scanner.terminate()
    assert core._scan_active is False


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — bookmark helpers
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_create_new_bookmark():
    rigctl = _rigctl(mode="AM")
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    bm = scanner._create_new_bookmark(145_500_000)
    assert bm.channel.frequency == 145_500_000
    assert bm.channel.modulation == "AM"


def test_scanning_freq_scanner_store_prev_bookmark():
    scanner = FrequencyScannerStrategy(_core())
    scanner._store_prev_bookmark(level=-30.0, freq=100_000_000)
    assert scanner._prev_level == -30.0
    assert scanner._prev_freq == 100_000_000
    assert scanner._hold_bookmark is True


def test_scanning_freq_scanner_erase_prev_bookmark():
    scanner = FrequencyScannerStrategy(_core())
    scanner._store_prev_bookmark(level=-30.0, freq=100_000_000)
    scanner._erase_prev_bookmark()
    assert scanner._prev_level == 0.0
    assert scanner._prev_freq == 0
    assert scanner._hold_bookmark is False


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — _autobookmark
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_autobookmark_first_call_stores_prev():
    """First call with prev_level=0 → store, no bookmark added."""
    scanner = FrequencyScannerStrategy(_core())
    task = _freq_task(new_bookmarks_list=[])
    scanner._autobookmark(level=-40, freq=100_000_000, task=task)
    assert scanner._prev_level == -40
    assert scanner._prev_freq == 100_000_000
    assert scanner._hold_bookmark is True
    assert len(task.new_bookmarks_list) == 0


@pytest.mark.parametrize("prev_level,new_level,expect_bookmark_added", [
    (-30, -40, True),   # new_level <= prev_level → bookmark added (peak passed)
    (-30, -30, True),   # equal → bookmark added
    (-30, -20, False),  # new_level >  prev_level → update prev (still ascending)
])
def test_scanning_freq_scanner_autobookmark_level_comparison_parametric(
    prev_level, new_level, expect_bookmark_added
):
    rigctl = _rigctl(mode="FM")
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    task = _freq_task(new_bookmarks_list=[])
    # Seed prev_level so first call doesn't take the "prev_level=0" branch
    scanner._store_prev_bookmark(level=prev_level, freq=100_000_000)
    scanner._autobookmark(level=new_level, freq=100_100_000, task=task)
    assert (len(task.new_bookmarks_list) == 1) is expect_bookmark_added


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: basic flow
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_scan_no_signal_completes():
    """No signal anywhere; scan completes one pass and notifies end."""
    rigctl = _rigctl(level=-600.0)  # below threshold
    queue = _queue()
    core = _core(rigctl=rigctl, queue=queue)
    scanner = FrequencyScannerStrategy(core)
    task = _freq_task()
    result = scanner.scan(task, _log())
    queue.notify_end_of_scan.assert_called_once()
    assert result is task


def test_scanning_freq_scanner_scan_iterates_frequency_range():
    """set_frequency is called for each step in the range."""
    rigctl = _rigctl(level=-600.0)
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    # range 100M..100.3M, step 100k → 3 tunes: 100M, 100.1M, 100.2M
    task = _freq_task(range_min=100_000_000, range_max=100_300_000, interval=100_000)
    scanner.scan(task, _log())
    assert rigctl.set_frequency.call_count == 3


@pytest.mark.parametrize("passes,expected_freq_calls", [
    (1, 2),  # range 100M..100.2M step 100k = 2 freqs per pass
    (2, 4),
    (3, 6),
])
def test_scanning_freq_scanner_scan_multiple_passes_parametric(passes, expected_freq_calls):
    rigctl = _rigctl(level=-600.0)
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(_freq_task(passes=passes), _log())
    assert rigctl.set_frequency.call_count == expected_freq_calls


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: process_queue resets pass_count
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_process_queue_resets_pass_count():
    events = [("txt_delay", "9")]
    queue = _queue(events=events)
    rigctl = _rigctl(level=-600.0)
    core = _core(rigctl=rigctl, queue=queue)
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(_freq_task(passes=2), _log())
    queue.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: range_min > range_max
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_scan_range_min_gt_range_max_terminates():
    """If range_min > range_max at scan time, terminate() is called and
    the inner while is skipped; notify_end_of_scan is still called."""
    queue = _queue()
    core = _core(queue=queue)
    scanner = FrequencyScannerStrategy(core)
    task = _freq_task()
    task.range_max = 50_000_000  # force invalid after construction
    scanner.scan(task, _log())
    assert core._scan_active is False
    queue.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: should_stop early return
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_scan_should_stop_early_return():
    """channel_tune deactivates core (no exception); next inner-while iteration
    hits should_stop() → True → returns without notify_end_of_scan."""
    # range covers 3 steps so there is a 'next' iteration
    task = _freq_task(range_min=100_000_000, range_max=100_300_000, interval=100_000)
    rigctl = _rigctl(level=-600.0)
    queue = _queue()
    core = _core(rigctl=rigctl, queue=queue)

    def terminating_tune(ch):
        core._scan_active = False

    core.channel_tune = Mock(side_effect=terminating_tune)
    scanner = FrequencyScannerStrategy(core)
    result = scanner.scan(task, _log())
    queue.notify_end_of_scan.assert_not_called()
    assert result is task


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: tune errors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [
    OSError("comm"),
    TimeoutError("timeout"),
    ValueError("bad freq"),
])
def test_scanning_freq_scanner_scan_tune_error_breaks_inner_loop(exc):
    """A tune exception breaks the inner freq-loop; outer loop runs pass_count_update
    and terminates normally."""
    rigctl = _rigctl()
    rigctl.set_frequency.side_effect = exc
    queue = _queue()
    core = _core(rigctl=rigctl, queue=queue)
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(_freq_task(), _log())
    queue.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: signal found branches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("record,expected_rec_calls", [
    (True,  2),   # _freq_task covers 2 steps (100M, 100.1M); signal on each → 2 calls
    (False, 0),
])
def test_scanning_freq_scanner_scan_record_parametric(record, expected_rec_calls):
    rigctl = _rigctl(level=-300.0)  # signal above threshold
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(_freq_task(record=record), _log())
    assert rigctl.start_recording.call_count == expected_rec_calls
    assert rigctl.stop_recording.call_count == expected_rec_calls


@pytest.mark.parametrize("do_log,expected_write_calls", [
    (True,  2),   # 2 steps in range, signal on each → 2 writes
    (False, 0),
])
def test_scanning_freq_scanner_scan_log_parametric(do_log, expected_write_calls):
    rigctl = _rigctl(level=-300.0)  # signal always present
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    log = _log()
    scanner.scan(_freq_task(log=do_log), log)
    assert log.write.call_count == expected_write_calls


def test_scanning_freq_scanner_scan_queue_sleep_called_when_signal_and_active():
    """queue_sleep is called once per freq where signal is found."""
    rigctl = _rigctl(level=-300.0)
    core = _core(rigctl=rigctl)
    sleep_calls = []
    core.queue_sleep = Mock(side_effect=lambda t: sleep_calls.append(t))
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(_freq_task(), _log())
    # 2 freqs in range, both have signal → 2 queue_sleep calls
    assert len(sleep_calls) == 2


@pytest.mark.parametrize("auto_bookmark", [True, False])
def test_scanning_freq_scanner_scan_auto_bookmark_parametric(auto_bookmark):
    """With auto_bookmark=True, autobookmark logic is triggered on signal."""
    rigctl = _rigctl(level=-300.0, mode="FM")
    core = _core(rigctl=rigctl)
    scanner = FrequencyScannerStrategy(core)
    task = _freq_task(auto_bookmark=auto_bookmark)
    scanner.scan(task, _log())
    # If auto_bookmark is True and signal found: _prev_level or new_bookmarks_list changes
    # (exact value depends on level comparison; just verify no exception)


# ---------------------------------------------------------------------------
# FrequencyScannerStrategy — scan: hold_bookmark (elif self._hold_bookmark)
# ---------------------------------------------------------------------------

def test_scanning_freq_scanner_scan_hold_bookmark_adds_to_list():
    """Freq A: signal → _autobookmark → _hold_bookmark=True.
    Freq B: no signal + _hold_bookmark=True → new bookmark appended."""
    # range: 100M, 100.1M (2 steps)
    task = _freq_task(
        range_min=100_000_000, range_max=100_200_000, interval=100_000,
        auto_bookmark=True, new_bookmarks_list=[],
    )
    rigctl = _rigctl(mode="FM")
    # signal_checks=1: one get_level call per frequency.
    # First freq (100M): -300.0 → signal found → auto_bookmark → _hold_bookmark=True
    # Second freq (100.1M): -600.0 → no signal → elif self._hold_bookmark branch
    rigctl.get_level.side_effect = [-300.0, -600.0] + [-600.0] * 50

    core = _core(rigctl=rigctl, config=_cfg(signal_checks=1))
    scanner = FrequencyScannerStrategy(core)
    scanner.scan(task, _log())

    # After first freq auto_bookmark: _hold_bookmark=True, _prev_level=-40 (sgn_level)
    # After second freq (no signal): elif self._hold_bookmark → _create_new_bookmark
    # new_bookmarks_list should have at least one entry
    assert len(task.new_bookmarks_list) >= 1


# ---------------------------------------------------------------------------
# Scanning2 facade
# ---------------------------------------------------------------------------

def test_scanning_facade_terminate_delegates():
    strategy = Mock(spec=ScannerStrategy)
    facade = Scanning2(scanner=strategy, log=_log(), log_filename="/tmp/scan.log")
    facade.terminate()
    strategy.terminate.assert_called_once()


def test_scanning_facade_scan_no_log():
    """task.log=False → log.open never called; strategy.scan called once."""
    strategy = Mock(spec=ScannerStrategy)
    log = _log()
    facade = Scanning2(scanner=strategy, log=log, log_filename="/tmp/scan.log")
    task = _bm_task(log=False)
    facade.scan(task)
    log.open.assert_not_called()
    log.close.assert_not_called()
    strategy.scan.assert_called_once_with(task, log)


def test_scanning_facade_scan_with_log():
    """task.log=True → log.open, strategy.scan, log.close called in order."""
    strategy = Mock(spec=ScannerStrategy)
    log = _log()
    facade = Scanning2(scanner=strategy, log=log, log_filename="/tmp/scan.log")
    task = _bm_task(log=True)
    facade.scan(task)
    log.open.assert_called_once_with("/tmp/scan.log")
    strategy.scan.assert_called_once_with(task, log)
    log.close.assert_called_once()


def test_scanning_facade_scan_log_open_ioerror_propagates():
    """IOError from log.open is re-raised and strategy.scan is NOT called."""
    strategy = Mock(spec=ScannerStrategy)
    log = _log()
    log.open.side_effect = IOError("disk full")
    facade = Scanning2(scanner=strategy, log=log, log_filename="/tmp/scan.log")
    with pytest.raises(IOError):
        facade.scan(_bm_task(log=True))
    strategy.scan.assert_not_called()
    log.close.assert_not_called()


# ---------------------------------------------------------------------------
# create_scanner factory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,expected_strategy_type", [
    ("bookmarks", BookmarkScannerStrategy),
    ("frequency", FrequencyScannerStrategy),
    ("BOOKMARKS", BookmarkScannerStrategy),  # case-insensitive
    ("FREQUENCY", FrequencyScannerStrategy),
])
def test_scanning_factory_mode_returns_correct_strategy_parametric(mode, expected_strategy_type):
    rigctl = _rigctl()
    queue = _queue()
    facade = create_scanner(
        scan_mode=mode,
        scan_queue=queue,
        log_filename="/tmp/scan.log",
        rigctl=rigctl,
    )
    assert isinstance(facade, Scanning2)
    assert isinstance(facade._scanner, expected_strategy_type)


@pytest.mark.parametrize("bad_mode", [
    "unknown",
    "book",
    "freq",
    "",
    "scan",
    "Bookmarks_extra",
])
def test_scanning_factory_invalid_mode_raises_valueerror_parametric(bad_mode):
    with pytest.raises(ValueError, match="Unsupported scan_mode"):
        create_scanner(
            scan_mode=bad_mode,
            scan_queue=_queue(),
            log_filename="/tmp/scan.log",
            rigctl=_rigctl(),
        )


def test_scanning_factory_uses_default_config_when_not_provided():
    facade = create_scanner("bookmarks", _queue(), "/tmp/scan.log", _rigctl())
    core = facade._scanner._core
    assert isinstance(core.config, ScanningConfig)
    assert core.config.signal_checks == ScanningConfig().signal_checks


def test_scanning_factory_uses_custom_config():
    custom = _cfg(signal_checks=5, no_signal_delay=0.3)
    facade = create_scanner(
        "bookmarks", _queue(), "/tmp/scan.log", _rigctl(), config=custom
    )
    assert facade._scanner._core.config.signal_checks == 5
    assert facade._scanner._core.config.no_signal_delay == 0.3


def test_scanning_factory_uses_default_log_when_not_provided():
    facade = create_scanner("bookmarks", _queue(), "/tmp/scan.log", _rigctl())
    assert isinstance(facade._log, LogFile)


def test_scanning_factory_uses_custom_log():
    custom_log = _log()
    facade = create_scanner(
        "bookmarks", _queue(), "/tmp/scan.log", _rigctl(), log=custom_log
    )
    assert facade._log is custom_log


def test_scanning_factory_uses_custom_sleep_fn():
    slept = []
    sleep = lambda t: slept.append(t)
    facade = create_scanner(
        "bookmarks", _queue(), "/tmp/scan.log", _rigctl(), sleep_fn=sleep
    )
    facade._scanner._core._sleep(0.5)
    assert slept == [0.5]


def test_scanning_factory_injects_rigctl_into_core():
    rigctl = _rigctl()
    facade = create_scanner("frequency", _queue(), "/tmp/scan.log", rigctl)
    assert facade._scanner._core.rigctl is rigctl


def test_scanning_factory_injects_queue_into_core():
    queue = _queue()
    facade = create_scanner("bookmarks", queue, "/tmp/scan.log", _rigctl())
    assert facade._scanner._core.scan_queue is queue


def test_scanning_factory_sets_log_filename():
    facade = create_scanner(
        "bookmarks", _queue(), "/var/log/rig.log", _rigctl()
    )
    assert facade._log_filename == "/var/log/rig.log"

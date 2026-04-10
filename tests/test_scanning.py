"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
Author: Simone Marzona <rafael@defying.me>

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
"""

from unittest.mock import Mock, create_autospec

import pytest

from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import Scanning
from rig_remote.scanning import ScanningTask
from rig_remote.stmessenger import STMessenger


@pytest.fixture
def scanning():
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(endpoint=rig_endpoint)
    scanning = Scanning(
        scan_queue=STMessenger(queue_comms=QueueComms()),
        log_filename="test_filename",
        rigctl=rigctl,
    )
    scanning._TIME_WAIT_FOR_TUNE = 0
    scanning._NO_SINGNAL_DELAY = 0
    scanning._log = Mock()
    return scanning


@pytest.fixture
def create_bookmark():
    """Factory fixture to create bookmarks with different configurations."""

    def _create(frequency=1, modulation="FM", description="test", lockout=""):
        return Bookmark(
            channel=Channel(input_frequency=frequency, modulation=modulation),
            description=description,
            lockout=lockout,
        )

    return _create


@pytest.fixture
def create_scanning_task():
    """Factory fixture to create scanning tasks with various configurations."""

    def _create(
        scan_mode="frequency",
        frequency_modulation="FM",
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=200,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=None,
    ):
        return ScanningTask(
            frequency_modulation=frequency_modulation,
            scan_mode=scan_mode,
            new_bookmarks_list=[],
            range_min=range_min,
            range_max=range_max,
            interval=interval,
            delay=delay,
            passes=passes,
            sgn_level=sgn_level,
            wait=wait,
            record=record,
            auto_bookmark=auto_bookmark,
            log=log,
            bookmarks=bookmarks or [],
        )

    return _create


@pytest.mark.parametrize("call_count", [1, 2, 3, 5, 10])
def test_scanning_terminate_multiple_calls(scanning, call_count):
    """Test terminate can be called multiple times safely."""
    assert scanning._scan_active is True
    for _ in range(call_count):
        scanning.terminate()
        assert scanning._scan_active is False


@pytest.mark.parametrize(
    "scan_mode, modulation, log_enabled, record_enabled, auto_bookmark_enabled",
    [
        ("bookmarks", "FM", False, False, False),
        ("frequency", "FM", False, False, False),
        ("bookmarks", "AM", True, False, False),
        ("frequency", "AM", True, False, False),
        ("bookmarks", "USB", False, True, False),
        ("frequency", "LSB", False, True, False),
        ("bookmarks", "FM", True, True, False),
        ("frequency", "FM", True, True, True),
        ("bookmarks", "CW", True, True, True),
        ("frequency", "WFM", False, False, True),
    ],
)
def test_scanning_scan_wrapper_modes(
    scanning,
    create_bookmark,
    create_scanning_task,
    scan_mode,
    modulation,
    log_enabled,
    record_enabled,
    auto_bookmark_enabled,
):
    """Test scan wrapper routes to correct method based on scan_mode."""
    bookmarks = [create_bookmark(modulation=modulation, lockout="L")] if scan_mode == "bookmarks" else []

    task = create_scanning_task(
        scan_mode=scan_mode,
        frequency_modulation=modulation,
        log=log_enabled,
        record=record_enabled,
        auto_bookmark=auto_bookmark_enabled,
        bookmarks=bookmarks,
    )

    # Mock the methods AND update the dispatch map to use the mocks
    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning._dispatch["bookmarks"] = scanning._bookmarks
    scanning._dispatch["frequency"] = scanning._frequency

    scanning.scan(task=task)

    if scan_mode == "bookmarks":
        scanning._bookmarks.assert_called_once()
        scanning._frequency.assert_not_called()
    else:
        scanning._frequency.assert_called_once()
        scanning._bookmarks.assert_not_called()


@pytest.mark.parametrize(
    "lockout_value, modulation",
    [
        ("L", "FM"),
        ("L", "AM"),
        ("L", "USB"),
        ("L", "LSB"),
        ("L", "CW"),
        ("L", "WFM"),
    ],
)
def test_scanning_scan_bookmarks_with_lockout(
    scanning, create_bookmark, create_scanning_task, lockout_value, modulation
):
    """Test bookmarks with lockout 'L' are skipped."""
    bookmarks = [create_bookmark(modulation=modulation, lockout=lockout_value)]
    task = create_scanning_task(scan_mode="bookmarks", bookmarks=bookmarks)

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    assert scanning._scan_active is True
    scanning._bookmarks(task=task)
    assert scanning._scan_active is False
    scanning._rigctl.set_frequency.assert_not_called()
    scanning._rigctl.get_level.assert_not_called()


@pytest.mark.parametrize(
    "scan_mode, num_bookmarks, log_enabled",
    [
        ("bookmarks", 1, False),
        ("bookmarks", 2, False),
        ("bookmarks", 5, False),
        ("frequency", 0, False),
        ("bookmarks", 1, True),
        ("bookmarks", 2, True),
        ("bookmarks", 3, True),
        ("frequency", 0, True),
    ],
)
def test_scanning_scan_various_configurations(
    scanning, create_bookmark, create_scanning_task, scan_mode, num_bookmarks, log_enabled
):
    """Test scanning with various configurations."""
    bookmarks = [create_bookmark(frequency=i * 1000) for i in range(1, num_bookmarks + 1)]
    task = create_scanning_task(
        scan_mode=scan_mode,
        bookmarks=bookmarks,
        log=log_enabled,
    )

    # Mock the methods AND update the dispatch map to use the mocks
    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning._log_close = Mock()
    scanning._dispatch["bookmarks"] = scanning._bookmarks
    scanning._dispatch["frequency"] = scanning._frequency

    scanning.scan(task=task)

    if scan_mode == "bookmarks":
        scanning._bookmarks.assert_called_once()
        scanning._frequency.assert_not_called()
    else:
        scanning._frequency.assert_called_once()
        scanning._bookmarks.assert_not_called()


@pytest.mark.parametrize(
    "scan_mode, exception_class, error_message",
    [
        ("bookmarks", IOError, "Test IOError"),
        ("frequency", IOError, "Test IOError"),
        ("bookmarks", IOError, "File not found"),
        ("frequency", IOError, "Permission denied"),
    ],
)
def test_scanning_scan_io_errors(
    scanning, create_bookmark, create_scanning_task, scan_mode, exception_class, error_message
):
    """Test IOError handling during log file operations."""
    bookmarks = [create_bookmark(), create_bookmark(frequency=2000)] if scan_mode == "bookmarks" else []
    task = create_scanning_task(scan_mode=scan_mode, bookmarks=bookmarks, log=True)

    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning._log_close = Mock()
    mock_log = create_autospec(LogFile)
    mock_log.open = Mock(side_effect=exception_class(error_message))
    scanning._log = mock_log

    with pytest.raises(exception_class):
        scanning.scan(task=task)

    scanning._bookmarks.assert_not_called()
    scanning._frequency.assert_not_called()
    scanning._log_close.assert_not_called()


@pytest.mark.parametrize(
    "exception_type, scan_mode, passes, modulation",
    [
        (ValueError, "frequency", 1, "FM"),
        (ValueError, "frequency", 2, "AM"),
        (OSError, "frequency", 1, "USB"),
        (OSError, "frequency", 2, "LSB"),
        (TimeoutError, "frequency", 1, "FM"),
        (TimeoutError, "frequency", 3, "AM"),
        (ConnectionError, "frequency", 1, "FM"),
        (ConnectionError, "frequency", 2, "USB"),
    ],
)
def test_scanning_set_frequency_exceptions(
    scanning, create_scanning_task, exception_type, scan_mode, passes, modulation
):
    """Test exception handling in set_frequency operations."""
    task = create_scanning_task(
        scan_mode=scan_mode,
        passes=passes,
        frequency_modulation=modulation,
        log=True,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_frequency.side_effect = exception_type

    scanning.scan(task=task)
    assert scanning._scan_active is False


@pytest.mark.parametrize(
    "exception_type, scan_mode, modulation",
    [
        (ValueError, "frequency", "FM"),
        (ValueError, "frequency", "AM"),
        (OSError, "frequency", "USB"),
        (OSError, "frequency", "LSB"),
        (TimeoutError, "frequency", "FM"),
        (TimeoutError, "frequency", "CW"),
        (ConnectionError, "frequency", "WFM"),
    ],
)
def test_scanning_set_mode_exceptions(scanning, create_scanning_task, exception_type, scan_mode, modulation):
    """Test exception handling in set_mode operations."""
    task = create_scanning_task(
        scan_mode=scan_mode,
        passes=2,
        frequency_modulation=modulation,
        log=True,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_mode.side_effect = exception_type

    scanning.scan(task=task)
    assert scanning._scan_active is False


@pytest.mark.parametrize(
    "num_bookmarks, sgn_level, signal_level, wait, record, modulation",
    [
        (1, 30, 2500, False, False, "FM"),
        (2, 30, 2500, False, True, "FM"),
        (3, 30, 2500, False, True, "AM"),
        (2, 100, 3000, False, True, "USB"),
        (1, 200, 5000, False, False, "LSB"),
        (4, 50, 2000, False, True, "FM"),
    ],
)
def test_scanning_bookmarks_no_wait_scenarios(
    scanning, create_bookmark, create_scanning_task, num_bookmarks, sgn_level, signal_level, wait, record, modulation
):
    """Test bookmark scanning without wait flag."""
    bookmarks = [create_bookmark(frequency=i * 1000, modulation=modulation) for i in range(1, num_bookmarks + 1)]
    task = create_scanning_task(
        scan_mode="bookmarks",
        bookmarks=bookmarks,
        sgn_level=sgn_level,
        wait=wait,
        record=record,
        log=True,
        frequency_modulation=modulation,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = signal_level

    assert scanning._scan_active is True
    scanning._bookmarks(task=task)
    assert scanning._scan_active is False

    assert scanning._rigctl.set_frequency.call_count == num_bookmarks
    assert scanning._rigctl.set_mode.call_count == num_bookmarks
    assert scanning._log.write.call_count == num_bookmarks
    assert scanning._rigctl.get_level.call_count == scanning._SIGNAL_CHECKS * num_bookmarks

    if record:
        assert scanning._rigctl.start_recording.call_count == num_bookmarks
    else:
        scanning._rigctl.start_recording.assert_not_called()


@pytest.mark.parametrize(
    "num_bookmarks, sgn_level, signal_level, record, modulation",
    [
        (1, 250, 250, False, "FM"),
        (2, 250, 250, True, "FM"),
        (3, 100, 100, True, "AM"),
        (2, 500, 500, True, "USB"),
        (1, 1000, 1000, False, "LSB"),
    ],
)
def test_scanning_bookmarks_with_wait_scenarios(
    scanning, create_bookmark, create_scanning_task, num_bookmarks, sgn_level, signal_level, record, modulation
):
    """Test bookmark scanning with wait flag enabled."""
    bookmarks = [create_bookmark(frequency=i * 1000, modulation=modulation) for i in range(1, num_bookmarks + 1)]
    task = create_scanning_task(
        scan_mode="bookmarks",
        bookmarks=bookmarks,
        sgn_level=sgn_level,
        wait=True,
        record=record,
        log=True,
        frequency_modulation=modulation,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = signal_level

    assert scanning._scan_active is True
    scanning._bookmarks(task=task)
    assert scanning._scan_active is False

    assert scanning._rigctl.set_frequency.call_count == num_bookmarks
    assert scanning._rigctl.set_mode.call_count == num_bookmarks
    assert scanning._log.write.call_count == num_bookmarks
    # wait=True doubles the signal checks
    assert scanning._rigctl.get_level.call_count == scanning._SIGNAL_CHECKS * num_bookmarks * 2

    if record:
        assert scanning._rigctl.start_recording.call_count == num_bookmarks


@pytest.mark.parametrize(
    "exception_type, scan_mode, wait, record",
    [
        (OSError, "bookmarks", True, True),
        (OSError, "bookmarks", False, True),
        (TimeoutError, "bookmarks", True, True),
        (TimeoutError, "bookmarks", True, False),
        (ConnectionError, "bookmarks", True, True),
        (OSError, "bookmarks", False, False),
    ],
)
def test_scanning_bookmark_exceptions_scenarios(
    scanning, create_bookmark, create_scanning_task, exception_type, scan_mode, wait, record
):
    """Test exception handling during bookmark scanning."""
    bookmarks = [create_bookmark(), create_bookmark(frequency=2000)]
    task = create_scanning_task(
        scan_mode=scan_mode,
        bookmarks=bookmarks,
        sgn_level=250,
        wait=wait,
        record=record,
        log=True,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_frequency.side_effect = exception_type

    scanning.scan(task=task)
    assert scanning._scan_active is False


@pytest.mark.parametrize(
    "range_min, range_max, interval, sgn_level, signal_level, wait, record, auto_bookmark, modulation",
    [
        (1000, 3000, 1, 250, 25000, True, True, True, "FM"),
        (1000, 5000, 1, 250, 25000, True, True, False, "FM"),
        (5000, 10000, 2, 200, 30000, True, False, True, "AM"),
        (10000, 15000, 1, 300, 35000, False, True, True, "USB"),
        (1000, 2000, 1, 100, 20000, True, True, True, "LSB"),
        (50000, 55000, 1, 500, 40000, True, True, False, "WFM"),
    ],
)
def test_scanning_frequency_wait_scenarios(
    scanning,
    create_bookmark,
    create_scanning_task,
    range_min,
    range_max,
    interval,
    sgn_level,
    signal_level,
    wait,
    record,
    auto_bookmark,
    modulation,
):
    """Test frequency scanning with various parameter combinations."""
    bookmarks = [create_bookmark(), create_bookmark(frequency=2000)]
    task = create_scanning_task(
        scan_mode="frequency",
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        sgn_level=sgn_level,
        wait=wait,
        record=record,
        auto_bookmark=auto_bookmark,
        log=True,
        bookmarks=bookmarks,
        frequency_modulation=modulation,
    )

    scanning._scan_queue.send_event_update(event=("tests", "tests"))
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = signal_level
    scanning._rigctl.get_mode.return_value = modulation

    assert scanning._scan_active is True
    scanning._frequency(task=task)
    assert scanning._scan_active is False

    expected_frequencies = max(1, (range_max - range_min) // 1000)
    assert scanning._rigctl.set_frequency.call_count == expected_frequencies
    assert scanning._rigctl.set_mode.call_count == expected_frequencies
    assert scanning._log.write.call_count == expected_frequencies


@pytest.mark.parametrize(
    "passes, range_min, range_max, interval",
    [
        (1, 1000, 2000, 1),
        (2, 1000, 3000, 1),
        (3, 5000, 10000, 2),
        (1, 10000, 20000, 5),
        (2, 1000, 5000, 2),
    ],
)
def test_scanning_multiple_passes(scanning, create_scanning_task, passes, range_min, range_max, interval):
    """Test scanning with multiple passes."""
    task = create_scanning_task(
        scan_mode="frequency",
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        passes=passes,
        log=True,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 1000

    scanning.scan(task=task)
    assert scanning._scan_active is False


@pytest.mark.parametrize(
    "modulation, sgn_level, expected_calls",
    [
        ("FM", 100, True),
        ("AM", 200, True),
        ("USB", 300, True),
        ("LSB", 400, True),
        ("CW", 500, True),
        ("WFM", 600, True),
    ],
)
def test_scanning_different_modulations(
    scanning, create_bookmark, create_scanning_task, modulation, sgn_level, expected_calls
):
    """Test scanning with different modulation types."""
    bookmarks = [create_bookmark(modulation=modulation)]
    task = create_scanning_task(
        scan_mode="bookmarks",
        bookmarks=bookmarks,
        frequency_modulation=modulation,
        sgn_level=sgn_level,
        log=True,
    )

    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = sgn_level + 1000

    scanning._bookmarks(task=task)

    if expected_calls:
        assert scanning._rigctl.set_mode.call_count > 0
        assert scanning._rigctl.set_frequency.call_count > 0


@pytest.mark.parametrize(
    "event_name, event_value, expected_processed, expected_range_min",
    [
        ("txt_range_min", "100", True, 100000),
        ("txt_range_max", "200", True, None),
        ("ckb_wait", True, True, None),
        ("invalid_event", "x", False, None),
    ],
)
def test_scanning_process_queue_events(
    scanning, create_scanning_task, event_name, event_value, expected_processed, expected_range_min, monkeypatch
):
    task = create_scanning_task(delay=0)

    # stub messenger to return one event then stop
    class FakeMessenger:
        calls = 0

        def update_queued(self):
            self.calls += 1
            return self.calls == 1

        def get_event_update(self):
            return (event_name, event_value)

    scanning._scan_queue = FakeMessenger()
    processed = scanning._process_queue(task)
    assert processed is expected_processed
    if expected_range_min is not None:
        assert task.range_min == expected_range_min


@pytest.mark.parametrize(
    "freq_exception, mode_exception",
    [
        (ValueError("bad freq"), None),
        (OSError("comm"), None),
        (TimeoutError("timeout"), None),
        (None, ValueError("bad mode")),
        (None, OSError("comm")),
        (None, TimeoutError("timeout")),
    ],
)
def test_scanning_channel_tune_exceptions(scanning, freq_exception, mode_exception):
    scanning._rigctl = create_autospec(RigCtl)
    if freq_exception:
        scanning._rigctl.set_frequency.side_effect = freq_exception
    else:
        scanning._rigctl.set_frequency.side_effect = None
        scanning._rigctl.set_mode.side_effect = mode_exception
    with pytest.raises((ValueError, OSError, TimeoutError)):
        scanning._channel_tune(Channel(input_frequency=1234, modulation="FM"))


def test_scanning_autobookmark_branches(scanning, create_scanning_task):
    task = create_scanning_task(auto_bookmark=True)
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_mode.return_value = "FM"
    # branch: no prev level -> store
    scanning._autobookmark(level=100, freq=1000, task=task)
    assert scanning._prev_level == 100 and scanning._prev_freq == 1000
    # branch: lower/equal level -> append and erase
    scanning._autobookmark(level=50, freq=1200, task=task)
    assert len(task.new_bookmarks_list) == 1
    assert scanning._prev_level == 0 and scanning._prev_freq == 0
    # branch: greater level -> store (parameters intentionally swapped in implementation)
    scanning._autobookmark(level=200, freq=1300, task=task)
    assert scanning._hold_bookmark is True


@pytest.mark.parametrize(
    "initial_passes, expected_active, expected_result",
    [
        (2, True, 1),
        (1, False, 0),
        (0, False, 0),
    ],
)
def test_scanning_pass_count_update(scanning, initial_passes, expected_active, expected_result):
    scanning._scan_active = True
    out = scanning._pass_count_update(pass_count=initial_passes)
    assert out == expected_result
    assert scanning._scan_active is expected_active


@pytest.mark.parametrize(
    "dbfs, expected_sgn",
    [
        (0, 0),
        (5, 50),
        (10, 100),
    ],
)
def test_scanning_dbfs_to_sgn(dbfs, expected_sgn):
    assert Scanning._dbfs_to_sgn(dbfs) == expected_sgn


@pytest.mark.parametrize(
    "levels, expected",
    [
        ([0, 0], False),
        ([1000, 0], True),
    ],
)
def test_scanning_signal_check(scanning, levels, expected):
    # rig mock cycles through provided levels
    class RigMock:
        def __init__(self, vals):
            self.vals = vals
            self.i = 0

        def get_level(self):
            v = self.vals[min(self.i, len(self.vals) - 1)]
            self.i += 1
            return v

    rig = RigMock(levels)
    assert scanning._signal_check(sgn_level=100, rig=rig) is expected


def test_scanning_create_new_bookmark_uses_mode(scanning):
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_mode.return_value = "USB"
    bm = scanning._create_new_bookmark(1234)
    assert bm.channel.modulation == "USB"


def test_scanning_erase_prev_bookmark(scanning):
    scanning._store_prev_bookmark(level=10, freq=1000)
    assert scanning._prev_level == 10 and scanning._prev_freq == 1000
    scanning._erase_prev_bookmark()
    assert scanning._prev_level == 0 and scanning._prev_freq == 0


@pytest.mark.parametrize(
    "delay, events",
    [
        (0, []),
        (2, [("txt_delay", 1), ("txt_interval", 2)]),
    ],
)
def test_scanning_queue_sleep_processes_events(scanning, create_scanning_task, delay, events):
    task = create_scanning_task(delay=delay)

    class MQ:
        def __init__(self, evs):
            self.evs = list(evs)

        def update_queued(self):
            return len(self.evs) > 0

        def get_event_update(self):
            return self.evs.pop(0)

    scanning._scan_queue = MQ(events)
    scanning._queue_sleep(task)
    # when events present, attributes updated accordingly
    if delay == 2:
        assert task.interval == 2


def test_scanning_channel_tune_success_path(scanning):
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.set_frequency.side_effect = None
    scanning._rigctl.set_mode.side_effect = None
    # Should not raise and should call both setters
    scanning._channel_tune(Channel(input_frequency=1234, modulation="FM"))
    assert scanning._rigctl.set_frequency.call_count == 1
    assert scanning._rigctl.set_mode.call_count == 1


def test_scanning_process_queue_invalid_break(scanning, create_scanning_task):
    """Ensure invalid event triggers warning and breaks without processing anything (hits lines 272-275)."""
    task = create_scanning_task(delay=0)

    class FakeMessenger:
        def __init__(self):
            self.calls = 0

        def update_queued(self):
            # Return True twice to exercise loop and break
            self.calls += 1
            return self.calls <= 2

        def get_event_update(self):
            # First invalid, then would-be valid (won't be reached due to break)
            return ("bad_event", "ignored")

    scanning._scan_queue = FakeMessenger()
    processed = scanning._process_queue(task)
    assert processed is False


@pytest.mark.parametrize("levels", [[500, 0], [1000, 500], [2000, 0]])
def test_scanning_signal_check_true_branch(scanning, levels):
    class RigMock:
        def __init__(self, vals):
            self.vals = vals
            self.i = 0

        def get_level(self):
            v = self.vals[min(self.i, len(self.vals) - 1)]
            self.i += 1
            return v

    rig = RigMock(levels)
    assert scanning._signal_check(sgn_level=50, rig=rig) is True


@pytest.mark.parametrize(
    "scan_mode, expect_called",
    [
        ("bookmarks", True),
        ("frequency", True),
    ],
)
def test_scanning_scan_dispatch_modes(scanning, create_scanning_task, scan_mode, expect_called):
    """Test scan dispatch uses the private dispatch map correctly."""
    # speed up by disabling sleep
    scanning._sleep = lambda *args, **kwargs: None
    task = create_scanning_task(scan_mode=scan_mode, log=False)

    # Spy wrappers to detect calls
    called = {"bookmarks": 0, "frequency": 0}

    def _wrap(fn_name):
        def _inner(t):
            called[fn_name] += 1
            return t

        return _inner

    # monkeypatch private dispatch entries
    scanning._dispatch["bookmarks"] = _wrap("bookmarks")
    scanning._dispatch["frequency"] = _wrap("frequency")

    scanning.scan(task)

    if scan_mode == "bookmarks":
        assert called["bookmarks"] == 1 and called["frequency"] == 0
    elif scan_mode == "frequency":
        assert called["frequency"] == 1 and called["bookmarks"] == 0


def test_scanning_scan_dispatch_unknown_mode(scanning, create_scanning_task):
    """Test scan with unknown mode logs warning and doesn't call any handler."""
    # speed up by disabling sleep
    scanning._sleep = lambda *args, **kwargs: None
    # Create a valid task first
    task = create_scanning_task(scan_mode="frequency", log=False)
    # Then manually override to unknown mode (bypassing validation)
    task.scan_mode = "unknown"

    # Spy wrappers to detect calls
    called = {"bookmarks": 0, "frequency": 0}

    def _wrap(fn_name):
        def _inner(t):
            called[fn_name] += 1
            return t

        return _inner

    # monkeypatch private dispatch entries
    scanning._dispatch["bookmarks"] = _wrap("bookmarks")
    scanning._dispatch["frequency"] = _wrap("frequency")

    scanning.scan(task)

    # unknown mode should not call any handler
    assert called["bookmarks"] == 0 and called["frequency"] == 0

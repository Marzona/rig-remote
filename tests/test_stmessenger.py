import os
from pathlib import Path

import pytest
from rig_remote.stmessenger import STMessenger, encode_bool
from mock import MagicMock
from rig_remote.queue_comms import QueueComms


@pytest.mark.parametrize(
    "event, should_raise",
    [
        ("tests", True),
        ([1, 2, 3], True),
        (("test_event",), True),
        ((1, 2), True),
        (("event", 1), True),
        (("event", True), True),
        (("event1", "event2"), False),
    ],
)
def test_stmessenger_send_event_update_validation(event, should_raise):
    stm = STMessenger(queue_comms=QueueComms())
    if should_raise:
        with pytest.raises(ValueError):
            stm.send_event_update(event)
    else:
        assert stm.send_event_update(event) is None


@pytest.mark.parametrize(
    "mock_return, expected_result",
    [
        (None, None),
        ("not_a_tuple", None),
        (("only_one_element",), None),
        (("param", "value"), ("param", "value")),
        (("txt_delay", "5"), ("txt_delay", "5")),
    ],
)
def test_stmessenger_get_event_update_exception(mock_return, expected_result):
    stm = STMessenger(queue_comms=QueueComms())
    if mock_return is Exception:
        stm.queue_comms.get_from_child = MagicMock(side_effect=Exception)
    else:
        stm.queue_comms.get_from_child = MagicMock()
        stm.queue_comms.get_from_child.return_value = mock_return
    assert stm.get_event_update() == expected_result


def test_stmessenger_update_queued():
    stm = STMessenger(queue_comms=QueueComms())
    event = ("test_event", "value")
    stm.send_event_update(event=event)
    assert stm.queue_comms.queued_for_child()
    assert stm.update_queued()


@pytest.mark.parametrize(
    "notify_first, expected_result",
    [
        (False, False),
        (True, True),
    ],
)
def test_stmessenger_check_end_of_scan(notify_first, expected_result):
    stm = STMessenger(queue_comms=QueueComms())
    if notify_first:
        stm.notify_end_of_scan()
    assert stm.check_end_of_scan() is expected_result


@pytest.mark.parametrize(
    "signal, expected_result",
    [
        (STMessenger.END_OF_SCAN_SIGNAL, True),
        (("non_end_signal", "value"), False),
        (None, False),
    ],
)
def test_stmessenger_check_end_of_scan_with_various_signals(signal, expected_result):
    stm = STMessenger(queue_comms=QueueComms())
    if signal is not None:
        stm.queue_comms.signal_parent(signal)
    assert stm.check_end_of_scan() is expected_result


@pytest.mark.parametrize(
    "signal, expected_result",
    [
        (STMessenger.END_OF_SCAN_SYNC, True),
        (("other_signal", "value"), False),
        (None, False),
    ],
)
def test_stmessenger_check_end_of_sync_with_various_signals(signal, expected_result):
    stm = STMessenger(queue_comms=QueueComms())
    if signal is not None:
        stm.queue_comms.signal_parent(signal)
    assert stm.check_end_of_sync() is expected_result


@pytest.mark.parametrize("value, expected", [(True, "true"), (False, "false")])
def test_encode_bool_exact_lowercase(value, expected):
    assert encode_bool(value) == expected


def test_send_event_update_rejects_int_at_type_level(tmp_path):
    import subprocess
    import sys

    snippet = tmp_path / "snip.py"
    snippet.write_text(
        "from rig_remote.stmessenger import STMessenger\n"
        "from rig_remote.queue_comms import QueueComms\n"
        "STMessenger(QueueComms()).send_event_update((\"x\", 1))\n"
    )
    res = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--python-executable", sys.executable, str(snippet)],
        capture_output=True, text=True, cwd=str(Path(__file__).parent.parent),
        env={**os.environ, "MYPYPATH": "src"},
    )
    assert res.returncode != 0
    assert "arg-type" in res.stdout

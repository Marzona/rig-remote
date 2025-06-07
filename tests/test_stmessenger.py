import pytest
from rig_remote.stmessenger import STMessenger
from mock import MagicMock
from rig_remote.queue_comms import QueueComms

fake_event_list = [("tests"), ([1, 2, 3])]


@pytest.mark.parametrize("fake_event", fake_event_list)
def test_stmessenger_wrong_event_update(fake_event):
    fake = fake_event
    stm = STMessenger(queuecomms=QueueComms())
    with pytest.raises(ValueError):
        stm.send_event_update(fake)


def test_stmessenger_good_event_update():
    fake = (1, 2)
    stm = STMessenger(queuecomms=QueueComms())
    assert stm.send_event_update(fake) is None


def test_stmessenger_end_of_scan1():
    stm = STMessenger(queuecomms=QueueComms())
    assert not stm.check_end_of_scan()


def test_stmessenger_end_of_scan2():
    stm = STMessenger(queuecomms=QueueComms())
    stm.notify_end_of_scan()
    assert stm.check_end_of_scan()


def test_stmessenger_empty_get_event_update():
    stm = STMessenger(queuecomms=QueueComms())
    stm.mqueue.get_from_child = MagicMock()
    stm.mqueue.get_from_child.return_value = None
    assert stm.get_event_update() is None


def test_stmessenger_error_get_event_update():
    stm = STMessenger(queuecomms=QueueComms())
    stm.mqueue.get_from_child = MagicMock(side_effect=Exception)
    assert stm.get_event_update() == ('', '')


def test_stmessenger_send_event_update():
    stm = STMessenger(queuecomms=QueueComms())
    event_list = (
        "test_event",
        "test_event2",
    )
    stm.send_event_update(event_list=event_list)
    assert stm.mqueue.child_queue.qsize() == 1

    event_list2 = ("test_event",)
    with pytest.raises(ValueError):
        stm.send_event_update(event_list=event_list2)
        assert stm.mqueue.child_queue.qsize() == 1


def test_stmessenger_update_queued():
    stm = STMessenger(queuecomms=QueueComms())
    event_list = (
        "test_event",
        "test_event2",
    )
    stm.send_event_update(event_list=event_list)
    assert stm.mqueue.queued_for_child()
    assert stm.update_queued()
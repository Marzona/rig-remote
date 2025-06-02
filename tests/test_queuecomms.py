import pytest

from rig_remote.queue_comms import QueueComms
from queue import Full


def test_queuecomms_queued_for_parent():
    qc = QueueComms()
    qc.parent_queue.put("tests")
    assert qc.queued_for_parent()
    qc.parent_queue.get()
    assert not (qc.queued_for_parent())


def test_queuecomms_queued_for_child():
    qc = QueueComms()
    qc.child_queue.put("tests")
    assert qc.queued_for_child()
    qc.child_queue.get()
    assert not (qc.queued_for_child())


def test_queuecomms_get_from_parent1():
    qc = QueueComms()
    qc.parent_queue.put("2")
    assert qc.get_from_parent() == "2"


def test_queuecomms_get_from_parent2():
    qc = QueueComms()
    assert qc.get_from_parent() is None


def test_queuecomms_get_from_child1():
    qc = QueueComms()
    qc.child_queue.put("2")
    assert qc.get_from_child() == "2"


def test_queuecomms_get_from_child2():
    qc = QueueComms()
    assert qc.get_from_child() is None


def test_queuecomms_queue_max_size_parent():
    qc = QueueComms()
    for i in range(qc._QUEUE_MAX_SIZE):
        qc.send_to_parent(i)
    with pytest.raises(Full):
        qc.send_to_parent("overflow")


def test_queuecomms_queue_max_size_child1():
    qc = QueueComms()
    for i in range(qc._QUEUE_MAX_SIZE):
        qc.send_to_child(i)
    with pytest.raises(Full):
        qc.send_to_child("overflow")


def test_queuecomms_queue_value_error_child2():
    qc = QueueComms()
    with pytest.raises(ValueError):
        qc.signal_child("overflow")


def test_queuecomms_queue_max_size_child3():
    qc = QueueComms()
    for i in range(qc._QUEUE_MAX_SIZE):
        qc.signal_child(i)
    with pytest.raises(Full):
        qc.signal_child(1)


def test_queuecomms_queue_value_error_parent2():
    qc = QueueComms()
    with pytest.raises(ValueError):
        qc.signal_parent("overflow")


def test_queuecomms_queue_max_size_parent3():
    qc = QueueComms()
    for i in range(qc._QUEUE_MAX_SIZE):
        qc.signal_parent(i)
    with pytest.raises(Full):
        qc.signal_parent(1)

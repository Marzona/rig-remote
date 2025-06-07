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
    item ="('end_of_scan', '1')"
    qc.parent_queue.put(item=item)
    assert qc.get_from_parent() == ("end_of_scan", "1")


def test_queuecomms_get_from_parent2():
    qc = QueueComms()
    assert qc.get_from_parent() is None


def test_queuecomms_get_from_child1():
    qc = QueueComms()
    item = "('end_of_scan', '1')"
    qc.child_queue.put(item=item)
    assert qc.get_from_child() == ("end_of_scan", "1")


def test_queuecomms_get_from_child2():
    qc = QueueComms()
    assert qc.get_from_child() is None


def test_queuecomms_queue_value_error_parent2():
    qc = QueueComms()
    with pytest.raises(ValueError):
        qc.signal_parent("overflow")
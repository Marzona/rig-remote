import pytest

from rig_remote.queue_comms import QueueComms

from queue import Full


def test_queuecomms_signal_invalid_queue():
    """Test _signal with invalid queue type raises ValueError (lines 105-107)."""
    with pytest.raises(ValueError):
        QueueComms._signal("not_a_queue", ("signal", "value"))


def test_queuecomms_signal_invalid_signal_type():
    """Test _signal with invalid signal type raises ValueError (lines 105-107)."""
    qc = QueueComms()
    with pytest.raises(ValueError):
        QueueComms._signal(qc.parent_queue, "not_a_tuple")


def test_queuecomms_signal_parent_queue_full():
    """Test signal_parent when queue is full raises Full exception (lines 145-146)."""
    qc = QueueComms()
    # Fill the queue to max size
    for i in range(qc._QUEUE_MAX_SIZE):
        qc.parent_queue.put(f"signal_{i}", False)

    # Next put should raise Full
    with pytest.raises(Full):
        qc.signal_parent(("overflow", "error"))


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

@pytest.mark.parametrize(
    "invalid_signal",
    [
        "overflow",
        123,
        None,
        ["list", "signal"],
        {"dict": "signal"},
    ]
)
def test_queuecomms_signal_parent_invalid_type(invalid_signal):
    """Test signal_parent with non-tuple signal types raises ValueError (lines 105-107)."""
    qc = QueueComms()
    with pytest.raises(ValueError):
        qc.signal_parent(invalid_signal)


@pytest.mark.parametrize(
    "valid_signal",
    [
        ("overflow", "error"),
        ("underflow", "warning"),
        ("status", "ok"),
    ]
)
def test_queuecomms_signal_parent_valid(valid_signal):
    """Test signal_parent with valid 2-element tuple signal succeeds."""
    qc = QueueComms()
    qc.signal_parent(valid_signal)
    assert qc.parent_queue.qsize() == 1

#!/usr/bin/env python

# import modules
import pytest
from rig_remote.queue_comms import QueueComms
from rig_remote.constants import QUEUE_MAX_SIZE
from Queue import Queue, Empty, Full
def test_queued_for_parent1():
    qc=QueueComms()
    qc.parent_queue.put("2")
    qc.parent_queue.get()
    assert(qc.queued_for_parent() == False)

def test_queued_for_parent2():
    qc=QueueComms()
    qc.parent_queue.put("2")
    assert(qc.queued_for_parent() == True)

def test_get_from_parent1():
    qc=QueueComms()
    qc.parent_queue.put("2")
    assert(qc.get_from_parent() == "2")

def test_get_from_parent2():
    qc=QueueComms()
    assert(qc.get_from_parent() == None)

def test_get_from_child1():
    qc=QueueComms()
    qc.child_queue.put("2")
    assert(qc.get_from_child() == "2")

def test_get_from_child2():
    qc=QueueComms()
    assert(qc.get_from_child() == None)

def test_queued_for_child1():
    qc=QueueComms()
    qc.child_queue.put("2")
    qc.child_queue.get()
    assert(qc.queued_for_child() == False)

def test_queued_for_child2():
    qc=QueueComms()
    qc.child_queue.put("2")
    assert(qc.queued_for_child() == True)

def test_queue_max_size_parent():
    qc=QueueComms()
    for i in range(QUEUE_MAX_SIZE):
        qc.send_to_parent(i)
    with pytest.raises(Full):
        qc.send_to_parent("overflow")

def test_queue_max_size_child1():
    qc=QueueComms()
    for i in range(QUEUE_MAX_SIZE):
        qc.send_to_child(i)
    with pytest.raises(Full):
        qc.send_to_child("overflow")

def test_queue_value_error_child2():
    qc=QueueComms()
    with pytest.raises(ValueError):
        qc.signal_child("overflow")

def test_queue_max_size_child3():
    qc=QueueComms()
    for i in range(QUEUE_MAX_SIZE):
        qc.signal_child(i)
    with pytest.raises(Full):
        qc.signal_child(1)

def test_queue_value_error_parent2():
    qc=QueueComms()
    with pytest.raises(ValueError):
        qc.signal_parent("overflow")

def test_queue_max_size_parent3():
    qc=QueueComms()
    for i in range(QUEUE_MAX_SIZE):
        qc.signal_parent(i)
    with pytest.raises(Full):
        qc.signal_parent(1)

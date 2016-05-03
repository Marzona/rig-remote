#!/usr/bin/env python

# import modules
import pytest
from rig_remote.stmessenger import STMessenger

fake_event_list=[("test"), ([1,2,3])]
@pytest.mark.parametrize("fake_event", fake_event_list)
def test_wrong_event_update(fake_event):
    fake=fake_event
    stm = STMessenger()
    with pytest.raises(ValueError):
        stm.send_event_update(fake)

def test_good_event_update():
    fake=(1,2)
    stm = STMessenger()
    assert (stm.send_event_update(fake) == None)

#class fake_queue_comms():
#    def get_from_child():
#        raise Exception

#def tests_wrong_get_event_update(fake_queue_comms):
#    stm = STMessenger
#    stm.mqueue = fake_queue_comms
#    assert (stm.send_event_update(fake) == [])


def test_end_of_scan1():
    stm = STMessenger()

    assert (stm.check_end_of_scan() == False)

def test_end_of_scan2():
    stm = STMessenger()
    stm.notify_end_of_scan()
    assert (stm.check_end_of_scan() == True)



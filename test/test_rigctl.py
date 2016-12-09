#!/usr/bin/env python

# import modules
import pytest
import socket
from rig_remote.rigctl import RigCtl
from rig_remote.constants import (
                                 DEFAULT_CONFIG,
                                 ALLOWED_VFO_COMMANDS,
                                 ALLOWED_SPLIT_MODES,
                                 RESET_CMD_DICT,
                                 )

testdata = [("127.0.0.1", "80"), ("test", "80"), ("127.0.0.1","test"), ("test", "test")]
testdata2 = [("F 100000"), ("M 100000")]

@pytest.fixture
def fake_target():
    fake_target= {}
    fake_target["hostname"] = "127.0.0.1"
    fake_target["port"] = 80
    fake_target["rig_number"] = 1
    return fake_target

@pytest.mark.parametrize("hostname, port", testdata)
def test_set_connection_refused(hostname, port, fake_target):
    DEFAULT_CONFIG["hostname"] = hostname
    DEFAULT_CONFIG["port"] = port
    rigctl = RigCtl(fake_target)
    with pytest.raises(socket.error):
        rigctl.set_frequency("1000000")

@pytest.mark.parametrize("hostname, port", testdata)
def test_get_connection_refused(hostname, port, fake_target):
    DEFAULT_CONFIG["hostname"] = hostname
    DEFAULT_CONFIG["port"] = port
    rigctl = RigCtl(fake_target)
    with pytest.raises(socket.error):
        rigctl.get_frequency()

def test_set_frequency(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_frequency("test")

def test_set_mode(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_mode(5)

def test_rig_reset(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.rig_reset("testreset")

def test_set_antenna(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_antenna("testreset")

def test_xit(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_xit(22)

def test_vfo_1(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_vfo(22)

def test_vfo_2(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_vfo("testvfo")

def test_split_mode_1(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_split_mode(22)

def test_split_mode_2(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_split_mode("testvfo")

def test_split_freq(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_split_freq("testvfo")

def test_rit(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_rit("testrit")

def test_parm_1(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_parm(22)

def test_parm_2(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_parm("testparm")

def test_mode_1(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_mode(22)

def test_mode_2(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_mode("testmode")

def test_func_1(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_func(22)

def test_func_2(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_func("testvfo")

def test_antenna(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_antenna("testparm")

def test_rig_reset(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_antenna("testparam")

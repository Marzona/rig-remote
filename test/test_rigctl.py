#!/usr/bin/env python

# import modules
import pytest
import socket
import telnetlib
from mock import patch, MagicMock
from rig_remote.rigctl import RigCtl
from rig_remote.constants import (
                                  DEFAULT_CONFIG,
                                  ALLOWED_VFO_COMMANDS,
                                  ALLOWED_SPLIT_MODES,
                                  RESET_CMD_DICT,
                                 )

testdata = [("127.0.0.1", "80"),
            ("test", "80"),
            ("127.0.0.1","test"),
            ("test", "test")]

@pytest.fixture
def fake_target():
    fake_target= {}
    fake_target["hostname"] = "127.0.0.1"
    fake_target["port"] = 80
    fake_target["rig_number"] = 1
    return fake_target

def test_rig_control():
    with pytest.raises(TypeError):
        rigctl = RigCtl("test")

@pytest.mark.parametrize("hostname, port", testdata)
def test_set_frequency(hostname, port, fake_target):
    DEFAULT_CONFIG["hostname"] = "127.0.0.1"
    DEFAULT_CONFIG["port"] = "80"
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl.set_frequency("1000000")
    rigctl._request.assert_called_once_with('F 1000000', None)

def test_request_timeout(fake_target):
    telnetlib.Telnet = MagicMock(side_effect=socket.timeout)
    rigctl = RigCtl(fake_target)
    with pytest.raises(socket.timeout):
        rigctl.get_frequency()

def test_request_socket_error(fake_target):
    telnetlib.Telnet = MagicMock(side_effect=socket.error)
    rigctl = RigCtl(fake_target)
    with pytest.raises(socket.error):
        rigctl.get_frequency()

def test_get_frequency(fake_target):
    DEFAULT_CONFIG["hostname"] = "127.0.0.1"
    DEFAULT_CONFIG["port"] = "80"
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "f"
    rigctl.get_frequency()
    rigctl._request == "f"

def test_get_frequency_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_frequency()

def test_get_level(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_level() == "22")

def test_get_level_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_level()

def test_set_bad_frequency(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_frequency("test")

def test_set_bad_mode(fake_target):
    rigctl = RigCtl(fake_target)
    with pytest.raises(ValueError):
        rigctl.set_mode(5)

def test_get_mode(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "m"
    assert(rigctl.get_mode() == "m")

def test_get_mode_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_mode()

def test_get_split_mode(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "m"
    assert(rigctl.get_split_mode() == "m")

def test_get_split_mode_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_split_mode()

def test_get_vfo_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_vfo()

def test_get_vfo(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_vfo() == "22")

def test_get_rit_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_rit()

def test_get_rit(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_rit() == "22")

def test_get_xit_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_xit()

def test_get_xit(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_xit() == "22")

def test_get_split_freq_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    with pytest.raises(ValueError):
        rigctl.get_split_freq()

def test_get_split_freq(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    assert(rigctl.get_split_freq() == 22)

def test_get_func_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_func()

def test_get_func(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_func() == "22")

def test_get_parm_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    with pytest.raises(ValueError):
        rigctl.get_parm()

def test_get_parm(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    assert(rigctl.get_parm() == "22")

def test_get_antenna_error(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = "22"
    with pytest.raises(ValueError):
        rigctl.get_antenna()

def test_get_antenna(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl._request.return_value = 22
    assert(rigctl.get_antenna() == 22)

def test_set_mode(fake_target):
    rigctl = RigCtl(fake_target)
    rigctl._request = MagicMock()
    rigctl.set_mode("AM")
    rigctl._request.assert_called_once_with('M AM', None)

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

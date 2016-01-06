#!/usr/bin/env python

# import modules
import pytest
import socket
from modules.rigctl import RigCtl
from modules.constants import DEFAULT_CONFIG

testdata = [("test", "80"), ("127.0.0.1","test"), ("test", "test")]
testdata2 = [("F 100000"), ("M 100000")]

@pytest.mark.parametrize("hostname, port", testdata)
def test_set_connection_refused(hostname, port):
    DEFAULT_CONFIG["hostname"] = hostname
    DEFAULT_CONFIG["port"] = port
    rigctl = RigCtl()
    with pytest.raises(socket.error):
        rigctl.set_frequency("1000000")

@pytest.mark.parametrize("hostname, port", testdata)
def test_get_connection_refused(hostname, port):
    DEFAULT_CONFIG["hostname"] = hostname
    DEFAULT_CONFIG["port"] = port
    rigctl = RigCtl()
    with pytest.raises(socket.error):
        rigctl.get_frequency()

#@pytest.mark.parametrize("cmd", testdata2)
#def test_request(hostname, port):
#    DEFAULT_CONFIG["hostname"] = "test"
#    DEFAULT_CONFIG["port"] = "test"
#    rigctl = RigCtl()
#    with pytest.raises(socket.error):
#        rigctl._request("F 10000")

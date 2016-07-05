#!/usr/bin/env python
import pytest
from rig_remote.utility import (
                                this_file_exists,
                                is_valid_port,
                                is_valid_hostname,
                                )

def test_this_file_exist():
    assert(None == this_file_exists("/nonexisting"))

def test_is_valid_port_1():
    with pytest.raises(ValueError):
        is_valid_port("test")

def test_is_valid_port_2():
    with pytest.raises(ValueError):
        is_valid_port(1000)

def test_is_valid_hostname():
    with pytest.raises(ValueError):
        is_valid_hostname("")

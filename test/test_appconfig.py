#!/usr/bin/env python

# import modules
import pytest
import os
from rig_remote.app_config import AppConfig

def test_app_config1():
    ac = AppConfig("")
    assert (ac.default_config_file == ".rig-remote/rig-remote.conf")


def test_app_config2():
    ac = AppConfig("test")
    assert (ac.config_file == "test")

def test_app_config3():
    ac = AppConfig("")
    assert (ac.config_file == os.path.join(os.path.expanduser('~'),".rig-remote/rig-remote.conf"))

def test_app_config4():
    ac = AppConfig("/tmp/test")
    ac.read_conf()
    assert(len(ac.config) == 16)

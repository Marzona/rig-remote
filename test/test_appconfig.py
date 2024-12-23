#!/usr/bin/env python

from rig_remote.app_config import AppConfig
from rig_remote.constants import DEFAULT_CONFIG


def test_app_config2():
    ac = AppConfig("test")
    assert ac.config_file == "test"


def test_app_config4():
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    assert len(ac.config) == 19


def test_app_config5():
    ac = AppConfig("")
    assert isinstance(ac.config, dict) == True


def test_app_config8():
    ac = AppConfig(DEFAULT_CONFIG)
    assert ac.config == {}


def test_app_config9():
    ac = AppConfig("./test/test_files/test-config.file")
    ac.read_conf()
    assert ac.config["bookmark_filename"] == "./test/test-bookmarks.csv"


def test_app_config6():
    ac = AppConfig(DEFAULT_CONFIG)
    assert ac.config_file["bookmark_filename"] is None

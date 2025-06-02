import os
from pathlib import Path
from unittest.mock import patch, mock_open
from rig_remote.app_config import AppConfig
import pytest
import tkinter as tk
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.ui import RigRemote

def test_app_config_init():
    ac = AppConfig(config_file=os.path.join(Path(__file__).parent,"test_files/test-config.file"))
    assert ac.config_file == os.path.join(Path(__file__).parent,"test_files/test-config.file")


@pytest.mark.parametrize(
    "config_file",
    [
        os.path.join(Path(__file__).parent,"test_files/test-config.file"),
        "",
    ],
)
def test_app_config_read(config_file):
    ac = AppConfig(config_file=config_file)
    ac.read_conf()
    assert len(ac.config) == 19
    assert isinstance(ac.config, dict)


@pytest.mark.parametrize(
    "config_file",
    [
        os.path.join(Path(__file__).parent,"test_files/test-config-missing-header.file"),
    ],
)
def test_app_config_read_error(config_file):
    ac = AppConfig(config_file=config_file)
    with pytest.raises(SystemExit):
        ac.read_conf()

def test_app_config_write_conf_permission_error():
    """Test writing configuration with permission error."""
    config_file = os.path.join(Path(__file__).parent, "test_files/test-write-config.conf")
    ac = AppConfig(config_file=config_file)
    ac.config = {
        "hostname1": "192.168.1.1",
        "port1": "7356",
        "hostname2": "192.168.1.2",
        "port2": "7357",
        "interval": "2",
        "delay": "10",
        "passes": "1",
        "sgn_level": "-20",
        "range_min": "25,000",
        "range_max": "1900,000",
        "wait": "true",
        "record": "true",
        "log": "true",
        "always_on_top": "false",
        "save_exit": "true",
        "aggr_scan": "true",
        "auto_bookmark": "true",
        "log_filename": "tests.log",
        "bookmark_filename": "bookmarks.csv",
        "monitor_mode_loops": "true"
    }
    ac.rig_endpoints = [
        RigEndpoint(
            hostname=ac.config["hostname{}".format(instance_number)],
            port=int(ac.config["port{}".format(instance_number)]),
            number=instance_number,
        )
        for instance_number in (1, 2)
    ]
    with patch('builtins.open', side_effect=PermissionError), \
         pytest.raises(PermissionError):
            ac.store_conf(window=RigRemote(root=tk.Tk(), ac=ac))

def test_app_config_write_conf_os_error():
    """Test writing configuration with IO error."""
    config_file = os.path.join(Path(__file__).parent, "test_files/test-write-config.conf")
    ac = AppConfig(config_file=config_file)
    ac.config = {
        "hostname1": "192.168.1.1",
        "port1": "7356",
        "hostname2": "192.168.1.2",
        "port2": "7357",
        "interval": "2",
        "delay": "10",
        "passes": "1",
        "sgn_level": "-20",
        "range_min": "25,000",
        "range_max": "1900,000",
        "wait": "true",
        "record": "true",
        "log": "true",
        "always_on_top": "false",
        "save_exit": "true",
        "aggr_scan": "true",
        "auto_bookmark": "true",
        "log_filename": "tests.log",
        "bookmark_filename": "bookmarks.csv",
        "monitor_mode_loops": "true"
    }
    ac.rig_endpoints = [
        RigEndpoint(
            hostname=ac.config["hostname{}".format(instance_number)],
            port=int(ac.config["port{}".format(instance_number)]),
            number=instance_number,
        )
        for instance_number in (1, 2)
    ]
    with patch('builtins.open', side_effect=OSError), \
         pytest.raises(OSError):
            ac.store_conf(window=RigRemote(root=tk.Tk(), ac=ac))


def test_app_config_store_conf(tmp_path):
    """Test writing configuration to file."""
    # Setup tests config file path
    config_file = os.path.join(tmp_path, "tests-config.conf")
    ac = AppConfig(config_file=str(config_file))

    # Set tests configuration values
    ac.config = {
        "hostname1": "192.168.1.1",
        "port1": "7356",
        "hostname2": "192.168.1.2",
        "port2": "7357",
        "interval": "2",
        "delay": "10",
        "passes": "1",
        "sgn_level": "-20",
        "range_min": "25,000",
        "range_max": "1900,000",
        "wait": "true",
        "record": "true",
        "log": "true",
        "always_on_top": "false",
        "save_exit": "true",
        "aggr_scan": "true",
        "auto_bookmark": "true",
        "log_filename": "tests.log",
        "bookmark_filename": "bookmarks.csv",
        "monitor_mode_loops": "true"
    }
    ac.rig_endpoints = [
        RigEndpoint(
            hostname=ac.config["hostname{}".format(instance_number)],
            port=int(ac.config["port{}".format(instance_number)]),
            number=instance_number,
        )
        for instance_number in (1, 2)
    ]
    # Write configuration
    mock_file = mock_open()
    with patch('builtins.open', mock_file):
        ac.store_conf(window=RigRemote(root=tk.Tk(), ac=ac))

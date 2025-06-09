import os
from pathlib import Path
from unittest.mock import patch, mock_open
from rig_remote.app_config import AppConfig
import pytest
import tkinter as tk
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.ui import RigRemote
import configparser
import itertools

def test_app_config_init():
    ac = AppConfig(config_file=os.path.join(Path(__file__).parent,"test_files/test_config_files/test-config.file"))
    assert ac.config_file == os.path.join(Path(__file__).parent,"test_files/test_config_files/test-config.file")

#
# def test_load_all_config_files():
#     """Test AppConfig initialization with all config files and verify all directives."""
#     config_dir = os.path.join(Path(__file__).parent, "test_files/test_config_files/")
#
#     config_files = [
#         os.path.join(config_dir, f)
#         for f in os.listdir(config_dir)
#         if f.endswith(('.ini', '.file')) and 'missing-header' not in f
#     ]
#
#     for config_file in config_files:
#         ac = AppConfig(config_file=config_file)
#         ac.read_conf()
#
#         # Verify config object exists
#         assert ac.config is not None
#
#         # Verify Rig URI section values
#         assert 'hostname1' in ac.config
#         assert 'hostname2' in ac.config
#         assert 'port1' in ac.config
#         assert 'port2' in ac.config
#
#         # Verify Scanning section values
#         assert 'passes' in ac.config
#         assert 'aggr_scan' in ac.config
#         assert 'auto_bookmark' in ac.config
#         assert 'range_min' in ac.config
#         assert 'range_max' in ac.config
#         assert 'interval' in ac.config
#         assert 'delay' in ac.config
#         assert 'record' in ac.config
#         assert 'sgn_level' in ac.config
#         assert 'wait' in ac.config
#
#         # Verify Main section values
#         assert 'log_filename' in ac.config
#         assert 'save_exit' in ac.config
#         assert 'always_on_top' in ac.config
#         assert 'log' in ac.config
#         assert 'bookmark_filename' in ac.config
#
#         # Verify boolean values are properly formatted
#         bool_fields = ['wait', 'record', 'log', 'always_on_top',
#                        'save_exit', 'aggr_scan', 'auto_bookmark']
#         for field in bool_fields:
#             assert ac.config[field].lower() in ['true', 'false']
#
#         # Verify numeric values are valid
#         assert ac.config['passes'].isdigit()
#         assert ac.config['interval'].isdigit()
#         assert ac.config['delay'].isdigit()
#         assert ac.config['sgn_level'].strip('-').isdigit()
#
#         # Verify ports are valid numbers
#         assert ac.config['port1'].isdigit()
#         assert ac.config['port2'].isdigit()
#
#         # Verify hostnames are not empty
#         assert ac.config['hostname1']
#         assert ac.config['hostname2']
#
#         # Verify range values contain only digits and commas
#         assert all(c.isdigit() or c == ',' for c in ac.config['range_min'])
#         assert all(c.isdigit() or c == ',' for c in ac.config['range_max'])

def get_test_configs():
    """Helper function to get all test configuration files."""
    config_dir = os.path.join(Path(__file__).parent, "test_files/test_config_files/")
    return [
        os.path.join(config_dir, f)
        for f in os.listdir(config_dir)
        if f.endswith(('.ini', '.file')) and 'missing-header' not in f
    ]

@pytest.mark.parametrize("config_file", get_test_configs())
def test_load_all_config_files(config_file):
    """Test AppConfig initialization with all config files and verify all directives."""
    ac = AppConfig(config_file=config_file)
    ac.read_conf()

    # Verify config object exists
    assert ac.config is not None

    # Verify Rig URI section values
    assert 'hostname1' in ac.config
    assert 'hostname2' in ac.config
    assert 'port1' in ac.config
    assert 'port2' in ac.config

    # Verify Scanning section values
    assert 'passes' in ac.config
    assert 'aggr_scan' in ac.config
    assert 'auto_bookmark' in ac.config
    assert 'range_min' in ac.config
    assert 'range_max' in ac.config
    assert 'interval' in ac.config
    assert 'delay' in ac.config
    assert 'record' in ac.config
    assert 'sgn_level' in ac.config
    assert 'wait' in ac.config

    # Verify Main section values
    assert 'log_filename' in ac.config
    assert 'save_exit' in ac.config
    assert 'always_on_top' in ac.config
    assert 'log' in ac.config
    assert 'bookmark_filename' in ac.config

    # Verify boolean values are properly formatted
    bool_fields = ['wait', 'record', 'log', 'always_on_top',
                  'save_exit', 'aggr_scan', 'auto_bookmark']
    for field in bool_fields:
        assert ac.config[field].lower() in ['true', 'false']

    # Verify numeric values are valid
    assert ac.config['passes'].isdigit()
    assert ac.config['interval'].isdigit()
    assert ac.config['delay'].isdigit()
    assert ac.config['sgn_level'].strip('-').isdigit()

    # Verify ports are valid numbers
    assert ac.config['port1'].isdigit()
    assert ac.config['port2'].isdigit()

    # Verify hostnames are not empty
    assert ac.config['hostname1']
    assert ac.config['hostname2']

    # Verify range values contain only digits and commas
    assert all(c.isdigit() or c == ',' for c in ac.config['range_min'])
    assert all(c.isdigit() or c == ',' for c in ac.config['range_max'])


@pytest.mark.parametrize(
    "config_file",
    [
        os.path.join(Path(__file__).parent,"test_files/test_config_files/test-config-missing-header.file"),
    ],
)
def test_app_config_read_error(config_file):
    ac = AppConfig(config_file=config_file)
    with pytest.raises(SystemExit):
        ac.read_conf()

def test_app_config_write_conf_permission_error():
    """Test writing configuration with permission error."""
    config_file = os.path.join(Path(__file__).parent, "test_files/test_config_files/test-write-config.conf")
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
    config_file = os.path.join(Path(__file__).parent, "test_files/test_config_files/test-write-config.conf")
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

@pytest.fixture
def base_config():
    config = configparser.ConfigParser()
    config['Rig URI'] = {
        'hostname1': '127.0.0.1',
        'hostname2': '127.0.0.1',
        'port1': '7356',
        'port2': '7357'
    }
    config['Monitor'] = {}
    return config

@pytest.mark.parametrize(
    "passes, auto_bookmark, aggr_scan, delay, interval, save_exit, log, "
    "always_on_top, wait, record, sgn_level",
    [
        (p, ab, ags, d, i, se, l, aot, w, r, sl)
        for p in [1, 100]  # passes
        for ab in [True, False]  # auto_bookmark
        for ags in [True, False]  # aggr_scan
        for d in [1, 2]  # delay
        for i in range(1, 2)  # interval
        for se in [True, False]  # save_exit
        for l in [True, False]  # log
        for aot in [True, False]  # always_on_top
        for w in [True, False]  # wait
        for r in [True, False]  # record
        for sl in [ -50, 0, 50]  # sgn_level
    ]
)
def test_config_file_generation(tmp_path, base_config, passes, auto_bookmark,
                              aggr_scan, delay, interval, save_exit, log,
                              always_on_top, wait, record, sgn_level):
    """Test generation of config files with all parameter combinations."""
    config = base_config

    config['Scanning'] = {
        'passes': str(passes),
        'aggr_scan': str(aggr_scan).lower(),
        'auto_bookmark': str(auto_bookmark).lower(),
        'range_min': '24000',
        'range_max': '1800000',
        'interval': str(interval),
        'delay': str(delay),
        'record': str(record).lower(),
        'sgn_level': str(sgn_level),
        'wait': str(wait).lower()
    }

    config['Main'] = {
        'log_filename': 'none',
        'save_exit': str(save_exit).lower(),
        'always_on_top': str(always_on_top).lower(),
        'log': str(log).lower(),
        'bookmark_filename': './test/test_files/test-bookmarks.csv'
    }

    config_path = tmp_path / f'test-config-{passes}-{interval}-{delay}-{sgn_level}.ini'
    with open(config_path, 'w') as configfile:
        config.write(configfile)

    # Verify the config file was created and can be read back
    assert config_path.exists()
    loaded_config = configparser.ConfigParser()
    loaded_config.read(config_path)

    # Verify scanning section
    assert loaded_config['Scanning']['passes'] == str(passes)
    assert loaded_config['Scanning']['auto_bookmark'] == str(auto_bookmark).lower()
    assert loaded_config['Scanning']['aggr_scan'] == str(aggr_scan).lower()
    assert loaded_config['Scanning']['delay'] == str(delay)
    assert loaded_config['Scanning']['interval'] == str(interval)
    assert loaded_config['Scanning']['record'] == str(record).lower()
    assert loaded_config['Scanning']['sgn_level'] == str(sgn_level)
    assert loaded_config['Scanning']['wait'] == str(wait).lower()

    # Verify main section
    assert loaded_config['Main']['save_exit'] == str(save_exit).lower()
    assert loaded_config['Main']['log'] == str(log).lower()
    assert loaded_config['Main']['always_on_top'] == str(always_on_top).lower()
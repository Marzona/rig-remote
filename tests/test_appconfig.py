import os
from pathlib import Path
from unittest.mock import patch, mock_open
from rig_remote.app_config import AppConfig
import pytest

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
    ac.config = {'tests': 'value'}

    with patch('builtins.open', side_effect=PermissionError), \
         pytest.raises(PermissionError):
        ac.write_conf()

def test_app_config_write_conf_os_error():
    """Test writing configuration with IO error."""
    config_file = os.path.join(Path(__file__).parent, "test_files/test-write-config.conf")
    ac = AppConfig(config_file=config_file)
    ac.config = {'tests': 'value'}

    with patch('builtins.open', side_effect=OSError), \
         pytest.raises(OSError):
        ac.write_conf()


def test_app_config_write_confzzz(tmp_path):
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

    # Write configuration
    mock_file = mock_open()
    with patch('builtins.open', mock_file):
        ac.write_conf()

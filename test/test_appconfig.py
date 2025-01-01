from rig_remote.app_config import AppConfig
import pytest


def test_app_config_init():
    ac = AppConfig(config_file="./test/test_files/test-config.file")
    assert ac.config_file == "./test/test_files/test-config.file"


@pytest.mark.parametrize(
    "config_file",
    [
        "./test/test_files/test-config.file",
        "",
    ],
)
def test_app_config_read(config_file):
    ac = AppConfig(config_file=config_file)
    ac.read_conf()
    assert len(ac.config) == 19
    assert isinstance(ac.config, dict) == True


@pytest.mark.parametrize(
    "config_file",
    [
        "./test/test_files/test-config-missing-header.file",
    ],
)
def test_app_config_read_error(config_file):
    ac = AppConfig(config_file=config_file)
    with pytest.raises(SystemExit):
        ac.read_conf()

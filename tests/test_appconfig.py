import os
from pathlib import Path
from rig_remote.app_config import AppConfig
import pytest
import configparser
from rig_remote.constants import RIG_COUNT, CONFIG_SECTIONS
from unittest.mock import Mock, patch


def test_app_config_init():
    ac = AppConfig(config_file=os.path.join(Path(__file__).parent, "test_files/test_config_files/test-config.file"))
    assert ac.config_file == os.path.join(Path(__file__).parent, "test_files/test_config_files/test-config.file")


def get_test_configs():
    """Helper function to get all test configuration files."""
    config_dir = os.path.join(Path(__file__).parent, "test_files/test_config_files/")
    return [
        os.path.join(config_dir, f)
        for f in os.listdir(config_dir)
        if f.endswith((".ini", ".file")) and "missing-header" not in f
    ]


@pytest.mark.parametrize("config_file", get_test_configs())
def test_load_all_config_files(config_file):
    """Test AppConfig initialization with all config files and verify all directives."""
    ac = AppConfig(config_file=config_file)
    ac.read_conf()

    # Verify config object exists
    assert ac.config is not None

    # Verify Rig URI section values
    assert "hostname1" in ac.config
    assert "hostname2" in ac.config
    assert "port1" in ac.config
    assert "port2" in ac.config

    # Verify Scanning section values
    assert "passes" in ac.config
    assert "aggr_scan" in ac.config
    assert "auto_bookmark" in ac.config
    assert "range_min" in ac.config
    assert "range_max" in ac.config
    assert "interval" in ac.config
    assert "delay" in ac.config
    assert "record" in ac.config
    assert "sgn_level" in ac.config
    assert "wait" in ac.config

    # Verify Main section values
    assert "log_filename" in ac.config
    assert "save_exit" in ac.config
    assert "always_on_top" in ac.config
    assert "log" in ac.config
    assert "bookmark_filename" in ac.config

    # Verify boolean values are properly formatted
    bool_fields = ["wait", "record", "log", "always_on_top", "save_exit", "aggr_scan", "auto_bookmark"]
    for field in bool_fields:
        assert ac.config[field].lower() in ["true", "false"]

    # Verify numeric values are valid
    assert ac.config["passes"].isdigit()
    assert ac.config["interval"].isdigit()
    assert ac.config["delay"].isdigit()
    assert ac.config["sgn_level"].strip("-").isdigit()

    # Verify ports are valid numbers
    assert ac.config["port1"].isdigit()
    assert ac.config["port2"].isdigit()

    # Verify hostnames are not empty
    assert ac.config["hostname1"]
    assert ac.config["hostname2"]

    # Verify range values contain only digits and commas
    assert all(c.isdigit() or c == "," for c in ac.config["range_min"])
    assert all(c.isdigit() or c == "," for c in ac.config["range_max"])


@pytest.fixture
def base_config():
    config = configparser.ConfigParser()
    config["Rig URI"] = {"hostname1": "127.0.0.1", "hostname2": "127.0.0.1", "port1": "7356", "port2": "7357"}
    config["Monitor"] = {}
    return config


@pytest.mark.parametrize(
    "passes, auto_bookmark, aggr_scan, delay, interval, save_exit, log, always_on_top, wait, record, sgn_level",
    [
        (p, ab, ags, d, i, se, log, aot, w, r, sl)
        for p in [1, 100]  # passes
        for ab in [True, False]  # auto_bookmark
        for ags in [True, False]  # aggr_scan
        for d in [1, 2]  # delay
        for i in range(1, 2)  # interval
        for se in [True, False]  # save_exit
        for log in [True, False]  # log
        for aot in [True, False]  # always_on_top
        for w in [True, False]  # wait
        for r in [True, False]  # record
        for sl in [-50, 0, 50]  # sgn_level
    ],
)
def test_appconfig_config_file_generation(
    tmp_path,
    base_config,
    passes,
    auto_bookmark,
    aggr_scan,
    delay,
    interval,
    save_exit,
    log,
    always_on_top,
    wait,
    record,
    sgn_level,
):
    """Test generation of config files with all parameter combinations."""
    config = base_config

    config["Scanning"] = {
        "passes": str(passes),
        "aggr_scan": str(aggr_scan).lower(),
        "auto_bookmark": str(auto_bookmark).lower(),
        "range_min": "24000",
        "range_max": "1800000",
        "interval": str(interval),
        "delay": str(delay),
        "record": str(record).lower(),
        "sgn_level": str(sgn_level),
        "wait": str(wait).lower(),
    }

    config["Main"] = {
        "log_filename": "none",
        "save_exit": str(save_exit).lower(),
        "always_on_top": str(always_on_top).lower(),
        "log": str(log).lower(),
        "bookmark_filename": "./test/test_files/test-bookmarks.csv",
    }

    config_path = tmp_path / f"test-config-{passes}-{interval}-{delay}-{sgn_level}.ini"
    with open(config_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)

    # Verify the config file was created and can be read back
    assert config_path.exists()
    loaded_config = configparser.ConfigParser()
    loaded_config.read(config_path)

    # Verify scanning section
    assert loaded_config["Scanning"]["passes"] == str(passes)
    assert loaded_config["Scanning"]["auto_bookmark"] == str(auto_bookmark).lower()
    assert loaded_config["Scanning"]["aggr_scan"] == str(aggr_scan).lower()
    assert loaded_config["Scanning"]["delay"] == str(delay)
    assert loaded_config["Scanning"]["interval"] == str(interval)
    assert loaded_config["Scanning"]["record"] == str(record).lower()
    assert loaded_config["Scanning"]["sgn_level"] == str(sgn_level)
    assert loaded_config["Scanning"]["wait"] == str(wait).lower()

    # Verify main section
    assert loaded_config["Main"]["save_exit"] == str(save_exit).lower()
    assert loaded_config["Main"]["log"] == str(log).lower()
    assert loaded_config["Main"]["always_on_top"] == str(always_on_top).lower()


def test_appconfig_init_uses_default_when_no_config_file():
    """__init__ sets config to DEFAULT_CONFIG when config_file is empty."""
    ac = AppConfig(config_file="")
    assert ac.config == AppConfig.DEFAULT_CONFIG


def test_appconfig_read_conf_missing_section_triggers_exit(monkeypatch, tmp_path):
    """Simulate configparser.MissingSectionHeaderError during read -> SystemExit(1)."""
    cfg = tmp_path / "bad.ini"
    cfg.write_text("this-is-not-a-section\nkey=value\n")

    ac = AppConfig(config_file=str(cfg))

    def fake_read(self, filename):
        raise configparser.MissingSectionHeaderError(filename=str(cfg), line="missing header", lineno=1)

    monkeypatch.setattr(configparser.RawConfigParser, "read", fake_read)
    with pytest.raises(SystemExit) as excinfo:
        ac.read_conf()
    assert excinfo.value.code == 1


def test_appconfig_read_conf_no_file_uses_default_and_builds_endpoints(tmp_path):
    """When the config file is missing, DEFAULT_CONFIG is used and rig_endpoints are built."""
    cfg_path = tmp_path / "no-such-dir" / "missing.ini"
    ac = AppConfig(config_file=str(cfg_path))
    # ensure file does not exist
    if os.path.exists(str(cfg_path)):
        os.remove(str(cfg_path))

    ac.read_conf()
    assert ac.config == AppConfig.DEFAULT_CONFIG
    assert isinstance(ac.rig_endpoints, list)
    assert len(ac.rig_endpoints) == RIG_COUNT
    # verify endpoints have hostname and integer port
    for ep in ac.rig_endpoints:
        assert isinstance(ep.hostname, str)
        assert isinstance(ep.port, int)


def test_appconfig_write_conf_creates_file_and_sections(tmp_path):
    """_write_conf writes a config file containing the expected sections and keys."""
    out_dir = tmp_path / "outdir"
    cfg_path = out_dir / "test-config.ini"
    ac = AppConfig(config_file=str(cfg_path))

    # ensure writable string values (avoid None in DEFAULT_CONFIG for writing)
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    ac.config["monitor_mode_loops"] = "10"

    # call internal writer and verify file was created and contains expected sections
    ac._write_conf()
    assert cfg_path.exists()
    content = cfg_path.read_text()
    # verify all expected sections are present
    for section in CONFIG_SECTIONS:
        assert f"[{section}]" in content


def test_appconfig_write_conf_handles_makedirs_ioerror(tmp_path, monkeypatch):
    """If os.makedirs raises IOError, _write_conf should continue and still write when dir exists."""
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = existing_dir / "test-config.ini"
    ac = AppConfig(config_file=str(cfg_path))

    # ensure writable string values
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}

    # force os.makedirs to raise IOError (simulate race/permission issue)
    def raise_io_error(path, *args, **kwargs):
        raise IOError("simulated makedirs failure")

    monkeypatch.setattr(os, "makedirs", raise_io_error)

    # Because the directory already exists, _write_conf should still be able to open and write the file
    ac._write_conf()
    assert cfg_path.exists()


def test_appconfig_get_conf_populates_from_window():
    """_get_conf pulls values from a window-like object into ac.config."""

    class FakeWidget:
        def __init__(self, v):
            self._v = v

        def get(self):
            return self._v

        def get_str_val(self):
            return self._v

        def isChecked(self):
            return self._v is True

        def text(self):
            return self._v

    fake_params = {
        "txt_hostname1": FakeWidget("host1"),
        "txt_port1": FakeWidget("1111"),
        "txt_hostname2": FakeWidget("host2"),
        "txt_port2": FakeWidget("2222"),
        "txt_interval": FakeWidget("10"),
        "txt_delay": FakeWidget("3"),
        "txt_passes": FakeWidget("5"),
        "txt_sgn_level": FakeWidget("-20"),
        "txt_range_min": FakeWidget("24000"),
        "txt_range_max": FakeWidget("1800000"),
        "ckb_wait": FakeWidget(False),
        "ckb_record": FakeWidget(True),
        "ckb_log": FakeWidget(False),
        "ckb_auto_bookmark": FakeWidget(True),
    }

    window = type("W", (), {})()
    window.params = fake_params
    window.ckb_top = FakeWidget(True)
    window.ckb_save_exit = FakeWidget(False)
    window.bookmarks_file = "/tmp/bookmarks.csv"
    window.log_file = "/tmp/log.txt"

    ac = AppConfig(config_file="")
    ac._get_conf(window)

    assert ac.config["hostname1"] == "host1"
    assert ac.config["port1"] == "1111"
    assert ac.config["hostname2"] == "host2"
    assert ac.config["port2"] == "2222"
    assert ac.config["interval"] == "10"
    assert ac.config["delay"] == "3"
    assert ac.config["passes"] == "5"
    assert ac.config["sgn_level"] == "-20"
    assert ac.config["range_min"] == "24000"
    assert ac.config["range_max"] == "1800000"
    assert not ac.config["wait"]
    assert ac.config["record"]
    assert not ac.config["log"]
    assert ac.config["always_on_top"]
    assert not ac.config["save_exit"]
    assert ac.config["auto_bookmark"]
    assert ac.config["bookmark_filename"] == "/tmp/bookmarks.csv"
    assert ac.config["log_filename"] == "/tmp/log.txt"


def test_appconfig_read_conf_with_empty_config_file(tmp_path):
    """When config file exists but is empty (no sections), DEFAULT_CONFIG is used."""
    cfg_path = tmp_path / "empty.ini"
    cfg_path.write_text("")  # Empty file with no sections

    ac = AppConfig(config_file=str(cfg_path))
    ac.read_conf()

    # Should fall back to DEFAULT_CONFIG when no sections are found
    assert ac.config == AppConfig.DEFAULT_CONFIG
    assert isinstance(ac.rig_endpoints, list)
    assert len(ac.rig_endpoints) == RIG_COUNT


def test_appconfig_write_conf_includes_aggr_scan(tmp_path):
    """_write_conf correctly writes the aggr_scan key to the Scanning section."""
    cfg_path = tmp_path / "test-config.ini"
    ac = AppConfig(config_file=str(cfg_path))

    # Set up config with aggr_scan
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    ac.config["aggr_scan"] = "true"

    ac._write_conf()
    assert cfg_path.exists()

    # Read back and verify aggr_scan is in Scanning section
    loaded_config = configparser.ConfigParser()
    loaded_config.read(cfg_path)
    assert loaded_config["Scanning"]["aggr_scan"] == "true"


def test_appconfig_store_conf_calls_get_conf_and_write_conf():
    """store_conf calls _get_conf to populate config and _write_conf to save it."""

    # Create a mock window similar to the one in test_appconfig_get_conf_populates_from_window
    class FakeWidget:
        def __init__(self, v):
            self._v = v

        def get(self):
            return self._v

        def get_str_val(self):
            return self._v

        def isChecked(self):
            return self._v is False

        def text(self):
            return self._v

    fake_params = {
        "txt_hostname1": FakeWidget("host1"),
        "txt_port1": FakeWidget("1111"),
        "txt_hostname2": FakeWidget("host2"),
        "txt_port2": FakeWidget("2222"),
        "txt_interval": FakeWidget("10"),
        "txt_delay": FakeWidget("3"),
        "txt_passes": FakeWidget("5"),
        "txt_sgn_level": FakeWidget("-20"),
        "txt_range_min": FakeWidget("24000"),
        "txt_range_max": FakeWidget("1800000"),
        "ckb_wait": FakeWidget(False),
        "ckb_record": FakeWidget(True),
        "ckb_log": FakeWidget(False),
        "ckb_auto_bookmark": FakeWidget(True),
    }

    window = type("W", (), {})()
    window.params = fake_params
    window.ckb_top = FakeWidget(True)
    window.ckb_save_exit = FakeWidget(False)
    window.bookmarks_file = "/tmp/bookmarks.csv"
    window.log_file = "/tmp/log.txt"

    ac = AppConfig(config_file="")

    # Mock _write_conf to verify it's called
    with patch.object(ac, "_write_conf") as mock_write_conf:
        ac.store_conf(window)

        # Verify _write_conf was called
        mock_write_conf.assert_called_once()

        # Verify that _get_conf was called by checking config is populated
        assert ac.config["hostname1"] == "host1"
        assert ac.config["port1"] == "1111"
        assert ac.config["hostname2"] == "host2"
        assert ac.config["port2"] == "2222"
        assert ac.config["interval"] == "10"
        assert ac.config["delay"] == "3"
        assert ac.config["passes"] == "5"
        assert ac.config["sgn_level"] == "-20"
        assert ac.config["range_min"] == "24000"
        assert ac.config["range_max"] == "1800000"
        assert ac.config["wait"]
        assert not ac.config["record"]
        assert ac.config["log"]
        assert not ac.config["always_on_top"]
        assert ac.config["save_exit"]
        assert not ac.config["auto_bookmark"]
        assert ac.config["bookmark_filename"] == "/tmp/bookmarks.csv"
        assert ac.config["log_filename"] == "/tmp/log.txt"

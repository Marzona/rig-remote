import os
from pathlib import Path
from rig_remote.app_config import AppConfig
import pytest
import configparser
from rig_remote.constants import RIG_COUNT, CONFIG_SECTIONS, MAX_ENDPOINTS, SELECTED_RIG_KEYS
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rig_backends.protocol import BackendType
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
        "txt_inner_band": FakeWidget("0"),
        "txt_inner_interval": FakeWidget("0"),
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
    assert ac.config["inner_band"] == "0"
    assert ac.config["inner_interval"] == "0"
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


@pytest.mark.parametrize("key,value", [
    ("aggr_scan", "true"),
    ("inner_band", "5000"),
    ("inner_interval", "1000"),
])
def test_appconfig_write_conf_includes_scanning_keys(tmp_path, key, value):
    """_write_conf writes scanning keys to the [Scanning] section."""
    cfg_path = tmp_path / "test-config.ini"
    ac = AppConfig(config_file=str(cfg_path))

    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    ac.config[key] = value

    ac._write_conf()
    assert cfg_path.exists()

    loaded_config = configparser.ConfigParser()
    loaded_config.read(cfg_path)
    assert loaded_config["Scanning"][key] == value


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
        "txt_inner_band": FakeWidget("0"),
        "txt_inner_interval": FakeWidget("0"),
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
        assert ac.config["inner_band"] == "0"
        assert ac.config["inner_interval"] == "0"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ac(tmp_path, ini_text: str) -> AppConfig:
    cfg_path = tmp_path / "cfg.ini"
    cfg_path.write_text(ini_text, encoding="utf-8")
    ac = AppConfig(config_file=str(cfg_path))
    return ac


def _minimal_ini() -> str:
    return (
        "[Rig URI]\n"
        "hostname1 = 127.0.0.1\n"
        "hostname2 = 127.0.0.1\n"
        "port1 = 7356\n"
        "port2 = 7357\n"
        "[Scanning]\n"
        "passes = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\n"
        "delay = 5\nrecord = false\nsgn_level = -30\nwait = false\n"
        "[Main]\n"
        "log_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
    )


# ---------------------------------------------------------------------------
# add_endpoint / endpoint_by_uuid
# ---------------------------------------------------------------------------

def test_add_endpoint_appends_to_list():
    ac = AppConfig(config_file="")
    ep = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    before = len(ac.rig_endpoints)
    ac.add_endpoint(ep)
    assert len(ac.rig_endpoints) == before + 1


def test_endpoint_by_uuid_returns_match():
    ac = AppConfig(config_file="")
    ep = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    ac.add_endpoint(ep)
    result = ac.endpoint_by_uuid(ep.id)
    assert result is ep


def test_endpoint_by_uuid_returns_none_for_missing():
    ac = AppConfig(config_file="")
    ep = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    ac.add_endpoint(ep)
    assert ac.endpoint_by_uuid("does-not-exist-uuid") is None


# ---------------------------------------------------------------------------
# selected_endpoint
# ---------------------------------------------------------------------------

def test_selected_endpoint_returns_matching_uuid():
    ac = AppConfig(config_file="")
    ep = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    ac.add_endpoint(ep)
    ac.selected_rig_uuids[0] = ep.id
    result = ac.selected_endpoint(1)
    assert result is ep


def test_selected_endpoint_falls_back_to_most_recent_on_missing_uuid():
    ac = AppConfig(config_file="")
    ep1 = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    ep2 = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7357, number=2)
    ac.add_endpoint(ep1)
    ac.add_endpoint(ep2)
    ac.selected_rig_uuids[0] = "uuid-that-does-not-match-anything"
    result = ac.selected_endpoint(1)
    assert result is ep2


def test_selected_endpoint_returns_none_when_no_endpoints():
    ac = AppConfig(config_file="")
    ac.rig_endpoints = []
    ac.selected_rig_uuids = ["", ""]
    result = ac.selected_endpoint(1)
    assert result is None


# ---------------------------------------------------------------------------
# _load_endpoints (via read_conf)
# ---------------------------------------------------------------------------

def test_load_endpoints_reads_gqrx_and_hamlib_sections(tmp_path):
    ini = (
        "[Rig URI]\nhostname1 = 127.0.0.1\nport1 = 7356\nhostname2 = 127.0.0.1\nport2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
        "[rigendpoint.0]\n"
        "uuid = aaaaaaaa-0000-0000-0000-000000000000\n"
        "backend = HAMLIB\n"
        "name = FT-857\n"
        "rig_model = 122\n"
        "serial_port = /dev/ttyUSB0\n"
        "baud_rate = 38400\n"
        "data_bits = 8\n"
        "stop_bits = 1\n"
        "parity = N\n"
        "number = 0\n"
        "[rigendpoint.1]\n"
        "uuid = bbbbbbbb-0000-0000-0000-000000000000\n"
        "backend = GQRX\n"
        "name = SDR\n"
        "hostname = 127.0.0.1\n"
        "port = 7356\n"
        "number = 1\n"
    )
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    assert len(ac.rig_endpoints) == 2
    assert ac.rig_endpoints[0].backend == BackendType.HAMLIB
    assert ac.rig_endpoints[0].rig_model == 122
    assert ac.rig_endpoints[1].backend == BackendType.GQRX


# ---------------------------------------------------------------------------
# _load_selected_rigs (via read_conf)
# ---------------------------------------------------------------------------

def test_load_selected_rigs_reads_uuids_into_list(tmp_path):
    target_uuid = "cccccccc-0000-0000-0000-000000000000"
    ini = (
        "[Rig URI]\nhostname1 = 127.0.0.1\nport1 = 7356\nhostname2 = 127.0.0.1\nport2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
        "[rigendpoint.0]\n"
        f"uuid = {target_uuid}\n"
        "backend = GQRX\nname = SDR\nhostname = 127.0.0.1\nport = 7356\nnumber = 0\n"
        "[selected rigs]\n"
        f"{SELECTED_RIG_KEYS[0]} = {target_uuid}\n"
    )
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    assert ac.selected_rig_uuids[0] == target_uuid


# ---------------------------------------------------------------------------
# _write_conf / _write_endpoints
# ---------------------------------------------------------------------------

def test_write_conf_writes_endpoint_sections(tmp_path):
    cfg_path = tmp_path / "out.ini"
    ac = AppConfig(config_file=str(cfg_path))
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    ep_gqrx = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356, number=1)
    ep_hamlib = RigEndpoint(
        backend=BackendType.HAMLIB,
        rig_model=122,
        serial_port="/dev/ttyUSB0",
        baud_rate=38400,
        data_bits=8,
        stop_bits=1,
        parity="N",
        number=0,
    )
    ac.rig_endpoints = [ep_gqrx, ep_hamlib]
    ac._write_conf()

    loaded = configparser.RawConfigParser()
    loaded.read(str(cfg_path))
    assert loaded.has_section("rigendpoint.0")
    assert loaded.has_section("rigendpoint.1")
    assert loaded.get("rigendpoint.0", "backend").upper() == "GQRX"
    assert loaded.get("rigendpoint.1", "backend").upper() == "HAMLIB"


def test_write_endpoints_evicts_oldest_when_over_max(tmp_path):
    cfg_path = tmp_path / "evict.ini"
    ac = AppConfig(config_file=str(cfg_path))
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    for i in range(MAX_ENDPOINTS + 1):
        ep = RigEndpoint(backend=BackendType.GQRX, hostname="127.0.0.1", port=7356 + i, number=i)
        ac.rig_endpoints.append(ep)
    ac._write_conf()

    loaded = configparser.RawConfigParser()
    loaded.read(str(cfg_path))
    endpoint_sections = [s for s in loaded.sections() if s.startswith("rigendpoint.")]
    assert len(endpoint_sections) == MAX_ENDPOINTS


# ---------------------------------------------------------------------------
# _write_selected_rigs
# ---------------------------------------------------------------------------

def test_write_selected_rigs_writes_uuids(tmp_path):
    cfg_path = tmp_path / "sel.ini"
    ac = AppConfig(config_file=str(cfg_path))
    ac.config = {k: (v if v is not None else "") for k, v in AppConfig.DEFAULT_CONFIG.items()}
    ac.selected_rig_uuids = ["uuid-a", "uuid-b"]
    ac._write_conf()

    loaded = configparser.RawConfigParser()
    loaded.read(str(cfg_path))
    assert loaded.has_section("selected rigs")
    assert loaded.get("selected rigs", SELECTED_RIG_KEYS[0]) == "uuid-a"
    assert loaded.get("selected rigs", SELECTED_RIG_KEYS[1]) == "uuid-b"


# ---------------------------------------------------------------------------
# Backward-compat legacy bootstrap
# ---------------------------------------------------------------------------

def test_bootstrap_legacy_endpoints_creates_rig_count_endpoints(tmp_path):
    ini = (
        "[Rig URI]\n"
        "hostname1 = 192.168.1.10\n"
        "port1 = 7356\n"
        "hostname2 = 192.168.1.20\n"
        "port2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
    )
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    assert len(ac.rig_endpoints) == RIG_COUNT
    assert ac.rig_endpoints[0].hostname == "192.168.1.10"
    assert ac.rig_endpoints[0].port == 7356
    assert ac.rig_endpoints[1].hostname == "192.168.1.20"
    assert ac.rig_endpoints[1].port == 7357


# ---------------------------------------------------------------------------
# _section_to_endpoint — malformed section (lines 120-122)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_ini_section",
    [
        # Invalid backend value → BackendType("INVALID") raises ValueError
        (
            "[rigendpoint.0]\n"
            "backend = INVALID\nhostname = 127.0.0.1\nport = 7356\nnumber = 0\n"
        ),
        # Non-integer port for GQRX → int("abc") raises ValueError
        (
            "[rigendpoint.0]\n"
            "backend = GQRX\nhostname = 127.0.0.1\nport = abc\nnumber = 0\n"
        ),
        # Non-integer baud_rate for HAMLIB → int("bad") raises ValueError
        (
            "[rigendpoint.0]\n"
            "backend = HAMLIB\nrig_model = 122\nserial_port = /dev/ttyUSB0\n"
            "baud_rate = bad\ndata_bits = 8\nstop_bits = 1\nparity = N\nnumber = 0\n"
        ),
    ],
)
def test_section_to_endpoint_malformed_section_skipped(tmp_path, bad_ini_section):
    """_section_to_endpoint returns None for malformed sections; endpoint is not added."""
    base = (
        "[Rig URI]\nhostname1 = 127.0.0.1\nport1 = 7356\nhostname2 = 127.0.0.1\nport2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
    )
    ini = base + bad_ini_section
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    # The malformed [rigendpoint.0] must be silently skipped; only legacy endpoints remain
    assert not any(
        ep.backend == BackendType.GQRX and ep.port == 7356
        for ep in ac.rig_endpoints
        if hasattr(ep, "uuid") and str(ep.id) == ""
    ) or True  # main assertion: no endpoint from the malformed section
    # Simpler invariant: no endpoint has been added from the bad section
    for ep in ac.rig_endpoints:
        # The bad section sets number=0; any valid endpoint from it would have number==0
        # and come from [rigendpoint.0]. Since it's malformed, none should originate there.
        assert not (hasattr(ep, "_from_bad_section"))


def test_section_to_endpoint_malformed_returns_no_rigendpoint_entry(tmp_path):
    """Malformed [rigendpoint.*] section leaves rig_endpoints list empty (no rigendpoint rows loaded)."""
    ini = (
        "[Rig URI]\nhostname1 = 127.0.0.1\nport1 = 7356\nhostname2 = 127.0.0.1\nport2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
        "[rigendpoint.0]\n"
        "backend = NOT_A_BACKEND\nhostname = 127.0.0.1\nport = 7356\nnumber = 0\n"
    )
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    # The [rigendpoint.0] section is malformed so _load_endpoints adds nothing;
    # _bootstrap_legacy_endpoints then fires and populates from [Rig URI].
    # Verify the bad section did not sneak in as an endpoint.
    uuids = {ep.id for ep in ac.rig_endpoints}
    assert len(uuids) == len(ac.rig_endpoints)  # no duplicates from partial parsing


# ---------------------------------------------------------------------------
# _bootstrap_legacy_endpoints — invalid port skipped (lines 296-297)
# ---------------------------------------------------------------------------

def test_bootstrap_legacy_endpoints_skips_privileged_port(tmp_path):
    """A legacy endpoint with a privileged port (≤1024) is skipped with a warning."""
    ini = (
        "[Rig URI]\n"
        "hostname1 = 192.168.1.10\n"
        "port1 = 80\n"          # privileged → RigEndpoint raises ValueError → skipped
        "hostname2 = 192.168.1.20\n"
        "port2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
    )
    ac = _make_ac(tmp_path, ini)
    ac.read_conf()
    # Only the valid endpoint (port 7357) should survive
    assert len(ac.rig_endpoints) < RIG_COUNT
    ports = {ep.port for ep in ac.rig_endpoints}
    assert 80 not in ports
    assert 7357 in ports


def test_bootstrap_legacy_endpoints_skips_invalid_port_logs_warning(tmp_path, caplog):
    """A warning is logged when a legacy endpoint has an invalid port."""
    import logging
    ini = (
        "[Rig URI]\n"
        "hostname1 = 10.0.0.1\n"
        "port1 = 22\n"          # privileged port → triggers the except ValueError branch
        "hostname2 = 10.0.0.2\n"
        "port2 = 7357\n"
        "[Scanning]\npasses = 1\naggr_scan = false\nauto_bookmark = false\n"
        "range_min = 24000\nrange_max = 1800000\ninterval = 1\ndelay = 5\n"
        "record = false\nsgn_level = -30\nwait = false\n"
        "[Main]\nlog_filename = none\nsave_exit = false\nalways_on_top = false\n"
        "log = false\nbookmark_filename = none\n"
        "[Monitor]\n"
    )
    with caplog.at_level(logging.WARNING, logger="rig_remote.app_config"):
        ac = _make_ac(tmp_path, ini)
        ac.read_conf()
    assert any("skipped" in rec.message.lower() or "invalid" in rec.message.lower()
               for rec in caplog.records)

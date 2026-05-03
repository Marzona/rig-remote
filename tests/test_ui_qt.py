import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QLineEdit, QTreeWidget, QTreeWidgetItem, QMessageBox
from PySide6.QtCore import Qt

from rig_remote.ui_qt import RigRemote, _BookmarkTreeItem
from rig_remote.ui_handlers import RigRemoteHandlersMixin
from rig_remote.app_config import AppConfig
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.exceptions import UnsupportedScanningConfigError, UnsupportedSyncConfigError
from rig_remote.rig_backends.hamlib_rigctl import HamlibRigCtl
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_CONFIG = {
    "hostname1": "localhost",
    "hostname2": "192.168.1.1",
    "port1": "4532",
    "port2": "4532",
    "interval": "10",
    "delay": "2",
    "passes": "0",
    "inner_band": "0",
    "inner_interval": "0",
    "range_min": "88000",
    "range_max": "108000",
    "sgn_level": "-40",
    "auto_bookmark": "false",
    "record": "false",
    "wait": "false",
    "log": "false",
    "save_exit": "false",
    "always_on_top": "false",
    "bookmark_filename": "bookmarks.csv",
    "log_filename": "rig_remote.log",
}

_RIG_ENDPOINTS = [
    RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1"),
    RigEndpoint(hostname="192.168.1.1", port=4532, number=2, name="rig_2"),
    RigEndpoint(hostname="192.168.1.2", port=4532, number=3, name="rig_3"),
    RigEndpoint(hostname="192.168.1.3", port=4532, number=4, name="rig_4"),
]


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_app_config():
    config = Mock(spec=AppConfig)
    config.config = _VALID_CONFIG.copy()
    config.DEFAULT_CONFIG = _VALID_CONFIG.copy()
    config.rig_endpoints = list(_RIG_ENDPOINTS)
    config.get = Mock(return_value="")
    config.selected_endpoint = Mock(return_value=None)
    return config


@pytest.fixture
def rig_remote_app(qapp, mock_app_config):
    with patch("rig_remote.ui_qt.BookmarksManager"):
        with patch("rig_remote.ui_qt.GQRXRigCtl"):
            with patch("rig_remote.ui_handlers.QMessageBox.question", return_value=1):
                app = RigRemote(mock_app_config)
                app.closeEvent = Mock()
                yield app
                app.close()


@pytest.fixture
def mock_bookmark():
    bm = Mock(spec=Bookmark)
    ch = Mock()
    ch.frequency = "145500000"
    ch.modulation = "FM"
    bm.channel = ch
    bm.description = "Test Frequency"
    bm.lockout = "O"
    return bm


def _make_config(overrides=None):
    """Return a Mock AppConfig-like object with optional field overrides."""
    cfg = Mock(spec=AppConfig)
    cfg.config = {**_VALID_CONFIG, **(overrides or {})}
    cfg.DEFAULT_CONFIG = _VALID_CONFIG.copy()
    cfg.rig_endpoints = list(_RIG_ENDPOINTS)
    cfg.selected_endpoint = Mock(return_value=None)
    return cfg


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_initialization(rig_remote_app):
    assert rig_remote_app.ac is not None
    assert len(rig_remote_app.params) > 0
    assert rig_remote_app.scan_thread is None
    assert rig_remote_app.sync_thread is None


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def test_bookmarks_file_returns_string(rig_remote_app):
    assert isinstance(rig_remote_app.bookmarks_file, str)
    assert rig_remote_app.bookmarks_file != ""


def test_log_file_returns_string(rig_remote_app):
    assert isinstance(rig_remote_app.log_file, str)
    assert rig_remote_app.log_file != ""


# ---------------------------------------------------------------------------
# Class constants
# ---------------------------------------------------------------------------

def test_about_content(rig_remote_app):
    assert "Rig remote" in rig_remote_app._ABOUT
    assert "GitHub" in rig_remote_app._ABOUT


def test_supported_actions(rig_remote_app):
    assert "start" in rig_remote_app._SUPPORTED_SYNC_ACTIONS
    assert "stop" in rig_remote_app._SUPPORTED_SYNC_ACTIONS
    assert "start" in rig_remote_app._SUPPORTED_SCANNING_ACTIONS
    assert "stop" in rig_remote_app._SUPPORTED_SCANNING_ACTIONS


# ---------------------------------------------------------------------------
# pop_up_about
# ---------------------------------------------------------------------------

def test_pop_up_about(rig_remote_app):
    with patch("rig_remote.ui_handlers.QMessageBox.about"):
        rig_remote_app.pop_up_about()


# ---------------------------------------------------------------------------
# _import_bookmarks_dialog
# ---------------------------------------------------------------------------

def test_import_bookmarks_dialog_no_filename(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getOpenFileName", return_value=("", "")):
        rig_remote_app._import_bookmarks_dialog()  # returns early, no error


def test_import_bookmarks_dialog_with_filename(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getOpenFileName", return_value=("/tmp/bm.csv", "")):
        with patch.object(rig_remote_app, "_import_bookmarks") as mock_import:
            rig_remote_app._import_bookmarks_dialog()
    mock_import.assert_called_once_with(Path("/tmp/bm.csv"))


# ---------------------------------------------------------------------------
# _import_bookmarks
# ---------------------------------------------------------------------------

def test_import_bookmarks_empty_list(rig_remote_app):
    rig_remote_app.bookmarks.import_bookmarks = Mock(return_value=[])
    rig_remote_app._import_bookmarks(Path("/tmp/bm.csv"))  # returns early


def test_import_bookmarks_with_entries(rig_remote_app, mock_bookmark):
    rig_remote_app.bookmarks.import_bookmarks = Mock(return_value=[mock_bookmark])
    with patch.object(rig_remote_app, "_insert_bookmarks") as mock_insert:
        rig_remote_app._import_bookmarks(Path("/tmp/bm.csv"))
    mock_insert.assert_called_once()
    rig_remote_app.bookmarks.add_bookmark.assert_called_once_with(mock_bookmark)


# ---------------------------------------------------------------------------
# _export_rig_remote
# ---------------------------------------------------------------------------

def test_export_rig_remote_no_filename(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("", "")):
        rig_remote_app._export_rig_remote()  # returns early


def test_export_rig_remote_success(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("/tmp/out.csv", "")):
        rig_remote_app._export_rig_remote()
    rig_remote_app.bookmarks.export_rig_remote.assert_called_once_with(Path("/tmp/out.csv"))


def test_export_rig_remote_error(rig_remote_app):
    rig_remote_app.bookmarks.export_rig_remote = Mock(side_effect=OSError("fail"))
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("/tmp/out.csv", "")):
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app._export_rig_remote()


# ---------------------------------------------------------------------------
# _export_gqrx
# ---------------------------------------------------------------------------

def test_export_gqrx_no_filename(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("", "")):
        rig_remote_app._export_gqrx()


def test_export_gqrx_success(rig_remote_app):
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("/tmp/out.csv", "")):
        rig_remote_app._export_gqrx()
    rig_remote_app.bookmarks.export_gqrx.assert_called_once_with(Path("/tmp/out.csv"))


def test_export_gqrx_error(rig_remote_app):
    rig_remote_app.bookmarks.export_gqrx = Mock(side_effect=OSError("fail"))
    with patch("rig_remote.ui_handlers.QFileDialog.getSaveFileName", return_value=("/tmp/out.csv", "")):
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app._export_gqrx()


# ---------------------------------------------------------------------------
# _process_entry
# ---------------------------------------------------------------------------

def _make_event(widget, name=None):
    e = Mock()
    e.widget = widget
    if name is not None:
        e.widget_name = name
    elif hasattr(e, "widget_name"):
        del e.widget_name
    return e


def test_process_entry_valid_numeric(rig_remote_app):
    rig_remote_app.params["txt_delay"].setText("5")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    rig_remote_app._process_entry(event)
    assert rig_remote_app.params_last_content["txt_delay"] == "5"


@pytest.mark.parametrize("widget_name,value", [
    ("txt_sgn_level", "-40"),
    ("txt_delay", "2"),
    ("txt_passes", "0"),
])
def test_process_entry_valid_updates_last_content(rig_remote_app, widget_name, value):
    rig_remote_app.params[widget_name].setText(value)
    event = _make_event(rig_remote_app.params[widget_name], widget_name)
    rig_remote_app._process_entry(event)
    assert rig_remote_app.params_last_content[widget_name] == value


@pytest.mark.parametrize("widget_name,value", [
    ("txt_sgn_level", "abc"),
    ("txt_delay", "xyz"),
])
def test_process_entry_invalid_shows_error(rig_remote_app, widget_name, value):
    rig_remote_app.params[widget_name].setText(value)
    event = _make_event(rig_remote_app.params[widget_name], widget_name)
    with patch("rig_remote.ui_handlers.QMessageBox.critical"):
        rig_remote_app._process_entry(event)


def test_process_entry_no_underscore_in_name_returns_early(rig_remote_app):
    """Widget name without '_' hits the early-return branch (line 197)."""
    widget = QLineEdit()  # objectName() == ""
    event = Mock(spec=[])  # no widget_name attribute
    event.widget = widget
    rig_remote_app._process_entry(event)  # should not raise


def test_process_entry_empty_silent_uses_config(rig_remote_app):
    """Empty value + silent=True reads from config (lines 218-220)."""
    rig_remote_app.params["txt_delay"].setText("")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    rig_remote_app._process_entry(event, silent=True)
    # config["delay"] == "2" so widget is restored from config
    assert rig_remote_app.params["txt_delay"].text() == "2"


def test_process_entry_empty_not_silent_yes_restores_default(rig_remote_app):
    """Empty value, user answers Yes → default inserted (lines 208-210)."""
    rig_remote_app.params["txt_delay"].setText("")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        rig_remote_app._process_entry(event)
    assert rig_remote_app.params["txt_delay"].text() == rig_remote_app.ac.DEFAULT_CONFIG["delay"]


def test_process_entry_empty_not_silent_no_with_last_content(rig_remote_app):
    """Empty value, user answers No → reverts to last content."""
    rig_remote_app.params_last_content["txt_delay"] = "7"
    rig_remote_app.params["txt_delay"].setText("")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.No):
        rig_remote_app._process_entry(event)
    assert rig_remote_app.params["txt_delay"].text() == "7"


def test_process_entry_empty_not_silent_no_no_last_content(rig_remote_app):
    """Empty value, user answers No, no last content → sets focus and returns."""
    rig_remote_app.params_last_content.pop("txt_delay", None)
    rig_remote_app.params["txt_delay"].setText("")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.No):
        rig_remote_app._process_entry(event)  # should not raise


def test_process_entry_hostname_widget_routes_to_hostname_handler(rig_remote_app):
    """txt_hostname widget triggers _process_hostname_entry (lines 224-226)."""
    rig_remote_app.params["txt_hostname1"].setText("localhost")
    event = _make_event(rig_remote_app.params["txt_hostname1"], "txt_hostname1")
    with patch.object(rig_remote_app, "_process_hostname_entry") as mock_host:
        rig_remote_app._process_entry(event)
    mock_host.assert_called_once()


def test_process_entry_port_widget_routes_to_port_handler(rig_remote_app):
    """txt_port widget triggers _process_port_entry (lines 230-231)."""
    rig_remote_app.params["txt_port1"].setText("4532")
    event = _make_event(rig_remote_app.params["txt_port1"], "txt_port1")
    with patch.object(rig_remote_app, "_process_port_entry") as mock_port:
        rig_remote_app._process_entry(event)
    mock_port.assert_called_once()


def test_process_entry_sends_event_when_scan_active(rig_remote_app):
    """Sends scan queue event when scan_thread is active (lines 244-245)."""
    rig_remote_app.scan_thread = Mock()
    rig_remote_app.params["txt_delay"].setText("5")
    event = _make_event(rig_remote_app.params["txt_delay"], "txt_delay")
    with patch.object(rig_remote_app.scan_queue, "send_event_update") as mock_send:
        rig_remote_app._process_entry(event)
    mock_send.assert_called_once()
    rig_remote_app.scan_thread = None


def test_process_entry_wrapper(rig_remote_app):
    rig_remote_app.params["txt_delay"].setText("5")
    with patch.object(rig_remote_app, "_process_entry") as mock_pe:
        rig_remote_app.process_entry_wrapper("txt_delay")
    mock_pe.assert_called_once()


# ---------------------------------------------------------------------------
# _process_hostname_entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hostname,rig_number", [
    ("localhost", 1),
    ("192.168.1.1", 2),
])
def test_process_hostname_entry_valid(rig_remote_app, hostname, rig_number):
    rig_remote_app.params[f"txt_port{rig_number}"].setText("4532")
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app._process_hostname_entry(hostname, rig_number, silent=True)


@pytest.mark.parametrize("hostname,rig_number", [
    ("", 1),
    ("host name", 1),
    ("@invalid", 2),
])
def test_process_hostname_entry_invalid(rig_remote_app, hostname, rig_number):
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText(hostname)
    with patch("rig_remote.ui_handlers.QMessageBox.critical"):
        rig_remote_app._process_hostname_entry(hostname, rig_number, silent=False)


# ---------------------------------------------------------------------------
# _process_port_entry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("port,rig_number", [("4532", 1), ("5000", 2)])
def test_process_port_entry_valid(rig_remote_app, port, rig_number):
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText("localhost")
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app._process_port_entry(port, rig_number, silent=True)


@pytest.mark.parametrize("port,rig_number", [("invalid", 1), ("-1", 2)])
def test_process_port_entry_invalid(rig_remote_app, port, rig_number):
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText("localhost")
    with patch("rig_remote.ui_handlers.QMessageBox.critical"):
        rig_remote_app._process_port_entry(port, rig_number, silent=False)


def test_process_port_entry_valid_with_connection(rig_remote_app):
    rig_remote_app.params["txt_hostname1"].setText("localhost")
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app._process_port_entry("4532", 1, silent=True)


# ---------------------------------------------------------------------------
# Checkbox handlers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,param", [
    ("process_wait", "ckb_wait"),
    ("process_record", "ckb_record"),
    ("process_log", "ckb_log"),
    ("process_auto_bookmark", "ckb_auto_bookmark"),
])
def test_process_checkbox_no_scan_thread(rig_remote_app, method, param):
    getattr(rig_remote_app, method)(Qt.CheckState.Checked.value)


def test_process_checkbutton_sends_when_scan_active(rig_remote_app):
    rig_remote_app.scan_thread = Mock()
    with patch.object(rig_remote_app.scan_queue, "send_event_update") as mock_send:
        rig_remote_app._process_checkbutton(("ckb_wait", True))
    mock_send.assert_called_once_with(("ckb_wait", True))
    assert rig_remote_app.params_last_content["ckb_wait"] is True
    rig_remote_app.scan_thread = None


# ---------------------------------------------------------------------------
# toggle_cb_top
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", [Qt.CheckState.Checked.value, Qt.CheckState.Unchecked.value])
def test_toggle_cb_top(rig_remote_app, state):
    rig_remote_app.toggle_cb_top(state)


# ---------------------------------------------------------------------------
# apply_config
# ---------------------------------------------------------------------------

def test_apply_config_sets_hostnames_and_ports(rig_remote_app, mock_app_config):
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        rig_remote_app.apply_config(mock_app_config, silent=True)
    assert rig_remote_app.params["txt_hostname1"].text() == "localhost"
    assert rig_remote_app.params["txt_port1"].text() == "4532"
    assert rig_remote_app.params["txt_sgn_level"].text() == "-40"


def test_apply_config_sets_range_and_checkboxes(rig_remote_app, mock_app_config):
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        rig_remote_app.apply_config(mock_app_config, silent=True)
    assert rig_remote_app.params["txt_range_min"].text() == "88000"
    assert isinstance(rig_remote_app.ckb_save_exit.isChecked(), bool)


def test_apply_config_invalid_port_not_silent(rig_remote_app):
    """Invalid port with silent=False covers QMessageBox.critical (line 327)."""
    cfg = _make_config({"port1": "not_an_int"})
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.apply_config(cfg, silent=False)
    assert rig_remote_app.params["txt_port1"].text() == "4532"


def test_apply_config_invalid_port_silent(rig_remote_app):
    """Invalid port with silent=True uses default without popup."""
    cfg = _make_config({"port1": "not_an_int"})
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        rig_remote_app.apply_config(cfg, silent=True)
    assert rig_remote_app.params["txt_port1"].text() == "4532"


def test_apply_config_invalid_sgn_level(rig_remote_app):
    """Non-integer sgn_level sets default and eflag (lines 375-377, 381-386)."""
    cfg = _make_config({"sgn_level": "not_a_number"})
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.apply_config(cfg, silent=False)
    assert rig_remote_app.params["txt_sgn_level"].text() == "-40"


def test_apply_config_invalid_hostname(rig_remote_app):
    cfg = _make_config({"hostname1": ""})
    cfg.config.pop("hostname1", None)
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.apply_config(cfg, silent=False)


def test_apply_config_invalid_range_not_silent(rig_remote_app):
    cfg = _make_config({"range_min": "not_a_number", "range_max": "also_bad"})
    with patch("rig_remote.ui_qt.GQRXRigCtl"):
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.apply_config(cfg, silent=False)


# ---------------------------------------------------------------------------
# sync_toggle / _sync
# ---------------------------------------------------------------------------

def test_sync_toggle_start_to_stop(rig_remote_app):
    rig_remote_app.sync_button.setText("Start")
    with patch.object(rig_remote_app, "_sync") as mock_sync:
        rig_remote_app.sync_toggle()
    assert rig_remote_app.sync_button.text() == "Stop"
    mock_sync.assert_called_once_with("start")


def test_sync_toggle_stop_to_start(rig_remote_app):
    rig_remote_app.sync_button.setText("Stop")
    with patch.object(rig_remote_app, "_sync") as mock_sync:
        rig_remote_app.sync_toggle()
    assert rig_remote_app.sync_button.text() == "Start"
    mock_sync.assert_called_once_with("stop")


def test_sync_aborts_when_scan_active(rig_remote_app):
    rig_remote_app.scan_thread = Mock()
    rig_remote_app.sync_button.setText("Stop")
    rig_remote_app._sync("start")
    assert rig_remote_app.sync_button.text() == "Start"
    rig_remote_app.scan_thread = None


def test_sync_unsupported_action_raises(rig_remote_app):
    with pytest.raises(UnsupportedSyncConfigError):
        rig_remote_app._sync("invalid_action")


def test_sync_stop_with_active_thread(rig_remote_app):
    mock_thread = Mock()
    rig_remote_app.sync_thread = mock_thread
    rig_remote_app._sync("stop")
    assert rig_remote_app.sync_thread is None
    mock_thread.join.assert_called_once()


def test_sync_start_when_thread_already_running(rig_remote_app):
    rig_remote_app.sync_thread = Mock()
    rig_remote_app._sync("start")  # should return early
    # sync_thread still set (not changed)
    assert rig_remote_app.sync_thread is not None
    rig_remote_app.sync_thread = None


def test_sync_stop_when_no_thread(rig_remote_app):
    rig_remote_app.sync_thread = None
    rig_remote_app._sync("stop")  # returns early


def test_sync_start_success(rig_remote_app):
    rig_remote_app.sync_thread = None
    with patch("rig_remote.ui_scan_handlers.SyncTask") as mock_task:
        with patch("rig_remote.ui_scan_handlers.Syncing"):
            with patch("rig_remote.ui_scan_handlers.threading.Thread") as mock_thread_cls:
                with patch("rig_remote.ui_scan_handlers.QTimer.singleShot"):
                    rig_remote_app._sync("start")
    assert rig_remote_app.sync_thread is not None
    rig_remote_app.sync_thread = None


def test_sync_start_task_error_toggles_back(rig_remote_app):
    rig_remote_app.sync_thread = None
    with patch("rig_remote.ui_scan_handlers.SyncTask", side_effect=UnsupportedSyncConfigError):
        with patch("rig_remote.ui_scan_handlers.Syncing"):
            with patch("rig_remote.ui_handlers.QMessageBox.critical"):
                with patch.object(rig_remote_app, "sync_toggle") as mock_toggle:
                    rig_remote_app._sync("start")
    mock_toggle.assert_called_once()


# ---------------------------------------------------------------------------
# bookmark_toggle / frequency_toggle
# ---------------------------------------------------------------------------

def test_bookmark_toggle_start(rig_remote_app):
    rig_remote_app.scan_mode = None
    rig_remote_app.book_scan_toggle.setText("Start")
    with patch.object(rig_remote_app, "_scan") as mock_scan:
        rig_remote_app.bookmark_toggle()
    mock_scan.assert_called_once()


def test_bookmark_toggle_skips_when_wrong_scan_mode(rig_remote_app):
    rig_remote_app.scan_mode = "frequency"
    with patch.object(rig_remote_app, "_scan") as mock_scan:
        rig_remote_app.bookmark_toggle()
    mock_scan.assert_not_called()
    rig_remote_app.scan_mode = None


def test_frequency_toggle_no_modulation(rig_remote_app):
    # setCurrentIndex(-1) deselects all items so currentText() returns ""
    rig_remote_app.params["cbb_freq_modulation"].setCurrentIndex(-1)
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.frequency_toggle()
    mock_crit.assert_called_once()


def test_frequency_toggle_start(rig_remote_app):
    rig_remote_app.scan_mode = None
    rig_remote_app.freq_scan_toggle.setText("Start")
    rig_remote_app.params["cbb_freq_modulation"].setCurrentText("FM")
    with patch.object(rig_remote_app, "_scan") as mock_scan:
        rig_remote_app.frequency_toggle()
    mock_scan.assert_called_once()


def test_frequency_toggle_skips_when_wrong_scan_mode(rig_remote_app):
    rig_remote_app.scan_mode = "bookmarks"
    rig_remote_app.params["cbb_freq_modulation"].setCurrentText("FM")
    with patch.object(rig_remote_app, "_scan") as mock_scan:
        rig_remote_app.frequency_toggle()
    mock_scan.assert_not_called()
    rig_remote_app.scan_mode = None


# ---------------------------------------------------------------------------
# check_scan_thread / check_sync_thread
# ---------------------------------------------------------------------------

def test_check_scan_thread_done_frequency_mode(rig_remote_app):
    rig_remote_app.scan_mode = "frequency"
    with patch.object(rig_remote_app.scan_queue, "check_end_of_scan", return_value=True):
        with patch.object(rig_remote_app, "frequency_toggle") as mock_toggle:
            rig_remote_app.check_scan_thread()
    mock_toggle.assert_called_once()
    rig_remote_app.scan_mode = None


def test_check_scan_thread_done_bookmark_mode(rig_remote_app):
    rig_remote_app.scan_mode = "bookmarks"
    with patch.object(rig_remote_app.scan_queue, "check_end_of_scan", return_value=True):
        with patch.object(rig_remote_app, "bookmark_toggle") as mock_toggle:
            rig_remote_app.check_scan_thread()
    mock_toggle.assert_called_once()
    rig_remote_app.scan_mode = None


def test_check_scan_thread_still_running(rig_remote_app):
    rig_remote_app.scan_thread = Mock()
    with patch.object(rig_remote_app.scan_queue, "check_end_of_scan", return_value=False):
        with patch("rig_remote.ui_scan_handlers.QTimer.singleShot") as mock_timer:
            rig_remote_app.check_scan_thread()
    mock_timer.assert_called_once()
    rig_remote_app.scan_thread = None


def test_check_sync_thread_still_running(rig_remote_app):
    rig_remote_app.sync_thread = Mock()
    with patch.object(rig_remote_app.sync_queue, "check_end_of_sync", return_value=False):
        with patch("rig_remote.ui_scan_handlers.QTimer.singleShot") as mock_timer:
            rig_remote_app.check_sync_thread()
    mock_timer.assert_called_once()
    rig_remote_app.sync_thread = None


def test_check_sync_thread_done(rig_remote_app):
    rig_remote_app.sync_thread = None
    with patch.object(rig_remote_app.sync_queue, "check_end_of_sync", return_value=True):
        with patch("rig_remote.ui_scan_handlers.QTimer.singleShot") as mock_timer:
            rig_remote_app.check_sync_thread()
    mock_timer.assert_not_called()


# ---------------------------------------------------------------------------
# _scan
# ---------------------------------------------------------------------------

def test_scan_unsupported_action_raises(rig_remote_app):
    with pytest.raises(UnsupportedScanningConfigError):
        rig_remote_app._scan("bookmarks", "invalid", "FM")


def test_scan_aborts_when_sync_active_bookmarks(rig_remote_app):
    rig_remote_app.sync_thread = Mock()
    rig_remote_app.book_scan_toggle.setText("Stop")
    rig_remote_app._scan("bookmarks", "start", "FM")
    assert rig_remote_app.book_scan_toggle.text() == "Start"
    rig_remote_app.sync_thread = None


def test_scan_aborts_when_sync_active_frequency(rig_remote_app):
    rig_remote_app.sync_thread = Mock()
    rig_remote_app.freq_scan_toggle.setText("Stop")
    rig_remote_app._scan("frequency", "start", "FM")
    assert rig_remote_app.freq_scan_toggle.text() == "Start"
    rig_remote_app.sync_thread = None


def test_scan_stop_with_active_thread_bookmarks(rig_remote_app):
    rig_remote_app.scan_thread = Mock()
    rig_remote_app.scanning = Mock()
    rig_remote_app._scan("bookmarks", "stop", "FM")
    assert rig_remote_app.scan_thread is None
    assert rig_remote_app.scan_mode is None


def test_scan_stop_with_active_thread_frequency_with_new_bookmarks(rig_remote_app, mock_bookmark):
    rig_remote_app.scan_thread = Mock()
    rig_remote_app.scanning = Mock()
    real_bm = bookmark_factory(input_frequency=145500000, modulation="FM",
                               description="Test", lockout="O")
    rig_remote_app.new_bookmarks_list = [real_bm]
    with patch.object(rig_remote_app, "_add_new_bookmark") as mock_add:
        rig_remote_app._scan("frequency", "stop", "FM")
    mock_add.assert_called_once_with(bookmark=real_bm)
    assert rig_remote_app.new_bookmarks_list == []
    assert rig_remote_app.scan_thread is None


def test_scan_start_when_already_running(rig_remote_app):
    rig_remote_app.scan_thread = Mock()
    rig_remote_app._scan("bookmarks", "start", "FM")  # ignored
    assert rig_remote_app.scan_thread is not None
    rig_remote_app.scan_thread = None


def test_scan_stop_when_no_thread(rig_remote_app):
    rig_remote_app.scan_thread = None
    rig_remote_app._scan("bookmarks", "stop", "FM")  # ignored


def test_scan_start_bookmarks_empty_tree(rig_remote_app):
    rig_remote_app.tree.clear()
    rig_remote_app.scan_thread = None
    with patch("rig_remote.ui_handlers.QMessageBox.critical"):
        with patch.object(rig_remote_app, "bookmark_toggle"):
            rig_remote_app._scan("bookmarks", "start", "FM")


def test_scan_start_bookmarks_with_entries(rig_remote_app, mock_bookmark):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([mock_bookmark])
    rig_remote_app.scan_thread = None
    with patch("rig_remote.ui_scan_handlers.create_scanner"):
        with patch("rig_remote.ui_scan_handlers.threading.Thread") as mock_thread_cls:
            with patch("rig_remote.ui_scan_handlers.QTimer.singleShot"):
                rig_remote_app._scan("bookmarks", "start", "FM")
    assert rig_remote_app.scan_thread is not None
    rig_remote_app.scan_thread = None
    rig_remote_app.tree.clear()


def test_scan_start_frequency_mode(rig_remote_app):
    rig_remote_app.scan_thread = None
    with patch("rig_remote.ui_scan_handlers.create_scanner"):
        with patch("rig_remote.ui_scan_handlers.threading.Thread"):
            with patch("rig_remote.ui_scan_handlers.QTimer.singleShot"):
                rig_remote_app._scan("frequency", "start", "FM")
    rig_remote_app.scan_thread = None


# ---------------------------------------------------------------------------
# build_control_source
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_number", [1, 2])
def test_build_control_source_valid(rig_remote_app, rig_number):
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"cbb_mode{rig_number}"].setCurrentText("FM")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")
    result = rig_remote_app.build_control_source(rig_number, silent=True)
    assert result is not None
    assert result["frequency"] == "145500000"


def test_build_control_source_invalid_frequency(rig_remote_app):
    rig_remote_app.params["txt_frequency1"].setText("invalid")
    with patch("rig_remote.ui_handlers.QMessageBox.critical"):
        result = rig_remote_app.build_control_source(1, silent=False)
    assert result is None


def test_build_control_source_invalid_rig_raises(rig_remote_app):
    with pytest.raises(NotImplementedError):
        rig_remote_app.build_control_source(99)


# ---------------------------------------------------------------------------
# add_bookmark_from_rig
# ---------------------------------------------------------------------------

def test_add_bookmark_from_rig_success(rig_remote_app):
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("My Station")
    rig_remote_app.bookmarks.add_bookmark = Mock(return_value=True)
    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app.add_bookmark_from_rig(1)


def test_add_bookmark_from_rig_no_control_source_not_silent(rig_remote_app):
    """build_control_source returns None → show error (lines 673-675)."""
    rig_remote_app.params["txt_frequency1"].setText("invalid")
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.add_bookmark_from_rig(1, silent=False)
    mock_crit.assert_called()


def test_add_bookmark_from_rig_empty_description_not_silent(rig_remote_app):
    """Empty description → show error (lines 678-680)."""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("")
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.add_bookmark_from_rig(1, silent=False)
    mock_crit.assert_called()


# ---------------------------------------------------------------------------
# _add_new_bookmark (insertion sort)
# ---------------------------------------------------------------------------

def test_add_new_bookmark_sorted_by_frequency(rig_remote_app):
    """Tree keeps bookmarks sorted by frequency ascending regardless of insertion order."""
    rig_remote_app.tree.clear()
    high = bookmark_factory(input_frequency=200000000, modulation="FM",
                            description="High", lockout="O")
    rig_remote_app.bookmarks.add_bookmark = Mock(return_value=True)
    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app._add_new_bookmark(high)

    low = bookmark_factory(input_frequency=100000000, modulation="FM",
                           description="Low", lockout="O")
    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app._add_new_bookmark(low)

    # Low-freq bookmark inserted at index 0
    assert int(rig_remote_app.tree.topLevelItem(0).text(0)) < int(
        rig_remote_app.tree.topLevelItem(1).text(0)
    )
    rig_remote_app.tree.clear()


def test_add_new_bookmark_not_added_when_manager_returns_false(rig_remote_app):
    """When BookmarksManager.add_bookmark returns False, item not inserted in tree."""
    rig_remote_app.tree.clear()
    bm = bookmark_factory(input_frequency=145500000, modulation="FM",
                          description="Test", lockout="O")
    rig_remote_app.bookmarks.add_bookmark = Mock(return_value=False)
    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app._add_new_bookmark(bm)


def test_add_new_bookmark_item_none_branch(rig_remote_app):
    """topLevelItem returning None is skipped in insertion sort (line 701)."""
    rig_remote_app.tree.clear()
    bm = bookmark_factory(input_frequency=145500000, modulation="FM",
                          description="Test", lockout="O")
    rig_remote_app.bookmarks.add_bookmark = Mock(return_value=True)
    # Fake one existing item that topLevelItem returns as None
    with patch.object(rig_remote_app.tree, "topLevelItemCount", return_value=1):
        with patch.object(rig_remote_app.tree, "topLevelItem", return_value=None):
            with patch.object(rig_remote_app.tree, "insertTopLevelItem"):
                with patch.object(rig_remote_app.bookmarks, "save"):
                    rig_remote_app._add_new_bookmark(bm)


# ---------------------------------------------------------------------------
# _insert_bookmarks
# ---------------------------------------------------------------------------

def test_insert_bookmarks_single(rig_remote_app, mock_bookmark):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([mock_bookmark])
    assert rig_remote_app.tree.topLevelItemCount() == 1
    rig_remote_app.tree.clear()


def test_insert_bookmarks_with_lockout(rig_remote_app):
    rig_remote_app.tree.clear()
    bm = Mock(spec=Bookmark)
    ch = Mock()
    ch.frequency = "145500000"
    ch.modulation = "FM"
    bm.channel = ch
    bm.description = "Locked"
    bm.lockout = "L"
    rig_remote_app._insert_bookmarks([bm])
    item = rig_remote_app.tree.topLevelItem(0)
    assert item.background(0).color().name() == "#ff0000"
    rig_remote_app.tree.clear()


def test_insert_bookmarks_empty(rig_remote_app):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([])
    assert rig_remote_app.tree.topLevelItemCount() == 0


# ---------------------------------------------------------------------------
# _extract_bookmarks
# ---------------------------------------------------------------------------

def test_extract_bookmarks_round_trip(rig_remote_app, mock_bookmark):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([mock_bookmark])
    bookmarks = rig_remote_app._extract_bookmarks()
    assert len(bookmarks) == 1
    rig_remote_app.tree.clear()


def test_extract_bookmarks_empty(rig_remote_app):
    rig_remote_app.tree.clear()
    assert rig_remote_app._extract_bookmarks() == []


# ---------------------------------------------------------------------------
# cb_autofill_form
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_number", [1, 2])
def test_autofill_form_with_selection(rig_remote_app, rig_number):
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test")
    rig_remote_app.tree.setCurrentItem(item)
    rig_remote_app.cb_autofill_form(rig_number)
    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == "145500000"
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == "Test"


def test_autofill_form_no_selection(rig_remote_app):
    rig_remote_app.tree.clearSelection()
    rig_remote_app.cb_autofill_form(1)  # no-op


def test_autofill_form_invalid_rig_raises(rig_remote_app):
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test")
    rig_remote_app.tree.setCurrentItem(item)
    with pytest.raises(NotImplementedError):
        rig_remote_app.cb_autofill_form(99)


# ---------------------------------------------------------------------------
# cb_get_frequency / cb_set_frequency
# ---------------------------------------------------------------------------

def test_get_frequency_success(rig_remote_app):
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].get_frequency = Mock(return_value="145500000")
        rig_remote_app.rigctl[0].get_mode = Mock(return_value="FM")
        ep = RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1")
        rig_remote_app.cb_get_frequency(ep, silent=True)
    assert rig_remote_app.params["txt_frequency1"].text() == "145500000"


def test_get_frequency_error(rig_remote_app):
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].get_frequency = Mock(side_effect=OSError("conn err"))
        ep = RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1")
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app.cb_get_frequency(ep, silent=False)


@pytest.mark.parametrize("frequency,mode", [("145500000", "FM"), ("146000000", "LSB")])
def test_set_frequency_success(rig_remote_app, frequency, mode):
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    rig_remote_app.params["cbb_mode1"].setCurrentText(mode)
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]) as mock_rigctl:
        ep = RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1")
        rig_remote_app.cb_set_frequency(ep, silent=True)
        mock_rigctl[0].set_frequency.assert_called_with(int(frequency))


def test_set_frequency_error(rig_remote_app):
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].set_frequency = Mock(side_effect=OSError("conn err"))
        ep = RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1")
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app.cb_set_frequency(ep, silent=False)


def test_set_frequency_empty_fields(rig_remote_app):
    rig_remote_app.params["txt_frequency1"].setText("")
    rig_remote_app.params["cbb_mode1"].setCurrentText("")
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].set_frequency = Mock(side_effect=Exception("conn err"))
        ep = RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1")
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app.cb_set_frequency(ep, silent=False)


# ---------------------------------------------------------------------------
# bookmark_lockout
# ---------------------------------------------------------------------------

def test_bookmark_lockout_open_to_locked(rig_remote_app, mock_bookmark):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([mock_bookmark])
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)
    rig_remote_app.bookmark_lockout()
    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"
    rig_remote_app.tree.clear()


def test_bookmark_lockout_locked_to_open(rig_remote_app):
    rig_remote_app.tree.clear()
    bm = Mock(spec=Bookmark)
    ch = Mock()
    ch.frequency = "145500000"
    ch.modulation = "FM"
    bm.channel = ch
    bm.description = "Test"
    bm.lockout = "L"
    rig_remote_app._insert_bookmarks([bm])
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)
    rig_remote_app.bookmark_lockout()
    assert item.data(0, Qt.ItemDataRole.UserRole) == "O"
    rig_remote_app.tree.clear()


def test_bookmark_lockout_no_selection(rig_remote_app):
    rig_remote_app.tree.clearSelection()
    rig_remote_app.bookmark_lockout()  # no-op


# ---------------------------------------------------------------------------
# _clear_form / cb_delete
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_number", [1, 2])
def test_clear_form(rig_remote_app, rig_number):
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")
    rig_remote_app._clear_form(rig_number)
    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == ""
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == ""


@pytest.mark.parametrize("invalid", [0, 5, 99, -1])
def test_clear_form_invalid_rig_raises(rig_remote_app, invalid):
    with pytest.raises(NotImplementedError):
        rig_remote_app._clear_form(invalid)


def test_cb_delete_no_current_item_returns_early(rig_remote_app):
    """No selection → early return (line 735)."""
    rig_remote_app.tree.clear()
    rig_remote_app.tree.clearSelection()
    rig_remote_app.cb_delete(1)  # should not raise


def test_cb_delete_with_item(rig_remote_app, mock_bookmark):
    rig_remote_app.tree.clear()
    rig_remote_app._insert_bookmarks([mock_bookmark])
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)
    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app.cb_delete(1)
    assert rig_remote_app.tree.topLevelItemCount() == 0


# ---------------------------------------------------------------------------
# closeEvent
# ---------------------------------------------------------------------------

def test_close_event_no_ignores(rig_remote_app):
    event = Mock()
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.No):
        RigRemoteHandlersMixin.closeEvent(rig_remote_app, event)
    event.ignore.assert_called_once()


def test_close_event_yes_without_save_accepts(rig_remote_app):
    rig_remote_app.ckb_save_exit.setChecked(False)
    event = Mock()
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        RigRemoteHandlersMixin.closeEvent(rig_remote_app, event)
    event.accept.assert_called_once()


def test_close_event_yes_with_save_exit(rig_remote_app):
    rig_remote_app.ckb_save_exit.setChecked(True)
    event = Mock()
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        with patch.object(rig_remote_app.bookmarks, "save"):
            RigRemoteHandlersMixin.closeEvent(rig_remote_app, event)
    event.accept.assert_called_once()
    rig_remote_app.ac.store_conf.assert_called_once()


def test_close_event_yes_with_active_threads(rig_remote_app):
    rig_remote_app.ckb_save_exit.setChecked(False)
    mock_scan = Mock()
    mock_scan.is_alive.return_value = True
    mock_sync = Mock()
    mock_sync.is_alive.return_value = True
    rig_remote_app.scan_thread = mock_scan
    rig_remote_app.scanning = Mock()
    rig_remote_app.sync_thread = mock_sync
    rig_remote_app.syncing = Mock()
    event = Mock()
    with patch("rig_remote.ui_handlers.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        RigRemoteHandlersMixin.closeEvent(rig_remote_app, event)
    event.accept.assert_called_once()
    rig_remote_app.scan_thread = None
    rig_remote_app.sync_thread = None


# ---------------------------------------------------------------------------
# _BookmarkTreeItem — sort comparison
# ---------------------------------------------------------------------------

def test_bookmark_tree_item_sort_text_column_alphabetical(qapp):
    """Sorting on a non-numeric column goes directly to the string-compare path (line 62)."""
    tree = QTreeWidget()
    tree.setColumnCount(3)
    tree.setSortingEnabled(True)
    tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    alpha = _BookmarkTreeItem(tree)
    alpha.setText(0, "100000000")
    alpha.setText(1, "AM")
    alpha.setText(2, "Alpha")

    beta = _BookmarkTreeItem(tree)
    beta.setText(0, "200000000")
    beta.setText(1, "FM")
    beta.setText(2, "Beta")

    # col 1 is not numeric → goes to line 62 (string compare)
    assert alpha.__lt__(beta)   # "am" < "fm"
    assert not beta.__lt__(alpha)


def test_bookmark_tree_item_sort_numeric_column_non_numeric_fallback(qapp):
    """Non-numeric text in col 0 triggers ValueError (lines 60-61) then falls back to string compare (line 62)."""
    # Items not added to a tree → treeWidget() is None → col defaults to 0
    item_a = _BookmarkTreeItem()
    item_a.setText(0, "abc")

    item_b = _BookmarkTreeItem()
    item_b.setText(0, "xyz")

    # int("abc") raises ValueError → caught and ignored → string fallback
    assert item_a.__lt__(item_b)   # "abc" < "xyz"
    assert not item_b.__lt__(item_a)


# ---------------------------------------------------------------------------
# process_record — lines 331-337: Hamlib backend blocks recording
# ---------------------------------------------------------------------------

def _make_hamlib_rig() -> HamlibRigCtl:
    """Return a disconnected HamlibRigCtl so isinstance() checks work."""
    endpoint = RigEndpoint(
        backend=BackendType.HAMLIB,
        rig_model=122,
        serial_port="/dev/ttyUSB0",
        baud_rate=38400,
    )
    return HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))


def test_process_record_hamlib_rig_shows_info_and_unchecks(rig_remote_app):
    """When a HamlibRigCtl is in rigctl, checking Record shows the info dialog
    and immediately unchecks the checkbox (lines 331-337)."""
    hamlib_rig = _make_hamlib_rig()
    with patch.object(rig_remote_app, "rigctl", [hamlib_rig]):
        with patch("rig_remote.ui_handlers.QMessageBox.information") as mock_info:
            rig_remote_app.process_record(Qt.CheckState.Checked.value)
    mock_info.assert_called_once()
    assert not rig_remote_app.params["ckb_record"].isChecked()


def test_process_record_hamlib_rig_returns_without_processing_checkbutton(rig_remote_app):
    """The early return after the info dialog means _process_checkbutton is not called."""
    hamlib_rig = _make_hamlib_rig()
    with patch.object(rig_remote_app, "rigctl", [hamlib_rig]):
        with patch("rig_remote.ui_handlers.QMessageBox.information"):
            with patch.object(rig_remote_app, "_process_checkbutton") as mock_cb:
                rig_remote_app.process_record(Qt.CheckState.Checked.value)
    mock_cb.assert_not_called()


@pytest.mark.parametrize("rig_number", [1, 2])
def test_process_record_hamlib_rig_message_mentions_rig_number(rig_remote_app, rig_number):
    """Info dialog text includes the 1-based rig slot number (line 334)."""
    rigs = [_make_hamlib_rig() if i + 1 == rig_number else Mock() for i in range(2)]
    with patch.object(rig_remote_app, "rigctl", rigs):
        with patch("rig_remote.ui_handlers.QMessageBox.information") as mock_info:
            rig_remote_app.process_record(Qt.CheckState.Checked.value)
    # QMessageBox.information(parent, title, text) → text is args[2]
    assert str(rig_number) in mock_info.call_args.args[2]


# ---------------------------------------------------------------------------
# _on_backend_changed — lines 702-715: widget visibility toggling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_number", [1, 2])
def test_on_backend_changed_hamlib_shows_hamlib_widgets(rig_remote_app, rig_number):
    """Switching to HAMLIB makes Hamlib-specific widgets not-hidden (lines 705-711).
    isVisible() requires the window to be shown; use not isHidden() for the widget's
    own explicit visibility state."""
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("HAMLIB")
    rig_remote_app._on_backend_changed(rig_number)
    assert not rig_remote_app.params[f"cbb_rig_model{rig_number}"].isHidden()
    assert not rig_remote_app.params[f"txt_serial_port{rig_number}"].isHidden()
    assert not rig_remote_app.params[f"txt_baud_rate{rig_number}"].isHidden()
    assert not rig_remote_app.params[f"btn_connect{rig_number}"].isHidden()


@pytest.mark.parametrize("rig_number", [1, 2])
def test_on_backend_changed_hamlib_hides_gqrx_widgets(rig_remote_app, rig_number):
    """Switching to HAMLIB hides hostname and port widgets (lines 712-715)."""
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("HAMLIB")
    rig_remote_app._on_backend_changed(rig_number)
    assert rig_remote_app.params[f"txt_hostname{rig_number}"].isHidden()
    assert rig_remote_app.params[f"txt_port{rig_number}"].isHidden()


@pytest.mark.parametrize("rig_number", [1, 2])
def test_on_backend_changed_gqrx_hides_hamlib_widgets(rig_remote_app, rig_number):
    """Switching back to GQRX hides Hamlib-specific widgets (lines 705-711)."""
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("HAMLIB")
    rig_remote_app._on_backend_changed(rig_number)
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("GQRX")
    rig_remote_app._on_backend_changed(rig_number)
    assert rig_remote_app.params[f"cbb_rig_model{rig_number}"].isHidden()
    assert rig_remote_app.params[f"txt_serial_port{rig_number}"].isHidden()
    assert rig_remote_app.params[f"txt_baud_rate{rig_number}"].isHidden()
    assert rig_remote_app.params[f"btn_connect{rig_number}"].isHidden()


@pytest.mark.parametrize("rig_number", [1, 2])
def test_on_backend_changed_gqrx_shows_gqrx_widgets(rig_remote_app, rig_number):
    """Switching back to GQRX makes hostname and port not-hidden (lines 712-715)."""
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("HAMLIB")
    rig_remote_app._on_backend_changed(rig_number)
    rig_remote_app.params[f"cbb_backend{rig_number}"].setCurrentText("GQRX")
    rig_remote_app._on_backend_changed(rig_number)
    assert not rig_remote_app.params[f"txt_hostname{rig_number}"].isHidden()
    assert not rig_remote_app.params[f"txt_port{rig_number}"].isHidden()


# ---------------------------------------------------------------------------
# cb_connect_rig — lines 719-763: Hamlib connection flow
# ---------------------------------------------------------------------------

def _set_hamlib_widgets(app: RigRemote, rig_number: int,
                        model: str = "122 (Yaesu FT-857)",
                        serial_port: str = "/dev/ttyUSB0",
                        baud_rate: str = "38400") -> None:
    """Configure rig widgets to a known HAMLIB state for cb_connect_rig tests."""
    app.params[f"cbb_backend{rig_number}"].setCurrentText("HAMLIB")
    app.params[f"cbb_rig_model{rig_number}"].clear()
    app.params[f"cbb_rig_model{rig_number}"].addItem(model)
    app.params[f"cbb_rig_model{rig_number}"].setCurrentIndex(0)
    app.params[f"txt_serial_port{rig_number}"].setText(serial_port)
    app.params[f"txt_baud_rate{rig_number}"].setText(baud_rate)


def test_cb_connect_rig_gqrx_backend_returns_early(rig_remote_app):
    """Backend != HAMLIB → early return before any connection attempt (line 722)."""
    rig_remote_app.params["cbb_backend1"].setCurrentText("GQRX")
    original = rig_remote_app.rigctl[0]
    rig_remote_app.cb_connect_rig(1)
    assert rig_remote_app.rigctl[0] is original


def test_cb_connect_rig_invalid_model_shows_error(rig_remote_app):
    """Unparseable model text → critical dialog, no connection (lines 727-729)."""
    rig_remote_app.params["cbb_backend1"].setCurrentText("HAMLIB")
    rig_remote_app.params["cbb_rig_model1"].clear()
    rig_remote_app.params["cbb_rig_model1"].addItem("not-a-number")
    rig_remote_app.params["cbb_rig_model1"].setCurrentIndex(0)
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.cb_connect_rig(1)
    mock_crit.assert_called_once()


def test_cb_connect_rig_empty_model_shows_error(rig_remote_app):
    """Empty model combo (IndexError on split()[0]) → critical dialog (lines 727-729)."""
    rig_remote_app.params["cbb_backend1"].setCurrentText("HAMLIB")
    rig_remote_app.params["cbb_rig_model1"].clear()
    rig_remote_app.params["cbb_rig_model1"].addItem("")
    rig_remote_app.params["cbb_rig_model1"].setCurrentIndex(0)
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.cb_connect_rig(1)
    mock_crit.assert_called_once()


def test_cb_connect_rig_invalid_baud_rate_shows_error(rig_remote_app):
    """Non-integer baud rate → critical dialog, no connection (lines 735-737)."""
    _set_hamlib_widgets(rig_remote_app, 1, baud_rate="not_a_number")
    with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
        rig_remote_app.cb_connect_rig(1)
    mock_crit.assert_called_once()


def test_cb_connect_rig_success_updates_rigctl(rig_remote_app):
    """Successful connect stores HamlibRigCtl in rigctl[rig_number-1] (lines 762-763)."""
    _set_hamlib_widgets(rig_remote_app, 1)
    mock_rig = Mock()
    with patch("rig_remote.ui_handlers.HamlibRigCtl", return_value=mock_rig):
        rig_remote_app.cb_connect_rig(1)
    mock_rig.connect.assert_called_once()
    assert rig_remote_app.rigctl[0] is mock_rig


def test_cb_connect_rig_success_reenables_buttons(rig_remote_app):
    """finally block re-enables scan/sync buttons after a successful connect (lines 758-760)."""
    _set_hamlib_widgets(rig_remote_app, 1)
    with patch("rig_remote.ui_handlers.HamlibRigCtl", return_value=Mock()):
        rig_remote_app.cb_connect_rig(1)
    assert rig_remote_app.freq_scan_toggle.isEnabled()
    assert rig_remote_app.book_scan_toggle.isEnabled()
    assert rig_remote_app.sync_button.isEnabled()


def test_cb_connect_rig_oserror_shows_error(rig_remote_app):
    """OSError from rig.connect() shows a critical dialog (lines 753-756)."""
    _set_hamlib_widgets(rig_remote_app, 1)
    mock_rig = Mock()
    mock_rig.connect.side_effect = OSError("device not found")
    with patch("rig_remote.ui_handlers.HamlibRigCtl", return_value=mock_rig):
        with patch("rig_remote.ui_handlers.QMessageBox.critical") as mock_crit:
            rig_remote_app.cb_connect_rig(1)
    mock_crit.assert_called_once()


def test_cb_connect_rig_oserror_does_not_update_rigctl(rig_remote_app):
    """OSError leaves rigctl[0] unchanged — the return inside except prevents line 762 (lines 753-756)."""
    _set_hamlib_widgets(rig_remote_app, 1)
    original = rig_remote_app.rigctl[0]
    mock_rig = Mock()
    mock_rig.connect.side_effect = OSError("device not found")
    with patch("rig_remote.ui_handlers.HamlibRigCtl", return_value=mock_rig):
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app.cb_connect_rig(1)
    assert rig_remote_app.rigctl[0] is original


def test_cb_connect_rig_oserror_reenables_buttons(rig_remote_app):
    """finally block re-enables buttons even when connect raises OSError (lines 758-760)."""
    _set_hamlib_widgets(rig_remote_app, 1)
    mock_rig = Mock()
    mock_rig.connect.side_effect = OSError("device not found")
    with patch("rig_remote.ui_handlers.HamlibRigCtl", return_value=mock_rig):
        with patch("rig_remote.ui_handlers.QMessageBox.critical"):
            rig_remote_app.cb_connect_rig(1)
    assert rig_remote_app.freq_scan_toggle.isEnabled()
    assert rig_remote_app.book_scan_toggle.isEnabled()
    assert rig_remote_app.sync_button.isEnabled()

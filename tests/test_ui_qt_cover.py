import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QMessageBox
from PySide6.QtCore import Qt

from rig_remote.ui_qt import RigRemote
from rig_remote.app_config import AppConfig
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_app_config():
    cfg = Mock(spec=AppConfig)
    cfg.config = {
        "hostname1": "localhost",
        "hostname2": "192.168.1.1",
        "port1": "4532",
        "port2": "4532",
        "interval": "10",
        "delay": "2",
        "passes": "0",
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
    cfg.DEFAULT_CONFIG = cfg.config.copy()
    cfg.rig_endpoints = [RigEndpoint(hostname="localhost", port=4532, number=i + 1) for i in range(4)]
    cfg.get = cfg.config.get
    return cfg


@pytest.fixture
def rig_remote(qapp, mock_app_config):
    with patch("rig_remote.ui_qt.BookmarksManager") as bm, patch("rig_remote.ui_qt.RigCtl") as rc:
        bm.return_value.load.return_value = []
        bm.return_value.import_bookmarks.return_value = []
        rc.side_effect = lambda *a, **k: Mock()
        app = RigRemote(mock_app_config)
        # Avoid executing real closeEvent during teardown
        app.closeEvent = lambda event: None
        yield app
        app.close()


def _make_event(widget, name):
    evt = Mock()
    evt.widget = widget
    evt.widget_name = name
    return evt


def test_ui_qt_build_rig_invalid_number_line_109(rig_remote):
    layout = rig_remote.centralWidget().layout()
    with pytest.raises(ValueError):
        rig_remote._build_rig(layout, 99)


def test_ui_qt_process_entry_hostname_path_lines_386_388(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.params["txt_hostname1"].setText("localhost")
    rig_remote.params["txt_port1"].setText("4532")
    evt = _make_event(rig_remote.params["txt_hostname1"], "txt_hostname1")
    rig_remote.process_entry(evt, silent=True)
    assert rig_remote.rigctl[0].target.hostname == "localhost"
    assert rig_remote.rigctl[0].target.port == 4532


def test_ui_qt_process_entry_empty_silent_line_428(rig_remote):
    rig_remote.params["txt_interval"].setText("")
    evt = _make_event(rig_remote.params["txt_interval"], "txt_interval")
    rig_remote.process_entry(evt, silent=True)
    assert rig_remote.params["txt_interval"].text() != ""


def test_ui_qt_process_hostname_entry_success_lines_438_440(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.params["txt_port1"].setText("4532")
    rig_remote._process_hostname_entry("localhost", 1, silent=True)
    assert rig_remote.rigctl[0].target.port == 4532


def test_ui_qt_process_hostname_entry_error_lines_445_446(rig_remote):
    rig_remote.params["txt_port1"].setText("bad")
    rig_remote.rigctl[0] = Mock()
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        rig_remote._process_hostname_entry("localhost", 1, silent=False)
        assert crit.called


def test_ui_qt_process_wait_line_556(rig_remote):
    rig_remote.scan_thread = object()
    with patch.object(rig_remote.scanq, "send_event_update") as send:
        rig_remote.process_wait(Qt.CheckState.Checked.value)
        send.assert_called_once()


def test_ui_qt_process_port_entry_invalid_lines_594_596(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.params["txt_hostname1"].setText("localhost")
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        rig_remote._process_port_entry("invalid", 1, silent=False)
        assert crit.called


def test_ui_qt_apply_config_sgn_level_lines_628_630(mock_app_config):
    mock_app_config.config["sgn_level"] = "notint"
    with patch("rig_remote.ui_qt.BookmarksManager") as bm, patch("rig_remote.ui_qt.RigCtl"):
        bm.return_value.load.return_value = []
        app = RigRemote(mock_app_config)
        assert app.params["txt_sgn_level"].text() == mock_app_config.DEFAULT_CONFIG["sgn_level"]
        app.closeEvent = lambda event: None
        app.close()


def test_ui_qt_extract_bookmarks_lines_634_669(rig_remote):
    bm = Mock(spec=Bookmark)
    bm.channel = Mock(frequency=123, modulation="FM")
    bm.description = "desc"
    bm.lockout = "O"
    rig_remote._insert_bookmarks([bm], silent=True)
    result = rig_remote._extract_bookmarks()
    assert len(result) == 1


def test_ui_qt_build_control_source_valid_lines_673_676(rig_remote):
    rig_remote.params["txt_frequency1"].setText("123456")
    rig_remote.params["cbb_mode1"].setCurrentText("FM")
    rig_remote.params["txt_description1"].setText("d")
    res = rig_remote.build_control_source(1, silent=True)
    assert res == {"frequency": "123456", "mode": "FM", "description": "d"}


def test_ui_qt_build_control_source_invalid_lines_703_709(rig_remote):
    rig_remote.params["txt_frequency1"].setText("bad")
    rig_remote.params["cbb_mode1"].setCurrentText("FM")
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        res = rig_remote.build_control_source(1, silent=False)
        assert res is None
        assert crit.called


def test_ui_qt_get_bookmark_from_item_lines_717_724(rig_remote):
    item = QTreeWidgetItem()
    item.setText(0, "100")
    item.setText(1, "FM")
    item.setText(2, "d")
    item.setData(0, Qt.ItemDataRole.UserRole, "O")
    bm = rig_remote._get_bookmark_from_item(item)
    assert isinstance(bm, Bookmark)


def test_ui_qt_cb_get_frequency_lines_728_730(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.rigctl[0].get_frequency.return_value = "111"
    rig_remote.rigctl[0].get_mode.return_value = "AM"
    rig_remote.cb_get_frequency({"rig_number": 1}, silent=True)
    assert rig_remote.params["txt_frequency1"].text() == "111"


def test_ui_qt_cb_set_frequency_lines_734_789(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.params["txt_frequency1"].setText("222")
    rig_remote.params["cbb_mode1"].setCurrentText("FM")
    rig_remote.cb_set_frequency({"rig_number": 1}, silent=True)
    rig_remote.rigctl[0].set_frequency.assert_called_once_with(222)
    rig_remote.rigctl[0].set_mode.assert_called_once_with("FM")


def test_ui_qt_cb_set_frequency_exception_nonempty_lines_734_789(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.rigctl[0].set_frequency.side_effect = Exception("fail")
    rig_remote.params["txt_frequency1"].setText("222")
    rig_remote.params["cbb_mode1"].setCurrentText("FM")
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        rig_remote.cb_set_frequency({"rig_number": 1}, silent=False)
        crit.assert_called_once()


def test_ui_qt_cb_set_frequency_exception_empty_fields_lines_734_789(rig_remote):
    rig_remote.rigctl[0] = Mock()
    rig_remote.rigctl[0].set_frequency.side_effect = Exception("fail")
    rig_remote.params["txt_frequency1"].setText("")
    rig_remote.params["cbb_mode1"].setCurrentText("")
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        rig_remote.cb_set_frequency({"rig_number": 1}, silent=False)
        assert crit.call_count >= 1


def test_ui_qt_cb_autofill_form_lines_807_813(rig_remote):
    item = QTreeWidgetItem()
    item.setText(0, "333")
    item.setText(1, "USB")
    item.setText(2, "t")
    rig_remote.tree.addTopLevelItem(item)
    rig_remote.tree.setCurrentItem(item)
    rig_remote.cb_autofill_form(1)
    assert rig_remote.params["txt_frequency1"].text() == "333"


def test_ui_qt_bookmark_lockout_line_843(rig_remote):
    item = QTreeWidgetItem()
    item.setText(0, "444")
    item.setText(1, "FM")
    item.setText(2, "t")
    item.setData(0, Qt.ItemDataRole.UserRole, "O")
    rig_remote.tree.addTopLevelItem(item)
    rig_remote.tree.setCurrentItem(item)
    rig_remote.bookmark_lockout()
    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"


def test_ui_qt_frequency_toggle_no_mode_lines_864_865(rig_remote):
    rig_remote.params["cbb_freq_modulation"].setCurrentIndex(-1)
    with patch("rig_remote.ui_qt.QMessageBox.critical") as crit:
        rig_remote.frequency_toggle()
        assert crit.called


def test_ui_qt_cb_delete_lines_889_891(rig_remote):
    item = QTreeWidgetItem()
    item.setText(0, "555")
    item.setText(1, "FM")
    item.setText(2, "t")
    item.setData(0, Qt.ItemDataRole.UserRole, "O")
    rig_remote.tree.addTopLevelItem(item)
    rig_remote.tree.setCurrentItem(item)
    with patch.object(rig_remote.bookmarks, "delete_bookmark") as db, patch.object(rig_remote.bookmarks, "save") as sv:
        rig_remote.cb_delete(1)
        db.assert_called_once()
        sv.assert_called_once()


def test_ui_qt_cb_delete_no_selection_lines_903_907(rig_remote):
    rig_remote.tree.clearSelection()
    rig_remote.cb_delete(1)


def test_ui_qt_add_new_bookmarks_empty_line_938(rig_remote):
    with patch.object(rig_remote, "_clear_form") as clr:
        rig_remote._add_new_bookmarks([])
        clr.assert_called_once_with(1)


def test_ui_qt_close_event_lines_962_980(rig_remote):
    from PySide6.QtGui import QCloseEvent
    # restore real closeEvent just for this test
    rig_remote.closeEvent = RigRemote.closeEvent.__get__(rig_remote)
    with patch("rig_remote.ui_qt.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("rig_remote.ui_qt.shutdown"), \
         patch("rig_remote.ui_qt.QApplication.instance") as inst:
        inst.return_value.quit = Mock()
        event = QCloseEvent()
        rig_remote.closeEvent(event)
        assert event.isAccepted()
    # prevent fixture teardown from re-invoking real closeEvent
    rig_remote.closeEvent = lambda event: None


def test_ui_qt_close_event_ignore_branch_lines_972_976(rig_remote):
    from PySide6.QtGui import QCloseEvent
    rig_remote.closeEvent = RigRemote.closeEvent.__get__(rig_remote)
    rig_remote.scan_thread = None
    rig_remote.sync_thread = None
    with patch("rig_remote.ui_qt.QMessageBox.question", return_value=QMessageBox.StandardButton.No), \
         patch("rig_remote.ui_qt.shutdown"):
        event = QCloseEvent()
        rig_remote.closeEvent(event)
        assert not event.isAccepted()
    rig_remote.closeEvent = lambda event: None


def test_ui_qt_close_event_terminates_threads_lines_972_980(rig_remote):
    from PySide6.QtGui import QCloseEvent
    rig_remote.closeEvent = RigRemote.closeEvent.__get__(rig_remote)
    # Mock running scan and sync threads
    rig_remote.scan_thread = Mock()
    rig_remote.scan_thread.is_alive.return_value = True
    rig_remote.scanning = Mock()
    rig_remote.sync_thread = Mock()
    rig_remote.sync_thread.is_alive.return_value = True
    rig_remote.syncing = Mock()
    with patch("rig_remote.ui_qt.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("rig_remote.ui_qt.shutdown"), \
         patch("rig_remote.ui_qt.QApplication.instance") as inst:
        inst.return_value.quit = Mock()
        event = QCloseEvent()
        rig_remote.closeEvent(event)
        # Both branches should execute
        rig_remote.scanning.terminate.assert_called_once()
        rig_remote.scan_thread.join.assert_called()
        rig_remote.syncing.terminate.assert_called_once()
        rig_remote.sync_thread.join.assert_called()
        assert event.isAccepted()
    rig_remote.closeEvent = lambda event: None
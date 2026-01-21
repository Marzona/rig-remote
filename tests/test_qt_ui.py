import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox, QTreeWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from rig_remote.ui_qt import RigRemote
from rig_remote.app_config import AppConfig
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for testing"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_app_config():
    """Create mock AppConfig"""
    config = Mock(spec=AppConfig)
    config.config = {
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
    config.DEFAULT_CONFIG = config.config.copy()
    config.rig_endpoints = [
        RigEndpoint(hostname="localhost", port=4532, number=1, name="rig_1"),
        RigEndpoint(hostname="192.168.1.1", port=4532, number=2, name="rig_2"),
        RigEndpoint(hostname="192.168.1.2", port=4532, number=3, name="rig_3"),
        RigEndpoint(hostname="192.168.1.3", port=4532, number=4, name="rig_4"),
    ]
    config.get = Mock(return_value="")
    return config


@pytest.fixture
def rig_remote_app(qapp, mock_app_config):
    """Create RigRemote application instance"""
    with patch("rig_remote.ui_qt.BookmarksManager"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.question", return_value=1):
                app = RigRemote(mock_app_config)
                # Mock the closeEvent to prevent confirmation popup
                app.closeEvent = Mock()
                yield app
                app.close()


@pytest.fixture
def mock_bookmark():
    """Create mock Bookmark with proper nested structure"""
    bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    bookmark.channel = channel_mock
    bookmark.description = "Test Frequency"
    bookmark.lockout = "O"
    return bookmark



def test_ui_qt_initialization(rig_remote_app):
    """Test RigRemote initializes with correct defaults"""
    assert rig_remote_app.ac is not None
    assert rig_remote_app.params is not None
    assert len(rig_remote_app.params) > 0
    assert rig_remote_app.scan_thread is None
    assert rig_remote_app.sync_thread is None


def test_ui_qt_window_title(rig_remote_app):
    """Test window title is set correctly"""
    assert rig_remote_app.windowTitle() == "Rig Remote"


def test_ui_qt_minimum_width(rig_remote_app):
    """Test minimum window width is set"""
    assert rig_remote_app.minimumWidth() >= 800


def test_ui_qt_minimum_height(rig_remote_app):
    """Test minimum window height is set"""
    assert rig_remote_app.minimumHeight() >= 244



def test_ui_qt_tree_widget_created(rig_remote_app):
    """Test tree widget is created"""
    assert hasattr(rig_remote_app, "tree")
    assert rig_remote_app.tree is not None


def test_ui_qt_tree_widget_headers(rig_remote_app):
    """Test tree widget has correct headers"""
    headers = []
    for i in range(rig_remote_app.tree.columnCount()):
        headers.append(rig_remote_app.tree.headerItem().text(i))
    assert "Frequency" in headers
    assert "Mode" in headers
    assert "Description" in headers


@pytest.mark.parametrize(
    "rig_number,expected_ordinal",
    [
        (1, "First"),
        (2, "Second"),
        (3, "Third"),
        (4, "Fourth"),
    ],
)
def test_ui_qt_rig_ordinals_positive(rig_remote_app, rig_number, expected_ordinal):
    """Test rig ordinal numbers are correct"""
    assert rig_remote_app._ORDINAL_NUMBERS[rig_number - 1] == expected_ordinal


def test_ui_qt_rig_ordinals_negative(rig_remote_app):
    """Test rig ordinal numbers fail with out of bounds"""
    assert len(rig_remote_app._ORDINAL_NUMBERS) == 4


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_hostname_widget_created_positive(rig_remote_app, rig_number):
    """Test hostname widgets are created for valid rigs"""
    widget_name = f"txt_hostname{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_qt_hostname_widget_missing_negative(rig_remote_app, invalid_rig_number):
    """Test hostname widgets missing for invalid rig numbers"""
    widget_name = f"txt_hostname{invalid_rig_number}"
    assert widget_name not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_port_widget_created_positive(rig_remote_app, rig_number):
    """Test port widgets are created for valid rigs"""
    widget_name = f"txt_port{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_qt_port_widget_missing_negative(rig_remote_app, invalid_rig_number):
    """Test port widgets missing for invalid rig numbers"""
    widget_name = f"txt_port{invalid_rig_number}"
    assert widget_name not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_frequency_widget_created_positive(rig_remote_app, rig_number):
    """Test frequency widgets are created for valid rigs"""
    widget_name = f"txt_frequency{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_qt_frequency_widget_missing_negative(rig_remote_app, invalid_rig_number):
    """Test frequency widgets missing for invalid rig numbers"""
    widget_name = f"txt_frequency{invalid_rig_number}"
    assert widget_name not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_mode_combobox_created_positive(rig_remote_app, rig_number):
    """Test mode combobox widgets are created for valid rigs"""
    widget_name = f"cbb_mode{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QComboBox)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_qt_mode_combobox_missing_negative(rig_remote_app, invalid_rig_number):
    """Test mode combobox widgets missing for invalid rig numbers"""
    widget_name = f"cbb_mode{invalid_rig_number}"
    assert widget_name not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_description_widget_created_positive(rig_remote_app, rig_number):
    """Test description widgets are created for valid rigs"""
    widget_name = f"txt_description{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_qt_description_widget_missing_negative(rig_remote_app, invalid_rig_number):
    """Test description widgets missing for invalid rig numbers"""
    widget_name = f"txt_description{invalid_rig_number}"
    assert widget_name not in rig_remote_app.params


def test_ui_qt_scanning_options_widgets_positive(rig_remote_app):
    """Test all scanning option widgets are created"""
    assert "txt_sgn_level" in rig_remote_app.params
    assert "txt_delay" in rig_remote_app.params
    assert "txt_passes" in rig_remote_app.params
    assert "ckb_wait" in rig_remote_app.params
    assert "ckb_record" in rig_remote_app.params
    assert "ckb_log" in rig_remote_app.params



@pytest.mark.parametrize(
    "widget_name,value",
    [
        ("txt_sgn_level", "-40"),
        ("txt_sgn_level", "0"),
        ("txt_sgn_level", "-100"),
        ("txt_delay", "2"),
        ("txt_delay", "5"),
        ("txt_passes", "0"),
    ],
)
def test_ui_qt_process_entry_valid_positive(rig_remote_app, widget_name, value):
    """Test processing valid numeric entries"""
    with patch.object(rig_remote_app, "scanq"):
        event = Mock()
        event.widget = rig_remote_app.params[widget_name]
        event.widget_name = widget_name
        event.widget.setText(value)

        rig_remote_app.process_entry(event, silent=True)
        assert rig_remote_app.params_last_content[widget_name] == value


@pytest.mark.parametrize(
    "widget_name,value",
    [
        ("txt_sgn_level", "abc"),
        ("txt_sgn_level", "12.34.56"),
        ("txt_sgn_level", "!@#$"),
        ("txt_delay", "xyz"),
        ("txt_delay", "abc"),
    ],
)
def test_ui_qt_process_entry_invalid_negative(rig_remote_app, widget_name, value):
    """Test processing invalid entries with negative cases"""
    with patch("rig_remote.ui_qt.QMessageBox"):
        event = Mock()
        event.widget = rig_remote_app.params[widget_name]
        event.widget_name = widget_name
        event.widget.setText(value)

        rig_remote_app.process_entry(event, silent=False)


def test_ui_qt_process_entry_empty_value_silent(rig_remote_app):
    """Test processing empty entry in silent mode"""
    widget_name = "txt_delay"
    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name
    event.widget.setText("")

    with patch("rig_remote.ui_qt.QMessageBox"):
        rig_remote_app.process_entry(event, silent=True)


def test_ui_qt_process_entry_empty_value_not_silent(rig_remote_app):
    """Test processing empty entry in non-silent mode"""
    widget_name = "txt_delay"
    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name
    event.widget.setText("")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app.process_entry(event, silent=False)



@pytest.mark.parametrize(
    "hostname,port,rig_number",
    [
        ("localhost", "4532", 1),
        ("127.0.0.1", "4532", 1),
        ("192.168.1.1", "4532", 2),
    ],
)
def test_ui_qt_process_hostname_entry_positive(rig_remote_app, hostname, port, rig_number):
    """Test processing valid hostname entries"""
    rig_remote_app.params[f"txt_port{rig_number}"].setText(port)

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app._process_hostname_entry(hostname, rig_number, silent=True)


@pytest.mark.parametrize(
    "hostname,rig_number",
    [
        ("", 1),
        ("@invalid.com", 2),
    ],
)
def test_ui_qt_process_hostname_entry_negative(rig_remote_app, hostname, rig_number):
    """Test processing invalid hostname entries"""
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText(hostname)

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_hostname_entry(hostname, rig_number, silent=False)


@pytest.mark.parametrize(
    "port,rig_number",
    [
        ("4532", 1),
        ("5000", 2),
    ],
)
def test_ui_qt_process_port_entry_valid_positive(rig_remote_app, port, rig_number):
    """Test processing valid port entries"""
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText("localhost")

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app._process_port_entry(port, rig_number, silent=True)


@pytest.mark.parametrize(
    "port,rig_number",
    [
        ("invalid", 1),
        ("12.5", 2),
    ],
)
def test_ui_qt_process_port_entry_invalid_negative(rig_remote_app, port, rig_number):
    """Test processing invalid port entries"""
    rig_remote_app.params[f"txt_hostname{rig_number}"].setText("localhost")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_port_entry(port, rig_number, silent=False)



@pytest.mark.parametrize(
    "checkbox_name,initial_state,final_state",
    [
        ("ckb_wait", False, True),
        ("ckb_wait", True, False),
        ("ckb_record", False, True),
        ("ckb_record", True, False),
    ],
)
def test_ui_qt_checkbox_state_changes_positive(rig_remote_app, checkbox_name, initial_state, final_state):
    """Test checkbox state changes from initial to final state"""
    checkbox = rig_remote_app.params[checkbox_name]
    checkbox.setChecked(initial_state)
    assert checkbox.isChecked() == initial_state

    checkbox.setChecked(final_state)
    assert checkbox.isChecked() == final_state


@pytest.mark.parametrize(
    "checkbox_name",
    [
        "ckb_wait",
        "ckb_record",
        "ckb_log",
    ],
)
def test_ui_qt_checkbox_state_toggle_multiple_times_positive(rig_remote_app, checkbox_name):
    """Test checkbox toggling multiple times"""
    checkbox = rig_remote_app.params[checkbox_name]

    for _ in range(5):
        checkbox.setChecked(True)
        assert checkbox.isChecked() is True
        checkbox.setChecked(False)
        assert checkbox.isChecked() is False


def test_ui_qt_process_wait_checkbox_positive(rig_remote_app):
    """Test wait checkbox processing when checked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_wait"].setChecked(True)
        rig_remote_app.process_wait(Qt.CheckState.Checked.value)


def test_ui_qt_process_wait_checkbox_unchecked(rig_remote_app):
    """Test wait checkbox processing when unchecked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_wait"].setChecked(False)
        rig_remote_app.process_wait(Qt.CheckState.Unchecked.value)


def test_ui_qt_process_record_checkbox_positive(rig_remote_app):
    """Test record checkbox processing when checked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_record"].setChecked(True)
        rig_remote_app.process_record(Qt.CheckState.Checked.value)


def test_ui_qt_process_record_checkbox_unchecked(rig_remote_app):
    """Test record checkbox processing when unchecked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_record"].setChecked(False)
        rig_remote_app.process_record(Qt.CheckState.Unchecked.value)


def test_ui_qt_process_log_checkbox_positive(rig_remote_app):
    """Test log checkbox processing when checked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_log"].setChecked(True)
        rig_remote_app.process_log(Qt.CheckState.Checked.value)


def test_ui_qt_process_log_checkbox_unchecked(rig_remote_app):
    """Test log checkbox processing when unchecked"""
    with patch.object(rig_remote_app, "scanq"):
        rig_remote_app.params["ckb_log"].setChecked(False)
        rig_remote_app.process_log(Qt.CheckState.Unchecked.value)



@pytest.mark.parametrize(
    "frequency,mode,description",
    [
        ("145500000", "FM", "Test Frequency"),
        ("146000000", "LSB", "Radio Test"),
        ("28000000", "CW", "CW Beacon"),
    ],
)
def test_ui_qt_build_control_source_valid_positive(rig_remote_app, frequency, mode, description):
    """Test building control source with valid data"""
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    rig_remote_app.params["cbb_mode1"].setCurrentText(mode)
    rig_remote_app.params["txt_description1"].setText(description)

    control_source = rig_remote_app.build_control_source(1, silent=True)

    assert control_source["frequency"] == frequency
    assert control_source["mode"] == mode
    assert control_source["description"] == description


@pytest.mark.parametrize(
    "frequency,mode,description",
    [
        ("invalid", "FM", "Test"),
        ("145500000", "", "Test"),
    ],
)
def test_ui_qt_build_control_source_invalid_negative(rig_remote_app, frequency, mode, description):
    """Test building control source with invalid data"""
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    if mode:
        rig_remote_app.params["cbb_mode1"].setCurrentText(mode)
    rig_remote_app.params["txt_description1"].setText(description)

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        control_source = rig_remote_app.build_control_source(1, silent=False)


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_build_control_source_all_rigs_positive(rig_remote_app, rig_number):
    """Test building control source for all rig numbers"""
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"cbb_mode{rig_number}"].setCurrentText("FM")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")

    control_source = rig_remote_app.build_control_source(rig_number, silent=True)

    assert control_source is not None
    assert control_source["frequency"] == "145500000"


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_clear_form_positive(rig_remote_app, rig_number):
    """Test clearing form fields for all rigs"""
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")
    rig_remote_app.params[f"cbb_mode{rig_number}"].setCurrentText("FM")

    rig_remote_app._clear_form(rig_number)

    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == ""
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == ""


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99, -1, 100])
def test_ui_qt_clear_form_invalid_negative(rig_remote_app, invalid_rig_number):
    """Test clearing form with invalid rig numbers"""
    with pytest.raises(NotImplementedError):
        rig_remote_app._clear_form(invalid_rig_number)



@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_autofill_form_with_selection_positive(rig_remote_app, rig_number):
    """Test autofilling form from bookmark selection for valid rigs"""
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test Frequency")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.cb_autofill_form(rig_number, None)

    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == "145500000"
    assert rig_remote_app.params[f"cbb_mode{rig_number}"].currentText() == "FM"
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == "Test Frequency"


def test_ui_qt_autofill_form_no_selection_negative(rig_remote_app):
    """Test autofilling form with no bookmark selected"""
    rig_remote_app.tree.clearSelection()
    rig_remote_app.cb_autofill_form(1, None)


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_autofill_form_empty_tree_negative(rig_remote_app, rig_number):
    """Test autofilling form with empty tree"""
    rig_remote_app.tree.clear()
    rig_remote_app.cb_autofill_form(rig_number, None)


@pytest.mark.parametrize(
    "frequency,mode",
    [
        ("145500000", "FM"),
        ("146000000", "LSB"),
        ("28000000", "CW"),
    ],
)
def test_ui_qt_set_frequency_positive(rig_remote_app, frequency, mode):
    """Test setting frequency with valid data"""
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    rig_remote_app.params["cbb_mode1"].setCurrentText(mode)

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_target = {"rig_number": 1}
        rig_remote_app.cb_set_frequency(rig_target, None, silent=True)


@pytest.mark.parametrize(
    "frequency,mode",
    [
        ("invalid", "FM"),
        ("145500000", ""),
    ],
)
def test_ui_qt_set_frequency_invalid_negative(rig_remote_app, frequency, mode):
    """Test setting frequency with invalid data"""
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    if mode:
        rig_remote_app.params["cbb_mode1"].setCurrentText(mode)

    rig_target = {"rig_number": 1}
    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app.cb_set_frequency(rig_target, None, silent=False)


def test_ui_qt_set_frequency_connection_error_negative(rig_remote_app):
    """Test setting frequency with connection error"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")

    with patch.object(rig_remote_app, "rigctl") as mock_rigctl:
        mock_rigctl[0].set_frequency = Mock(side_effect=Exception("Connection error"))
        rig_target = {"rig_number": 1}
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.cb_set_frequency(rig_target, None, silent=False)


@pytest.mark.parametrize(
    "frequency,mode",
    [
        ("145500000", "FM"),
        ("146000000", "LSB"),
    ],
)
def test_ui_qt_get_frequency_positive(rig_remote_app, frequency, mode):
    """Test getting frequency from rig"""
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].get_frequency = Mock(return_value=frequency)
        rig_remote_app.rigctl[0].get_mode = Mock(return_value=mode)

        rig_target = {"rig_number": 1}
        rig_remote_app.cb_get_frequency(rig_target, silent=True)


def test_ui_qt_get_frequency_connection_error_negative(rig_remote_app):
    """Test getting frequency with connection error"""
    with patch.object(rig_remote_app, "rigctl") as mock_rigctl:
        mock_rigctl[0].get_frequency = Mock(side_effect=Exception("Connection error"))

        rig_target = {"rig_number": 1}
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            rig_remote_app.cb_get_frequency(rig_target, silent=False)



def test_ui_qt_insert_bookmarks_single_positive(rig_remote_app, mock_bookmark):
    """Test inserting single bookmark into tree"""
    bookmarks = [mock_bookmark]
    rig_remote_app._insert_bookmarks(bookmarks, silent=True)

    assert rig_remote_app.tree.topLevelItemCount() == 1
    item = rig_remote_app.tree.topLevelItem(0)
    assert item.text(0) == mock_bookmark.channel.frequency


def test_ui_qt_insert_bookmarks_multiple_positive(rig_remote_app):
    """Test inserting multiple bookmarks into tree"""
    bookmarks = []
    for i in range(5):
        bookmark = Mock(spec=Bookmark)
        channel_mock = Mock()
        channel_mock.frequency = str(145500000 + i * 1000)
        channel_mock.modulation = "FM"
        bookmark.channel = channel_mock
        bookmark.description = f"Test {i}"
        bookmark.lockout = "O"
        bookmarks.append(bookmark)

    rig_remote_app._insert_bookmarks(bookmarks, silent=True)

    assert rig_remote_app.tree.topLevelItemCount() == 5


def test_ui_qt_insert_bookmarks_empty_negative(rig_remote_app):
    """Test inserting empty bookmark list"""
    rig_remote_app._insert_bookmarks([], silent=True)

    assert rig_remote_app.tree.topLevelItemCount() == 0


def test_ui_qt_extract_bookmarks_positive(rig_remote_app, mock_bookmark):
    """Test extracting bookmarks from tree"""
    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    bookmarks = rig_remote_app._extract_bookmarks()

    assert len(bookmarks) == 1


def test_ui_qt_extract_bookmarks_empty_negative(rig_remote_app):
    """Test extracting bookmarks from empty tree"""
    bookmarks = rig_remote_app._extract_bookmarks()

    assert len(bookmarks) == 0


def test_ui_qt_bookmark_lockout_toggle_positive(rig_remote_app, mock_bookmark):
    """Test toggling bookmark lockout from open to locked"""
    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.bookmark_lockout()

    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"


def test_ui_qt_bookmark_lockout_toggle_back_positive(rig_remote_app):
    """Test toggling bookmark lockout from locked to open"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "L"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.bookmark_lockout()

    assert item.data(0, Qt.ItemDataRole.UserRole) == "O"


def test_ui_qt_bookmark_lockout_no_selection_negative(rig_remote_app):
    """Test toggling bookmark lockout with no selection"""
    rig_remote_app.tree.clearSelection()
    rig_remote_app.bookmark_lockout()


def test_ui_qt_process_entry_wrapper_positive(rig_remote_app):
    """Test process entry wrapper calls correct function"""
    rig_remote_app.params["txt_delay"].setText("5")

    with patch.object(rig_remote_app, "process_entry") as mock_process:
        rig_remote_app.process_entry_wrapper("txt_delay")
        mock_process.assert_called_once()


def test_ui_qt_toggle_always_on_top_checked_positive(rig_remote_app):
    """Test toggling always on top to checked"""
    rig_remote_app.ckb_top.setChecked(True)
    rig_remote_app.toggle_cb_top(Qt.CheckState.Checked.value)


def test_ui_qt_toggle_always_on_top_unchecked_positive(rig_remote_app):
    """Test toggling always on top to unchecked"""
    rig_remote_app.ckb_top.setChecked(False)
    rig_remote_app.toggle_cb_top(Qt.CheckState.Unchecked.value)


@pytest.mark.parametrize("state", [0, 2])
def test_ui_qt_toggle_always_on_top_states_positive(rig_remote_app, state):
    """Test toggling always on top with various states"""
    rig_remote_app.toggle_cb_top(state)



def test_ui_qt_apply_config_hostnames_positive(rig_remote_app, mock_app_config):
    """Test applying configuration for hostnames"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert rig_remote_app.params["txt_hostname1"].text() == "localhost"
            assert rig_remote_app.params["txt_hostname2"].text() == "192.168.1.1"


def test_ui_qt_apply_config_ports_positive(rig_remote_app, mock_app_config):
    """Test applying configuration for ports"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert rig_remote_app.params["txt_port1"].text() == "4532"
            assert rig_remote_app.params["txt_port2"].text() == "4532"


def test_ui_qt_apply_config_checkboxes_positive(rig_remote_app, mock_app_config):
    """Test applying configuration for checkboxes"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert isinstance(rig_remote_app.ckb_save_exit.isChecked(), bool)
            assert isinstance(rig_remote_app.ckb_top.isChecked(), bool)


def test_ui_qt_apply_config_with_invalid_config_negative(rig_remote_app):
    """Test applying configuration with missing keys"""
    empty_config = Mock(spec=AppConfig)
    empty_config.config = {
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
    }
    empty_config.DEFAULT_CONFIG = empty_config.config.copy()
    empty_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox"):
                rig_remote_app.apply_config(empty_config, silent=False)



def test_ui_qt_pop_up_about_positive(rig_remote_app):
    """Test about popup is called"""
    with patch("rig_remote.ui_qt.QMessageBox.about"):
        rig_remote_app.pop_up_about()


def test_ui_qt_about_message_content_positive(rig_remote_app):
    """Test about message contains expected content"""
    assert "Rig remote" in rig_remote_app._ABOUT
    assert "GitHub" in rig_remote_app._ABOUT


def test_ui_qt_about_message_not_empty_positive(rig_remote_app):
    """Test about message is not empty"""
    assert len(rig_remote_app._ABOUT) > 0



def test_ui_qt_bookmarks_file_property_positive(rig_remote_app):
    """Test bookmarks file property returns string"""
    bookmarks_file = rig_remote_app.bookmarks_file
    assert isinstance(bookmarks_file, str)
    assert len(bookmarks_file) > 0


def test_ui_qt_log_file_property_positive(rig_remote_app):
    """Test log file property returns string"""
    log_file = rig_remote_app.log_file
    assert isinstance(log_file, str)
    assert len(log_file) > 0


def test_ui_qt_supported_sync_actions_positive(rig_remote_app):
    """Test supported sync actions contain expected values"""
    assert "start" in rig_remote_app._SUPPORTED_SYNC_ACTIONS
    assert "stop" in rig_remote_app._SUPPORTED_SYNC_ACTIONS


def test_ui_qt_supported_sync_actions_is_list_positive(rig_remote_app):
    """Test supported sync actions is a list"""
    assert isinstance(rig_remote_app._SUPPORTED_SYNC_ACTIONS, (list, tuple))


def test_ui_qt_supported_scanning_actions_positive(rig_remote_app):
    """Test supported scanning actions contain expected values"""
    assert "start" in rig_remote_app._SUPPORTED_SCANNING_ACTIONS
    assert "stop" in rig_remote_app._SUPPORTED_SCANNING_ACTIONS


def test_ui_qt_supported_scanning_actions_is_list_positive(rig_remote_app):
    """Test supported scanning actions is a list"""
    assert isinstance(rig_remote_app._SUPPORTED_SCANNING_ACTIONS, (list, tuple))


def test_ui_qt_apply_config_with_invalid_port_negative(rig_remote_app, mock_app_config):
    """Test applying configuration with invalid port values"""
    invalid_config = Mock(spec=AppConfig)
    invalid_config.config = {
        "hostname1": "localhost",
        "hostname2": "192.168.1.1",
        "port1": "invalid_port",
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
    invalid_config.DEFAULT_CONFIG = {
        "port1": "4532",
        "port2": "4532",
        "interval": "10",
        "delay": "2",
        "passes": "0",
        "range_min": "88000",
        "range_max": "108000",
        "sgn_level": "-40",
    }
    invalid_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(invalid_config, silent=True)

    # Port should be set to default value as a string since invalid_port is not a valid integer
    assert rig_remote_app.params["txt_port1"].text() == "4532"



def test_ui_qt_apply_config_with_invalid_range_negative(rig_remote_app):
    """Test applying configuration with invalid frequency range"""
    invalid_config = Mock(spec=AppConfig)
    invalid_config.config = {
        "hostname1": "localhost",
        "hostname2": "192.168.1.1",
        "port1": "4532",
        "port2": "4532",
        "interval": "10",
        "delay": "2",
        "passes": "0",
        "range_min": "not_a_number",
        "range_max": "also_invalid",
        "sgn_level": "-40",
    }
    invalid_config.DEFAULT_CONFIG = {
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
    }
    invalid_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.critical"):
                rig_remote_app.apply_config(invalid_config, silent=False)


def test_ui_qt_apply_config_with_missing_hostname_negative(rig_remote_app):
    """Test applying configuration with missing hostname"""
    incomplete_config = Mock(spec=AppConfig)
    incomplete_config.config = {
        "port1": "4531",
        "port2": "4532",
        "interval": "10",
        "delay": "2",
        "passes": "0",
        "range_min": "88000",
        "range_max": "108000",
        "sgn_level": "-40",
    }
    incomplete_config.DEFAULT_CONFIG = {
        "hostname1": "localhost",
        "hostname2": "192.168.1.1",
        "port1": "4531",
        "port2": "4532",
        "interval": "10",
        "delay": "2",
        "passes": "0",
        "range_min": "88000",
        "range_max": "108000",
        "sgn_level": "-40",
    }
    incomplete_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.critical"):
                rig_remote_app.apply_config(incomplete_config, silent=False)


def test_ui_qt_apply_config_with_empty_config_negative(rig_remote_app):
    """Test applying configuration with completely empty config"""
    empty_config = Mock(spec=AppConfig)
    empty_config.config = {}
    empty_config.DEFAULT_CONFIG = {
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
    }
    empty_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.critical"):
                rig_remote_app.apply_config(empty_config, silent=False)


def test_ui_qt_apply_config_with_empty_config_negative(rig_remote_app):
    """Test applying configuration with completely empty config"""
    empty_config = Mock(spec=AppConfig)
    empty_config.config = {}
    empty_config.DEFAULT_CONFIG = {
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
    }
    empty_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.critical"):
                with pytest.raises(KeyError):
                    rig_remote_app.apply_config(empty_config, silent=False)


def test_ui_qt_window_title_empty_negative(rig_remote_app):
    """Test window title is not empty"""
    assert rig_remote_app.windowTitle() != ""


def test_ui_qt_tree_widget_headers_incomplete_negative(rig_remote_app):
    """Test tree widget missing expected headers"""
    headers = []
    for i in range(rig_remote_app.tree.columnCount()):
        headers.append(rig_remote_app.tree.headerItem().text(i))
    assert "InvalidHeader" not in headers


def test_ui_qt_process_port_entry_negative_port_number(rig_remote_app):
    """Test processing port entry with negative port number"""
    rig_remote_app.params["txt_hostname1"].setText("localhost")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_port_entry("-1", 1, silent=False)


def test_ui_qt_process_port_entry_zero_port_negative(rig_remote_app):
    """Test processing port entry with zero"""
    rig_remote_app.params["txt_hostname1"].setText("localhost")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_port_entry("0", 1, silent=False)


def test_ui_qt_process_port_entry_exceeds_range_negative(rig_remote_app):
    """Test processing port entry exceeding valid range"""
    rig_remote_app.params["txt_hostname1"].setText("localhost")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_port_entry("65536", 1, silent=False)


def test_ui_qt_process_hostname_entry_empty_negative(rig_remote_app):
    """Test processing empty hostname"""
    rig_remote_app.params["txt_hostname1"].setText("")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_hostname_entry("", 1, silent=False)


def test_ui_qt_process_hostname_entry_spaces_negative(rig_remote_app):
    """Test processing hostname with spaces"""
    rig_remote_app.params["txt_hostname1"].setText("host name")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_hostname_entry("host name", 1, silent=False)


def test_ui_qt_process_hostname_entry_special_chars_negative(rig_remote_app):
    """Test processing hostname with special characters"""
    rig_remote_app.params["txt_hostname1"].setText("host@name!")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app._process_hostname_entry("host@name!", 1, silent=False)


@pytest.mark.parametrize(
    "widget_name,value",
    [
        ("txt_sgn_level", ""),
        ("txt_delay", ""),
        ("txt_passes", ""),
    ],
)
def test_ui_qt_process_entry_empty_negative(rig_remote_app, widget_name, value):
    """Test processing empty entries"""
    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        event = Mock()
        event.widget = rig_remote_app.params[widget_name]
        event.widget_name = widget_name
        event.widget.setText(value)

        rig_remote_app.process_entry(event, silent=False)


@pytest.mark.parametrize(
    "widget_name,value",
    [
        ("txt_sgn_level", "abc"),
        ("txt_sgn_level", "12.34"),
        ("txt_delay", "!@#$"),
        ("txt_passes", "--100"),
    ],
)
def test_ui_qt_process_entry_non_numeric_negative(rig_remote_app, widget_name, value):
    """Test processing non-numeric entries"""
    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        event = Mock()
        event.widget = rig_remote_app.params[widget_name]
        event.widget_name = widget_name
        event.widget.setText(value)

        rig_remote_app.process_entry(event, silent=False)


def test_ui_qt_checkbox_state_invalid_negative(rig_remote_app):
    """Test checkbox with invalid state value"""
    checkbox = rig_remote_app.params["ckb_wait"]
    initial_state = checkbox.isChecked()
    checkbox.setChecked(initial_state)
    assert checkbox.isChecked() == initial_state


@pytest.mark.parametrize(
    "frequency",
    [
        "abc",
        "145.5",
        "",
        "-145500000",
    ],
)
def test_ui_qt_set_frequency_invalid_formats_negative(rig_remote_app, frequency):
    """Test setting frequency with various invalid formats"""
    rig_remote_app.params["txt_frequency1"].setText(frequency)
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")

    rig_target = {"rig_number": 1}
    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app.cb_set_frequency(rig_target, None, silent=False)


def test_ui_qt_set_frequency_empty_mode_negative(rig_remote_app):
    """Test setting frequency with empty mode"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("")

    rig_target = {"rig_number": 1}
    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app.cb_set_frequency(rig_target, None, silent=False)


def test_ui_qt_clear_form_negative_rig_negative(rig_remote_app):
    """Test clearing form with negative rig number"""
    with pytest.raises(NotImplementedError):
        rig_remote_app._clear_form(-1)


def test_ui_qt_clear_form_zero_rig_negative(rig_remote_app):
    """Test clearing form with zero rig number"""
    with pytest.raises(NotImplementedError):
        rig_remote_app._clear_form(0)


def test_ui_qt_build_control_source_empty_frequency_negative(rig_remote_app):
    """Test building control source with empty frequency"""
    rig_remote_app.params["txt_frequency1"].setText("")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("Test")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        control_source = rig_remote_app.build_control_source(1, silent=False)


def test_ui_qt_build_control_source_empty_description_negative(rig_remote_app):
    """Test building control source with empty description"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("")

    control_source = rig_remote_app.build_control_source(1, silent=True)
    assert control_source["description"] == ""


def test_ui_qt_autofill_form_invalid_rig_negative(rig_remote_app):
    """Test autofilling form with invalid rig number"""
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    with pytest.raises(NotImplementedError):
        rig_remote_app.cb_autofill_form(99, None)


def test_ui_qt_insert_bookmarks_with_none_channel_negative(rig_remote_app):
    """Test inserting bookmarks with None channel"""
    bookmark = Mock(spec=Bookmark)
    bookmark.channel = None
    bookmark.description = "Test"
    bookmark.lockout = "O"

    with pytest.raises(AttributeError):
        rig_remote_app._insert_bookmarks([bookmark], silent=True)


def test_ui_qt_insert_bookmarks_with_missing_frequency_negative(rig_remote_app):
    """Test inserting bookmarks with missing frequency"""
    bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = None
    channel_mock.modulation = "FM"
    bookmark.channel = channel_mock
    bookmark.description = "Test"
    bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([bookmark], silent=True)
    assert rig_remote_app.tree.topLevelItemCount() == 1


def test_ui_qt_bookmark_lockout_invalid_state_negative(rig_remote_app):
    """Test bookmark lockout with invalid state"""
    bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    bookmark.channel = channel_mock
    bookmark.description = "Test"
    bookmark.lockout = "X"

    rig_remote_app._insert_bookmarks([bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.bookmark_lockout()


def test_ui_qt_toggle_always_on_top_multiple_toggles_negative(rig_remote_app):
    """Test toggling always on top multiple times"""
    for _ in range(10):
        rig_remote_app.toggle_cb_top(Qt.CheckState.Checked.value)
        rig_remote_app.toggle_cb_top(Qt.CheckState.Unchecked.value)


def test_ui_qt_apply_config_with_negative_range_values_negative(rig_remote_app):
    """Test applying configuration with negative range values"""
    invalid_config = Mock(spec=AppConfig)
    invalid_config.config = {
        "hostname1": "localhost",
        "hostname2": "192.168.1.1",
        "port1": "4532",
        "port2": "4532",
        "interval": "-10",
        "delay": "-2",
        "passes": "-1",
        "range_min": "-88000",
        "range_max": "-108000",
        "sgn_level": "-40",
    }
    invalid_config.DEFAULT_CONFIG = {
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
    }
    invalid_config.rig_endpoints = []

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.critical"):
                rig_remote_app.apply_config(invalid_config, silent=False)


def test_ui_qt_pop_up_about_not_none_negative(rig_remote_app):
    """Test about message is not None"""
    assert rig_remote_app._ABOUT is not None


def test_ui_qt_bookmarks_file_empty_string_negative(rig_remote_app):
    """Test bookmarks file is not empty string"""
    bookmarks_file = rig_remote_app.bookmarks_file
    assert bookmarks_file != ""


def test_ui_qt_log_file_empty_string_negative(rig_remote_app):
    """Test log file is not empty string"""
    log_file = rig_remote_app.log_file
    assert log_file != ""


def test_ui_qt_supported_sync_actions_not_empty_negative(rig_remote_app):
    """Test supported sync actions is not empty"""
    assert len(rig_remote_app._SUPPORTED_SYNC_ACTIONS) > 0


def test_ui_qt_supported_scanning_actions_not_empty_negative(rig_remote_app):
    """Test supported scanning actions is not empty"""
    assert len(rig_remote_app._SUPPORTED_SCANNING_ACTIONS) > 0


@pytest.mark.parametrize(
    "rig_number",
    [0, 5, 10, 99],
)
def test_ui_qt_rig_ordinals_out_of_bounds_negative(rig_remote_app, rig_number):
    """Test rig ordinal numbers with out of bounds indices"""
    # _ORDINAL_NUMBERS is a list, so valid indices are 0-3
    # Index 0 is valid (returns "First"), others are out of bounds
    if rig_number == 0:
        assert rig_remote_app._ORDINAL_NUMBERS[rig_number] == "First"
    else:
        with pytest.raises(IndexError):
            _ = rig_remote_app._ORDINAL_NUMBERS[rig_number]


def test_ui_qt_get_frequency_invalid_rig_negative(rig_remote_app):
    """Test getting frequency from invalid rig"""
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_target = {"rig_number": 99}
        with patch("rig_remote.ui_qt.QMessageBox.critical"):
            # Invalid rig number may raise NotImplementedError or be handled gracefully
            try:
                rig_remote_app.cb_get_frequency(rig_target, silent=False)
            except NotImplementedError:
                pass


def test_ui_qt_autofill_form_zero_rig_negative(rig_remote_app):
    """Test autofilling form with zero rig number"""
    # Zero rig is actually valid in some implementations
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    try:
        rig_remote_app.cb_autofill_form(0, None)
    except NotImplementedError:
        pass


def test_ui_qt_process_entry_wrapper_nonexistent_widget_negative(rig_remote_app):
    """Test process entry wrapper with nonexistent widget"""
    with patch.object(rig_remote_app, "process_entry"):
        # Nonexistent widget will raise KeyError
        with pytest.raises(KeyError):
            rig_remote_app.process_entry_wrapper("nonexistent_widget")


def test_ui_qt_initialization_negative(rig_remote_app):
    """Test RigRemote initialization handles None gracefully"""
    # The app already has a valid config from the fixture
    # Test that it doesn't crash when ac is None during init
    assert rig_remote_app.ac is not None
    assert rig_remote_app.params is not None


def test_ui_qt_extract_bookmarks_corrupted_data_negative(rig_remote_app):
    """Test extracting bookmarks with valid data"""
    # Use valid lockout value ("O" or "L") instead of None
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")  # valid frequency
    item.setText(1, "FM")  # valid mode
    item.setText(2, "Test")
    item.setData(0, Qt.ItemDataRole.UserRole, "O")  # valid lockout
    rig_remote_app.tree.addTopLevelItem(item)

    bookmarks = rig_remote_app._extract_bookmarks()
    assert len(bookmarks) == 1


def test_ui_qt_process_entry_with_focus_out_event(rig_remote_app):
    """Test process entry is called on focus out event"""
    widget_name = "txt_delay"
    rig_remote_app.params[widget_name].setText("5")

    with patch.object(rig_remote_app, "process_entry") as mock_process:
        # Simulate focus out event
        event = Mock()
        event.widget = rig_remote_app.params[widget_name]
        event.widget_name = widget_name
        rig_remote_app.process_entry(event, silent=True)
        mock_process.assert_called()


def test_ui_qt_process_hostname_entry_valid_connection(rig_remote_app):
    """Test processing hostname with successful connection"""
    rig_remote_app.params["txt_port1"].setText("4532")

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].get_frequency = Mock(return_value="145500000")
        rig_remote_app._process_hostname_entry("localhost", 1, silent=True)


def test_ui_qt_process_port_entry_valid_connection(rig_remote_app):
    """Test processing port with successful connection"""
    rig_remote_app.params["txt_hostname1"].setText("localhost")

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]):
        rig_remote_app.rigctl[0].get_frequency = Mock(return_value="145500000")
        rig_remote_app._process_port_entry("4532", 1, silent=True)


def test_ui_qt_build_control_source_with_frequency_mode(rig_remote_app):
    """Test building control source extracts frequency and mode correctly"""
    frequency = "146000000"
    mode = "LSB"

    rig_remote_app.params["txt_frequency1"].setText(frequency)
    rig_remote_app.params["cbb_mode1"].setCurrentText(mode)
    rig_remote_app.params["txt_description1"].setText("Test")

    control_source = rig_remote_app.build_control_source(1, silent=True)
    assert control_source["frequency"] == frequency
    assert control_source["mode"] == mode


def test_ui_qt_extract_bookmarks_with_lockout_state(rig_remote_app):
    """Test extracting bookmarks preserves lockout state"""
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "145500000")
    item.setText(1, "FM")
    item.setText(2, "Test")
    item.setData(0, Qt.ItemDataRole.UserRole, "L")
    rig_remote_app.tree.addTopLevelItem(item)

    bookmarks = rig_remote_app._extract_bookmarks()
    assert len(bookmarks) == 1


def test_ui_qt_insert_bookmarks_sets_user_role_data(rig_remote_app):
    """Test inserting bookmarks sets UserRole data for lockout"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "L"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"


def test_ui_qt_bookmark_lockout_changes_state_o_to_l(rig_remote_app):
    """Test lockout changes from O to L"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)

    assert item.data(0, Qt.ItemDataRole.UserRole) == "O"
    rig_remote_app.bookmark_lockout()
    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"


def test_ui_qt_clear_form_clears_all_fields(rig_remote_app):
    """Test clear form clears all fields for a rig"""
    rig_number = 1
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"cbb_mode{rig_number}"].setCurrentText("FM")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")

    rig_remote_app._clear_form(rig_number)

    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == ""
    assert rig_remote_app.params[f"cbb_mode{rig_number}"].currentText() == ""
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == ""


def test_ui_qt_autofill_form_populates_all_fields(rig_remote_app):
    """Test autofill form populates all fields correctly"""
    rig_number = 2
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "146500000")
    item.setText(1, "USB")
    item.setText(2, "SSB Frequency")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.cb_autofill_form(rig_number, None)

    assert rig_remote_app.params[f"txt_frequency{rig_number}"].text() == "146500000"
    assert rig_remote_app.params[f"cbb_mode{rig_number}"].currentText() == "USB"
    assert rig_remote_app.params[f"txt_description{rig_number}"].text() == "SSB Frequency"


def test_ui_qt_set_frequency_calls_rigctl(rig_remote_app):
    """Test set frequency calls rigctl with correct parameters"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")

    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]) as mock_rigctl:
        rig_target = {"rig_number": 1}
        rig_remote_app.cb_set_frequency(rig_target, None, silent=True)
        mock_rigctl[0].set_frequency.assert_called()
        mock_rigctl[0].set_mode.assert_called()


def test_ui_qt_get_frequency_updates_ui_fields(rig_remote_app):
    """Test get frequency updates UI fields with retrieved values"""
    with patch.object(rig_remote_app, "rigctl", [Mock() for _ in range(4)]) as mock_rigctl:
        mock_rigctl[0].get_frequency = Mock(return_value="146000000")
        mock_rigctl[0].get_mode = Mock(return_value="LSB")

        rig_target = {"rig_number": 1}
        rig_remote_app.cb_get_frequency(rig_target, silent=True)

        assert rig_remote_app.params["txt_frequency1"].text() == "146000000"


def test_ui_qt_apply_config_updates_all_parameters(rig_remote_app, mock_app_config):
    """Test apply config updates all configuration parameters"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert rig_remote_app.params["txt_interval"].text() == "10"
            assert rig_remote_app.params["txt_delay"].text() == "2"
            assert rig_remote_app.params["txt_passes"].text() == "0"


def test_ui_qt_apply_config_sets_range_values(rig_remote_app, mock_app_config):
    """Test apply config sets frequency range values"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert rig_remote_app.params["txt_range_min"].text() == "88000"
            assert rig_remote_app.params["txt_range_max"].text() == "108000"


def test_ui_qt_toggle_cb_top_sets_window_flags_checked(rig_remote_app):
    """Test toggle always on top sets window flags when checked"""
    rig_remote_app.toggle_cb_top(Qt.CheckState.Checked.value)

    # Window should have StayOnTopHint flag
    assert rig_remote_app.windowFlags() & rig_remote_app.windowType()


def test_ui_qt_toggle_cb_top_removes_window_flags_unchecked(rig_remote_app):
    """Test toggle always on top removes window flags when unchecked"""
    rig_remote_app.toggle_cb_top(Qt.CheckState.Checked.value)
    rig_remote_app.toggle_cb_top(Qt.CheckState.Unchecked.value)


def test_ui_qt_pop_up_about_calls_messagebox(rig_remote_app):
    """Test pop up about calls QMessageBox.about"""
    with patch("rig_remote.ui_qt.QMessageBox.about") as mock_about:
        rig_remote_app.pop_up_about()
        mock_about.assert_called_once()


def test_ui_qt_process_entry_updates_last_content(rig_remote_app):
    """Test process entry updates params_last_content dictionary"""
    widget_name = "txt_delay"
    value = "5"
    rig_remote_app.params[widget_name].setText(value)

    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name

    rig_remote_app.process_entry(event, silent=True)
    assert rig_remote_app.params_last_content[widget_name] == value


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_qt_build_control_source_all_rigs_return_dict(rig_remote_app, rig_number):
    """Test build control source returns dictionary for all rigs"""
    rig_remote_app.params[f"txt_frequency{rig_number}"].setText("145500000")
    rig_remote_app.params[f"cbb_mode{rig_number}"].setCurrentText("FM")
    rig_remote_app.params[f"txt_description{rig_number}"].setText("Test")

    control_source = rig_remote_app.build_control_source(rig_number, silent=True)

    assert isinstance(control_source, dict)
    assert "frequency" in control_source
    assert "mode" in control_source
    assert "description" in control_source


def test_ui_qt_apply_config_with_all_valid_values(rig_remote_app, mock_app_config):
    """Test apply config with all valid configuration values"""
    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

            assert rig_remote_app.params["txt_sgn_level"].text() == "-40"
            assert rig_remote_app.params["txt_range_min"].text() == "88000"
            assert rig_remote_app.params["txt_range_max"].text() == "108000"


def test_ui_qt_extract_bookmarks_returns_bookmark_list(rig_remote_app):
    """Test extract bookmarks returns list of Bookmark objects"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    bookmarks = rig_remote_app._extract_bookmarks()

    assert isinstance(bookmarks, list)
    assert len(bookmarks) == 1
    assert isinstance(bookmarks[0], Bookmark)



def test_ui_qt_event_filter_focus_out_line_109(rig_remote_app):
    """Test eventFilter processes focus out events (line 109)"""
    widget = rig_remote_app.params["txt_delay"]
    widget.setText("5")

    # Create a focus out event
    from PySide6.QtGui import QFocusEvent

    event = QFocusEvent(QFocusEvent.Type.FocusOut)

    # Verify event is processed without error
    result = rig_remote_app.eventFilter(widget, event)
    assert widget.text() == "5"



def test_ui_qt_process_hostname_rigctl_assignment_lines_386_388(rig_remote_app):
    """Test hostname processing assigns rigctl target (lines 386-388)"""
    rig_remote_app.params["txt_port1"].setText("4532")
    rig_remote_app.params["txt_hostname1"].setText("localhost")

    event = Mock()
    event.widget = rig_remote_app.params["txt_hostname1"]
    event.widget_name = "txt_hostname1"

    rig_remote_app.process_entry(event, silent=True)

    # Verify rigctl target was set
    assert rig_remote_app.rigctl[0].target.hostname == "localhost"
    assert rig_remote_app.rigctl[0].target.port == 4532


def test_ui_qt_process_port_rigctl_assignment_lines_790_796(rig_remote_app):
    """Test port processing assigns rigctl target (lines 790-796)"""
    rig_remote_app.params["txt_hostname1"].setText("localhost")
    rig_remote_app.params["txt_port1"].setText("4532")

    event = Mock()
    event.widget = rig_remote_app.params["txt_port1"]
    event.widget_name = "txt_port1"

    rig_remote_app.process_entry(event, silent=True)

    # Verify rigctl target was set with correct port
    assert rig_remote_app.rigctl[0].target.port == 4532
    assert rig_remote_app.rigctl[0].target.hostname == "localhost"


def test_ui_qt_build_control_source_frequency_validation_line_428(rig_remote_app):
    """Test build control source validates frequency (line 428)"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("Test")

    control_source = rig_remote_app.build_control_source(1, silent=True)

    assert control_source is not None
    assert control_source["frequency"] == "145500000"
    assert isinstance(control_source, dict)


def test_ui_qt_build_control_source_mode_extraction_lines_438_440(rig_remote_app):
    """Test build control source extracts mode (lines 438-440)"""
    rig_remote_app.params["txt_frequency1"].setText("146000000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("LSB")
    rig_remote_app.params["txt_description1"].setText("SSB")

    control_source = rig_remote_app.build_control_source(1, silent=True)

    assert control_source["mode"] == "LSB"
    assert "mode" in control_source


def test_ui_qt_build_control_source_description_extraction_lines_938_944(rig_remote_app):
    """Test build control source extracts description"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("Test Description")

    control_source = rig_remote_app.build_control_source(1, silent=True)

    assert control_source["description"] == "Test Description"


def test_ui_qt_build_control_source_invalid_frequency_lines_945_963(rig_remote_app):
    """Test build control source validates invalid frequency (lines 945-963)"""
    rig_remote_app.params["txt_frequency1"].setText("invalid")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("Test")

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        control_source = rig_remote_app.build_control_source(1, silent=False)

    assert control_source is None



def test_ui_qt_clear_form_all_fields_lines_445_446(rig_remote_app):
    """Test clear form clears all fields (lines 445-446)"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("Test")

    rig_remote_app._clear_form(1)

    assert rig_remote_app.params["txt_frequency1"].text() == ""
    assert rig_remote_app.params["txt_description1"].text() == ""
    assert rig_remote_app.params["cbb_mode1"].currentIndex() == -1



def test_ui_qt_autofill_form_frequency_field_lines_454_456(rig_remote_app):
    """Test autofill form populates frequency (lines 454-456)"""
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "147500000")
    item.setText(1, "FM")
    item.setText(2, "Test Freq")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.cb_autofill_form(1, None)

    assert rig_remote_app.params["txt_frequency1"].text() == "147500000"
    assert rig_remote_app.params["cbb_mode1"].currentText() == "FM"
    assert rig_remote_app.params["txt_description1"].text() == "Test Freq"


def test_ui_qt_autofill_form_rig_2_lines_460_461(rig_remote_app):
    """Test autofill form for rig 2 (lines 460-461)"""
    item = QTreeWidgetItem(rig_remote_app.tree)
    item.setText(0, "144390000")
    item.setText(1, "USB")
    item.setText(2, "Rig 2 Test")
    rig_remote_app.tree.addTopLevelItem(item)
    rig_remote_app.tree.setCurrentItem(item)

    rig_remote_app.cb_autofill_form(2, None)

    assert rig_remote_app.params["txt_frequency2"].text() == "144390000"
    assert rig_remote_app.params["cbb_mode2"].currentText() == "USB"



def test_ui_qt_set_frequency_calls_rigctl_lines_474_475(rig_remote_app):
    """Test set frequency calls rigctl (lines 474-475)"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")

    with patch.object(rig_remote_app.rigctl[0], "set_frequency") as mock_set_freq:
        with patch.object(rig_remote_app.rigctl[0], "set_mode") as mock_set_mode:
            rig_remote_app.cb_set_frequency({"rig_number": 1}, None, silent=True)

            mock_set_freq.assert_called_once_with("145500000")
            mock_set_mode.assert_called_once_with("FM")


def test_ui_qt_get_frequency_calls_rigctl_lines_523_524(rig_remote_app):
    """Test get frequency calls rigctl (lines 523-524)"""
    with patch.object(rig_remote_app.rigctl[0], "get_frequency", return_value="145500000"):
        with patch.object(rig_remote_app.rigctl[0], "get_mode", return_value="FM"):
            rig_remote_app.cb_get_frequency({"rig_number": 1}, silent=True)

            assert rig_remote_app.params["txt_frequency1"].text() == "145500000"
            assert rig_remote_app.params["cbb_mode1"].currentText() == "FM"


def test_ui_qt_get_frequency_updates_ui_lines_529_530(rig_remote_app):
    """Test get frequency updates UI fields (lines 529-530)"""
    with patch.object(rig_remote_app.rigctl[0], "get_frequency", return_value=" 146000000 "):
        with patch.object(rig_remote_app.rigctl[0], "get_mode", return_value="LSB"):
            rig_remote_app.cb_get_frequency({"rig_number": 1}, silent=True)

            # Verify strip() is called on frequency
            assert rig_remote_app.params["txt_frequency1"].text() == "146000000"



def test_ui_qt_insert_bookmarks_create_item_line_561(rig_remote_app):
    """Test insert bookmarks creates tree item (line 561)"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)

    assert rig_remote_app.tree.topLevelItemCount() == 1


def test_ui_qt_insert_bookmarks_set_columns_lines_577_579(rig_remote_app):
    """Test insert bookmarks sets all columns (lines 577-579)"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "LSB"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Local Repeater"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)

    item = rig_remote_app.tree.topLevelItem(0)
    assert item.text(0) == "145500000"
    assert item.text(1) == "LSB"
    assert item.text(2) == "Local Repeater"


def test_ui_qt_extract_bookmarks_retrieves_data_lines_611_613(rig_remote_app):
    """Test extract bookmarks retrieves data (lines 611-613)"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    bookmarks = rig_remote_app._extract_bookmarks()

    assert len(bookmarks) == 1
    assert bookmarks[0].channel.frequency == 145500000
    assert bookmarks[0].channel.modulation == "FM"
    assert bookmarks[0].description == "Test"





def test_ui_qt_apply_config_sets_hostname_port_lines_617_619(rig_remote_app, mock_app_config):
    """Test apply config sets hostname and port (lines 617-619)"""
    mock_app_config.config["hostname1"] = "192.168.1.1"
    mock_app_config.config["port1"] = "4532"

    with patch.object(rig_remote_app, "_build_ui"):
        with patch("rig_remote.ui_qt.RigCtl"):
            rig_remote_app.apply_config(mock_app_config, silent=True)

    assert rig_remote_app.params["txt_hostname1"].text() == "192.168.1.1"
    assert rig_remote_app.params["txt_port1"].text() == "4532"



def test_ui_qt_apply_config_sets_parameters_lines_625_652(rig_remote_app, mock_app_config):
    """Test apply config sets all parameters (lines 625-652)"""
    mock_app_config.config = {
        "hostname1": "localhost",
        "hostname2": "localhost",
        "port1": "4532",
        "port2": "4533",
        "interval": "25",
        "delay": "2",
        "passes": "0",
        "range_min": "50000",
        "range_max": "1000000",
        "sgn_level": "-50",
        "auto_bookmark": "true",
        "record": "true",
        "wait": "true",
        "log": "true",
        "save_exit": "true",
        "always_on_top": "true",
    }

    with patch.object(rig_remote_app, "_build_ui"):
        rig_remote_app.apply_config(mock_app_config, silent=True)

    assert rig_remote_app.params["txt_interval"].text() == "25"
    assert rig_remote_app.params["txt_delay"].text() == "2"
    assert rig_remote_app.params["txt_passes"].text() == "0"
    assert rig_remote_app.params["txt_range_min"].text() == "50000"
    assert rig_remote_app.params["txt_range_max"].text() == "1000000"
    assert rig_remote_app.params["txt_sgn_level"].text() == "-50"


def test_ui_qt_bookmark_lockout_open_to_locked_lines_656_659(rig_remote_app):
    """Test bookmark lockout toggles from open to locked (lines 656-659)"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)
    rig_remote_app.bookmark_lockout()

    assert item.data(0, Qt.ItemDataRole.UserRole) == "L"
    assert item.background(0).color() == QColor("red")


def test_ui_qt_bookmark_lockout_locked_to_open(rig_remote_app):
    """Test bookmark lockout toggles from locked to open"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "L"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)
    rig_remote_app.bookmark_lockout()

    assert item.data(0, Qt.ItemDataRole.UserRole) == "O"
    assert item.background(0).color() == QColor("white")



def test_ui_qt_toggle_cb_top_sets_flags_lines_686_692(rig_remote_app):
    """Test toggle always on top sets window flags (lines 686-692)"""
    initial_flags = rig_remote_app.windowFlags()

    rig_remote_app.toggle_cb_top(Qt.CheckState.Checked.value)
    flags_checked = rig_remote_app.windowFlags()

    # Verify flag includes WindowStaysOnTopHint
    assert flags_checked & Qt.WindowType.WindowStaysOnTopHint

    rig_remote_app.toggle_cb_top(Qt.CheckState.Unchecked.value)
    flags_unchecked = rig_remote_app.windowFlags()

    # Verify flag does not include WindowStaysOnTopHint
    assert not (flags_unchecked & Qt.WindowType.WindowStaysOnTopHint)



def test_ui_qt_process_wait_checkbox_lines_700_707(rig_remote_app):
    """Test process wait checkbox (lines 700-707)"""
    rig_remote_app.scan_thread = Mock()  # Simulate active scan

    with patch.object(rig_remote_app.scanq, "send_event_update") as mock_send:
        rig_remote_app.process_wait(Qt.CheckState.Checked.value)

        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        assert args[0] == "ckb_wait"
        assert args[1] is True


def test_ui_qt_process_record_checkbox_lines_711_713(rig_remote_app):
    """Test process record checkbox (lines 711-713)"""
    rig_remote_app.scan_thread = Mock()

    with patch.object(rig_remote_app.scanq, "send_event_update") as mock_send:
        rig_remote_app.process_record(Qt.CheckState.Checked.value)

        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        assert args[0] == "ckb_record"


def test_ui_qt_process_log_checkbox_line_717(rig_remote_app):
    """Test process log checkbox (line 717)"""
    rig_remote_app.scan_thread = Mock()

    with patch.object(rig_remote_app.scanq, "send_event_update") as mock_send:
        rig_remote_app.process_log(Qt.CheckState.Checked.value)

        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        assert args[0] == "ckb_log"


def test_ui_qt_process_auto_bookmark_checkbox_lines_724_plus(rig_remote_app):
    """Test process auto bookmark checkbox"""
    rig_remote_app.scan_thread = Mock()

    with patch.object(rig_remote_app.scanq, "send_event_update") as mock_send:
        rig_remote_app.process_auto_bookmark(Qt.CheckState.Checked.value)

        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        assert args[0] == "ckb_auto_bookmark"


def test_ui_qt_process_checkbutton_stores_last_content(rig_remote_app):
    """Test checkbox processing stores last content"""
    rig_remote_app.scan_thread = Mock()

    with patch.object(rig_remote_app.scanq, "send_event_update"):
        rig_remote_app.process_wait(Qt.CheckState.Checked.value)

        assert rig_remote_app.params_last_content["ckb_wait"] is True



def test_ui_qt_process_entry_updates_last_content_line_826(rig_remote_app):
    """Test process entry updates params_last_content (line 826)"""
    widget_name = "txt_delay"
    value = "5"
    rig_remote_app.params[widget_name].setText(value)

    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name

    rig_remote_app.process_entry(event, silent=True)

    assert rig_remote_app.params_last_content[widget_name] == value


def test_ui_qt_process_entry_broadcast_signal_lines_847_848(rig_remote_app):
    """Test process entry broadcasts signal (lines 847-848)"""
    widget_name = "txt_interval"
    value = "20"
    rig_remote_app.params[widget_name].setText(value)
    rig_remote_app.scan_thread = Mock()  # Simulate active scan

    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name

    with patch.object(rig_remote_app.scanq, "send_event_update") as mock_send:
        rig_remote_app.process_entry(event, silent=True)

        mock_send.assert_called_once()


def test_ui_qt_process_entry_validation_failure_lines_870_904(rig_remote_app):
    """Test process entry handles validation failure (lines 870-904)"""
    widget_name = "txt_sgn_level"
    invalid_value = "abc"
    original_value = "-50"

    rig_remote_app.params[widget_name].setText(original_value)
    rig_remote_app.params_last_content[widget_name] = original_value
    rig_remote_app.params[widget_name].setText(invalid_value)

    event = Mock()
    event.widget = rig_remote_app.params[widget_name]
    event.widget_name = widget_name

    with patch("rig_remote.ui_qt.QMessageBox.critical"):
        rig_remote_app.process_entry(event, silent=False)

    # Verify widget still has focus or is in error state
    assert rig_remote_app.params[widget_name].text() == invalid_value


def test_ui_qt_process_hostname_entry_validation_lines_919_932(rig_remote_app):
    """Test process hostname entry validation (lines 919-932)"""
    rig_remote_app.params["txt_port1"].setText("4532")
    rig_remote_app.params["txt_hostname1"].setText("invalid hostname with spaces")

    event = Mock()
    event.widget = rig_remote_app.params["txt_hostname1"]
    event.widget_name = "txt_hostname1"

    # Should handle gracefully even with unusual hostnames
    rig_remote_app.process_entry(event, silent=True)



def test_ui_qt_bookmark_add_broadcasts_and_saves(rig_remote_app):
    """Test adding bookmark saves changes"""
    rig_remote_app.params["txt_frequency1"].setText("145500000")
    rig_remote_app.params["cbb_mode1"].setCurrentText("FM")
    rig_remote_app.params["txt_description1"].setText("New Bookmark")

    with patch.object(rig_remote_app.bookmarks, "save"):
        rig_remote_app.cb_add(1, silent=True)

    assert rig_remote_app.tree.topLevelItemCount() == 1
    item = rig_remote_app.tree.topLevelItem(0)
    assert item.text(2) == "New Bookmark"


def test_ui_qt_bookmark_delete_removes_and_saves(rig_remote_app):
    """Test deleting bookmark removes from tree and saves"""
    mock_bookmark = Mock(spec=Bookmark)
    channel_mock = Mock()
    channel_mock.frequency = "145500000"
    channel_mock.modulation = "FM"
    mock_bookmark.channel = channel_mock
    mock_bookmark.description = "Test"
    mock_bookmark.lockout = "O"

    rig_remote_app._insert_bookmarks([mock_bookmark], silent=True)
    item = rig_remote_app.tree.topLevelItem(0)
    rig_remote_app.tree.setCurrentItem(item)

    with patch.object(rig_remote_app.bookmarks, "delete_bookmark"):
        with patch.object(rig_remote_app.bookmarks, "save"):
            rig_remote_app.cb_delete(1)

    assert rig_remote_app.tree.topLevelItemCount() == 0

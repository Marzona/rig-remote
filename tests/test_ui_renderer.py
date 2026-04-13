import pytest
from unittest.mock import MagicMock, Mock, patch
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox

from rig_remote.ui_renderer import RigRemoteUIBuilder
from rig_remote.ui_qt import RigRemote
from rig_remote.app_config import AppConfig
from rig_remote.models.rig_endpoint import RigEndpoint


# ---------------------------------------------------------------------------
# Minimal concrete subclass used for pure-mixin tests (no Qt infrastructure)
# ---------------------------------------------------------------------------

class ConcreteBuilder(RigRemoteUIBuilder):
    """Minimal concrete subclass to allow instantiation of the mixin."""

    _ORDINAL_NUMBERS = ["First", "Second"]
    params = {}
    params_last_content = {}
    rigctl = []

    def setWindowTitle(self, title):
        pass

    def setMinimumSize(self, w, h):
        pass

    def setCentralWidget(self, widget):
        pass

    def menuBar(self):
        return MagicMock()

    def close(self):
        return True


def test_build_rig_invalid_number_raises():
    builder = ConcreteBuilder()
    with pytest.raises(ValueError):
        builder._build_rig(MagicMock(), -1)


def test_build_rig_number_too_large_raises():
    builder = ConcreteBuilder()
    with pytest.raises(ValueError):
        builder._build_rig(MagicMock(), 99)


# ---------------------------------------------------------------------------
# Fixtures – mirror those in test_ui_qt.py so full RigRemote can be built
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_app_config():
    """Create mock AppConfig."""
    config = Mock(spec=AppConfig)
    config.config = {
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
    """Create RigRemote application instance."""
    with patch("rig_remote.ui_qt.BookmarksManager"):
        with patch("rig_remote.ui_qt.RigCtl"):
            with patch("rig_remote.ui_qt.QMessageBox.question", return_value=1):
                app = RigRemote(mock_app_config)
                app.closeEvent = Mock()
                yield app
                app.close()


# ---------------------------------------------------------------------------
# Tests for _build_ui (window title and minimum size)
# ---------------------------------------------------------------------------

def test_ui_renderer_window_title(rig_remote_app):
    """_build_ui sets window title to 'Rig Remote'."""
    assert rig_remote_app.windowTitle() == "Rig Remote"


def test_ui_renderer_window_title_not_empty(rig_remote_app):
    """_build_ui produces a non-empty window title."""
    assert rig_remote_app.windowTitle() != ""


def test_ui_renderer_minimum_width(rig_remote_app):
    """_build_ui sets minimum width >= 800."""
    assert rig_remote_app.minimumWidth() >= 800


def test_ui_renderer_minimum_height(rig_remote_app):
    """_build_ui sets minimum height >= 244."""
    assert rig_remote_app.minimumHeight() >= 244


# ---------------------------------------------------------------------------
# Tests for _build_tree_view
# ---------------------------------------------------------------------------

def test_ui_renderer_tree_widget_created(rig_remote_app):
    """_build_tree_view creates the tree attribute."""
    assert hasattr(rig_remote_app, "tree")
    assert rig_remote_app.tree is not None


def test_ui_renderer_tree_widget_headers(rig_remote_app):
    """_build_tree_view sets the correct column headers."""
    headers = [
        rig_remote_app.tree.headerItem().text(i)
        for i in range(rig_remote_app.tree.columnCount())
    ]
    assert "Frequency" in headers
    assert "Mode" in headers
    assert "Description" in headers


def test_ui_renderer_tree_widget_headers_no_invalid(rig_remote_app):
    """_build_tree_view does not introduce unexpected headers."""
    headers = [
        rig_remote_app.tree.headerItem().text(i)
        for i in range(rig_remote_app.tree.columnCount())
    ]
    assert "InvalidHeader" not in headers


# ---------------------------------------------------------------------------
# Tests for _build_rig / _ORDINAL_NUMBERS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rig_number,expected_ordinal",
    [
        (1, "First"),
        (2, "Second"),
        (3, "Third"),
        (4, "Fourth"),
    ],
)
def test_ui_renderer_rig_ordinals_positive(rig_remote_app, rig_number, expected_ordinal):
    """_ORDINAL_NUMBERS contains the correct label for each rig."""
    assert rig_remote_app._ORDINAL_NUMBERS[rig_number - 1] == expected_ordinal


def test_ui_renderer_rig_ordinals_count(rig_remote_app):
    """_ORDINAL_NUMBERS has exactly 4 entries."""
    assert len(rig_remote_app._ORDINAL_NUMBERS) == 4


# ---------------------------------------------------------------------------
# Tests for _build_rig_config – widget presence/absence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_renderer_hostname_widget_created(rig_remote_app, rig_number):
    """_build_rig_config creates a hostname QLineEdit for valid rigs."""
    widget_name = f"txt_hostname{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_renderer_hostname_widget_absent_for_invalid_rig(rig_remote_app, invalid_rig_number):
    """No hostname widget is created for out-of-range rig numbers."""
    assert f"txt_hostname{invalid_rig_number}" not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_renderer_port_widget_created(rig_remote_app, rig_number):
    """_build_rig_config creates a port QLineEdit for valid rigs."""
    widget_name = f"txt_port{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_renderer_port_widget_absent_for_invalid_rig(rig_remote_app, invalid_rig_number):
    """No port widget is created for out-of-range rig numbers."""
    assert f"txt_port{invalid_rig_number}" not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_renderer_frequency_widget_created(rig_remote_app, rig_number):
    """_build_rig_config creates a frequency QLineEdit for valid rigs."""
    widget_name = f"txt_frequency{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_renderer_frequency_widget_absent_for_invalid_rig(rig_remote_app, invalid_rig_number):
    """No frequency widget is created for out-of-range rig numbers."""
    assert f"txt_frequency{invalid_rig_number}" not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_renderer_mode_combobox_created(rig_remote_app, rig_number):
    """_build_rig_config creates a mode QComboBox for valid rigs."""
    widget_name = f"cbb_mode{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QComboBox)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_renderer_mode_combobox_absent_for_invalid_rig(rig_remote_app, invalid_rig_number):
    """No mode combobox is created for out-of-range rig numbers."""
    assert f"cbb_mode{invalid_rig_number}" not in rig_remote_app.params


@pytest.mark.parametrize("rig_number", [1, 2])
def test_ui_renderer_description_widget_created(rig_remote_app, rig_number):
    """_build_rig_config creates a description QLineEdit for valid rigs."""
    widget_name = f"txt_description{rig_number}"
    assert widget_name in rig_remote_app.params
    assert isinstance(rig_remote_app.params[widget_name], QLineEdit)


@pytest.mark.parametrize("invalid_rig_number", [0, 5, 10, 99])
def test_ui_renderer_description_widget_absent_for_invalid_rig(rig_remote_app, invalid_rig_number):
    """No description widget is created for out-of-range rig numbers."""
    assert f"txt_description{invalid_rig_number}" not in rig_remote_app.params


# ---------------------------------------------------------------------------
# Tests for _build_scanning_options
# ---------------------------------------------------------------------------

def test_ui_renderer_scanning_options_widgets_present(rig_remote_app):
    """_build_scanning_options creates all expected scanning widgets."""
    assert "txt_sgn_level" in rig_remote_app.params
    assert "txt_delay" in rig_remote_app.params
    assert "txt_passes" in rig_remote_app.params
    assert "ckb_wait" in rig_remote_app.params
    assert "ckb_record" in rig_remote_app.params
    assert "ckb_log" in rig_remote_app.params

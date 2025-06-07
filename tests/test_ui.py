
import pytest
from unittest.mock import MagicMock, patch
import tkinter as tk
from rig_remote.ui import RigRemote, ToolTip, RCCheckbutton
from rig_remote.models.bookmark import Bookmark

@pytest.fixture
def mock_app_config():
    """Mock AppConfig to avoid file dependencies."""
    mock_config = MagicMock()
    mock_config.config = {
        "bookmark_filename": "mock_bookmarks.csv",
        "log_filename": "mock_log.log"  # Add the missing key
    }
    return mock_config

@pytest.fixture
def rig_remote(mock_app_config):
    """Fixture to create a RigRemote instance with a mocked AppConfig."""
    root = tk.Tk()
    rr = RigRemote(root, mock_app_config)
    rr.bookmarks_manager = MagicMock()  # Mock the bookmarks_manager
    yield rr
    rr.root.destroy()

def test_ui_initialize_ui(rig_remote):
    """Test that the UI initializes correctly."""
    assert rig_remote.tree is not None
    assert rig_remote.params is not None

def test_ui_load_bookmarks(rig_remote):
    """Test loading bookmarks."""
    mock_bookmarks = [
        Bookmark(channel=MagicMock(frequency_as_string="123.45", modulation="FM"), description="Test", lockout="0")
    ]
    with patch.object(rig_remote.bookmarks_manager, "load", return_value=mock_bookmarks):
        rig_remote._load_bookmarks()
        assert len(rig_remote.tree.get_children()) == 0

def test_ui_insert_bookmarks(rig_remote):
    """Test inserting bookmarks into the tree."""
    mock_bookmarks = [
        Bookmark(channel=MagicMock(frequency_as_string="123.45", modulation="FM"), description="Test", lockout="0")
    ]
    rig_remote._insert_bookmarks(mock_bookmarks)
    assert len(rig_remote.tree.get_children()) == 1


def test_ui_extract_bookmarks(rig_remote):
    """Test extracting bookmarks from the tree."""
    mock_bookmarks = [
        Bookmark(
            channel=MagicMock(frequency_as_string="123,45", modulation="FM"),
            description="Test1",
            lockout="0"
        ),
        Bookmark(
            channel=MagicMock(frequency_as_string="456,78", modulation="AM"),
            description="Test2",
            lockout="L"
        )
    ]
    rig_remote._insert_bookmarks(mock_bookmarks)

    extracted = rig_remote._extract_bookmarks()
    assert len(extracted) == 2
    assert extracted[0].channel.frequency_as_string == "12,345"
    assert extracted[1].channel.frequency_as_string == "45,678"


def test_ui_delete_callback(rig_remote):
    """Test callback deletion with source parameter."""
    mock_bookmark = Bookmark(
        channel=MagicMock(frequency_as_string="12,345", modulation="FM"),
        description="Test",
        lockout="0"
    )
    rig_remote._insert_bookmarks([mock_bookmark])

    item = rig_remote.tree.get_children()[0]
    rig_remote.tree.focus(item)
    rig_remote.cb_delete(source=1)

    assert len(rig_remote.tree.get_children()) == 0


def test_ui_tooltip(rig_remote):
    """Test tooltip creation and configuration."""
    test_widget = tk.Label(rig_remote.root, text="Test")
    tooltip = ToolTip(test_widget, text="Test tooltip", delay=100)

    assert tooltip._opts["text"] == "Test tooltip"
    assert tooltip._opts["delay"] == 100
    assert tooltip._tipwindow is None


def test_ui_rc_checkbutton(rig_remote):
    """Test custom checkbutton functionality."""
    check = RCCheckbutton(rig_remote.root)

    check.set_str_val("true")
    assert check.is_checked() is True
    assert check.get_str_val() == "true"

    check.set_str_val("false")
    assert check.is_checked() is False
    assert check.get_str_val() == "false"
import pytest
from unittest.mock import MagicMock
from rig_remote.utility import (
    khertz_to_hertz,
    shutdown,
    center_window
)

def test_utility_khertz_to_hertz():
    """Test frequency conversion from kHz to Hz."""
    assert khertz_to_hertz("1000") == 1000000
    assert khertz_to_hertz(1000) == 1000000

    with pytest.raises(ValueError):
        khertz_to_hertz("invalid")

def test_utility_shutdown_without_save():
    """Test shutdown function when save on exit is disabled."""
    window = MagicMock()
    window.ckb_save_exit.get_str_val.return_value = "false"

    shutdown(window)

    assert not hasattr(window, '_io') or not window._io.save.called
    window.master.destroy.assert_called_once()


def test_utility_center_window_custom_size():
    """Test window centering calculation with custom size."""
    window = MagicMock()
    window.winfo_screenwidth.return_value = 1920
    window.winfo_screenheight.return_value = 1080

    center_window(window, width=800, height=600)

    window.geometry.assert_called_once_with("800x600+560+240")

def test_utility_center_window_default_size():
    """Test window centering calculation with default size."""
    window = MagicMock()
    window.winfo_screenwidth.return_value = 1920
    window.winfo_screenheight.return_value = 1080

    center_window(window)

    window.geometry.assert_called_once_with("300x200+810+440")
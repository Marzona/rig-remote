"""
Tests to verify that all required modules and constants can be imported correctly.
This ensures that the package structure is intact and all dependencies are properly defined.
"""
import pytest


# Constants that should exist in the constants module
constants_to_check = [
    "BM",
    "LEN_BM",
]

# Module import statements to test
import_statements = [
    "from rig_remote.app_config import AppConfig",
    "from rig_remote.disk_io import IO",
    "from rig_remote.disk_io import LogFile",
    "from rig_remote.exceptions import InvalidPathError",
    "from rig_remote.exceptions import UnsupportedScanningConfigError",
    "from rig_remote.rigctl import RigCtl",
    "from rig_remote.scanning import Scanning2",
    "from rig_remote.scanning import create_scanner",
    "from rig_remote.stmessenger import STMessenger",
]


@pytest.mark.parametrize("constant_name", constants_to_check)
def test_import_constants(constant_name):
    """Test that all required constants can be imported from rig_remote.constants."""
    import rig_remote.constants as constants
    assert hasattr(constants, constant_name), f"Constant '{constant_name}' not found in rig_remote.constants"


@pytest.mark.parametrize("import_statement", import_statements)
def test_import_modules(import_statement):
    """Test that all required classes can be imported from their respective modules."""
    try:
        exec(import_statement)
    except ImportError as e:
        pytest.fail(f"Failed to execute import: {import_statement}\nError: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error executing import: {import_statement}\nError: {e}")


def test_import_all_constants_module():
    """Test that the constants module can be imported as a whole."""
    try:
        import rig_remote.constants
        assert rig_remote.constants is not None
    except ImportError as e:
        pytest.fail(f"Failed to import rig_remote.constants: {e}")


def test_import_all_core_modules():
    """Test that all core modules exist and can be imported."""
    core_modules = [
        "rig_remote.app_config",
        "rig_remote.disk_io",
        "rig_remote.exceptions",
        "rig_remote.rigctl",
        "rig_remote.scanning",
        "rig_remote.stmessenger",
    ]

    for module_name in core_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")

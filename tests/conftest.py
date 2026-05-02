import sys
from unittest.mock import MagicMock


class _HamlibError(Exception):
    """Stand-in for Hamlib.error used by scanner_core._HAMLIB_ERROR."""


_hamlib_mock = MagicMock()
_hamlib_mock.Rig = MagicMock()
_hamlib_mock.error = _HamlibError  # must be a real exception class, not a MagicMock
_hamlib_mock.RIG_VFO_CURR = 0
_hamlib_mock.RIG_LEVEL_STRENGTH = 1
_hamlib_mock.RIG_PASSBAND_NOCHANGE = -1
_hamlib_mock.RIG_RESET_NONE = 0
_hamlib_mock.RIG_RESET_SOFT = 1
_hamlib_mock.RIG_RESET_VFO = 2
_hamlib_mock.RIG_RESET_MCALL = 4
_hamlib_mock.RIG_RESET_MASTER = 8

sys.modules["Hamlib"] = _hamlib_mock

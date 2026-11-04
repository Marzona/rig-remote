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


# ---------------------------------------------------------------------------
# Headless guard: a real modal dialog blocks forever when no user can click it
# (e.g. in CI with QT_QPA_PLATFORM=offscreen). Any dialog a test does not patch
# explicitly fails the test immediately instead of hanging the whole run.
# Tests that patch these methods themselves override this guard.
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

_MODAL_DIALOGS = {
    "PySide6.QtWidgets.QMessageBox": ("about", "critical", "information", "question", "warning"),
    "PySide6.QtWidgets.QFileDialog": ("getOpenFileName", "getSaveFileName"),
}


def _unexpected_dialog(*args: object, **kwargs: object) -> None:
    raise AssertionError(f"Unexpected modal dialog opened in test (args={args!r}); patch it explicitly.")


@pytest.fixture(autouse=True)
def _no_blocking_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    for target, methods in _MODAL_DIALOGS.items():
        for method in methods:
            monkeypatch.setattr(f"{target}.{method}", _unexpected_dialog)

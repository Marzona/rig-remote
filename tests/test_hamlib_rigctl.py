import sys
import threading
from unittest.mock import MagicMock

import pytest

from rig_remote.rig_backends.hamlib_rigctl import HamlibRigCtl
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType
from rig_remote.models.rig_endpoint import RigEndpoint

_hl = sys.modules["Hamlib"]


def _make_endpoint():
    return RigEndpoint(
        backend=BackendType.HAMLIB,
        rig_model=122,
        serial_port="/dev/ttyUSB0",
        baud_rate=38400,
    )


def _make_ctl_with_mock_rig():
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)
    mock_rig = MagicMock()
    ctl._rig = mock_rig
    return ctl, mock_rig


def test_connect_calls_rig_and_opens():
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)

    mock_rig_instance = MagicMock()
    _hl.Rig.return_value = mock_rig_instance

    ctl.connect()

    _hl.Rig.assert_called_with(122)
    mock_rig_instance.open.assert_called_once()


def test_connect_raises_oserror_on_open_failure():
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)

    mock_rig_instance = MagicMock()
    mock_rig_instance.open.side_effect = RuntimeError("hardware failure")
    _hl.Rig.return_value = mock_rig_instance

    with pytest.raises(OSError):
        ctl.connect()


def test_disconnect_calls_close():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.disconnect()
    mock_rig.close.assert_called_once()


def test_disconnect_sets_rig_to_none_after_close():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.disconnect()
    assert ctl._rig is None


def test_disconnect_handles_exception_gracefully():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.close.side_effect = RuntimeError("close failed")
    ctl.disconnect()
    assert ctl._rig is None


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        (145000000, 145000000),
        (7000000, 7000000),
        (0, 0),
    ],
)
def test_get_frequency_returns_int(raw_value, expected):
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_freq.return_value = raw_value
    result = ctl.get_frequency()
    mock_rig.get_freq.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == expected
    assert isinstance(result, int)


@pytest.mark.parametrize(
    "frequency",
    [145000000, 7000000, 0],
)
def test_set_frequency_calls_rig(frequency):
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.set_frequency(frequency)
    mock_rig.set_freq.assert_called_once_with(_hl.RIG_VFO_CURR, frequency)


@pytest.mark.parametrize(
    "raw_level, expected",
    [
        (5, 50),
        (-3, -30),
        (0, 0),
    ],
)
def test_get_level_multiplies_by_10(raw_level, expected):
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_level_i.return_value = raw_level
    result = ctl.get_level()
    mock_rig.get_level_i.assert_called_once_with(_hl.RIG_LEVEL_STRENGTH)
    assert result == expected


def test_set_mode_translates_and_calls_rig():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.set_mode("AM")
    mock_rig.set_mode.assert_called_once_with(
        _hl.RIG_VFO_CURR,
        1,
        _hl.RIG_PASSBAND_NOCHANGE,
    )


def test_get_mode_calls_rig_and_translates():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_mode.return_value = (1, 0)
    result = ctl.get_mode()
    mock_rig.get_mode.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == "AM"


def test_start_recording_raises_not_implemented():
    ctl, _ = _make_ctl_with_mock_rig()
    with pytest.raises(NotImplementedError):
        ctl.start_recording()


def test_stop_recording_raises_not_implemented():
    ctl, _ = _make_ctl_with_mock_rig()
    with pytest.raises(NotImplementedError):
        ctl.stop_recording()


def test_require_rig_raises_oserror_when_not_connected():
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)
    assert ctl._rig is None
    with pytest.raises(OSError):
        ctl._require_rig()


def test_thread_safety_concurrent_get_frequency():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_freq.return_value = 145000000
    results = []
    errors = []

    def worker():
        try:
            results.append(ctl.get_frequency())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors
    assert len(results) == 2
    assert all(r == 145000000 for r in results)

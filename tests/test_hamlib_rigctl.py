import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from rig_remote.rig_backends.hamlib_rigctl import HamlibRigCtl, _hamlib
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType
from rig_remote.models.rig_endpoint import RigEndpoint

_hl = sys.modules["Hamlib"]


def _make_endpoint() -> RigEndpoint:
    return RigEndpoint(
        backend=BackendType.HAMLIB,
        rig_model=122,
        serial_port="/dev/ttyUSB0",
        baud_rate=38400,
    )


def _make_ctl_with_mock_rig() -> tuple[HamlibRigCtl, MagicMock]:
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)
    mock_rig = MagicMock()
    ctl._rig = mock_rig
    return ctl, mock_rig


# ---------------------------------------------------------------------------
# _hamlib() lazy import
# ---------------------------------------------------------------------------

def test_hamlib_import_error_raises_with_helpful_message():
    with patch.dict(sys.modules, {"Hamlib": None}):
        with pytest.raises(ImportError, match="The Hamlib Python module is required"):
            _hamlib()


# ---------------------------------------------------------------------------
# endpoint property
# ---------------------------------------------------------------------------

def test_endpoint_getter_returns_endpoint():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    assert ctl.endpoint is endpoint


def test_endpoint_setter_replaces_endpoint():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    new_endpoint = _make_endpoint()
    ctl.endpoint = new_endpoint
    assert ctl.endpoint is new_endpoint


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------

def test_connect_calls_rig_and_opens():
    endpoint = _make_endpoint()
    translator = ModeTranslator(BackendType.HAMLIB)
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)

    mock_rig_instance = MagicMock()
    _hl.Rig.return_value = mock_rig_instance

    ctl.connect()

    _hl.Rig.assert_called_with(122)
    mock_rig_instance.open.assert_called_once()


def test_connect_closes_existing_rig_before_reconnecting():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    old_rig = MagicMock()
    ctl._rig = old_rig

    new_rig = MagicMock()
    _hl.Rig.return_value = new_rig

    ctl.connect()

    old_rig.close.assert_called_once()
    assert ctl._rig is new_rig


def test_connect_continues_when_closing_existing_rig_fails():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    old_rig = MagicMock()
    old_rig.close.side_effect = RuntimeError("close failed")
    ctl._rig = old_rig

    new_rig = MagicMock()
    _hl.Rig.return_value = new_rig

    ctl.connect()  # must not raise

    assert ctl._rig is new_rig


def test_connect_raises_oserror_on_open_failure():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))

    mock_rig_instance = MagicMock()
    mock_rig_instance.open.side_effect = RuntimeError("hardware failure")
    _hl.Rig.return_value = mock_rig_instance

    with pytest.raises(OSError):
        ctl.connect()


# ---------------------------------------------------------------------------
# disconnect()
# ---------------------------------------------------------------------------

def test_disconnect_calls_close():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.disconnect()
    mock_rig.close.assert_called_once()


def test_disconnect_sets_rig_to_none_after_close():
    ctl, _ = _make_ctl_with_mock_rig()
    ctl.disconnect()
    assert ctl._rig is None


def test_disconnect_sets_rig_to_none_even_when_close_raises():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.close.side_effect = RuntimeError("close failed")
    ctl.disconnect()
    assert ctl._rig is None


def test_disconnect_when_not_connected_is_noop():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    ctl.disconnect()  # _rig is None; must not raise


# ---------------------------------------------------------------------------
# _require_rig()
# ---------------------------------------------------------------------------

def test_require_rig_raises_oserror_when_not_connected():
    endpoint = _make_endpoint()
    ctl = HamlibRigCtl(endpoint=endpoint, mode_translator=ModeTranslator(BackendType.HAMLIB))
    assert ctl._rig is None
    with pytest.raises(OSError):
        ctl._require_rig()


# ---------------------------------------------------------------------------
# set_frequency / get_frequency
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frequency", [145000000, 7000000, 0])
def test_set_frequency_calls_rig(frequency: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.set_frequency(frequency)
    mock_rig.set_freq.assert_called_once_with(_hl.RIG_VFO_CURR, frequency)


def test_set_frequency_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_freq.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_frequency(145000000)


@pytest.mark.parametrize(
    "raw_value, expected",
    [(145000000, 145000000), (7000000, 7000000), (0, 0)],
)
def test_get_frequency_returns_int(raw_value: int, expected: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_freq.return_value = raw_value
    result = ctl.get_frequency()
    mock_rig.get_freq.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == expected
    assert isinstance(result, int)


def test_get_frequency_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_freq.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_frequency()


# ---------------------------------------------------------------------------
# set_mode / get_mode
# ---------------------------------------------------------------------------

def test_set_mode_translates_and_calls_rig():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    ctl.set_mode("AM")
    mock_rig.set_mode.assert_called_once_with(_hl.RIG_VFO_CURR, 1, _hl.RIG_PASSBAND_NOCHANGE)


def test_set_mode_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_mode.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_mode("AM")


def test_get_mode_calls_rig_and_translates():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_mode.return_value = (1, 0)
    result = ctl.get_mode()
    mock_rig.get_mode.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == "AM"


def test_get_mode_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_mode.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_mode()


# ---------------------------------------------------------------------------
# get_level
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_level, expected",
    [(5, 50), (-3, -30), (0, 0)],
)
def test_get_level_multiplies_by_10(raw_level: int, expected: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_level_i.return_value = raw_level
    result = ctl.get_level()
    mock_rig.get_level_i.assert_called_once_with(_hl.RIG_LEVEL_STRENGTH)
    assert result == expected


def test_get_level_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_level_i.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_level()


# ---------------------------------------------------------------------------
# recording stubs
# ---------------------------------------------------------------------------

def test_start_recording_raises_not_implemented():
    ctl, _ = _make_ctl_with_mock_rig()
    with pytest.raises(NotImplementedError):
        ctl.start_recording()


def test_stop_recording_raises_not_implemented():
    ctl, _ = _make_ctl_with_mock_rig()
    with pytest.raises(NotImplementedError):
        ctl.stop_recording()


# ---------------------------------------------------------------------------
# set_rit / get_rit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rit", [0, 100, -200])
def test_set_rit_calls_rig_and_returns_empty(rit: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_rit(rit)
    mock_rig.set_rit.assert_called_once_with(_hl.RIG_VFO_CURR, rit)
    assert result == ""


def test_set_rit_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_rit.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_rit(100)


def test_get_rit_calls_rig_and_returns_string():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_rit.return_value = 50
    result = ctl.get_rit()
    mock_rig.get_rit.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == "50"


def test_get_rit_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_rit.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_rit()


# ---------------------------------------------------------------------------
# set_xit / get_xit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("xit", [0, 500, -100])
def test_set_xit_calls_rig_and_returns_empty(xit: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_xit(xit)
    mock_rig.set_xit.assert_called_once_with(_hl.RIG_VFO_CURR, xit)
    assert result == ""


def test_set_xit_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_xit.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_xit(100)


def test_get_xit_calls_rig_and_returns_string():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_xit.return_value = 200
    result = ctl.get_xit()
    mock_rig.get_xit.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == "200"


def test_get_xit_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_xit.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_xit()


# ---------------------------------------------------------------------------
# set_split_freq / get_split_freq
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("freq", [145100000, 7001000])
def test_set_split_freq_calls_rig_and_returns_empty(freq: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_split_freq(freq)
    mock_rig.set_split_freq.assert_called_once_with(_hl.RIG_VFO_CURR, freq)
    assert result == ""


def test_set_split_freq_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_split_freq.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_split_freq(145100000)


def test_get_split_freq_returns_int():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_split_freq.return_value = 145100000
    result = ctl.get_split_freq()
    mock_rig.get_split_freq.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == 145100000
    assert isinstance(result, int)


def test_get_split_freq_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_split_freq.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_split_freq()


# ---------------------------------------------------------------------------
# set_split_mode / get_split_mode
# ---------------------------------------------------------------------------

def test_set_split_mode_translates_and_calls_rig():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_split_mode("FM")
    mock_rig.set_split_mode.assert_called_once_with(_hl.RIG_VFO_CURR, 32, _hl.RIG_PASSBAND_NOCHANGE)
    assert result == ""


def test_set_split_mode_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_split_mode.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_split_mode("FM")


def test_get_split_mode_calls_rig_and_translates():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_split_mode.return_value = (32, 0)
    result = ctl.get_split_mode()
    mock_rig.get_split_mode.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == "FM"


def test_get_split_mode_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_split_mode.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_split_mode()


# ---------------------------------------------------------------------------
# set_func / get_func
# ---------------------------------------------------------------------------

def test_set_func_calls_rig_and_returns_empty():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_func("NB")
    mock_rig.set_func.assert_called_once_with(
        _hl.RIG_VFO_CURR, getattr(_hl, "RIG_FUNC_NB", 0), 1
    )
    assert result == ""


def test_set_func_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_func.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_func("NB")


def test_get_func_returns_empty_string():
    ctl, _ = _make_ctl_with_mock_rig()
    assert ctl.get_func() == ""


# ---------------------------------------------------------------------------
# set_parm / get_parm (stubs)
# ---------------------------------------------------------------------------

def test_set_parm_returns_empty_string():
    ctl, _ = _make_ctl_with_mock_rig()
    assert ctl.set_parm("anything") == ""


def test_get_parm_returns_empty_string():
    ctl, _ = _make_ctl_with_mock_rig()
    assert ctl.get_parm() == ""


# ---------------------------------------------------------------------------
# set_vfo / get_vfo
# ---------------------------------------------------------------------------

def test_set_vfo_calls_rig_with_resolved_constant():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    expected_const = getattr(_hl, "RIG_VFO_A")
    result = ctl.set_vfo("A")
    mock_rig.set_vfo.assert_called_once_with(expected_const)
    assert result == ""


def test_set_vfo_raises_for_unknown_vfo():
    ctl, _ = _make_ctl_with_mock_rig()
    # Explicitly pin the attribute to None so getattr returns None for this name
    _hl.RIG_VFO_NXYZZY = None
    with pytest.raises(ValueError, match="Unknown VFO"):
        ctl.set_vfo("NXYZZY")


def test_set_vfo_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_vfo.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_vfo("A")


def test_get_vfo_calls_rig_and_returns_string():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_vfo.return_value = "VFOA"
    result = ctl.get_vfo()
    mock_rig.get_vfo.assert_called_once_with()
    assert result == "VFOA"


def test_get_vfo_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_vfo.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_vfo()


# ---------------------------------------------------------------------------
# set_antenna / get_antenna
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("antenna", [1, 2])
def test_set_antenna_calls_rig_and_returns_empty(antenna: int) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.set_antenna(antenna)
    mock_rig.set_ant.assert_called_once_with(_hl.RIG_VFO_CURR, antenna)
    assert result == ""


def test_set_antenna_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.set_ant.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.set_antenna(1)


def test_get_antenna_returns_int():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_ant.return_value = 2
    result = ctl.get_antenna()
    mock_rig.get_ant.assert_called_once_with(_hl.RIG_VFO_CURR)
    assert result == 2
    assert isinstance(result, int)


def test_get_antenna_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_ant.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.get_antenna()


# ---------------------------------------------------------------------------
# rig_reset
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "signal, const_name",
    [
        ("NONE", "RIG_RESET_NONE"),
        ("SOFTWARE_RESET", "RIG_RESET_SOFT"),
        ("VFO_RESET", "RIG_RESET_VFO"),
        ("MEMORY_CLEAR_RESET", "RIG_RESET_MCALL"),
        ("MASTER_RESET", "RIG_RESET_MASTER"),
    ],
)
def test_rig_reset_valid_signals(signal: str, const_name: str) -> None:
    ctl, mock_rig = _make_ctl_with_mock_rig()
    result = ctl.rig_reset(signal)
    mock_rig.reset.assert_called_once_with(getattr(_hl, const_name))
    assert result == ""


def test_rig_reset_raises_for_unknown_signal():
    ctl, _ = _make_ctl_with_mock_rig()
    with pytest.raises(ValueError, match="Unknown reset signal"):
        ctl.rig_reset("SELF_DESTRUCT")


def test_rig_reset_reraises_on_error():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.reset.side_effect = RuntimeError("hw error")
    with pytest.raises(RuntimeError):
        ctl.rig_reset("NONE")


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

def test_thread_safety_concurrent_get_frequency():
    ctl, mock_rig = _make_ctl_with_mock_rig()
    mock_rig.get_freq.return_value = 145000000
    results: list[int] = []
    errors: list[Exception] = []

    def worker() -> None:
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

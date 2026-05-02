import pytest
from unittest.mock import MagicMock, create_autospec

from rig_remote.rig_backends.gqrx_rigctl import GQRXRigCtl
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType
from rig_remote.models.rig_endpoint import RigEndpoint


def _make_ctl(mode_translator=None):
    endpoint = RigEndpoint(backend=BackendType.GQRX, hostname="localhost", port=7356)
    ctl = GQRXRigCtl(endpoint=endpoint, mode_translator=mode_translator)
    ctl._send_message = create_autospec(ctl._send_message)
    return ctl


@pytest.mark.parametrize(
    "frequency, expected_cmd",
    [
        (145000000, "F 145000000"),
        (0, "F 0"),
        (1, "F 1"),
    ],
)
def test_set_frequency_valid_sends_command(frequency, expected_cmd):
    ctl = _make_ctl()
    ctl.set_frequency(frequency)
    ctl._send_message.assert_called_once_with(request=expected_cmd)


@pytest.mark.parametrize(
    "bad_value",
    ["not_a_number", "abc", None],
)
def test_set_frequency_non_numeric_raises(bad_value):
    ctl = _make_ctl()
    with pytest.raises(ValueError):
        ctl.set_frequency(bad_value)


@pytest.mark.parametrize(
    "response, expected",
    [
        ("145000000", 145000000),
        ("7000000.5", 7000000),
        ("0", 0),
    ],
)
def test_get_frequency_string_response_cast_to_int(response, expected):
    ctl = _make_ctl()
    ctl._send_message.return_value = response
    assert ctl.get_frequency() == expected


def test_get_frequency_non_numeric_response_raises():
    ctl = _make_ctl()
    ctl._send_message.return_value = "not_a_number"
    with pytest.raises((ValueError, Exception)):
        ctl.get_frequency()


@pytest.mark.parametrize(
    "response, expected",
    [
        ("42", 42),
        ("-30.5", -30),
        ("0.9", 0),
    ],
)
def test_get_level_string_response_cast(response, expected):
    ctl = _make_ctl()
    ctl._send_message.return_value = response
    assert ctl.get_level() == expected


def test_get_level_non_string_raises():
    ctl = _make_ctl()
    ctl._send_message.return_value = 42
    with pytest.raises(ValueError):
        ctl.get_level()


def test_set_mode_delegates_to_translator_and_sends():
    translator = MagicMock(spec=ModeTranslator)
    translator.to_backend.return_value = "FM"
    ctl = _make_ctl(mode_translator=translator)
    ctl.set_mode("FM")
    translator.to_backend.assert_called_once_with("FM")
    ctl._send_message.assert_called_once_with(request="M FM")


def test_get_mode_sends_m_command_and_translates():
    translator = MagicMock(spec=ModeTranslator)
    translator.from_backend.return_value = "AM"
    ctl = _make_ctl(mode_translator=translator)
    ctl._send_message.return_value = "AM"
    result = ctl.get_mode()
    ctl._send_message.assert_called_once_with(request="m")
    translator.from_backend.assert_called_once_with("AM")
    assert result == "AM"


def test_get_mode_strips_newline_before_translate():
    translator = MagicMock(spec=ModeTranslator)
    translator.from_backend.return_value = "FM"
    ctl = _make_ctl(mode_translator=translator)
    ctl._send_message.return_value = "FM\n"
    ctl.get_mode()
    translator.from_backend.assert_called_once_with("FM")


@pytest.mark.parametrize(
    "xit, expected_cmd",
    [
        (0, "Z 0"),
        (500, "Z 500"),
        (-500, "Z -500"),
    ],
)
def test_set_xit_sends_z_command(xit, expected_cmd):
    ctl = _make_ctl()
    ctl._send_message.return_value = "RPRT 0"
    ctl.set_xit(xit)
    ctl._send_message.assert_called_once_with(expected_cmd)


def test_get_xit_sends_lowercase_z():
    ctl = _make_ctl()
    ctl._send_message.return_value = "0"
    ctl.get_xit()
    ctl._send_message.assert_called_once_with("z")


@pytest.mark.parametrize(
    "vfo",
    ["VFOA", "VFOB", "VFOC", "currVFO", "VFO", "MEM", "Main", "Sub", "TX", "RX"],
)
def test_set_vfo_valid_sends_command(vfo):
    ctl = _make_ctl()
    ctl._send_message.return_value = "RPRT 0"
    ctl.set_vfo(vfo)
    ctl._send_message.assert_called_once_with(f"V {vfo}")


@pytest.mark.parametrize(
    "bad_vfo",
    ["INVALID", "vfoa", 123, ""],
)
def test_set_vfo_invalid_raises(bad_vfo):
    ctl = _make_ctl()
    with pytest.raises(ValueError):
        ctl.set_vfo(bad_vfo)


@pytest.mark.parametrize(
    "split_mode",
    ["AM", "FM", "CW", "CWR", "USB", "LSB", "RTTY", "RTTYR", "WFM",
     "AMS", "PKTLSB", "PKTUSB", "PKTFM", "ECSSUSB", "ECSSLSB",
     "FAX", "SAM", "SAL", "SAH", "DSB"],
)
def test_set_split_mode_valid_sends_command(split_mode):
    ctl = _make_ctl()
    ctl._send_message.return_value = "RPRT 0"
    ctl.set_split_mode(split_mode)
    ctl._send_message.assert_called_once_with(f"X {split_mode}")


@pytest.mark.parametrize(
    "bad_mode",
    ["UNKNOWN", "wfm", 0, ""],
)
def test_set_split_mode_invalid_raises(bad_mode):
    ctl = _make_ctl()
    with pytest.raises(ValueError):
        ctl.set_split_mode(bad_mode)


@pytest.mark.parametrize(
    "reset_signal, expected_int",
    [
        ("NONE", 0),
        ("SOFTWARE_RESET", 1),
        ("VFO_RESET", 2),
        ("MEMORY_CLEAR_RESET", 4),
        ("MASTER_RESET", 8),
    ],
)
def test_rig_reset_valid_sends_command(reset_signal, expected_int):
    ctl = _make_ctl()
    ctl._send_message.return_value = "RPRT 0"
    ctl.rig_reset(reset_signal)
    ctl._send_message.assert_called_once_with(f"* {expected_int}")


@pytest.mark.parametrize(
    "bad_signal",
    ["INVALID", "none", 0, "SOFT"],
)
def test_rig_reset_invalid_raises(bad_signal):
    ctl = _make_ctl()
    with pytest.raises(ValueError):
        ctl.rig_reset(bad_signal)


def test_set_frequency_with_passthrough_translator():
    translator = ModeTranslator(BackendType.GQRX)
    ctl = _make_ctl(mode_translator=translator)
    ctl.set_frequency(100000000)
    ctl._send_message.assert_called_once_with(request="F 100000000")

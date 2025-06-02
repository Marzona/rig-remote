import pytest
from mock import create_autospec, patch
from rig_remote.rigctl import RigCtl
from rig_remote.models.rig_endpoint import RigEndpoint


@pytest.mark.parametrize(
    "command, message",
    [
        ("start_recording", "AOS"),
        ("stop_recording", "LOS"),
    ],
)
def test_rigctl_set_commands_no_param(command, message):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    getattr(rigctl, command)()
    rigctl._send_message.assert_called_once_with(request=message)


@pytest.mark.parametrize(
    "command, parameter, message",
    [
        ("set_frequency", "1000000", "F 1000000"),
        ("set_mode", "FM", "M FM"),
        ("set_vfo", "VFOA", "V VFOA"),
        ("set_vfo", "VFOB", "V VFOB"),
        ("set_vfo", "VFOC", "V VFOC"),
        ("set_vfo", "currVFO", "V currVFO"),
        ("set_vfo", "VFO", "V VFO"),
        ("set_vfo", "MEM", "V MEM"),
        ("set_vfo", "Main", "V Main"),
        ("set_vfo", "Sub", "V Sub"),
        ("set_vfo", "TX", "V TX"),
        ("set_vfo", "RX", "V RX"),
        ("set_rit", 22, "J 22"),
        ("set_xit", "xit", "J xit"),
        ("set_split_freq", 22, "I 22"),
        ("set_split_mode", "AM", "X AM"),
        ("set_split_mode", "FM", "X FM"),
        ("set_split_mode", "CW", "X CW"),
        ("set_split_mode", "CWR", "X CWR"),
        ("set_split_mode", "USB", "X USB"),
        ("set_split_mode", "LSB", "X LSB"),
        ("set_split_mode", "RTTY", "X RTTY"),
        ("set_split_mode", "RTTYR", "X RTTYR"),
        ("set_split_mode", "WFM", "X WFM"),
        ("set_split_mode", "AMS", "X AMS"),
        ("set_split_mode", "PKTLSB", "X PKTLSB"),
        ("set_split_mode", "PKTUSB", "X PKTUSB"),
        ("set_split_mode", "PKTFM", "X PKTFM"),
        ("set_split_mode", "ECSSUSB", "X ECSSUSB"),
        ("set_split_mode", "ECSSLSB", "X ECSSLSB"),
        ("set_split_mode", "FAX", "X FAX"),
        ("set_split_mode", "SAM", "X SAM"),
        ("set_split_mode", "SAL", "X SAL"),
        ("set_split_mode", "SAH", "X SAH"),
        ("set_split_mode", "DSB", "X DSB"),
        ("set_func", "FAGC", "U FAGC"),
        ("set_func", "NB", "U NB"),
        ("set_func", "COMP", "U COMP"),
        ("set_func", "VOX", "U VOX"),
        ("set_func", "TONE", "U TONE"),
        ("set_func", "TSQL", "U TSQL"),
        ("set_func", "SBKIN", "U SBKIN"),
        ("set_func", "FBKIN", "U FBKIN"),
        ("set_func", "ANF", "U ANF"),
        ("set_func", "NR", "U NR"),
        ("set_func", "AIP", "U AIP"),
        ("set_func", "APF", "U APF"),
        ("set_func", "MON", "U MON"),
        ("set_func", "MN", "U MN"),
        ("set_func", "RF", "U RF"),
        ("set_func", "ARO", "U ARO"),
        ("set_func", "LOCK", "U LOCK"),
        ("set_func", "MUTE", "U MUTE"),
        ("set_func", "VSC", "U VSC"),
        ("set_func", "REV", "U REV"),
        ("set_func", "SQL", "U SQL"),
        ("set_func", "ABM", "U ABM"),
        ("set_func", "BC", "U BC"),
        ("set_func", "MBC", "U MBC"),
        ("set_func", "AFC", "U AFC"),
        ("set_func", "SATMODE", "U SATMODE"),
        ("set_func", "SCOPE", "U SCOPE"),
        ("set_func", "RESUME", "U RESUME"),
        ("set_func", "TBURST", "U TBURST"),
        ("set_func", "TUNER", "U TUNER"),
        ("set_parm", "ANN", "P ANN"),
        ("set_parm", "BACKLIGHT", "P BACKLIGHT"),
        ("set_parm", "BEEP", "P BEEP"),
        ("set_parm", "TIME", "P TIME"),
        ("set_parm", "BAT", "P BAT"),
        ("set_parm", "KEYLIGHT", "P KEYLIGHT"),
        ("set_antenna", 1, "Y 1"),
        ("rig_reset", "NONE", "* 0"),
        ("rig_reset", "VFO_RESET", "* 2"),
        ("rig_reset", "MEMORY_CLEAR_RESET", "* 4"),
        ("rig_reset", "MASTER_RESET", "* 8"),
    ],
)
def test_rigctl_set_commands(command, parameter, message):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    getattr(rigctl, command)(parameter)
    rigctl._send_message.assert_called_once_with(request=message)


def test_rigctl_set_commands_socket_mock():
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    with patch("socket.socket") as mock_socket:
        rigctl.set_frequency(frequency=1.1)
        assert mock_socket.call_count == 1
        mock_socket().connect.assert_called_once_with(("localhost", 8080))
        mock_socket().sendall.assert_called_once_with((bytearray(b"F 1.1\n")))
        mock_socket().close.assert_called_once()

def test_rigctl_set_commands_socket_mock_exception():
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.sendall.side_effect = TimeoutError("Socket timeout")
        with pytest.raises(TimeoutError):
            rigctl.set_frequency(frequency=1.1)
        assert mock_socket.call_count == 1
        mock_socket().connect.assert_called_once_with(("localhost", 8080))
        mock_socket().sendall.assert_called_once_with((bytearray(b"F 1.1\n")))

@pytest.mark.parametrize(
    "command, message, msg_type",
    [
        ("get_frequency", "f", "str"),
        ("get_mode", "m", "str"),
        ("get_vfo", "v", "str"),
        ("get_rit", "j", "str"),
        ("get_xit", "j", "str"),
        ("get_split_freq", "i", "int"),
        ("get_split_mode", "x", "str"),
        ("get_func", "u", "str"),
        ("get_parm", "p", "str"),
        ("get_antenna", "y", "int"),
        ("get_level", "l", "str"),
    ],
)
def test_rigctl_get_commands(command, message, msg_type):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    if msg_type == "int":
        rigctl._send_message.return_value = 2
    else:
        rigctl._send_message.return_value = "2"
    getattr(rigctl, command)()
    rigctl._send_message.assert_called_once_with(request=message)


@pytest.mark.parametrize(
    "command, message, msg_type",
    [
        ("get_frequency", "f", "int"),
        ("get_mode", "m", "int"),
        ("get_vfo", "v", "int"),
        ("get_rit", "j", "int"),
        ("get_xit", "J", "int"),
        ("get_split_freq", "i", "str"),
        ("get_split_mode", "x", "int"),
        ("get_func", "u", "int"),
        ("get_parm", "p", "int"),
        ("get_antenna", "y", "str"),
        ("get_level", "l", "int"),
    ],
)
def test_rigctl_get_commands_error(command, message, msg_type):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    if msg_type == "int":
        rigctl._send_message.return_value = 2
    else:
        rigctl._send_message.return_value = "2"
    with pytest.raises(ValueError):
        getattr(rigctl, command)()


@pytest.mark.parametrize(
    "command, parameter, message, msg_type",
    [
        ("set_frequency", "tests", "f", "int"),
        ("set_mode", 22, "m", "int"),
        ("set_vfo", 22, "v", "int"),
        ("set_rit", "tests", "j", "int"),
        ("set_xit", 22, "J", "int"),
        ("set_split_freq", "tests", "i", "str"),
        ("set_split_mode", "tests", "x", "int"),
        ("set_func", "tests", "u", "int"),
        ("set_parm", "tests", "p", "int"),
        ("set_antenna", "tests", "y", "str"),
        ("rig_reset", "tests", "*", "str"),
    ],
)
def test_rigctl_set_commands_error(command, parameter, message, msg_type):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    if msg_type == "int":
        rigctl._send_message.return_value = 2
    else:
        rigctl._send_message.return_value = "2"
    with pytest.raises(ValueError):
        getattr(rigctl, command)(parameter)


@pytest.mark.parametrize(
    "command, message",
    [
        ("get_split_mode", "x"),
    ],
)
def test_rigctl_get_commands_no_reqest(command, message):
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    rigctl._send_message.return_value = "2"

    getattr(rigctl, command)()
    rigctl._send_message.assert_called_once_with(message)


def test_rigctl_get_mode_old_gqrx_versions():
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    rigctl._send_message = create_autospec(rigctl._send_message)
    rigctl._send_message.return_value = "FM\n"
    assert rigctl.get_mode() == "FM"

def test_rigctl_send_message_connection_error():
    """Test connection error handling in _send_message."""
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)

    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.connect.side_effect = ConnectionRefusedError()
        with pytest.raises(ConnectionRefusedError):
            rigctl._send_message("tests")


def test_rigctl_send_message_socket_error():
    """Test socket error handling in _send_message."""
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)

    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.sendall.side_effect = OSError()
        with pytest.raises(OSError):
            rigctl._send_message("tests")


def test_rigctl_send_message_receive_error():
    """Test receive error handling in _send_message."""
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)

    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.recv.side_effect = OSError()
        with pytest.raises(OSError):
            rigctl._send_message("tests")



@pytest.fixture
def mock_socket():
    with patch('socket.socket') as mock:
        socket_instance = mock.return_value
        socket_instance.send.return_value = None
        socket_instance.recv.return_value = b"OK\n"
        socket_instance.connect.return_value = None
        yield socket_instance

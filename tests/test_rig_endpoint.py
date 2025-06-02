from rig_remote.models.rig_endpoint import RigEndpoint
import pytest


def test_rig_endpoint_init():
    hostname = "localhost"
    port = 8080
    name = "rig_name"
    number: int = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number, name=name)

    assert rig_endpoint.hostname == hostname
    assert rig_endpoint.port == port
    assert rig_endpoint.number == number
    assert rig_endpoint.name == name
    assert isinstance(rig_endpoint.id, str)


@pytest.mark.parametrize(
    "hostname1,port1, name1, number1",
    [
        ("localhost", 1024, "rig_name", 1),
        ("localhost", 8080, "rig_name", -1),
        ("localhost", 8080, "rig_name", 0),
        ("localhost", 8080, "rig_name", "a"),
    ],
)
def test_rig_endpoint_init_error(hostname1, port1, name1, number1):
    with pytest.raises(ValueError):
        RigEndpoint(hostname=hostname1, port=port1, number=number1, name=name1)


@pytest.mark.parametrize(
    "hostname1,port1, name1, number1, hostname2, port2, name2, number2, expected",
    [
        ("localhost", 8080, "rig_name", 1, "localhost", 8080, "rig_name", 1, True),
        ("localhost", 8080, "rig_name", 1, "localhost", 8081, "rig_name", 1, False),
        ("localhost", 8080, "rig_name", 1, "localhost", 8080, "rig_name2", 1, False),
        ("localhost", 8080, "rig_name", 1, "localhost", 8080, "rig_name", 2, False),
        ("localhost", 8080, "rig_name", 1, "127.0.0.1", 8080, "rig_name", 2, False),
        ("localhost", 8080, "rig_name", 1, "127.0.0.1", 8080, "rig_name", 2, False),
    ],
)
def test_rig_endpoint_comparison(
    hostname1, port1, name1, number1, hostname2, port2, name2, number2, expected
):
    rig_endpoint1 = RigEndpoint(
        hostname=hostname1, port=port1, number=number1, name=name1
    )
    rig_endpoint2 = RigEndpoint(
        hostname=hostname2, port=port2, number=number2, name=name2
    )

    assert (rig_endpoint1 == rig_endpoint2) == expected


@pytest.mark.parametrize(
    "port",
    [
        8080,
        "8080",
    ],
)
def test_rig_endpoint_set_port(port):
    hostname = "localhost"
    port = 8080
    name = "rig_name"
    number: int = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number, name=name)
    rig_endpoint.set_port(port=port)


@pytest.mark.parametrize(
    "test_port",
    [
        1024,
        1023,
        -1,
        0,
    ],
)
def test_rig_endpoint_set_port_error(test_port):
    hostname = "localhost"
    port = 8080
    name = "rig_name"
    number: int = 1
    with pytest.raises(ValueError):
        RigEndpoint(hostname=hostname, port=port, number=number, name=name).set_port(
            port=test_port
        )


@pytest.mark.parametrize(
    "test_hostname",
    [
        "tests",
        "192.168.1.10.1",
        "192.168.1.300",
    ],
)
def test_rig_endpoint_set_hostname_error(test_hostname):
    hostname = "localhost"
    port = 8080
    name = "rig_name"
    number: int = 1
    with pytest.raises(ValueError):
        RigEndpoint(
            hostname=hostname, port=port, number=number, name=name
        ).set_hostname(hostname=test_hostname)


@pytest.mark.parametrize(
    "test_hostname",
    [
        "localhost",
        "127.0.0.1",
    ],
)
def test_rig_endpoint_set_hostname(test_hostname):
    hostname = "localhost"
    port = 8080
    name = "rig_name"
    number: int = 1
    RigEndpoint(hostname=hostname, port=port, number=number, name=name).set_hostname(
        hostname=test_hostname
    )

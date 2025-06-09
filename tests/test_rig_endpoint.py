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
    "hostname, port, name, number",
    [
        (ip, port, "test_rig", number)
        for ip in [
            "192.168.1.1",
            "192.168.0.100",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1"
        ]
        for port in [1025, 3000, 5000, 7000, 9000]
        for number in [0, 1]
    ]
)
def test_rig_endpoint_valid_ports_and_numbers(hostname, port, name, number):
    """Test RigEndpoint initialization with various private IPs, ports and numbers."""
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number, name=name)

    assert rig_endpoint.hostname == hostname
    assert rig_endpoint.port == port
    assert rig_endpoint.number == number
    assert rig_endpoint.name == name
    assert isinstance(rig_endpoint.id, str)


@pytest.mark.parametrize(
    "endpoint1_data, endpoint2_data, expected",
    [
        (
                {"hostname": "192.168.1.1", "port": 1025, "name": "rig1", "number": 0},
                {"hostname": "192.168.1.1", "port": 1025, "name": "rig1", "number": 0},
                True
        ),
        (
                {"hostname": "192.168.1.1", "port": 1025, "name": "rig1", "number": 0},
                {"hostname": "192.168.1.1", "port": 1026, "name": "rig1", "number": 0},
                False
        ),
        (
                {"hostname": "10.0.0.1", "port": 5000, "name": "rig1", "number": 1},
                {"hostname": "10.0.0.2", "port": 5000, "name": "rig1", "number": 1},
                False
        ),
        (
                {"hostname": "127.0.0.1", "port": 9000, "name": "rig_test", "number": 0},
                {"hostname": "127.0.0.1", "port": 9000, "name": "rig_test", "number": 1},
                False
        ),
        (
                {"hostname": "172.16.0.1", "port": 3000, "name": "rig_a", "number": 0},
                {"hostname": "172.16.0.1", "port": 3000, "name": "rig_b", "number": 0},
                False
        )
    ]
)
def test_rig_endpoint_equality(endpoint1_data, endpoint2_data, expected):
    """Test equality comparison between RigEndpoint objects with various configurations."""
    endpoint1 = RigEndpoint(**endpoint1_data)
    endpoint2 = RigEndpoint(**endpoint2_data)

    assert (endpoint1 == endpoint2) == expected


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

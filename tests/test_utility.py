import pytest
from rig_remote.utility import (
    khertz_to_hertz,
)


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (0, 0),
        (1, 1000),
        (10, 10000),
        (100, 100000),
        (1000, 1000000),
        (5000, 5000000),
        (10000, 10000000),
        (50000, 50000000),
        (100000, 100000000),
        (-1, -1000),
        (-100, -100000),
        (-1000, -1000000),
    ],
)
def test_utility_khertz_to_hertz_valid_inputs(input_value, expected_output):
    """Test frequency conversion from kHz to Hz with valid integer inputs."""
    assert khertz_to_hertz(input_value) == expected_output


@pytest.mark.parametrize(
    "invalid_value",
    [
        "invalid",
        "1000",
        1000.5,
        10.25,
        None,
        [],
        {},
        [1000],
        {"value": 1000},
        (1000,),
    ],
)
def test_utility_khertz_to_hertz_invalid_inputs(invalid_value):
    """Test frequency conversion raises TypeError for non-integer inputs."""
    with pytest.raises(TypeError, match="value must be an integer"):
        khertz_to_hertz(invalid_value)


@pytest.mark.parametrize(
    "bool_value, expected_output",
    [
        (True, 1000),
        (False, 0),
    ],
)
def test_utility_khertz_to_hertz_boolean_inputs(bool_value, expected_output):
    """Test frequency conversion with boolean inputs (bool is subclass of int in Python)."""
    assert khertz_to_hertz(bool_value) == expected_output

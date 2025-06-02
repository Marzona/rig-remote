from rig_remote.models.channel import Channel
import pytest


def test_channel_init_happy_path():
    test_channel = Channel(input_frequency="1000", modulation="AM")
    assert test_channel.frequency == 1000
    assert test_channel.frequency_as_string == "1,000"
    assert test_channel.modulation == "AM"
    assert isinstance(test_channel.id, str)


@pytest.mark.parametrize(
    "input_frequency1, modulation1, input_frequency2, modulation2, expected",
    [
        ("1", "AM", "1", "FM", False),
        ("1", "AM", "2", "AM", False),
        ("1", "AM", "1", "AM", True),
    ],
)
def test_channel_comparison(
    input_frequency1, modulation1, input_frequency2, modulation2, expected
):
    test_channel1 = Channel(input_frequency=input_frequency1, modulation=modulation1)
    test_channel2 = Channel(input_frequency=input_frequency2, modulation=modulation2)
    assert (test_channel1 == test_channel2) == expected


def test_channel_invalid_frequency():
    with pytest.raises(ValueError):
        Channel(input_frequency="a", modulation="AM")
    with pytest.raises(ValueError):
        Channel(input_frequency="1,", modulation="AM")


def test_channel_invalid_modulation():
    with pytest.raises(ValueError):
        Channel(input_frequency="1", modulation="AMM")

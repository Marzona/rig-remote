from rig_remote.models.channel import Channel
import pytest
from rig_remote.models.modulation_modes import ModulationModes
from rig_remote.models.channel import Channel


@pytest.mark.parametrize(
    "frequency, modulation",
    [
        (freq, mode)
        for freq in [100, 25000]
        for mode in ModulationModes
    ]
)
def test_channel_init_all_modulations(frequency, modulation):
    """Test Channel initialization with test frequencies and all ModulationModes."""
    channel = Channel(input_frequency=frequency, modulation=modulation)

    assert channel.frequency == frequency
    assert channel.frequency_as_string == f"{frequency:,}"
    assert channel.modulation == modulation
    assert isinstance(channel.id, str)


@pytest.mark.parametrize(
    "channel1_freq, channel1_mod, channel2_freq, channel2_mod, expected_equal",
    [
        (1000, ModulationModes.AM, 1000, ModulationModes.AM, True),
        (1000, ModulationModes.AM, 2000, ModulationModes.AM, False),
        (1000, ModulationModes.AM, 1000, ModulationModes.FM, False),
        (25000, ModulationModes.USB, 25000, ModulationModes.USB, True),
        (25000, ModulationModes.USB, 25000, ModulationModes.LSB, False),
        (4000000, ModulationModes.CW, 4000000, ModulationModes.CW, True),
        (4000000, ModulationModes.CW, 4000000, ModulationModes.CWR, False),
        (250000, ModulationModes.FM, 250000, ModulationModes.WFM, False),
        (250000, ModulationModes.FM, 250001, ModulationModes.FM, False)
    ]
)
def test_channel_equality(channel1_freq, channel1_mod, channel2_freq, channel2_mod, expected_equal):
    """Test Channel equality comparison with various frequency and modulation combinations."""
    channel1 = Channel(input_frequency=channel1_freq, modulation=channel1_mod)
    channel2 = Channel(input_frequency=channel2_freq, modulation=channel2_mod)

    assert (channel1 == channel2) == expected_equal

@pytest.mark.parametrize(
    "input_frequency, modulation",
    [
        ("invalid", ModulationModes.AM),
        ("1,000,", ModulationModes.FM),
        (-1, ModulationModes.USB),
        (500000001, ModulationModes.LSB),
        ("abc123", ModulationModes.CW),
        (1000, "InvalidMode"),
        ("", ModulationModes.AM),
        ("#123", ModulationModes.FM)
    ]
)
def test_invalid_channel_creation(input_frequency, modulation):
    """Test Channel initialization with invalid parameters that should raise ValueError."""
    with pytest.raises(ValueError):
        Channel(input_frequency=input_frequency, modulation=modulation)

def test_channel_invalid_frequency():
    with pytest.raises(ValueError):
        Channel(input_frequency="a", modulation="AM")
    with pytest.raises(ValueError):
        Channel(input_frequency="1,", modulation="AM")


def test_channel_invalid_modulation():
    with pytest.raises(ValueError):
        Channel(input_frequency=1, modulation="AMM")

@pytest.mark.parametrize(
    "input_frequency, modulation, frequency_as_string",
    [
        (1, ModulationModes.WFM_ST_OIRT, "1"),
        (1000, ModulationModes.AMS, "1,000"),
        (25000, ModulationModes.CWU, "25,000"),
        (250000, ModulationModes.USB, "250,000"),
        (1900000, ModulationModes.CWL, "1,900,000"),
        (4000000, ModulationModes.LSB, "4,000,000"),
        (1000, ModulationModes.CW, "1,000"),
        (25000, ModulationModes.CWR, "25,000"),
        (250000, ModulationModes.RTTY, "250,000"),
        (1900000, ModulationModes.RTTYR, "1,900,000"),
        (4000000, ModulationModes.AM, "4,000,000"),
        (1000, ModulationModes.FM, "1,000"),
        (25000, ModulationModes.WFM, "25,000"),
        (250000, ModulationModes.PKTLSB, "250,000"),
        (1900000, ModulationModes.PKTU, "1,900,000"),
        (4000000, ModulationModes.SB, "4,000,000"),
        (1000, ModulationModes.PKTFM, "1,000"),
        (25000, ModulationModes.ECSSUSB, "25,000"),
        (250000, ModulationModes.ECSSLSB, "250,000"),
        (1900000, ModulationModes.WFM_ST, "1,900,000"),
        (4000000, ModulationModes.FAX, "4,000,000"),
        (1000, ModulationModes.SAM, "1,000"),
        (25000, ModulationModes.SAL, "25,000"),
        (250000, ModulationModes.SAH, "250,000"),
        (1900000, ModulationModes.DSB, "1,900,000")
    ]
)
def test_channel_frequency_and_modulation(input_frequency, modulation, frequency_as_string):
    """Test Channel initialization with various frequencies and all modulation modes."""
    channel = Channel(input_frequency=input_frequency, modulation=modulation)

    assert channel.frequency == input_frequency
    assert channel.frequency_as_string == frequency_as_string
    assert channel.modulation == modulation
    assert isinstance(channel.id, str)
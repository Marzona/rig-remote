from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
import pytest


@pytest.mark.parametrize(
    "channel1,description1, lockout1",
    [
        (Channel(input_frequency=1, modulation="AM"), "test_descroption", "L"),
        (Channel(input_frequency=1, modulation="AM"), "test_descroption", "0"),
        (Channel(input_frequency=1, modulation="AM"), "test_descroption", ""),
        (Channel(input_frequency=1, modulation="AM"), "test_descroption", "O"),
    ],
)
def test_bookmark_init(channel1, description1, lockout1):
    bookmark = Bookmark(channel=channel1, description=description1, lockout=lockout1)

    assert bookmark.channel == channel1
    assert bookmark.description == description1
    assert bookmark.lockout == lockout1
    assert isinstance(bookmark.id, str)


@pytest.mark.parametrize(
    "channel1,description1, lockout1",
    [
        (Channel(input_frequency=1, modulation="am"), "test_descroption", "C"),
        (Channel(input_frequency=1, modulation="am"), "", "L"),
    ],
)
def test_bookmark_init_error(channel1, description1, lockout1):
    with pytest.raises(ValueError):
        Bookmark(channel=channel1, description=description1, lockout=lockout1)


@pytest.mark.parametrize(
    "channel1, descripton1, lockout1, channel2, description2, lockout2, expected",
    [
        (
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            True,
        ),
        (
            Channel(input_frequency=2, modulation="AM"),
            "test_description",
            "L",
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            False,
        ),
        (
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "O",
            True,
        ),
        (
            Channel(input_frequency=1, modulation="AM"),
            "tests",
            "L",
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            False,
        ),
        (
            Channel(input_frequency=1, modulation="FM"),
            "test_description",
            "L",
            Channel(input_frequency=1, modulation="AM"),
            "test_description",
            "L",
            False,
        ),
    ],
)
def test_bookmark_comparison(
    channel1, descripton1, lockout1, channel2, description2, lockout2, expected
):
    test_bookmark1 = Bookmark(
        channel=channel1, description=descripton1, lockout=lockout1
    )
    test_bookmark2 = Bookmark(
        channel=channel2, description=description2, lockout=lockout2
    )

    assert (test_bookmark1 == test_bookmark2) == expected

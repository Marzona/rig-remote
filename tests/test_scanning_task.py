import pytest

from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.models.modulation_modes import ModulationModes


@pytest.mark.parametrize(
    "frequency_modulation, scan_mode, new_bookmarks_list, range_min, range_max, interval, delay, passes, sgn_level, wait, record, auto_bookmark, log, bookmarks",
    [
        (
            "AM",
            "frequency",
            [],
            6,
            4,
            1000,
            1,
            1,
            0,
            False,
            False,
            False,
            False,
            [
                Bookmark(
                    channel=Channel(input_frequency=1, modulation="AM"),
                    description="description1",
                    lockout="L",
                )
            ],
        ),
        (
            "AM",
            "frequenc",
            [],
            1,
            4,
            1000,
            1,
            1,
            0,
            False,
            False,
            False,
            False,
            [
                Bookmark(
                    channel=Channel(input_frequency=1, modulation="AM"),
                    description="description1",
                    lockout="L",
                )
            ],
        ),
        (
            "AM",
            "bookmark",
            [],
            1,
            4,
            1000,
            1,
            1,
            0,
            False,
            False,
            False,
            False,
            [
                Bookmark(
                    channel=Channel(input_frequency=1, modulation="AM"),
                    description="description1",
                    lockout="L",
                )
            ],
        ),
        (
            "AM",
            "not_supported_mode",
            [],
            1,
            4,
            1000,
            1,
            1,
            0,
            False,
            False,
            False,
            False,
            [
                Bookmark(
                    channel=Channel(input_frequency=1, modulation="AM"),
                    description="description1",
                    lockout="L",
                )
            ],
        ),
    ],
)
def test_scanning_task_init_error(
    frequency_modulation,
    scan_mode,
    new_bookmarks_list,
    range_min,
    range_max,
    interval,
    delay,
    passes,
    sgn_level,
    wait,
    record,
    auto_bookmark,
    log,
    bookmarks,
):
    with pytest.raises(ValueError):
        ScanningTask(
            frequency_modulation=frequency_modulation,
            scan_mode=scan_mode,
            new_bookmarks_list=new_bookmarks_list,
            range_min=range_min,
            range_max=range_max,
            interval=interval,
            delay=delay,
            passes=passes,
            sgn_level=sgn_level,
            wait=wait,
            record=record,
            auto_bookmark=auto_bookmark,
            log=log,
            bookmarks=bookmarks,
        )


@pytest.mark.parametrize(
    "frequency_modulation, interval, delay, passes",
    [
        (mod, interval, delay, passes)
        for mod in ModulationModes
        for interval in range(1, 6)
        for delay in range(1, 6)
        for passes in range(1, 6)
    ],
)
def test_scanning_task_full_params(frequency_modulation, interval, delay, passes):
    """Test ScanningTask with all combinations of modulation modes and scanning parameters."""
    interval_hz = interval * 1000  # Convert to Hz since _MIN_INTERVAL is 1000
    range_max = 500000001  # Should be corrected to 500000000

    task = ScanningTask(
        frequency_modulation=frequency_modulation,
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=-100,  # Should be corrected to 0
        range_max=range_max,
        interval=interval_hz,
        delay=delay,
        passes=passes,
        sgn_level=0,
        wait=0,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[],
    )

    assert task.frequency_modulation == frequency_modulation
    assert task.interval == max(interval_hz, task._MIN_INTERVAL)
    assert task.delay == delay
    assert task.passes == passes
    assert task.range_min == 0
    assert task.range_max == 500000000
    assert task.error is None


@pytest.mark.parametrize(
    "passes, expected_passes",
    [
        (0, 1),
        (-1, 1),
        (-10, 1),
        (-100, 1),
    ],
)
def test_scanning_task_passes_less_than_one(passes, expected_passes):
    """Test ScanningTask corrects passes < 1 to minimum value of 1."""
    task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=100000,
        range_max=200000,
        interval=1000,
        delay=1,
        passes=passes,
        sgn_level=0,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[],
    )

    assert task.passes == expected_passes
    assert task.error is None

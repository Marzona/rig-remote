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
        (-1, 1),
        (-10, 1),
        (-100, 1),
    ],
)
def test_scanning_task_passes_less_than_one(passes, expected_passes):
    """Negative passes are clamped to 1; 0 means infinite and is kept (see the infinite-passes tests)."""
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


# ---------------------------------------------------------------------------
# ScanningTask.apply_update
# ---------------------------------------------------------------------------

def _apply_task(**kw) -> ScanningTask:
    params = dict(
        frequency_modulation="FM", scan_mode="frequency", new_bookmarks_list=[],
        range_min=100_000_000, range_max=101_000_000, interval=100_000, delay=1,
        passes=1, sgn_level=-40, wait=False, record=False, auto_bookmark=False,
        log=False, bookmarks=[],
    )
    params.update(kw)
    return ScanningTask(**params)


@pytest.mark.parametrize("name,value,attr,expected", [
    ("interval", 0, "interval", 1000),
    ("interval", -1, "interval", 1000),
    ("interval", 5000, "interval", 5000),
    ("passes", 0, "passes", 0),   # INFINITE_PASSES is valid, not clamped
    ("passes", -3, "passes", 1),
    ("passes", 4, "passes", 4),
    ("delay", -1, "delay", 0),
    ("delay", 9, "delay", 9),
    ("sgn_level", -500, "sgn_level", -500),
    ("wait", True, "wait", True),
    ("record", True, "record", True),
    ("range_min", -1, "range_min", 0),
    ("range_max", 600_000_000, "range_max", 500_000_000),
    ("range_max", 99_000_000, "range_max", 100_001_000),
    ("range_min", 101_000_000, "range_min", 100_999_000),
])
def test_apply_update_clamps_and_logs(name, value, attr, expected, caplog):
    task = _apply_task()
    with caplog.at_level("ERROR"):
        task.apply_update(name, value)
    assert getattr(task, attr) == expected
    assert task.range_min < task.range_max
    clamped = getattr(task, attr) != value
    assert (len(caplog.records) > 0) == clamped


def test_apply_update_range_pinned_at_zero_reopens_band():
    task = _apply_task(range_min=0, range_max=1000)
    task.apply_update("range_max", -5)
    assert (task.range_min, task.range_max) == (0, 1000)


def test_apply_update_range_not_enforced_in_bookmark_mode():
    task = _apply_task(scan_mode="bookmarks")
    task.apply_update("range_max", 50_000_000)
    assert task.range_max == 50_000_000


@pytest.mark.parametrize("name,value,exc", [
    ("bogus", 1, ValueError),
    ("scan_mode", 1, ValueError),
    ("wait", 1, TypeError),
    ("passes", True, TypeError),
    ("passes", "3", TypeError),
])
def test_apply_update_rejects_wrong_name_or_type(name, value, exc, caplog):
    task = _apply_task()
    with caplog.at_level("ERROR"), pytest.raises(exc):
        task.apply_update(name, value)  # type: ignore[arg-type]
    assert caplog.records


def test_scanning_task_init_negative_delay_clamped():
    assert _apply_task(delay=-2).delay == 0


def test_scanning_task_passes_zero_means_infinite(caplog):
    """passes=0 is INFINITE_PASSES (the UI's "0=Infinite", the config default): kept, not clamped."""
    with caplog.at_level("ERROR"):
        task = _apply_task(passes=0)
    assert task.passes == 0
    assert not caplog.records

"""
Functional tests for frequency scanning against a live gqrx instance.

These tests duplicate test_frequency_scanning.py but use a real RigCtl
connected to gqrx at 127.0.0.1:7356.  No mocks are used on RigCtl — every
command goes over the network.

After each scan the test re-tunes each step, reads back the frequency and
mode via get_frequency() / get_mode(), builds two Bookmark objects — one
from what was SENT and one from what was READ — and asserts they are equal.
Bookmark equality (via __eq__) compares Channel (frequency + modulation),
so the assertion proves the rig accepted and confirmed every tuning command.

The module is skipped automatically when gqrx is not reachable.
"""

import time

import pytest
from unittest.mock import Mock

from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningConfig, create_scanner
from rig_remote.stmessenger import STMessenger
from functional_tests.gqrx_config import (
    _GQRX_HOST,
    _GQRX_PORT,
    _SETTLE_S,
    _MAX_READBACK_RETRIES,
    _gqrx_reachable,
)


# ---------------------------------------------------------------------------
# Module-level availability guard
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not _gqrx_reachable(),
    reason=f"gqrx not available at {_GQRX_HOST}:{_GQRX_PORT} — skipping hardware tests",
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> tuple[RigCtl, list[tuple[int, str]]]:
    """Return a real RigCtl bound to gqrx, plus a list that records every
    (frequency, modulation) pair issued by channel_tune.

    _send_message is wrapped at the instance level (no mock library) so that
    consecutive ``F <freq>`` / ``M <mode>`` pairs are captured.
    """
    rigctl = RigCtl(
        endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1)
    )

    tuned: list[tuple[int, str]] = []
    pending_freq: list[int | None] = [None]
    original_send = rigctl._send_message

    def _recording_send(request: str) -> str:
        result = original_send(request)
        if request.startswith("F "):
            pending_freq[0] = int(float(request[2:]))
        elif request.startswith("M ") and pending_freq[0] is not None:
            tuned.append((pending_freq[0], request[2:].strip()))
            pending_freq[0] = None
        return result

    rigctl._send_message = _recording_send  # type: ignore[method-assign]
    return rigctl, tuned


def _make_queue() -> Mock:
    """STMessenger stub: queue is always empty."""
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _make_config() -> ScanningConfig:
    """ScanningConfig with a short settle delay so gqrx can process commands."""
    return ScanningConfig(
        time_wait_for_tune=_SETTLE_S,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _freq_task(
    range_min: int,
    range_max: int,
    interval: int,
    modulation: str = "FM",
    passes: int = 1,
) -> ScanningTask:
    return ScanningTask(
        frequency_modulation=modulation,
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        delay=0,
        passes=passes,
        sgn_level=-40,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[],
    )


def _assert_round_trips(rigctl: RigCtl, tuned_pairs: list[tuple[int, str]]) -> None:
    """For each (frequency, modulation) pair recorded during the scan.

    IMPORTANT: callers must pass a snapshot (``list(tuned)``) rather than the
    live ``tuned`` list.  The recording wrapper on ``_send_message`` is still
    active during verification, so calling ``set_frequency`` / ``set_mode``
    inside this function would append to the original list and cause the loop
    to see spurious extra entries.

    For each pair:

    1. Re-tune gqrx to that frequency and mode.
    2. Read back the active frequency and mode.
    3. Build a *sent* Bookmark and a *read* Bookmark, both with description
       ``"scan_step"`` so that Bookmark.__eq__ reduces to Channel equality
       (frequency + modulation).
    4. Assert sent == read, proving the rig accepted and confirmed the command.
    """
    for freq, modulation in tuned_pairs:
        rigctl.set_frequency(freq)
        rigctl.set_mode(modulation)

        sent_bookmark = bookmark_factory(
            input_frequency=freq,
            modulation=modulation,
            description="scan_step",
        )

        # Retry read-back: gqrx may not have committed the value immediately.
        read_bookmark = None
        for _ in range(_MAX_READBACK_RETRIES):
            time.sleep(_SETTLE_S)
            read_freq = int(rigctl.get_frequency())
            read_mode = rigctl.get_mode().strip()
            read_bookmark = bookmark_factory(
                input_frequency=read_freq,
                modulation=read_mode,
                description="scan_step",
            )
            if sent_bookmark == read_bookmark:
                break

        assert sent_bookmark == read_bookmark, (
            f"Round-trip mismatch at ({freq} Hz, {modulation}) "
            f"after {_MAX_READBACK_RETRIES} attempts: "
            f"sent channel={sent_bookmark.channel}, "
            f"read channel={read_bookmark.channel}"  # type: ignore[union-attr]
        )


# ---------------------------------------------------------------------------
# Test: single pass, FM broadcast band
# ---------------------------------------------------------------------------

def test_scanning_frequency_all_steps_tuned_fm_broadcast():
    """Scan a portion of the FM broadcast band (88–93 MHz, 1 MHz step, 5 steps).

    Uses a 5-step window rather than the full 88–108 MHz band to keep the
    number of back-to-back TCP connections within gqrx's capacity.  Verifies
    that every step is tuned and confirmed via Bookmark round-trip comparison.
    """
    RANGE_MIN = 88_000_000
    RANGE_MAX = 93_000_000   # 5 steps: 88, 89, 90, 91, 92 MHz
    INTERVAL  =  1_000_000

    expected_frequencies = list(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    assert [f for f, _ in tuned] == expected_frequencies, (
        f"Expected {len(expected_frequencies)} steps, got {len(tuned)}"
    )
    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Test: multiple passes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("passes", [1, 2, 3])
def test_scanning_frequency_multiple_passes_multiplies_tune_calls(passes):
    """Each additional pass repeats the full sweep; every unique step is confirmed."""
    RANGE_MIN = 100_000_000
    RANGE_MAX = 100_500_000
    INTERVAL  =  100_000       # 5 steps per pass

    steps_per_pass = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_freq_task(
        range_min=RANGE_MIN,
        range_max=RANGE_MAX,
        interval=INTERVAL,
        passes=passes,
    ))

    assert len(tuned) == steps_per_pass * passes, (
        f"Expected {steps_per_pass * passes} steps, got {len(tuned)}"
    )

    # Verify unique steps only to avoid redundant hardware round-trips.
    unique_steps = list(dict.fromkeys(tuned))
    _assert_round_trips(rigctl, unique_steps)


# ---------------------------------------------------------------------------
# Test: modulation applied uniformly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("modulation", ["FM", "AM", "USB", "LSB", "CW"])
def test_scanning_frequency_correct_modulation_sent_for_each_step(modulation):
    """set_mode is called with the task modulation for every step, confirmed
    by a Bookmark round-trip comparison."""
    RANGE_MIN = 145_000_000
    RANGE_MAX = 145_500_000
    INTERVAL  =  100_000       # 5 steps

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_freq_task(
        range_min=RANGE_MIN,
        range_max=RANGE_MAX,
        interval=INTERVAL,
        modulation=modulation,
    ))

    assert len(tuned) == expected_steps, (
        f"Expected {expected_steps} steps, got {len(tuned)}"
    )
    assert all(m == modulation for _, m in tuned), (
        f"Unexpected modulation in tuned steps: {tuned}"
    )
    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Test: frequency order
# ---------------------------------------------------------------------------

def test_scanning_frequency_steps_tuned_in_ascending_order():
    """Frequencies are tuned in strict ascending order; every step is confirmed."""
    RANGE_MIN = 144_000_000
    RANGE_MAX = 146_000_000
    INTERVAL  =  500_000       # 4 steps: 144M, 144.5M, 145M, 145.5M

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    freqs = [f for f, _ in tuned]
    assert freqs == sorted(freqs), "Frequencies not tuned in ascending order"
    assert freqs[0] == RANGE_MIN
    assert freqs[-1] == RANGE_MAX - INTERVAL

    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Negative tests: invalid and boundary parameters
# ---------------------------------------------------------------------------

def test_scanning_frequency_range_min_equals_range_max_raises_value_error():
    """ScanningTask raises ValueError when range_min equals range_max."""
    with pytest.raises(ValueError):
        _freq_task(range_min=88_000_000, range_max=88_000_000, interval=1_000_000)


def test_scanning_frequency_range_min_greater_than_range_max_raises_value_error():
    """ScanningTask raises ValueError when range_min exceeds range_max."""
    with pytest.raises(ValueError):
        _freq_task(range_min=108_000_000, range_max=88_000_000, interval=1_000_000)


def test_scanning_frequency_invalid_scan_mode_raises_value_error():
    """ScanningTask raises ValueError for an unrecognised scan_mode."""
    with pytest.raises(ValueError):
        ScanningTask(
            frequency_modulation="FM",
            scan_mode="invalid",
            new_bookmarks_list=[],
            range_min=88_000_000,
            range_max=108_000_000,
            interval=1_000_000,
            delay=0,
            passes=1,
            sgn_level=-40,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=False,
            bookmarks=[],
        )


@pytest.mark.parametrize("passes", [-3, -1, 0])
def test_scanning_frequency_negative_passes_clamped_to_one(passes):
    """passes < 1 is silently clamped to 1; the scan executes exactly once."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000
    INTERVAL  =  1_000_000  # 2 steps: 88 MHz, 89 MHz

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=passes)
    assert task.passes == 1, f"Expected clamped passes=1, got {task.passes}"

    scanner.scan(task)

    assert len(tuned) == expected_steps, (
        f"Expected {expected_steps} tune calls, got {len(tuned)}"
    )
    _assert_round_trips(rigctl, list(tuned))


def test_scanning_frequency_interval_below_minimum_clamped_to_1000hz():
    """interval < 1000 Hz is clamped to 1000 Hz; steps are spaced 1 kHz apart."""
    RANGE_MIN        = 88_000_000
    RANGE_MAX        = 88_010_000
    INTERVAL_RAW     = 100        # below the 1 kHz floor
    INTERVAL_CLAMPED = 1_000

    expected_frequencies = list(range(RANGE_MIN, RANGE_MAX, INTERVAL_CLAMPED))  # 10 steps

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL_RAW)
    assert task.interval == INTERVAL_CLAMPED, (
        f"Expected clamped interval={INTERVAL_CLAMPED}, got {task.interval}"
    )

    scanner.scan(task)

    actual_freqs = [f for f, _ in tuned]
    assert actual_freqs == expected_frequencies, (
        f"Expected frequencies at 1 kHz spacing, got {actual_freqs}"
    )
    _assert_round_trips(rigctl, list(tuned))


def test_scanning_frequency_zero_signal_checks_all_steps_tuned():
    """signal_checks=0 disables level sampling; every step is still tuned."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000
    INTERVAL  =  1_000_000  # 3 steps

    expected_steps = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    config = ScanningConfig(
        time_wait_for_tune=_SETTLE_S,
        signal_checks=0,
        no_signal_delay=0.0,
    )

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=config,
        log=Mock(spec=LogFile),
    )

    scanner.scan(_freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL))

    assert len(tuned) == expected_steps, (
        f"Expected {expected_steps} tune calls with signal_checks=0, "
        f"got {len(tuned)}"
    )
    _assert_round_trips(rigctl, list(tuned))


def test_scanning_frequency_negative_range_min_clamped_to_zero_aborts_scan():
    """range_min < 0 is clamped to 0; tuning 0 Hz is invalid so the pass aborts
    immediately with no frequency calls."""
    RANGE_MIN_RAW = -1_000_000
    RANGE_MAX     = 91_000_000
    INTERVAL      = 30_000_000

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN_RAW, range_max=RANGE_MAX, interval=INTERVAL)
    assert task.range_min == 0, f"Expected clamped range_min=0, got {task.range_min}"

    scanner.scan(task)

    # Channel rejects frequency=0 (must be >= 1 Hz), so the pass aborts before
    # any set_frequency call is issued.
    assert len(tuned) == 0, (
        f"Expected 0 tune calls (0 Hz is invalid), got {len(tuned)}"
    )

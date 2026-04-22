"""
Functional tests for auto-bookmark scanning against a live gqrx instance.

These tests mirror test_auto_bookmark.py but use a real RigCtl connected to
gqrx at 127.0.0.1:7356.  No mocks are used on RigCtl — every command goes
over the network.

Signal detection is guaranteed by setting sgn_level=-200 (threshold=-2000),
which is well below the gqrx noise floor on any frequency.  This makes the
auto-bookmark state machine deterministic regardless of actual RF conditions.

After each scan the test re-tunes each outer step and verifies the
frequency/mode were accepted via Bookmark round-trip comparison.

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

pytestmark = [
    pytest.mark.skipif(
        not _gqrx_reachable(),
        reason=f"gqrx not available at {_GQRX_HOST}:{_GQRX_PORT} — skipping hardware tests",
    ),
    pytest.mark.xdist_group("gqrx_serial"),
]

# sgn_level whose threshold (-200 × 10 = -2000) is well below the gqrx noise
# floor, so signal_check() returns True at every step regardless of RF content.
_SGN_LEVEL_ALWAYS_ON = -200


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> tuple[RigCtl, list[tuple[int, str]]]:
    """Real RigCtl bound to gqrx with a recording _send_message wrapper."""
    rigctl = RigCtl(endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1))

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
    q = Mock(spec=STMessenger)
    q.update_queued.return_value = False
    return q


def _make_config() -> ScanningConfig:
    return ScanningConfig(
        time_wait_for_tune=_SETTLE_S,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _auto_task(
    range_min: int,
    range_max: int,
    interval: int,
    sgn_level: int = _SGN_LEVEL_ALWAYS_ON,
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
        sgn_level=sgn_level,
        wait=False,
        record=False,
        auto_bookmark=True,
        log=False,
        bookmarks=[],
    )


def _assert_round_trips(rigctl: RigCtl, tuned_pairs: list[tuple[int, str]]) -> None:
    """Re-tune each (frequency, modulation) pair and confirm via read-back."""
    for freq, modulation in tuned_pairs:
        rigctl.set_frequency(freq)
        rigctl.set_mode(modulation)
        sent = bookmark_factory(input_frequency=freq, modulation=modulation, description="scan_step")

        read_bm = None
        for _ in range(_MAX_READBACK_RETRIES):
            time.sleep(_SETTLE_S)
            read_bm = bookmark_factory(
                input_frequency=int(rigctl.get_frequency()),
                modulation=rigctl.get_mode().strip(),
                description="scan_step",
            )
            if sent == read_bm:
                break

        assert sent == read_bm, (
            f"Round-trip mismatch at ({freq} Hz, {modulation}): "
            f"sent={sent.channel}, read={read_bm.channel}"  # type: ignore[union-attr]
        )


# ---------------------------------------------------------------------------
# Test: auto-bookmark creates one bookmark per two consecutive signal steps
# ---------------------------------------------------------------------------

def test_auto_bookmark_consecutive_signals_produce_bookmarks():
    """With signal guaranteed at every step, every pair of consecutive steps
    produces one bookmark via the _autobookmark path.

    4 outer steps (88–92 MHz) → 2 bookmarks at 88 MHz and 90 MHz.
    All outer steps are confirmed via Bookmark round-trip.
    """
    RANGE_MIN = 88_000_000
    RANGE_MAX = 92_000_000   # 4 steps: 88, 89, 90, 91 MHz
    INTERVAL  =  1_000_000

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    scanner.scan(task)

    # 4 outer steps tuned
    assert len(tuned) == 4, f"Expected 4 outer steps, got {len(tuned)}"

    # 4 steps with signal at every step → 2 bookmarks (pairs: step1+2, step3+4)
    assert len(task.new_bookmarks_list) == 2, (
        f"Expected 2 bookmarks from 4 consecutive signal steps, "
        f"got {len(task.new_bookmarks_list)}"
    )

    # First bookmark at RANGE_MIN (first step of first pair)
    assert task.new_bookmarks_list[0].channel.frequency == RANGE_MIN, (
        f"Expected first bookmark at {RANGE_MIN} Hz, "
        f"got {task.new_bookmarks_list[0].channel.frequency}"
    )

    # Second bookmark at RANGE_MIN + 2*INTERVAL (first step of second pair)
    assert task.new_bookmarks_list[1].channel.frequency == RANGE_MIN + 2 * INTERVAL, (
        f"Expected second bookmark at {RANGE_MIN + 2 * INTERVAL} Hz, "
        f"got {task.new_bookmarks_list[1].channel.frequency}"
    )

    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Test: bookmark frequencies fall within the scanned range
# ---------------------------------------------------------------------------

def test_auto_bookmark_frequencies_within_scan_range():
    """Every auto-generated bookmark frequency must lie within [range_min, range_max)."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 93_000_000   # 5 steps
    INTERVAL  =  1_000_000

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _auto_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    scanner.scan(task)

    for bm in task.new_bookmarks_list:
        assert RANGE_MIN <= bm.channel.frequency < RANGE_MAX, (
            f"Bookmark frequency {bm.channel.frequency} outside "
            f"scan range [{RANGE_MIN}, {RANGE_MAX})"
        )

    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Test: bookmark modulation matches task modulation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("modulation", ["FM", "AM", "USB"])
def test_auto_bookmark_bookmark_modulation_matches_task(modulation):
    """The modulation stored in each auto-bookmark matches what get_mode()
    returns from gqrx after tuning to that frequency."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps; 1 bookmark expected
    INTERVAL  =  1_000_000

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _auto_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX,
        interval=INTERVAL, modulation=modulation,
    )
    scanner.scan(task)

    # 2 steps with signal at both → hold path fires → 1 bookmark at step 1
    # (step 2's signal triggers _autobookmark, which bookmarks step 1's freq)
    assert len(task.new_bookmarks_list) == 1

    # The bookmark's modulation must match what gqrx confirmed
    bm = task.new_bookmarks_list[0]
    rigctl.set_frequency(bm.channel.frequency)
    rigctl.set_mode(modulation)
    time.sleep(_SETTLE_S)
    confirmed_mode = rigctl.get_mode().strip()

    assert bm.channel.modulation == confirmed_mode, (
        f"Bookmark modulation {bm.channel.modulation!r} != "
        f"gqrx-confirmed mode {confirmed_mode!r}"
    )

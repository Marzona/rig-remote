"""
Functional tests for queue-driven parameter updates mid-scan against a live
gqrx instance.

These tests mirror test_queue_updates_mid_scan.py but use a real RigCtl
connected to gqrx at 127.0.0.1:7356.  No mocks are used on RigCtl — every
set_frequency/set_mode command goes over the network.

A real STMessenger (with real QueueComms) is pre-loaded with events before the
scan starts; the scan picks them up at the first process_queue() call.

The tuned-frequency recording wrapper from the other gqrx tests is used so
that the actual sequence of set_frequency calls can be asserted independently
of signal conditions.

Parameters covered:
  txt_passes    — extended pass count issues the correct total tune calls
  txt_range_max — narrowed range_max stops the sweep before the original bound
  txt_interval  — widened interval reduces the number of steps per pass
  txt_sgn_level — threshold adjusted so detection changes on real noise levels

The module is skipped automatically when gqrx is not reachable.
"""

import time

import pytest
from unittest.mock import Mock

from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.queue_comms import QueueComms
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> tuple[RigCtl, list[int]]:
    """Real RigCtl bound to gqrx, recording every set_frequency argument."""
    rigctl = RigCtl(endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1))

    tuned_freqs: list[int] = []
    original_send = rigctl._send_message

    def _recording_send(request: str) -> str:
        result = original_send(request)
        if request.startswith("F "):
            tuned_freqs.append(int(float(request[2:])))
        return result

    rigctl._send_message = _recording_send  # type: ignore[method-assign]
    return rigctl, tuned_freqs


def _make_live_queue(events: list[tuple[str, str]] | None = None) -> STMessenger:
    """Real STMessenger pre-loaded with *events*."""
    q = STMessenger(queue_comms=QueueComms())
    for event in (events or []):
        q.send_event_update(event)
    return q


def _make_config() -> ScanningConfig:
    return ScanningConfig(
        time_wait_for_tune=_SETTLE_S,
        signal_checks=1,
        no_signal_delay=0.0,
    )


def _freq_task(
    range_min: int,
    range_max: int,
    interval: int,
    sgn_level: int = -40,
    passes: int = 1,
    delay: int = 0,
    auto_bookmark: bool = False,
) -> ScanningTask:
    return ScanningTask(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        delay=delay,
        passes=passes,
        sgn_level=sgn_level,
        wait=False,
        record=False,
        auto_bookmark=auto_bookmark,
        log=False,
        bookmarks=[],
    )


def _assert_round_trips(rigctl: RigCtl, freqs: list[int], modulation: str = "FM") -> None:
    """Confirm each unique frequency in *freqs* was accepted by gqrx."""
    for freq in dict.fromkeys(freqs):
        rigctl.set_frequency(freq)
        rigctl.set_mode(modulation)
        sent = bookmark_factory(input_frequency=freq, modulation=modulation, description="step")

        read_bm = None
        for _ in range(_MAX_READBACK_RETRIES):
            time.sleep(_SETTLE_S)
            read_bm = bookmark_factory(
                input_frequency=int(rigctl.get_frequency()),
                modulation=rigctl.get_mode().strip(),
                description="step",
            )
            if sent == read_bm:
                break

        assert sent == read_bm, (
            f"Round-trip mismatch at {freq} Hz: sent={sent.channel}, "
            f"read={read_bm.channel}"  # type: ignore[union-attr]
        )


# ---------------------------------------------------------------------------
# passes update
# ---------------------------------------------------------------------------

def test_passes_update_mid_scan_extends_total_tune_calls():
    """txt_passes=3 consumed on step 1 resets pass_count to 3; total tune
    calls confirmed by counting F commands and by round-trip verification of
    each unique step."""
    RANGE_MIN      = 88_000_000
    RANGE_MAX      = 90_000_000   # 2 steps per pass: 88 M, 89 M
    INTERVAL       =  1_000_000
    STEPS_PER_PASS = 2

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue([("txt_passes", "3")]),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=1)
    scanner.scan(task)

    assert len(tuned) == STEPS_PER_PASS * 3, (
        f"Expected {STEPS_PER_PASS * 3} tune calls (3 passes × {STEPS_PER_PASS} steps), "
        f"got {len(tuned)}: {tuned}"
    )
    assert task.passes == 3
    _assert_round_trips(rigctl, list(dict.fromkeys(tuned)))


# ---------------------------------------------------------------------------
# range_max update
# ---------------------------------------------------------------------------

def test_range_max_update_mid_scan_truncates_sweep():
    """txt_range_max=90000 (kHz → 90 MHz) consumed on step 1 truncates a
    88–93 MHz sweep to 88 M and 89 M only; confirmed via round-trip."""
    RANGE_MIN   = 88_000_000
    RANGE_MAX   = 93_000_000   # original: 5 steps
    INTERVAL    =  1_000_000
    NEW_MAX_KHZ = "90000"      # 90 MHz

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue([("txt_range_max", NEW_MAX_KHZ)]),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    scanner.scan(task)

    assert len(tuned) == 2, (
        f"Expected 2 tune calls after range_max narrowed to 90 MHz, got {len(tuned)}: {tuned}"
    )
    assert task.range_max == 90_000_000
    assert 90_000_000 not in tuned, "90 MHz (exclusive upper bound) must not be tuned"
    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# interval update
# ---------------------------------------------------------------------------

def test_interval_update_mid_scan_reduces_step_count():
    """txt_interval=2000000 (Hz → 2 MHz) consumed on step 1 widens steps from
    1 MHz to 2 MHz; the resulting steps are confirmed via round-trip."""
    RANGE_MIN        = 88_000_000
    RANGE_MAX        = 93_000_000   # original 1 MHz: 5 steps
    INTERVAL         =  1_000_000
    NEW_INTERVAL_HZ  = "2000000"   # 2 MHz in Hz

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue([("txt_interval", NEW_INTERVAL_HZ)]),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL)
    scanner.scan(task)

    # 88M (+2M) 90M (+2M) 92M (+2M) → 94M > 93M stop: 3 steps
    assert len(tuned) == 3, (
        f"Expected 3 tune calls after interval widened to 2 MHz, got {len(tuned)}: {tuned}"
    )
    assert task.interval == 2_000_000

    # Steps must be on the new 2 MHz grid starting from RANGE_MIN
    expected = [88_000_000, 90_000_000, 92_000_000]
    assert tuned == expected, f"Expected steps {expected}, got {tuned}"
    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# sgn_level update: threshold adjusted to cross real gqrx noise floor
# ---------------------------------------------------------------------------

def test_sgn_level_update_mid_scan_changes_signal_detection():
    """gqrx noise floor is typically around −100 dBFS, which is above the
    default threshold (sgn_level=-40 → threshold=-400) so signal is always
    detected.  Raising sgn_level to -5 (threshold=-50) puts the threshold
    above the noise floor, turning signal detection off.

    With auto_bookmark=True and signal initially forced ON, queuing
    txt_sgn_level=-5 after the first step stops further bookmark creation.

    Strategy:
      - 4-step range; sgn_level=-200 (always-on) as initial value.
      - Queue txt_sgn_level=-5 → after step 1's process_queue, threshold=-50.
      - Step 1: process_queue updates threshold to -50; gqrx noise ~-100 <-50
        → no signal at step 1 (update applied BEFORE channel_tune).
      - Steps 2-4: no signal either.
      - Result: 0 bookmarks created (threshold raised above noise floor).

    Compare to the baseline (no queue event): with sgn_level=-200, threshold=
    -2000, gqrx noise ~-100 >= -2000 → signal at every step → 2 bookmarks.
    """
    RANGE_MIN = 88_000_000
    RANGE_MAX = 92_000_000   # 4 steps
    INTERVAL  =  1_000_000

    # --- Baseline: no queue event, sgn_level=-200, signal at every step ---
    rigctl_base, _ = _make_rigctl()
    scanner_base = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue(),
        log_filename="/dev/null",
        rigctl=rigctl_base,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )
    task_base = _freq_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        sgn_level=-200, auto_bookmark=True,
    )
    scanner_base.scan(task_base)
    baseline_bookmarks = len(task_base.new_bookmarks_list)

    # --- With update: sgn_level raised to -5, threshold above noise floor ---
    rigctl_upd, _ = _make_rigctl()
    scanner_upd = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue([("txt_sgn_level", "-5")]),
        log_filename="/dev/null",
        rigctl=rigctl_upd,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )
    task_upd = _freq_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        sgn_level=-200, auto_bookmark=True,
    )
    scanner_upd.scan(task_upd)
    updated_bookmarks = len(task_upd.new_bookmarks_list)

    assert baseline_bookmarks > 0, (
        "Baseline with sgn_level=-200 should detect signal and create bookmarks "
        f"— got {baseline_bookmarks}"
    )
    assert updated_bookmarks < baseline_bookmarks, (
        f"Raising sgn_level to -5 should reduce bookmark count: "
        f"baseline={baseline_bookmarks}, updated={updated_bookmarks}"
    )
    assert task_upd.sgn_level == -5


# ---------------------------------------------------------------------------
# Multiple events applied in the same process_queue call
# ---------------------------------------------------------------------------

def test_multiple_queued_events_all_applied():
    """txt_passes=2 and txt_range_max=90000 (90 MHz) are both consumed on
    step 1; the scan runs 2 passes over the truncated 88–90 MHz range (4 total
    tune calls) and both values are reflected in the final task."""
    RANGE_MIN   = 88_000_000
    RANGE_MAX   = 93_000_000   # original: 5 steps per pass
    INTERVAL    =  1_000_000

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_live_queue([
            ("txt_passes",    "2"),
            ("txt_range_max", "90000"),   # 90 MHz
        ]),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _freq_task(range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL, passes=1)
    scanner.scan(task)

    # 2 passes × 2 steps (88 M, 89 M < 90 M) = 4 tune calls
    assert len(tuned) == 4, (
        f"Expected 4 tune calls (2 passes × 2 steps after range_max=90 MHz), "
        f"got {len(tuned)}: {tuned}"
    )
    assert task.passes    == 2
    assert task.range_max == 90_000_000
    _assert_round_trips(rigctl, list(dict.fromkeys(tuned)))

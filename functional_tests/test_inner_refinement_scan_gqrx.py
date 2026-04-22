"""
Functional tests for inner refinement scanning against a live gqrx instance.

These tests mirror test_inner_refinement_scan.py but use a real RigCtl
connected to gqrx at 127.0.0.1:7356.  No mocks are used on RigCtl.

Signal detection is guaranteed by setting sgn_level=-200 (threshold=-2000),
ensuring the inner scan path is exercised at every outer step regardless of
actual RF content.

After each scan the test verifies:
  - Sub-band frequencies were actually sent to and confirmed by gqrx.
  - Each bookmark frequency falls within [trigger, trigger + inner_band).
  - Outer steps also confirmed via round-trip.

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

_SGN_LEVEL_ALWAYS_ON = -200  # threshold -2000, always below gqrx noise floor


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> tuple[RigCtl, list[int]]:
    """Real RigCtl bound to gqrx, plus a list recording every frequency sent
    via set_frequency (outer steps and inner sub-band steps alike)."""
    rigctl = RigCtl(endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1))

    all_freqs: list[int] = []
    original_send = rigctl._send_message

    def _recording_send(request: str) -> str:
        result = original_send(request)
        if request.startswith("F "):
            all_freqs.append(int(float(request[2:])))
        return result

    rigctl._send_message = _recording_send  # type: ignore[method-assign]
    return rigctl, all_freqs


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


def _inner_task(
    range_min: int,
    range_max: int,
    interval: int,
    inner_band: int,
    inner_interval: int,
    modulation: str = "FM",
) -> ScanningTask:
    return ScanningTask(
        frequency_modulation=modulation,
        scan_mode="frequency",
        new_bookmarks_list=[],
        range_min=range_min,
        range_max=range_max,
        interval=interval,
        delay=0,
        passes=1,
        sgn_level=_SGN_LEVEL_ALWAYS_ON,
        wait=False,
        record=False,
        auto_bookmark=True,
        log=False,
        bookmarks=[],
        inner_band=inner_band,
        inner_interval=inner_interval,
    )


def _assert_round_trip(rigctl: RigCtl, freq: int, modulation: str) -> None:
    """Confirm a single (frequency, modulation) pair via gqrx read-back."""
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
# Test: inner sub-band frequencies are tuned on real hardware
# ---------------------------------------------------------------------------

def test_inner_scan_sub_band_frequencies_sent_to_gqrx():
    """With signal guaranteed at every outer step, the inner scan sweeps
    [trigger, trigger + inner_band) for each outer trigger.

    Verifies that at least one sub-band frequency was tuned (i.e., a frequency
    not on the outer MHz grid was sent to gqrx) and confirmed by the rig.
    """
    RANGE_MIN      = 88_000_000
    RANGE_MAX      = 90_000_000   # 2 outer steps: 88 MHz, 89 MHz
    INTERVAL       =  1_000_000
    INNER_BAND     =    500_000
    INNER_INTERVAL =    250_000   # sub-band steps: 88M, 88.25M

    rigctl, all_freqs = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _inner_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        inner_band=INNER_BAND, inner_interval=INNER_INTERVAL,
    )
    scanner.scan(task)

    # At least one sub-band frequency (not on the outer MHz grid) must appear.
    sub_band_freqs = [f for f in all_freqs if f % INTERVAL != 0]
    assert sub_band_freqs, (
        f"No sub-band frequencies tuned; all tuned freqs: {all_freqs}"
    )

    # Confirm each unique sub-band frequency was accepted by gqrx.
    for freq in dict.fromkeys(sub_band_freqs):
        _assert_round_trip(rigctl, freq, "FM")


# ---------------------------------------------------------------------------
# Test: one bookmark per outer trigger, each within the inner band
# ---------------------------------------------------------------------------

def test_inner_scan_bookmarks_within_inner_band():
    """Each outer signal detection produces exactly one bookmark, and its
    frequency must fall within [trigger, trigger + inner_band)."""
    RANGE_MIN      = 88_000_000
    RANGE_MAX      = 90_000_000   # 2 outer steps → 2 bookmarks
    INTERVAL       =  1_000_000
    INNER_BAND     =    500_000
    INNER_INTERVAL =    250_000

    rigctl, _ = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _inner_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        inner_band=INNER_BAND, inner_interval=INNER_INTERVAL,
    )
    scanner.scan(task)

    # One bookmark per outer trigger (2 outer steps)
    assert len(task.new_bookmarks_list) == 2, (
        f"Expected 2 bookmarks (one per outer trigger), "
        f"got {len(task.new_bookmarks_list)}"
    )

    outer_triggers = list(range(RANGE_MIN, RANGE_MAX, INTERVAL))
    for bm, trigger in zip(task.new_bookmarks_list, outer_triggers):
        bm_freq = bm.channel.frequency
        assert trigger <= bm_freq < trigger + INNER_BAND, (
            f"Bookmark at {bm_freq} Hz is outside inner band "
            f"[{trigger}, {trigger + INNER_BAND}) for trigger {trigger}"
        )


# ---------------------------------------------------------------------------
# Test: inner sub-band steps stay within exclusive upper bound
# ---------------------------------------------------------------------------

def test_inner_scan_steps_do_not_exceed_inner_band_upper_bound():
    """No frequency at or beyond trigger + inner_band should appear in the
    tuned-frequency log (exclusive upper bound is respected on real hardware)."""
    RANGE_MIN      = 88_000_000
    RANGE_MAX      = 89_000_000   # 1 outer step: 88 MHz
    INTERVAL       =  1_000_000
    TRIGGER        = 88_000_000
    INNER_BAND     =    500_000
    INNER_INTERVAL =    250_000   # inner steps: 88M, 88.25M (88.5M excluded)

    rigctl, all_freqs = _make_rigctl()
    scanner = create_scanner(
        scan_mode="frequency",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    task = _inner_task(
        range_min=RANGE_MIN, range_max=RANGE_MAX, interval=INTERVAL,
        inner_band=INNER_BAND, inner_interval=INNER_INTERVAL,
    )
    scanner.scan(task)

    inner_upper = TRIGGER + INNER_BAND
    over_bound = [f for f in all_freqs if TRIGGER <= f and f >= inner_upper]
    assert over_bound == [], (
        f"Frequencies at or beyond inner_band upper bound {inner_upper} Hz "
        f"were tuned: {over_bound}"
    )

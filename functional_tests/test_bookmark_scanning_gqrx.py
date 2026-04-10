"""
Functional tests for bookmark scanning against a live gqrx instance.

These tests mirror test_frequency_scanning_gqrx.py but exercise the bookmark
scan pipeline.  Bookmarks are loaded from the project test CSV file, then a
real RigCtl connected to gqrx at 127.0.0.1:7356 is used — no mocks on RigCtl.

After each scan the test re-tunes each non-locked bookmark, reads back the
frequency and mode via get_frequency() / get_mode(), builds a *sent* Bookmark
and a *read* Bookmark, and asserts they are equal.  Bookmark.__eq__ compares
Channel (frequency + modulation), proving the rig accepted and confirmed every
tuning command.

The module is skipped automatically when gqrx is not reachable.
"""

import time
from pathlib import Path

import pytest
from unittest.mock import Mock

from rig_remote.bookmarksmanager import BookmarksManager, bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
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
# Constants
# ---------------------------------------------------------------------------

BOOKMARK_FILE = (
    Path(__file__).parent.parent / "tests" / "test_files" / "test-rig_remote-bookmarks.csv"
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

def _load_bookmarks() -> list[Bookmark]:
    """Load all bookmarks from the test CSV file."""
    return BookmarksManager().load(str(BOOKMARK_FILE))


def _non_locked(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Return only bookmarks that are not locked out."""
    return [bm for bm in bookmarks if bm.lockout != "L"]


def _make_rigctl() -> tuple[RigCtl, list[tuple[int, str]]]:
    """Return a real RigCtl bound to gqrx, plus a list that records every
    (frequency, modulation) pair issued by channel_tune.

    _send_message is wrapped at the instance level so that consecutive
    ``F <freq>`` / ``M <mode>`` pairs are captured without using the mock
    library.

    IMPORTANT: callers must pass ``list(tuned)`` (a snapshot) to
    _assert_round_trips — the wrapper is still active during verification and
    would otherwise keep appending to the live list.
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
    """STMessenger stub: queue is always empty (no UI events during scan)."""
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


def _bm_task(bookmarks: list[Bookmark], passes: int = 1) -> ScanningTask:
    return ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmarks_list=[],
        range_min=88_000_000,
        range_max=108_000_000,
        interval=1_000_000,
        delay=0,
        passes=passes,
        sgn_level=-40,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=bookmarks,
    )


def _assert_round_trips(rigctl: RigCtl, tuned_pairs: list[tuple[int, str]]) -> None:
    """For each (frequency, modulation) pair recorded during the scan:

    1. Re-tune gqrx to that frequency and mode.
    2. Read back the active frequency and mode (with retry for gqrx latency).
    3. Build a *sent* Bookmark and a *read* Bookmark — both with description
       ``"scan_step"`` so Bookmark.__eq__ reduces to Channel equality.
    4. Assert sent == read, proving the rig confirmed the command.
    """
    for freq, modulation in tuned_pairs:
        rigctl.set_frequency(freq)
        rigctl.set_mode(modulation)

        sent_bookmark = bookmark_factory(
            input_frequency=freq,
            modulation=modulation,
            description="scan_step",
        )

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
# Test: all non-locked bookmarks are tuned and confirmed
# ---------------------------------------------------------------------------

def test_bookmark_scanning_all_bookmarks_tuned_and_confirmed():
    """Every non-locked bookmark is tuned to gqrx and confirmed via round-trip
    Bookmark comparison.

    Asserts:
    - set_frequency / set_mode were called for every active bookmark.
    - The tuned order matches the bookmark list order.
    - Each frequency and mode read back from gqrx matches what was sent.
    """
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_bm_task(bookmarks))

    assert len(tuned) == len(active), (
        f"Expected {len(active)} tune calls, got {len(tuned)}"
    )

    # Verify tuned order matches bookmark list order.
    for bm, (freq, mode) in zip(active, tuned):
        assert freq == bm.channel.frequency, (
            f"Order mismatch: expected {bm.channel.frequency}, got {freq}"
        )
        assert mode == bm.channel.modulation, (
            f"Order mismatch: expected {bm.channel.modulation}, got {mode}"
        )

    _assert_round_trips(rigctl, list(tuned))


# ---------------------------------------------------------------------------
# Test: multiple passes repeat all bookmarks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("passes", [1, 2, 3])
def test_bookmark_scanning_multiple_passes_multiplies_tune_calls(passes):
    """Each additional pass repeats the full bookmark sweep.

    Total tune calls == len(active_bookmarks) × passes.
    The unique set of (freq, mode) pairs is confirmed via round-trip.
    """
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_bm_task(bookmarks, passes=passes))

    assert len(tuned) == len(active) * passes, (
        f"Expected {len(active) * passes} tune calls "
        f"({len(active)} bookmarks × {passes} passes), got {len(tuned)}"
    )

    unique_steps = list(dict.fromkeys(tuned))
    _assert_round_trips(rigctl, unique_steps)


# ---------------------------------------------------------------------------
# Test: frequency and mode are sent in bookmark list order
# ---------------------------------------------------------------------------

def test_bookmark_scanning_tuned_in_bookmark_list_order():
    """Bookmarks are tuned in the same order they appear in the file.

    For each active bookmark, the corresponding entry in the tuned list must
    carry the matching frequency and modulation.
    """
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl, tuned = _make_rigctl()
    scanner = create_scanner(
        scan_mode="bookmarks",
        scan_queue=_make_queue(),
        log_filename="/dev/null",
        rigctl=rigctl,
        config=_make_config(),
        log=Mock(spec=LogFile),
    )

    scanner.scan(_bm_task(bookmarks))

    assert len(tuned) == len(active)
    for bm, (freq, mode) in zip(active, tuned):
        sent_bm = bookmark_factory(
            input_frequency=freq,
            modulation=mode,
            description=bm.description,
        )
        expected_bm = bookmark_factory(
            input_frequency=bm.channel.frequency,
            modulation=bm.channel.modulation,
            description=bm.description,
        )
        assert sent_bm == expected_bm, (
            f"Bookmark {bm.id}: expected ({bm.channel.frequency}, "
            f"{bm.channel.modulation}), got ({freq}, {mode})"
        )

"""
Functional tests for disk-logging against a live gqrx instance.

These tests mirror test_disk_logging.py but use a real RigCtl connected to
gqrx at 127.0.0.1:7356 and a real temporary log file on disk.  No mocks are
used on RigCtl — every command goes over the network.

For the frequency scanner:
  sgn_level=-200 (threshold=-2000) ensures signal is detected at every step,
  making the number of expected log entries deterministic.

For the bookmark scanner:
  log.write() is unconditional (called for every non-locked bookmark regardless
  of signal), so no special sgn_level manipulation is required.

In both cases the test reads the log file after the scan and verifies:
  - The file was created and is non-empty.
  - The correct number of lines was written.
  - Each line begins with the expected record-type prefix ("F " or "B ").

The module is skipped automatically when gqrx is not reachable.
"""

import tempfile
import os
from pathlib import Path

import pytest
from unittest.mock import Mock

from rig_remote.bookmarksmanager import BookmarksManager
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
# Module-level availability guard
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.skipif(
        not _gqrx_reachable(),
        reason=f"gqrx not available at {_GQRX_HOST}:{_GQRX_PORT} — skipping hardware tests",
    ),
    pytest.mark.xdist_group("gqrx_serial"),
]

BOOKMARK_FILE = (
    Path(__file__).parent.parent / "tests" / "test_files" / "test-rig_remote-bookmarks.csv"
)

_SGN_LEVEL_ALWAYS_ON = -200  # threshold -2000, always below gqrx noise floor


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> RigCtl:
    return RigCtl(endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1))


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


def _load_bookmarks() -> list[Bookmark]:
    return BookmarksManager().load(str(BOOKMARK_FILE))


def _non_locked(bookmarks: list[Bookmark]) -> list[Bookmark]:
    return [bm for bm in bookmarks if bm.lockout != "L"]


def _read_log_lines(path: str) -> list[str]:
    """Return non-empty lines from the log file."""
    with open(path) as fh:
        return [line for line in fh.read().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Frequency scanner: log.write() called once per signal detection
# ---------------------------------------------------------------------------

def test_freq_scan_log_file_written_once_per_step_with_guaranteed_signal():
    """With sgn_level=-200, signal is detected at every outer step.
    The log file must contain one 'F ...' entry per step, written to a real
    file on disk via a real LogFile instance (no mocks on I/O)."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 91_000_000   # 3 steps: 88, 89, 90 MHz
    INTERVAL  =  1_000_000
    EXPECTED_ENTRIES = len(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl = _make_rigctl()

    with tempfile.NamedTemporaryFile(
        suffix=".log", delete=False, mode="w"
    ) as tmp:
        log_path = tmp.name

    try:
        scanner = create_scanner(
            scan_mode="frequency",
            scan_queue=_make_queue(),
            log_filename=log_path,
            rigctl=rigctl,
            config=_make_config(),
        )

        task = ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmarks_list=[],
            range_min=RANGE_MIN,
            range_max=RANGE_MAX,
            interval=INTERVAL,
            delay=0,
            passes=1,
            sgn_level=_SGN_LEVEL_ALWAYS_ON,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=True,
            bookmarks=[],
        )
        scanner.scan(task)

        lines = _read_log_lines(log_path)
        assert len(lines) == EXPECTED_ENTRIES, (
            f"Expected {EXPECTED_ENTRIES} log entries, got {len(lines)}"
        )
        for line in lines:
            assert line.startswith("F "), (
                f"Expected each line to start with 'F ', got: {line!r}"
            )
    finally:
        os.unlink(log_path)


# ---------------------------------------------------------------------------
# Frequency scanner: log file record contains signal frequency
# ---------------------------------------------------------------------------

def test_freq_scan_log_file_entries_contain_tuned_frequency():
    """Each log entry's frequency token matches the corresponding step
    frequency tuned during the scan."""
    RANGE_MIN = 88_000_000
    RANGE_MAX = 90_000_000   # 2 steps: 88 MHz, 89 MHz
    INTERVAL  =  1_000_000
    EXPECTED_FREQS = list(range(RANGE_MIN, RANGE_MAX, INTERVAL))

    rigctl = _make_rigctl()

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as tmp:
        log_path = tmp.name

    try:
        scanner = create_scanner(
            scan_mode="frequency",
            scan_queue=_make_queue(),
            log_filename=log_path,
            rigctl=rigctl,
            config=_make_config(),
        )

        task = ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmarks_list=[],
            range_min=RANGE_MIN,
            range_max=RANGE_MAX,
            interval=INTERVAL,
            delay=0,
            passes=1,
            sgn_level=_SGN_LEVEL_ALWAYS_ON,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=True,
            bookmarks=[],
        )
        scanner.scan(task)

        lines = _read_log_lines(log_path)
        assert len(lines) == len(EXPECTED_FREQS)

        # Log format: "F <weekday> <YYYY-Mon-DD> <HH:MM:SS> <frequency> ..."
        for line, expected_freq in zip(lines, EXPECTED_FREQS):
            parts = line.split()
            # parts[0]="F", parts[1]=weekday, parts[2]=date, parts[3]=time, parts[4]=frequency
            log_freq = int(parts[4])
            assert log_freq == expected_freq, (
                f"Log entry frequency {log_freq} != expected {expected_freq}"
            )
    finally:
        os.unlink(log_path)


# ---------------------------------------------------------------------------
# Bookmark scanner: log.write() called for every non-locked bookmark
# ---------------------------------------------------------------------------

def test_bm_scan_log_file_written_for_each_non_locked_bookmark():
    """The bookmark scanner writes one 'B ...' log entry for every non-locked
    bookmark, unconditionally on signal, to a real file on disk."""
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as tmp:
        log_path = tmp.name

    try:
        scanner = create_scanner(
            scan_mode="bookmarks",
            scan_queue=_make_queue(),
            log_filename=log_path,
            rigctl=rigctl,
            config=_make_config(),
        )

        task = ScanningTask(
            frequency_modulation="FM",
            scan_mode="bookmarks",
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
            log=True,
            bookmarks=bookmarks,
        )
        scanner.scan(task)

        lines = _read_log_lines(log_path)
        assert len(lines) == len(active), (
            f"Expected {len(active)} log entries (one per non-locked bookmark), "
            f"got {len(lines)}"
        )
        for line in lines:
            assert line.startswith("B "), (
                f"Expected each line to start with 'B ', got: {line!r}"
            )
    finally:
        os.unlink(log_path)


# ---------------------------------------------------------------------------
# Bookmark scanner: log entries contain the correct bookmark frequencies
# ---------------------------------------------------------------------------

def test_bm_scan_log_file_entries_contain_bookmark_frequencies():
    """Each 'B ...' log entry's frequency token matches the corresponding
    non-locked bookmark's frequency."""
    bookmarks = _load_bookmarks()
    active = _non_locked(bookmarks)

    rigctl = _make_rigctl()

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as tmp:
        log_path = tmp.name

    try:
        scanner = create_scanner(
            scan_mode="bookmarks",
            scan_queue=_make_queue(),
            log_filename=log_path,
            rigctl=rigctl,
            config=_make_config(),
        )

        task = ScanningTask(
            frequency_modulation="FM",
            scan_mode="bookmarks",
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
            log=True,
            bookmarks=bookmarks,
        )
        scanner.scan(task)

        lines = _read_log_lines(log_path)
        assert len(lines) == len(active)

        # Log format: "B <weekday> <YYYY-Mon-DD> <HH:MM:SS> <frequency> ..."
        for line, bm in zip(lines, active):
            parts = line.split()
            # parts[0]="B", parts[1]=weekday, parts[2]=date, parts[3]=time, parts[4]=frequency
            log_freq = int(parts[4])
            assert log_freq == bm.channel.frequency, (
                f"Log entry frequency {log_freq} != "
                f"bookmark frequency {bm.channel.frequency}"
            )
    finally:
        os.unlink(log_path)

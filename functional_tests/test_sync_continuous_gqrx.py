"""
Functional tests for continuous sync against a live gqrx instance.

These tests mirror test_sync_continuous.py but use real RigCtl instances
connected to gqrx at 127.0.0.1:7356.  Both src and dst point to the same
gqrx endpoint: get_frequency()/get_mode() read the current rig state and
set_frequency()/set_mode() write it back, completing a full TCP round-trip
on every sync cycle.

Termination is driven by a lightweight wrapper around src._send_message that
calls syncing.terminate() after N frequency-read commands, keeping the test
synchronous with no threads or wall-time sleeps (beyond the _SYNC_INTERVAL
set to zero).

After N cycles the test verifies:
  - Exactly N set_frequency and set_mode commands were issued on dst.
  - The last frequency committed to gqrx matches the value set before the sync.
  - notify_end_of_scan() was called exactly once when the loop exited.

The module is skipped automatically when gqrx is not reachable.
"""

import time

import pytest
from unittest.mock import Mock

from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.sync_task import SyncTask
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing
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
# Shared helpers
# ---------------------------------------------------------------------------

def _make_rigctl() -> RigCtl:
    return RigCtl(endpoint=RigEndpoint(hostname=_GQRX_HOST, port=_GQRX_PORT, number=1))


def _make_sync_task(src: RigCtl, dst: RigCtl) -> SyncTask:
    return SyncTask(
        syncq=STMessenger(queue_comms=QueueComms()),
        src_rig=src,
        dst_rig=dst,
    )


def _run_n_cycles(
    n_cycles: int,
) -> tuple[Syncing, RigCtl, RigCtl, SyncTask]:
    """Wire a continuous sync against live gqrx and run it for exactly
    *n_cycles*, terminating via a _send_message wrapper on src.

    Both src and dst point to the same gqrx endpoint.  The wrapper increments
    a counter on every frequency-read command ("f") and calls terminate() once
    the counter reaches *n_cycles*.

    Returns (syncing, src, dst, task) for post-run inspection.
    """
    src = _make_rigctl()
    dst = _make_rigctl()
    task = _make_sync_task(src, dst)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    freq_reads: list[int] = [0]
    original_send = src._send_message

    def _counting_send(request: str) -> str:
        result = original_send(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= n_cycles:
                syncing.terminate()
        return result

    src._send_message = _counting_send  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)
    return syncing, src, dst, task


# ---------------------------------------------------------------------------
# Test: loop runs exactly N cycles before terminate() stops it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_cycles", [1, 2, 3])
def test_sync_continuous_runs_n_cycles(n_cycles):
    """Sync runs exactly *n_cycles* frequency+mode propagations against real
    gqrx, then exits cleanly.

    Verified by counting the set_frequency requests issued to dst.
    """
    # Wrap dst._send_message to count SET commands.
    dst_sets: list[str] = []
    original_dst_send_holder: list = []

    src = _make_rigctl()
    dst = _make_rigctl()
    task = _make_sync_task(src, dst)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    freq_reads: list[int] = [0]
    original_src = src._send_message
    original_dst = dst._send_message

    def _src_send(request: str) -> str:
        result = original_src(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= n_cycles:
                syncing.terminate()
        return result

    def _dst_send(request: str) -> str:
        result = original_dst(request)
        if request.startswith("F ") or request.startswith("M "):
            dst_sets.append(request)
        return result

    src._send_message = _src_send  # type: ignore[method-assign]
    dst._send_message = _dst_send  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)

    freq_sets = [r for r in dst_sets if r.startswith("F ")]
    mode_sets = [r for r in dst_sets if r.startswith("M ")]

    assert len(freq_sets) == n_cycles, (
        f"Expected {n_cycles} set_frequency calls on dst, got {len(freq_sets)}"
    )
    assert len(mode_sets) == n_cycles, (
        f"Expected {n_cycles} set_mode calls on dst, got {len(mode_sets)}"
    )


# ---------------------------------------------------------------------------
# Test: committed frequency is confirmed by gqrx read-back after sync
# ---------------------------------------------------------------------------

def test_sync_continuous_last_frequency_confirmed_by_gqrx():
    """After the sync loop exits, get_frequency() on the shared gqrx endpoint
    returns the value that was propagated in the final cycle."""
    KNOWN_FREQ = 88_000_000   # tune to this before starting sync

    src = _make_rigctl()
    dst = _make_rigctl()

    # Pre-condition: tune gqrx to a known frequency before sync begins.
    src.set_frequency(KNOWN_FREQ)
    src.set_mode("FM")
    time.sleep(_SETTLE_S)

    task = _make_sync_task(src, dst)
    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    freq_reads: list[int] = [0]
    original_src = src._send_message

    def _src_send(request: str) -> str:
        result = original_src(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= 2:
                syncing.terminate()
        return result

    src._send_message = _src_send  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)

    # After sync, read back from dst (same endpoint) to confirm set_frequency
    # was actually committed to gqrx.
    read_freq = None
    for _ in range(_MAX_READBACK_RETRIES):
        time.sleep(_SETTLE_S)
        read_freq = int(dst.get_frequency())
        if read_freq == KNOWN_FREQ:
            break

    assert read_freq == KNOWN_FREQ, (
        f"Expected gqrx to confirm frequency {KNOWN_FREQ} Hz after sync, "
        f"got {read_freq}"
    )


# ---------------------------------------------------------------------------
# Test: notify_end_of_scan called exactly once on loop exit
# ---------------------------------------------------------------------------

def test_sync_continuous_notify_end_of_scan_called_once():
    """task.syncq.notify_end_of_scan() is called exactly once when the
    continuous sync loop terminates, verified against a real gqrx connection."""
    src = _make_rigctl()
    dst = _make_rigctl()

    syncq = Mock(spec=STMessenger)
    task = SyncTask(syncq=syncq, src_rig=src, dst_rig=dst)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    freq_reads: list[int] = [0]
    original_src = src._send_message

    def _src_send(request: str) -> str:
        result = original_src(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= 2:
                syncing.terminate()
        return result

    src._send_message = _src_send  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)

    syncq.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# Test: set_frequency precedes set_mode in every cycle on real hardware
# ---------------------------------------------------------------------------

def test_sync_continuous_frequency_set_before_mode_every_cycle():
    """Within each sync cycle the 'F <freq>' command is sent to dst before the
    'M <mode>' command, verified by recording raw _send_message calls on dst
    against a live gqrx connection."""
    N = 3

    src = _make_rigctl()
    dst = _make_rigctl()
    task = _make_sync_task(src, dst)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    cmd_log: list[str] = []
    original_dst = dst._send_message

    def _recording_dst(request: str) -> str:
        result = original_dst(request)
        if request.startswith("F ") or request.startswith("M "):
            cmd_log.append(request[0])   # "F" or "M"
        return result

    freq_reads: list[int] = [0]
    original_src = src._send_message

    def _src_send(request: str) -> str:
        result = original_src(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= N:
                syncing.terminate()
        return result

    src._send_message = _src_send  # type: ignore[method-assign]
    dst._send_message = _recording_dst  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)

    assert cmd_log == ["F", "M"] * N, (
        f"Expected alternating F/M for {N} cycles, got: {cmd_log}"
    )


# ---------------------------------------------------------------------------
# Test: no extra commands on dst after terminate()
# ---------------------------------------------------------------------------

def test_sync_continuous_no_extra_commands_after_terminate():
    """Exactly N 'F ' and N 'M ' commands reach dst — no commands are issued
    after the cycle in which terminate() is called."""
    N = 2

    src = _make_rigctl()
    dst = _make_rigctl()
    task = _make_sync_task(src, dst)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    dst_cmds: list[str] = []
    original_dst = dst._send_message

    def _recording_dst(request: str) -> str:
        result = original_dst(request)
        if request.startswith("F ") or request.startswith("M "):
            dst_cmds.append(request[:1])
        return result

    freq_reads: list[int] = [0]
    original_src = src._send_message

    def _src_send(request: str) -> str:
        result = original_src(request)
        if request == "f":
            freq_reads[0] += 1
            if freq_reads[0] >= N:
                syncing.terminate()
        return result

    src._send_message = _src_send  # type: ignore[method-assign]
    dst._send_message = _recording_dst  # type: ignore[method-assign]

    syncing.sync(task=task, once=False)

    freq_cmds = [c for c in dst_cmds if c == "F"]
    mode_cmds = [c for c in dst_cmds if c == "M"]
    assert len(freq_cmds) == N, (
        f"Expected {N} F commands on dst, got {len(freq_cmds)}: {dst_cmds}"
    )
    assert len(mode_cmds) == N, (
        f"Expected {N} M commands on dst, got {len(mode_cmds)}: {dst_cmds}"
    )

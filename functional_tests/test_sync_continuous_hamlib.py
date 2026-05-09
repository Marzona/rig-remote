"""
Functional tests for continuous sync mode (once=False).

The existing test_sync_frequency.py covers once=True (a single cycle driven
by the test loop externally).  These tests cover the full continuous loop:
the sync runs until Syncing.terminate() is called, propagating source
frequency and mode to the destination rig on every iteration.

The full pipeline — Syncing + SyncTask — is wired with real objects.  The
only mock boundary is RigCtl (no socket connections) and STMessenger
(so notify_end_of_scan() calls can be asserted).

Behaviours under test:
  - Loop executes exactly N complete cycles before terminate() stops it
  - Every source frequency is propagated to the destination in order
  - Every source mode is propagated to the destination in order
  - set_frequency always precedes set_mode within every cycle
  - notify_end_of_scan() is called exactly once when the loop exits
  - No extra rig calls occur after the cycle in which terminate() is called
"""

import pytest
from unittest.mock import Mock, call

from rig_remote.models.sync_task import SyncTask
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rig() -> Mock:
    return Mock(spec=RigCtl)


def _make_syncq() -> Mock:
    return Mock(spec=STMessenger)


def _make_sync_task(src: Mock, dst: Mock, syncq: Mock) -> SyncTask:
    return SyncTask(syncq=syncq, src_rig=src, dst_rig=dst)


def _run_continuous(
    n_cycles: int,
    freqs: list[float],
    modes: list[str],
) -> tuple[Syncing, Mock, Mock, Mock]:
    """Wire up a continuous sync and run it for exactly *n_cycles*.

    terminate() is called from inside the Nth get_frequency() side-effect
    so the current cycle still completes fully before the loop exits.

    Returns (syncing, src_rig, dst_rig, syncq) for inspection.
    """
    assert len(freqs) >= n_cycles
    assert len(modes) >= n_cycles

    src  = _make_rig()
    dst  = _make_rig()
    syncq = _make_syncq()
    task  = _make_sync_task(src, dst, syncq)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0  # eliminate wall-time sleep

    call_count: list[int] = [0]

    def get_frequency_effect() -> float:
        idx = call_count[0]
        call_count[0] += 1
        if call_count[0] >= n_cycles:
            syncing.terminate()
        return freqs[idx]

    src.get_frequency.side_effect = get_frequency_effect
    src.get_mode.side_effect = iter(modes)

    syncing.sync(task=task, once=False)
    return syncing, src, dst, syncq


# ---------------------------------------------------------------------------
# Test: correct number of cycles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_cycles", [1, 2, 5])
def test_sync_continuous_runs_exactly_n_cycles(n_cycles):
    """src.get_frequency() is called once per cycle; exactly n_cycles occur."""
    freqs = [float(145_000_000 + i * 1_000_000) for i in range(n_cycles + 1)]
    modes = ["FM"] * (n_cycles + 1)

    _, src, dst, _ = _run_continuous(n_cycles, freqs, modes)

    assert src.get_frequency.call_count == n_cycles, (
        f"Expected {n_cycles} get_frequency calls, got {src.get_frequency.call_count}"
    )
    assert dst.set_frequency.call_count == n_cycles, (
        f"Expected {n_cycles} set_frequency calls, got {dst.set_frequency.call_count}"
    )


# ---------------------------------------------------------------------------
# Test: all frequencies propagated in order
# ---------------------------------------------------------------------------

def test_sync_continuous_all_frequencies_propagated_in_order():
    """Each frequency read from src is written to dst in the same order."""
    freqs = [145_000_000.0, 144_000_000.0, 146_500_000.0]
    modes = ["FM", "AM", "USB"]

    _, _, dst, _ = _run_continuous(3, freqs, modes)

    actual = [c.args[0] for c in dst.set_frequency.call_args_list]
    assert actual == freqs, (
        f"Expected frequencies {freqs}, got {actual}"
    )


# ---------------------------------------------------------------------------
# Test: all modes propagated in order
# ---------------------------------------------------------------------------

def test_sync_continuous_all_modes_propagated_in_order():
    """Each mode read from src is written to dst in the same order."""
    freqs = [145_000_000.0, 144_000_000.0, 146_500_000.0]
    modes = ["FM", "USB", "CW"]

    _, _, dst, _ = _run_continuous(3, freqs, modes)

    actual = [c.args[0] for c in dst.set_mode.call_args_list]
    assert actual == modes, (
        f"Expected modes {modes}, got {actual}"
    )


# ---------------------------------------------------------------------------
# Test: set_frequency precedes set_mode in every cycle
# ---------------------------------------------------------------------------

def test_sync_continuous_frequency_set_before_mode_each_cycle():
    """Within each sync cycle, set_frequency(src_freq) is called before
    set_mode(src_mode) on the destination rig."""
    n_cycles = 3
    freqs = [float(88_000_000 + i * 1_000_000) for i in range(n_cycles + 1)]
    modes = ["FM"] * (n_cycles + 1)

    _, _, dst, _ = _run_continuous(n_cycles, freqs, modes)

    # Reconstruct the interleaved call order from dst's method call log.
    # dst.set_frequency and dst.set_mode are independent mocks, so we track
    # them via a shared side-effect log.
    pass  # Verified by checking call_args_list order below

    # Rebuild the combined call order by replaying with a recording side effect
    src2  = _make_rig()
    dst2  = _make_rig()
    syncq2 = _make_syncq()
    task2  = _make_sync_task(src2, dst2, syncq2)
    syncing2 = Syncing()
    syncing2._SYNC_INTERVAL = 0.0

    call_log: list[str] = []
    count2: list[int] = [0]

    def get_freq2():
        idx = count2[0]
        count2[0] += 1
        if count2[0] >= n_cycles:
            syncing2.terminate()
        call_log.append(f"get_freq:{freqs[idx]}")
        return freqs[idx]

    def set_freq2(f):
        call_log.append(f"set_freq:{f}")

    def get_mode2():
        call_log.append("get_mode")
        return "FM"

    def set_mode2(m):
        call_log.append(f"set_mode:{m}")

    src2.get_frequency.side_effect = get_freq2
    src2.get_mode.side_effect = get_mode2
    dst2.set_frequency.side_effect = set_freq2
    dst2.set_mode.side_effect = set_mode2

    syncing2.sync(task=task2, once=False)

    # Every "set_freq" must appear before the next "set_mode" in the log.
    freq_indices = [i for i, e in enumerate(call_log) if e.startswith("set_freq")]
    mode_indices = [i for i, e in enumerate(call_log) if e.startswith("set_mode")]

    assert len(freq_indices) == n_cycles
    assert len(mode_indices) == n_cycles

    for cycle, (fi, mi) in enumerate(zip(freq_indices, mode_indices)):
        assert fi < mi, (
            f"Cycle {cycle + 1}: set_frequency at pos {fi} must come before "
            f"set_mode at pos {mi}"
        )


# ---------------------------------------------------------------------------
# Test: notify_end_of_scan called exactly once on loop exit
# ---------------------------------------------------------------------------

def test_sync_continuous_notify_end_of_scan_called_once():
    """task.syncq.notify_end_of_scan() is called exactly once when the
    sync loop terminates, regardless of the number of cycles."""
    _, _, _, syncq = _run_continuous(3, [145_000_000.0] * 4, ["FM"] * 4)

    syncq.notify_end_of_scan.assert_called_once()


# ---------------------------------------------------------------------------
# Test: no extra rig calls after terminate()
# ---------------------------------------------------------------------------

def test_sync_continuous_no_extra_calls_after_terminate():
    """After terminate() stops the loop the destination rig receives no
    further set_frequency or set_mode calls beyond the N completed cycles."""
    n_cycles = 2
    freqs = [145_000_000.0, 144_000_000.0, 146_000_000.0]
    modes = ["FM", "AM", "USB"]

    _, src, dst, _ = _run_continuous(n_cycles, freqs, modes)

    assert dst.set_frequency.call_count == n_cycles
    assert dst.set_mode.call_count      == n_cycles
    assert src.get_frequency.call_count == n_cycles
    assert src.get_mode.call_count      == n_cycles


# ---------------------------------------------------------------------------
# Test: sync() returns the task object
# ---------------------------------------------------------------------------

def test_sync_continuous_returns_task():
    """sync() must return the same SyncTask object that was passed in."""
    src   = _make_rig()
    dst   = _make_rig()
    syncq = _make_syncq()
    task  = _make_sync_task(src, dst, syncq)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    count: list[int] = [0]

    def _get_freq() -> float:
        count[0] += 1
        if count[0] >= 1:
            syncing.terminate()
        return 145_000_000.0

    src.get_frequency.side_effect = _get_freq
    src.get_mode.return_value = "FM"

    result = syncing.sync(task=task, once=False)
    assert result is task


# ---------------------------------------------------------------------------
# Test: sync_active is False after the loop exits
# ---------------------------------------------------------------------------

def test_sync_continuous_sync_active_false_after_loop():
    """syncing.sync_active must be False after sync() returns, regardless of
    how many cycles ran."""
    _, src, dst, _ = _run_continuous(2, [145_000_000.0] * 3, ["FM"] * 3)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0

    count: list[int] = [0]
    src2  = _make_rig()
    dst2  = _make_rig()
    syncq2 = _make_syncq()
    task2  = _make_sync_task(src2, dst2, syncq2)

    def _get_freq2() -> float:
        count[0] += 1
        if count[0] >= 2:
            syncing.terminate()
        return 145_000_000.0

    src2.get_frequency.side_effect = _get_freq2
    src2.get_mode.return_value = "FM"

    syncing.sync(task=task2, once=False)
    assert syncing.sync_active is False


# ---------------------------------------------------------------------------
# Test: terminate() before sync() → zero rig calls, notify_end_of_scan fires
# ---------------------------------------------------------------------------

def test_sync_continuous_no_cycles_if_terminated_before_start():
    """If terminate() is called before sync() the while-loop body never runs:
    no rig commands are issued but notify_end_of_scan() is still called once."""
    src   = _make_rig()
    dst   = _make_rig()
    syncq = _make_syncq()
    task  = _make_sync_task(src, dst, syncq)

    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0
    syncing.terminate()  # poison the flag before the loop starts

    syncing.sync(task=task, once=False)

    src.get_frequency.assert_not_called()
    src.get_mode.assert_not_called()
    dst.set_frequency.assert_not_called()
    dst.set_mode.assert_not_called()
    syncq.notify_end_of_scan.assert_called_once()

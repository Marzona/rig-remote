"""
Functional tests for frequency synchronisation between two rigs.

These tests exercise the full sync pipeline end-to-end — Syncing, SyncTask,
and RigCtl — wired together with real objects.  The only mock boundary is
RigCtl._send_message (radio hardware), injected directly on the instances so
no socket connections are attempted.

Assertions target the _send_message call log to verify that:
  - frequency is first read (GET) from the source rig (port 7356)
  - the same frequency is then written (SET) to the destination rig (port 7357)
  - mode is read from source and written to destination in the same cycle
  - the correct order is maintained across multiple sync cycles
"""

from unittest.mock import Mock

from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.sync_task import SyncTask
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SRC_PORT = 7356   # primary gqrx instance (source)
_DST_PORT = 7357   # secondary gqrx instance (destination)

_FREQ_UP   = 145_600_000   # 145.6 MHz — simulates user tuning up
_FREQ_DOWN = 144_000_000   # 144.0 MHz — simulates user tuning down
_MODE_1    = "WFM"
_MODE_2    = "AM"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rigctl(port: int, rig_number: int) -> RigCtl:
    """Return a RigCtl bound to localhost at *port*."""
    return RigCtl(RigEndpoint(hostname="localhost", port=port, number=rig_number))


def _make_sync_task(src_rig: RigCtl, dst_rig: RigCtl) -> SyncTask:
    """Return a SyncTask with a fresh real STMessenger."""
    return SyncTask(
        syncq=STMessenger(queue_comms=QueueComms()),
        src_rig=src_rig,
        dst_rig=dst_rig,
    )


def _request_arg(c: object) -> str:
    """Extract the request string from a Mock call regardless of whether
    it was passed as a positional or keyword argument.

    RigCtl mixes both styles:
      get_frequency  → _send_message("f")          positional
      get_mode       → _send_message(request="m")  keyword
      set_frequency  → _send_message(request=...)  keyword
      set_mode       → _send_message(request=...)  keyword
    """
    from unittest.mock import _Call  # type: ignore[attr-defined]
    # call_args_list items are _Call objects; .args / .kwargs are standard
    assert hasattr(c, "args") and hasattr(c, "kwargs")
    if getattr(c, "args"):
        return str(getattr(c, "args")[0])
    return str(getattr(c, "kwargs")["request"])


# ---------------------------------------------------------------------------
# Functional test
# ---------------------------------------------------------------------------

def test_sync_reads_from_src_and_propagates_to_dst() -> None:
    """Two sync cycles cover four distinct _send_message interactions:

        cycle 1 — frequency UP  : src returns 145.6 MHz, mode WFM
        cycle 2 — frequency DOWN: src returns 144.0 MHz, mode AM

    The test verifies that:
      1. Every get on the source rig is followed immediately by the
         corresponding set on the destination rig (no reordering).
      2. Frequency changes (up and down) are propagated correctly.
      3. Both mode changes reach the destination in the right cycle.
    """
    # -- RigCtl instances; _send_message is replaced with a Mock so no
    #    real socket connections are attempted. --
    src_rig = _make_rigctl(port=_SRC_PORT, rig_number=1)
    dst_rig = _make_rigctl(port=_DST_PORT, rig_number=2)

    # Four ordered _send_message responses from the source rig — the "queue"
    # of messages that trigger each retrieval:
    #   cycle 1: frequency up  → _FREQ_UP,   then mode change → _MODE_1
    #   cycle 2: frequency down → _FREQ_DOWN, then mode change → _MODE_2
    src_rig._send_message = Mock(  # type: ignore[method-assign]
        side_effect=[
            str(_FREQ_UP),    # cycle 1 — get_frequency() → 145.6 MHz (up)
            _MODE_1,          # cycle 1 — get_mode()      → WFM
            str(_FREQ_DOWN),  # cycle 2 — get_frequency() → 144.0 MHz (down)
            _MODE_2,          # cycle 2 — get_mode()      → AM
        ]
    )
    # Destination rig just needs to absorb the set calls.
    dst_rig._send_message = Mock(return_value="")  # type: ignore[method-assign]

    task    = _make_sync_task(src_rig=src_rig, dst_rig=dst_rig)
    syncing = Syncing()
    syncing._SYNC_INTERVAL = 0.0  # avoid wall-time sleep; 0 s is still valid

    # -- Cycle 1 --
    syncing.sync(task=task, once=True)

    # sync() sets sync_active=False after once=True; re-arm before cycle 2.
    syncing.sync_active = True

    # -- Cycle 2 --
    syncing.sync(task=task, once=True)

    # ------------------------------------------------------------------ #
    # Assertions                                                           #
    # ------------------------------------------------------------------ #

    # --- source rig: four reads in strict order (f, m, f, m) ---
    assert src_rig._send_message.call_count == 4, (
        f"Expected 4 reads from src rig, got {src_rig._send_message.call_count}"
    )

    src_requests = [_request_arg(c) for c in src_rig._send_message.call_args_list]
    assert src_requests == ["f", "m", "f", "m"], (
        f"Source rig commands out of order: {src_requests}"
    )

    # --- destination rig: four writes matching the source values ---
    assert dst_rig._send_message.call_count == 4, (
        f"Expected 4 writes to dst rig, got {dst_rig._send_message.call_count}"
    )

    dst_requests = [_request_arg(c) for c in dst_rig._send_message.call_args_list]

    # Cycle 1: frequency UP propagated before mode change 1
    assert dst_requests[0] == f"F {float(_FREQ_UP)}", (
        f"Cycle 1 — expected frequency up 'F {float(_FREQ_UP)}', got '{dst_requests[0]}'"
    )
    assert dst_requests[1] == f"M {_MODE_1}", (
        f"Cycle 1 — expected mode '{_MODE_1}', got '{dst_requests[1]}'"
    )

    # Cycle 2: frequency DOWN propagated before mode change 2
    assert dst_requests[2] == f"F {float(_FREQ_DOWN)}", (
        f"Cycle 2 — expected frequency down 'F {float(_FREQ_DOWN)}', got '{dst_requests[2]}'"
    )
    assert dst_requests[3] == f"M {_MODE_2}", (
        f"Cycle 2 — expected mode '{_MODE_2}', got '{dst_requests[3]}'"
    )

"""
Shared primitive layer for all scanner strategies.

ScannerCore owns the RigCtl reference, the STMessenger queue, the
ScanningConfig, the liveness flag, and the sleep indirection.  All
scanner strategies are composed with a ScannerCore instance.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from rig_remote.models.channel import Channel
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.scanning_config import ScanningConfig
from rig_remote.stmessenger import STMessenger
from rig_remote.utility import khertz_to_hertz

logger = logging.getLogger(__name__)


class ScannerCore:
    """Low-level scanning primitives shared by all scanner strategies.

    Owns:
      - the STMessenger queue reference
      - the RigCtl reference
      - the ScanningConfig
      - the liveness flag (_scan_active)
      - the sleep indirection (injectable for tests)
    """

    # Explicit converters for every mutable ScanningTask field that can arrive
    # via the scan queue.  Using a whitelist prevents arbitrary string values
    # from bypassing ScanningTask's validation and makes the allowed mutations
    # self-documenting.  range_min / range_max are handled separately because
    # they require a kHz→Hz conversion before assignment.
    _QUEUE_EVENT_CONVERTERS: dict[str, Callable[[Any], Any]] = {
        "wait": bool,
        "record": bool,
        "sgn_level": int,
        "passes": int,
        "interval": int,
        "delay": int,
    }

    def __init__(
        self,
        scan_queue: STMessenger,
        rigctl: RigCtl,
        config: ScanningConfig,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        """Initialise the core with all required dependencies.

        :param scan_queue: Inter-thread messenger used to receive UI parameter
            updates while a scan is running.
        :param rigctl: RigCtl instance used to send frequency and mode commands
            to the radio hardware.
        :param config: ScanningConfig holding all timing and signal constants
            for this session.
        :param sleep_fn: Optional callable used instead of ``time.sleep``; inject
            a no-op in tests to avoid wall-time delays.
        """
        self.scan_queue = scan_queue
        self.rigctl = rigctl
        self.config = config
        self._scan_active: bool = True
        self._sleep: Callable[[float], None] = sleep_fn or time.sleep

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def terminate(self) -> None:
        """Deactivate the scan loop by clearing the liveness flag."""
        logger.info("Terminating scan.")
        self._scan_active = False

    def should_stop(self) -> bool:
        """Return True when the scan has been terminated.

        Using a method prevents mypy from narrowing _scan_active to
        Literal[True] inside while-loops.

        :returns: True if ``terminate()`` has been called, False otherwise.
        """
        return not self._scan_active

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def queue_sleep(self, task: ScanningTask) -> None:
        """Poll the queue every second for *task.delay* seconds.

        Checks the queue on each iteration so that UI parameter updates
        are applied promptly even during a delay period.

        :param task: The active ScanningTask; its ``delay`` field determines
            how many seconds to wait, and it may be mutated by queue events
            processed during the wait.
        """
        remaining = task.delay
        while True:
            if self.scan_queue.update_queued():
                self.process_queue(task)
            if remaining > 0:
                self._sleep(1)
                remaining -= 1
            else:
                break

    def process_queue(self, task: ScanningTask) -> bool:
        """Drain the scan queue, applying valid UI parameter updates to *task*.

        Each event is a ``(param_name, param_value)`` pair.  Names matching
        ``config.valid_scan_update_event_names`` are applied via ``setattr``
        (with special handling for ``range_min`` / ``range_max`` which are
        converted from kHz to Hz).  Unknown names or conversion errors abort
        processing for that event.

        :param task: The active ScanningTask to update in-place.
        :returns: True if at least one event was successfully applied,
            False otherwise.
        """
        processed = False
        while self.scan_queue.update_queued():
            event = self.scan_queue.get_event_update()
            if event is None:
                break

            param_name, param_value = event
            logger.info("Retrieved event %s %s", param_name, param_value)

            if param_name not in self.config.valid_scan_update_event_names:
                logger.warning(
                    "Unsupported scan update event %s — supported: %s",
                    param_name,
                    self.config.valid_scan_update_event_names,
                )
                break

            try:
                # UI passes "txt_range_min"; task attribute is "range_min".
                key = param_name.split("_", 1)[1]
                if key == "range_min":
                    task.range_min = khertz_to_hertz(int(param_value))
                elif key == "range_max":
                    task.range_max = khertz_to_hertz(int(param_value))
                elif key in self._QUEUE_EVENT_CONVERTERS:
                    converter = self._QUEUE_EVENT_CONVERTERS[key]
                    setattr(task, key, converter(param_value))
                else:
                    logger.warning(
                        "Queue event key %r has no registered converter — skipping",
                        key,
                    )
                    break
            except (ValueError, TypeError) as exc:
                logger.warning("Queue event update failed: %s — event: %s %s", exc, param_name, param_value)
                break

            processed = True
            logger.info("Queue event applied: %s = %s", param_name, param_value)

        return processed

    # ------------------------------------------------------------------
    # Radio control helpers
    # ------------------------------------------------------------------

    def channel_tune(self, channel: Channel) -> None:
        """Tune the rig to *channel* and wait for it to settle.

        Issues a frequency command followed by a mode command, sleeping for
        ``config.time_wait_for_tune`` seconds after each.  Sets
        ``_scan_active = False`` and re-raises on communications errors so
        the caller can abort the current pass.

        :param channel: Channel containing the target frequency (Hz) and
            modulation string to send to the rig.
        :raises ValueError: If the frequency or modulation value is rejected
            by the rig.
        :raises OSError: If a low-level I/O error occurs while communicating
            with the rig.
        :raises TimeoutError: If the rig does not respond within the expected
            time window.
        """
        logger.info("Tuning to %i", channel.frequency)
        try:
            self.rigctl.set_frequency(channel.frequency)
        except ValueError:
            logger.error("Bad frequency parameter.")
            raise
        except (OSError, TimeoutError):
            logger.error("Communications error while setting frequency.")
            self._scan_active = False
            raise
        self._sleep(self.config.time_wait_for_tune)

        try:
            self.rigctl.set_mode(channel.modulation)
        except ValueError:
            logger.error("Bad modulation parameter.")
            raise
        except (OSError, TimeoutError):
            logger.error("Communications error while setting mode.")
            self._scan_active = False
            raise
        self._sleep(self.config.time_wait_for_tune)

    def signal_check(self, sgn_level: int) -> bool:
        """Sample the signal level ``config.signal_checks`` times.

        Compares the raw level returned by the rig against *sgn_level* × 10
        (converting dBFS to internal units).  Returns True as soon as at
        least one sample exceeds the threshold.

        :param sgn_level: Signal threshold in dBFS.  Any rig level reading
            at or above ``sgn_level * 10`` is counted as a hit.
        :returns: True if the signal was detected in at least one sample,
            False if all samples were below the threshold.
        """
        threshold = int(sgn_level) * 10  # dBFS → internal units
        signal_found = 0
        level: float = 0.0

        for i in range(self.config.signal_checks):
            logger.debug("Signal check %d/%d: level threshold=%f", i + 1, self.config.signal_checks, threshold)
            level = self.rigctl.get_level()
            logger.debug("Signal check result: level=%f  threshold=%f", level, threshold)
            if level >= threshold:
                signal_found += 1
            self._sleep(self.config.no_signal_delay)

        if signal_found > 0:
            logger.info(
                "Activity found — level: %f  hits: %d/%d",
                level,
                signal_found,
                self.config.signal_checks,
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Pass-count helper
    # ------------------------------------------------------------------

    def pass_count_update(self, pass_count: int) -> int:
        """Decrement *pass_count* and deactivate the scan when it reaches zero.

        A value of zero means "unlimited passes" and is never decremented
        further; the scan is deactivated only when the count transitions
        from 1 to 0.

        :param pass_count: Current remaining pass count.
        :returns: Updated pass count after decrementing (minimum 0).
        """
        if pass_count > 0:
            pass_count -= 1
        if pass_count == 0:
            logger.info("Maximum passes reached — deactivating scan.")
            self._scan_active = False
        return pass_count

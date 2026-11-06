"""
Shared primitive layer for all scanner strategies.

ScannerCore owns the RigBackend reference, the STMessenger queue, the
ScanningConfig, the liveness flag, and the sleep indirection.  All
scanner strategies are composed with a ScannerCore instance.
"""

import logging
import time
from collections.abc import Callable

from rig_remote.constants import INFINITE_PASSES
from rig_remote.models.channel import Channel
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rig_backends.protocol import RigBackend
from rig_remote.scanning_config import ScanningConfig
from rig_remote.stmessenger import STMessenger
from rig_remote.utility import khertz_to_hertz

logger = logging.getLogger(__name__)


# Hamlib.error is an optional runtime dependency.  Import it lazily so the
# module loads correctly in environments where Hamlib is not installed.
def parse_bool(value: str) -> bool:
    """Strictly parse a queue boolean: true/false (any case) or 1/0.

    :raises ValueError: for anything else (``bool("False")`` would be True).
    """
    normalised = value.strip().lower()
    if normalised in ("true", "1"):
        return True
    if normalised in ("false", "0"):
        return False
    raise ValueError(f"invalid boolean value {value!r}")


# When Hamlib is absent, _HAMLIB_ERROR is a never-raised sentinel type.
try:
    from Hamlib import error as _HAMLIB_ERROR
except ImportError:
    _HAMLIB_ERROR = type("_NoHamlibError", (Exception,), {})


class ScannerCore:
    """Low-level scanning primitives shared by all scanner strategies.

    Owns:
      - the STMessenger queue reference
      - the RigBackend reference
      - the ScanningConfig
      - the liveness flag (_scan_active)
      - the sleep indirection (injectable for tests)
    """

    _QUEUE_EVENT_CONVERTERS: dict[str, Callable[[str], int | bool]] = {
        "wait": parse_bool,
        "record": parse_bool,
        "sgn_level": int,
        "passes": int,
        "interval": int,
        "delay": int,
    }

    def __init__(
        self,
        scan_queue: STMessenger,
        rigctl: RigBackend,
        config: ScanningConfig,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.scan_queue = scan_queue
        self.rigctl = rigctl
        self.config = config
        self._scan_active: bool = True
        self._passes_updated: bool = False
        self._sleep: Callable[[float], None] = sleep_fn or time.sleep

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def terminate(self) -> None:
        """Deactivate the scan loop by clearing the liveness flag."""
        logger.info("Terminating scan.")
        self._scan_active = False

    def should_stop(self) -> bool:
        return not self._scan_active

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def queue_sleep(self, task: ScanningTask) -> None:
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
        """Apply every queued update to *task*; return True if any was applied.

        An invalid event is logged and skipped, and draining continues, so a
        bad event never delays the valid events queued behind it. A ``passes``
        update is recorded for ``consume_passes_update``.
        """
        processed = False
        while self.scan_queue.update_queued():
            event = self.scan_queue.get_event_update()
            if event is None:
                break

            param_name, param_value = event
            if not isinstance(param_value, str):
                logger.warning(  # type: ignore[unreachable]
                    "Queue event %s has non-str value %r (%s) — skipping",
                    param_name,
                    param_value,
                    type(param_value).__name__,
                )
                continue
            logger.info("Retrieved event %s %s", param_name, param_value)

            if param_name not in self.config.valid_scan_update_event_names:
                logger.warning(
                    "Unsupported scan update event %s — supported: %s",
                    param_name,
                    self.config.valid_scan_update_event_names,
                )
                continue

            try:
                key = param_name.split("_", 1)[1]
                if key in ("range_min", "range_max"):
                    task.apply_update(key, khertz_to_hertz(int(param_value)))
                elif key in self._QUEUE_EVENT_CONVERTERS:
                    converter = self._QUEUE_EVENT_CONVERTERS[key]
                    task.apply_update(key, converter(param_value))
                else:
                    logger.warning(
                        "Queue event key %r has no registered converter — skipping",
                        key,
                    )
                    continue
            except (ValueError, TypeError) as exc:  # parse failures; clamping is done in apply_update
                logger.warning(
                    "Queue event update failed: %s — event: %s %s",
                    exc,
                    param_name,
                    param_value,
                )
                continue

            if key == "passes":
                self._passes_updated = True
            processed = True
            logger.info("Queue event applied: %s = %s", param_name, param_value)

        return processed

    # ------------------------------------------------------------------
    # Radio control helpers
    # ------------------------------------------------------------------

    def channel_tune(self, channel: Channel) -> None:
        """Tune the rig to *channel* and wait for it to settle.

        Catches OSError, TimeoutError, and Hamlib.error (all treated as
        retriable communications errors).  ValueError from ModeTranslator
        (unmapped mode) is also retriable — the scan skips the channel.
        """
        logger.info("Tuning to %i", channel.frequency)
        try:
            self.rigctl.set_frequency(channel.frequency)
        except ValueError:
            logger.error("Bad frequency parameter.")
            raise
        except (OSError, TimeoutError, _HAMLIB_ERROR):
            logger.error("Communications error while setting frequency.")
            self._scan_active = False
            raise
        self._sleep(self.config.time_wait_for_tune)

        try:
            self.rigctl.set_mode(channel.modulation)
        except ValueError:
            logger.error("Bad modulation parameter.")
            raise
        except (OSError, TimeoutError, _HAMLIB_ERROR):
            logger.error("Communications error while setting mode.")
            self._scan_active = False
            raise
        self._sleep(self.config.time_wait_for_tune)

    def signal_check(self, sgn_level: int) -> bool:
        """Sample the signal level ``config.signal_checks`` times."""
        threshold = int(sgn_level) * 10
        signal_found = 0
        level: int = 0

        for i in range(self.config.signal_checks):
            logger.debug(
                "Signal check %d/%d: threshold=%d",
                i + 1,
                self.config.signal_checks,
                threshold,
            )
            level = self.rigctl.get_level()
            logger.debug("Signal check result: level=%d threshold=%d", level, threshold)
            if level >= threshold:
                signal_found += 1
            self._sleep(self.config.no_signal_delay)

        if signal_found > 0:
            logger.info(
                "Activity found — level: %d  hits: %d/%d",
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
        """Count one finished pass and deactivate the scan after the last one.

        ``INFINITE_PASSES`` (0) means scan until stopped: the count is returned
        unchanged and the scan stays active. A positive count is decremented,
        and the scan is deactivated when it reaches zero.
        """
        if pass_count == INFINITE_PASSES:
            return pass_count
        pass_count -= 1
        if pass_count <= 0:
            logger.info("Maximum passes reached — deactivating scan.")
            self._scan_active = False
            return 0
        return pass_count

    def consume_passes_update(self) -> bool:
        """Return True once after a queue event changed ``passes``, then reset.

        Strategies use this to restart their remaining-pass count only when the
        user changed the number of passes, not on every queue event. It also
        catches ``passes`` updates applied while sleeping in ``queue_sleep``.
        """
        updated = self._passes_updated
        self._passes_updated = False
        return updated

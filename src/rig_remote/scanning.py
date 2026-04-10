"""
Refactored scanning module using the composition pattern.

Design:
    ScanningConfig   — dataclass holding all tuning/signal constants.
    ScannerCore      — shared low-level primitives (tune, signal check,
                       queue management) composed into both strategies.
    BookmarkScannerStrategy  — bookmark-scan strategy, composed with ScannerCore.
    FrequencyScannerStrategy — frequency-scan strategy, composed with ScannerCore;
                               owns prev-level/freq bookmarking state.
    Scanning2                — public facade; owns the LogFile lifecycle and
                       delegates scan() / terminate() to the strategy.
    create_scanner() — factory: accepts scan_mode + dependencies,
                       builds ScannerCore, wraps it in the right strategy,
                       returns a ready Scanning2 instance.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Protocol, runtime_checkable

from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.utility import khertz_to_hertz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScanningConfig:
    """All tunable constants for a scanning session.

    Moving these out of the class body makes them explicit, injectable,
    and easy to override in tests without monkey-patching.

    :param time_wait_for_tune: Seconds to wait after issuing a tune command
        before reading the signal level.
    :param signal_checks: Number of times to sample the signal level before
        deciding whether a signal is present or absent.
    :param no_signal_delay: Seconds to wait between consecutive signal-level
        samples.
    :param valid_scan_update_event_names: Queue event names that are permitted
        to mutate the running ScanningTask during a scan.
    """

    # Seconds to wait after issuing a tune command before reading the signal.
    time_wait_for_tune: float = 0.25

    # How many times to sample the signal level before deciding presence/absence.
    signal_checks: int = 2

    # Seconds to wait between consecutive signal-level samples.
    no_signal_delay: float = 0.2

    # Queue event names that are allowed to mutate the running ScanningTask.
    valid_scan_update_event_names: List[str] = field(
        default_factory=lambda: [
            "ckb_wait",
            "ckb_record",
            "txt_range_max",
            "txt_range_min",
            "txt_sgn_level",
            "txt_passes",
            "txt_interval",
            "txt_delay",
        ]
    )

    def __eq__(self, other: object) -> bool:
        """Two ScanningConfigs are equal when all fields match.

        :param other: Object to compare against.
        :returns: True if *other* is a ScanningConfig with identical field
            values; NotImplemented if *other* is a different type.
        """
        if not isinstance(other, ScanningConfig):
            return NotImplemented
        return (
            self.time_wait_for_tune == other.time_wait_for_tune
            and self.signal_checks == other.signal_checks
            and self.no_signal_delay == other.no_signal_delay
            and self.valid_scan_update_event_names == other.valid_scan_update_event_names
        )


# ---------------------------------------------------------------------------
# Scanner strategy protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ScannerStrategy(Protocol):
    """Structural interface every scanner strategy must satisfy."""

    def scan(self, task: ScanningTask, log: LogFile) -> ScanningTask:
        """Execute a full scan and return the (possibly mutated) task.

        :param task: The scanning task describing range, mode, and options.
        :param log: Open LogFile to write activity records into.
        :returns: The ScanningTask after the scan completes.
        """
        ...

    def terminate(self) -> None:
        """Signal the strategy to stop scanning at the next safe opportunity."""
        ...


# ---------------------------------------------------------------------------
# Shared primitive layer
# ---------------------------------------------------------------------------

class ScannerCore:
    """Low-level scanning primitives shared by all scanner strategies.

    Owns:
      - the STMessenger queue reference
      - the RigCtl reference
      - the ScanningConfig
      - the liveness flag (_scan_active)
      - the sleep indirection (injectable for tests)
    """

    def __init__(
        self,
        scan_queue: STMessenger,
        rigctl: RigCtl,
        config: ScanningConfig,
        sleep_fn: Optional[Callable[[float], None]] = None,
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
            logger.warning("Retrieved event %s %s", param_name, param_value)

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
                else:
                    setattr(task, key, param_value)
            except Exception as exc:
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
            logger.info("Signal checks remaining: %d", self.config.signal_checks - i)
            level = self.rigctl.get_level()
            logger.info("Level: %f  threshold: %f", level, threshold)
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


# ---------------------------------------------------------------------------
# Bookmark scan strategy
# ---------------------------------------------------------------------------

class BookmarkScannerStrategy:
    """Scans through a pre-built list of bookmarks."""

    def __init__(self, core: ScannerCore) -> None:
        """Initialise the strategy with a shared ScannerCore.

        :param core: ScannerCore instance providing all low-level primitives.
        """
        self._core = core

    def terminate(self) -> None:
        """Delegate termination to the underlying ScannerCore."""
        self._core.terminate()

    def scan(self, task: ScanningTask, log: LogFile) -> ScanningTask:
        """Iterate over ``task.bookmarks``, tuning and checking each in turn.

        Locked bookmarks (``lockout == "L"``) are skipped.  A tune failure
        aborts the current pass but does not stop the outer loop unless
        ``terminate()`` was called.  Recording, logging, and the wait-for-
        signal loop are all governed by the corresponding flags in *task*.

        :param task: ScanningTask containing the bookmark list and all scan
            options (record, log, wait, passes, sgn_level, delay).
        :param log: Open LogFile to write bookmark activity records into
            when ``task.log`` is True.
        :returns: The ScanningTask after all passes complete or the scan is
            terminated.
        """
        pass_count = task.passes
        logger.info("Starting bookmark scan")

        while self._core._scan_active:
            for bookmark in task.bookmarks:
                logger.info("Processing bookmark %s", bookmark.id)

                if self._core.process_queue(task):
                    pass_count = task.passes

                if bookmark.lockout == "L":
                    logger.info("Bookmark %s locked — skipping.", bookmark.id)
                    continue

                try:
                    self._core.channel_tune(bookmark.channel)
                except (OSError, TimeoutError):
                    logger.error("Tune failed for bookmark %s — aborting pass.", bookmark.id)
                    break

                if task.record:
                    self._core.rigctl.start_recording()
                    logger.info("Recording started.")

                if self._core.signal_check(sgn_level=task.sgn_level):
                    logger.info("Signal found on bookmarked frequency %s.", bookmark.id)

                if task.log:
                    log.write(record_type="B", record=bookmark, signal=[])

                while task.wait:
                    if self._core.signal_check(sgn_level=task.sgn_level) and self._core._scan_active:
                        self._core.process_queue(task)
                    else:
                        break

                if self._core._scan_active:
                    self._core.queue_sleep(task)

                if task.record:
                    self._core.rigctl.stop_recording()
                    logger.info("Recording stopped.")

                if self._core.should_stop():
                    logger.info("Scan terminated — exiting bookmark loop.")
                    return task

            pass_count = self._core.pass_count_update(pass_count)

        self._core.scan_queue.notify_end_of_scan()
        return task


# ---------------------------------------------------------------------------
# Frequency scan strategy
# ---------------------------------------------------------------------------

class FrequencyScannerStrategy:
    """Sweeps a frequency range, optionally auto-bookmarking active frequencies."""

    def __init__(self, core: ScannerCore) -> None:
        """Initialise the strategy with a shared ScannerCore.

        :param core: ScannerCore instance providing all low-level primitives.
        """
        self._core = core
        self._prev_level: float = 0.0
        self._prev_freq: int = 0
        self._hold_bookmark: bool = False

    def terminate(self) -> None:
        """Delegate termination to the underlying ScannerCore."""
        self._core.terminate()

    # ------------------------------------------------------------------
    # Auto-bookmark helpers (owned here because they track per-scan state)
    # ------------------------------------------------------------------

    def _create_new_bookmark(self, freq: int) -> Bookmark:
        """Create and return a new auto-generated Bookmark at *freq*.

        Queries the rig for the current mode so the bookmark reflects the
        modulation in use at the time of creation.

        :param freq: Frequency in Hz at which to create the bookmark.
        :returns: A new Bookmark instance with description "auto added by scan".
        """
        bm = bookmark_factory(
            input_frequency=freq,
            modulation=self._core.rigctl.get_mode(),
            description="auto added by scan",
            lockout="",
        )
        logger.info("New bookmark created: %s", bm)
        return bm

    def _store_prev_bookmark(self, level: float, freq: int) -> None:
        """Record a candidate peak frequency for potential auto-bookmarking.

        :param level: Signal level recorded at *freq*.
        :param freq: Frequency in Hz of the candidate peak.
        """
        self._prev_level = level
        self._prev_freq = freq
        self._hold_bookmark = True

    def _erase_prev_bookmark(self) -> None:
        """Clear the stored candidate peak, resetting auto-bookmark state."""
        self._prev_level = 0.0
        self._prev_freq = 0
        self._hold_bookmark = False

    def _autobookmark(self, level: int, freq: int, task: ScanningTask) -> None:
        """Update auto-bookmark state and emit a bookmark when the peak has passed.

        On the first call (no previous level stored) the current position is
        saved as a candidate.  On subsequent calls the level is compared to the
        previous candidate: if it has stopped rising the previous frequency is
        bookmarked; otherwise the candidate is updated to the new position.

        :param level: Signal level at *freq* (in the same units as ``sgn_level``).
        :param freq: Current frequency in Hz being evaluated.
        :param task: Active ScanningTask; new bookmarks are appended to
            ``task.new_bookmarks_list``.
        """
        if not self._prev_level:
            self._store_prev_bookmark(level=level, freq=freq)
            return
        if level <= self._prev_level:
            new_bm = self._create_new_bookmark(self._prev_freq)
            logger.info("Auto-bookmarking previous frequency.")
            task.new_bookmarks_list.append(new_bm)
            self._erase_prev_bookmark()
        else:
            self._store_prev_bookmark(level=level, freq=freq)

    # ------------------------------------------------------------------
    # Main scan loop
    # ------------------------------------------------------------------

    def scan(self, task: ScanningTask, log: LogFile) -> ScanningTask:
        """Sweep from ``task.range_min`` to ``task.range_max`` in steps of
        ``task.interval``, performing a signal check at each frequency.

        When a signal is found, optional recording, auto-bookmarking, and
        activity logging are performed according to the flags in *task*.
        After each signal hit the scan pauses for ``task.delay`` seconds
        (via ``queue_sleep``) before continuing.  If no signal is found but
        a previous peak was held (``_hold_bookmark``), that frequency is
        auto-bookmarked.

        :param task: ScanningTask describing the frequency range, step size,
            modulation, and all scan options (record, log, auto_bookmark,
            passes, sgn_level, delay).
        :param log: Open LogFile to write frequency activity records into
            when ``task.log`` is True.
        :returns: The ScanningTask after all passes complete or the scan is
            terminated.
        """
        self._prev_freq = task.range_min
        pass_count = task.passes
        logger.info("Starting frequency scan")

        while self._core._scan_active:
            freq = task.range_min
            logger.info("Scan pass %d, interval %d Hz", pass_count, task.interval)

            if freq > task.range_max:
                logger.error("range_min > range_max — stopping scan.")
                self._core.terminate()

            while freq < task.range_max:
                if self._core.should_stop():
                    return task

                if self._core.process_queue(task):
                    pass_count = task.passes

                try:
                    self._core.channel_tune(
                        Channel(modulation=task.frequency_modulation, input_frequency=freq)
                    )
                except (OSError, TimeoutError, ValueError):
                    logger.error("Tune error at %d Hz — aborting pass.", freq)
                    break

                if self._core.signal_check(sgn_level=task.sgn_level):
                    if task.record:
                        self._core.rigctl.start_recording()
                        logger.info("Recording started.")

                    if task.auto_bookmark:
                        self._autobookmark(level=task.sgn_level, freq=freq, task=task)

                    if task.log:
                        new_bm = self._create_new_bookmark(freq)
                        log.write(record_type="F", record=new_bm, signal=[])

                    if self._core._scan_active:
                        self._core.queue_sleep(task)

                    if task.record:
                        self._core.rigctl.stop_recording()
                        logger.info("Recording stopped.")

                elif self._hold_bookmark:
                    new_bm = self._create_new_bookmark(self._prev_freq)
                    task.new_bookmarks_list.append(new_bm)
                    self._store_prev_bookmark(level=task.sgn_level, freq=self._prev_freq)

                freq += task.interval

            pass_count = self._core.pass_count_update(pass_count)

        self._core.scan_queue.notify_end_of_scan()
        return task


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------

class Scanning2:
    """Public facade.

    Owns the LogFile lifecycle (open before delegating, close after).
    Delegates scan() and terminate() to the injected strategy.
    """

    def __init__(
        self,
        scanner: ScannerStrategy,
        log: LogFile,
        log_filename: str,
    ) -> None:
        """Initialise the facade with its strategy and log configuration.

        :param scanner: A ScannerStrategy implementation (BookmarkScannerStrategy
            or FrequencyScannerStrategy) to delegate scan work to.
        :param log: LogFile instance whose lifecycle this facade manages.
        :param log_filename: Path to the activity log file; passed to
            ``log.open()`` when ``task.log`` is True.
        """
        self._scanner = scanner
        self._log = log
        self._log_filename = log_filename

    def terminate(self) -> None:
        """Delegate termination to the underlying scanner strategy."""
        self._scanner.terminate()

    def scan(self, task: ScanningTask) -> None:
        """Open the log (if requested), run the scan, then close the log.

        :param task: ScanningTask driving the scan; its ``log`` flag controls
            whether the LogFile is opened and closed around the scan.
        :raises IOError: If ``task.log`` is True and the log file cannot be
            opened.
        """
        if task.log:
            logger.info("Opening scan log: %s", self._log_filename)
            try:
                self._log.open(self._log_filename)
            except IOError:
                logger.exception("Could not open log file.")
                raise

        logger.info("Starting scan, mode: %s", task.scan_mode)
        self._scanner.scan(task, self._log)

        if task.log:
            self._log.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_SCANNER_REGISTRY = {
    "bookmarks": BookmarkScannerStrategy,
    "frequency": FrequencyScannerStrategy,
}


def create_scanner(
    scan_mode: str,
    scan_queue: STMessenger,
    log_filename: str,
    rigctl: RigCtl,
    config: Optional[ScanningConfig] = None,
    log: Optional[LogFile] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
) -> Scanning2:
    """Factory — returns a fully composed Scanning2 for *scan_mode*.

    Looks up the strategy class in ``_SCANNER_REGISTRY``, builds a
    ScannerCore from the supplied dependencies, wraps it in the chosen
    strategy, and returns a ready-to-use Scanning2 facade.

    :param scan_mode: Scanning mode string — ``"bookmarks"`` or
        ``"frequency"`` (case-insensitive).
    :param scan_queue: Inter-thread messenger between the UI thread and the
        scan thread, used to deliver parameter updates during a scan.
    :param log_filename: Path to the activity log file passed to
        ``Scanning2``.
    :param rigctl: RigCtl instance for the radio hardware being scanned.
    :param config: Optional ScanningConfig; a default ScanningConfig() is
        used when not provided.
    :param log: Optional LogFile; a fresh LogFile() is created when not
        provided.
    :param sleep_fn: Optional sleep callable injected into ScannerCore;
        pass a no-op lambda in tests to eliminate wall-time delays.
    :returns: A fully composed Scanning2 instance ready to call ``scan()``.
    :raises ValueError: If *scan_mode* is not a recognised mode.
    """
    strategy_cls = _SCANNER_REGISTRY.get(scan_mode.lower())
    if strategy_cls is None:
        raise ValueError(
            f"Unsupported scan_mode {scan_mode!r}. "
            f"Supported modes: {list(_SCANNER_REGISTRY)}"
        )

    resolved_config = config or ScanningConfig()
    resolved_log = log or LogFile()

    core = ScannerCore(
        scan_queue=scan_queue,
        rigctl=rigctl,
        config=resolved_config,
        sleep_fn=sleep_fn,
    )
    strategy = strategy_cls(core)

    return Scanning2(
        scanner=strategy,
        log=resolved_log,
        log_filename=log_filename,
    )

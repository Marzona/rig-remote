"""
Frequency scan strategy.

Sweeps a frequency range from range_min to range_max in steps of interval,
optionally auto-bookmarking active frequencies and recording/logging activity.
"""

import logging

from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.scanner_core import ScannerCore

logger = logging.getLogger(__name__)


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
        logger.info("Stored candidate peak at %d Hz (level %s)", freq, level)

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
    # Inner refinement scan
    # ------------------------------------------------------------------

    def _inner_scan(self, freq_start: int, task: ScanningTask) -> tuple[int, float]:
        """Sweep [freq_start, freq_start + task.inner_band) at task.inner_interval
        steps and return the frequency with the highest signal level.

        The number of samples is task.inner_band // task.inner_interval (integer
        steps that fit before the upper bound, matching the exclusive convention
        of the outer scan loop).

        Tune errors at individual steps are logged and skipped; if every step
        fails the method returns (freq_start, -inf) so the caller can still
        create a bookmark at the trigger frequency.

        :param freq_start: Frequency in Hz where the outer scan detected a
            signal above the threshold — the lower bound of the inner sweep.
        :param task: Active ScanningTask supplying inner_band, inner_interval,
            and frequency_modulation.
        :returns: ``(peak_freq, peak_level)`` — the frequency inside the inner
            band that produced the strongest signal.
        """
        peak_freq: int = freq_start
        peak_level: float = float("-inf")
        freq: int = freq_start
        inner_end: int = freq_start + task.inner_band

        logger.info(
            "Inner scan: [%d, %d) Hz step %d Hz",
            freq_start,
            inner_end,
            task.inner_interval,
        )

        while freq < inner_end:
            try:
                self._core.channel_tune(
                    Channel(modulation=task.frequency_modulation, input_frequency=freq)
                )
            except (OSError, TimeoutError, ValueError):
                logger.warning("Inner scan tune error at %d Hz — skipping step.", freq)
                freq += task.inner_interval
                continue

            level = self._core.rigctl.get_level()
            logger.info("Inner scan: freq=%d Hz  level=%f", freq, level)

            if level > peak_level:
                peak_level = level
                peak_freq = freq

            freq += task.inner_interval

        logger.info(
            "Inner scan complete: peak at %d Hz (level=%f)", peak_freq, peak_level
        )
        return peak_freq, peak_level

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

        while not self._core.should_stop():
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
                        if task.inner_band > 0 and task.inner_interval > 0:
                            peak_freq, _ = self._inner_scan(freq, task)
                            new_bm = self._create_new_bookmark(peak_freq)
                            task.new_bookmarks_list.append(new_bm)
                            logger.info(
                                "Inner scan bookmark at %d Hz", peak_freq
                            )
                        else:
                            self._autobookmark(level=task.sgn_level, freq=freq, task=task)

                    if task.log:
                        new_bm = self._create_new_bookmark(freq)
                        log.write(record_type="F", record=new_bm, signal=[])

                    if not self._core.should_stop():
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

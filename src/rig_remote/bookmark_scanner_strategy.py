"""
Bookmark scan strategy.

Iterates over a pre-built list of Bookmark objects, tuning the rig to each
non-locked entry and performing optional recording, logging and wait loops.
"""

import logging

from rig_remote.disk_io import LogFile
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.scanner_core import ScannerCore

logger = logging.getLogger(__name__)


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

        while not self._core.should_stop():
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
                    if self._core.signal_check(sgn_level=task.sgn_level) and not self._core.should_stop():
                        self._core.process_queue(task)
                    else:
                        break

                if not self._core.should_stop():
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

"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation


Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2106 Tim Sweeney

TAS - Tim Sweeney - mainetim@gmail.com
"""

import logging

import socket
import time
from rig_remote.bookmarksmanager import bookmark_factory
from rig_remote.models.channel import Channel
from rig_remote.rigctl import RigCtl
from rig_remote.disk_io import LogFile
from rig_remote.stmessenger import STMessenger
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.utility import (
    khertz_to_hertz,
)

logger = logging.getLogger(__name__)


class Scanning:
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    _VALID_SCAN_UPDATE_EVENT_NAMES = [
        "ckb_wait",
        "ckb_record",
        "txt_range_max",
        "txt_range_min",
        "txt_sgn_level",
        "txt_passes",
        "txt_interval",
        "txt_delay",
    ]
    # once we send the cmd for tuning a freq, wait this time
    _TIME_WAIT_FOR_TUNE = 0.25
    # once tuned a freq, check this number of times for a signal
    _SIGNAL_CHECKS = 2
    # time to wait between checks on the same frequency
    _NO_SIGNAL_DELAY = 0.2

    def __init__(
        self,
        scan_queue: STMessenger,
        log_filename: str,
        rigctl: RigCtl,
        log: LogFile = LogFile(),
    ):
        self._scan_active = True
        self._log_filename = log_filename
        self._rigctl = rigctl
        self._prev_level = None
        self._prev_freq = None
        self._scan_queue = scan_queue
        self._hold_bookmark = False
        self._log = log

    def terminate(self):
        logger.info("Terminating scan.")
        self._scan_active = False

    def _queue_sleep(self, task: ScanningTask):
        """check the queue regularly during 'sleep'

        :param task: current scanning task

        """

        length = task.delay
        while True:
            if self._scan_queue.update_queued():
                self._process_queue(task)
            if length > 0:
                time.sleep(1)
                length -= 1
            else:
                break

    def scan(self, task: ScanningTask):
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.scan_mode value

        :param task: object that represent a scanning task
        :returns: updates the scanning task object with the new activity found
        """

        if task.log:
            logger.info("Enabling scan log.")
            try:
                self._log.open(self._log_filename)
            except IOError:
                logger.exception("Error while opening the log file.")
                raise
        logger.info("starting scan task with scan mode %s", task.scan_mode)
        if task.scan_mode.lower() == "bookmarks":  # TODO replace with call map
            _ = self._bookmarks(task)
        elif task.scan_mode.lower() == "frequency":
            _ = self._frequency(task)
        self._log.close()

    def _channel_tune(self, channel: Channel):
        """helper function called inside _frequency().
        This is for reducing the code inside the while true loops
        """

        logger.info("Tuning to %i", channel.frequency)
        try:
            self._rigctl.set_frequency(channel.frequency)
        except ValueError:
            logger.error("Bad frequency parameter passed.")
            raise
        except (socket.error, socket.timeout):
            logger.error("Communications Error!")
            self.scan_active = False
            raise
        time.sleep(self._TIME_WAIT_FOR_TUNE)

        try:
            self._rigctl.set_mode(channel.modulation)
        except ValueError:
            logger.error("Bad modulation parameter passed.")
            raise
        except (socket.error, socket.timeout):
            logger.error("Communications Error!")
            self.scan_active = False
            raise
        time.sleep(self._TIME_WAIT_FOR_TUNE)

    def _bookmarks(self, task: ScanningTask) -> ScanningTask:
        """Performs a bookmark scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()
        For every bookmark we tune the frequency and we call _signal_check

        :param task: object that represent a scanning task
        :raises Exception: if there is a communication error with the rig.
        :returns: updates the scanning task object with the new activity found
        """

        pass_count = task.passes
        # old_pass_count = pass_count = task.passes
        logger.info("Starting bookmark scan")
        while self._scan_active:
            for bookmark in task.bookmarks:
                logger.info("tuning bookmark %s with id ", bookmark, bookmark.id)
                if self._process_queue(task):
                    # the ui allows some params to be changed during the scan.
                    pass_count = task.passes
                if bookmark.lockout == "L":
                    logger.info(
                        "bookmark with id %s is locked, skipping this bookmark in the scan.",
                        bookmark.id,
                    )
                    continue
                try:
                    self._channel_tune(bookmark.channel)
                except (socket.error, socket.timeout):
                    logger.error(
                        "unable to tune bookmark %s exiting scanning loop.", bookmark.id
                    )
                    break

                if task.record:
                    self._rigctl.start_recording()
                    logger.info("Recording started.")
                if self._signal_check(sgn_level=task.sgn_level, rig=self._rigctl):
                    logger.info(
                        "This freq is bookmarked as: %s and we found signal again.",
                        bookmark.id,
                    )

                if task.log:
                    self._log.write(record_type="B", record=bookmark, signal=[])
                    logger.info("logging for bookmark %s", bookmark.id)

                while task.wait:
                    if (
                        self._signal_check(sgn_level=task.sgn_level, rig=self._rigctl)
                        and self._scan_active
                    ):
                        self._process_queue(task)
                    else:
                        logger.info(
                            "scanning not active or no signal level, exiting wait loop"
                        )
                        break

                if self._scan_active:
                    logger.info("enqueueing a sleep item...")
                    self._queue_sleep(task)

                if task.record:
                    self._rigctl.stop_recording()
                    logger.info("Recording stopped.")

                if not self._scan_active:
                    logger.info("Scanning stopped, exiting scanning loop.")
                    return task
            pass_count = self._pass_count_update(pass_count=pass_count)
        self._scan_queue.notify_end_of_scan()
        return task

    def _frequency(self, task):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :returns: updates the scanning task object with the new activity found
        """
        level = []

        pass_count = task.passes
        logger.info("Starting frequency scan")
        while self._scan_active:
            logger.info("scan pass %i with interval %i", pass_count, task.interval)
            freq = task.range_min
            if freq > task.range_max:
                logger.error("Frequency beyond than max, stopping scan")
                self.terminate()
            while freq < task.range_max:
                if not self._scan_active:
                    return task
                if self._process_queue(task):
                    # the ui allows some params to be changed during the scan.
                    pass_count = task.passes
                try:
                    self._channel_tune(
                        channel=Channel(
                            modulation=task.frequency_modulation, input_frequency=freq
                        )
                    )
                except (socket.error, socket.timeout):
                    logger.error(
                        "error tuning frequency %s and mode %s",
                        freq,
                        task.frequency_modulation,
                    )
                    break
                if self._signal_check(sgn_level=task.sgn_level, rig=self._rigctl):
                    if task.record:
                        self._rigctl.start_recording()
                        logger.info("Recording started.")
                    if task.auto_bookmark:
                        self._autobookmark(level=level, freq=freq, task=task)
                    if task.log:
                        nbm = self._create_new_bookmark(freq)
                        self._log.write(record_type="F", record=nbm, signal=[])

                    if self._scan_active:
                        self._queue_sleep(task)
                    if task.record:
                        self._rigctl.stop_recording()
                        logger.info("Recording stopped.")
                elif self._hold_bookmark:
                    nbm = self._create_new_bookmark(self._prev_freq)
                    logger.info("adding new bookmark to list")
                    task.new_bookmark_list.append(nbm)
                    self._store_prev_bookmark(False, None)
                freq = freq + task.interval
            pass_count = self._pass_count_update(pass_count=pass_count)
        self._scan_queue.notify_end_of_scan()
        return task

    def _create_new_bookmark(self, freq: int):
        bookmark = bookmark_factory(
            input_frequency=freq,
            modulation=self._rigctl.get_mode(),
            description="auto added by scan",
            lockout="",
        )
        logger.info("New bookmark created %s", bookmark)
        return bookmark

    def _erase_prev_bookmark(self):
        self._prev_level = None
        self._prev_freq = None

    def _store_prev_bookmark(self, level: int, freq: int):
        self._prev_level = level
        self._prev_freq = freq
        self._hold_bookmark = True

    def _autobookmark(self, level: int, freq: int, task: ScanningTask):
        if not self._prev_level:
            self._store_prev_bookmark(level=level, freq=freq)
            return
        if level <= self._prev_level:
            nbm = self._create_new_bookmark(self._prev_freq)
            logger.info("adding new bookmark to list")
            task.new_bookmark_list.append(nbm)
            self._erase_prev_bookmark()
        else:
            self._store_prev_bookmark(True, level)

    def _pass_count_update(self, pass_count: int) -> int:
        if pass_count > 0:
            pass_count -= 1
        if pass_count == 0:
            logger.info("max passes reached, set scan status to inactive.")
            self._scan_active = False
        return pass_count

    @staticmethod
    def _dbfs_to_sgn(value: int):
        return int(value) * 10

    def _signal_check(self, sgn_level: int, rig: RigCtl) -> bool:
        """check for the signal self._SIGNAL_CHECKS times pausing
        self._NO_SIGNAL_DELAY between checks.

        :param sgn_level: minimum signal level we are searching
        :returns true/false: signal found, signal not found
        :return type: boolean
        """
        sgn = self._dbfs_to_sgn(sgn_level)
        signal_found = 0
        level = 0

        for i in range(0, self._SIGNAL_CHECKS):
            logger.info("Signal checks left:{}".format(self._SIGNAL_CHECKS - i))
            level = rig.get_level()
            logger.info(
                "detected signal level sgn_level:%f, dbfs signal level %f", level, sgn
            )
            if level >= sgn:
                logger.info("Signal found")
                signal_found += 1
            time.sleep(self._NO_SIGNAL_DELAY)
        if signal_found > 0:
            logger.info(
                "Activity found, signal level: %i %i checks out of %i",
                level,
                signal_found,
                self._SIGNAL_CHECKS,
            )
            return True
        return False

    def _process_queue(self, task: ScanningTask):
        """Process the scan thread queue, updating parameter values
           from the UI while the scan is progressing. Checks to make sure the event is a valid one,
           else it's logged and dropped.

        :param: task: current task object
        :returns: True if an update was processed,
                  False if no update was found.
        """
        logger.info("checking for scaning update events")
        processed_something = False
        while self._scan_queue.update_queued():
            param_name, param_value = self._scan_queue.get_event_update()
            if param_name not in self._VALID_SCAN_UPDATE_EVENT_NAMES:
                logger.warning(
                    "Retrieved a non supported scan update event %s supported events are %s.",
                    param_name,
                    self._VALID_SCAN_UPDATE_EVENT_NAMES,
                )
                break
            logger.info(
                "Retrieved scan update event : param name %s, param value %s",
                param_name,
                param_value,
            )
            try:
                key = str(
                    param_name.split("_", 1)[1]
                )  # the UI passes txt_range_min while the attrib is range_min
                if key == "range_min":
                    task.range_min = khertz_to_hertz(param_value)
                elif key == "range_max":
                    task.range_max = khertz_to_hertz(param_value)
                else:
                    setattr(task, key, param_value)

            except Exception as e:
                logger.warning("Processing event update failed with {}".format(e))
                logger.warning("Event list: %s %s", param_name, param_value)
                break
            processed_something = True
            logger.info("Queue passed %s %i", param_name, param_value)
        return processed_something

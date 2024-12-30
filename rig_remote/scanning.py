#!/usr/bin/env python
"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2106 Tim Sweeney

TAS - Tim Sweeney - mainetim@gmail.com

2016/02/16 - TAS - Added code to support continuous bookmark scanning.
                   scan method modified to support threading.
2016/02/18 - TAS - Changed code from "monitor mode" fixed looping to
                   choice of variable or infinite looping.
                   Only done in bookmark scanning, still need to rework
                   frequency scanning to match. Also need to implement
                   changes in delay code (to allow for wait on signal).
2016/02/19 - TAS - Fixed code for frequency scan to support threading.
2016/02/20 - TAS - Recoded signal_check to help prevent false positives.
                   Implemented "wait for signal" style pause in bookmark
                   scanning. Selectable via the "wait" checkbox. When
                   on, scanning will pause on signal detection until
                   the frequency has been been clear for "Delay" seconds.
                   When off, scanning will resume after "Delay" seconds no
                   matter if a signal is still present or not.
2016/02/21 - TAS - Added error handling for initial rig_control call.
2016/02/24 - TAS - Added bookmark lockout support. Changed how bookmarks
                   are passed so that on-the-fly lockout will work. Added
                   logging activity to file.
2016/03/11 - TAS - Added skeleton code to process queue.
                   Still to do: change parameter passing to dict.
2016/03/13 - TAS - Strip the scan parameters strings completely of
                   non-numerics to avoid ValueExceptions.
2016/03/15 - TAS - Recoded to pass most parameters in a dict, which also stores
                   local int versions. TODO: Flesh out queue-based value changes.
2016/03/16 - TAS - Added code to allow parameter updating while scan is active.
2016/04/12 - TAS - Auto-bookmarking option restored on frequency scans. Proper time and mode
                   now recorded. New bookmarks are held in a list of dicts and processed by
                   the main thread once this thread has completed.
2016/04/24 - TAS - Changed thread communications to use STMessenger class in support of resolving
                   Issue #30. GUI interaction removed.
2106/04/27 - TAS - Rewrote bookmark scanning to streamline logic (slightly), and include additional
                   opportunities for queue processing. Added _queue_sleep method for queue processing
                   while pausing. Related to Issue #43.
2016/05/30 - TAS - Small fixes and modify _create_new_bookmark for multiple uses.
"""

import logging

import socket
import time
from rig_remote.bookmarksmanager import bookmark_factory
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

    # once we send the cmd for tuning a freq, wait this time
    _TIME_WAIT_FOR_TUNE = 0.25
    # once tuned a freq, check this number of times for a signal
    _SIGNAL_CHECKS = 2
    # time to wait between checks on the same frequency
    _NO_SIGNAL_DELAY = 0.1

    def __init__(self, scan_queue: STMessenger, log_filename: str, rigctl: RigCtl):
        self._scan_active = True
        self._log_filename = log_filename
        self._rigctl = rigctl
        self.prev_level = None
        self.prev_freq = None
        self._scan_queue = scan_queue
        self.hold_bookmark = False

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
        :type task: object from ScanningTask

        :returns: updates the scanning task object with the new activity found
        """

        log = LogFile()
        try:
            log.open(self._log_filename)
        except IOError:
            logger.exception("Error while opening the log file.")
            raise
        logger.info("starting scan task with scan mode %s", task.scan_mode)
        if task.scan_mode.lower() == "bookmarks":
            _ = self._bookmarks(task, log)
        elif task.scan_mode.lower() == "frequency":
            _ = self._frequency(task, log)
        log.close()

    def _frequency_tune(self, freq: int):
        """helper function called inside _frequency().
        This is for reducing the code inside the while true loops
        """

        logger.info("Tuning to %i", freq)
        try:
            self._rigctl.set_frequency(freq)
        except ValueError:
            logger.error("Bad frequency parameter passed.")
            raise
        except (socket.error, socket.timeout):
            logger.error("Communications Error!")
            self.scan_active = False
            raise
        time.sleep(self._TIME_WAIT_FOR_TUNE)

    def _create_new_bookmark(self, freq: int):
        bookmark = bookmark_factory(
            input_frequency=freq,
            modulation=self._rigctl.get_mode(),
            description="auto added by scan",
            lockout="",
        )
        logger.info("nuew bookmkar created %s", bookmark)
        return bookmark

    def _frequency(self, task, log):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask

        :returns: updates the scanning task object with the new activity found
        """
        self._rigctl.set_mode(task.frequency_modulation)
        level = []

        pass_count = task.passes
        logger.info("Starting frequency scan")
        while self._scan_active:
            logger.info("scan pass %i with interval %i", pass_count, task.interval)
            freq = task.range_min
            # If the range is negative, silently bail...
            if freq > task.range_max:
                logger.info("Frequency beyond than max, stopping scan")
                self.terminate()
            while freq < task.range_max:
                if self._process_queue(task):
                    try:
                        self._frequency_tune(freq)
                    except (socket.error, socket.timeout):
                        break
                if self._signal_check(task.sgn_level, self._rigctl, level):
                    if task.record:
                        self._rigctl.start_recording()
                        logger.info("Recording started.")

                    if task.auto_bookmark:
                        self._autobookmark(level, task, freq)
                    if task.log:
                        nbm = self._create_new_bookmark(freq)
                        log.write("F", nbm, level[0])

                    if self._scan_active:
                        self._queue_sleep(task)
                    if task.record:
                        self._rigctl.stop_recording()
                        logger.info("Recording stopped.")
                elif self.hold_bookmark:
                    nbm = self._create_new_bookmark(self.prev_freq)
                    logger.info("adding new bookmark to list")
                    task.new_bookmark_list.append(nbm)
                    self._prev_bookmark(False, None, None)
                freq = freq + task.interval
                if not self._scan_active:
                    return task
            pass_count, task = self._pass_count_update(pass_count, task)
        self._scan_queue.notify_end_of_scan()
        return task

    def _prev_bookmark(self, level, freq):
        self.prev_level = level
        self.prev_freq = freq
        self.hold_bookmark = True

    def _autobookmark(self, level, task, freq):
        if not self.prev_level:
            self._prev_bookmark(True, level, freq)
            return
        if level[0] < self.prev_level[0]:
            nbm = self._create_new_bookmark(self.prev_freq)
            logger.info("adding new bookmark to list")
            task.new_bookmark_list.append(nbm)
            self._prev_bookmark(False, None, None)
        else:
            self._prev_bookmark(True, level, freq)

    def _pass_count_update(self, pass_count, task):
        if pass_count > 0:
            pass_count -= 1
            if pass_count == 0 and task.passes > 0:
                logger.info("max passes reached.")
                self._scan_active = False
        return pass_count, task

    @staticmethod
    def _dbfs_to_sgn(value: int):
        return int(value) * 10

    def _signal_check(self, sgn_level: int, rig: RigCtl, detected_level: list):
        """check for the signal self._SIGNAL_CHECKS times pausing
        self._NO_SIGNAL_DELAY between checks. Puts signal level in
        list to hand back to caller for logging.

        :param sgn_level: minimum signal level we are searching
        :type sgn_level: string from the UI setting
        :returns true/false: signal found, signal not found
        :return type: boolean
        """
        del detected_level[:]
        sgn = self._dbfs_to_sgn(sgn_level)
        signal_found = 0
        level = 0

        for i in range(0, self._SIGNAL_CHECKS):
            logger.info("Checks left:{}".format(self._SIGNAL_CHECKS - i))
            level = int(rig.get_level())
            logger.info(
                "detected signal level sgn_level:%f, dbfs signal level %f", level, sgn
            )
            if level > sgn:
                logger.info("Signal found")
                signal_found += 1
            time.sleep(self._NO_SIGNAL_DELAY)
        if signal_found > 1:
            logger.info("Activity found, signal level: " "{}".format(level))
            detected_level.append(level)
            return True
        return False

    def _bookmarks(self, task: ScanningTask, log) -> ScanningTask:
        """Performs a bookmark scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()
        For every bookmark we tune the frequency and we call _signal_check

        :param task: object that represent a scanning task
        :raises Exception: if there is a communication error with the rig.
        :returns: updates the scanning task object with the new activity found
        """

        level = []
        old_pass_count = pass_count = task.passes
        logger.info("Starting bookmark scan")
        while self._scan_active:
            for bookmark in task.bookmarks:
                logger.info("tuning bookmark %s with id ", bookmark, bookmark.id)
                self._process_queue(task)
                if old_pass_count != task.passes:
                    old_pass_count = pass_count = task.passes
                if bookmark.lockout == "L":
                    continue
                try:
                    self._frequency_tune(bookmark.channel.frequency)
                except (socket.error, socket.timeout):
                    break

                if self._signal_check(task.sgn_level, self._rigctl, level):
                    logger.info(
                        "This freq is bookmarked as: %s", bookmark.channel.frequency
                    )

                    if task.record:
                        self._rigctl.start_rezcording()
                        logger.info("Recording started.")

                    if task.log:
                        log.write("B", bookmark, level[0])

                    while task.wait:
                        if (
                            self._signal_check(task.sgn_level, self._rigctl, level)
                            and self._scan_active
                        ):
                            self._process_queue(task)
                        else:
                            break

                    if self._scan_active:
                        self._queue_sleep(task)

                    if task.record:
                        self._rigctl.stop_recording()
                        logger.info("Recording stopped.")

                if not self._scan_active:
                    return task
            pass_count, task = self._pass_count_update(pass_count, task)
        self._scan_queue.notify_end_of_scan()
        return task

    def _process_queue(self, task: ScanningTask):
        """Process the scan thread queue, updating parameter values
           from the UI. Checks to make sure the event is a valid one,
           else it's logged and dropped.

        :param: task: current task object
        :returns: True if an update was processed,
                  False if no update was found.
        """

        processed_something = False
        while self._scan_queue.update_queued():
            name, value = self._scan_queue.get_event_update()
            if not name or not value:
                logger.warning("Event update attempt returned None.")
                break
            try:
                key = str(name.split("_", 1)[1])
                if key in task.params:
                    if key in ("range_min", "range_max"):
                        task.params[key] = khertz_to_hertz(value)
                    else:
                        task.params[key] = value
                else:
                    logger.warning("Invalid key in event update: {}".format(key))
                    break
            except Exception as e:
                logger.warning("Processing event update failed with {}".format(e))
                logger.warning("Event list: {} {}".format(name, value))
                break
            processed_something = True
            logger.info("Queue passed %s %i", name, value)
            logger.info("Params[%s] = %s", key, task.params[key])
        return processed_something

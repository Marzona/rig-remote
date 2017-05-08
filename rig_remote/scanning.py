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

# import modules

import datetime
from rig_remote.rigctl import RigCtl
from rig_remote.disk_io import LogFile
from rig_remote.constants import SUPPORTED_SCANNING_MODES
from rig_remote.constants import TIME_WAIT_FOR_TUNE
from rig_remote.constants import SIGNAL_CHECKS
from rig_remote.constants import NO_SIGNAL_DELAY
from rig_remote.constants import MIN_INTERVAL
from rig_remote.constants import MONITOR_MODE_DELAY
from rig_remote.constants import BM
from rig_remote.exceptions import UnsupportedScanningConfigError, InvalidScanModeError
from rig_remote.stmessenger import STMessenger
from rig_remote.utility import(
                             khertz_to_hertz,
                             dbfs_to_sgn,
                             build_rig_uri,
                            )
import socket
import logging
import time
import re

# logging configuration
logger = logging.getLogger(__name__)

# class definition

class ScanningTask(object):
    """Representation of a scan task, with helper method for checking
    for proper frequency range.

    """

    def __init__(self,
                 scanq,
                 mode,
                 bookmarks,
                 nbl,
                 pass_params,
                 rig_controller,
                 log_filename):
        """We do some checks to see if we are good to go with the scan.

        :param scanq: queue used send/receive events from the UI.
        :type scanq: Queue object
        :param pass_params: configuration parameters
        :type pass_params: standard python dictionary
        :param mode: scanning mode, either bookmark or frequency
        :type mode: string
        :param bookmark: the actual list of bookmarks, may be empty
        :type bookmark: list of tuples, every tuple is a bookmark
        :raises: UnsupportedScanningConfigError if action or mode are not
        allowed
        :raises: ValueError if the pass_params dictionary contains invalid data
        :returns: none
        """

        self.error = None
        self.new_bookmark_list = nbl
        self.bookmarks = bookmarks
        self.scanq = scanq
        self.log_filename = log_filename

        if mode.lower() not in SUPPORTED_SCANNING_MODES:
            logger.error("Unsupported scanning mode "\
                          "provided, exiting.")
            logger.error("Provided mode:{}".format(mode))
            logger.error("Supported modes:{}".format(SUPPORTED_SCANNING_MODES))
            raise UnsupportedScanningConfigError

        self.mode = mode
        self.params = pass_params
        self.rig = rig_controller

        try:
            self.params["range_min"] = \
                            khertz_to_hertz(int(filter(str.isdigit,
                                                       self.params["txt_range_min"].get())))
            self.params["range_max"] = \
                            khertz_to_hertz(int(filter(str.isdigit,
                                                       self.params["txt_range_max"].get())))
            self.params["interval"] = int(filter(str.isdigit,
                                                 self.params["txt_interval"].get()))
            self.params["delay"] = int(filter(str.isdigit,
                                              self.params["txt_delay"].get()))
            self.params["passes"] = int(filter(str.isdigit,
                                               self.params["txt_passes"].get()))
            self.params["sgn_level"] = int(re.sub("[^-0-9]",
                                                  "",
                                                  self.params["txt_sgn_level"].get()))
            self.params["log"] = self.params["ckb_log"].is_checked()
            self.params["wait"] = self.params["ckb_wait"].is_checked()
            self.params["record"] = self.params["ckb_record"].is_checked()
            self.params["auto_bookmark"] = self.params["ckb_auto_bookmark"].is_checked()

        except ValueError:
            """We log some info and re raise."""
            logger.exception("One input values is not of the proper type.")
            logger.exception("range_max:{}".format(self.params["txt_range_max"]))
            logger.exception("range_min:{}".format(self.params["txt_range_min"]))
            logger.exception("interval:{}".format(self.params["txt_interval"]))
            logger.exception("delay:{}".format(self.params["txt_delay"]))
            logger.exception("passes:{}".format(self.params["txt_passes"]))
            logger.exception("sgn_level:{}".format(self.params["txt_sgn_level"]))
            raise

        if mode == "frequency":
            self._check_interval()

    def _check_interval(self):
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than MIN_INTERVAL, if there is such a low interval
        we overwrite and log an error.
        """

        if khertz_to_hertz(self.params["interval"]) < MIN_INTERVAL:
            logger.error("Low interval provided:{}".format(self.params["interval"]))
            logger.error("Overriding with {}".format(MIN_INTERVAL))
            self.params["interval"] = MIN_INTERVAL


class Scanning(object):
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    def __init__(self):
        self.scan_active = True
        self.prev_level = None
        self.prev_freq = None
        self.hold_bookmark = False

    def terminate(self):
        self.scan_active = False

    def _queue_sleep(self, task):
        """check the queue regularly during 'sleep'

        :param task: current scanning task
        :type Scanningtask object
        :returns: None
        """

        length = task.params["delay"]
        if not isinstance(length, int):
            logger.error("delay is not an int: {}".format(type(task.params["delay"])))
            raise ValueError

        while True:
            if task.scanq.update_queued():
                self._process_queue(task)
            if length > 0:
                time.sleep(1)
                length -= 1
            else: break

    def scan(self, task):
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        if (not task or
            not task.mode or
            task.mode.lower() not in SUPPORTED_SCANNING_MODES):
            logger.exception("Invalid scan mode provided:{}".format(task.mode))
            raise InvalidScanModeError

        log = LogFile()
        log.open(task.log_filename)
        if task.mode.lower() == "bookmarks":
            task = self._bookmarks(task, log)
        elif task.mode.lower() == "frequency":
            task = self._frequency(task, log)
        log.close()

    def _frequency_tune(self, task, freq):
        """helper function called inside _frequency().
        This is for reducing the code inside the while true loops
        """

        logger.info("Tuning to {}".format(freq))
        try:
            task.rig.set_frequency(freq)
        except ValueError:
            logger.warning ("Bad frequency parameter passed.")
            raise
        except (socket.error, socket.timeout):
            logger.warning("Communications Error!")
            self.scan_active = False
            raise
        time.sleep(TIME_WAIT_FOR_TUNE)

    def _create_new_bookmark(self, task, freq):
        nbm = {}
        nbm["freq"] = freq
        nbm["mode"] = task.rig.get_mode()
        nbm["time"] = datetime.datetime.utcnow().strftime("%a %b %d %H:%M %Y")
        return nbm

    def _start_recording(self):
        task.rig.start_recording()
        logger.info("Recording started.")

    def _stop_recording(self):
        task.rig.stop_recording()
        logger.info("Recording stopped.")

    def _get_task_items(self, task):
        freq = task.params["range_min"]
        pass_count = task.params["passes"]
        interval = khertz_to_hertz(task.params["interval"])
        return freq, pass_count, interval

    def _frequency(self, task, log):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        mode = task.params["cbb_scan_mode"].get()
        task.rig.set_mode(mode )

        level = []

        pass_count = task.params["passes"]
        interval = khertz_to_hertz(task.params["interval"])
        while self.scan_active:
            freq = task.params["range_min"]
            # If the range is negative, silently bail...
            if freq > task.params["range_max"]:
                self.scan_active = False
            while freq < task.params["range_max"]:
                if self._process_queue(task):
                    freq, pass_count, interval = self._get_task_items(task)
                try:
                    self._frequency_tune(task, freq)
                except (socket.error, socket.timeout):
                    break

                if self._signal_check(task.params["sgn_level"],
                                      task.rig,
                                      level):

                    if task.params["record"]:
                        self._start_recording()

                    if task.params["auto_bookmark"]:
                        self._autobookmark(level, task, freq)

                    if task.params["log"]:
                        nbm = self._create_new_bookmark(task, freq)
                        log.write('F', nbm, level[0])

                    if self.scan_active:
                        self._queue_sleep(task)

                    if task.params["record"]:
                        self._stop_recording()
                elif self.hold_bookmark:
                    nbm = self._create_new_bookmark(task, self.prev_freq)
                    task.new_bookmark_list.append(nbm)
                    self._prev_bookmark(False, None, None)
                freq = freq + interval
                if not self.scan_active:
                    return task
            pass_count, task = self._pass_count_update(pass_count, task)
        task.scanq.notify_end_of_scan()
        return task

    def _prev_bookmark(self, hold, level, freq):
        logger.error("dati{},{},{}".format(hold, level, freq))
        self.prev_level = level
        self.prev_freq = freq
        self.hold_bookmark = True

    def _autobookmark(self, level, task, freq):
        if not self.prev_level:
            self._prev_bookmark(True, level, freq)
            return
        if level[0] < self.prev_level[0]:
            nbm = self._create_new_bookmark(task, self.prev_freq)
            task.new_bookmark_list.append(nbm)
            self._prev_bookmark(False, None, None)
        else:
            self._prev_bookmark(True, level, freq)

    def _pass_count_update(self, pass_count, task):
        if pass_count > 0:
            pass_count -= 1
            if pass_count == 0 and task.params["passes"] > 0:
                self.scan_active = False
        return pass_count, task

    def _signal_check(self, sgn_level, rig, detected_level):
        """check for the signal SIGNAL_CHECKS times pausing
        NO_SIGNAL_DELAY between checks. Puts signal level in
        list to hand back to caller for logging.

        :param sgn_level: minimum signal level we are searching
        :type sgn_level: string from the UI setting
        :returns true/false: signal found, signal not found
        :return type: boolean
        """

        del detected_level[:]
        sgn = dbfs_to_sgn(sgn_level)
        signal_found = 0

        for i in range(0, SIGNAL_CHECKS):
            logger.info("Checks left:{}".format(SIGNAL_CHECKS -i))
            level = int(rig.get_level().replace(".", ""))
            logger.info("sgn_level:{}".format(level))
            logger.info("dbfs_sgn:{}".format(sgn))
            if level > sgn:
                signal_found += 1
            time.sleep(NO_SIGNAL_DELAY)
        if signal_found > 1:
            logger.info("Activity found, signal level: "\
                        "{}".format(level))
            detected_level.append(level)
            return True
        return False

    def _bookmarks(self, task, log):
        """Performs a bookmark scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()
        For every bookmark we tune the frequency and we call _signal_check

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises Exception: if there is a communication error with the rig.
        :returns: updates the scanning task object with the new activity found
        """

        level = []
        old_pass_count = pass_count = task.params['passes']
        while self.scan_active:
            for item in task.bookmarks.get_children():
                self._process_queue(task)
                if old_pass_count != task.params['passes']:
                    old_pass_count = pass_count = task.params['passes']
                bookmark = task.bookmarks.item(item).get('values')
                if (bookmark[BM.lockout]) == 'L':
                    continue
                freq = bookmark[BM.freq].replace(',', '')
                try:
                    self._frequency_tune(task, freq)
                except (socket.error, socket.timeout):
                    break

                if self._signal_check(task.params['sgn_level'],
                                      task.rig,
                                      level):
                    logger.info(
                        "This freq is bookmarked as: {}".format(bookmark[BM.freq]))

                    if task.params['record']:
                        self._start_recording()

                    if task.params['log']:
                        log.write('B', bookmark, level[0])

                    while task.params['wait']:
                        if self._signal_check(task.params['sgn_level'],
                                              task.rig,
                                              level) and self.scan_active:
                            self._process_queue(task)
                        else: break

                    if self.scan_active:
                        self._queue_sleep(task)

                    if task.params['record']:
                        self._stop_recording()

                if not self.scan_active:
                    return task
            pass_count, task = self._pass_count_update(pass_count, task)
        task.scanq.notify_end_of_scan()
        return task

    def _process_queue(self, task):
        """Process the scan thread queue, updating parameter values
           from the UI. Checks to make sure the event is a valid one,
           else it's logged and dropped.

        :param: task: current task object
        :type: ScanningTask object
        :returns: True if an update was processed,
                  False if no update was found.
        """

        processed_something = False
        while task.scanq.update_queued():
            name, value = task.scanq.get_event_update()
            if not name or not value:
                logger.warning("Event update attempt returned None.")
                break
            try:
                key = str(name.split("_", 1)[1])
                if key in task.params:
                    if key in ('range_min', 'range_max'):
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

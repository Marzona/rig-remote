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

2016/04/29 - TAS - Changed thread communications to use STMessenger class in support of resolving
                   Issue #30. GUI interaction removed.
"""

# import modules

import datetime
from modules.rigctl import RigCtl
from modules.disk_io import Log_file
from modules.constants import SUPPORTED_SCANNING_MODES
from modules.constants import TIME_WAIT_FOR_TUNE
from modules.constants import SIGNAL_CHECKS
from modules.constants import NO_SIGNAL_DELAY
from modules.constants import MIN_INTERVAL
from modules.constants import MONITOR_MODE_DELAY
from modules.constants import BM
from modules.exceptions import UnsupportedScanningConfigError
from modules.stmessenger import STMessenger
import logging
import time
import re

# logging configuration
logger = logging.getLogger(__name__)

# helper functions

def khertz_to_hertz(value):
    return value*1000

def dbfs_to_sgn(value):
    return value*10

class ScanningTask(object):
    """Representation of a scan task, with helper method for checking
    for proper frequency range.

    """

    def __init__(self,
                 scanq,
                 mode,
                 bookmarks,
                 nbl,
                 pass_params):
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

        if mode.lower() not in SUPPORTED_SCANNING_MODES:
            logger.error("Unsupported scanning mode "\
                          "provided, exiting.")
            logger.error("Provided mode:{}".format(mode))
            logger.error("Supported modes:{}".format(SUPPORTED_SCANNING_MODES))
            raise UnsupportedScanningConfigError

        self.mode = mode
        self.params = pass_params

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
        we overwrite and log a warning.
        """

        if khertz_to_hertz(self.params["interval"]) < MIN_INTERVAL:
            logger.info("Low interval provided:{}".format(self.params["interval"]))
            logger.info("Overriding with {}".format(MIN_INTERVAL))
            self.params["interval"] = MIN_INTERVAL


class Scanning(object):
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    def __init__(self):
        self.scan_active = True

    def terminate(self):
        self.scan_active = False

    def scan(self, task):
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        rigctl = RigCtl()
        log = Log_file()
        log.open()
        if task and task.mode.lower() == "bookmarks":
            task = self._bookmarks(task, rigctl, log)
        elif task and task.mode.lower() == "frequency":
            task = self._frequency(task, rigctl, log)
        log.close()

    def _frequency(self, task, rigctl, log):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """
        level = []
        pass_count = task.params["passes"]
        while self.scan_active:
            freq = task.params["range_min"]
            # If the range is negative, silently bail...
            if freq > task.params["range_max"]:
                self.scan_active = False
            interval = khertz_to_hertz(task.params["interval"])
            while freq < task.params["range_max"]:
                if task.scanq.update_queued():
                    self.process_queue(task)
                    freq = task.params["range_min"]
                    pass_count = task.params["passes"]
                    interval = khertz_to_hertz(task.params["interval"])
                logger.info("Tuning to {}".format(freq))
                logger.info("Interval:{}".format(task.params["interval"]))
                try:
                    rigctl.set_frequency(freq)
                except Exception:
                    logger.warning("Communications Error!")
                    self.scan_active = False
                    break
                time.sleep(TIME_WAIT_FOR_TUNE)

                if self._signal_check(task.params["sgn_level"], rigctl, level):
                    logger.info("Activity found on freq: {}".format(freq))
                    if task.params["record"]:
                        rigctl.start_recording()
                        logger.info("Recording started.")
                    if task.params["auto_bookmark"]:
                        nbm = {}
                        nbm["freq"] = freq
                        nbm["mode"] = rigctl.get_mode()
                        nbm["time"] = datetime.datetime.utcnow().strftime("%a %b %d %H:%M %Y")
                    task.new_bookmark_list.append(nbm)
                    if task.params["log"]:
                        log.write('F', nbm, level[0])
                    if self.scan_active:
                        time.sleep(task.params["delay"])
                    if task.params["record"]:
                        rigctl.stop_recording()
                        logger.info("Recording stopped.")
                freq = freq + interval
                if not self.scan_active:
                    return task
            if pass_count > 0:
                pass_count -= 1
                if pass_count == 0 and task.params["passes"] > 0:
                    self.scan_active = False
                else:
                    time.sleep(MONITOR_MODE_DELAY)
        task.scanq.notify_end_of_scan()
        return task

    def _signal_check(self, sgn_level, rigctl, detected_level):
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
            logging.info("Checks left:{}".format(SIGNAL_CHECKS -i))
            level = int(rigctl.get_level().replace(".", ""))
            logger.info("sgn_level:{}".format(level))
            logger.info("dbfs_sgn:{}".format(sgn))
            if level > sgn:
                signal_found += 1
            time.sleep(NO_SIGNAL_DELAY)
        logger.info("signal_found:{}".format(signal_found))
        if signal_found > 1:
            detected_level.append(level)
            return True
        return False

    def _bookmarks(self, task, rigctl, log):
        """Performs a bookmark scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()
        For every bookmark we tune the frequency and we call _signal_check

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises Exception: if there is a communication error with the rig.
        :returns: updates the scanning task object with the new activity found
        """

        level = []
        pass_count = task.params["passes"]
        while self.scan_active:
            if task.scanq.update_queued():
                self.process_queue(task)
                pass_count = task.params["passes"]
            for item in task.bookmarks.get_children():
                bookmark = task.bookmarks.item(item).get('values')
                if (bookmark[BM.lockout]) == "L":
                    continue
                logger.info("Tuning to {}".format(bookmark[BM.freq]))
                try:
                    rigctl.set_frequency(bookmark[BM.freq].replace(',', ''))
                except Exception:
                    logger.warning("Communications Error!")
                    self.scan_active = False
                    break
                time.sleep(TIME_WAIT_FOR_TUNE)
                if self._signal_check(task.params["sgn_level"], rigctl, level):
                    logger.info(
                        "Activity found on freq: {}".format(bookmark[BM.freq]))
                    if task.params["record"]:
                        rigctl.start_recording()
                        logger.info("Recording started.")
                    if task.params["log"]:
                        log.write('B', bookmark, level[0])
                    if self.scan_active:
                        time.sleep(task.params["delay"])
                    while task.params["wait"]:
                        while self._signal_check(
                                task.params["sgn_level"], rigctl, level) and self.scan_active:
                            continue
                        if self.scan_active:
                            time.sleep(task.params["delay"])
                        if not (self._signal_check(
                                task.params["sgn_level"], rigctl, level)) or not self.scan_active:
                            break
                    if task.params["record"]:
                        rigctl.stop_recording()
                        logger.info("Recording stopped.")
                if not self.scan_active:
                    return task
            if pass_count > 0:
                pass_count -= 1
                if pass_count == 0 and task.params["passes"] > 0:
                    self.scan_active = False
                else:
                    time.sleep(MONITOR_MODE_DELAY)
        task.scanq.notify_end_of_scan()
        return task

    def process_queue(self, task):

        while task.scanq.update_queued():
            name, value = task.scanq.get_event_update()
            key = str(name.split("_", 1)[1])
            if key in ("range_min", "range_max"):
                task.params[key] = khertz_to_hertz(value)
            else:
                task.params[key] = value
            logger.info("Queue passed %s %i", name, value)
            logger.info("Params[%s] = %s", key, task.params[key])


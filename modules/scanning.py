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
"""
from modules.rigctl import RigCtl
from modules.constants import SUPPORTED_SCANNING_MODES
from modules.constants import TIME_WAIT_FOR_TUNE
from modules.constants import SIGNAL_CHECKS
from modules.constants import NO_SIGNAL_DELAY
from modules.constants import MIN_INTERVAL
from modules.constants import UNKNOWN_MODE
from modules.constants import MONITOR_MODE_DELAY
from modules.exceptions import UnsupportedScanningConfigError
import logging
import time

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
                 mode,
                 bookmark_list,
                 monitoring_loops,
                 range_min=None,
                 range_max=None,
                 delay=None,
                 interval=None,
                 sgn_level=None,
                 recording=False,
                 monitoring=False):

        """We do some checks to see if we are good to go with the scan.

        :param mode: scanning mode, either bookmark or frequency
        :type mode: string
        :param bookmark_list: the actual list of bookmarks, may be empty
        :type bookmark_list: list of tuples, every tuple is a bookmark
        :raises: UnsupportedScanningConfigError if action or mode are not
        allowed
        :returns: none
        """

        self.error = None
        self.new_bookmark_list = []
        self.bookmark_list = bookmark_list

        if mode.lower() not in SUPPORTED_SCANNING_MODES:
            logger.error("Unsupported scanning mode "\
                          "provided, exiting.")
            logger.error("Provided mode:{}".format(mode))
            logger.error("Supported modes:{}".format(SUPPORTED_SCANNING_MODES))
            raise UnsupportedScanningConfigError

        self.mode = mode
        self.recording = recording
        self.monitoring = monitoring
        self.monitoring_loops = monitoring_loops

        try:
            self.range_min = khertz_to_hertz(int(range_min.replace(',', '')))
            self.range_max = khertz_to_hertz(int(range_max.replace(',', '')))
            self.interval = int(interval)
            self.delay = int(delay)
            self.sgn_level = int(sgn_level)
        except ValueError:
            """We log some info and re raise."""
            logger.exception("One input values is not of the proper type.")
            logger.exception("range_max:{}".format(range_max))
            logger.exception("range_min:{}".format(range_min))
            logger.exception("interval:{}".format(interval))
            logger.exception("delay:{}".format(delay))
            logger.exception("sgn_level:{}".format(sgn_level))
            raise

        if mode == "frequency":
            self._check_interval()

    def _check_interval(self):
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than MIN_INTERVAL, if there is such a low interval
        we overwrite and log a warning.
        """

        if khertz_to_hertz(self.interval) < MIN_INTERVAL:
            logger.info("Low interval provided:{}".format(self.interval))
            logger.info("Overriding with {}".format(MIN_INTERVAL))
            self.interval = MIN_INTERVAL


class Scanning(object):
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    def scan(self, task):
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        rigctl = RigCtl()
        if task and task.mode.lower() == "bookmarks":
            updated_task = self._bookmarks(task, rigctl)
        elif task and task.mode.lower() == "frequency":
            updated_task = self._frequency(task, rigctl)
        return updated_task

    def _frequency(self, task, rigctl):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """
        for i in range(task.monitoring_loops):
            logger.warning("loop {}".format(i))
            freq = task.range_min
            interval = khertz_to_hertz(task.interval)
            while freq < task.range_max:
                logger.info("Tuning to {}".format(freq))
                logger.warning("Interval:{}".format(task.interval))
                rigctl.set_frequency(freq)
                time.sleep(TIME_WAIT_FOR_TUNE)

                if self._signal_check(task.sgn_level, rigctl):
                    logger.info("Activity found on freq: {}".format(freq))
                    if task.recording:
                        rigctl.start_recording()
                        logger.warning("Recording started.")
                    triple = (freq, UNKNOWN_MODE, str(freq))
                    task.new_bookmark_list.append(triple)
                    time.sleep(task.delay)
                    if task.recording:
                        rigctl.stop_recording()
                        logger.warning("Recording stopped.")
                freq = freq + interval
            if task.monitoring == False:
                # if we are not monitoring, at the end of the first loop
                # we are done.
                break
            else:
                time.sleep(MONITOR_MODE_DELAY)

        return task

    def _signal_check(self, sgn_level, rigctl):
        """check for the signal SIGNAL_CHECKS times pausing 
        NO_SIGNAL_DELAY between checks.

        :param sgn_level: minimum signal level we are searching
        :type sgn_level: string from the UI setting
        :returns true/false: signal found, signal not found
        :return type: boolean
        """

        sgn = dbfs_to_sgn(sgn_level)

        for i in range(0, SIGNAL_CHECKS):
            logging.info("Checks left:{}".format(SIGNAL_CHECKS -i))
            level = int(rigctl.get_level().replace(".", ""))
            logger.info("sgn_level:{}".format(level))
            logger.info("dbfs_sgn:{}".format(sgn))
            if int(rigctl.get_level().replace(".", "")) > sgn:
                return True
            else:
                time.sleep(NO_SIGNAL_DELAY)
        return False

    def _bookmarks(self, task, rigctl):
        """Performs a bookmark scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()
        For every bookmark we tune the frequency and we call _signal_check

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        for i in range(task.monitoring_loops):
            for bookmark in task.bookmark_list:
                logger.info("Tuning to {}".format(bookmark[0]))
                rigctl.set_frequency(bookmark[0].replace(',', ''))
                time.sleep(TIME_WAIT_FOR_TUNE)
                if self._signal_check(task.sgn_level, rigctl):
                    logger.info("Activity found on freq: {}".format(bookmark[0]))
                    if task.recording:
                        rigctl.start_recording()
                        logger.info("Recording started.")
                    task.new_bookmark_list.append(bookmark)
                    time.sleep(task.delay)
                    if task.recording:
                        rigctl.stop_recording()
                        logger.info("Recording stopped.")
            if task.monitoring == False:
                # if we are not monitoring, at the end of the first loop
                # we are done.
                break
            else:
                time.sleep(MONITOR_MODE_DELAY)
        return task

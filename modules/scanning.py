#!/usr/bin/env python

from modules.rigctl import RigCtl
from modules.constants import SUPPORTED_SCANNING_MODES
from modules.constants import TIME_WAIT_FOR_SIGNAL
from modules.constants import TIME_WAIT_FOR_TUNE
from modules.constants import MIN_INTERVAL
from modules.constants import MAX_SCAN_THREADS
import logging
import os
import time

# logging configuration
logger = logging.getLogger(__name__)

class ScanningReport(object):

    def __init__(self):
        self.frequency = None
        self.date = None
        self.comment_header = "Discovered on "

class ScanningTask(object):

    def __init__(self,
                 mode,
                 bookmark_list,
                 range_min = None,
                 range_max = None,
                 delay = None,
                 interval = None,
                 sgn_level = None):

        """We do some checks to see if we are good to go with the scan.

        :param mode: scanning mode, either bookmark or frequency
        :type mode: string
        :param bookmark_list: the actual list of bookmarks, may be empty
        :type bookmark_list: list of tuples, every tuple is a bookmark
        :raises: UnsupportedScanningConfigError if action or mode are not allowed
        :returns: none
        """

        self.error = None
        self.new_bookmark_list=[]
        self.bookmark_list = bookmark_list

        if mode.lower() not in SUPPORTED_SCANNING_MODES:
            logger.error("Unsupported scanning mode "\
                          "provided, exiting.")
            logger.error("Provided mode:{}".format(mode))
            logger.error("Supported modes:{}".format(SUPPORTED_SCANNING_MODES))
            raise UnsupportedScanningConfigError

        self.mode = mode

        try:
            self.range_min = int(range_min.replace(',', ''))*1000000
            self.range_max = int(range_max.replace(',', ''))*1000000
            self.interval = int(interval)
            self.delay = int(delay)
            self.sgn_level = int(sgn_level)
        except ValueError:
            """We log some info and re raise
            """
            logger.exception("One of the input values isn't of the proper type.")
            logger.exception("range_max:{}".format(range_max))
            logger.exception("range_min:{}".format(range_min))
            logger.exception("interval:{}".format(interval))
            logger.exception("delay:{}".format(delay))
            logger.exception("sgn_level:{}".format(sgn_level))
            raise

        self._check_interval()

    def _check_interval(self):
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than MIN_INTERVAL, if there is such a low interval
        we overwrite and log a warning.
        """

        if self.interval < MIN_INTERVAL:
            logger.info("Low interval provided:{}".format(self.interval))
            logger.info("Overriding with {}".format(MIN_INTERVAL))
            self.interval = MIN_INTERVAL

class Scanning(object):


    def scan(self, task):
        """Wrapper class around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        if task and task.mode.lower() == "bookmarks":
            updated_task = self._bookmarks(task)
        elif task and task.mode.lower() == "frequency":
            updated_task = self._frequency(task)
        return updated_task

    def _frequency(self, task):
        """Performs a frequency scan, using the task obj for finding 
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        rigctl = RigCtl()
        freq = task.range_min
        while freq < task.range_max:
            logger.info("delay {}".format(task.delay))
            logger.info("Tuning to {}".format(freq))
            logger.info("interval:{}".format(task.interval))
            rigctl.set_frequency(freq)
            time.sleep(TIME_WAIT_FOR_TUNE)
            logger.info("sgn_level:{}".format(int(rigctl.get_level().replace(".",""))))
            if int(rigctl.get_level().replace(".","")) > task.sgn_level:
                logger.info("Activity found on freq: {}".format(freq))
                task.new_bookmark_list.append(freq)
                time.sleep(task.delay)
            freq = freq + task.interval

        return task

    def _bookmarks(self, task):
        """Performs a bookmark scan, using the task obj for finding 
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        rigctl = RigCtl()
        for bookmark in task.bookmark_list:
            logger.info("Tuning to {}".format(bookmark[0]))
            rigctl.set_frequency(bookmark[0].replace(',', ''))
            time.sleep(TIME_WAIT_FOR_TUNE)
            logger.info("sgn_level:{}".format(int(rigctl.get_level().replace(".",""))))
            if int(rigctl.get_level().replace(".","")) > task.sgn_level:
                logger.info("Activity found on freq: {}".format(bookmark[0]))
                task.new_bookmark_list.append(bookmark)
                time.sleep(task.delay)
        return task
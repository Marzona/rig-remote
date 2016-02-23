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

2016/02/23 - TAS - Added lockout field to treeview and coded toggle for it.
                   Still need to highlight locked fields, and add supporting
                   scanning code.
                   
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
                 stop_scan_button,
                 range_min = None,
                 range_max = None,
                 delay = None,
                 passes = None,
                 interval = None,
                 sgn_level = None,
                 record = False,
                 log = False,
                 wait = False):

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
        self.record = record
        self.log = log
        self.wait = wait
        self.stop_scan_button = stop_scan_button

        try:
            self.range_min = khertz_to_hertz(int(range_min.replace(',', '')))
            self.range_max = khertz_to_hertz(int(range_max.replace(',', '')))
            self.interval = int(interval)
            self.delay = int(delay)
            self.passes = int(passes)
            self.sgn_level = int(sgn_level)
        except ValueError:
            """We log some info and re raise."""
            logger.exception("One input values is not of the proper type.")
            logger.exception("range_max:{}".format(range_max))
            logger.exception("range_min:{}".format(range_min))
            logger.exception("interval:{}".format(interval))
            logger.exception("delay:{}".format(delay))
            logger.exception("passes:{}".format(passes))
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
        if task and task.mode.lower() == "bookmarks":
            updated_task = self._bookmarks(task, rigctl)
        elif task and task.mode.lower() == "frequency":
            updated_task = self._frequency(task, rigctl)
#        return updated_task

    def _frequency(self, task, rigctl):
        """Performs a frequency scan, using the task obj for finding
        all the info. This function is wrapped by Scanning.scan()

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """
        pass_count = task.passes
        while (self.scan_active == True):
            freq = task.range_min
            interval = khertz_to_hertz(task.interval)
            while freq < task.range_max:
                logger.info("Tuning to {}".format(freq))
                logger.info("Interval:{}".format(task.interval))
                try :
                    rigctl.set_frequency(freq)
                except Exception :
                    logger.warning("Communications Error!")
                    self.scan_active  = False
                    break
                time.sleep(TIME_WAIT_FOR_TUNE)

                if self._signal_check(task.sgn_level, rigctl):
                    logger.info("Activity found on freq: {}".format(freq))
                    if task.record:
                        rigctl.start_recording()
                        logger.info("Recording started.")
                    triple = (freq, UNKNOWN_MODE, str(freq))
                    task.new_bookmark_list.append(triple)
                    time.sleep(task.delay)
                    if task.record:
                        rigctl.stop_recording()
                        logger.info("Recording stopped.")
                freq = freq + interval
                if self.scan_active == False :
                    return task
            if pass_count > 0 :
                pass_count -= 1
                if pass_count == 0 and task.passes > 0:
                    self.scan_active = False
                else:
                    time.sleep(MONITOR_MODE_DELAY) 
        task.stop_scan_button.event_generate("<Button-1>")
        task.stop_scan_button.event_generate("<ButtonRelease-1>")
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
        signal_found = 0

        for i in range(0, SIGNAL_CHECKS):
            logging.info("Checks left:{}".format(SIGNAL_CHECKS -i))
            level = int(rigctl.get_level().replace(".", ""))
            logger.info("sgn_level:{}".format(level))
            logger.info("dbfs_sgn:{}".format(sgn))
            if (level > sgn) :
                signal_found += 1
            time.sleep(NO_SIGNAL_DELAY)
        logger.info("signal_found:{}".format(signal_found))
        if (signal_found > 1) :
            return True
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

        pass_count = task.passes

        while (self.scan_active == True):
            for bookmark in task.bookmark_list:
                logger.info("Tuning to {}".format(bookmark[0]))
                try:
                    rigctl.set_frequency(bookmark[0].replace(',', ''))
                except Exception :
                    logger.warning("Communications Error!")
                    self.scan_active  = False
                    break
                time.sleep(TIME_WAIT_FOR_TUNE)
                if self._signal_check(task.sgn_level, rigctl):
                    logger.info(
                        "Activity found on freq: {}".format(bookmark[0]))
                    if task.record:
                        rigctl.start_recording()
                        logger.info("Recording started.")
                    task.new_bookmark_list.append(bookmark)
                    time.sleep(task.delay)
                    while task.wait :
                        while self._signal_check(task.sgn_level, rigctl): 
                            continue
                        time.sleep(task.delay)
                        if not (self._signal_check(task.sgn_level, rigctl)):
                            break
                    if task.record:
                        rigctl.stop_recording()
                        logger.info("Recording stopped.")
                if self.scan_active == False :
                    return task
            if pass_count > 0 :
                pass_count -= 1
                if pass_count == 0 and task.passes > 0:
                    self.scan_active = False
                else:
                    time.sleep(MONITOR_MODE_DELAY) 
        task.stop_scan_button.event_generate("<Button-1>")
        task.stop_scan_button.event_generate("<ButtonRelease-1>")
        return task

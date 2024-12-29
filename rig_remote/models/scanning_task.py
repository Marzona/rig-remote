#!/usr/bin/env python

from rig_remote.exceptions import InvalidScanModeError, UnsupportedScanningConfigError
import logging

logger = logging.getLogger(__name__)


class ScanningTask:
    """Representation of a scan task, with helper method for checking
    for proper frequency range.

    """

    # we can can trhgou a frequency range or through the bookmarks only
    _SUPPORTED_SCANNING_MODES = ("bookmarks", "frequency")
    # minimum interval in hertz
    _MIN_INTERVAL: int = 1000

    def __init__(
        self,
        frequency_modulation: str,
        scan_mode: str,
        new_bookmark_list: list,
        range_min: int,
        range_max: int,
        interval: int,
        delay: int,
        passes: int,
        sgn_level: int,
        wait: int,
        record: bool,
        auto_bookmark: bool,
        log: bool,
        bookmarks: list,
    ):
        """We do some checks to see if we are good to go with the scan.

        :param pass_params: configuration parameters
        :param scan_mode: scanning mode, either bookmark or frequency
        :raises: InvalidScanModeError if action or mode are not
        allowed
        :raises: ValueError if the pass_params dictionary contains invalid data
        :returns: none
        """
        self.bookmarks = bookmarks
        self.error = None
        self.frequency_modulation = frequency_modulation
        self.new_bookmark_list = new_bookmark_list
        self.range_min = range_min
        self.range_max = range_max
        self.interval = interval
        self.delay = delay
        self.passes = passes
        self.sgn_level = sgn_level
        self.log = log
        self.wait = wait
        self.record = record
        self.auto_bookmark = auto_bookmark
        if scan_mode.lower() not in self._SUPPORTED_SCANNING_MODES:
            logger.error(
                "Unsupported scanning mode provided %s, supported scan modes are %s.",
                scan_mode,
                self._SUPPORTED_SCANNING_MODES,
            )
            raise UnsupportedScanningConfigError

        self.scan_mode = scan_mode

        if scan_mode not in self._SUPPORTED_SCANNING_MODES:
            logger.error(
                "Unsupported scanning mode provided %s, supported modes are %s",
                scan_mode,
                self._SUPPORTED_SCANNING_MODES,
            )
            raise InvalidScanModeError
        if scan_mode == "frequency":
            self._check_interval()

    def _check_interval(self):
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than self._MIN_INTERVAL, if there is such a low interval
        we overwrite and log an error.
        """
        if self.interval < self._MIN_INTERVAL:
            logger.error(
                "Low interval provided %i, overriding with %i",
                self.interval,
                self._MIN_INTERVAL,
            )
            self.interval = self._MIN_INTERVAL

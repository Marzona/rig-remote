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
Copyright (c) 2016 Tim Sweeney
"""

import logging
from typing import List

from rig_remote.models.bookmark import Bookmark

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
        new_bookmark_list: List[Bookmark],
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
        bookmarks: List[Bookmark],
    ):
        """We do some checks to see if we are good to go with the scan.

        :param scan_mode: scanning mode, either bookmark or frequency
        :raises: InvalidScanModeError if action or mode are not
        allowed
        :raises: ValueError if the pass_params dictionary contains invalid data

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
        self.scan_mode = scan_mode
        self._post_init()

    def _post_init(self)->None:
        self._check_scan_mode()
        self._check_passes()

    def _check_scan_mode(self)->None:
        if self.scan_mode.lower() not in self._SUPPORTED_SCANNING_MODES:
            message = (f"Unsupported scanning mode provided {self.scan_mode}, "
                       f"supported modes are {self._SUPPORTED_SCANNING_MODES}")
            logger.error(message)
            raise ValueError(message)
        self.scan_mode = self.scan_mode
        if self.scan_mode == "frequency":
            self._check_interval()
            self._check_range()

    def _check_interval(self)->None:
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than self._MIN_INTERVAL, if there is such a low intervalInvalidScanModeError
        we overwrite and log an error.
        """

        if self.interval < self._MIN_INTERVAL:
            logger.error(
                "Low interval provided %i, overriding with %i",
                self.interval,
                self._MIN_INTERVAL,
            )
            self.interval = self._MIN_INTERVAL

    def _check_range(self)->None:
        if self.range_min >= self.range_max:
            message = f"range_min {self.range_min} must be lower and different from range_max :{self.range_max}"
            logger.error(message)
            raise ValueError(message)

    def _check_passes(self)->None:
        if self.passes < 1:
            logger.error("scan passes must be >=1, got %i, updated to 1", self.passes)
            self.passes = 1

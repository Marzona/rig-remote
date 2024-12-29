#!/usr/bin/env python

from rig_remote.exceptions import UnsupportedScanningConfigError
from typing import Dict
import re
import logging
from rig_remote.utility import (
    khertz_to_hertz,
)

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
        new_bookmark_list,
        pass_params: Dict,
        bookmarks: list,
    ):
        """We do some checks to see if we are good to go with the scan.

        :param pass_params: configuration parameters
        :param scan_mode: scanning mode, either bookmark or frequency
        :raises: UnsupportedScanningConfigError if action or mode are not
        allowed
        :raises: ValueError if the pass_params dictionary contains invalid data
        :returns: none
        """
        self.bookmarks = bookmarks
        self.error = None
        self.frequency_modulation = frequency_modulation
        self.new_bookmark_list = new_bookmark_list
        self.range_min = None
        self.range_max = None
        self.interval = None
        self.delay = None
        self.passes = None
        self.sgn_level = None
        self.log = None
        self.wait = None
        self.record = None
        self.auto_bookmark = None
        if scan_mode.lower() not in self._SUPPORTED_SCANNING_MODES:
            logger.error("Unsupported scanning mode " "provided, exiting.")
            logger.error("Provided mode:{}".format(scan_mode))
            logger.error("Supported modes:{}".format(self._SUPPORTED_SCANNING_MODES))
            raise UnsupportedScanningConfigError

        self.scan_mode = scan_mode
        self._params = pass_params

        try:
            self.range_min = khertz_to_hertz(
                int("".join(filter(str.isdigit, self._params["txt_range_min"].get())))
            )
            self.range_max = khertz_to_hertz(
                int("".join(filter(str.isdigit, self._params["txt_range_max"].get())))
            )
            self.interval = khertz_to_hertz(
                int("".join(filter(str.isdigit, self._params["txt_interval"].get())))
            )
            self.delay = int(
                "".join(filter(str.isdigit, self._params["txt_delay"].get()))
            )

            self.passes = int(
                "".join(filter(str.isdigit, self._params["txt_passes"].get()))
            )

            self.sgn_level = int(
                re.sub("[^-0-9]", "", self._params["txt_sgn_level"].get())
            )
            self.log = self._params["ckb_log"].is_checked()
            self.wait = self._params["ckb_wait"].is_checked()
            self.record = self._params["ckb_record"].is_checked()
            self.auto_bookmark = self._params["ckb_auto_bookmark"].is_checked()

        except ValueError:
            """We log some info and re raise."""
            logger.exception("One input values is not of the proper type.")
            logger.exception("range_max:{}".format(self._params["txt_range_max"]))
            logger.exception("range_min:{}".format(self._params["txt_range_min"]))
            logger.exception("interval:{}".format(self._params["txt_interval"]))
            logger.exception("delay:{}".format(self._params["txt_delay"]))
            logger.exception("passes:{}".format(self._params["txt_passes"]))
            logger.exception("sgn_level:{}".format(self._params["txt_sgn_level"]))
            raise

        if scan_mode == "frequency":
            self._check_interval()

    def _check_interval(self):
        """Checks for a sane interval. We don't want to search for signals
        with bandwidth lower than self._MIN_INTERVAL, if there is such a low interval
        we overwrite and log an error.
        """

        if self.interval < self._MIN_INTERVAL:
            logger.error("Low interval provided:{}".format(self.interval))
            logger.error("Overriding with {}".format(self._MIN_INTERVAL))
            self.interval = self._MIN_INTERVAL

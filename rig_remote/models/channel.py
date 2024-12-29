#!/usr/bin/env python

from dataclasses import dataclass
from uuid import uuid4
import logging

import re


logger = logging.getLogger(__name__)


@dataclass
class Channel:
    _MODULATIONS = (
        "AM",
        "FM",
        "WFM",
        "WFM_ST",
        "LSB",
        "USB",
        "CW",
        "CWL",
        "CWU",
    )

    input_frequency: str
    modulation: str
    id: str = str(uuid4())

    def __eq__(self, other):
        if self.frequency == other.frequency and self.modulation == other.modulation:
            return True

    def __post_init__(self):
        if self.modulation.upper() not in self._MODULATIONS:
            raise ValueError(
                "Provided modulation is not supported, supported modulations are %s",
                self._MODULATIONS,
            )

        self._frequency_validator()

    def _frequency_validator(self):
        """Filter invalid chars and add thousands separator."""
        if isinstance(self.input_frequency, str):
            try:
                parsed_input_freq = "{:,}".format(
                    int(re.sub("[^0-9]", "", self.input_frequency))
                )
            except ValueError:
                logger.exception(
                    "error converting frequency " ":{}".format(self.frequency)
                )
                raise

            nocommas: str = parsed_input_freq.replace(",", "")

            if re.search("[^0-9]", nocommas) or int(nocommas) <= 0:
                raise ValueError(
                    "Frequency must be int, value provided %i", self.frequency
                )

            self.frequency = int(nocommas)
        self.frequency = int(self.input_frequency)

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

from dataclasses import dataclass
from rig_remote.models.modulation_modes import ModulationModes
from uuid import uuid4
import logging

import re
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Channel:
    _MODULATIONS = [modulation.value for modulation in ModulationModes]

    input_frequency: int
    modulation: str
    frequency_as_string: Optional[str] = None
    id: str = str(uuid4())
    frequency: int = 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Channel):
            return NotImplemented
        return self.frequency == other.frequency and self.modulation == other.modulation

    def __post_init__(self)-> None:
        if self.modulation.upper() not in self._MODULATIONS:
            message = (
                "Provided modulation %s is not supported, supported modulations are %s",
                self.modulation,
                self._MODULATIONS,
            )
            logger.error(message)
            raise ValueError(message)

        self._frequency_validator()

    def _frequency_validator(self) -> None:
        """Filter invalid chars and add thousands separator."""
        try:
            frequency_int = int(re.sub("[^0-9]", "", str(self.input_frequency)))
        except ValueError:
            logger.error("error converting frequency %s", self.input_frequency)
            raise

        if frequency_int < 1 or frequency_int > 500000000:
            message = "invalid frequency %s" % self.input_frequency
            raise ValueError(message)

        self.frequency_as_string = "{:,}".format(frequency_int)
        self.frequency = frequency_int

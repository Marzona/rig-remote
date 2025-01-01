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
from uuid import uuid4
import logging
from rig_remote.models.channel import Channel

logger = logging.getLogger(__name__)


@dataclass
class Bookmark:
    _LOCKOUTS = ["", "L", "O", "0"]
    channel: Channel
    description: str
    lockout: str = ""
    id: str = str(uuid4())

    def __eq__(self, other):
        if self.channel == other.channel and self.description == other.description:
            return True
        else:
            logger.info(
                "channel or description are different, bookmarks are not the same."
            )
            return False

    def __post_init__(self):
        if self.lockout.upper() not in self._LOCKOUTS:
            message = (
                "Provided lockout value %s is not supported, supported values are %s",
                self.lockout,
                self._LOCKOUTS,
            )
            logger.error(message)
            raise ValueError(message)
        if not self.description:
            raise ValueError("Please add a description")

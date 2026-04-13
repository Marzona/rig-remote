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
from dataclasses import dataclass, field
from uuid import uuid4

from rig_remote.models.channel import Channel

logger = logging.getLogger(__name__)


@dataclass
class Bookmark:
    _LOCKOUTS = ["", "L", "O", "0"]
    channel: Channel
    description: str
    lockout: str = ""
    id: str = field(default_factory=lambda: str(uuid4()), compare=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bookmark):
            raise NotImplementedError
        return self.channel == other.channel and self.description == other.description

    def __post_init__(self) -> None:
        if self.lockout.upper() not in self._LOCKOUTS:
            message = (
                f"Provided lockout value {self.lockout!r} is not supported, "
                f"supported values are {self._LOCKOUTS}"
            )
            logger.error(message)
            raise ValueError(message)
        if not self.description:
            raise ValueError("Please add a description")

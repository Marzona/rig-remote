#!/usr/bin/env python

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
        if (
            self.channel.frequency == other.channel.frequency
            and self.channel.modulation == other.channel.modulation
        ):
            return True

    def __post_init__(self):
        if self.lockout.upper() not in self._LOCKOUTS:
            raise ValueError(
                "Provided lockout value %s is not supported, supported values are %s",
                self.lockout,
                self._LOCKOUTS,
            )
        if not self.description:
            raise ValueError("Please add a description")

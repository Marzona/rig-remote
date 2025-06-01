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

from rig_remote.stmessenger import STMessenger
from rig_remote.rigctl import RigCtl

logger = logging.getLogger(__name__)


@dataclass()
class SyncTask:
    """Representation of a scan task, with helper method for checking
    for proper frequency range.

    """

    syncq: STMessenger
    src_rig: RigCtl
    dst_rig: RigCtl
    error: str = ""
    id: str = str(uuid4())

    def __eq__(self, other):
        if self.src_rig == other.src_rig and self.dst_rig == other.dst_rig:
            return True
        else:
            logger.info(
                "channel or description are different, bookmarks are not the same."
            )
            return False

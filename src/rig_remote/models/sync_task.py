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

from rig_remote.rig_backends.protocol import RigBackend
from rig_remote.stmessenger import STMessenger

logger = logging.getLogger(__name__)


@dataclass()
class SyncTask:
    """Representation of a sync task."""

    syncq: STMessenger
    src_rig: RigBackend
    dst_rig: RigBackend
    error: str = ""
    id: str = field(default_factory=lambda: str(uuid4()), compare=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SyncTask):
            raise NotImplementedError
        return self.src_rig == other.src_rig and self.dst_rig == other.dst_rig

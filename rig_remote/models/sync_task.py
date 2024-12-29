#!/usr/bin/env python

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

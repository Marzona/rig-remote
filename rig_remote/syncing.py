#!/usr/bin/env python
"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Simone Marzona

License: MIT License

Copyright (c) 2015 Simone Marzona
"""

# import modules

import datetime
from rig_remote.rigctl import RigCtl
from rig_remote.disk_io import LogFile
from rig_remote.constants import (MIN_INTERVAL,
                                  BM,
                                  REVERSE_MODE_MAP,
                                  SYNC_INTERVAL,
                                  )
from rig_remote.exceptions import UnsupportedSyncConfigError
from rig_remote.stmessenger import STMessenger
import socket
import logging
import time
import re

# logging configuration
logger = logging.getLogger(__name__)

# class definition

class SyncTask(object):
    """Representation of a scan task, with helper method for checking
    for proper frequency range.

    """

    def __init__(self, syncq, src_rig_controller, dst_rig_controller):
        self.error = None
        self.syncq = syncq

        if not all([src_rig_controller.target["hostname"],
                    src_rig_controller.target["hostname"],
                    dst_rig_controller.target["hostname"],
                    dst_rig_controller.target["hostname"]]):
            logger.info("Source and destination hostname/port needs "
                        "to be filled in.")
            raise UnsupportedSyncConfigError
        self.src_rig = src_rig_controller
        self.dst_rig = dst_rig_controller

class Syncing(object):
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    def __init__(self):
        self.sync_active = True

    def terminate(self):
        self.sync_active = False

    def sync(self, task):
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :type task: object from ScanningTask
        :raises: none
        :returns: updates the scanning task object with the new activity found
        """

        if not isinstance(task, SyncTask):
            logger.error("Unsupported task in sync queue.")
            raise UnsupportedSyncConfigError

        level = []
        while self.sync_active:
            task.dst_rig.set_frequency(task.src_rig.get_frequency())
            task.dst_rig.set_mode(str(task.src_rig.get_mode()))
            time.sleep(SYNC_INTERVAL)
        task.syncq.notify_end_of_scan()
        self.terminate()
        return task

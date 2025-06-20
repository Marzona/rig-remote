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

import logging
import time
from rig_remote.models.sync_task import SyncTask


logger = logging.getLogger(__name__)


class Syncing:
    """Provides methods for doing the bookmark/frequency scan,
    updating the bookmarks with the active frequencies found.

    """

    _SYNC_INTERVAL = 0.1

    def __init__(self):
        self.sync_active = True

    def terminate(self)->None:
        logger.info("Terminating sync task")
        self.sync_active = False

    def sync(self, task: SyncTask, once: bool = False)->SyncTask:
        """Wrapper method around _frequency and _bookmarks. It calls one
        of the wrapped functions matching the task.mode value

        :param task: object that represent a scanning task
        :param once: if True, the sync will stop after the first frequency change
        :returns: updates the scanning task object with the new activity found
        """

        logger.info("Starting sync from rig 1 to rig 2, task id %s", task.id)

        while self.sync_active:
            task.dst_rig.set_frequency(task.src_rig.get_frequency())
            task.dst_rig.set_mode(task.src_rig.get_mode())
            time.sleep(self._SYNC_INTERVAL)
            if once is True:
                self.terminate()
        task.syncq.notify_end_of_scan()
        self.terminate()
        return task

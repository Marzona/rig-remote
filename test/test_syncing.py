from rig_remote.syncing import Syncing
from rig_remote.models.sync_task import SyncTask
from rig_remote.stmessenger import STMessenger
from rig_remote.rigctl import RigCtl
from rig_remote.queue_comms import QueueComms
from unittest.mock import create_autospec


def test_syncing_terminate():
    syncing = Syncing()
    assert syncing._SYNC_INTERVAL == 0.1
    assert syncing.sync_active == True
    syncing.terminate()
    assert syncing.sync_active == False


def test_sycing_sync():
    syncing = Syncing()
    sync_task = SyncTask(
        syncq=STMessenger(queuecomms=QueueComms()),
        src_rig=create_autospec(RigCtl),
        dst_rig=create_autospec(RigCtl),
        error="",
    )
    syncing.sync(task=sync_task, once=True)
    syncing.terminate()
    sync_task.src_rig.get_frequency.assert_called_once()
    sync_task.src_rig.get_mode.assert_called_once()
    sync_task.dst_rig.set_frequency.assert_called_once()
    sync_task.dst_rig.set_mode.assert_called_once()
    assert syncing.sync_active == False

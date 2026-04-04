from rig_remote.models.sync_task import SyncTask
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rigctl import RigCtl
from rig_remote.stmessenger import STMessenger
from rig_remote.queue_comms import QueueComms
import pytest


def test_sync_task_init():
    sync_task = SyncTask(
        STMessenger(queue_comms=QueueComms()),
        RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1")),
        RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8081, number=2, name="test_rig2")),
        "",
    )
    assert sync_task.src_rig.endpoint.number == 1
    assert sync_task.dst_rig.endpoint.number == 2
    assert isinstance(sync_task.id, str)


@pytest.mark.parametrize(
    "syncq1, src_rig1, dst_rig1, error1, syncq2, src_rig2, dst_rig2, error2, expected",
    [
        (
            STMessenger(queue_comms=QueueComms()),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1")),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=2, name="test_rig2")),
            "",
            STMessenger(queue_comms=QueueComms()),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1")),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=2, name="test_rig2")),
            "",
            False,
        ),
        (
            STMessenger(queue_comms=QueueComms()),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1")),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8081, number=2, name="test_rig2")),
            "",
            STMessenger(queue_comms=QueueComms()),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1")),
            RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8081, number=2, name="test_rig2")),
            "",
            False,
        ),
    ],
)
def test_sync_task_comparison_false(syncq1, src_rig1, dst_rig1, error1, syncq2, src_rig2, dst_rig2, error2, expected):
    sync_task1 = SyncTask(syncq=syncq1, src_rig=src_rig1, dst_rig=dst_rig1, error=error1)
    sync_task2 = SyncTask(syncq=syncq2, src_rig=src_rig2, dst_rig=dst_rig2, error=error2)

    assert (sync_task1 == sync_task2) == expected


def test_sync_task_comparison_true():
    src_rig = RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8080, number=1, name="test_rig1"))
    dst_rig = RigCtl(endpoint=RigEndpoint(hostname="localhost", port=8081, number=2, name="test_rig2"))
    sync_task1 = SyncTask(
        STMessenger(queue_comms=QueueComms()),
        src_rig,
        dst_rig,
        "",
    )
    sync_task2 = SyncTask(
        STMessenger(queue_comms=QueueComms()),
        src_rig,
        dst_rig,
        "",
    )
    assert sync_task1 == sync_task2

"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
Author: Simone Marzona <rafael@defying.me>

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
"""
from unittest.mock import Mock, create_autospec

import pytest

from rig_remote.disk_io import LogFile
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.channel import Channel
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import Scanning
from rig_remote.scanning import ScanningTask
from rig_remote.stmessenger import STMessenger


@pytest.fixture
def scanning():
    hostname = "localhost"
    port = 8080
    number = 1
    rig_endpoint = RigEndpoint(hostname=hostname, port=port, number=number)
    rigctl = RigCtl(target=rig_endpoint)
    scanning = Scanning(
        scan_queue=STMessenger(queuecomms=QueueComms()),
        log_filename="test_filename",
        rigctl=rigctl,
    )
    scanning._TIME_WAIT_FOR_TUNE = 0  # all api calls are mocked no need for this safety
    scanning._NO_SINGNAL_DELAY = 0  # all api calls are mocked no need for this safety
    scanning._log = Mock()
    return scanning


def test_scanning_terminate(scanning):
    assert scanning._scan_active is True
    scanning.terminate()
    assert scanning._scan_active is False
    scanning.terminate()
    assert scanning._scan_active is False


def test_scanning_scan_wrapper(scanning):
    bookmarks_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=200,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="L",
            )
        ],
    )

    frequency_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=200,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="L",
            )
        ],
    )

    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning.scan(task=frequency_scanning_task)
    scanning._bookmarks.assert_not_called()
    scanning._frequency.assert_called_once()
    scanning.scan(task=bookmarks_scanning_task)
    scanning._bookmarks.assert_called_once()


def test_scanning_scan_bookmarks_lockout(scanning):
    bookmarks_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=200,
        wait=False,
        record=False,
        auto_bookmark=False,
        log=False,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="L",
            )
        ],
    )
    scanning._rigctl = create_autospec(RigCtl)
    assert scanning._scan_active is True
    scanning._bookmarks(task=bookmarks_scanning_task)
    assert scanning._scan_active is False
    # bookmark has lockout set
    scanning._rigctl.assert_not_called()
    scanning._rigctl.get_level.assert_not_called()


@pytest.mark.parametrize(
    "scanning_task",
    [
        ScanningTask(  # bookmarks scan
            frequency_modulation="FM",
            scan_mode="bookmarks",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=False,
            bookmarks=[
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
            ],
        ),
        ScanningTask(  # frequency scan
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=False,
        ),
        ScanningTask(  # bookmarks scan and log
            frequency_modulation="FM",
            scan_mode="bookmarks",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=True,
            bookmarks=[
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
            ],
        ),
        ScanningTask(  # frequency scan and log
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        ),
    ],
)
def test_scanning_scan(scanning, scanning_task):
    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning._log_close = Mock()

    scanning.scan(task=scanning_task)
    if scanning_task.scan_mode.lower() == "bookmarks":
        scanning._bookmarks.assert_called_once()
        scanning._frequency.assert_not_called()
    if scanning_task.scan_mode.lower() == "frequency":
        scanning._bookmarks.assert_not_called()
        scanning._frequency.assert_called_once()


@pytest.mark.parametrize(
    "scanning_task",
    [
        ScanningTask(  # bookmarks scan and log and IOError
            frequency_modulation="FM",
            scan_mode="bookmarks",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            record=False,
            auto_bookmark=False,
            log=True,
            bookmarks=[
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
                Bookmark(
                    channel=Channel(input_frequency="1", modulation="FM"),
                    description="description1",
                    lockout="",
                ),
            ],
        ),
        ScanningTask(  # frequency scan and log and IOError
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=1,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        ),
    ],
)
def test_scanning_scan_io_error(scanning, scanning_task):
    scanning._bookmarks = Mock()
    scanning._frequency = Mock()
    scanning._log_close = Mock()
    mock_log = create_autospec(LogFile)
    mock_log.open = Mock(side_effect=IOError("Test IOError"))
    scanning._log = mock_log
    with pytest.raises(IOError):
        scanning.scan(task=scanning_task)
    scanning._bookmarks.assert_not_called()
    scanning._frequency.assert_not_called()
    scanning._log_close.assert_not_called()


@pytest.mark.parametrize(
    "exception_type, exception_raise, scanning_task",
    [

        (ValueError, ValueError("Test ValueError"), ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),
        (OSError, OSError("OSrror"),ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),
        (TimeoutError, TimeoutError("TimeoutError"),ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),

    ]
)
def test_scanning_scan_frequency_exceptions(scanning,exception_type, exception_raise,scanning_task):
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_frequency.side_effect =exception_type
    scanning.scan(task=scanning_task)
    assert scanning._scan_active is False


@pytest.mark.parametrize(
    "exception_type, exception_raise, scanning_task",
    [

        (ValueError, ValueError("Test ValueError"), ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),
        (OSError, OSError("OSrror"),ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),
        (TimeoutError, TimeoutError("TimeoutError"),ScanningTask(
            frequency_modulation="FM",
            scan_mode="frequency",
            new_bookmark_list=[],
            range_min=1,
            range_max=1000,
            interval=1,
            delay=1,
            passes=2,
            sgn_level=200,
            wait=False,
            bookmarks=[],
            record=False,
            auto_bookmark=False,
            log=True,
        )),

    ]
)
def test_scanning_scan_mode_exceptions(scanning,exception_type, exception_raise,scanning_task):
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_mode.side_effect =exception_type
    scanning.scan(task=scanning_task)
    assert scanning._scan_active is False




def test_scanning_scan_bookmarks_no_wait(scanning):
    bookmarks_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=30,
        wait=False,
        record=True,
        auto_bookmark=False,
        log=True,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
        ],
    )
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    assert scanning._scan_active is True
    scanning._bookmarks(task=bookmarks_scanning_task)
    assert scanning._scan_active is False
    assert scanning._rigctl.set_frequency.call_count == len(
        bookmarks_scanning_task.bookmarks
    )
    assert scanning._rigctl.set_mode.call_count == len(
        bookmarks_scanning_task.bookmarks
    )
    assert scanning._log.write.call_count == len(bookmarks_scanning_task.bookmarks)
    # because wait=False
    assert scanning._rigctl.get_level.call_count == scanning._SIGNAL_CHECKS * 2
    assert scanning._rigctl.start_recording.call_count == len(
        bookmarks_scanning_task.bookmarks
    )


def test_scanning_scan_bookmarks_wait(scanning):
    bookmarks_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=250,
        wait=True,
        record=True,
        auto_bookmark=False,
        log=True,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
        ],
    )
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = (
        250  # TODO mettere una lista di valori di ritorno per coprire 171
    )
    assert scanning._scan_active is True
    scanning._bookmarks(task=bookmarks_scanning_task)
    assert scanning._scan_active is False
    assert scanning._rigctl.set_frequency.call_count == len(
        bookmarks_scanning_task.bookmarks
    )
    assert scanning._rigctl.set_mode.call_count == len(
        bookmarks_scanning_task.bookmarks
    )
    assert scanning._log.write.call_count == len(bookmarks_scanning_task.bookmarks)
    assert scanning._rigctl.get_level.call_count == scanning._SIGNAL_CHECKS * 4
    assert scanning._rigctl.start_recording.call_count == len(
        bookmarks_scanning_task.bookmarks
    )



@pytest.mark.parametrize(
    "exception_type, exception_raise, scanning_task",
    [

        (OSError, OSError("OSrror"),ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=250,
        wait=True,
        record=True,
        auto_bookmark=False,
        log=True,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
        ],
    )),
        (TimeoutError, TimeoutError("TimeoutError"),ScanningTask(
        frequency_modulation="FM",
        scan_mode="bookmarks",
        new_bookmark_list=[],
        range_min=1,
        range_max=1000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=250,
        wait=True,
        record=True,
        auto_bookmark=False,
        log=True,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
        ],
    )),

    ]
)
def test_scanning_scan_bookmark_exceptions(scanning,exception_type, exception_raise,scanning_task):
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 2500
    scanning._rigctl.set_frequency.side_effect =exception_type

    scanning.scan(task=scanning_task)
    assert scanning._scan_active is False


def test_scanning_scan_frequency_wait(scanning):
    frequency_scanning_task = ScanningTask(
        frequency_modulation="FM",
        scan_mode="frequency",
        new_bookmark_list=[],
        range_min=1000,
        range_max=3000,
        interval=1,
        delay=1,
        passes=1,
        sgn_level=250,
        wait=True,
        record=True,
        auto_bookmark=True,
        log=True,
        bookmarks=[
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
            Bookmark(
                channel=Channel(input_frequency="1", modulation="FM"),
                description="description1",
                lockout="",
            ),
        ],
    )
    scanning._scan_queue.send_event_update(
        event_list=(
            "tests",
            "tests",
        )
    )
    scanning._rigctl = create_autospec(RigCtl)
    scanning._rigctl.get_level.return_value = 25000
    scanning._rigctl.get_mode.return_value = "FM"
    assert scanning._scan_active is True
    scanning._frequency(task=frequency_scanning_task)
    assert scanning._scan_active is False
    assert scanning._rigctl.set_frequency.call_count == 2
    assert scanning._rigctl.set_mode.call_count == 2
    assert scanning._log.write.call_count == 2
    # because wait=True
    assert scanning._rigctl.get_level.call_count == 4
    assert scanning._rigctl.start_recording.call_count == 2

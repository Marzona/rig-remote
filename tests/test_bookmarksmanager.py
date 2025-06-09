import os
from pathlib import Path

import pytest

from rig_remote.disk_io import IO
from mock import Mock

from rig_remote.exceptions import BookmarkFormatError

from rig_remote.models.channel import Channel
from rig_remote.models.bookmark import Bookmark


from rig_remote.bookmarksmanager import bookmark_factory, BookmarksManager


@pytest.fixture
def bookmark_manager_with_bookmarks():
    bookmark_manager_with_bookmarks = BookmarksManager()
    bookmark_manager_with_bookmarks._io.csv_save = Mock()
    bookmark_manager_with_bookmarks._io.csv_save.return_value = None
    description = "test_description"
    lockout = "L"
    bookmark1 = Bookmark(
        channel=Channel(input_frequency=1, modulation="AM"),
        description=description,
        lockout=lockout,
    )
    bookmark2 = Bookmark(
        channel=Channel(input_frequency=1, modulation="FM"),
        description=description,
        lockout=lockout,
    )
    bookmark_manager_with_bookmarks.bookmarks = [bookmark1, bookmark2]
    return bookmark_manager_with_bookmarks


def test_bookmark_factory():
    input_frequency = "1"
    lockout = "L"
    modulation = "AM"
    description = "test_bookmark"
    bookmark = bookmark_factory(
        input_frequency=int(input_frequency),
        modulation=modulation,
        description=description,
        lockout=lockout,
    )

    assert bookmark.description == description
    assert bookmark.channel.frequency == int(input_frequency)
    assert bookmark.channel.modulation == modulation
    assert bookmark.lockout == lockout


@pytest.mark.parametrize(
    "delimiter",
    [":" "," '"'],
)
def test_bookmarkmanager_save(delimiter):
    io = IO()
    io.csv_save = Mock(return_value=None)
    bookmarks_manager = BookmarksManager(io=io)
    description = "test_description"
    lockout = "L"
    bookmarks_list = [
        Bookmark(
            channel=Channel(input_frequency=1, modulation="AM"),
            description=description,
            lockout=lockout,
        )
    ]
    bookmarks_manager.save(
        bookmarks_file="tests", delimiter=delimiter
    )

    bookmarks_manager._io.csv_save.assert_called_once_with("tests", delimiter)


@pytest.mark.parametrize(
    "delimiter",
    [
        ":",
        ",",
        '"',
    ],
)
def test_bookmarkmanager_load(delimiter):
    io = IO()
    io.csv_load = Mock(return_value=None)
    bookmarks_manager = BookmarksManager(io=io)
    bookmarks_manager.load(bookmark_file="tests", delimiter=delimiter)

    bookmarks_manager._io.csv_load.assert_called_once_with("tests", delimiter)


def test_bookmarkmanager_load_non_existent_file():
    bookmarks_manager = BookmarksManager()
    non_existent_file = os.path.join(Path(__file__).parent,"test_files/nonexistent_file.csv")
    loaded = bookmarks_manager.load(bookmark_file=non_existent_file)
    assert loaded == []


@pytest.mark.parametrize(
    "filename, delimiter, expected",
    [
        (os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks.csv"), ",", 0),
        (os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks-duplicates.csv"), ",", 0),
        (os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks-skipped.csv"), ",", 4),
    ],
)

def test_bookmarkmanager_load2(filename, delimiter, expected):
    bookmarks_manager = BookmarksManager()
    bookmarks_manager.load(bookmark_file=filename, delimiter=delimiter)

    assert (
        len(bookmarks_manager._io.rows) - len(bookmarks_manager.bookmarks)
        == expected
    )
    for item in bookmarks_manager.bookmarks:
        assert isinstance(item, Bookmark)


@pytest.mark.parametrize(
    "filename, count",
    [
        (os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks.csv"), 0),
        (os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks-duplicates.csv"), 0),
    ],
)
def test_bookmarkmanager_import_bookmarks_rig_remote(filename, count):
    bookmarks_manager = BookmarksManager()
    bookmarks_manager._import_gqrx = Mock()
    bookmarks_manager.import_bookmarks(filename=filename)

    bookmarks_manager._import_gqrx.assert_not_called()

    assert (
        len(bookmarks_manager.bookmarks) - len(bookmarks_manager._io.rows) == count
    )
    for item in bookmarks_manager.bookmarks:
        assert isinstance(item, Bookmark)


@pytest.mark.parametrize(
    "filename",
    [
        os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks-broken.csv"),
        os.path.join(Path(__file__).parent,"test_files/test-rig_remote-bookmarks-unsupported.csv"),
    ],
)
def test_bookmarkmanager_import_bookmarks_rig_remote_unsupported(filename):
    bookmarks_manager = BookmarksManager()
    bookmarks_manager._import_gqrx = Mock()
    with pytest.raises(BookmarkFormatError):
        bookmarks_manager.import_bookmarks(filename=filename)


def test_bookmarkmanager_delete_bookmark(bookmark_manager_with_bookmarks):
    bookmark1 = bookmark_manager_with_bookmarks.bookmarks[0]
    bookmark2 = bookmark_manager_with_bookmarks.bookmarks[1]

    bookmark_manager_with_bookmarks.delete_bookmark(bookmark=bookmark1)

    assert len(bookmark_manager_with_bookmarks.bookmarks) == 1
    assert bookmark_manager_with_bookmarks.bookmarks[0] == bookmark2

    bookmark_manager_with_bookmarks.delete_bookmark(bookmark2)
    bookmark_manager_with_bookmarks.delete_bookmark(bookmark2)


def test_bookmarkmanager_add_bookmark():
    bookmarks_manager = BookmarksManager()
    description = "test_description"
    lockout = "L"
    bookmark1 = Bookmark(
        channel=Channel(input_frequency=1, modulation="AM"),
        description=description,
        lockout=lockout,
    )
    bookmark2 = Bookmark(
        channel=Channel(input_frequency=1, modulation="FM"),
        description=description,
        lockout=lockout,
    )

    assert len(bookmarks_manager.bookmarks) == 0

    bookmarks_manager.add_bookmark(bookmark=bookmark1)

    assert len(bookmarks_manager.bookmarks) == 1
    assert bookmarks_manager.bookmarks[0] == bookmark1

    bookmarks_manager.add_bookmark(bookmark=bookmark1)

    assert len(bookmarks_manager.bookmarks) == 1

    bookmarks_manager.add_bookmark(bookmark=bookmark2)

    assert len(bookmarks_manager.bookmarks) == 2
    assert bookmarks_manager.bookmarks[0] == bookmark1
    assert bookmarks_manager.bookmarks[1] == bookmark2


def test_bookmarkmanager_export_rig_remote(bookmark_manager_with_bookmarks):
    bookmark_manager_with_bookmarks.export_rig_remote(filename="tests")
    bookmark_manager_with_bookmarks._io.csv_save.assert_called_once_with("tests", ",")


def test_bookmarkmanager_export_gqrx(bookmark_manager_with_bookmarks):
    bookmark_manager_with_bookmarks.export_gqrx(filename="tests")
    bookmark_manager_with_bookmarks._io.csv_save.assert_called_once_with("tests", ";")

    assert len(bookmark_manager_with_bookmarks._io.rows) == 7
    assert bookmark_manager_with_bookmarks._io.rows[0] == [
        1,
        "test_description",
        "FM",
        "",
        "Untagged",
    ]
    assert bookmark_manager_with_bookmarks._io.rows[1] == [
        1,
        "test_description",
        "AM",
        "",
        "Untagged",
    ]
    assert bookmark_manager_with_bookmarks._io.rows[1:] == [
        [1, "test_description", "AM", "", "Untagged"],
        [
            "# Frequency ",
            " Name                     ",
            " Modulation          ",
            "  Bandwidth",
            " Tags",
        ],
        [],
        ["Marine VHF          ", " #c0c0c0"],
        ["Untagged            ", " #c0c0c0"],
        ["# Tag name          ", "  color"],
    ]


def test_bookmarkmanager_import_bookmarks_no_file():
    bookmarks_manager = BookmarksManager()
    bookmarks_manager._detect_format = Mock()
    bookmarks_manager.import_bookmarks(filename="")
    bookmarks_manager._detect_format.assert_not_called()


@pytest.mark.parametrize(
    "filename, count",
    [
        (os.path.join(Path(__file__).parent,"test_files/test-gqrx-bookmarks.csv"), 0),
        (os.path.join(Path(__file__).parent,"test_files/test-gqrx-bookmarks-duplicates.csv"), 2),
    ],
)
def test_bookmarkmanager_import_bookmarks_gqrx(filename, count):
    bookmarks_manager = BookmarksManager()
    bookmarks_manager._import_rig_remote = Mock()
    bookmarks_manager.import_bookmarks(filename=filename)

    bookmarks_manager._import_rig_remote.assert_not_called()
    assert (
        len(bookmarks_manager._io.rows)
        - bookmarks_manager._GQRX_FIRST_BOOKMARK
        - len(bookmarks_manager.bookmarks)
        == count
    )
    for item in bookmarks_manager.bookmarks:
        assert isinstance(item, Bookmark)

#!/usr/bin/env python

from rig_remote.exceptions import (
    InvalidPathError,
    BookmarkFormatError,
)
from rig_remote.models.channel import Channel
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.modulation_modes import ModulationModes
import logging

from rig_remote.disk_io import IO

logger = logging.getLogger(__name__)
from typing import Callable

def bookmark_factory(
    input_frequency: int | str , modulation: str, description: str, lockout: str = ""
):
    return Bookmark(
        channel=Channel(input_frequency=input_frequency, modulation=modulation),
        description=description,
        lockout=lockout,
    )

class BookmarksManager:
    """Implements the bookmarks management."""

    io: IO
    _BOOKMARK_ENTRY_FIELDS = 4

    _GQRX_BOOKMARK_FIRST_LINE = "# Tag name          ;  color\n"
    # gqrx bookmark file has 5 lines of header
    _GQRX_FIRST_BOOKMARK = 5
    _GQRX_BOOKMARK_HEADER = [
        ["# Tag name          ", "  color"],
        ["Untagged            ", " #c0c0c0"],
        ["Marine VHF          ", " #c0c0c0"],
        [],
        [
            "# Frequency ",
            " Name                     ",
            " Modulation          ",
            "  Bandwidth",
            " Tags",
        ],
    ]

    def __init__(self, io: IO = IO(), bookmark_factory:Callable=bookmark_factory, modulation_modes:ModulationModes = ModulationModes):
        self.io = io
        self.bookmarks = []
        self._bookmark_factory = bookmark_factory
        self._modulation_modes = modulation_modes
        self._IMPORTERS_MAP = {
            "gqrx": self._import_gqrx,
            "rig-remote": self._import_rig_remote,
        }

    def save(self, bookmarks_file: str, bookmarks: list, delimiter: str = ","):
        """Bookmarks handling. Saves the bookmarks as a csv file.

        :param bookmarks_file: filename to load, with full path
        :param delimiter: delimiter to use for creating the csv file,

        defaults to ','
        :raises : none
        :returns : none
        """

        self.io.row_list = []

        for bookmark in bookmarks:
            self.io.row_list.append(
                [
                    bookmark.channel.frequency,
                    bookmark.channel.modulation,
                    bookmark.description,
                    bookmark.lockout,
                ]
            )

        self.io.csv_save(bookmarks_file, delimiter)

    def load(self, bookmark_file: str, delimiter: str = ",") -> list:
        """Bookmarks handling. Loads the bookmarks as
        a csv file.

        :param bookmark_file: filename to load, with full path
        :type bookmark_file: string
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ',''
        :type delimiter: string
        :raises : none
        :returns : none
        """

        try:
            self.io.csv_load(bookmark_file, delimiter)
        except InvalidPathError:
            logger.info("No bookmarks file found, skipping.")
            return []
        skipped_count = 0
        for entry in self.io.row_list:
            if len(entry) < self._BOOKMARK_ENTRY_FIELDS:
                logger.info(
                    "skipping line %s as invalid, not enough fields, expecting 4", entry
                )
                skipped_count += 1
                continue
            bookmark = self._bookmark_factory(
                input_frequency=entry[0],
                modulation=entry[1],
                description=entry[2],
                lockout=entry[3],
            )

            self.bookmarks.append(bookmark)
        logger.info("Skipped %i entries", skipped_count)
        return self.bookmarks

    def import_bookmarks(self, filename:str):
        """handles the import of the bookmarks. It is a
        Wrapper around the import funtions and the requester function.

        """
        if not filename:
            logger.info("no filename provided, nothing to import.")
            return
        return self._IMPORTERS_MAP[self._detect_format(filename)](filename)


    def _detect_format(self, filename: str):
        """Method for detecting the bookmark type. Only two types are supported.

        :param filename: file path to read
        :type filename: string
        """

        with open(filename, "r") as fn:
            line = fn.readline()
        if self._GQRX_BOOKMARK_FIRST_LINE == line:
            return "gqrx"
        if len(line.split(",")) == 4:
            return "rig-remote"
        raise BookmarkFormatError

    def _import_rig_remote(self, file_path):
        """Imports the bookmarks using rig-remote format. It wraps around
        the load method.

        :param file_path: path o fhte file to import
        :type file_path: string
        """

        try:
            return self.load(file_path, ",")
        except ValueError:
            raise BookmarkFormatError

    def _import_gqrx(self, file_path):
        """Method for importing gqrx bookmarks.

        :param file_path: path of the file to be loaded
        :type file_path: string
        """

        self.io.csv_load(file_path, ";")

        count = 0
        bookmarks = []
        for row in self.io.row_list:
            count += 1
            if count < self._GQRX_FIRST_BOOKMARK + 1:
                continue
            try:
                bookmark = self._bookmark_factory(
                    input_frequency=row[0].strip(),
                    modulation=self._modulation_modes[row[2].strip().upper()].value,
                    description=row[1].strip(),
                )
                self.add_bookmark(bookmark)
                bookmarks.append(bookmark)
            except IndexError:
                pass
        return bookmarks

    def delete_bookmark(self, bookmark: Bookmark) -> bool:
        try:
            self.bookmarks.pop(self.bookmarks.index(bookmark))
        except ValueError:
            pass
        logger.info("bookmark %s deleted", bookmark)
        return True

    def add_bookmark(self, bookmark: Bookmark) -> bool:
        if not bookmark in self.bookmarks:
            self.bookmarks.append(bookmark)
            return True
        logger.info("bookmark %s added", bookmark)
        return False

    def export_rig_remote(self, filename:str):
        """Wrapper method for exporting using rig remote csv format.
        it wraps around the save method used when "save on exit" is selected.
        """

        try:
            self.save(
                bookmarks_file=filename,
                bookmarks=self.bookmarks,
                delimiter=",",
            )
        except ValueError:
            raise BookmarkFormatError

    def export_gqrx(self, filename:str):
        """Wrapper method for exporting using rig remote csv format.
        It wraps around the save method used when "save on exit" is selected
        and around a function that provides the format/data conversion.
        """

        self.io.row_list = self._GQRX_BOOKMARK_HEADER
        self._save_gqrx(filename)

    def _save_gqrx(self, filename):
        """Private method for saving the bookmarks file in csv compatible
        with gqrx bookmark format. It wraps around csv_save method of disk_io
        module.

        :param filename: filename to be saved
        :type filename: string
        """

        for bookmark in self.bookmarks:
            gqrx_bookmark = [
                bookmark.channel.frequency,
                bookmark.description,
                bookmark.channel.modulation,
                "",
                "Untagged",
            ]
            self.io.row_list.append(gqrx_bookmark)

        self.io.row_list.reverse()

        logger.info("saving %i bookmarks", len(self.io.row_list))
        self.io.csv_save(filename, ";")

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

from rig_remote.exceptions import (
    InvalidPathError,
    BookmarkFormatError,
)
from rig_remote.models.channel import Channel
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.modulation_modes import ModulationModes
import logging

from rig_remote.disk_io import IO

from typing import Callable

logger = logging.getLogger(__name__)


def bookmark_factory(
    input_frequency: int | str, modulation: str, description: str, lockout: str = ""
) -> Bookmark:
    return Bookmark(
        channel=Channel(input_frequency=input_frequency, modulation=modulation),
        description=description,
        lockout=lockout,
    )


class BookmarksManager:
    """Implements the bookmarks management."""

    _BOOKMARK_ENTRY_FIELDS = 4

    def __init__(
        self,
        io: IO = IO(),
        bookmark_factory: Callable = bookmark_factory,
        modulation_modes: ModulationModes = ModulationModes,
    ):
        self._io = io
        self.bookmarks = []
        self._bookmark_factory = bookmark_factory
        self._modulation_modes = modulation_modes
        self._IMPORTERS_MAP = {
            "gqrx": self._import_gqrx,
            "rig-remote": self._import_rig_remote,
        }

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

    def save(self, bookmarks_file: str, delimiter: str = ","):
        """Bookmarks handling. Saves the bookmarks as a csv file.

        :param bookmarks_file: filename to load, with full path
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ','
        :raises : none
        :returns : none
        """
        self._io.rows = []

        for bookmark in self.bookmarks:
            self._io.rows.append(
                [
                    bookmark.channel.frequency,
                    bookmark.channel.modulation,
                    bookmark.description,
                    bookmark.lockout,
                ]
            )

        self._io.csv_save(bookmarks_file, delimiter)

    def load(self, bookmark_file: str, delimiter: str = ",") -> list:
        """Bookmarks handling. Loads the bookmarks as
        a csv file.

        :param bookmark_file: filename to load, with full path
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ',''
        :raises : none
        :returns : none
        """
        try:
            self._io.csv_load(bookmark_file, delimiter)
        except InvalidPathError:
            logger.info("No bookmarks file found, skipping.")
            return []
        skipped_count = 0

        for entry in self._io.rows:
            if len(entry) != self._BOOKMARK_ENTRY_FIELDS:
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

    def import_bookmarks(self, filename: str):
        """handles the import of the bookmarks. It is a
        Wrapper around the import funtions and the requester function.

        """
        if not filename:
            logger.info("no filename provided, nothing to import.")
            return None
        return self._IMPORTERS_MAP[self._detect_format(filename)](filename)

    def _detect_format(self, filename: str):
        """Method for detecting the bookmark type. Only two types are supported.

        :param filename: file path to read
        """

        with open(filename, "r") as fn:
            line = fn.readline()
        if self._GQRX_BOOKMARK_FIRST_LINE == line:
            return "gqrx"
        if len(line.split(",")) == 4:
            return "rig-remote"
        message = f"No parser found for filename {filename}"
        logger.error(message)
        raise BookmarkFormatError(message)

    def _import_rig_remote(self, file_path):
        """Imports the bookmarks using rig-remote format. It wraps around
        the load method.

        :param file_path: path o fhte file to import
        """

        return self.load(file_path, ",")

    def _import_gqrx(self, file_path):
        """Method for importing gqrx bookmarks.

        :param file_path: path of the file to be loaded
        """

        self._io.csv_load(file_path, ";")

        count = 0
        bookmarks = []
        for row in self._io.rows:
            count += 1
            if count < self._GQRX_FIRST_BOOKMARK + 1:
                continue
            bookmark = self._bookmark_factory(
                input_frequency=row[0].strip(),
                modulation=self._modulation_modes[row[2].strip().upper()].value,
                description="gqrx_import",
            )
            self.add_bookmark(bookmark)
            bookmarks.append(bookmark)
        return bookmarks

    def delete_bookmark(self, bookmark: Bookmark) -> bool:
        try:
            self.bookmarks.pop(self.bookmarks.index(bookmark))
        except ValueError:
            pass
        logger.info("bookmark %s deleted", bookmark)
        return True

    def add_bookmark(self, bookmark: Bookmark) -> bool:
        if bookmark not in self.bookmarks:
            self.bookmarks.append(bookmark)
            return True
        logger.info("bookmark %s added", bookmark)
        return False

    def export_rig_remote(self, filename: str):
        """Wrapper method for exporting using rig remote csv format.
        it wraps around the save method used when "save on exit" is selected.
        """

        self.save(
            bookmarks_file=filename,
            delimiter=",",
        )

    def export_gqrx(self, filename: str):
        """Wrapper method for exporting using rig remote csv format.
        It wraps around the save method used when "save on exit" is selected
        and around a function that provides the format/data conversion.
        """

        self._io.rows = self._GQRX_BOOKMARK_HEADER
        self._save_gqrx(filename)

    def _save_gqrx(self, filename: str):
        """Private method for saving the bookmarks file in csv compatible
        with gqrx bookmark format. It wraps around csv_save method of disk_io
        module.

        :param filename: filename to be saved
        """

        for bookmark in self.bookmarks:
            gqrx_bookmark = [
                bookmark.channel.frequency,
                bookmark.description,
                bookmark.channel.modulation,
                "",
                "Untagged",
            ]
            self._io.rows.append(gqrx_bookmark)

        self._io.rows.reverse()

        logger.info("saving %i bookmarks", len(self._io.rows))
        self._io.csv_save(filename, ";")

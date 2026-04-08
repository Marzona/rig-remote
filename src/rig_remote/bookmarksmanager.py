"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation


Author: Simone Marzona
form
License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
"""

import logging
from pathlib import Path
from typing import Callable, Union

from rig_remote.exceptions import (
    InvalidPathError,
    BookmarkFormatError,
)
from rig_remote.models.channel import Channel
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.modulation_modes import ModulationModes
from rig_remote.disk_io import IO

logger = logging.getLogger(__name__)


def bookmark_factory(
    input_frequency: int, modulation: str, description: str, lockout: str = "", bookmark_id: str = ""
) -> Bookmark:
    """Create a Bookmark instance from the provided parameters.

    :param input_frequency: The frequency for the bookmark
    :param modulation: The modulation mode
    :param description: The bookmark description
    :param lockout: The lockout status, defaults to empty string
    :returns: A new Bookmark instance
    """
    return Bookmark(
        channel=Channel(input_frequency=input_frequency, modulation=modulation),
        description=description,
        lockout=lockout,
        id=bookmark_id,
    )


class BookmarksManager:
    """Implements the bookmarks management."""

    _BOOKMARK_ENTRY_FIELDS = 5

    def __init__(
        self,
        io: IO = IO(),
        factory: Callable[[int, str, str, str], Bookmark] = bookmark_factory,
    ) -> None:
        self._io = io
        self.bookmarks: list[Bookmark] = []
        self._factory = factory
        self._modulation_modes = ModulationModes
        self._importers_map = {
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

    def save(self, bookmarks_file: str, delimiter: str = ",") -> None:
        """Bookmarks handling. Saves the bookmarks as a csv file.

        :param bookmarks_file: filename to save, with full path
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ','
        """
        self._io.rows = []

        for bookmark in self.bookmarks:
            self._io.rows.append(
                [
                    str(bookmark.channel.frequency),
                    bookmark.channel.modulation,
                    bookmark.description,
                    bookmark.lockout,
                    bookmark.id,
                ]
            )

        self._io.csv_save(bookmarks_file, delimiter)

    def load(self, bookmark_file: str, delimiter: str = ",") -> list[Bookmark]:
        """Bookmarks handling. Loads the bookmarks as
        a csv file.

        :param bookmark_file: filename to load, with full path
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ',''
        :raises : none
        :returns : list of bookmarks loaded
        """
        try:
            self._io.csv_load(bookmark_file, delimiter)
        except InvalidPathError:
            logger.info("No bookmarks file found, skipping.")
            return []
        skipped_count = 0
        id_list = []
        for entry in self._io.rows:
            if len(entry) != self._BOOKMARK_ENTRY_FIELDS:
                logger.info(
                    "skipping line %s as invalid, not enough fields, expecting %i", entry, self._BOOKMARK_ENTRY_FIELDS
                )
                skipped_count += 1
                continue
            if entry[4] in id_list:
                logger.info("skipping line %s as duplicate", entry)
                skipped_count += 1
                continue
            id_list.append(entry[4])

            bookmark = self._factory(
                input_frequency=entry[0],
                modulation=entry[1],
                description=entry[2],
                lockout=entry[3],
                bookmark_id=entry[4],
            )
            self.bookmarks.append(bookmark)
        logger.info("Skipped %i entries", skipped_count)
        return self.bookmarks

    def import_bookmarks(self, filename: str) -> Union[list[Bookmark], None]:
        """handles the import of the bookmarks. It is a
        Wrapper around the import functions and the requester function.

        """
        if not filename:
            logger.info("no filename provided, nothing to import.")
            return None
        return self._importers_map[self._detect_format(filename)](filename)

    def _detect_format(self, filename: str) -> str:
        """Method for detecting the bookmark type. Only two types are supported.

        :param filename: file path to read
        """

        with open(filename, "r") as fn:
            line = fn.readline()
        if self._GQRX_BOOKMARK_FIRST_LINE == line:
            logger.info("detected gqrx bookmark format for file %s", filename)
            return "gqrx"
        if len(line.split(",")) == 5:
            logger.info("detected rig-remote bookmark format for file %s", filename)
            return "rig-remote"
        message = f"No parser found for filename {filename}"
        logger.error(message)
        raise BookmarkFormatError(message)

    def _import_rig_remote(self, file_path: str) -> list[Bookmark]:
        """Imports the bookmarks using rig-remote format. It wraps around
        the load method.

        :param file_path: path of the file to import
        """

        return self.load(file_path, ",")

    def _import_gqrx(self, file_path: str) -> list[Bookmark]:
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
            bookmark = self._factory(
                input_frequency=row[0].strip(),
                modulation=self._modulation_modes[row[2].strip().upper()].value,
                description="gqrx_import",
                lockout="",
            )
            self.add_bookmark(bookmark)
            bookmarks.append(bookmark)
        return bookmarks

    def delete_bookmark(self, bookmark: Bookmark) -> bool:
        """Deletes a bookmark from the list if it exists.

        :param bookmark: The bookmark to delete
        :returns: True if the operation was attempted
        """
        try:
            self.bookmarks.pop(self.bookmarks.index(bookmark))
        except ValueError:
            pass
        logger.info("bookmark %s deleted", bookmark)
        return True

    def add_bookmark(self, bookmark: Bookmark) -> bool:
        """Adds a bookmark to the list if it's not already present.

        :param bookmark: The bookmark to add
        :returns: True if added, False if already exists
        """
        if bookmark not in self.bookmarks:
            self.bookmarks.append(bookmark)
            return True
        logger.info("bookmark %s added", bookmark)
        return False

    def export_rig_remote(self, filename: Path) -> None:
        """Wrapper method for exporting using rig remote csv format.
        It wraps around the save method used when "save on exit" is selected.

        :param filename: destination path for the exported bookmarks
        """

        self.save(
            bookmarks_file=str(filename),
            delimiter=",",
        )

    def export_gqrx(self, filename: Path) -> None:
        """Wrapper method for exporting using gqrx bookmark format.
        It wraps around the save method used when "save on exit" is selected
        and around a function that provides the format/data conversion.

        :param filename: destination path for the exported bookmarks
        """

        self._io.rows = self._GQRX_BOOKMARK_HEADER
        self._save_gqrx(str(filename))

    def _save_gqrx(self, filename: str) -> None:
        """Private method for saving the bookmarks file in csv compatible
        with gqrx bookmark format. It wraps around csv_save method of disk_io
        module.

        :param filename: filename to be saved
        """

        for bookmark in self.bookmarks:
            gqrx_bookmark: list[Union[str, int]] = [
                int(bookmark.channel.frequency),
                bookmark.description,
                bookmark.channel.modulation,
                "",
                "Untagged",
            ]
            self._io.rows.append(gqrx_bookmark)

        self._io.rows.reverse()

        logger.info("saving %i bookmarks", len(self._io.rows))
        self._io.csv_save(filename, ";")

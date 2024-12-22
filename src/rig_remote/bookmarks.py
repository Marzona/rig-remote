#!/usr/bin/env python

# import modules
from rig_remote.disk_io import IO
from rig_remote.constants import (
    LEN_BM,
    BM,
    CBB_MODES,
    GQRX_FIRST_BOOKMARK,
    GQRX_BOOKMARK_FIRST_LINE,
    REVERSE_MODE_MAP,
    GQRX_BOOKMARK_HEADER,
)
from rig_remote.exceptions import (
    InvalidPathError,
    FormatError,
)
from rig_remote.utility import (
    frequency_pp_parse,
    frequency_pp,
)
import logging
import tkinter as tk
from tkinter import messagebox, filedialog
import os

# logging configuration
logger = logging.getLogger(__name__)


# classes definition
class Bookmarks(object):
    """Implements the bookmarks management."""

    def __init__(self, tree, io=IO()):
        self.bookmarks = io
        self.tree = tree

    def save(self, bookmark_file, delimiter=",", silent=False):
        """Bookmarks handling. Saves the bookmarks as
        a csv file.

        :param bookmark_file: filename to load, with full path
        :type bookmark_file: string
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ','
        :type delimiter: string
        :param silent: suppress messagebox
        :type silent: boolean
        :raises : none
        :returns : none
        """

        self.bookmarks.row_list = []
        for item in self.tree.get_children():
            values = self.tree.item(item).get("values")
            values[BM.freq] = str(frequency_pp_parse(values[BM.freq]))
            self.bookmarks.row_list.append(values)
        # Not where we want to do this, and will be fixed with BookmarkSet
        try:
            os.makedirs(os.path.dirname(bookmark_file))
        except IOError:
            logger.info(
                "Error while trying to create bookmark " "path as {}".format(
                    bookmark_file
                )
            )
        except OSError:
            logger.info("The bookmark file already exists.")
        self.bookmarks.csv_save(bookmark_file, delimiter)

    def load(self, bookmark_file, delimiter, silent=False):
        """Bookmarks handling. Loads the bookmarks as
        a csv file.

        :param bookmark_file: filename to load, with full path
        :type bookmark_file: string
        :param delimiter: delimiter to use for creating the csv file,
        defaults to ',''
        :type delimiter: string
        :param silent: suppress messagebox
        :type silent: boolean
        :raises : none
        :returns : none
        """

        if bookmark_file == "noname":
            return

        try:
            self.bookmarks.csv_load(bookmark_file, delimiter)
        except InvalidPathError:
            logger.info("No bookmarks file found, skipping.")
            return
        self._insert_bookmarks(self.bookmarks.row_list)

    def _insert_bookmarks(self, bookmarks, silent=False):
        """Method for inserting bookmark data already loaded.

        :param bookmarks: bookmarks to import in the UI
        :type bookmarks: dict
        """

        count = 0
        for line in bookmarks:
            logger.info(line)
            error = False
            if len(line) < LEN_BM:
                line.append("O")
            if frequency_pp_parse(line[BM.freq]) == None:
                error = True
            try:
                line[BM.freq] = frequency_pp(line[BM.freq])
            except ValueError:
                logger.exception("Malformed bookmark in {}" " skipping...".format(line))
                continue
            if line[BM.mode] not in CBB_MODES:
                error = True
            if error == True:
                if not silent:
                    messagebox.showerror(
                        "Error",
                        "Invalid value in " "Bookmark #%i. " "Skipping..." % count,
                    )
            else:
                item = self.tree.insert("", tk.END, values=line)
                self.bookmark_bg_tag(item, line[BM.lockout])

    def bookmark_bg_tag(self, item, value):
        """Set item background color based on lock status.

        :param value: Locked or unlocked
        :type value: string
        :param item: item in the bookmark tree
        :type item: tree element
        :raises: none
        """

        if value == "L":
            self.tree.tag_configure("locked", background="red")
            self.tree.item(item, tags="locked")
        else:
            self.tree.tag_configure("unlocked", background="white")
            self.tree.item(item, tags="unlocked")

    def import_bookmarks(self, silent=True):
        """handles the import of the bookmarks. It is a
        Wrapper around the import funtions and the requester function.

        :params root: main window
        :type root: tkinter panel
        """

        filename = filedialog.askopenfilename(
            initialdir="~/",
            title="Select bookmark file",
            filetypes=(("csv files", "*.csv"), ("all files", "*.*")),
        )
        if not filename:
            return

        fileformat = self._detect_format(filename)

        if fileformat == "gqrx":
            self._import_gqrx(filename)
            return

        if fileformat == "rig-remote":
            self._import_rig_remote(filename)
            return

        if not silent:
            logger.error(
                "Unsupported format, supported formats are rig-remote"
                "rig-remote and gqrx,"
            )
            messagebox.showerror("Error", "Unsupported file format.")

    def _detect_format(self, filename):
        """Method for detecting the bookmark type. Only two types are supported.

        :param filename: file path to read
        :type filename: string
        """

        if not filename:
            logger.error("No filename passed.")
            raise InvalidPathError

        with open(filename, "r") as fn:
            line = fn.readline()
        if GQRX_BOOKMARK_FIRST_LINE == line:
            return "gqrx"
        if len(line.split(",")) == 4:
            return "rig-remote"
        raise FormatError()

    def _import_rig_remote(self, file_path):
        """Imports the bookmarks using rig-remote format. It wraps around
        the load method.

        :param file_path: path o fhte file to import
        :type file_path: string
        """

        try:
            self.load(file_path, ",", silent=False)
        except ValueError:
            raise FormatError

    def _import_gqrx(self, file_path):
        """Method for importing gqrx bookmarks.

        :param file_path: path of the file to be loaded
        :type file_path: string
        """

        self.bookmarks.csv_load(file_path, ";")

        count = 0
        book = []
        for line in self.bookmarks.row_list:
            count += 1
            if count < GQRX_FIRST_BOOKMARK + 1:
                continue
            try:
                new_line = []
                new_line.append(line[0].strip())
                new_line.append(REVERSE_MODE_MAP[line[2].strip()])
                new_line.append(line[1].strip())
                book.append(new_line)
            except IndexError:
                pass

        self._insert_bookmarks(book)

    def export_rig_remote(self):
        """Wrapper method for exporting using rig remote csv format.
        it wraps around the save method used when "save on exit" is selected.
        """

        filename = self._export_panel()
        try:
            self.save(filename, ",", silent=False)
        except ValueError:
            raise FormatError

    def export_gqrx(self):
        """Wrapper method for exporting using rig remote csv format.
        It wraps around the save method used when "save on exit" is selected
        and around a function that provides the format/data conversion.
        """

        filename = self._export_panel()
        self.bookmarks.row_list = GQRX_BOOKMARK_HEADER
        self._save_gqrx(filename)

    def _save_gqrx(self, filename):
        """Private method for saving the bookmarks file in csv compatible
        with gqrx bookmark format. It wraps around csv_save method of disk_io
        module.

        :param filename: filename to be saved
        :type filename: string
        """

        for item in self.tree.get_children():
            gqrx_bookmark = []
            values = self.tree.item(item).get("values")
            values[BM.freq] = str(frequency_pp_parse(values[BM.freq]))
            gqrx_bookmark.append(values[0])
            gqrx_bookmark.append(values[2])
            gqrx_bookmark.append(values[1])
            gqrx_bookmark.append("")
            gqrx_bookmark.append("Untagged")
            self.bookmarks.row_list.append(gqrx_bookmark)
        # Not where we want to do this, and will be fixed with BookmarkSet
        try:
            os.makedirs(os.path.dirname(filename))
        except IOError:
            logger.info(
                "Error while trying to create bookmark " "path as {}".format(filename)
            )
        except OSError:
            logger.info("The bookmark filef already exists.")
        self.bookmarks.row_list.reverse()
        self.bookmarks.csv_save(filename, ";")

    def _export_panel(self):
        """handles the popup for selecting the path for saving the file."""

        filename = filedialog.asksaveasfilename(
            initialdir="~/",
            title="Select bookmark file",
            initialfile="bookmarks-export.csv",
            filetypes=(("csv", "*.csv"), ("all files", "*.*")),
        )
        return filename

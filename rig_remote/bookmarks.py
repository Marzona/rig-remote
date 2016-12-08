#!/usr/bin/env python

# import modules
from rig_remote.disk_io import IO
from rig_remote.constants import (
                                 SUPPORTED_BOOKMARK_FORMATS,
                                 LEN_BM,
                                 BM,
                                 CBB_MODES,
                                 )
from rig_remote.exceptions import (
                                  UnsupportedBookmarkFormatError,
                                  InvalidPathError,
                                  )
from rig_remote.utility import (
                               frequency_pp_parse,
                               frequency_pp,
                               )
import logging
import Tkinter as tk
import os

# logging configuration
logger = logging.getLogger(__name__)

# classes definition
class Bookmarks(object):
    """Implements the bookmarks management.
    """

    def __init__(self, tree, io = IO()):
        self.bookmarks = io
        self.tree = tree

    def save(self, bookmark_file, delimiter = ',', silent = False):
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
            values = self.tree.item(item).get('values')
            values[BM.freq] = str(frequency_pp_parse(values[BM.freq]))
            self.bookmarks.row_list.append(values)
        # Not where we want to do this, and will be fixed with BookmarkSet
        try:
            os.makedirs(os.path.dirname(bookmark_file))
        except IOError:
            logger.info("Error while trying to create bookmark " \
                        "path as {}".format(bookmark_file))
        except OSError:
            logger.info("The bookmark directory already exists.")
        self.bookmarks.csv_save(bookmark_file, delimiter)

    def load(self, bookmark_file, delimiter, silent = False):
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

        count = 0
        for line in self.bookmarks.row_list:
            count += 1
            error = False
            if len(line) < LEN_BM:
                line.append("O")
            if frequency_pp_parse(line[BM.freq]) == None :
                error = True
            line[BM.freq] = frequency_pp(line[BM.freq])
            if line[BM.mode] not in CBB_MODES :
                error = True
            if error == True :
                if not silent:
                    tkMessageBox.showerror("Error", "Invalid value in "\
                                           "Bookmark #%i. "\
                                           "Skipping..." %count)
            else:
                item = self.tree.insert('', tk.END, values=line)
                self.bookmark_bg_tag(item, line[BM.lockout])

    def bookmark_bg_tag(self, item, value) :
        """Set item background color based on lock status.

        :param value: Locked or unlocked
        :type value: string
        :param item: item in the bookmark tree
        :type item: tree element
        :raises: none
        """

        if value == "L" :
            self.tree.tag_configure('locked', background = 'red')
            self.tree.item(item, tags = "locked")
        else :
            self.tree.tag_configure('unlocked', background = 'white')
            self.tree.item(item, tags = "unlocked")

    def import_bookmarks(self):
        """handles the import of the bookmarks. It is a 
        Wrapper around the import funtions and the requester function.

        :params: none
        :raises: none
        """

        bookmark_format, file_path = self.import_requester()
        call = "_import{}".format(bookmark_format)
        setattr(self, call, bookmark_path)

    def _import_rig_remote(self, file_path):
        """Imports the bookmarks using rig-remote format. It wraps around
        the load method.

        :param file_path: path o fhte file to import
        :type file_path: string
        """

        self.load(file_path, ",", silent = False)

    def _import_gqrx(self, file_path):
        pass

    def _export_rig_remote(self, file_path):
        self.load(file_path, ",", silent = False)

    def _export_gqrx(self, file_path):
        pass

    def export_bookmarks(self):
        """handles the popup for selecting the path and the format.
        """

        bookmark_format, file_path = self.export_requester()
        call = "_export{}".format(bookmark_format)
        setattr(self, call, bookmark_path)

    def import_requester(self):
        """wrapper around requester()
        """

        pass

    def export_requester(self):
        """wrapper around requester()
        """

        pass

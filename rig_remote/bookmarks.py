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

# logging configuration
logger = logging.getLogger(__name__)

# classes definition

class Bookmarks(object):
    """Implements the bookmarks management.
    """

    def __init__(self, tree, io = IO()):
        self.bookmarks = io
        self.tree = tree

    def save(self, bookmark_file, silent = False):
        """Bookmarks handling. Saves the bookmarks as
        a csv file.

        :param filename: filename to load, with full path
        :type filename: string
        :param delimiter: delimiter to use for creating the csv file
        :type delimiter: string
        :param silent: suppress messagebox
        :type silent: boolean
        :raises : none
        :returns : none
        """

        for item in self.tree.get_children():
            values = self.tree.item(item).get('values')
            logger.error("1078")
            values[BM.freq] = str(frequency_pp_parse(values[BM.freq]))
            bookmarks.row_list.append(values)
        # Not where we want to do this, and will be fixed with BookmarkSet
        try:
            os.makedirs(os.path.dirname(bookmarks_file))
        except IOError:
            logger.info("Error while trying to create bookmark " \
                "path as {}".format(bookmarks_file))
        except OSError:
            logger.info("The bookmark directory already exists.")
        bookmarks.csv_save(bookmarks_file, delimiter)

    def load(self, bookmark_file, delimiter, silent = False):
        """Bookmarks handling. Loads the bookmarks as
        a csv file.

        :param filename: filename to load, with full path
        :type filename: string
        :param delimiter: delimiter to use for creating the csv file
        :type delimiter: string
        :param silent: suppress messagebox
        :type silent: boolean
        :raises : none
        :returns : none
        """

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
            logger.error("1058")
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
        """

        bookmark_format, file_path = self.import_requester()
        call = "_import{}".format(bookmark_format)
        setattr(self, call, bookmark_path)

    def _import_rig_remote(self, file_path):
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

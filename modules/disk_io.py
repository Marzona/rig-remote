#!/usr/bin/env python

"""
Remote application that interacts with gqrx using rigctl protocol.
Gqrx partially implements rigctl since version 2.3.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
License: MIT License

Copyright (c) 2014 Rafael Marmelo
"""

import csv
import logging
import os.path
from modules.exceptions import InvalidPathError

# logging configuration
logger = logging.getLogger(__name__)

class IO(object):
    """IO wrapper class

    """
    def __init__(self):
        self.row_list = []

    def _path_check(self, csv_file):
        """Helper function that checks if the path is valid.

        :param csv_file: path
        :type csv_file: string
        :raises InvalidPathError: if the path is invalid
        :returns:none
        """

        if not os.path.exists(csv_file):
            logger.warning("Invalid path provided:{}".format(csv_file))
            raise InvalidPathError


    def csv_load(self, csv_file, delimiter):
        """Read the frequency bookmarks file and populate the tree.

        :param csv_file: path of the file to be written
        :type csv_file: string
        :param delimiter: delimiter char
        :type delimiter: string
        :raises: csv.Error if the data to be written as csv isn't valid
        :returns: none
        """

        self._path_check(csv_file)

        try:
            with open(csv_file, 'r') as data_file:
                reader = csv.reader(data_file, delimiter=delimiter)
                for line in reader:
                    self.row_list.append(line)

        except csv.Error:
            logger.error("The file  provided({})"\
                         " is not a file with values "\
                         "separated by {}.".format(csv_file, delimiter))

        except (IOError, OSError):
            logger.error("Error while trying to read the file: "\
                         "{}".format(csv_file))

    def csv_save(self, csv_file, delimiter):
        """Save current frequencies to disk.

        :param delimiter: delimiter char used in the csv
        :type delimiter: string
        :raises: IOError, OSError
        """

        try:
            with open(csv_file, 'w') as data_file:
                writer = csv.writer(data_file, delimiter=delimiter)
                for row in self.row_list:
                    writer.writerow(row)
        except (IOError, OSError):
            logger.error("Error while trying to write the file: "\
                         "{}".format(csv_file))



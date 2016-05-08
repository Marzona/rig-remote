#!/usr/bin/env python

"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney

TAS - Tim Sweeney - mainetim@gmail.com

2016/02/24 - TAS - Added log file class to handle logging scanning
                   activity to a file.

"""

import csv
import logging
import os.path
from rig_remote.exceptions import InvalidPathError
from rig_remote.constants import BM
import datetime
import time

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
            logger.exception("The file  provided({})"\
                             " is not a file with values "\
                             "separated by {}.".format(csv_file, delimiter))

        except (IOError, OSError):
            logger.exception("Error while trying to read the file: "\
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


class LogFile(object):
    """Handles the a tasks of logging to a file.

    """

    def __init__(self):
        """Defines the log file name and
        sets the fhandler self.log_file to None.
        """

        self.log_filename = None
        self.log_file = None

    def open(self, name = None):
        """Opens a log file.

        :param name: log file name, defaults to None
        :type name: string
        """
        if name != None :
            self.log_filename = name
        try:
            self.log_file = open(self.log_filename, 'a')
        except (IOError, OSError):
            logger.error("Error while trying to open log file: "\
                         "{}".format(self.log_filename))

    def write(self, record_type, record, signal):
        """Writes a message to the log file.

        :param record_type: type of the record to write
        :type record_type: string
        :param record: data to write
        :type record: tuple
        :param signal: signal level
        :type signal: list
        :raises IOError or OSError for any issue that happens while writing.
        """

        if record_type not in ["B","F"]:
            logger.error("Record type not supported, must be 'B' or 'F'"\
                         "got {}".format(record_type))
            raise TypeError

        if record_type == 'B' :
            lstr = 'B ' + str(datetime.datetime.today().strftime\
                              ("%a %Y-%b-%d %H:%M:%S")) + ' ' + \
                record[BM.freq] + ' ' + record[BM.mode] + \
                ' ' + str(signal) + "\n"
        else :
            lstr = 'F ' + str(datetime.datetime.today().strftime\
                              ("%a %Y-%b-%d %H:%M:%S")) + ' ' + \
                str(record['freq']) + ' ' + record['mode'] + \
                ' ' + str(signal) + "\n"
        try:
            self.log_file.write(lstr)
        except AttributeError:
            logger.exception("No log file provided, but log feature selected.")
            raise
        except (IOError, OSError):
            logger.exception("Error while trying to write log file: "\
                         "{}".format(self.log_filename))
        except (TypeError, IndexError):
            logger.exception("At least one of the parameter isn't of the "\
                             "expected type:"\
                             "record_type {},"\
                             "record {},"\
                             "signal {}".format(type(record_type),
                                                type(record),
                                                type(signal)))
            raise

    def close(self):
        """Closes the log file.

        :raises IOError OSError: if there are issues while closing the log file
        """

        if self.log_file != None :
            try:
                self.log_file.close()
            except (IOError, OSError):
                logger.error("Error while trying to close log file: "\
                             "{}".format(self.log_filename))


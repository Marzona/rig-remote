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

TAS - Tim Sweeney - mainetim@gmail.com
"""

import csv
import logging
import os.path
from rig_remote.exceptions import InvalidPathError
import datetime

from rig_remote.models.bookmark import Bookmark

logger = logging.getLogger(__name__)


class IO:
    """IO wrapper class"""

    def __init__(self):
        self.row_list = []

    @staticmethod
    def _path_check(csv_file: str):
        """Helper function that checks if the path is valid.

        :param csv_file: path
        :raises InvalidPathError: if the path is invalid
        :returns:none
        """

        if not os.path.exists(csv_file):
            logger.info("Invalid path provided:%s", csv_file)
            raise InvalidPathError

    def csv_load(self, csv_file: str, delimiter: str):
        """Read the frequency bookmarks file and populate the tree.

        :param csv_file: path of the file to be written
        :param delimiter: delimiter char
        :raises: csv.Error if the data to be written as csv isn't valid

        """
        self._path_check(csv_file)
        logger.info("reading csv file %s with delimiter %s.", csv_file, delimiter)
        with open(csv_file, "r") as data_file:
            self.row_list = []
            reader = csv.reader(data_file, delimiter=delimiter)
            for line in reader:
                self.row_list.append(line)
        logger.info("loaded %i rows from csv %s", len(self.row_list), csv_file)

    def csv_save(self, csv_file: str, delimiter: str):
        """Save current frequencies to disk.

        :param delimiter: delimiter char used in the csv
        :raises: IOError, OSError
        """
        count = 0
        try:
            with open(csv_file, "w") as data_file:
                writer = csv.writer(data_file, delimiter=delimiter)
                while self.row_list:
                    count += 1
                    writer.writerow(self.row_list.pop())
        except (IOError, OSError):
            logger.error("Error while trying to write the file: %a", csv_file)
            self.row_list = []
            self.test = "test"
        logger.info("saved %i rows", count)


class LogFile:
    """Handles the tasks of logging to a file."""

    def __init__(self):
        """Defines the log file name and
        sets the fhandler self.log_file to None.
        """

        self.log_filename = None
        self.log_file = None

    def open(self, name: str = None):
        """Opens a log file.

        :param name: log file name, defaults to None
        """
        if name is not None:
            self.log_filename = name
        try:
            os.makedirs(os.path.dirname(self.log_filename))
        except IOError:
            logger.info(
                "Error while trying to create log file path as %s", self.log_filename
            )
        try:
            self.log_file = open(self.log_filename, "a")
        except (IOError, OSError):
            logger.error("Error while trying to open log file: %s", self.log_filename)

    def write(self, record_type: str, record: Bookmark, signal: list):
        """Writes a message to the log file.

        :param record_type: type of the record to write
        :param record: data to write
        :param signal: signal level
        :raises IOError or OSError for any issue that happens while writing.
        """

        if record_type not in ["B", "F"]:
            logger.error(
                "Record type not supported, must be 'B' or 'F'" "got %s", record_type
            )
            raise TypeError

        if record_type == "B":
            lstr = (
                "B "
                + str(datetime.datetime.today().strftime("%a %Y-%b-%d %H:%M:%S"))
                + " "
                + record.channel.frequency
                + " "
                + record.channel.modulation
                + " "
                + str(signal)
                + "\n"
            )
        else:
            lstr = (
                "F "
                + str(datetime.datetime.today().strftime("%a %Y-%b-%d %H:%M:%S"))
                + " "
                + str(record.channel.frequency)
                + " "
                + record.channel.modulation
                + " "
                + str(signal)
                + "\n"
            )
        try:
            self.log_file.write(lstr)
        except AttributeError:
            logger.exception("No log file provided, but log feature selected.")
            raise
        except (IOError, OSError):
            logger.exception(
                "Error while trying to write log file: %s", self.log_filename
            )
        except (TypeError, IndexError):
            logger.exception(
                "At least one of the parameter isn't of the "
                "expected type: record_type %s, record %s, signal %s",
                type(record_type),
                type(record),
                type(signal),
            )
            raise

    def close(self):
        """Closes the log file.

        :raises IOError OSError: if there are issues while closing the log file
        """

        if self.log_file is not None:
            try:
                self.log_file.close()
            except (IOError, OSError):
                logger.error(
                    "Error while trying to close log file: %s", self.log_filename
                )

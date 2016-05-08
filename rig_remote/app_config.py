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

2016/03/21 - TAS - Validate config file entries on read.

"""

# import modules

from rig_remote.disk_io import IO
from rig_remote.constants import DEFAULT_CONFIG
import logging
import os

# logging configuration
logger = logging.getLogger(__name__)

class AppConfig(object):
    """This class reads the status of the UI and and parses the data
    so that it's suitable to be saved as a csv, and the reverse

    """

    def __init__(self, alternate_config_file):
        """Default config, they will be overwritten when a conf is loaded
        this will be used to write a default config file.
        If the command line specifies a config file we note it in
        alternate_config_file and we use it, otherwise we check for
        the default one.

        :param alternate_config_file: config file passed as input argument
        :type alternate_config_file: string
        :raises: none
        :returns:none
        """

        self.old_path = False
        self.io = IO()
        self.default_config_file = ".rig-remote/rig-remote.conf"
        self.config_file = None
        self.config = dict.copy(DEFAULT_CONFIG)

        if alternate_config_file:
            self.config_file = alternate_config_file
        else:
            logger.info("No custom config file specified...")
            self.config_file = os.path.join(os.path.expanduser('~'),
                                            self.default_config_file)

    def read_conf(self):
        """Read the configuration file.
        If the default one doesn't exist we create one with sane values.
        and then we re-read it. It logs an error if a line of the file is not
        valid and moves on to the next one.

        :param: none
        :raises: none
        :returns: none
        """
        if os.path.isfile(self.config_file):
            logger.info("Using config file:{}".format(self.config_file))
            self.io.csv_load(self.config_file, "=")
            error = 0
            for row in self.io.row_list:
                if len(row) == 2 and row[0].strip() in self.config.keys() :
                    self.config[row[0].strip()] = row[1].strip()
                else:
                    logger.warning("Error in config file line: " + str(row))
        else:
            self.write_conf()
            self.read_conf()

    def write_conf(self):
        """Writes the configuration to file. If the default config path
        is missing it will be created. If this is not possible the config file
        will not be saved.

        :param: none
        :raises: IOError, OSError if it is not possible to write the config
        :returns: none
        """

        self.io.row_list = []
        # checking the directory path for default config file
        if self.old_path:
            self.old_pathname = self.config_file
            self.config_file = os.path.join(os.path.expanduser('~'), self.default_config_file)
        try:
            os.makedirs(os.path.dirname(self.config_file))
        except IOError:
            logger.info("Error while trying to create default config "\
                              "path as {}".format(self.config_file))
        except OSError:
            logger.info("The default config directory already exists.")
        if self.old_path:
            try:
                os.remove(self.old_pathname)
            except OSError:
                logger.info("Could not remove old config file.")
            try:
                os.rmdir(os.path.dirname(self.old_pathname))
            except OSError:
                logger.info("Could not remove old config directory.")
        for key in self.config.keys():
            row = []
            row.append(key)
            row.append(self.config[key])
            self.io.row_list.append(row)
        self.io.csv_save(self.config_file, "=")


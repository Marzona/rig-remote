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
2016/05/30 - TAS - Config path now established in main module. Stripped out old file support.

"""

# import modules

from rig_remote.disk_io import IO
from rig_remote.constants import (
                                  DEFAULT_CONFIG,
                                  RIG_URI_CONFIG,
                                  MONITOR_CONFIG,
                                  SCANNING_CONFIG,
                                  MAIN_CONFIG,
                                  CONFIG_SECTIONS,
                                  UPGRADE_MESSAGE,
                                  )
import logging
import os
import sys
import ConfigParser
from rig_remote.exceptions import (
                                   NonRetriableError,
                                  )

# logging configuration
logger = logging.getLogger(__name__)


# class definition
class AppConfig(object):
    """This class reads the status of the UI and and parses the data
    so that it's suitable to be saved as a csv, and the reverse

    """

    def __init__(self, config_file):
        """Default config, they will be overwritten when a conf is loaded
        this will be used to write a default config file.
        If the command line specifies a config file we note it in
        alternate_config_file and we use it, otherwise we check for
        the default one.

        :param config_file: config file passed as input argument
        :type config_file: string
        :raises: none
        :returns:none
        """

        self.io = IO()
        self.config_file = config_file
        if not self.config_file:
            self.config = dict.copy(DEFAULT_CONFIG)
        else:
            self.config = {}

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

            config = ConfigParser.RawConfigParser()
            try:
                config.read(self.config_file)
            except ConfigParser.MissingSectionHeaderError:
                    logger.error("Missing Sections in the config file.")
                    logger.error(UPGRADE_MESSAGE)
                    sys.exit(1)
            except ConfigParser.Error:
                    logger.exception("Error while loading"
                                     "{}".format(self.config_file))

            if config.sections == []:
                logger.info("Config file needs to be upgraded.")
                logger.info("Please execute the config-updater.")
                raise NonRetriableError
            for section in config.sections():
                for item in config.items(section):
                    self.config[item[0]] = item[1]
        else:
            self.config = DEFAULT_CONFIG

    def write_conf(self):
        """Writes the configuration to file. If the default config path
        is missing it will be created. If this is not possible the config file
        will not be saved.

        :param: none
        :raises: IOError, OSError if it is not possible to write the config
        :returns: none
        """

        self.io.row_list = []
        try:
            os.makedirs(os.path.dirname(self.config_file))
        except IOError:
            logger.info("Error while trying to create config "
                        "path as {}".format(self.config_file))
        except OSError:
            logger.info("The config directory already exists.")
        config = ConfigParser.RawConfigParser()
        for section in CONFIG_SECTIONS:
            config.add_section(section)

        for key in self.config.keys():
            if key in RIG_URI_CONFIG:
                config.set("Rig URI", key, self.config[key])
            if key in MONITOR_CONFIG:
                config.set("Monitor", key, self.config[key])
            if key in MAIN_CONFIG:
                config.set("Main", key, self.config[key])
            if key in SCANNING_CONFIG:
                config.set("Scanning", key, self.config[key])

        with open(self.config_file, "wb") as cf:
            config.write(cf)

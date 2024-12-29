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

import configparser
import logging
import os
import sys

from rig_remote.constants import (
    RIG_URI_CONFIG,
    MONITOR_CONFIG,
    SCANNING_CONFIG,
    MAIN_CONFIG,
    CONFIG_SECTIONS,
)
from rig_remote.disk_io import IO
from rig_remote.exceptions import NonRetriableError
from rig_remote.models.rig_endpoint import RigEndpoint

logger = logging.getLogger(__name__)


class AppConfig:
    """This class reads the status of the UI and and parses the data
    so that it's suitable to be saved as a csv, and the reverse

    """

    DEFAULT_CONFIG = {
        "hostname1": "127.0.0.1",
        "port1": "7356",
        "hostname2": "127.0.0.1",
        "port2": "7357",
        "interval": "1",
        "delay": "5",
        "passes": "0",
        "sgn_level": "-30",
        "range_min": "24,000",
        "range_max": "1800,000",
        "wait": "false",
        "record": "false",
        "log": "false",
        "always_on_top": "true",
        "save_exit": "false",
        "aggr_scan": "false",
        "auto_bookmark": "false",
        "log_filename": None,
        "bookmark_filename": None,
    }
    _UPGRADE_MESSAGE = (
        "This config file may deserve an "
        "upgrade, please execute the "
        "following comand: "
        "python ./config_checker.py -uc ~/.rig-remote/ or "
        "Check https://github.com/Marzona/rig-remote/wiki/User-Manual#config_checker "
        "for more info."
    )

    def __init__(self, config_file: str):
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
        self.rig_endpoints = []
        self.config_file = config_file
        if not self.config_file:
            self.config = dict.copy(self.DEFAULT_CONFIG)
        else:
            self.config = {}

    def read_conf(self):
        """Read the configuration file.
        If the default one doesn't exist we create one with sane values.
        and then we re-read it. It logs an error if a line of the file is not
        valid and moves on to the next one.

        """

        if os.path.isfile(self.config_file):
            logger.info("Using config file:{}".format(self.config_file))
            config = configparser.RawConfigParser()
            try:
                config.read(self.config_file)
            except configparser.MissingSectionHeaderError:
                logger.errorshutdown("Missing Sections in the config file.")
                logger.error(self._UPGRADE_MESSAGE)
                sys.exit(1)
            except configparser.Error:
                logger.exception("Error while loading" "{}".format(self.config_file))

            if not config.sections:
                logger.info("Config file needs to be upgraded.")
                logger.info("Please execute the config-updater.")
                raise NonRetriableError
            for section in config.sections():
                for item in config.items(section):
                    self.config[item[0]] = item[1]
        else:
            logger.info("Using default configuration...")
            self.config = self.DEFAULT_CONFIG

        # generate the rig endpoints from config
        self.rig_endpoints = [
            RigEndpoint(
                hostname=self.config["hostname{}".format(instance_number)],
                port=int(self.config["port{}".format(instance_number)]),
                rig_number=instance_number,
            )
            for instance_number in (1, 2)
        ]

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
            logger.info(
                "Error while trying to create config " "path as {}".format(
                    self.config_file
                )
            )
        except OSError:
            logger.info("The config directory already exists.")
        config = configparser.RawConfigParser()
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

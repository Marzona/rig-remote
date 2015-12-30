#!/usr/bin/env python

# import modules

from modules.disk_io import IO
from modules.constants import DIRMODE
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

        self.io= IO()
        self.default_config_file = ".gqrx-remote/gqrx-remote.conf"
        self.config_file = None
        self.config = {}
        self.config["hostname"] = "127.0.0.1"
        self.config["port"] = "7356"
        self.config["interval"] = "15"
        self.config["delay"] = "5"
        self.config["sgn_level"] = "25"
        self.config["range_min"] = "24"
        self.config["range_max"] = "1800"
        self.config["always_on_top"] = "True"
        self.config["save_exit"] = "False"
        self.config["auto_bookmark"] = "False"

        if alternate_config_file:
            self.config_file = alternate_config_file
        else:
            logger.info("No custom config file specified...")
            self.config_file = os.path.join(os.path.expanduser('~'),
                                            self.default_config_file)

    def read_conf(self):
        """Read the configuration file. 
        If the default one doesn't exist we create one with sane values.
        and then we re-read it.

        :param: none
        :raises: none
        :returns: none
        """

        if os.path.isfile(self.config_file):
            logger.info("Using config file:{}".format(self.config_file))
            self.io.csv_load(self.config_file, "=")
            for row in self.io.row_list:
                self.config[row[0].strip()]=row[1].strip()
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
        try:
            os.makedirs(os.path.dirname(self.config_file))
        except IOError:
            logger.exception("Error while trying to create default config "\
                              "path as {}".format(self.config_file))
        except (OSError, FileExistError):
            logger.warning("The default config directory already exists..")

        for key in self.config.keys():
            row=[]
            row.append(key)
            row.append(self.config[key])
            self.io.row_list.append(row)
        self.io.csv_save(self.config_file, "=")

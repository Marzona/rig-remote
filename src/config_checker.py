#!/usr/bin/env python
"""
Utility for
- updating rig-remote config file to the last supported version.
- checking the sanity of the bookmarks file
- checking the sanity of the config file

Please refer to:
https://github.com/Marzona/rig-remote/blob/master/rig_remote
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Simone Marzona <rafael@defying.me>

License: MIT License

Copyright (c) 2015 Simone Marzona
"""


# import modules
import os
import csv
import shutil
import configparser
import platform
import argparse
import logging
import pprint
from os.path import expanduser
from rig_remote.constants import (
                                  DEFAULT_CONFIG,
                                  RIG_URI_CONFIG,
                                  MONITOR_CONFIG,
                                  SCANNING_CONFIG,
                                  MAIN_CONFIG,
                                  CONFIG_SECTIONS,
                                  )
# helper functions

# logging configuration
logger = logging.getLogger(__name__)

def input_arguments():
    """Argument parser.

    """

    parser = argparse.ArgumentParser(
        description=(
            "Utility to check the configuration files and to update"\
            " them to the last version."),
        epilog="""Please refer to:
        https://github.com/Marzona/rig-remote/wiki
        http://gqrx.dk/,
        http://gqrx.dk/doc/remote-control,
        http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

        Author: Simone Marzona <marzona@knoway.info>

        License: MIT License

        Copyright (c) 2017 Simone Marzona""")

    parser.add_argument("--check_config",
                        "-cc",
                        type=str,
                        required=False,
                        dest="check_config",
                        help="Path of the config folder we want to "\
                             "check.",
                        )
    parser.add_argument("--dump",
                        "-d",
                        required=False,
                        dest="dump",
                        action="store_true",
                        help="Dump some useful info for debugging.",
                       )
    parser.add_argument("--update_config",
                        "-uc",
                        required=False,
                        type=str,
                        dest="update_config",
                        help="Path of the folder we want to update."\
                             "The config file will be overwritten "\
                             "and a .back file will be created too."
                       )


    return parser.parse_args()

def dump_info():
    """Dumps some info regarding the environment we are running in.
    The intended use is to ask the user to paste this info for
    troubleshooting steps.

    """

    print("Python version: {}".format(platform.python_version()))
    print("\n   ")
    print("System's release version: {}".format(platform.version()))
    print("\n   ")
    print("Platform: {}".format(platform.platform()))
    print("\n   ")
    print("OS environment: {}".format(platform.os.environ))
    print("\n   ")
    print("Platform architecture: {}".format(platform.architecture()))
    print("\n   ")
    print("Linux distrubition name: {}".format(platform.dist()))
    print("\n   ")
    print("System/OS name: {}".format(platform.system()))

def update_config(config):
    config_file = os.path.join(config, "rig-remote.conf")
    config = configparser.RawConfigParser()
    for section in CONFIG_SECTIONS:
        config.add_section(section)
    with open(config_file, "r") as cf:
        print("Using config file:{}".format(config_file))
        for line in cf:
            line = line.rstrip("\n")
            if line.split("=")[0].strip() in RIG_URI_CONFIG:
                config.set("Rig URI", line.split("=")[0], line.split("=")[1])
            if line.split("=")[0].strip() in MONITOR_CONFIG:
                config.set("Monitor", line.split("=")[0], line.split("=")[1])
            if line.split("=")[0].strip() in MAIN_CONFIG:
                config.set("Main", line.split("=")[0], line.split("=")[1])
            if line.split("=")[0].strip() in SCANNING_CONFIG:
                config.set("Scanning", line.split("=")[0], line.split("=")[1])

    shutil.copyfile(config_file, "{}.back".format(config_file))
    with open(config_file, "wb") as cf:
        config.write(cf)

def check_config(config):

    config_file = os.path.join(config, "rig-remote.conf")

    with open(config_file, "r") as cf:
        print("Using config file:{}".format(config_file))
        count = 0
        config_data = []
        for row in cf:
            row = row.rstrip("\n")
            if "bookmark_filename" in row:
                bookmark_file = row.split("=")[1].rstrip("'").strip()
            if any (["[" in row,
                     "#" in row,
                     "\n" == row,
                     "" == row]):
                continue
            count += 1
            if len(row.split("=")) == 2:
                config_data.append(row)
            else:
                print("Error in config file, line: {}".format(row))
        if count < 19:
            print("The configuration file seems to be "\
                           "missing some keyword")
        print("\n   ")
        print("Config dump:")
        pprint.pprint(config_data)
        print("\n   ")
        print ("Bookmarks info:")
        if bookmark_file:
            with open(bookmark_file, "r") as bf:
                row_list = []
                reader = csv.reader(bf, delimiter=",")
                for line in reader:
                    if len(line)!=4:
                        print("Bookmark line malformed: {}".format(line))
                    row_list.append(line)
            print("\n   ")
            pprint.pprint(row_list)



# entry point
if __name__ == "__main__":
    args = input_arguments()
    if not any([args.check_config, args.dump, args.update_config]):
        print("At least one option is required, try "\
                    "config_checker --help")

    if args.dump:
        dump_info()
    elif args.update_config:
        update_config(args.update_config)
    elif args.check_config:
        check_config(args.check_config)

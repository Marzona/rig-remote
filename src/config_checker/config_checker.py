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

import os
import csv
import platform
import argparse
import logging
import pprint
from rig_remote.app_config import AppConfig

logger = logging.getLogger(__name__)


def input_arguments():
    """Argument parser.

    """

    parser = argparse.ArgumentParser(
        description=(
            "Utility to check the configuration files and collect system's information"),
        epilog="""Please refer to:
        https://github.com/Marzona/rig-remote/wiki
        http://gqrx.dk/,
        http://gqrx.dk/doc/remote-control,
        http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

        Author: Simone Marzona <marzona@knoway.info>

        License: MIT License

        Copyright (c) 2017 Simone Marzona""")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check_config",
                       "-cc",
                       type=str,
                       dest="check_config",
                       help="Path of the config folder we want to " \
                            "check, example ~/.rig-remote/",
                       )
    group.add_argument("--dump",
                       "-d",
                       dest="dump",
                       action="store_true",
                       help="Dump system info for debugging.",
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
    print("Linux distrubition name: {}".format(platform.freedesktop_os_release()))
    print("\n   ")
    print("System/OS name: {}".format(platform.system()))

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
            if any(["[" in row,
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
            print("The configuration is " \
                  "missing some keyword")
        print("\n   ")
        print("Config dump:")
        pprint.pprint(config_data)
        print("\n   ")
        print("Bookmarks info:")
        if bookmark_file:
            with open(bookmark_file, "r") as bf:
                row_list = []
                reader = csv.reader(bf, delimiter=",")
                for line in reader:
                    if len(line) != 4:
                        print("Bookmark line malformed: {}".format(line))
                    row_list.append(line)
            print("\n   ")
            pprint.pprint(row_list)

        print("Parsing configuration file: {}".format(config_file))
        ac=AppConfig(config_file=config_file)
        try:
            ac.read_conf()
            print("Configuration file is valid.")
            return True
        except SystemExit as e:
            print("Error reading configuration file: {}".format(e))
            print("Please check the configuration file for errors.")
            return False
        except Exception as e:
            print("Unexpected error: {}".format(e))
            return False

# entry point
def cli():
    args = input_arguments()
    if not any([args.check_config, args.dump]):
        print("At least one option is required, try " \
              "config_checker --help")

    if args.dump:
        dump_info()
    elif args.check_config:
        check_config(args.check_config)
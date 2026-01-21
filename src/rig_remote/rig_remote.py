#!/usr/bin/env python

"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
Author: Simone Marzona <rafael@defying.me>

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
"""

import argparse
import os
import sys
import textwrap
from logging import Logger

from rig_remote.ui_qt import RigRemote
from rig_remote.app_config import AppConfig
from PySide6 import QtWidgets

# helper functions
def input_arguments()->argparse.Namespace:
    """Argument parser.

    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(textwrap.fill(
            "Rig controller that interacts with a rig using the rigctl protocol.\
             ")),
        epilog="""Please refer to:
        https://github.com/Marzona/rig-remote/wiki
        http://gqrx.dk/,
        http://gqrx.dk/doc/remote-control,
        http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

        Author: Simone Marzona <marzona@knoway.info>
        Additional features: Tim Sweeney <mainetim@"GEE"mail.com>

        License: MIT License

        Copyright (c) 2015 Simone Marzona
        Copyright (c) 2016 Tim Sweeney""")

    parser.add_argument("--bookmarks",
                        "-b",
                        type=str,
                        required=False,
                        dest="alternate_bookmark_file",
                        help="Sets the full path for the bookmark file.")

    parser.add_argument("--config",
                        "-c",
                        type=str,
                        required=False,
                        dest="alternate_config_file",
                        help="Sets the full path for the config file.")

    parser.add_argument("--log",
                        "-l",
                        type=str,
                        required=False,
                        dest="alternate_log_file",
                        help="Sets the full path for the activity log file.")

    parser.add_argument("--prefix",
                        "-p",
                        type=str,
                        required=False,
                        dest="alternate_prefix",
                        help="Sets the directory prefix for default working files. " +
                        "NOTE: Individual path options override this prefix.")

    parser.add_argument("--verbose",
                        "-v",
                        dest="verbose",
                        action="store_true",
                        help="Increase log verbosity.")

    return parser.parse_args()

def log_configuration(verbose: bool)->Logger:
    """
    Configure logging and return the root logger with an explicit level set.
    Ensures time.tzset is called if available and that handlers use the same level.
    """
    import logging
    import time

    level = logging.INFO if verbose else logging.WARNING
    logger = logging.getLogger()  # root logger
    logger.setLevel(level)

    # Call tzset if available (harmless)
    try:
        if hasattr(time, "tzset"):
            time.tzset()
    except Exception:
        pass

    # Ensure at least one handler exists and synchronize handler levels
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        for h in logger.handlers:
            try:
                h.setLevel(level)
            except Exception:
                pass

    return logger


def process_path(path:str)->str:
    """Handle tilde expansion in a path.

    :param path: path to expand
    """

    working_path, working_name = os.path.split(path)
    if working_path:
        working_path = os.path.expanduser(working_path)
    return os.path.join(working_path, working_name)


# entry point
def cli()->None:
    DEFAULT_PREFIX = os.path.expanduser("~/.rig-remote")
    DEFAULT_CONFIG_FILENAME = "rig-remote.conf"
    DEFAULT_LOG_FILENAME = "rig-remote-log.txt"
    DEFAULT_BOOKMARK_FILENAME = "rig-remote-bookmarks.csv"

    args = input_arguments()
    log_configuration(args.verbose)
    if args.alternate_prefix:
        prefix = args.alternate_prefix
        dir_prefix = os.path.expanduser(prefix)
    else:
        dir_prefix = DEFAULT_PREFIX
    if args.alternate_config_file:
        conf = args.alternate_config_file
        config_file = process_path(conf)
    else:
        config_file = os.path.join(dir_prefix, DEFAULT_CONFIG_FILENAME)

    app_config = AppConfig(config_file=config_file)
    # set bookmarks and log filename in this order:
    #   use command line alternate path
    #   use path from config file
    #   use default path
    app_config.read_conf()

    if args.alternate_bookmark_file is not None:
        bookmarks = args.alternate_bookmark_file
        app_config.config['bookmark_filename'] = process_path(bookmarks)
    elif app_config.config["bookmark_filename"] is None:
        app_config.config["bookmark_filename"] = os.path.join(dir_prefix, DEFAULT_BOOKMARK_FILENAME)
    # set activity log filename
    if args.alternate_log_file is not None:
        log = args.alternate_log_file
        app_config.config['log_filename'] = process_path(log)
    else:
        app_config.config['log_filename'] = os.path.join(dir_prefix, DEFAULT_LOG_FILENAME)

    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(True)
    window = RigRemote(app_config)
    window.resize(1024, 978)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    cli()
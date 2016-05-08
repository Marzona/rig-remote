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
import logging
import os
import time
import textwrap
import Tkinter as tk
from rig_remote.ui import RigRemote
from rig_remote.app_config import AppConfig
from rig_remote.utility import this_file_exists

def input_arguments():
    """Argument parser.

    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(textwrap.fill(
            "Remote app that interacts with a rig using the rigctl protocol.\
             Gqrx partially implements rigctl since version 2.3")),
        epilog="""Please refer to:
        http://gqrx.dk/,
        http://gqrx.dk/doc/remote-control,
        http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

        Author: Rafael Marmelo <rafael@defying.me>
        Author: Simone Marzona
        Additional features: Tim Sweeney <mainetim@"GEE"mail.com>

        License: MIT License

        Copyright (c) 2014 Rafael Marmelo
        Copyright (c) 2015 Simone Marzona
        Copyright (c) 2016 Tim Sweeney""")

    parser.add_argument("--bookmarks",
                        "-b",
                        type=str,
                        required=False,
                        dest="alternate_bookmark_file",
                        help="Overrides the default bookmark file.")

    parser.add_argument("--config",
                        "-c",
                        type=str,
                        required=False,
                        dest="alternate_config_file",
                        help="Overrides the default config file.")

    parser.add_argument("--log",
                        "-l",
                        type=str,
                        required=False,
                        dest="alternate_log_file",
                        help="Overrides the default log file.")

    parser.add_argument("--verbose",
                        "-v",
                        dest="verbose",
                        action="store_true",
                        help="Increase log verbosity.")

    return parser.parse_args()

def log_configuration(verbose):
    """Logger configuration: time/date formatting.

    """

    os.environ["TZ"] = "UTC"

    # Windows doesn't support tzset. Ignore for now.
    try:
        time.tzset()
    except AttributeError:
        pass

    if verbose:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z")
    else:
        logging.basicConfig(level=logging.WARNING,
                            format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z")

    return logging.getLogger(__name__)

def find_existing_bookmarks_file():
    """ See if we have an existing bookmark file, including defaults from
        previous versions.
        :returns: filename if an existing file is found, None otherwise.
        """

    filename = this_file_exists(os.path.join(os.getcwd(),'rig-bookmarks.csv'))
    if filename: return filename
    filename = this_file_exists(os.path.join(os.path.expanduser('~'),
                                            '.rig-remote/rig-bookmarks.csv'))
    return filename

def get_bookmarks_filename(filename):
    if filename == 'noname':
        filename = find_existing_bookmarks_file()
        if not filename:
            filename = os.path.join(os.path.expanduser('~'),
                                            '.rig-remote/rig-remote-bookmarks.csv')
    return filename

# entry point
if __name__ == "__main__":

    args = input_arguments()
    logger = log_configuration(args.verbose)

    config_file = args.alternate_config_file
    if not config_file:
        config_file = this_file_exists(os.path.join(os.path.expanduser('~'),
                                                    '.rig_remote/rig_remote.conf'))
    root = tk.Tk()
    ac = AppConfig(config_file)
    # set bookmarks filename in this order:
    #   use command line alternate path
    #   use path from config file
    #   use path of existing file found
    #   use default path
    if args.alternate_bookmark_file:
        ac.config['bookmark_filename'] = args.alternate_bookmark_file
    else:
        ac.config['bookmark_filename'] = get_bookmarks_filename(ac.config['bookmark_filename'])
    #set activity log filename
    if args.alternate_log_file:
        ac.config['log_filename'] = args.alternate_log_file
    elif ac.config['log_filename'] == 'noname':
        ac.config['log_filename'] = os.path.join(os.path.expanduser('~'),
                                            '.rig-remote/rig-remote-log.txt')
    if args.alternate_config_file:
        ac.config['alternate_config_file'] = True
    if args.alternate_bookmark_file:
        ac.config['alternate_bookmark_file'] = True
    if args.alternate_log_file:
        ac.config['alternate_log_file'] = True
    app = RigRemote(root, ac)
    app.apply_config(ac)
    app.mainloop()
    if app.scan_thread != None :
        app.scanning.terminate()

#!/usr/bin/env python3

"""
Remote application that interacts with gqrx using rigctl protocol.
Gqrx partially implements rigctl since version 2.3.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
License: MIT License

Copyright (c) 2014 Rafael Marmelo
"""

import argparse
import logging
import os
import time
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox
from modules.ui import GqrxRemote
from modules.app_config import AppConfig


def input_arguments():
    parser = argparse.ArgumentParser(
        description="""Remote application 
        that interacts with gqrx using
        rigctl protocol.
        Gqrx partially implements rigctl 
        since version 2.3""",
        epilog="""Please refer to:
        http://gqrx.dk/,
        http://gqrx.dk/doc/remote-control,
        http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

        Author: Rafael Marmelo <rafael@defying.me>
        License: MIT License

        Copyright (c) 2014 Rafael Marmelo""")

    parser.add_argument("--file",
                        "-f",
                        type=str,
                        required=False,
                        dest="alternate_config_file",
                        help="Overrides the default config file.")

    parser.add_argument("--verbose",
                        "-v",
                        dest="verbose",
                        action="store_true",
                        help="Increase log verbosity.")

    args = parser.parse_args()
    return args

def log_configuration(verbose):
    os.environ["TZ"] = "UTC"
    time.tzset()
    if verbose:
        logging.basicConfig(format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z",
                            level=logging.WARNING)
    else:
        logging.basicConfig(format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z",
                            level=logging.INFO)
    logging.Formatter.converter = time.utctime

# entry point
if __name__ == "__main__":

    args = input_arguments()
    log_configuration(args.verbose)
    logger = logging.getLogger(__name__)

    config_file = args.alternate_config_file
    root = tk.Tk()
    ac = AppConfig(config_file)
    app = GqrxRemote(root, ac)
    app.mainloop()

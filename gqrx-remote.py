#!/usr/bin/env python

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
import Tkinter as tk
from modules.ui import GqrxRemote
from modules.app_config import AppConfig


def input_arguments():
    """Argument parser.

    """

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

    return parser.parse_args()

def log_configuration(verbose):
    """Logger configuration: time/date formatting.

    """

    os.environ["TZ"] = "UTC"
    time.tzset()
    if verbose:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z")
    else:
        logging.basicConfig(level=logging.WARNING,
                            format="%(asctime)s %(message)s",
                            datefmt="%m/%d/%Y %I:%M:%S %p %Z")

    return logging.getLogger(__name__)

# entry point
if __name__ == "__main__":

    args = input_arguments()
    logger = log_configuration(args.verbose)

    config_file = args.alternate_config_file
    root = tk.Tk()
    ac = AppConfig(config_file)
    app = GqrxRemote(root, ac)
    app.apply_config(ac)
    app.mainloop()

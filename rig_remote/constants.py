#!/usr/bin/env python
"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://rig.dk/
http://rig.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
"""

CBB_MODES = (
    "",
    "AM",
    "FM",
    "WFM",
    "WFM_ST",
    "LSB",
    "USB",
    "CW",
    "CWL",
    "CWU",
)


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

LEN_BM = 4


class BM:
    """Helper class with 4 attribs."""

    freq, modulation, desc, lockout = range(LEN_BM)


SCANNING_CONFIG = [
    "range_min",
    "range_max",
    "delay",
    "interval",
    "auto_bookmark",
    "sgn_level",
    "wait",
    "record",
    "aggr_scan",
    "passes",
]
MAIN_CONFIG = ["always_on_top", "save_exit", "bookmark_filename", "log", "log_filename"]
MONITOR_CONFIG = ["monitor_mode_loops"]
RIG_URI_CONFIG = ["port1", "hostname1", "port2", "hostname2"]
CONFIG_SECTIONS = [
    "Scanning",
    "Main",
    "Rig URI",
    "Monitor",
]

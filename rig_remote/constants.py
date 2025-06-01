"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://rig.dk/
http://rig.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation


Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
"""

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

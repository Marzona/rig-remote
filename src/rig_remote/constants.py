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

# Number of fields in a bookmark record (frequency, modulation, description, lockout)
LEN_BM = 4

# Upper bound for valid rig frequencies (500 MHz)
MAX_FREQUENCY_HZ = 500_000_000

# Log record type identifiers used in activity log files
LOG_RECORD_BOOKMARK = "B"
LOG_RECORD_FREQUENCY = "F"


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
    "inner_band",
    "inner_interval",
]
MAIN_CONFIG = ["always_on_top", "save_exit", "bookmark_filename", "log", "log_filename"]
MONITOR_CONFIG = ["monitor_mode_loops"]
RIG_COUNT = 2
RIG_URI_CONFIG = [f"{k}{r+1}" for r in range(RIG_COUNT) for k in ("port", "hostname")]
CONFIG_SECTIONS = [
    "Scanning",
    "Main",
    "Rig URI",
    "Monitor",
]

# Maximum number of endpoint sections persisted in the INI file.
# When a new endpoint is saved and the count exceeds this limit,
# the oldest endpoint is evicted (FIFO) and the eviction is logged.
MAX_ENDPOINTS = 20

# INI key names for the [selected rigs] section.
SELECTED_RIG_KEYS = [
    "SELECTED_RIG1_RIG_ENDPOINT",
    "SELECTED_RIG2_RIG_ENDPOINT",
]

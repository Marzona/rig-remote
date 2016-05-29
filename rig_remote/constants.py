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

# constant definition
ALLOWED_BOOKMARK_TASKS = ["load", "save"]
DIRMODE = 644
CBB_MODES = ('',
             'OFF',
             'RAW',
             'AM',
             'FM',
             'WFM',
             'WFM_ST',
             'LSB',
             'USB',
             'CW',
             'CWL',
             'CWU')

# scanning constants
# once tuned a freq, check this number of times for a signal
SIGNAL_CHECKS=2
# time to wait between checks on the same frequency
NO_SIGNAL_DELAY = .1
# once we send the cmd for tuning a freq, wait this time
TIME_WAIT_FOR_TUNE = .25
# minimum interval in hertz
MIN_INTERVAL = 1000
# fictional mode set for active frequencies
UNKNOWN_MODE = "unknown"
# monitoring mode delay
MONITOR_MODE_DELAY = 2

# dictionary for mapping between rig modes and rig-remote modes
# the key is the rig-remote namings and the value is the rig naming

MODE_MAP = {}
MODE_MAP["AM"] = "AM",
MODE_MAP["FM"] = "NarrowFM",
MODE_MAP["WFM_ST"] = "WFM(stereo)",
MODE_MAP["WFM"] = "WFM(mono)",
MODE_MAP["LSB"] = "LSB",
MODE_MAP["USB"] = "USB",
MODE_MAP["CW"] = "CW",
MODE_MAP["CWL"] = "CW-L",
MODE_MAP["CWU"] = "CW-U"

SUPPORTED_SCANNING_ACTIONS = ("start",
                               "stop")

SUPPORTED_SCANNING_MODES = ("bookmarks",
                            "frequency")
DEFAULT_CONFIG = {"hostname" : "127.0.0.1",
                  "port" : "7356",
                  "interval" : "1",
                  "delay" : "5",
                  "passes" : "0",
                  "sgn_level" : "-30",
                  "range_min" : "24,000",
                  "range_max" : "1800,000",
                  "wait" : "false",
                  "record" : "false",
                  "log" : "false",
                  "always_on_top" : "true",
                  "save_exit" : "false",
                  "auto_bookmark" : "false",
                  "log_filename" : "noname",
                  "bookmark_filename" : "noname"}

LEN_BM = 4

class BM(object):
    "Helper class with 4 attribs."

    freq, mode, desc, lockout = range(LEN_BM)

UI_EVENT_TIMER_DELAY = 1000
QUEUE_MAX_SIZE = 10

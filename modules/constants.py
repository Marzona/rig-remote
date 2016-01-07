#!/usr/bin/env python


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
NO_SIGNAL_DELAY = .2
# once we send the cmd for tuning a freq, wait this time
TIME_WAIT_FOR_TUNE=.2
# minimum interval in hertz
MIN_INTERVAL = 1000
# fictional mode set for active frequencies
UNKNOWN_MODE = "unknown"
# dictionary for mapping between gqrx modes and gqrx-remote modes
# the key is the gqrx-remote namings and the value is the gqrx naming

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

SUPPORTED_SCANNING_ACTIONS = ("start")

SUPPORTED_SCANNING_MODES = ("bookmarks",
                            "frequency")
BOOKMARKS_FILE = "gqrx-bookmarks.csv"
DEFAULT_CONFIG = {"hostname" : "127.0.0.1",
                  "port" : "7356",
                  "interval" : "1",
                  "delay" : "5",
                  "sgn_level" : "-30",
                  "range_min" : "24,000",
                  "range_max" : "1800,000",
                  "always_on_top" : "True",
                  "save_exit" : "False",
                  "auto_bookmark" : "False"}

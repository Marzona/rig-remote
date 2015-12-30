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
# once tuned a freq, wait this time for getting the signal
TIME_WAIT_FOR_SIGNAL=.5
# once we send the cmd for tuning a freq, wait this time
TIME_WAIT_FOR_TUNE=.5

#maximum scanning threads
MAX_SCAN_THREADS = 1

# minimum interval
MIN_INTERVAL = 100000
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

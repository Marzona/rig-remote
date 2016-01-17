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
"""
# import modules
import pytest
from modules.scanning import ScanningTask
from modules.constants import MIN_INTERVAL
from modules.exceptions import UnsupportedScanningConfigError

@pytest.fixture
def scan_task():
    mode = "bookmarks"
    bookmark_list = []
    min_freq = "100"
    max_freq = "50"
    delay = "1"
    sgn_level = "50"
    interval= "100000"
    scan_task = ScanningTask(mode,
                             bookmark_list,
                             min_freq,
                             max_freq,
                             delay,
                             interval,
                             sgn_level)
    return scan_task

def test_bad_interval(scan_task):

    scan_task._check_interval()
    minimum_interval = MIN_INTERVAL*100
    assert (scan_task.interval == minimum_interval)

def test_good_interval(scan_task):

    scan_task.interval= "100001"
    scan_task._check_interval()
    assert (scan_task.interval != MIN_INTERVAL)


def test_unsupported_scan_mode():
    mode = "test"
    bookmark_list = []
    min_freq = "100"
    max_freq = "50"
    delay = "1"
    sgn_level = "50"
    interval= "100000"
    with pytest.raises(UnsupportedScanningConfigError):
        scan_task = ScanningTask(mode,
                                 bookmark_list,
                                 min_freq,
                                 max_freq,
                                 delay,
                                 interval,
                                 sgn_level)

testdata=[("bookmarks",
           [],
           "test",
           "50",
           "1",
           "50",
           "100000"),
          ("bookmarks",
           [],
           "10",
           "test",
           "1",
           "50",
           "100000"),
           ("bookmarks",
           [],
           "10",
           "50",
           "test",
           "50",
           "100000"),
           ("bookmarks",
           [],
           "10",
           "50",
           "1",
           "test",
           "100000"),
           ("bookmarks",
           [],
           "10",
           "50",
           "1",
           "50",
           "test")]

@pytest.mark.parametrize("mode, bookmark_list, min_freq,max_freq,delay,sgn_level,interval", testdata)
def test_bad_param(mode, bookmark_list, min_freq,max_freq,delay,sgn_level,interval):
    with pytest.raises(ValueError):
        ScanningTask(mode,
                     bookmark_list,
                     min_freq,
                     max_freq,
                     delay,
                     interval,
                     sgn_level)


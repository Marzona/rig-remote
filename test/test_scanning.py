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

class TestStr (str) :

    def __new__(cls, *args, **kw):
        return str.__new__(cls, *args, **kw)

    def __init__(self, lstr):
        self.lstr = lstr

    def get(self):
        return(self.lstr)

class TestBool (object) :

    def __init__(self, lbool):
        self.lbool = lbool

    def is_checked(self):
        return(self.lbool)


@pytest.fixture
def scan_task():
    params = {}
    scanq = None
    mode = "bookmarks"
    bookmark_list = []
    stop_scan_button = None
    params["txt_range_min"] = TestStr("100")
    params["txt_range_max"] = TestStr("50")
    params["txt_delay"] = TestStr("1")
    params["txt_passes"] = TestStr("0")
    params["txt_sgn_level"] = TestStr("50")
    params["txt_interval"] = TestStr("100000")
    params["ckb_record"] = TestBool(False)
    params["ckb_log"] = TestBool(False)
    params["ckb_wait"] = TestBool(False)
    scan_task = ScanningTask(scanq,
                             mode,
                             bookmark_list,
                             stop_scan_button,
                             params)
    return scan_task

def test_bad_interval(scan_task):

    scan_task._check_interval()
    minimum_interval = MIN_INTERVAL*100
    assert (scan_task.params["interval"] == minimum_interval)

def test_good_interval(scan_task):

    scan_task.interval= "100001"
    scan_task._check_interval()
    assert (scan_task.interval != MIN_INTERVAL)


def test_unsupported_scan_mode():

    params = {}
    scanq = None
    mode = "test"
    bookmark_list = []
    stop_scan_button = None
    params["txt_range_min"] = TestStr("100")
    params["txt_range_max"] = TestStr("50")
    params["txt_delay"] = TestStr("1")
    params["txt_passes"] = TestStr("0")
    params["txt_sgn_level"] = TestStr("50")
    params["txt_interval"] = TestStr("100000")
    params["ckb_record"] = TestBool(False)
    params["ckb_log"] = TestBool(False)
    params["ckb_wait"] = TestBool(False)

    with pytest.raises(UnsupportedScanningConfigError):
        scan_task = ScanningTask(scanq,
                                 mode,
                                 bookmark_list,
                                 stop_scan_button,
                                 params)


testdata=[(None,
           "bookmarks",
           [],
           None,
           "test",
           "50",
           "1",
           "0",
           "50",
           "100000",
           False,
           False,
           False),
          (None,
           "bookmarks",
           [],
           None,
           "10",
           "test",
           "1",
           "0",
           "50",
           "100000",
           False,
           False,
           False),
          (None,
           "bookmarks",
           [],
           None,
           "10",
           "50",
           "test",
           "0",
           "50",
           "100000",
           False,
           False,
           False),
          (None,
           "bookmarks",
           [],
           None,
           "10",
           "50",
           "1",
           "test",
           "50",
           "100000",
           False,
           False,
           False),
          (None,
           "bookmarks",
           [],
           None,
           "10",
           "50",
           "1",
           "0",
           "test",
           "100000",
           False,
           False,
           False),
          (None,
           "bookmarks",
           [],
           None,
           "10",
           "50",
           "1",
           "0",
           "50",
           "test",
           False,
           False,
           False)]

@pytest.mark.parametrize(
"scanq, mode, bookmark_list, stop_scan_button, min_freq, max_freq, delay, passes, sgn_level, interval, record, log, wait", testdata)
def test_bad_param(scanq, mode, bookmark_list, stop_scan_button, min_freq, max_freq, delay, passes, sgn_level, interval, record, log, wait):
    with pytest.raises(ValueError):

        params = {}
        params["txt_range_min"] = TestStr(min_freq)
        params["txt_range_max"] = TestStr(max_freq)
        params["txt_delay"] = TestStr(delay)
        params["txt_passes"] = TestStr(passes)
        params["txt_sgn_level"] = TestStr(sgn_level)
        params["txt_interval"] = TestStr(interval)
        params["ckb_record"] = TestBool(record)
        params["ckb_log"] = TestBool(log)
        params["ckb_wait"] = TestBool(wait)

        ScanningTask(scanq,
                     mode,
                     bookmark_list,
                     stop_scan_button,
                     params)

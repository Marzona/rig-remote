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

import pytest
from rig_remote.disk_io import LogFile
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningTask
from rig_remote.scanning import Scanning
from rig_remote.exceptions import UnsupportedScanningConfigError
from rig_remote.stmessenger import STMessenger

@pytest.fixture
def fake_target():
    return {"hostname": "test", "port": 80, "rig_number": 1}


class TestStr(str):

    def __new__(cls, *args, **kw):
        return str.__new__(cls, *args, **kw)

    def __init__(self, lstr):
        self.lstr = lstr

    def get(self):
        return self.lstr


class TestBool(object):

    def __init__(self, lbool):
        self.lbool = lbool

    def is_checked(self):
        return self.lbool


@pytest.fixture
def fake_rig():
    class fake_rig(object):
        def set_frequency(self, freq):
            pass

        def get_mode(self):
            return "am"

        def get_level(self):
            return "8.2"

    return fake_rig()


@pytest.fixture
def FakeSTMessenger():
    class FakeSTMessenger(object):
        def update_queued(self):
            return False

        def get_event_update(self):
            return None, None

    return FakeSTMessenger



def test_scan_task():
    scanq = STMessenger()
    mode = "bookmarks"
    rig = None
    bookmark_list = []
    new_bookmark_list = []
    params = {"txt_range_min": TestStr("99"), "txt_range_max": TestStr("500"), "txt_delay": TestStr("1"),
              "txt_passes": TestStr("0"), "txt_sgn_level": TestStr("50"), "txt_interval": TestStr("100000"),
              "ckb_record": TestBool(False), "ckb_log": TestBool(False), "ckb_wait": TestBool(False), "delay": 1,
              "ckb_auto_bookmark": TestBool(False)}

    fake_target = {"hostname": "127.0.0.1", "port": 80, "rig_number": 1}

    scan_task = ScanningTask(mode, new_bookmark_list, params)
    return scan_task

def test_delay():
    s = Scanning()
    s._queue_sleep(test_scan_task())


def test_low_interval():
    scan_task = test_scan_task()
    scan_task.params["interval"] = 1000 / 10000
    scan_task._check_interval()
    assert scan_task.params["interval"] == 1000 / 10000


def test_interval():
    scan_task = test_scan_task()
    scan_task.params["interval"] = 1000 * 100
    scan_task._check_interval()
    assert scan_task.params["interval"] == 1000 * 100


def test_unsupported_scan_mode(fake_target):

    params = {}
    scanq = None
    mode = "test"
    bookmark_list = []
    new_bookmark_list = []
    params["txt_range_min"] = TestStr("100")
    params["txt_range_max"] = TestStr("50")
    params["txt_delay"] = TestStr("1")
    params["txt_passes"] = TestStr("0")
    params["txt_sgn_level"] = TestStr("50")
    params["txt_interval"] = TestStr("100000")
    params["ckb_record"] = TestBool(False)
    params["ckb_log"] = TestBool(False)
    params["ckb_wait"] = TestBool(False)
    params["ckb_auto_bookmark"] = TestBool(False)

    with pytest.raises(UnsupportedScanningConfigError):
        scan_task = ScanningTask(mode, new_bookmark_list, params,)

testdata = [
    (
        None,
        "bookmarks",
        [],
        [],
        "test",
        "50",
        "1",
        "0",
        "50",
        "100000",
        False,
        False,
        False,
        False,
    ),
    (
        None,
        "bookmarks",
        [],
        [],
        "10",
        "test",
        "1",
        "0",
        "50",
        "100000",
        False,
        False,
        False,
        False,
    ),
    (
        None,
        "bookmarks",
        [],
        [],
        "10",
        "50",
        "test",
        "0",
        "50",
        "100000",
        False,
        False,
        False,
        False,
    ),
    (
        None,
        "bookmarks",
        [],
        [],
        "10",
        "50",
        "1",
        "test",
        "50",
        "100000",
        False,
        False,
        False,
        False,
    ),
    (
        None,
        "bookmarks",
        [],
        [],
        "10",
        "50",
        "1",
        "0",
        "test",
        "100000",
        False,
        False,
        False,
        False,
    ),
    (
        None,
        "bookmarks",
        [],
        [],
        "10",
        "50",
        "1",
        "0",
        "50",
        "test",
        False,
        False,
        False,
        False,
    ),
]


@pytest.mark.parametrize(
    "scanq, mode, bookmark_list, new_bookmark_list, min_freq, max_freq, delay, passes, sgn_level, interval, record, log, wait, auto_bookmark",
    testdata,
)
def test_bad_param(
    scanq,
    mode,
    bookmark_list,
    new_bookmark_list,
    min_freq,
    max_freq,
    delay,
    passes,
    sgn_level,
    interval,
    record,
    log,
    wait,
    auto_bookmark,
    fake_target,
):
    with pytest.raises(ValueError):

        params = {"txt_range_min": TestStr(min_freq), "txt_range_max": TestStr(max_freq), "txt_delay": TestStr(delay),
                  "txt_passes": TestStr(passes), "txt_sgn_level": TestStr(sgn_level), "txt_interval": TestStr(interval),
                  "ckb_record": TestBool(record), "ckb_log": TestBool(log), "ckb_wait": TestBool(wait),
                  "ckb_auto_bookmark": TestBool(auto_bookmark)}

        ScanningTask(
            mode,
            new_bookmark_list,
            params,
            RigCtl(fake_target),
        )


def test_tune():
    st = test_scan_task()
    st.passes = 4
    log = LogFile()
    freq = "test"
    s = Scanning()
    with pytest.raises(ValueError):
        s._frequency_tune(st, freq)


def test_2_tune():
    st = test_scan_task()
    st.passes = 4
    log = LogFile()
    freq = st.params["txt_range_min"]
    s = Scanning()
    try:
        s._frequency_tune(st, freq)
    except Exception:
        pass
    assert s.scan_active == False


def test_new_bookmarks_1(fake_rig):
    st = test_scan_task()
    st.rig = fake_rig
    freq = st.params["txt_range_min"]
    s = Scanning()
    original_len = len(st.new_bookmark_list)
    nbm = s._create_new_bookmark(st, freq)
    st.new_bookmark_list.append(nbm)
    assert original_len + 1 == len(st.new_bookmark_list)


def test_new_bookmarks_2(fake_rig):
    s = Scanning()
    st = test_scan_task()
    st.rig = fake_rig
    freq = st.params["txt_range_min"]
    nbm = s._create_new_bookmark(st, freq)
    assert isinstance(nbm, dict) == True


def test_signal_check(fake_rig):
    s = Scanning()
    st = test_scan_task()
    st.rig = fake_rig
    sgn_level = 2
    detected_level = []
    assert s._signal_check(sgn_level, fake_rig, detected_level) == True


def test_pass_count_update():
    scan_task = test_scan_task()
    s = Scanning()
    s.scan_active = True
    scan_task.params["txt_passes"] = 2
    n, task = s._pass_count_update(1, scan_task)
    assert s.scan_active == False


def test_get_scan_items():
    s = Scanning()
    scan_task = test_scan_task()
    txt_range_min, txt_passes, txt_interval = s._get_task_items(scan_task)

    assert txt_range_min == scan_task.params["txt_range_min"]
    assert txt_passes == scan_task.params["txt_passes"]
    assert txt_interval / 1000 == scan_task.params["txt_interval"]


def test_queue_sleep_1( FakeSTMessenger):
    # sillt test just to make sure that the while true actually ends.
    scan_task = test_scan_task()
    s = Scanning()
    scan_task.params["delay"] = 1
    scan_task.scanq = FakeSTMessenger()
    s._queue_sleep(scan_task)


def test_terminate():
    s = Scanning()
    s.terminate()
    assert s.scan_active == False

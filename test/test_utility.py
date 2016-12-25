#!/usr/bin/env python
import pytest
from rig_remote.utility import (
                                this_file_exists,
                                is_valid_port,
                                is_valid_hostname,
                                process_path,
                                frequency_pp_parse,
                                store_conf,
                                build_rig_uri,
                                dbfs_to_sgn,
                                )
from rig_remote.ui import RigRemote
import Tkinter as tk
from mock import MagicMock
from rig_remote.app_config import AppConfig

testdata = [("aggr_scan", "false"),
            ("auto_bookmark", "false"),
            ("hostname1", ""),
            ("passes", ""),
            ("aggr_scan", "false"),
            ("log", "false"),
            ("record", "false"),
            ("range_max", ""),
            ("log_filename", "none"),
            ("interval", ""),
            ("hostname2", ""),
            ("range_min", ""),
            ("delay", ""),
            ("bookmark_filename", "./test/test-bookmarks.csv"),
            ("sgn_level", ""),
            ("save_exit", "false"),
            ("always_on_top", "false"),
            ("auto_bookmark", "false"),
            ("wait", "false"),
            ("port2", ""),
            ("port1", "")]

def test_this_file_exist():
    assert(None == this_file_exists("/nonexisting"))

def test_is_valid_port_1():
    with pytest.raises(ValueError):
        is_valid_port("test")

def test_is_valid_port_2():
    with pytest.raises(ValueError):
        is_valid_port(1000)

def test_is_valid_hostname():
    with pytest.raises(ValueError):
        is_valid_hostname("")

def test_process_path_1():
    path= "/tmp/p"
    assert(path == process_path(path))

def test_process_path_2():
    path="~/test/p"
    processed_path= process_path(path)
    assert(("home" in processed_path) ==True)

def test_frequency_pp_parse1():
    freq=2
    with pytest.raises(ValueError):
        frequency_pp_parse(freq)

def test_frequency_pp_parse2():
    freq="2,4"
    pfreq=frequency_pp_parse(freq)
    assert("," not in pfreq)

def test_build_rig_uri():
    with pytest.raises(NotImplementedError):
        build_rig_uri(3,"test")

@pytest.mark.parametrize("key, value", testdata)
def test_store_conf(key, value):
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.ac.write_conf = MagicMock()
    out = store_conf(rr)
    assert(out.config[key] == value)
    rr.root.destroy()

def test_khertz_to_hertz():
    assert(dbfs_to_sgn(10) == 100)

def test_error_khertz_to_hertz():
    with pytest.raises(ValueError):
        dbfs_to_sgn("test")

def test_dbfs_to_sgn():
    assert(dbfs_to_sgn(10) == 100)

def test_error_dbfs_to_sgn():
    with pytest.raises(ValueError):
        dbfs_to_sgn("test")

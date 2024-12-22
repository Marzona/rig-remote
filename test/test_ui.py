#!/usr/bin/env python

# import modules
import pytest
import socket
from rig_remote.ui import RigRemote
from rig_remote.app_config import AppConfig
from rig_remote.exceptions import UnsupportedScanningConfigError
from rig_remote.utility import is_valid_hostname, is_valid_port
import Tkinter as tk
from socket import gaierror

@pytest.fixture
def fake_target():
    fake_target= {}
    fake_target["hostname"] = "127.0.0.1"
    fake_target["port"] = 80
    fake_target["rig_number"] = 1
    return fake_target

@pytest.fixture
def fake_control_source():
    fake_control_source ={}
    fake_control_source["frequency"] = "123,000"
    fake_control_source["mode"] = "AM"
    fake_control_source["description"] = "test"
    return fake_control_source

def truncate_bookmark_file():
    with open("./test/test-bookmarks.csv", "rw+") as f:
        for i in range(10):
            f.readline()
        f.truncate()

def test_load_conf1():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)

    assert (rr.params["txt_hostname1"].get() == "127.0.0.1")
    rr.root.destroy()

def test_load_conf2():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_port1"].get() == "7356")
    rr.root.destroy()

def test_load_conf3():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_range_max"].get() == "1800,000")
    rr.root.destroy()

def test_load_conf4():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_range_min"].get() == "24,000")
    rr.root.destroy()

def test_load_conf5():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["cbb_mode1"].get() == "")
    rr.root.destroy()

def test_load_conf6():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_interval"].get() == "1")
    rr.root.destroy()

def test_load_conf7():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_passes"].get() == "1")
    rr.root.destroy()

def test_load_conf8():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert(rr.params["ckb_auto_bookmark"].is_checked() == 0)
    rr.root.destroy()

def test_load_conf9():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_frequency1"].get() == "")
    rr.root.destroy()

def test_load_conf10():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert(rr.params["ckb_wait"].is_checked() == 0)
    rr.root.destroy()

def test_load_conf11():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_sgn_level"].get() == "-30")
    rr.root.destroy()

def test_load_conf12():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert(rr.params["ckb_log"].is_checked() == 0)
    rr.root.destroy()

def test_load_conf13():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert(rr.params["ckb_record"].is_checked() == 0)
    rr.root.destroy()


def test_load_conf14():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert(rr.params["ckb_auto_bookmark"].is_checked() == 0)
    rr.root.destroy()

def test_load_conf15():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["txt_description1"].get() == "")
    rr.root.destroy()

def test_load_conf16():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["cbb_mode1"].current() == 0)
    rr.root.destroy()

def test_load_conf17():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    assert (rr.params["cbb_mode1"].config()["values"][4] == ('', 'AM', 'FM', 'WFM', 'WFM_ST', 'LSB', 'USB', 'CW', 'CWL', 'CWU'))
    rr.root.destroy()

testdata = [("80"), ("test"), ("1024")]
@pytest.mark.parametrize("port", testdata)
def test_ko_is_valid_port(port):
    with pytest.raises(ValueError):
        is_valid_port(port)


def test_ok_is_valid_port():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    assert(is_valid_port("1025") == None)
    rr.root.destroy()


testdata = ['', 'string', '123,333']
@pytest.mark.parametrize("entry", testdata)
def test_cb_add(entry, fake_control_source):
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    rr.params["txt_frequency1"].insert(0, entry)
    rr.cb_add(fake_control_source, True)
    rr.root.destroy()
    truncate_bookmark_file()

testdata = ['', 'string', '123.123', '123.123.', '127.0.0.1']
@pytest.mark.parametrize("entry", testdata)
def test_process_hostname_entry(entry):
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    rr._process_hostname_entry(entry, True)
    rr.root.destroy()
    truncate_bookmark_file()

def test_process_port_entry_1():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    rr._process_port_entry("test", True)
    rr.rigctl_one.port=None
    rr.root.destroy()

def test_process_port_entry_2():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.apply_config(ac)
    rr._process_port_entry("8080", True)
    rr.rigctl_one.port= "8080"
    rr.root.destroy()

def test_ko_1_is_valid_hostname():
    with pytest.raises(gaierror):
        is_valid_hostname(" ")

def test_ko_2_is_valid_hostname():
    with pytest.raises(ValueError):
        is_valid_hostname("")

def test_popup_about():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    assert(rr.ckb_top.val.get() == False)

def test_scan():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    with pytest.raises(UnsupportedScanningConfigError):
        rr._scan("test","test")

def test_new_activity_message():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    assert(rr._new_activity_message([]) == "")

def test_error_clear_form():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    with pytest.raises(NotImplementedError):
        rr._clear_form(3)

def test_1_clear_form():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr._clear_form(1)
    assert(rr.params["txt_frequency1"].get() == "")
    assert(rr.params["txt_port1"].get() == "")

def test_2_clear_form():
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr._clear_form(2)
    assert(rr.params["txt_frequency2"].get() == "")
    assert(rr.params["txt_port2"].get() == "")

def test_cb_get_frequency(fake_target):
    root = tk.Tk()
    ac = AppConfig("./test/test-config.file")
    ac.read_conf()
    rr = RigRemote(root, ac)
    rr.cb_get_frequency(fake_target)

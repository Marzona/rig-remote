#!/usr/bin/env python
import pytest
from rig_remote.utility import (
                                this_file_exists,
                                is_valid_port,
                                is_valid_hostname,
                                process_path,
                                frequency_pp_parse,
                                build_rig_uri,
                                )

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

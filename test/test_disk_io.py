#!/usr/bin/env python

# import modules
import pytest
import socket
import csv
from rig_remote.disk_io import IO, LogFile
from rig_remote.exceptions import InvalidPathError

def test_non_existent_path():
    io=IO()
    with pytest.raises(InvalidPathError):
        io._path_check("")


def test_good_path_csv_load():

    io=IO()
    io.csv_load("/tmp/",",")

def test_good_path_csv_save():

    io=IO()
    io.csv_save("/tmp/test.csv",",")


def test_bad_file_csv_save():

    io=IO()
    io.row_list=2
    with pytest.raises(TypeError):
        io.csv_save("/tmp/test.csv",",")

def test_bad_file2_csv_save():

    io=IO()
    io.row_list=[2,2]
    with pytest.raises(csv.Error):
        io.csv_save("/tmp/test.csv",",")

def test_no_logfile():
    lf=LogFile()
    with pytest.raises(AttributeError):
        lf.write("B",("122"),["2","2"])

def test_bad_data1():
    lf=LogFile()
    lf.open("/tmp/nofile")
    with pytest.raises(TypeError):
        lf.write("B",(122),["2","2"])

def test_bad_data2():
    lf=LogFile()
    lf.open("/tmp/nofile")
    with pytest.raises(TypeError):
        lf.write("C",("122"),["2","2"])

def test_bad_data3():
    lf=LogFile()
    lf.open("/tmp/nofile")
    with pytest.raises(IndexError):
        lf.write("B",["122"],"2")

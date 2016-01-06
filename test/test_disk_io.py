#!/usr/bin/env python

# import modules
import pytest
import socket
from modules.disk_io import IO
from modules.exceptions import InvalidPathError

def test_non_existent_path():
    io=IO()
    with pytest.raises(InvalidPathError):
        io._path_check("")


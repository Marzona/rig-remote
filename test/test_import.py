#!/usr/bin/env python
import pytest
import importlib
constants_module=[
                  ("ALLOWED_BOOKMARK_TASKS"),
                  ("BM"),
                  ("BOOKMARKS_FILE"),
                  ("CBB_MODES"),
                  ("DEFAULT_CONFIG"),
                  ("LEN_BM"),
                  ("LOG_FILE_NAME"),
                  ("MIN_INTERVAL"),
                  ("MONITOR_MODE_DELAY"),
                  ("NO_SIGNAL_DELAY"),
                  ("QUEUE_MAX_SIZE"),
                  ("SIGNAL_CHECKS"),
                  ("SUPPORTED_SCANNING_ACTIONS"),
                  ("SUPPORTED_SCANNING_MODES"),
                  ("TIME_WAIT_FOR_TUNE"),
                  ("UI_EVENT_TIMER_DELAY"),
                  ("UNKNOWN_MODE"),
                 ]

app_config_module=[
                   ("from rig_remote.app_config import AppConfig"),
                  ]

disk_io_module=[
                ("from rig_remote.disk_io import IO"),
                ("from rig_remote.disk_io import LogFile"),
                ]

exception_module=[
                  ("from rig_remote.exceptions import InvalidPathError"),
                  ("from rig_remote.exceptions import UnsupportedScanningConfigError"),
                  ]

rigctl_module=[
               ("from rig_remote.rigctl import RigCtl"),
              ]

scanning_module=[("from rig_remote.scanning import Scanning"),
                 ("from rig_remote.scanning import ScanningTask"),
                ]
stmessenger_module=[
                    ("from rig_remote.stmessenger import STMessenger"),
                   ]

@pytest.mark.parametrize("entry", constants_module)
def test_import_constants(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", app_config_module)
def test_import_app_config(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", disk_io_module)
def test_import_disk_io(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", exception_module)
def test_import_exception(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", rigctl_module)
def test_import_rigctl(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", scanning_module)
def test_import_scanning(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")

@pytest.mark.parametrize("entry", stmessenger_module)
def test_import_stmessenger(entry):
    getattr(__import__("rig_remote", fromlist=[entry]), "constants")



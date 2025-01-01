constants_module = [
    ("BM"),
    ("BOOKMARKS_FILE"),
    ("CBB_MODES"),
    ("DEFAULT_CONFIG"),
    ("LEN_BM"),
    ("LOG_FILE_NAME"),
    ("MIN_INTERVAL"),
    ("SUPPORTED_SCANNING_ACTIONS"),
]

app_config_module = [
    ("from rig_remote.app_config import AppConfig"),
]

disk_io_module = [
    ("from rig_remote.disk_io import IO"),
    ("from rig_remote.disk_io import LogFile"),
]

exception_module = [
    ("from rig_remote.exceptions import InvalidPathError"),
    ("from rig_remote.exceptions import UnsupportedScanningConfigError"),
]

rigctl_module = [
    ("from rig_remote.rigctl import RigCtl"),
]

scanning_module = [
    ("from rig_remote.scanning import Scanning"),
    ("from rig_remote.scanning import ScanningTask"),
]
stmessenger_module = [
    ("from rig_remote.stmessenger import STMessenger"),
]

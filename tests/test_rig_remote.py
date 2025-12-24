# python
import os
import sys
import time
import logging
import pytest

from rig_remote import rig_remote as rr


@pytest.fixture
def set_argv():
    old = sys.argv[:]
    def _set(argv_list):
        sys.argv[:] = list(argv_list)
    yield _set
    sys.argv[:] = old


@pytest.fixture
def set_env_home():
    old = os.environ.get("HOME")
    def _set(val):
        if val is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = val
    yield _set
    if old is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = old


@pytest.fixture
def patch_attr():
    """
    Patch an attribute on an object and restore it after the test.
    Usage: patch_attr(obj, "name", new_value)
    """
    patches = []
    def _patch(obj, name, value):
        had = hasattr(obj, name)
        orig = getattr(obj, name, None)
        patches.append((obj, name, orig, had))
        setattr(obj, name, value)
    yield _patch
    for obj, name, orig, had in reversed(patches):
        if had:
            setattr(obj, name, orig)
        else:
            try:
                delattr(obj, name)
            except Exception:
                # some objects may not allow delattr; ignore
                pass


@pytest.fixture
def fake_tzset():
    orig = getattr(time, "tzset", None)
    time.tzset = lambda: None
    yield
    if orig is None:
        try:
            delattr(time, "tzset")
        except Exception:
            pass
    else:
        time.tzset = orig


def test_rig_remote_process_path_expands_tilde(set_env_home):
    set_env_home("/home/testuser")
    path = "~/mydir/file.txt"
    expected = os.path.join(os.path.expanduser("~/mydir"), "file.txt")
    assert rr.process_path(path) == expected


def test_rig_remote_process_path_no_dir():
    assert rr.process_path("file.txt") == "file.txt"


def test_rig_remote_input_arguments_all_flags(set_argv):
    set_argv([
        "prog",
        "-v",
        "-b", "/tmp/b.csv",
        "-c", "/tmp/c.conf",
        "-l", "/tmp/log.txt",
        "-p", "/prefix"
    ])
    args = rr.input_arguments()
    assert args.verbose is True
    assert args.alternate_bookmark_file == "/tmp/b.csv"
    assert args.alternate_config_file == "/tmp/c.conf"
    assert args.alternate_log_file == "/tmp/log.txt"
    assert args.alternate_prefix == "/prefix"


def test_rig_remote_input_arguments_defaults(set_argv):
    set_argv(["prog"])
    args = rr.input_arguments()
    assert args.verbose is False
    assert args.alternate_bookmark_file is None
    assert args.alternate_config_file is None
    assert args.alternate_log_file is None
    assert args.alternate_prefix is None


def test_rig_remote_log_configuration_sets_level_and_handles_tzset(fake_tzset):
    # preserve root logger state
    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    try:
        logger_verbose = rr.log_configuration(True)
        assert logger_verbose.level == logging.INFO

        logger_quiet = rr.log_configuration(False)
        assert logger_quiet.level == logging.WARNING
    finally:
        # restore root logger
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level


def test_rig_remote_log_configuration_updates_existing_handler_levels(patch_attr):
    """
    Ensure existing handlers get their levels updated and exercise tzset-absent path.
    """
    # remove tzset if present to exercise branch where tzset is absent
    if hasattr(time, "tzset"):
        patch_attr(time, "tzset", None)
        try:
            delattr(time, "tzset")
        except Exception:
            pass

    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    # add a handler with NOTSET so it should be updated by log_configuration
    handler = logging.StreamHandler()
    handler.setLevel(logging.NOTSET)
    root.addHandler(handler)

    try:
        rr.log_configuration(True)
        assert root.level == logging.INFO
        assert any(h.level == logging.INFO for h in root.handlers)
    finally:
        # cleanup handlers and restore level
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level


def test_rig_remote_log_configuration_adds_handler_if_none(fake_tzset):
    """
    Exercise the branch where no handlers exist on the root logger.
    Ensure a handler is added, it has a formatter and correct level.
    """
    root = logging.getLogger()
    # preserve and clear handlers
    orig_handlers = root.handlers[:]
    orig_level = root.level
    for h in root.handlers[:]:
        root.removeHandler(h)

    try:
        logger = rr.log_configuration(True)
        # root logger should now have at least one handler
        assert len(root.handlers) >= 1
        # the handler(s) should have been set to INFO (or at least one)
        assert any(h.level == logging.INFO for h in root.handlers)
        # handler should have a formatter attached
        assert any(getattr(h, "formatter", None) is not None for h in root.handlers)
        # returned logger should be the root logger
        assert logger is root
    finally:
        # restore original handlers and level
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        for h in orig_handlers:
            if h not in root.handlers:
                root.addHandler(h)
        root.level = orig_level


def test_rig_remote_sets_paths_and_launches(set_argv, patch_attr):
    set_argv([
        "prog",
        "-b", "~/bookmarks.csv",
        "-l", "~/activity.log",
        "-c", "~/rig.conf",
        "-p", "~/.prefix"
    ])

    class FakeAppConfig:
        def __init__(self, config_file):
            self.config_file = config_file
            self.config = {"bookmark_filename": None, "log_filename": None}
        def read_conf(self):
            self.config["bookmark_filename"] = None

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQApp:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            self._quit_on_last = val
        def exec(self):
            return 0

    patch_attr(rr.QtWidgets, "QApplication", FakeQApp)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            self._size = (w, h)
        def show(self):
            self._shown = True

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == 0

    window = container["instance"]
    assert window is not None
    bookmark_set = window.app_config.config["bookmark_filename"]
    log_set = window.app_config.config["log_filename"]
    assert bookmark_set is not None and os.path.expanduser("~/bookmarks.csv") == os.path.expanduser(bookmark_set)
    assert log_set is not None and os.path.expanduser("~/activity.log") == os.path.expanduser(log_set)


def test_rig_remote_respects_existing_appconfig_values(set_argv, patch_attr):
    set_argv(["prog"])

    class FakeAppConfig:
        def __init__(self, config_file):
            self.config_file = config_file
            self.config = {
                "bookmark_filename": "~/existing_bookmarks.csv",
                "log_filename": "~/existing_activity.log"
            }
        def read_conf(self):
            pass

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQApp:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            self._quit_on_last = val
        def exec(self):
            return 0

    patch_attr(rr.QtWidgets, "QApplication", FakeQApp)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            pass
        def show(self):
            pass

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == 0

    window = container["instance"]
    assert window is not None

    # bookmark should be preserved
    assert os.path.expanduser(window.app_config.config["bookmark_filename"]) == os.path.expanduser("~/existing_bookmarks.csv")

    # log is set to the app default under `~/.rig-remote/rig-remote-log.txt`
    expected_log = os.path.join(os.path.expanduser("~/.rig-remote"), "rig-remote-log.txt")
    assert os.path.expanduser(window.app_config.config["log_filename"]) == expected_log


def test_rig_remote_uses_explicit_config_file(set_argv, patch_attr):
    """
    Ensure the CLI passes the explicit -c config filename into AppConfig.
    This exercises the branch where an alternate config file is honored.
    """
    cfg_path = "/tmp/myexplicit.conf"
    set_argv(["prog", "-c", cfg_path])

    # capture the config_file passed to AppConfig
    captured = {"config_file": None}
    class FakeAppConfig:
        def __init__(self, config_file):
            captured["config_file"] = config_file
            self.config_file = config_file
            self.config = {"bookmark_filename": None, "log_filename": None}
        def read_conf(self):
            self.config["bookmark_filename"] = None

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQApp:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            pass
        def exec(self):
            return 0

    patch_attr(rr.QtWidgets, "QApplication", FakeQApp)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            pass
        def show(self):
            pass

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == 0

    # AppConfig should have been constructed with the explicit path (exact match)
    assert captured["config_file"] == cfg_path


def test_rig_remote_propagates_nonzero_app_exec_exit_code(set_argv, patch_attr):
    set_argv(["prog"])

    class FakeAppConfig:
        def __init__(self, config_file):
            self.config_file = config_file
            self.config = {"bookmark_filename": None, "log_filename": None}
        def read_conf(self):
            self.config["bookmark_filename"] = None

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQAppNonZero:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            pass
        def exec(self):
            return 5

    patch_attr(rr.QtWidgets, "QApplication", FakeQAppNonZero)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            pass
        def show(self):
            pass

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == 5

def test_rig_remote_log_configuration_calls_tzset_when_present(patch_attr):
    called = {"v": False}
    def my_tzset():
        called["v"] = True

    # ensure tzset is present and record if called
    patch_attr(time, "tzset", my_tzset)

    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    try:
        rr.log_configuration(True)
        assert called["v"] is True
    finally:
        # restore root logger
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level


def test_rig_remote_log_configuration_handles_missing_tzset(patch_attr):
    # remove tzset if present to exercise branch where tzset is absent
    if hasattr(time, "tzset"):
        patch_attr(time, "tzset", None)
        try:
            delattr(time, "tzset")
        except Exception:
            pass

    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    try:
        logger = rr.log_configuration(False)
        # ensure no exception and logger level set to WARNING
        assert logger.level == logging.WARNING
        assert root.level == logging.WARNING
    finally:
        # restore root logger
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level


def test_rig_remote_sets_default_log_when_none(set_argv, patch_attr):
    set_argv(["prog"])

    class FakeAppConfig:
        def __init__(self, config_file):
            self.config_file = config_file
            self.config = {"bookmark_filename": None, "log_filename": None}
        def read_conf(self):
            # simulate config with no log filename set
            self.config["bookmark_filename"] = None

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQApp:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            pass
        def exec(self):
            return 0

    patch_attr(rr.QtWidgets, "QApplication", FakeQApp)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            pass
        def show(self):
            pass

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == 0

    window = container["instance"]
    expected_log = os.path.join(os.path.expanduser("~/.rig-remote"), "rig-remote-log.txt")
    assert os.path.expanduser(window.app_config.config["log_filename"]) == expected_log
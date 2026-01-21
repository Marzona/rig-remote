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


@pytest.mark.parametrize(
    "input_path, expected_path, set_home",
    [
        ("file.txt", "file.txt", None),
        ("~/mydir/file.txt", "~/mydir/file.txt", "/home/testuser"),
        ("~/file.conf", "~/file.conf", "/home/testuser"),
        ("~/.config/app/file.txt", "~/.config/app/file.txt", "/home/user"),
        ("/absolute/path/file.txt", "/absolute/path/file.txt", None),
        ("relative/path/file.txt", "relative/path/file.txt", None),
    ]
)
def test_rig_remote_process_path(input_path, expected_path, set_home, set_env_home):
    if set_home:
        set_env_home(set_home)
    result = rr.process_path(input_path)
    if "~" in expected_path:
        expected = os.path.join(os.path.expanduser(os.path.dirname(expected_path)), os.path.basename(expected_path))
    else:
        expected = expected_path
    assert result == expected


@pytest.mark.parametrize(
    "argv, expected_verbose, expected_bookmark, expected_config, expected_log, expected_prefix",
    [
        (["prog"], False, None, None, None, None),
        (["prog", "-v"], True, None, None, None, None),
        (["prog", "-b", "/tmp/b.csv"], False, "/tmp/b.csv", None, None, None),
        (["prog", "-c", "/tmp/c.conf"], False, None, "/tmp/c.conf", None, None),
        (["prog", "-l", "/tmp/log.txt"], False, None, None, "/tmp/log.txt", None),
        (["prog", "-p", "/prefix"], False, None, None, None, "/prefix"),
        (["prog", "-v", "-b", "/tmp/b.csv"], True, "/tmp/b.csv", None, None, None),
        (["prog", "-v", "-c", "/tmp/c.conf", "-l", "/tmp/log.txt"], True, None, "/tmp/c.conf", "/tmp/log.txt", None),
        (["prog", "-v", "-b", "/tmp/b.csv", "-c", "/tmp/c.conf", "-l", "/tmp/log.txt", "-p", "/prefix"],
         True, "/tmp/b.csv", "/tmp/c.conf", "/tmp/log.txt", "/prefix"),
        (["prog", "--verbose"], True, None, None, None, None),
        (["prog", "--bookmarks", "/b.csv"], False, "/b.csv", None, None, None),
        (["prog", "--config", "/c.conf"], False, None, "/c.conf", None, None),
        (["prog", "--log", "/log.txt"], False, None, None, "/log.txt", None),
        (["prog", "--prefix", "/p"], False, None, None, None, "/p"),
    ]
)
def test_rig_remote_input_arguments(set_argv, argv, expected_verbose, expected_bookmark,
                                     expected_config, expected_log, expected_prefix):
    set_argv(argv)
    args = rr.input_arguments()
    assert args.verbose is expected_verbose
    assert args.alternate_bookmark_file == expected_bookmark
    assert args.alternate_config_file == expected_config
    assert args.alternate_log_file == expected_log
    assert args.alternate_prefix == expected_prefix


@pytest.mark.parametrize(
    "verbose, expected_level",
    [
        (True, logging.INFO),
        (False, logging.WARNING),
    ]
)
def test_rig_remote_log_configuration_sets_level_and_handles_tzset(fake_tzset, verbose, expected_level):
    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    try:
        logger = rr.log_configuration(verbose)
        assert logger.level == expected_level
    finally:
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


@pytest.mark.parametrize(
    "test_scenario, argv, existing_bookmark, existing_log, expected_exit_code",
    [
        # Test with command line args overriding
        ("cli_overrides", ["prog", "-b", "~/bookmarks.csv", "-l", "~/activity.log", "-c", "~/rig.conf", "-p", "~/.prefix"],
         None, None, 0),
        # Test respecting existing config values
        ("respect_existing", ["prog"], "~/existing_bookmarks.csv", "~/existing_activity.log", 0),
        # Test with explicit config file
        ("explicit_config", ["prog", "-c", "/tmp/myexplicit.conf"], None, None, 0),
        # Test with non-zero exit code
        ("nonzero_exit", ["prog"], None, None, 5),
        # Test with default log when none
        ("default_log", ["prog"], None, None, 0),
    ]
)
def test_rig_remote_cli_scenarios(set_argv, patch_attr, test_scenario, argv, existing_bookmark, existing_log, expected_exit_code):
    """Test various CLI scenarios with different configurations."""
    set_argv(argv)

    captured = {"config_file": None}

    class FakeAppConfig:
        def __init__(self, config_file):
            captured["config_file"] = config_file
            self.config_file = config_file
            self.config = {
                "bookmark_filename": existing_bookmark,
                "log_filename": existing_log
            }
        def read_conf(self):
            if test_scenario != "respect_existing":
                self.config["bookmark_filename"] = None

    patch_attr(rr, "AppConfig", FakeAppConfig)

    class FakeQApp:
        def __init__(self, argv_list):
            self.argv_list = argv_list
        def setQuitOnLastWindowClosed(self, val):
            self._quit_on_last = val
        def exec(self):
            return expected_exit_code

    patch_attr(rr.QtWidgets, "QApplication", FakeQApp)

    container = {"instance": None}
    class FakeWindow:
        def __init__(self, app_config):
            self.app_config = app_config
            container["instance"] = self
        def resize(self, w, h):
            if test_scenario == "cli_overrides":
                self._size = (w, h)
        def show(self):
            if test_scenario == "cli_overrides":
                self._shown = True

    patch_attr(rr, "RigRemote", FakeWindow)

    def fake_exit(code=0):
        raise SystemExit(code)

    patch_attr(rr.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as excinfo:
        rr.cli()
    assert excinfo.value.code == expected_exit_code

    window = container["instance"]
    assert window is not None

    if test_scenario == "cli_overrides":
        bookmark_set = window.app_config.config["bookmark_filename"]
        log_set = window.app_config.config["log_filename"]
        assert bookmark_set is not None and os.path.expanduser("~/bookmarks.csv") == os.path.expanduser(bookmark_set)
        assert log_set is not None and os.path.expanduser("~/activity.log") == os.path.expanduser(log_set)
    elif test_scenario == "respect_existing":
        assert os.path.expanduser(window.app_config.config["bookmark_filename"]) == os.path.expanduser("~/existing_bookmarks.csv")
        expected_log = os.path.join(os.path.expanduser("~/.rig-remote"), "rig-remote-log.txt")
        assert os.path.expanduser(window.app_config.config["log_filename"]) == expected_log
    elif test_scenario == "explicit_config":
        assert captured["config_file"] == "/tmp/myexplicit.conf"
    elif test_scenario == "default_log":
        expected_log = os.path.join(os.path.expanduser("~/.rig-remote"), "rig-remote-log.txt")
        assert os.path.expanduser(window.app_config.config["log_filename"]) == expected_log


@pytest.mark.parametrize(
    "tzset_scenario, verbose, expected_level",
    [
        ("present_and_called", True, logging.INFO),
        ("present_and_called", False, logging.WARNING),
        ("missing", True, logging.INFO),
        ("missing", False, logging.WARNING),
        ("raises_exception", True, logging.INFO),
        ("raises_exception", False, logging.WARNING),
    ]
)
def test_rig_remote_log_configuration_tzset_scenarios(patch_attr, tzset_scenario, verbose, expected_level):
    """Test log_configuration with various tzset scenarios."""
    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    called = {"v": False}

    if tzset_scenario == "present_and_called":
        def my_tzset():
            called["v"] = True
        patch_attr(time, "tzset", my_tzset)
    elif tzset_scenario == "missing":
        if hasattr(time, "tzset"):
            patch_attr(time, "tzset", None)
            try:
                delattr(time, "tzset")
            except Exception:
                pass
    elif tzset_scenario == "raises_exception":
        def failing_tzset():
            raise RuntimeError("tzset failed")
        patch_attr(time, "tzset", failing_tzset)

    try:
        logger = rr.log_configuration(verbose)
        assert logger.level == expected_level
        assert root.level == expected_level

        if tzset_scenario == "present_and_called":
            assert called["v"] is True
    finally:
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level


@pytest.mark.parametrize(
    "verbose, expected_level",
    [
        (True, logging.INFO),
        (False, logging.WARNING),
    ]
)
def test_rig_remote_log_configuration_handles_handler_setlevel_exception(patch_attr, verbose, expected_level):
    """Test that log_configuration handles exceptions when calling handler.setLevel()."""
    root = logging.getLogger()
    orig_handlers = root.handlers[:]
    orig_level = root.level

    class FailingHandler(logging.Handler):
        def setLevel(self, level):
            raise RuntimeError("setLevel failed")

    failing_handler = FailingHandler()
    root.addHandler(failing_handler)

    try:
        logger = rr.log_configuration(verbose)
        assert logger.level == expected_level
    finally:
        for h in root.handlers[:]:
            if h not in orig_handlers:
                root.removeHandler(h)
        root.level = orig_level
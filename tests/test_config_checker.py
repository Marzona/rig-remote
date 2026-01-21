import pytest
from unittest.mock import patch, mock_open, MagicMock

from config_checker.config_checker import (
    input_arguments,
    dump_info,
    check_config,
    cli,
)
from rig_remote.app_config import AppConfig


# Tests for input_arguments function
def test_config_checker_input_arguments_no_args():
    """Test input_arguments with no arguments"""
    with patch("sys.argv", ["config_checker"]):
        args = input_arguments()
        assert args.check_config is None
        assert args.dump is False


def test_config_checker_input_arguments_check_config():
    """Test input_arguments with --check_config flag"""
    test_path = "/path/to/config"
    with patch("sys.argv", ["config_checker", "--check_config", test_path]):
        args = input_arguments()
        assert args.check_config == test_path
        assert args.dump is False


def test_config_checker_input_arguments_check_config_short():
    """Test input_arguments with -cc short flag"""
    test_path = "/path/to/config"
    with patch("sys.argv", ["config_checker", "-cc", test_path]):
        args = input_arguments()
        assert args.check_config == test_path
        assert args.dump is False


def test_config_checker_input_arguments_dump():
    """Test input_arguments with --dump flag"""
    with patch("sys.argv", ["config_checker", "--dump"]):
        args = input_arguments()
        assert args.check_config is None
        assert args.dump is True


def test_config_checker_input_arguments_dump_short():
    """Test input_arguments with -d short flag"""
    with patch("sys.argv", ["config_checker", "-d"]):
        args = input_arguments()
        assert args.check_config is None
        assert args.dump is True


def test_config_checker_input_arguments_mutually_exclusive():
    """Test input_arguments rejects both --dump and --check_config"""
    with patch("sys.argv", ["config_checker", "--dump", "--check_config", "/path"]):
        with pytest.raises(SystemExit):
            input_arguments()


# Tests for dump_info function
@patch("platform.python_version")
@patch("platform.version")
@patch("platform.platform")
@patch("platform.system")
@patch("platform.architecture")
@patch("platform.freedesktop_os_release")
def test_config_checker_dump_info_prints_all_info(
    mock_freedesktop, mock_arch, mock_system_name, mock_platform, mock_version, mock_python_version, capsys
):
    """Test dump_info prints all system information"""
    mock_python_version.return_value = "3.9.0"
    mock_version.return_value = "Linux version 5.0"
    mock_platform.return_value = "Linux-5.0-generic-x86_64"
    mock_system_name.side_effect = ["Linux", "Linux"]
    mock_arch.return_value = ("64bit", "ELF")
    mock_freedesktop.return_value = {"NAME": "Ubuntu", "VERSION": "20.04"}

    dump_info()
    captured = capsys.readouterr()

    assert "Python version: 3.9.0" in captured.out
    assert "Linux version 5.0" in captured.out
    assert "Linux-5.0-generic-x86_64" in captured.out
    assert "64bit" in captured.out


@patch("platform.python_version", side_effect=Exception("Mock error"))
def test_config_checker_dump_info_handles_exception(mock_python_version):
    """Test dump_info handles exceptions gracefully"""
    with pytest.raises(Exception):
        dump_info()


# Tests for check_config function
def test_config_checker_check_config_valid(capsys):
    """Test check_config with valid configuration"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
bookmark_filename='bookmarks.csv'
log_filename='rig_remote.log'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            assert result is True


def test_config_checker_check_config_missing_keys(capsys):
    """Test check_config with missing configuration keys"""
    config_content = """hostname1='localhost'
port1='4532'
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            _ = check_config("/mock/config")
            captured = capsys.readouterr()
            assert "missing some keyword" in captured.out


def test_config_checker_check_config_malformed_lines(capsys):
    """Test check_config with malformed configuration lines"""
    config_content = """hostname1='localhost'
port1='4532'=extra=values
invalid_line_without_equals
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            _ = check_config("/mock/config")
            captured = capsys.readouterr()
            assert "missing some keyword" in captured.out
            assert "Bookmark line malformed" in captured.out

def test_config_checker_check_config_skip_invalid_rows(capsys):
    """Test check_config skips rows with [, #, newlines, or empty strings"""
    config_content = """hostname1='localhost'
port1='4532'
# This is a comment line
[section]
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
bookmark_filename='bookmarks.csv'
log_filename='rig_remote.log'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            assert result is True
            captured = capsys.readouterr()
            assert "Configuration file is valid" in captured.out


def test_config_checker_check_config_invalid_bookmarks(capsys):
    """Test check_config with invalid bookmarks file"""
    config_content = """hostname1='localhost'
port1='4532'
bookmark_filename='bookmarks.csv'
"""
    bookmarks_content = "145500000,FM\n146520000,FM,Simplex,O,Extra\n"

    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            captured = capsys.readouterr()
            assert "Bookmark line malformed" in captured.out


def test_config_checker_check_config_file_not_found():
    """Test check_config when config file doesn't exist"""
    with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
        with pytest.raises(FileNotFoundError):
            check_config("/mock/config")


def test_config_checker_check_config_app_config_read_error(capsys):
    """Test check_config when AppConfig.read_conf raises SystemExit"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
log_filename='rig_remote.log'
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf", side_effect=SystemExit("Config error")):
            result = check_config("/mock/config")
            assert result is False
            captured = capsys.readouterr()
            assert "Error reading configuration file" in captured.out


def test_config_checker_check_config_app_config_unexpected_error(capsys):
    """Test check_config when AppConfig.read_conf raises unexpected error"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
log_filename='rig_remote.log'
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf", side_effect=ValueError("Unexpected error")):
            result = check_config("/mock/config")
            assert result is False
            captured = capsys.readouterr()
            assert "Unexpected error" in captured.out


@pytest.mark.parametrize(
    "bookmark_line,should_error",
    [
        (["145500000", "FM", "Local", "O"], False),
        (["145500000", "FM", "Local"], True),
        (["145500000", "FM", "Local", "O", "Extra"], True),
        (["145500000"], True),
    ],
)
def test_config_checker_check_config_bookmark_validation(bookmark_line, should_error, capsys):
    """Test check_config bookmark line validation"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
bookmark_filename='bookmarks.csv'
log_filename='rig_remote.log'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch("csv.reader") as mock_reader:
            mock_reader.return_value = [bookmark_line]
            with patch.object(AppConfig, "read_conf"):
                result = check_config("/mock/config")
                captured = capsys.readouterr()

                if should_error:
                    assert "Bookmark line malformed" in captured.out
                else:
                    assert result is True


# Tests for cli function
def test_config_checker_cli_no_args(capsys):
    """Test cli with no arguments"""
    with patch("sys.argv", ["config_checker"]):
        cli()
        captured = capsys.readouterr()
        assert "At least one option is required" in captured.out


def test_config_checker_cli_with_dump(capsys):
    """Test cli with --dump flag"""
    with patch("sys.argv", ["config_checker", "--dump"]):
        with patch("config_checker.config_checker.dump_info") as mock_dump:
            cli()
            mock_dump.assert_called_once()


def test_config_checker_cli_with_check_config(capsys):
    """Test cli with --check_config flag"""
    config_content = """hostname1='localhost'
port1='4532'
"""
    with patch("sys.argv", ["config_checker", "--check_config", "/mock/config"]):
        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch("config_checker.config_checker.check_config") as mock_check:
                mock_check.return_value = True
                cli()
                mock_check.assert_called_once_with("/mock/config")


def test_config_checker_cli_check_config_failure(capsys):
    """Test cli when check_config returns False"""
    config_content = """hostname1='localhost'
port1='4532'
"""
    with patch("sys.argv", ["config_checker", "--check_config", "/mock/config"]):
        with patch("builtins.open", mock_open(read_data=config_content)):
            with patch("config_checker.config_checker.check_config") as mock_check:
                mock_check.return_value = False
                cli()
                mock_check.assert_called_once()


# Integration tests
def test_config_checker_full_workflow_valid(capsys):
    """Test complete workflow with valid configuration"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
bookmark_filename='bookmarks.csv'
log_filename='rig_remote.log'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            assert result is True
            captured = capsys.readouterr()
            assert "Using config file" in captured.out
            assert "Configuration file is valid" in captured.out


def test_config_checker_full_workflow_with_errors(capsys):
    """Test complete workflow with configuration errors"""
    config_content = """hostname1='localhost'
port1='4532'=extra=values
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            captured = capsys.readouterr()
            assert "missing some keyword" in captured.out


def test_config_checker_check_config_with_bookmark_file(capsys):
    """Test check_config when bookmark_filename is in config"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
log_filename='rig_remote.log'
bookmark_filename='bookmarks.csv'
"""
    bookmark_content = "Name,Frequency,Mode,RxFilter\nTest,7074000,LSB,normal\n"

    def open_side_effect(filename, *args, **kwargs):
        if "bookmarks" in filename:
            return mock_open(read_data=bookmark_content)()
        else:
            return mock_open(read_data=config_content)()

    with patch("builtins.open", side_effect=open_side_effect):
        with patch.object(AppConfig, "read_conf"):
            result = check_config("/mock/config")
            assert result is True
            captured = capsys.readouterr()
            assert "Bookmarks info:" in captured.out

def test_config_checker_check_config_malformed_line_error_message(capsys):
    """Test check_config prints error for malformed config lines with extra equals"""
    config_content = """hostname1='localhost'
port1='4532'
hostname2='192.168.1.1'
port2='4532'
interval='10'
delay='2'
passes='0'
range_min='88000'
range_max='108000'
sgn_level='-40'
auto_bookmark='false'
record='false'
wait='false'
log='false'
save_exit='false'
always_on_top='false'
log_filename='rig_remote.log'
malformed=line=with=extra=equals
bookmark_filename='bookmarks.csv'
"""
    with patch("builtins.open", mock_open(read_data=config_content)):
        with patch.object(AppConfig, "read_conf"):
            _ = check_config("/mock/config")
            captured = capsys.readouterr()
            assert "Error in config file, line: malformed=line=with=extra=equals" in captured.out
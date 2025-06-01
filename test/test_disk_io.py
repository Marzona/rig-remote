import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock, Mock

import pytest

from rig_remote.disk_io import IO, LogFile
from rig_remote.exceptions import InvalidPathError


@pytest.fixture
def io():
    return IO()


@pytest.fixture
def log_file():
    return LogFile()


@pytest.fixture
def mock_bookmark():
    mock = MagicMock()
    mock.channel = MagicMock()
    mock.channel.frequency = "100000000"
    mock.channel.modulation = "FM"
    mock.channel.description = "Test"
    mock.lockout = "0"
    return mock


def test_disk_io_csv_load_happy_path(io):
    filename = os.path.join(Path(__file__).parent, "test_files/test-rig_remote-bookmarks.csv")
    io.csv_load(csv_file=filename, delimiter=",")
    assert len(io.row_list) == 25


@pytest.mark.parametrize("filename", [
    os.path.join(Path(__file__).parent, "test_files/no_file"),
])
def test_disk_io_csv_load_non_existing_file(io, filename):
    with pytest.raises(InvalidPathError):
        io.csv_load(csv_file=filename, delimiter=",")
    assert len(io.row_list) == 0


def test_disk_io_csv_load_permission_error(io):
    with patch('builtins.open', side_effect=PermissionError):
        with pytest.raises(InvalidPathError):
            io.csv_load("test.csv", ",")
    assert len(io.row_list) == 0


def test_disk_io_csv_load_encoding_error(io):
    with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid')):
        with pytest.raises(InvalidPathError):
            io.csv_load("test.csv", ",")
    assert len(io.row_list) == 0


def test_disk_io_csv_save_success(io, tmp_path):
    file_path = tmp_path / "test_file.csv"
    io.row_list.append(["118600000", "AM", "Dublin airport Tower", "O"])
    io.csv_save(str(file_path), ",")
    io.row_list = []
    io.csv_load(csv_file=str(file_path), delimiter=",")
    assert io.row_list == [["118600000", "AM", "Dublin airport Tower", "O"]]


def test_disk_io_csv_save_mock(io):
    with patch("builtins.open", new_callable=mock_open) as mock_file:
        with patch("csv.writer") as mock_writer:
            io.row_list.append(["118600000,AM,Dublin airport Tower,O"])
            io.csv_save("test_file.csv", ",")
            assert mock_writer.call_args[1] == {"delimiter": ","}
            mock_writer.assert_called_once()
            assert mock_file.call_args_list[0][0] == ("test_file.csv", "w")


def test_disk_io_csv_save_error_handling(io):
    with patch("builtins.open", new_callable=mock_open):
        with patch("csv.writer", side_effect=IOError()):
            io.row_list.append(["118600000,AM,Dublin airport Tower,O"])
            io.csv_save("test_file.csv", ",")
            assert io.row_list == []


def test_disk_io_path_check_invalid(io):
    with pytest.raises(InvalidPathError):
        io._path_check("")


def test_disk_io_write_without_open(log_file):
    with pytest.raises(AttributeError):
        log_file.write("B", "122", ["2", "2"])


def test_disk_io_write_invalid_type(log_file, tmp_path):
    log_path = tmp_path / "test.log"
    log_file.open(str(log_path))
    with pytest.raises(TypeError):
        log_file.write(record_type="X", record=MagicMock(), signal=[1, 2])


def test_disk_io_write_with_signal(log_file, tmp_path, mock_bookmark):
    log_path = tmp_path / "test.log"
    log_file.open(str(log_path))
    log_file.write(record_type="F", record=mock_bookmark, signal=["-50", "-60"])
    log_file.close()

    with open(log_path, 'r') as f:
        content = f.read().strip()
        # Verify core elements in space-separated format
        assert content.startswith("F")  # Type
        assert "100000000" in content  # Frequency
        assert "FM" in content  # Modulation
        assert "['-50', '-60']" in content  # Signal values in list format


def test_disk_io_write_bookmark(log_file, tmp_path, mock_bookmark):
    log_path = tmp_path / "test.log"
    log_file.open(str(log_path))
    log_file.write(record_type="B", record=mock_bookmark, signal=None)
    log_file.close()

    with open(log_path, 'r') as f:
        content = f.read().strip()
        # Verify core elements in space-separated format
        assert content.startswith("B")  # Type
        assert mock_bookmark.channel.frequency in content  # Frequency
        assert mock_bookmark.channel.modulation in content  # Modulation
        assert "None" in content  # Signal (None)


@pytest.mark.parametrize("exception_type,mock_type",
                         [
                             (IndexError, Mock(side_effect=IndexError("Write failed"))),
                             (AttributeError, Mock(side_effect=AttributeError("Write failed"))),
                             (TypeError, Mock(side_effect=TypeError("Write failed"))),
                             (OSError, Mock(side_effect=OSError("Write failed"))),
                             (IOError, Mock(side_effect=IOError("Write failed"))),

                         ]
                         )
def test_disk_io_write_bookmark_exception(log_file, tmp_path, mock_bookmark, exception_type, mock_type):
    log_path = os.path.join(tmp_path, "test.log")
    log_file.open(log_path)
    log_file.log_file_handler.write = mock_type
    with pytest.raises(exception_type):
        log_file.write(record_type="B", record=mock_bookmark, signal=[])


def test_disk_io_close_log_file(log_file):
    with patch('builtins.open', mock_open()) as mock_file:
        log_file.open("test.log")
        log_file.close()
        mock_file().close.assert_called_once()


def test_disk_io_open_makedirs_error(log_file):
    with patch('os.makedirs', side_effect=IOError("Failed to create directory")):
        log_file.open("/nonexistent/path/test.log")
        # Test passes if no exception is raised, as error is logged but not raised


def test_disk_io_close_error(log_file, tmp_path):
    log_path = tmp_path / "test.log"
    log_file.open(str(log_path))

    # Mock the file close to raise an error
    log_file.log_file_handler.close = MagicMock(side_effect=OSError("Close failed"))

    # Test should complete without raising exception (error is logged)
    log_file.close()

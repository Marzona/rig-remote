import pytest
import csv
from rig_remote.disk_io import IO, LogFile
from rig_remote.exceptions import InvalidPathError
import tempfile
import os
from unittest.mock import patch, mock_open


def test_disk_io_csv_load_happy_path():
    io = IO()
    filename = "./test/test_files/test-rig_remote-bookmarks.csv"
    io.csv_load(csv_file=filename, delimiter=",")
    assert len(io.row_list) == 25


@pytest.mark.parametrize(
    "filename",
    [
        "./test/test_files/no_file",
    ],
)
def test_disk_io_csv_load_non_happy_path(filename):
    io = IO()
    with pytest.raises(InvalidPathError):
        io.csv_load(csv_file=filename, delimiter=",")
    assert len(io.row_list) == 0


def test_dksk_io_csv_save():
    io = IO()
    temp_dir = tempfile.TemporaryDirectory()
    filename = "test_file.csv"
    file_path = os.path.join(temp_dir.name, filename)
    io.row_list.append(["118600000,AM,Dublin airport Tower,O"])
    io.csv_save(file_path, ",")
    io.row_list = []
    io.csv_load(csv_file=file_path, delimiter=",")
    io.row_list == [["[118600000]", "['AM']", "['Dublin airport Tower']", "['O']"]]
    temp_dir.cleanup()


@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_dksk_io_csv_save2(mock_file):
    io = IO()
    filename = "test_file.csv"
    io.row_list.append(["118600000,AM,Dublin airport Tower,O"])

    with patch("csv.writer") as mock_writer:
        io.csv_save(csv_file=filename, delimiter=",")
        assert mock_writer.call_args[1] == {"delimiter": ","}
        mock_writer.assert_called_once()
        assert mock_file.call_args_list[0][0] == (filename, "w")


@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_dksk_io_csv_save_error(mock_file):
    io = IO()
    filename = "test_file.csv"
    io.row_list.append(["118600000,AM,Dublin airport Tower,O"])
    with patch("csv.writer") as mock_writer:
        mock_writer.side_effect = IOError()
        io.csv_save(csv_file=filename, delimiter=",")
        assert io.row_list == []


def test_disk_io_non_existent_path():
    io = IO()
    with pytest.raises(InvalidPathError):
        io._path_check("")


def test_disk_io_good_path_csv_save():
    io = IO()
    io.csv_save("/tmp/test.csv", ",")


def test_disk_io_bad_file_csv_save():
    io = IO()
    with pytest.raises(TypeError):
        io.csv_save(["/tmp/test.csv", ","])


def test_disk_io_bad_file2_csv_save():
    io = IO()
    io.row_list = [2, 2]
    with pytest.raises(csv.Error):
        io.csv_save("/tmp/test.csv", ",")


def test_disk_io_no_logfile():
    lf = LogFile()
    with pytest.raises(AttributeError):
        lf.write("B", "122", ["2", "2"])


def test_disk_io_bad_data1():
    lf = LogFile()
    lf.open("/tmp/nofile")
    with pytest.raises(TypeError):
        lf.write("B", 122, ["2", "2"])


def test_disk_io_bad_data2():
    lf = LogFile()
    lf.open("/tmp/nofile")
    with pytest.raises(TypeError):
        lf.write("C", "122", ["2", "2"])

#!/usr/bin/env python

# import modules
import pytest
import os
from rig_remote.bookmarks import Bookmarks
from rig_remote.disk_io import IO
from mock import MagicMock, Mock
import tkFileDialog
from rig_remote.exceptions import (
                                   InvalidPathError,
                                   FormatError,
                                  )
from rig_remote.constants import (
                                  GQRX_BOOKMARK_HEADER,
                                  CBB_MODES,
                                 )

import ttk
@pytest.fixture
def bk():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    bk_list = []
    bk_list.append(value)
    bk = Bookmarks(tree, io=IO())
    bk._insert_bookmarks(bk_list)

    return bk

def test_export_panel():
    bk = Bookmarks("test", io=IO())
    tkFileDialog.asksaveasfilename = MagicMock()
    tkFileDialog.asksaveasfilename.return_Value = "testfile"
    bk._export_panel() == "testfile"

def test_detect_format():
    bk = Bookmarks("test", io=IO())
    with pytest.raises(InvalidPathError):
        bk._detect_format("")

def test_export_rig_remote_bad_attrib():
    bk = Bookmarks("test", io=IO())
    bk._export_panel = MagicMock()
    bk._export_panel.return_value == ""
    with pytest.raises(AttributeError):
        bk.export_rig_remote()


def test_save_gqrx():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    assert (isinstance(bk.bookmarks.row_list, list))
    assert (len(bk.bookmarks.row_list) == 0)


def test_save_gqrx_len():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    assert (len(bk.bookmarks.row_list) == 1)

def test_save_gqrx_freq():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    int(bk.bookmarks.row_list[0][0])

def test_save_gqrx_mode():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    assert (bk.bookmarks.row_list[0][2] in CBB_MODES)

def test_save_gqrx_tag():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    assert (bk.bookmarks.row_list[0][4] == "Untagged")

def test_save_gqrx_comment():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_save = MagicMock()
    bk.bookmarks.return_value = None
    bk._save_gqrx("test")
    assert(isinstance(bk.bookmarks.row_list[0][1], str))

def test_insert_bookmark_values_present(bk):
    assert ("values" in (bk.tree.item("I001")).keys())

def test_insert_bookmark_text_present(bk):
    assert ("text" in (bk.tree.item("I001")).keys())

def test_insert_bookmark_image_present(bk):
    assert ("image" in (bk.tree.item("I001")).keys())

def test_insert_bookmark_values(bk):
    assert (bk.tree.item("I001")["values"] == [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O'])

def test_insert_bookmark_image(bk):
    assert (bk.tree.item("I001")["image"] == "")

def test_insert_bookmark_text(bk):
    assert (bk.tree.item("I001")["text"] == "")

def test_detect_format(bk):
    with pytest.raises(InvalidPathError):
        bk._detect_format("")

def test_detect_format_dir(bk):
    with pytest.raises(IOError):
        bk._detect_format("/tmp")

def test_load_nothing(bk):
    assert (bk.load("","") == None)

def test_import_rig_remote():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.load = MagicMock()
    bk.load.return_value = "test"
    bk._import_rig_remote("test")
    bk.load.assert_called_once_with("test", ",", silent=False)

def test_import_gqrx():
    tree = ttk.Treeview(columns=("frequency",
                                 "mode",
                                 "description",
                                 "lockout"),
                        displaycolumns=("frequency",
                                        "mode",
                                        "description"),
                        show="headings")
    value =  [u'5,955,000', u'AM', u'found on 18.34 jan 08 2015', u'O']
    tree.insert("",0,values = value)
    bk = Bookmarks(tree, io=IO())
    bk.bookmarks.csv_load = MagicMock()
    bk.bookmarks.csv_load.return_value = "test"
    bk.bookmarks.row_list.append([""])
    bk.bookmarks.row_list.append([""])
    bk.bookmarks.row_list.append([""])
    bk.bookmarks.row_list.append([""])
    bk.bookmarks.row_list.append([""])
    bk.bookmarks.row_list.append(["    28800000"," standing spike           "," Narrow FM           ","      10000"," Untagged"])
    bk._insert_bookmarks = MagicMock()
    bk._import_gqrx("test")
    bk._insert_bookmarks.assert_called_once_with([['28800000', 'FM', 'standing spike']])

"""
Remote application that interacts with rigs using rigctl protocol.
Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Simone Marzona
License: MIT License
Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
TAS - Tim Sweeney - mainetim@gmail.com
"""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from rig_remote.ui import RigRemote

import logging


logger = logging.getLogger(__name__)


def khertz_to_hertz(value:int)->int:
    if not isinstance (value, int):
        logger.error("khertz_to_hertz: value must be an integer, got %s", type(value))
        raise TypeError("value must be an integer")
    return value * 1000


def shutdown(window:RigRemote)->None:
    """Here we quit. Before exiting, if save_exit checkbox is checked
    we save the configuration of the app and the bookmarks.
    We call store_conf and we destroy the main window

    :param window: object that represent the UI
    :returns: none
    """
    if window.ckb_save_exit.get_str_val():
        window.bookmarks.save(bookmarks_file=window.bookmarks_file)
        window.ac.store_conf(window=window)
    window.master.destroy()



def center_window(window:RigRemote, width:int=300, height:int=200)->None:
    """Centers a given window with a given size

    :param window: the window instance to be centered
    :param width: width of the window
    :param height: height of the window
    """

    # get screen width and height
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    # calculate position x and y coordinates
    x = (screen_width / 2) - (width / 2)
    y = (screen_height / 2) - (height / 2)
    window.geometry("%dx%d+%d+%d" % (width, height, x, y)) # type: ignore

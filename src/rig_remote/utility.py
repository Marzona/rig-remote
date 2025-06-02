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

import logging

logger = logging.getLogger(__name__)


def khertz_to_hertz(value):
    return int(value) * 1000


def shutdown(window):
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



def center_window(window, width=300, height=200):
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
    window.geometry("%dx%d+%d+%d" % (width, height, x, y))

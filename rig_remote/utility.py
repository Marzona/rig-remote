#!/usr/bin/env python

"""
Remote application that interacts with rigs using rigctl protocol.
Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation
Author: Rafael Marmelo
Author: Simone Marzona
License: MIT License
Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2016 Tim Sweeney
TAS - Tim Sweeney - mainetim@gmail.com
2016/05/04 - TAS - Moved frequency_pp and frequency_pp_parse here.
2016/05/07 - TAS - Moved is_valid_hostname and is_valid_port here.
2016/05/08 - TAS - Added this_file_exists.
2016/05/30 - TAS - Added process_path.
"""

from socket import gethostbyname, gaierror
import logging

logger = logging.getLogger(__name__)


def khertz_to_hertz(value):
    return int(value) * 1000


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


def shutdown(window, silent=False):
    """Here we quit. Before exiting, if save_exit checkbox is checked
    we save the configuration of the app and the bookmarks.
    We call store_conf and we destroy the main window

    :param window: object that represent the UI
    :type window: tkk instance
    :param silent: handles the visualization of the message box
    :type silent: boolean
    :returns: none
    """

    if window.ckb_save_exit.get_str_val() == "true":
        window.io.save(window.bookmarks_file)
        store_conf(window)

    window.master.destroy()


def store_conf(window):
    """populates the ac object reading the info from the UI.

    :param window: object used to hold the app configuration.
    :type window: AppConfig() object
    :returns window.ac: window instance with ac obj updated.
    """

    window.ac.config["hostname1"] = window.params["txt_hostname1"].get()
    window.ac.config["port1"] = window.params["txt_port1"].get()
    window.ac.config["hostname2"] = window.params["txt_hostname2"].get()
    window.ac.config["port2"] = window.params["txt_port2"].get()
    window.ac.config["interval"] = window.params["txt_interval"].get()
    window.ac.config["delay"] = window.params["txt_delay"].get()
    window.ac.config["passes"] = window.params["txt_passes"].get()
    window.ac.config["sgn_level"] = window.params["txt_sgn_level"].get()
    window.ac.config["range_min"] = window.params["txt_range_min"].get()
    window.ac.config["range_max"] = window.params["txt_range_max"].get()
    window.ac.config["wait"] = window.params["ckb_wait"].get_str_val()
    window.ac.config["record"] = window.params["ckb_record"].get_str_val()
    window.ac.config["log"] = window.params["ckb_log"].get_str_val()
    window.ac.config["always_on_top"] = window.ckb_top.get_str_val()
    window.ac.config["save_exit"] = window.ckb_save_exit.get_str_val()
    window.ac.config["auto_bookmark"] = window.params["ckb_auto_bookmark"].get_str_val()
    window.ac.config["bookmark_filename"] = window.bookmarks_file
    window.ac.config["log_filename"] = window.log_file
    window.ac.write_conf()
    return window.ac


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

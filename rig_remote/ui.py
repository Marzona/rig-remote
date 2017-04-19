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

2016/02/16 - TAS - Added code to support continuous bookmark scanning.
                   Temporarily disabled freq activity logging and notification.
                   Scan call now a separate thread.
                   Added a "stop" button.
2016/02/18 - TAS - Changed code from "monitor mode" fixed looping to
                   choice of variable or infinite looping.
                   Added a "pass count" field in config display.
                   Only done in bookmark scanning, still need to rework
                   frequency scanning to match. Also need to implement
                   changes in delay code (to allow for wait on signal).
2016/02/19 - TAS - Added frequency scan "Stop" button.
2016/02/20 - TAS - Added "wait" checkbox. See scanning.py for notes.
2016/02/22 - TAS - Removed "stop" button and use a "toggle" function for
                   start/stop of scanning. Add "lock" button to UI as
                   placeholder, but haven't implemented lockout yet.
2016/02/23 - TAS - Added lockout field to treeview and coded toggle for it.
2016/02/24 - TAS - Added lockout highlight code. Changed how bookmarks
                   are passed to scan thread. Added support for logging
                   scanning activity to a file.
2016/03/11 - TAS - Changed program parameter storage to a dict, to make
                   validity checking and thread updating easier. Added
                   a queue to pass updated parameters to scanning thread.
                   Added bindings to parameter widgets to check type
                   validity of numeric parameters, and force updates onto
                   queue. Added Checkbutton class to streamline handling.
                   TODO: Change initial thread parameter passing to
                   a dict also, and then flesh out skeleton update code
                   in scanning thread. Update config code to add new
                   checkboxes.
2016/03/13 - TAS - Blank parameter fields now default to DEFAULT_CONFIG values.
                   (Github issue #21)
2016/03/15 - TAS - Added more scanning option validation. Changed scan
                   initialization to pass
                   most params in a dict.
2016/03/19 - TAS - Added validation of the config file when it is applied.
2016/03/20 - TAS - Added some validation of user frequency input, and of the
                   bookmark file when it
                   is loaded.
2016/03/21 - TAS - Added new checkbutton config data to config file handling
                   methods.
2016/04/12 - TAS - Added back auto-bookmarking option on frequency scan.
                   Bookmarks are processed once the
                   scan thread has completed. Only one bookmark per frequency.
                   (If logging enabled, all occurences are logged.)
2016/04/24 - TAS - Changed communications between main and scan threads to use
                   STMessenger class, to
                   enable thread-safe notification of scan thread termination
                   (Issue #30).
2016/05/02 - TAS - Refactor is_valid_hostname(), and the methods that call it,
                   to properly handle bad input.
2016/05/30 - TAS - Stripped out old path support.
"""

# import modules

import logging
from rig_remote.constants import (
                                  ALLOWED_BOOKMARK_TASKS,
                                  SUPPORTED_SCANNING_ACTIONS,
                                  CBB_MODES,
                                  LEN_BM,
                                  BM,
                                  DEFAULT_CONFIG,
                                  UI_EVENT_TIMER_DELAY,
                                  ABOUT,
                                  )
from rig_remote.exceptions import UnsupportedScanningConfigError
from rig_remote.bookmarks import Bookmarks
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningTask
from rig_remote.scanning import Scanning
from rig_remote.utility import (
                                frequency_pp,
                                frequency_pp_parse,
                                is_valid_port,
                                is_valid_hostname,
                                ToolTip,
                                build_rig_uri,
                                shutdown,
                                RCCheckbutton,
                                center_window,
                                )
import Tkinter as tk
import ttk
from Tkinter import LabelFrame
import tkMessageBox
import threading
import itertools
import webbrowser
from rig_remote.stmessenger import STMessenger

# logging configuration
logger = logging.getLogger(__name__)

# classes definition
class RigRemote(ttk.Frame):
    """Remote application that interacts with the rig using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.
    :raises: none
    :returns: none
    """

    def __init__(self, root, ac):
        ttk.Frame.__init__(self, root)
        self.root = root
        self.params = {}
        self.params_last_content = {}
        self.alt_files = {}
        self.bookmarks_file = ac.config["bookmark_filename"]
        self.log_file = ac.config["log_filename"]
        self.build(ac)
        self.params["cbb_mode1"].current(0)
        self.focus_force()
        self.update()
        # bookmarks loading on start
        self.bookmarks = Bookmarks(self.tree)
        self.bookmarks.load(self.bookmarks_file, ",")
        self.scan_thread = None
        self.scan_mode = None
        self.scanning = None
        self.selected_bookmark = None
        self.scanq = STMessenger()
        self.new_bookmark_list = []
        self.bind_all("<1>", lambda event:self.focus_set(event))
        self.ac = ac
        self.buildmenu(root)

    def pop_up_about(self):
        """Describes a pop-up window.
        """

        # the pop-up needs to be on top
        self.ckb_top.val.set(False)
        panel = tk.Toplevel(self.root)
        center_window(panel, 500, 150)
        text = tk.StringVar()
        label = tk.Label(panel, textvariable=text)
        text.set(ABOUT)
        label.pack()

    def buildmenu(self, root):
        """method for building the menu of the main window
        """

        menubar = tk.Menu(root)
        appmenu = tk.Menu(menubar, tearoff=0)
        appmenu.add_command(label="About", command=self.pop_up_about)
        appmenu.add_command(label="Quit",
                            command=lambda: shutdown(
                                                     self
                                                    ))

        bookmarksmenu = tk.Menu(menubar, tearoff=0)
        exportmenu = tk.Menu(menubar, tearoff=0)
        bookmarksmenu.add_command(label="Import",
                                  command=self.bookmarks.import_bookmarks)
        bookmarksmenu.add_cascade(label = "Export", menu = exportmenu)
        exportmenu.add_command(label="Export GQRX",
                                  command=self.bookmarks.export_gqrx)
        exportmenu.add_command(label="Export rig-remote",
                                  command=self.bookmarks.export_rig_remote)

        root.config(menu=menubar)
        menubar.add_cascade(label="Rig Remote", menu=appmenu)
        menubar.add_cascade(label="Bookmarks", menu=bookmarksmenu)

    def build(self, ac):
        """Build and initialize the GUI widgets.
        :param: ac
        :raises: none
        :returns: None
        """
        self.master.title("Rig Remote")
        self.master.minsize(800, 244)
        self.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # bookmarks list

        self.tree = ttk.Treeview(self,
                                 columns=("frequency",
                                          "mode",
                                          "description",
                                          "lockout"),
                                 displaycolumns=("frequency",
                                                 "mode",
                                                 "description"),
                                  show="headings")
        t_tree = ToolTip(self.tree,
                         follow_mouse=1,
                         text="Your bookmark list")

        self.tree.heading('frequency',
                          text='Frequency',
                          anchor=tk.CENTER)
        self.tree.column('frequency',
                         width=100,
                         stretch=True,
                         anchor=tk.CENTER)
        self.tree.heading('mode',
                          text='Mode',
                          anchor=tk.CENTER)
        self.tree.column('mode',
                         width=70,
                         stretch=True,
                         anchor=tk.CENTER)
        self.tree.heading('description',
                          text='Description',
                          )
        self.tree.column('description',
                         stretch=True,
                         )
        ysb = ttk.Scrollbar(self,
                            orient=tk.VERTICAL,
                            command=self.tree.yview)
        ysb.grid(row=0,
                 column=2,
                 rowspan=5,
                 sticky=tk.NS)
        xsb = ttk.Scrollbar(self,
                            orient=tk.HORIZONTAL,
                            command=self.tree.xview)
        xsb.grid(row=5,
                 column=0,
                 sticky=tk.NSEW
                 )
        self.tree.configure(
                            yscroll=ysb.set,
                            )
        self.tree.grid(row=0,
                       column=0,
                       rowspan=5,
                       sticky=tk.NSEW
                       )

        # vertical separator between bookmarks and comands
        ttk.Frame(self).grid(row=0,
                             column=2,
                             rowspan=5,
                             padx=5)
        # right-side container
        self.rig_config_menu = LabelFrame(self,
                                          text="First Rig configuration")
        self.rig_config_menu.grid(row=0,
                                  column=3,
                                  sticky=tk.NSEW)

        ttk.Label(self.rig_config_menu,
                  text="Hostname:").grid(row=1,
                                         column=2,
                                         sticky=tk.W)
        self.params["txt_hostname1"] = ttk.Entry(self.rig_config_menu,
                                                name="txt_hostname1")
        self.params["txt_hostname1"].grid(row=1,
                                         column=3,
                                         columnspan=2,
                                         padx=2,
                                         pady=2,
                                        sticky=tk.EW)
        t_txt_hostname = ToolTip(self.params["txt_hostname1"],
                                 follow_mouse=1,
                                 text="Hostname to connect.")
        self.params["txt_hostname1"].bind("<Return>", self.process_entry)
        self.params["txt_hostname1"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.rig_config_menu,
                  text="Port:").grid(row=2,
                                     column=2,
                                     sticky=tk.W)
        self.params["txt_port1"] = ttk.Entry(self.rig_config_menu,
                                            name="txt_port1")
        self.params["txt_port1"].grid(row=2,
                                     column=3,
                                     padx=2,
                                     pady=2,
                                   sticky=tk.EW)
        t_txt_port1 = ToolTip(self.params["txt_port1"],
                             follow_mouse=1,
                             text="Port to connect.")
        self.params["txt_port1"].bind("<Return>", self.process_entry)
        self.params["txt_port1"].bind("<FocusOut>", self.process_entry)

        # second rig config

        self.rig_config_menu = LabelFrame(self,
                                          text="Second Rig configuration")
        self.rig_config_menu.grid(row=0,
                                  column=4,
                                  sticky=tk.NSEW)

        ttk.Label(self.rig_config_menu,
                  text="Hostname:").grid(row=1,
                                         column=3,
                                         sticky=tk.W)
        self.params["txt_hostname2"] = ttk.Entry(self.rig_config_menu,
                                                name="txt_hostname2")
        self.params["txt_hostname2"].grid(row=1,
                                         column=4,
                                         columnspan=2,
                                         padx=2,
                                         pady=2,
                                        sticky=tk.EW)
        t_txt_hostname = ToolTip(self.params["txt_hostname2"],
                                 follow_mouse=1,
                                 text="Hostname to connect.")
        self.params["txt_hostname2"].bind("<Return>", self.process_entry)
        self.params["txt_hostname2"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.rig_config_menu,
                  text="Port:").grid(row=2,
                                     column=3,
                                     sticky=tk.W)
        self.params["txt_port2"] = ttk.Entry(self.rig_config_menu,
                                            name="txt_port2")
        self.params["txt_port2"].grid(row=2,
                                     column=4,
                                     padx=2,
                                     pady=2,
                                   sticky=tk.EW)
        t_txt_port2 = ToolTip(self.params["txt_port2"],
                             follow_mouse=1,
                             text="Port to connect.")
        self.params["txt_port2"].bind("<Return>", self.process_entry)
        self.params["txt_port2"].bind("<FocusOut>", self.process_entry)


        # second rig bookmarking
        # horizontal separator
        ttk.Frame(self.rig_config_menu).grid(row=3,
                                             column=1,
                                             columnspan=3,
                                             pady=5)

        self.rig_control_menu = LabelFrame(self,
                                           text="Second Rig Control")
        self.rig_control_menu.grid(row=1,
                                   column=4,
                                   stick=tk.NSEW)

        ttk.Label(self.rig_control_menu,
                  text="Frequency:").grid(row=5,
                                          column=1,
                                          sticky=tk.W)
        self.params["txt_frequency2"] = ttk.Entry(self.rig_control_menu,
                                                 name="txt_frequency2")
        self.params["txt_frequency2"].grid(row=5,
                                          column=2,
                                          columnspan=3,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_frequency = ToolTip(self.params["txt_frequency2"],
                                  follow_mouse=1,
                                  text="Frequency to tune on this rig.")
        ttk.Label(self.rig_control_menu,
                  text="Hz").grid(row=5,
                                   column=4,
                                   sticky=tk.EW)

        ttk.Label(self.rig_control_menu,
                  text="Mode:").grid(row=6,
                                     column=1,
                                     sticky=tk.W)
        self.params["cbb_mode2"] = ttk.Combobox(self.rig_control_menu,
                                                name="cbb_mode2",width=15)
        self.params["cbb_mode2"].grid(row=6,
                                      column=2,
                                      columnspan=3,
                                      padx=2,
                                      pady=2,
                                      sticky=tk.EW)
        t_cbb_mode2 = ToolTip(self.params["cbb_mode2"],
                              follow_mouse=1,
                              text="Mode to use for tuning the frequency.")
        self.params["cbb_mode2"]['values'] = CBB_MODES

        ttk.Label(self.rig_control_menu,
                  text="Description:").grid(row=7,
                                            column=1,
                                            sticky=tk.EW)
        self.params["txt_description2"] = ttk.Entry(self.rig_control_menu,
                                                    name="txt_description2")
        self.params["txt_description2"].grid(row=7,
                                             column=2,
                                             columnspan=3,
                                             padx=2,
                                             pady=2,
                                             sticky=tk.EW)
        t_txt_description2 = ToolTip(self.params["txt_description2"],
                                     follow_mouse=1,
                                     text="Description of the bookmark.")

        self.btn_add2 = ttk.Button(self.rig_control_menu,
                                   text="Add",
                                   width=7,
                                   command=self.cb_second_add)
        t_btn_add2 = ToolTip(self.btn_add2,
                             follow_mouse=1,
                             text="Bookmark this frequency.")
        self.btn_add2.grid(row=9,
                           column=2,
                           padx=2,
                           pady=2)

        self.btn_delete2 = ttk.Button(self.rig_control_menu,
                                      text="Remove",
                                      width=7,
                                      command=self.cb_delete2)
        t_btn_delete2 = ToolTip(self.btn_delete2,
                               follow_mouse=1,
                               text="Remove this frequency from bookmarks.")
        self.btn_delete2.grid(row=9,
                              column=1,
                              padx=2,
                              pady=2)

        self.btn_load2 = ttk.Button(self.rig_control_menu,
                                    text="Get",
                                    width=7,
                                    command=self.cb_second_get_frequency)
        t_btn_load2 = ToolTip(self.btn_load2,
                              follow_mouse=1,
                              text="Get the frequency and mode from the rig.")
        self.btn_load2.grid(row=8,
                            column=3,
                            padx=2,
                            pady=2)

        self.btn_tune2 = ttk.Button(self.rig_control_menu,
                                    text="Set",
                                    width=7,
                                    command=self.cb_second_set_frequency)
        t_btn_tune2 = ToolTip(self.btn_tune2,
                             follow_mouse=1,
                             text="Tune the frequency and mode from the "
                                  "rig control panel above.")

        self.btn_tune2.grid(row=8,
                            column=1,
                            padx=2,
                            pady=2)

        self.btn_recall2 = ttk.Button(self.rig_control_menu,
                                      text="Recall",
                                      width=7,
                                   command=self.cb_second_fill_form)
        t_btn_recall2 = ToolTip(self.btn_recall2,
                                follow_mouse=1,
                                text="Recall the frequency and mode from the "
                                     "bookmarks into this rig control panel.")
        t_btn_recall2 = ToolTip(self.btn_recall2,
                                follow_mouse=1,
                                text="Recall the frequency and mode from the "
                                     "bookmarks into this rig control panel.")

        self.btn_recall2.grid(row=9,
                              column=3,
                              padx=2,
                              pady=2)

        # horizontal separator
        ttk.Frame(self.rig_config_menu).grid(row=3,
                                             column=0,
                                             columnspan=3,
                                             pady=5)

        self.rig_control_menu = LabelFrame(self,
                                           text="First Rig Control")
        self.rig_control_menu.grid(row=1,
                                   column=3,
                                   stick=tk.NSEW)

        ttk.Label(self.rig_control_menu,
                  text="Frequency:").grid(row=5,
                                          column=0,
                                          sticky=tk.W)
        self.params["txt_frequency1"] = ttk.Entry(self.rig_control_menu,
                                                 name="txt_frequency1")
        self.params["txt_frequency1"].grid(row=5,
                                          column=1,
                                          columnspan=3,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_frequency = ToolTip(self.params["txt_frequency1"],
                                  follow_mouse=1,
                                  text="Frequency to tune on this rig.")
        ttk.Label(self.rig_control_menu,
                  text="Hz").grid(row=5,
                                   column=3,
                                   sticky=tk.EW)

        ttk.Label(self.rig_control_menu,
                  text="Mode:").grid(row=6,
                                     column=0,
                                     sticky=tk.W)
        self.params["cbb_mode1"] = ttk.Combobox(self.rig_control_menu,
                                               name="cbb_mode1",width=15)
        self.params["cbb_mode1"].grid(row=6,
                                     column=1,
                                     columnspan=3,
                                     padx=2,
                                     pady=2,
                                     sticky=tk.EW)
        t_cbb_mode1 = ToolTip(self.params["cbb_mode1"],
                              follow_mouse=1,
                              text="Mode to use for tuning the frequency.")
        self.params["cbb_mode1"]['values'] = CBB_MODES

        ttk.Label(self.rig_control_menu,
                  text="Description:").grid(row=7,
                                            column=0,
                                            sticky=tk.EW)
        self.params["txt_description1"] = ttk.Entry(self.rig_control_menu,
                                                   name="txt_description1")
        self.params["txt_description1"].grid(row=7,
                                            column=1,
                                            columnspan=3,
                                            padx=2,
                                            pady=2,
                                            sticky=tk.EW)
        t_txt_description1 = ToolTip(self.params["txt_description1"],
                                    follow_mouse=1,
                                    text="Description of the bookmark.")

        self.btn_add1 = ttk.Button(self.rig_control_menu,
                                  text="Add",
                                  width=7,
                                  command=self.cb_first_add)
        t_btn_add1 = ToolTip(self.btn_add1,
                            follow_mouse=1,
                            text="Bookmark this frequency.")
        self.btn_add1.grid(row=9,
                          column=1,
                          padx=2,
                          pady=2)

        self.btn_delete1 = ttk.Button(self.rig_control_menu,
                                     text="Remove",
                                     width=7,
                                     command=self.cb_delete1)
        t_btn_delete1 = ToolTip(self.btn_delete1,
                               follow_mouse=1,
                               text="Remove the selected bookmark.")
        self.btn_delete1.grid(row=9,
                             column=0,
                             padx=2,
                             pady=2)

        self.btn_load1 = ttk.Button(self.rig_control_menu,
                                   text="Get",
                                   width=7,
                                   command=self.cb_first_get_frequency)
        t_btn_load1 = ToolTip(self.btn_load1,
                             follow_mouse=1,
                             text="Get the frequency and mode from the rig.")

        self.btn_load1.grid(row=8,
                           column=2,
                           padx=2,
                           pady=2)

        self.btn_tune1 = ttk.Button(self.rig_control_menu,
                                   text="Set",
                                   width=7,
                                   command=self.cb_first_set_frequency)
        t_btn_tune1 = ToolTip(self.btn_tune1,
                              follow_mouse=1,
                              text="Tune the frequency and mode from the "
                                   "rig control panel above.")

        self.btn_tune1.grid(row=8,
                            column=0,
                            padx=2,
                            pady=2)

        self.btn_recall1 = ttk.Button(self.rig_control_menu,
                                      text="Recall",
                                      width=7,
                                      command=self.cb_first_fill_form)
        t_btn_recall1 = ToolTip(self.btn_recall1,
                                follow_mouse=1,
                                text="Recall the frequency and mode from the "
                                     "bookmarks into this rig control panel.")

        self.btn_recall1.grid(row=9,
                              column=2,
                              padx=2,
                              pady=2)

        # horizontal separator
        ttk.Frame(self.rig_control_menu).grid(row=9,
                                              column=0,
                                              columnspan=3,
                                              pady=5)


        self.scanning_conf_menu = LabelFrame(self, text="Scanning options")
        self.scanning_conf_menu.grid(row=4,
                                    column=3,
                                    stick=tk.NSEW)

        ttk.Label(self.scanning_conf_menu,
                  text="Signal level:").grid(row=10,
                                             column=0,
                                             sticky=tk.W)
        self.params["txt_sgn_level"] = ttk.Entry(self.scanning_conf_menu,
                                                 name="txt_sgn_level",
                                                 width=10)
        self.params["txt_sgn_level"].grid(row=10,
                                          column=1,
                                          columnspan=1,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_sgn_level = ToolTip(self.params["txt_sgn_level"],
                                  follow_mouse=1,
                                  text="Signal level to trigger on.")
        self.params["txt_sgn_level"].bind("<Return>", self.process_entry)
        self.params["txt_sgn_level"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.scanning_conf_menu,
                  text=" dBFS").grid(row=10,
                                     column=2,
                                     padx=0,
                                     sticky=tk.W)

        ttk.Label(self.scanning_conf_menu,
                  text="Delay:").grid(row=13,
                                      column=0,
                                      sticky=tk.W)
        self.params["txt_delay"] = ttk.Entry(self.scanning_conf_menu,
                                             name="txt_delay", width=10)
        t_txt_delay = ToolTip(self.params["txt_delay"],
                              follow_mouse=1,
                              text="Delay after finding a signal.")
        self.params["txt_delay"].grid(row=13,
                                      column=1,
                                      columnspan=1,
                                      padx=2,
                                      pady=2,
                                      sticky=tk.W)
        ttk.Label(self.scanning_conf_menu,
                  text=" seconds").grid(row=13,
                                       padx=0,
                                       column=2,
                                       sticky=tk.EW)
        self.params["txt_delay"].bind("<Return>", self.process_entry)
        self.params["txt_delay"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.scanning_conf_menu,
                  text="Passes:").grid(row=14,
                                       column=0,
                                       sticky=tk.W)
        self.params["txt_passes"] = ttk.Entry(self.scanning_conf_menu,
                                              name="txt_passes", width=10)
        self.params["txt_passes"].grid(row=14,
                                       column=1,
                                       columnspan=1,
                                       padx=2,
                                       pady=2,
                                       sticky=tk.W)
        t_txt_passes = ToolTip(self.params["txt_passes"],
                              follow_mouse=1,
                              text="Number of scans.")
        ttk.Label(self.scanning_conf_menu,
                  text="  0=Infinite").grid(row=14,
                                            padx=0,
                                            column=2,
                                            sticky=tk.EW)
        self.params["txt_passes"].bind("<Return>", self.process_entry)
        self.params["txt_passes"].bind("<FocusOut>", self.process_entry)

        self.cb_wait = tk.BooleanVar()
        self.params["ckb_wait"] = RCCheckbutton(self.scanning_conf_menu,
                                                name="ckb_wait",
                                                text="Wait",
                                                onvalue=True,
                                                offvalue=False,
                                                variable=self.cb_wait)
        self.params["ckb_wait"].grid(row=15,
                                     column=0,
                                     columnspan=1,
                                     sticky=tk.E)
        t_ckb_wait = ToolTip(self.params["ckb_wait"],
                             follow_mouse=1,
                             text="Waits after having found an active"
                                  " frequency.")
        self.params["ckb_wait"].val = self.cb_wait
        self.cb_wait.trace("w", self.process_wait)

        self.cb_record = tk.BooleanVar()
        self.params["ckb_record"] = RCCheckbutton(self.scanning_conf_menu,
                                                  name="ckb_record",
                                                  text="Record",
                                                  onvalue=True,
                                                  offvalue=False,
                                                  variable=self.cb_record)
        self.params["ckb_record"].grid(row=15,
                                       column=1,
                                       columnspan=1,
                                       sticky=tk.E)
        t_ckb_record = ToolTip(self.params["ckb_record"],
                               follow_mouse=1,
                               text="Enable the recording of signal to"
                                    " a file.")
        self.params["ckb_record"].val = self.cb_record
        self.cb_record.trace("w", self.process_record)

        self.cb_log = tk.BooleanVar()
        self.params["ckb_log"] = RCCheckbutton(self.scanning_conf_menu,
                                               name="ckb_log",
                                               text="Log",
                                               onvalue=True,
                                               offvalue=False,
                                               variable=self.cb_log)
        t_ckb_log = ToolTip(self.params["ckb_log"],
                            follow_mouse=1,
                            text="Logs the activities to a file.")
        self.params["ckb_log"].grid(row=15,
                                    column=3,
                                    columnspan=1,
                                    sticky=tk.E)
        self.params["ckb_log"].val = self.cb_log
        self.cb_log.trace("w", self.process_log)


        self.freq_scanning_menu = LabelFrame(self, text="Frequency scanning")
        self.freq_scanning_menu.grid(row=3,
                                     column=3,
                                     #rowspan=3,
                                     stick=tk.NSEW)

        self.freq_scan_toggle = ttk.Button(self.freq_scanning_menu,
                                          text="Start",
                                          command=self.frequency_toggle,
                                          )
        t_freq_scan_toggle = ToolTip(self.freq_scan_toggle,
                                     follow_mouse=1,
                                     text="Starts a frequency scan.")
        self.freq_scan_toggle.grid(row=17,
                                   column=2,
                                   padx=2,
                                   sticky=tk.W)

        ttk.Label(self.freq_scanning_menu,
                  text="Min/Max:").grid(row=12,
                                        column=0,
                                        sticky=tk.W)
        ttk.Label(self.freq_scanning_menu,
                  text="khz").grid(row=12,
                                   padx=0,
                                   column=3,
                                   sticky=tk.W)
        self.params["txt_range_min"] = ttk.Entry(self.freq_scanning_menu,
                                                 name="txt_range_min",
                                                 width=8)
        self.params["txt_range_min"].grid(row=12,
                                          column=1,
                                          columnspan=1,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_range_min = ToolTip(self.params["txt_range_min"],
                                  follow_mouse=1,
                                  text="Lower bound of the frequency"
                                       " band to scan.")
        self.params["txt_range_min"].bind("<Return>", self.process_entry)
        self.params["txt_range_min"].bind("<FocusOut>", self.process_entry)

        self.params["txt_range_max"] = ttk.Entry(self.freq_scanning_menu,
                                                 name="txt_range_max",
                                                 width=8)
        self.params["txt_range_max"].grid(row=12,
                                          column=2,
                                          columnspan=1,
                                          padx=0,
                                          pady=0,
                                          sticky=tk.W)
        t_txt_range_max = ToolTip(self.params["txt_range_max"],
                                  follow_mouse=1,
                                  text="Upper bound of the frequency"
                                       " band to scan.")
        self.params["txt_range_max"].bind("<Return>", self.process_entry)
        self.params["txt_range_max"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.freq_scanning_menu,
                  text="Interval:").grid(row=13,
                                         column=0,
                                         sticky=tk.W)
        self.params["txt_interval"] = ttk.Entry(self.freq_scanning_menu,
                                                name="txt_interval",
                                                width=6)
        self.params["txt_interval"].grid(row=13,
                                         column=1,
                                         columnspan=1,
                                         padx=2,
                                         pady=2,
                                         sticky=tk.W)
        t_txt_interval = ToolTip(self.params["txt_interval"],
                                 follow_mouse=1,
                                 text="Tune once every interval khz.")
        ttk.Label(self.freq_scanning_menu,
                  text="Khz").grid(row=13,
                                   padx=0,
                                   column=2,
                                   sticky=tk.EW)
        self.params["txt_interval"].bind("<Return>", self.process_entry)
        self.params["txt_interval"].bind("<FocusOut>", self.process_entry)

        self.cb_auto_bookmark = tk.BooleanVar()
        self.params["ckb_auto_bookmark"] = \
            RCCheckbutton(self.freq_scanning_menu,
                          name="ckb_auto_bookmark",
                          text="auto bookmark",
                          onvalue=True,
                          offvalue=False,
                          variable=self.cb_auto_bookmark)
        t_ckb_auto_bookmark = ToolTip(self.params["ckb_auto_bookmark"],
                                      follow_mouse=1,
                                      text="Bookmark any active frequency"
                                           " found.")
        self.params["ckb_auto_bookmark"].grid(row=17,
                                              column=0,
                                              columnspan=1)
        self.params["ckb_auto_bookmark"].val = self.cb_auto_bookmark
        self.cb_auto_bookmark.trace("w", self.process_auto_bookmark)

        ttk.Label(self.freq_scanning_menu,
                  text="Scan mode:").grid(row=16,
                                          column=0,
                                          sticky=tk.W)
        self.params["cbb_scan_mode"] = ttk.Combobox(self.freq_scanning_menu,
                                                    name="cbb_scan_mode",
                                                    width=4)
        self.params["cbb_scan_mode"].grid(row=16,
                                          column=1,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.EW)
        t_cbb_scan_mode = ToolTip(self.params["cbb_scan_mode"],
                                  follow_mouse=1,
                                  text="Mode to use for the frequency scan.")
        self.params["cbb_scan_mode"]['values'] = CBB_MODES

########### not ready yet
#        self.cb_aggr_scan = tk.BooleanVar()
#        self.params["ckb_aggr_scan"] = RCCheckbutton(self.scanning_conf_menu,
#                                                  name="aggr_scan",
#                                                  text="Aggr",
#                                                  onvalue=True,
#                                                  offvalue=False,
#                                                  variable=self.cb_aggr_scan)
#        self.params["ckb_aggr_scan"].grid(row=15,
#                                           column=2,
#                                           columnspan=1,
#                                           sticky=tk.E)
#        t_ckb_aggr_scan = ToolTip(self.params["ckb_aggr_scan"],
#                                   follow_mouse=1,
#                                   text="Split the frequency range "
#                                        "and use both rigs "
#                                        "simultaneously. Implies auto bookmark")
#        self.params["ckb_aggr_scan"].val = self.cb_aggr_scan
#        self.cb_aggr_scan.trace("w", self.process_record)

        ttk.Frame(self.freq_scanning_menu).grid(row=17,
                                                column=0,
                                                columnspan=3,
                                                pady=5)

        self.book_scanning_menu = LabelFrame(self, text="Bookmark scanning")
        self.book_scanning_menu.grid(row=3,
                                     column=4,
                                     stick=tk.NSEW)

        #horrible horizontal placeholder
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                                column=1,
                                sticky=tk.NSEW)
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                                column=2,
                                sticky=tk.NSEW)

        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                                column=3,
                                sticky=tk.NSEW)

        self.book_scan_toggle = ttk.Button(self.book_scanning_menu,
                                           text="Start",
                                           command=self.bookmark_toggle,
                                           )
        t_book_scan_toggle = ToolTip(self.book_scan_toggle,
                                     follow_mouse=1,
                                     text="Starts a bookmark scan.")
        self.book_scan_toggle.grid(row=18,
                                   column=1,
                                   columnspan=1,
                                   padx=2,
                                   sticky=tk.W)

        self.book_lockout = ttk.Button(self.book_scanning_menu,
                                       text="Lock",
                                       command=self.bookmark_lockout,
                                      )
        t_book_lockout = ToolTip(self.book_lockout,
                                 follow_mouse=1,
                                 text="Toggle skipping selected bookmark.")
        self.book_lockout.grid(row=18,
                               column=3,
                               columnspan=1,
                               padx=2,
                               sticky=tk.W)

        # horizontal separator
        ttk.Frame(self.book_scanning_menu).grid(row=19,
                                                column=0,
                                                columnspan=3,
                                                rowspan=1,
                                                pady=5)

        self.control_menu = LabelFrame(self, text="Options")

        self.control_menu.grid(row=4,
                               column=4,
                               stick=tk.NSEW)

        self.cb_top = tk.BooleanVar()
        self.ckb_top = RCCheckbutton(self.control_menu,
                                     text="Always on top",
                                     onvalue=True,
                                     offvalue=False,
                                     variable=self.cb_top)
        self.ckb_top.grid(row=21,
                          column=2,
                          columnspan=1,
                          padx=2,
                          sticky=tk.EW)
        t_ckb_top = ToolTip(self.ckb_top,
                            follow_mouse=1,
                            text="This window is always on top.")
        self.ckb_top.val = self.cb_top
        self.cb_top.trace("w", self.toggle_cb_top)

        self.cb_save_exit = tk.BooleanVar()
        self.ckb_save_exit = RCCheckbutton(self.control_menu,
                                           text="Save on exit",
                                           onvalue=True,
                                           offvalue=False,
                                           variable=self.cb_save_exit)
        self.ckb_save_exit.grid(row=21,
                                column=1,
                                columnspan=1,
                                padx=2,
                                sticky=tk.EW)
        t_ckb_save_exit = ToolTip(self.ckb_save_exit,
                                  follow_mouse=1,
                                  text="Save setting on exit.")
        self.ckb_save_exit.val = self.cb_save_exit

        # horizontal separator
        ttk.Frame(self.control_menu).grid(row=22,
                                          column=0,
                                          columnspan=3,
                                          pady=5)

    def focus_set(self, event) :
        """Give focus to screen object in click event. Used to
        force <FocusOut> callbacks.
        """

        if not isinstance(event.widget, basestring) :
            event.widget.focus_set()

    def apply_config(self, ac, silent = False):
        """Applies the config to the UI.

        :param ac: object instance for handling the app config
        :type ac: AppConfig object
        :param silent: suppress messagebox
        :type silent: boolean
        :raises : none
        :returns : none
        """

        eflag = False
        try:
            is_valid_hostname(ac.config["hostname1"])
        except ValueError:
            self.params["txt_hostname1"].insert(0, DEFAULT_CONFIG["hostname1"])
            if not silent:
                tkMessageBox.showerror("Config File Error"
                                       "One (or more) "
                                       "of the values in the config file was "
                                       "invalid, and the default was used "
                                       "instead.",
                                       parent=self)
        else:
            self.params["txt_hostname1"].insert(0, ac.config["hostname1"])
        # Test positive integer values
        for key in ("port1",
                    "interval",
                    "delay",
                    "passes",
                    "range_min",
                    "range_max") :
            ekey = "txt_" + key
            if str.isdigit(ac.config[key].replace(',','')) :
                self.params[ekey].insert(0, ac.config[key])
            else:
                self.params[ekey].insert(0, DEFAULT_CONFIG[key])
                eflag = True
        # Test integer values
        try :
            int(ac.config["sgn_level"])
        except ValueError :
            self.params["txt_sgn_level"].insert(0, DEFAULT_CONFIG["sgn_level"])
            eflag = True
        else:
            self.params["txt_sgn_level"].insert(0, ac.config["sgn_level"])
        if eflag :
            if not silent:
                tkMessageBox.showerror("Config File Error", "One (or more) "
                                   "of the values in the config file was "
                                   "invalid, and the default was used "
                                   "instead.", parent = self)
        self.params["ckb_auto_bookmark"].set_str_val(
                ac.config["auto_bookmark"].lower())
        self.params["ckb_record"].set_str_val(ac.config["record"].lower())
        self.params["ckb_wait"].set_str_val(ac.config["wait"].lower())
        self.params["ckb_log"].set_str_val(ac.config["log"].lower())
        self.ckb_save_exit.set_str_val(ac.config["save_exit"].lower())
        if ac.config["always_on_top"].lower() == "true":
            if self.ckb_top.is_checked() == False:
                self.ckb_top.invoke()

        self.rigctl = RigCtl(build_rig_uri(1, self.params))
        # Here we create a copy of the params dict to use when
        # checking validity of new input
        for key in self.params :
            if self.params[key].winfo_class() == "TEntry":
                self.params_last_content[key] = self.params[key].get()
            elif self.params[key].winfo_class() == "TCheckbutton" :
                self.params_last_content[key] = self.params[key].is_checked()

    def bookmark_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle bookmark scan Start/Stop button, changing label text as
        appropriate.
        """

        if self.scan_mode == None or self.scan_mode == "bookmarks" :
            action = self.book_scan_toggle.cget('text').lower()
            self.book_scan_toggle.config(text = next(icycle))
            self._scan("bookmarks", action)

    def bookmark_lockout(self, icycle=itertools.cycle(["L", "O"])):
        """Toggle lockout of selected bookmark.
        """

        if (self.selected_bookmark == None) :
            # will use this in future to support "current scan" lockout
            return
        else:
            values = list((self.tree.item(self.selected_bookmark, "values")))
            if values[BM.lockout] == 'L' :
                values[BM.lockout] = "O"
            else :
                values[BM.lockout] = "L"
            self.tree.item(self.selected_bookmark, values = values)
            self.bookmarks.bookmark_bg_tag(self.selected_bookmark, values[BM.lockout])


    def frequency_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle frequency scan Start/Stop button, changing label text as
        appropriate.
        """

        if self.params["cbb_scan_mode"].get() == "":
            tkMessageBox.showerror("Error",
                                   "You must select a mode for "
                                   "performing a frequency scan.")
            return

        if self.scan_mode == None or self.scan_mode == "frequency" :
            action = self.freq_scan_toggle.cget('text').lower()
            self.freq_scan_toggle.config(text = next(icycle))
            self._scan("frequency", action)

    def _process_port_entry(self, event_value, number, silent = False):
        """ Process event for port number entry

        :param event_value: new port number
        :type event_value: str
        :param silent: suppress messagebox
        :type silent: boolean
        :return:
        """

        try:
            is_valid_port(event_value)
        except ValueError:
            if not silent:
                tkMessageBox.showerror("Error",
                                       "Invalid input value in "
                                       "port. Must be integer and greater than "
                                       "1024")
            return
        if number == 1:
            self.rigctl.target["port"]=event_value

    def _process_hostname_entry(self, event_value, number, silent = False):
        """ Process event for hostname entry

        :param event_value: new hostname
        :type event_value: str
        :param silent: suppress messagebox
        :type silent: boolean
        :return:
        """

        try:
            is_valid_hostname(event_value)
        except Exception:
            if not silent:
                tkMessageBox.showerror("Error",
                                       "Invalid Hostname")
            return
        if number == 1:
            self.rigctl.target["hostname"]=event_value


    def process_entry(self, event, silent = False) :
        """Process a change in an entry widget. Check validity of
        numeric data. If empty field, offer the default or return to
        edit. If not valid, display a message and reset
        the widget to its previous state. Otherwise push the
        change onto the queue.

        :param event: event dict generated by widget handler
        :param silent: suppress messagebox
        :type silent: boolean
        :returns: None
        """

        event_name = str(event.widget).split('.')[-1]
        event_value = event.widget.get()
        ekey = str(event_name.split("_",1)[1])
        if (event_value == "") or event_value.isspace() :
            if not silent:
                answer = tkMessageBox.askyesno("Error",
                                               "{} must have a value "
                                               "entered. Use the "
                                               "default?".format(ekey))
            else:
                answer = True     #default answer for testing
            if answer :
                event_value = DEFAULT_CONFIG[ekey]
                event.widget.delete(0, 'end')
                event.widget.insert(0, event_value)
                self.params_last_content[event_name] = event_value
            else :
                if (self.params_last_content[event_name] != "") and \
                        (not(self.params_last_content[event_name].isspace())):
                    event.widget.delete(0, 'end')
                    event.widget.insert(0, self.params_last_content[event_name])
                else :
                    event.widget.focus_set()
                    return
        if event_name == "txt_hostname1":
            self._process_hostname_entry(event_value, 1)
            return
        if event_name == "txt_hostname2":
            self._process_hostname_entry(event_value, 2)
            return

        if event_name == "txt_port1":
            self._process_port_entry(event_value, 1)
            return
        if event_name == "txt_port2":
            self._process_port_entry(event_value, 2)
            return

        try :
            event_value_int = int(event.widget.get().replace(',',''))
        except ValueError:
            if not silent:
                tkMessageBox.showerror("Error",
                                   "Invalid input value in %s" % event_name)
            event.widget.focus_set()
            return
        self.params_last_content[event_name] = event_value
        if self.scan_thread != None :
            event_list = (event_name, event_value_int)
            self.scanq.send_event_update(event_list)

    def process_wait(self, *args):
        """ Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored
        :returns: None
        """
        event_list = ("ckb_wait", self.cb_wait.get())
        self._process_checkbutton(event_list)

    def process_record(self, *args) :
        """ Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_record", self.cb_record.get())
        self._process_checkbutton(event_list)

    def process_log(self, *args) :
        """ Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_log", self.cb_log.get())
        self._process_checkbutton(event_list)

    def process_auto_bookmark(self, *args) :
        """ Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_auto_bookmark", self.cb_auto_bookmark.get())
        self._process_checkbutton(event_list)

    def _process_checkbutton(self, event_list) :
        """Take the event_list generated by caller and push it on the queue.

        :param event_list: name of param to update, value of param
        :type event_list: list
        :returns: None
        """

        if self.scan_thread != None :
            self.scanq.send_event_update(event_list)
            self.params_last_content[event_list[0]] = event_list[1]

    def check_scanthread(self):
        """Check it the scan thread has sent us a termination signal.
        :returns: None
        """

        if self.scanq.check_end_of_scan():
            if self.scan_mode == 'frequency':
                self.frequency_toggle()
            else:
                self.bookmark_toggle()
        else:
            if self.scan_thread != None:
                self.after(UI_EVENT_TIMER_DELAY, self.check_scanthread)

    def _scan(self, mode, action, silent = False):
        """Wrapper around the scanning class instance. Creates the task
        object and issues the scan.

        :param mode: bookmark or frequency
        :type mode: string
        :param action: supported actions defined in UPPORTED_SCANNING_ACTIONS
        :type action: string
        :raises: NotImplementedError if action different than "start" is passed
        :returns: None
        """

        if action.lower() not in SUPPORTED_SCANNING_ACTIONS:
            logger.error("Provided action:{}".format(action))
            logger.error("Supported "
                         "actions:{}".format(SUPPORTED_SCANNING_ACTIONS))
            raise UnsupportedScanningConfigError

        if action.lower() == "stop" and self.scan_thread != None:
            # there is a scan ongoing and we want to terminate it
            self.scanning.terminate()
            self.scan_thread.join()
            self.scan_thread = None
            if mode.lower() == "frequency" :
                self._add_new_bookmarks(self.new_bookmark_list)
                self.new_bookmark_list = []
            self.scan_mode = None
            return

        if (action.lower() == "start" and self.scan_thread != None) :
            # we are already scanning, so another start is ignored
            return

        if (action.lower() == "stop" and self.scan_thread == None) :
            # we already stopped scanning, another stop is ignored
            return

        if (action.lower() == "start" and self.scan_thread == None) :
            # there is no ongoing scan task and we want to start one

            if len(self.tree.get_children()) == 0 and mode == "bookmarks":
                if not silent:
                    tkMessageBox.showerror("Error",
                                           "No bookmarks to scan.")
                self.bookmark_toggle()
            else:
                self.scan_mode = mode
                scanq = self.scanq
                bookmarks = self.tree
                pass_params = dict.copy(self.params)
                nbl = self.new_bookmark_list
                task = ScanningTask(scanq,
                                    mode,
                                    bookmarks,
                                    nbl,
                                    pass_params,
                                    self.rigctl,
                                    self.log_file)
                self.scanning = Scanning()
                self.scan_thread = threading.Thread(target = self.scanning.scan,
                                                    args = (task,))
                self.scan_thread.start()
                self.after(0, self.check_scanthread)

    def _new_activity_message(self, nbl):
        """Provides a little formatting from the new bookmark list.

        :param nbl: new bookmark list
        :type nbl: list
        :raises : none
        :returns message: message to be printed in an info messagebox.
        :type message: string
        """

        message = []
        for nb in nbl:
            message.append(nb[2])
        message = ", ".join(message)
        logger.warning(message)
        return message

    def _clear_form(self, source):
        """Clear the form.. nothing more.

        :param: none
        :raises: none
        :returns: none
        """

        if source not in (1,2):
            logger.error("The rig number {} is not supported".format(source))
            raise NotImplementedError

        frequency = ("txt_frequency{}".format(source))
        mode = ("cbb_mode{}".format(source))
        description = ("txt_description{}".format(source))

        self.params[frequency].delete(0, tk.END)
        self.params[description].delete(0, tk.END)
        self.params[mode].delete(0, tk.END)

    def _add_new_bookmarks(self, nbl):
        """Fill in the data, calls uses cb_add() and calls clear_form.

        :param nbl: list of new frequencies to bookmark
        :type nbl: list
        :raises: none
        :returns: none
        """
        self._clear_form(1)
        for nb in nbl:
            self.params["txt_description1"].insert(0,
                                                  "activity on {}".format(nb["time"]))
            self.params["txt_frequency1"].insert(0,
                                                frequency_pp(str(nb["freq"])))
            self.params["cbb_mode1"].insert(0,nb["mode"])
            # adding bookmark to the list
            self.cb_first_add(True)
            self._clear_form(1)

    def toggle_cb_top(self, *args):
        """Set window property to be always on top.

        :param: none
        :raises: none
        :returns: none
        """

        self.master.attributes("-topmost", self.ckb_top.val.get())

    def cb_second_get_frequency(self):
        """Wrapper around cb_set_frequency.

        """
        rig_target=build_rig_uri(2, self.params)
        self.cb_get_frequency(rig_target)

    def cb_first_get_frequency(self):
        """Wrapper around cb_set_frequency.

        """
        rig_target=build_rig_uri(1, self.params)
        self.cb_get_frequency(rig_target)

    def cb_get_frequency(self, rig_target, silent = False):
        """Get current rig frequency and mode.

        :param silent: suppress messagebox
        :type silent: boolean
        :raises: none
        :returns: none
        """

        # clear fields
        self._clear_form(rig_target["rig_number"])
        try:
            frequency = self.rigctl.get_frequency(rig_target)
            mode = self.rigctl.get_mode(rig_target)
            # update fields
            txt_frequency = "txt_frequency{}".format(rig_target["rig_number"])
            self.params[txt_frequency].insert(0,
                                                frequency_pp(frequency))
            cbb_mode = "cbb_mode{}".format(rig_target["rig_number"])
            self.params[cbb_mode].insert(0, mode)
        except Exception as err:
            if not silent:
                tkMessageBox.showerror("Error",
                                   "Could not connect to rig.\n%s" % err,
                                   parent=self)

    def cb_second_set_frequency(self):
        """Wrapper around cb_set_frequency.
        """

        rig_target = build_rig_uri(2, self.params)
        self.cb_set_frequency(rig_target, event = None)

    def cb_first_set_frequency(self):
        """Wrapper around cb_set_frequency.
        """

        rig_target = build_rig_uri(1, self.params)
        self.cb_set_frequency(rig_target, event = None)

    def cb_set_frequency(self, rig_target, event, silent = False):
        """Set the rig frequency and mode.

        :param event: not used?
        :type event:
        :param rig_target: rig we are referring to (hostname and port)
        :type rig_taret: dict
        :param silent: suppress messagebox
        :type silent: boolean
        :raises: none
        :returns: none
        """

        txt_frequency = "txt_frequency{}".format(rig_target["rig_number"])
        cbb_mode = "cbb_mode{}".format(rig_target["rig_number"])
        frequency = self.params[txt_frequency].get()
        mode = self.params[cbb_mode].get()

        try:
            self.rigctl.set_frequency(frequency.replace(',', ''), rig_target)
            self.rigctl.set_mode(str((mode)), rig_target)
        except Exception as err:
            if not silent and (frequency != "" or mode != ""):
                tkMessageBox.showerror("Error",
                                       "Could not set frequency.\n%s" % err,
                                       parent=self)
            if not silent and (frequency == "" or mode == ""):
                tkMessageBox.showerror("Error",
                                       "Please provide frequency and mode.",
                                       parent=self)

    def cb_second_fill_form(self):
        """Wrapper around cb_set_frequency.
        """

        self.cb_autofill_form(2, event = None)

    def cb_first_fill_form(self):
        """Wrapper around cb_set_frequency.
        """

        self.cb_autofill_form(1, event = None)

    def cb_autofill_form(self, rig_target, event):
        """Auto-fill bookmark fields with details
        of currently selected Treeview entry.

        :param event: not used?
        :type event:
        :raises: none
        :returns: none
        """

        self.selected_bookmark = self.tree.focus()
        values = self.tree.item(self.selected_bookmark).get('values')
        self._clear_form(rig_target)

        cbb_mode = "cbb_mode{}".format(rig_target)
        txt_frequency = "txt_frequency{}".format(rig_target)
        txt_description = "txt_description{}".format(rig_target)

        self.params[cbb_mode].insert(0, values[1])
        self.params[txt_frequency].insert(0, values[0])
        self.params[txt_description].insert(0, values[2])

    def build_control_source(self, number, silent = False):
        if number not in (1,2):
            logger.error("The rig number {} is not supported".format(number))
            raise NotImplementedError

        control_source= {}
        freq = "txt_frequency{}".format(number)
        mode = "cbb_mode{}".format(number)
        description = "txt_description{}".format(number)
        control_source["frequency"] = frequency_pp_parse(self.params[freq].get())
        try:
            int(control_source["frequency"])
        except (ValueError, TypeError):
            if not (silent) :
                tkMessageBox.showerror("Error",
                                       "Invalid value in Frequency field."
                                       "Note: '.' isn't allowed.")
                self.params[freq].focus_set()
            return
        control_source["mode"] = self.params[mode].get()
        control_source["description"] = self.params[description].get()
        return control_source

    def cb_second_add(self, silent = False):
        """Wrapper around cb_add.
        """

        control_source = self.build_control_source(2)
        self.cb_add(control_source, silent)

    def cb_first_add(self, silent = False):
        """Wrapper around cb_add.
        """

        control_source = self.build_control_source(1)
        self.cb_add(control_source, silent)

    def cb_add(self, control_source, silent = False):
        """Add frequency to tree and saves the bookmarks.

        :param: none
        :raises: none
        :returns: none
        """

        frequency = control_source["frequency"]
        mode = control_source["mode"]
        description = control_source["description"]
        lockout = "O"
        # find where to insert (insertion sort)
        idx = tk.END
        for item in self.tree.get_children():
            freq = str(self.tree.item(item).get('values')[BM.freq])
            uni_curr_freq = frequency_pp_parse(freq)
            curr_freq = uni_curr_freq.encode("UTF-8")
            curr_mode = self.tree.item(item).get('values')[BM.mode]
            if frequency < curr_freq:
                idx = self.tree.index(item)
                break
            elif (frequency == curr_freq and
                  mode == curr_mode) :
                if not (silent) :
                    tkMessageBox.showerror("Error", "A bookmark with the "
                                           "same frequency and mode "
                                           "already exists.", parent=self)
                return
        # insert
        item = self.tree.insert('',
                                idx,
                                values=[frequency_pp(frequency),
                                        mode,
                                        description,
                                        lockout])

        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        # save
        self.bookmarks.save(self.bookmarks_file)

    def cb_delete2(self):
        """wrapper around cb_delete
        """

        self.cb_delete(2)

    def cb_delete1(self):
        """wrapper around cb_delete
        """

        self.cb_delete(1)


    def cb_delete(self, source):
        """Delete frequency from tree.

        :param: none
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        if item != '':
            self.tree.delete(item)
            # save
        self.bookmarks.save(self.bookmarks_file)
        self._clear_form(source)

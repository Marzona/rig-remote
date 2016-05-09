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
2016/03/15 - TAS - Added more scanning option validation. Changed scan initialization to pass
                   most params in a dict.
2016/03/19 - TAS - Added validation of the config file when it is applied.
2016/03/20 - TAS - Added some validation of user frequency input, and of the bookmark file when it
                   is loaded.
2016/03/21 - TAS - Added new checkbutton config data to config file handling methods.
2016/04/12 - TAS - Added back auto-bookmarking option on frequency scan. Bookmarks are processed once the
                   scan thread has completed. Only one bookmark per frequency. (If logging enabled, all
                   occurences are logged.)
2016/04/24 - TAS - Changed communications between main and scan threads to use STMessenger class, to
                   enable thread-safe notification of scan thread termination (Issue #30).
2016/05/02 - TAS - Refactor is_valid_hostname(), and the methods that call it, to properly handle bad input.
2016/05/04 - TAS - Cut some bookmark functionality out to start moving it to s separate class. ui.py now
                   broken.
2016/05/07 - TAS - Integrate BookmarkSet into ui. Rename all callbacks to uniform pattern.
2016/05/08 - TAS - Merge from devel: handle config, initial bookmarks, and log file names correctly.
"""

# import modules


import logging
from rig_remote.bookmarks import BookmarkSet
from rig_remote.constants import SUPPORTED_SCANNING_ACTIONS
from rig_remote.constants import CBB_MODES
from rig_remote.constants import BM
from rig_remote.constants import DEFAULT_CONFIG
from rig_remote.constants import UI_EVENT_TIMER_DELAY
from rig_remote.exceptions import UnsupportedScanningConfigError, DuplicateBookmark, InvalidBookmark
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import ScanningTask
from rig_remote.scanning import Scanning
from rig_remote.stmessenger import STMessenger
from rig_remote.utility import frequency_pp, frequency_pp_parse, is_valid_port, is_valid_hostname
import Tkinter as tk
import ttk
import os
from Tkinter import LabelFrame
import tkMessageBox
import threading
import itertools


# logging configuration
logger = logging.getLogger(__name__)

# class definition

class RCCheckbutton(ttk.Checkbutton) :
    """
    RCCheckbutton is derived from ttk.Checkbutton, and adds an 
    "is_checked" method to simplify checking instance's state, and
    new methods to return string state values for config file.
    """
    def __init__(self,*args,**kwargs) :
        self.var = kwargs.get('variable', tk.BooleanVar())
        kwargs['variable'] = self.var
        ttk.Checkbutton.__init__(self, *args, **kwargs)

    def is_checked(self) :
        return self.var.get()

    def get_str_val(self) :
        if self.is_checked() :
            return ("true")
        else :
            return ("false")

    def set_str_val(self, value) :
        if value.lower() in ("true", "t") :
            self.var.set(True)
        else :
            self.var.set(False)

class ToolTip:
    def __init__(self, master, text='Your text here', delay=1500, **opts):
        self.master = master
        self._opts = {'anchor':'center',
                      'bd':1,
                      'bg':'lightyellow',
                      'delay':delay,
                      'fg':'black',
                      'follow_mouse':0,
                      'font':None,
                      'justify':'left',
                      'padx':4,
                      'pady':2,
                      'relief':'solid',
                      'state':'normal',
                      'text':text,
                      'textvariable':None,
                      'width':0,
                      'wraplength':150}
        self.configure(**opts)
        self._tipwindow = None
        self._id = None
        self._id1 = self.master.bind("<Enter>", self.enter, '+')
        self._id2 = self.master.bind("<Leave>", self.leave, '+')
        self._id3 = self.master.bind("<ButtonPress>", self.leave, '+')
        self._follow_mouse = 0
        if self._opts['follow_mouse']:
            self._id4 = self.master.bind("<Motion>", self.motion, '+')
            self._follow_mouse = 1

    def configure(self, **opts):
        for key in opts:
            if self._opts.has_key(key):
                self._opts[key] = opts[key]
            else:
                KeyError = 'KeyError: Unknown option: "%s"' %key
                raise KeyError
    """
    these methods handle the callbacks on "<Enter>", "<Leave>" and "<Motion>"
    events on the parent widget; override them if you want to change the 
    widget's behavior
    """
    def enter(self, event=None):
        self._schedule()

    def leave(self, event=None):
        self._unschedule()
        self._hide()

    def motion(self, event=None):
        if self._tipwindow and self._follow_mouse:
            x, y = self.coords()
            self._tipwindow.wm_geometry("+%d+%d" % (x, y))

    """
    ------the methods that do the work:
    """

    def _schedule(self):
        self._unschedule()
        if self._opts['state'] == 'disabled':
            return
        self._id = self.master.after(self._opts['delay'], self._show)

    def _unschedule(self):
        id = self._id
        self._id = None
        if id:
            self.master.after_cancel(id)

    def _show(self):
        if self._opts['state'] == 'disabled':
            self._unschedule()
            return
        if not self._tipwindow:
            self._tipwindow = tw = tk.Toplevel(self.master)
            # hide the window until we know the geometry
            tw.withdraw()
            tw.wm_overrideredirect(1)

            if tw.tk.call("tk", "windowingsystem") == 'aqua':
                tw.tk.call("::tk::unsupported::MacWindowStyle",
                           "style",
                           tw._w,
                           "help",
                           "none")

            self.create_contents()
            tw.update_idletasks()
            x, y = self.coords()
            tw.wm_geometry("+%d+%d" % (x, y))
            tw.deiconify()

    def _hide(self):
        tw = self._tipwindow
        self._tipwindow = None
        if tw:
            tw.destroy()
                
    ##----these methods might be overridden in derived classes:

    def coords(self):
        # The tip window must be completely outside the master widget;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        # or we take care that the mouse pointer is always outside the tipwindow :-)
        tw = self._tipwindow
        twx, twy = tw.winfo_reqwidth(), tw.winfo_reqheight()
        w, h = tw.winfo_screenwidth(), tw.winfo_screenheight()
        # calculate the y coordinate:
        if self._follow_mouse:
            y = tw.winfo_pointery() + 20
            # make sure the tipwindow is never outside the screen:
            if y + twy > h:
                y = y - twy - 30
        else:
            y = self.master.winfo_rooty() + self.master.winfo_height() + 3
            if y + twy > h:
                y = self.master.winfo_rooty() - twy - 3
        # we can use the same x coord in both cases:
        x = tw.winfo_pointerx() - twx / 2
        if x < 0:
            x = 0
        elif x + twx > w:
            x = w - twx
        return x, y

    def create_contents(self):
        opts = self._opts.copy()
        for opt in ('delay', 'follow_mouse', 'state'):
            del opts[opt]
        label = tk.Label(self._tipwindow, **opts)
        label.pack()

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
        self.bookmarks = BookmarkSet(self.bookmarks_file)
        self.bookmarks.load_from_file()
        self.build(ac)
        self.params["cbb_mode"].current(0)
        self.focus_force()
        self.update()
        # bookmarks loading on start
        self.bookmarks.load_bookmark_tree(self)
        self.scan_thread = None
        self.scan_mode = None
        self.scanning = None
        self.selected_bookmark = None
        self.scanq = STMessenger()
        self.new_bookmark_list = []
        self.bind_all("<1>", lambda event:self.focus_set(event))

    def build(self, ac):
        """Build and initialize the GUI widgets.
        :param: none
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
                         text="Bookmark list, double click to recall.")

        self.tree.heading('frequency',
                          text='Frequency',
                          anchor=tk.CENTER)
        self.tree.column('frequency',
                         #minwidth=100,
                         width=100,
                         stretch=True,
                         anchor=tk.CENTER)
        self.tree.heading('mode',
                          text='Mode',
                          anchor=tk.CENTER)
        self.tree.column('mode',
                         #minwidth=80,
                         width=70,
                         stretch=True,
                         anchor=tk.CENTER)
        self.tree.heading('description',
                          text='Description',
                          )
        self.tree.column('description',
                         stretch=True,
                         #width=70
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
        self.tree.bind('<<TreeviewSelect>>',
                       self._cb_autofill_form)
        self.tree.bind('<Double-Button-1>',
                       self._cb_set_frequency_button)

        # vertical separator between bookmarks and comands
        ttk.Frame(self).grid(row=0,
                             column=2,
                             rowspan=5,
                             padx=5)
        # right-side container
        self.rig_config_menu = LabelFrame(self,
                                          text="Rig configuration")
        self.rig_config_menu.grid(row=0,
                                  column=3,
                                  sticky=tk.NSEW)

        ttk.Label(self.rig_config_menu,
                  text="Hostname:").grid(row=1,
                                         column=2,
                                         sticky=tk.W)
        self.params["txt_hostname"] = ttk.Entry(self.rig_config_menu,
                                                name="txt_hostname")
        self.params["txt_hostname"].grid(row=1,
                                         column=3,
                                         columnspan=2,
                                         padx=2,
                                         pady=2,
                                        sticky=tk.EW)
        t_txt_hostname = ToolTip(self.params["txt_hostname"],
                                 follow_mouse=1,
                                 text="Hostname to connect.")
        self.params["txt_hostname"].bind("<Return>", self._cb_general_entry)
        self.params["txt_hostname"].bind("<FocusOut>", self._cb_general_entry)

        ttk.Label(self.rig_config_menu,
                  text="Port:").grid(row=2,
                                     column=2,
                                     sticky=tk.W)
        self.params["txt_port"] = ttk.Entry(self.rig_config_menu,
                                            name="txt_port")
        self.params["txt_port"].grid(row=2,
                                     column=3,
                                     padx=2,
                                     pady=2,
                                   sticky=tk.EW)
        t_txt_port = ToolTip(self.params["txt_port"],
                             follow_mouse=1,
                             text="Port to connect.")
        self.params["txt_port"].bind("<Return>", self._cb_general_entry)
        self.params["txt_port"].bind("<FocusOut>", self._cb_general_entry)

        # horizontal separator
        ttk.Frame(self.rig_config_menu).grid(row=3,
                                             column=0,
                                             columnspan=3,
                                             pady=5)

        self.rig_control_menu = LabelFrame(self,
                                           text="Rig Control")
        self.rig_control_menu.grid(row=1,
                                   column=3,
                                   stick=tk.NSEW)

        ttk.Label(self.rig_control_menu,
                  text="Frequency:").grid(row=5,
                                          column=0,
                                          sticky=tk.W)
        self.params["txt_frequency"] = ttk.Entry(self.rig_control_menu,
                                                 name="txt_frequency")
        self.params["txt_frequency"].grid(row=5,
                                          column=1,
                                          columnspan=3,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_frequency = ToolTip(self.params["txt_frequency"],
                                  follow_mouse=1,
                                  text="Frequency to tune.")
        ttk.Label(self.rig_control_menu,
                  text="Hz").grid(row=5,
                                   column=3,
                                   sticky=tk.EW)

        ttk.Label(self.rig_control_menu,
                  text="Mode:").grid(row=6,
                                     column=0,
                                     sticky=tk.W)
        self.params["cbb_mode"] = ttk.Combobox(self.rig_control_menu, 
                                               name="cbb_mode",width=15)
        self.params["cbb_mode"].grid(row=6,
                                     column=1,
                                     columnspan=3,
                                     padx=2,
                                     pady=2,
                                     sticky=tk.EW)
        t_cbb_mode = ToolTip(self.params["cbb_mode"],
                              follow_mouse=1,
                              text="Mode to use for tuning the frequency.")
        self.params["cbb_mode"]['values'] = CBB_MODES

        ttk.Label(self.rig_control_menu,
                  text="Description:").grid(row=7,
                                            column=0,
                                            sticky=tk.EW)
        self.params["txt_description"] = ttk.Entry(self.rig_control_menu,
                                                   name="txt_description")
        self.params["txt_description"].grid(row=7,
                                            column=1,
                                            columnspan=3,
                                            padx=2,
                                            pady=2,
                                            sticky=tk.EW)
        t_txt_description = ToolTip(self.params["txt_description"],
                                    follow_mouse=1,
                                    text="Description of the bookmark.")

        self.btn_add = ttk.Button(self.rig_control_menu,
                                  text="Add",
                                  width=7,
                                  command=self._cb_bookmark_add_button)
        t_btn_add = ToolTip(self.btn_add,
                            follow_mouse=1,
                            text="Bookmark this frequency.")
        self.btn_add.grid(row=8,
                          column=1,
                          padx=2,
                          pady=2)

        self.btn_delete = ttk.Button(self.rig_control_menu,
                                     text="Delete",
                                     width=7,
                                     command=self._cb_bookmark_delete_button)
        t_btn_delete = ToolTip(self.btn_delete,
                               follow_mouse=1,
                               text="Remove this frequency from bookmarks.")
        self.btn_delete.grid(row=8,
                             column=2,
                             padx=2,
                             pady=2)

        self.btn_load = ttk.Button(self.rig_control_menu,
                                   text="Get",
                                   width=7,
                                   command=self._cb_get_rig_data_button)
        t_btn_load = ToolTip(self.btn_load,
                             follow_mouse=1,
                             text="Get the frequency and mode from the rig.")

        self.btn_load.grid(row=8,
                           column=3,
                           padx=2,
                           pady=2)

        # horizontal separator
        ttk.Frame(self.rig_control_menu).grid(row=9,
                                              column=0,
                                              columnspan=3,
                                              pady=5)


        self.scanning_conf_menu = LabelFrame(self, text="Scanning options")
        self.scanning_conf_menu.grid(row=2,
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
        self.params["txt_sgn_level"].bind("<Return>", self._cb_general_entry)
        self.params["txt_sgn_level"].bind("<FocusOut>", self._cb_general_entry)

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
        self.params["txt_delay"].bind("<Return>", self._cb_general_entry)
        self.params["txt_delay"].bind("<FocusOut>", self._cb_general_entry)

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
        self.params["txt_passes"].bind("<Return>", self._cb_general_entry)
        self.params["txt_passes"].bind("<FocusOut>", self._cb_general_entry)

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
                             text="Waits after having found an active"\
                                  " frequency.")
        self.params["ckb_wait"].val = self.cb_wait
        self.cb_wait.trace("w", self._cb_wait_checkbutton)

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
                               text="Enable the recording of signal to"\
                                    " a file.")
        self.params["ckb_record"].val = self.cb_record
        self.cb_record.trace("w", self._cb_record_checkbutton)

        self.cb_log = tk.BooleanVar()
        self.params["ckb_log"] = RCCheckbutton(self.scanning_conf_menu,
                                               name="ckd_log",
                                               text="Log",
                                               onvalue=True,
                                               offvalue=False,
                                               variable=self.cb_log)
        t_ckb_log = ToolTip(self.params["ckb_log"],
                            follow_mouse=1,
                            text="Logs the activities to a file.")
        self.params["ckb_log"].grid(row=15,
                                    column=2,
                                    columnspan=1,
                                    sticky=tk.E)
        self.params["ckb_log"].val = self.cb_log
        self.cb_log.trace("w", self._cb_log_checkbutton)

        self.freq_scanning_menu = LabelFrame(self, text="Frequency scanning")
        self.freq_scanning_menu.grid(row=3,
                                     column=3,
                                     #rowspan=3,
                                     stick=tk.NSEW)

        self.freq_scan_toggle = ttk.Button(self.freq_scanning_menu,
                                           text="Start",
                                           command=self._cb_frequency_scan_button_toggle,
                                           )
        t_freq_scan_toggle = ToolTip(self.freq_scan_toggle,
                                     follow_mouse=1,
                                     text="Starts a frequency scan.")
        self.freq_scan_toggle.grid(row=16,
                                   column=2,
                                   columnspan=1,
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
                                                 width=10)
        self.params["txt_range_min"].grid(row=12,
                                          column=1,
                                          columnspan=1,
                                          padx=2,
                                          pady=2,
                                          sticky=tk.W)
        t_txt_range_min = ToolTip(self.params["txt_range_min"],
                                  follow_mouse=1,
                                  text="Lower bound of the frequency"\
                                       " band to scan.")
        self.params["txt_range_min"].bind("<Return>", self._cb_general_entry)
        self.params["txt_range_min"].bind("<FocusOut>", self._cb_general_entry)

        self.params["txt_range_max"] = ttk.Entry(self.freq_scanning_menu,
                                                 name="txt_range_max",
                                                 width=10)
        self.params["txt_range_max"].grid(row=12,
                                          column=2,
                                          columnspan=1,
                                          padx=0,
                                          pady=0,
                                          sticky=tk.W)
        t_txt_range_max = ToolTip(self.params["txt_range_max"],
                                  follow_mouse=1,
                                  text="Upper bound of the frequency"\
                                       " band to scan.")
        self.params["txt_range_max"].bind("<Return>", self._cb_general_entry)
        self.params["txt_range_max"].bind("<FocusOut>", self._cb_general_entry)

        ttk.Label(self.freq_scanning_menu,
                  text="Interval:").grid(row=13,
                                         column=0,
                                         sticky=tk.W)
        self.params["txt_interval"] = ttk.Entry(self.freq_scanning_menu,
                                                name="txt_interval",
                                                width=10)
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
        self.params["txt_interval"].bind("<Return>", self._cb_general_entry)
        self.params["txt_interval"].bind("<FocusOut>", self._cb_general_entry)

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
                                      text="Bookmark any active frequency"\
                                           " found.")
        self.params["ckb_auto_bookmark"].grid(row=16,
                                              column=0,
                                              columnspan=2)
        self.params["ckb_auto_bookmark"].val = self.cb_auto_bookmark
        self.cb_auto_bookmark.trace("w", self._cb_auto_bookmark_checkbutton)

        ttk.Frame(self.freq_scanning_menu).grid(row=17,
                                                column=0,
                                                columnspan=3,
                                                pady=5)

        self.book_scanning_menu = LabelFrame(self, text="Bookmark scanning")
        self.book_scanning_menu.grid(row=4,
                                     column=3,
                                     stick=tk.NSEW)

        #horrible horizontal placeholder
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=18,
                                column=0,
                                sticky=tk.NSEW)
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=18,
                                column=1,
                                sticky=tk.NSEW)

        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=18,
                                column=2,
                                sticky=tk.NSEW)

        self.book_scan_toggle = ttk.Button(self.book_scanning_menu,
                                           text="Start",
                                           command=self._cb_bookmark_scan_button_toggle,
                                           )
        t_book_scan_toggle = ToolTip(self.book_scan_toggle,
                                     follow_mouse=1,
                                     text="Start a bookmark scan.")
        self.book_scan_toggle.grid(row=18,
                                   column=2,
                                   columnspan=1,
                                   padx=2,
                                   sticky=tk.W)

        self.book_lockout = ttk.Button(self.book_scanning_menu,
                                       text="Lock",
                                       command=self._cb_bookmark_lock_button,
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

        self.control_menu.grid(row=5,
                               column=3,
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
        self.cb_top.trace("w", self._toggle_cb_top)

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

        self.btn_quit = ttk.Button(self.control_menu,
                                   text="Quit",
                                   command=lambda: self.shutdown(ac))
        t_btn_quit = ToolTip(self.btn_quit,
                             follow_mouse=1,
                             text="Exit rig-remote.")
        self.btn_quit.grid(row=21,
                           column=3,
                           columnspan=1,
                           sticky=tk.SE)

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
        ac.read_conf()
        try:
            is_valid_hostname(ac.config["hostname"])
        except Exception:
            self.params["txt_hostname"].insert(0, DEFAULT_CONFIG["hostname"])
            if not silent:
                tkMessageBox.showerror("Config File Error", "One (or more) " \
                                                        "of the values in the config file was " \
                                                        "invalid, and the default was used " \
                                                        "instead.", parent=self)
        else:
            self.params["txt_hostname"].insert(0, ac.config["hostname"])
        # Test positive integer values
        for key in ("port",
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
                tkMessageBox.showerror("Config File Error", "One (or more) "\
                                   "of the values in the config file was "\
                                   "invalid, and the default was used "\
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
        self.rigctl = RigCtl(self.params["txt_hostname"].get(),
                             self.params["txt_port"].get())
        for key in ('alternate_config_file', 'alternate_bookmark_file', 'alternate_log_file'):
            self.alt_files[key] = key in ac.config
            ac.config.pop(key, None)
        # Here we create a copy of the params dict to use when
        # checking validity of new input
        for key in self.params :
            if self.params[key].winfo_class() == "TEntry":
                self.params_last_content[key] = self.params[key].get()
            elif self.params[key].winfo_class() == "TCheckbutton" :
                self.params_last_content[key] = self.params[key].is_checked()

    def _store_conf(self, ac):
        """populates the ac object reading the info from the UI
        :param ac: object used to hold the app configuration.
        :type ac: AppConfig() object
        :returns ac: ac obj updated.
        """
        ac.config["hostname"] = self.params["txt_hostname"].get()
        ac.config["port"] = self.params["txt_port"].get()
        ac.config["interval"] = self.params["txt_interval"].get()
        ac.config["delay"] = self.params["txt_delay"].get()
        ac.config["passes"] = self.params["txt_passes"].get()
        ac.config["sgn_level"] = self.params["txt_sgn_level"].get()
        ac.config["range_min"] = self.params["txt_range_min"].get()
        ac.config["range_max"] = self.params["txt_range_max"].get()
        ac.config["wait"] = self.params["ckb_wait"].get_str_val()
        ac.config["record"] = self.params["ckb_record"].get_str_val()
        ac.config["log"] = self.params["ckb_log"].get_str_val()
        ac.config["always_on_top"] = self.ckb_top.get_str_val()
        ac.config["save_exit"] = self.ckb_save_exit.get_str_val()
        ac.config["auto_bookmark"] = \
                                self.params["ckb_auto_bookmark"].get_str_val()
        ac.config["bookmark_filename"] = self.bookmarks_file
        ac.config["log_filename"] = self.log_file
        return ac

    def shutdown(self,ac, silent = False):
        """Here we quit. Before exiting, if save_exit checkbox is checked
        we save the configuration of the app and the bookmarks.
        :param ac: object that represent the UI configuration
        :type ac:AppConfig instance
        :returns: none
        """

        if self.cb_save_exit.get():
            if ((not self.alt_files['alternate_bookmark_file']) and
                os.path.basename(self.bookmarks_file) == 'rig-bookmarks.csv'):
                old_bookmark_path = self.bookmarks_file
                self.bookmarks_file = os.path.join(os.path.expanduser('~'),
                                            '.rig-remote/rig-remote-bookmarks.csv')
                self.bookmark("save", ",")
                try:
                    os.remove(old_bookmark_path)
                except OSError:
                    logger.info("Failed to remove old bookmark file: %s", old_bookmark_path)
            ac = self._store_conf(ac)
            if ((not self.alt_files['alternate_config_file']) and
                os.path.join(os.path.split(os.path.dirname(ac.config_file))[1],
                os.path.basename(ac.config_file)) == ".rig_remote/rig_remote.conf"):
                ac.old_path = True
            ac.write_conf()
        self.master.destroy()

    def _cb_bookmark_scan_button_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle bookmark scan Start/Stop button, changing label text as
           appropriate.
        """

        if self.scan_mode == None or self.scan_mode == "bookmarks" :
            action = self.book_scan_toggle.cget('text').lower()
            self.book_scan_toggle.config(text = next(icycle))
            self._scan("bookmarks", action)

    def bookmark_bg_tag(self, item, value) :
        """Set item background color based on lock status
        """

        if value == "L" :
            self.tree.tag_configure('locked', background = 'red')
            self.tree.item(item, tags = "locked")
        else :
            self.tree.tag_configure('unlocked', background = 'white')
            self.tree.item(item, tags = "unlocked")

    def _cb_bookmark_lock_button(self, icycle=itertools.cycle(["L", "O"])):
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
            self.bookmark_bg_tag(self.selected_bookmark, values[BM.lockout])


    def _cb_frequency_scan_button_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle frequency scan Start/Stop button, changing label text as
           appropriate.
        """

        if self.scan_mode == None or self.scan_mode == "frequency" : 
            action = self.freq_scan_toggle.cget('text').lower()
            self.freq_scan_toggle.config(text = next(icycle))
            self._scan("frequency", action)

    def _cb_port_entry(self, event_value, silent = False):
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
                                   "Invalid input value in "\
                                   "port. Must be integer and greater than "\
                                   "1024")
            return
        self.rigctl.port=event_value

    def _cb_hostname_entry(self, event_value, silent = False):
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
        self.rigctl.hostname=event_value


    def _cb_general_entry(self, event, silent = False) :
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
                answer = tkMessageBox.askyesno("Error", "{} must have a value "\
                                           "entered. Use the "\
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
        if event_name == "txt_hostname":
            self._cb_hostname_entry(event_value)
            return
        if event_name == "txt_port":
            self._cb_port_entry(event_value)
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

    def _cb_wait_checkbutton(self, *args):
        """ Methods to handle checkbutton updates

        :param *args: ignored
        :returns: None
        """
        event_list = ("ckb_wait", self.cb_wait.get())
        self._process_checkbutton_cb(event_list)

    def _cb_record_checkbutton(self, *args) :
        """ Methods to handle checkbutton updates

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_record", self.cb_record.get())
        self._process_checkbutton_cb(event_list)

    def _cb_log_checkbutton(self, *args) :
        """ Methods to handle checkbutton updates

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_log", self.cb_log.get())
        self._process_checkbutton_cb(event_list)

    def _cb_auto_bookmark_checkbutton(self, *args) :
        """ Methods to handle checkbutton updates

        :param *args: ignored
        :returns: None
        """

        event_list = ("ckb_auto_bookmark", self.cb_auto_bookmark.get())
        self._process_checkbutton_cb(event_list)

    def _process_checkbutton_cb(self, event_list) :
        """Take the event_list generated by caller and push it on the queue.

        :param event_list: name of param to update, value of param
        :type event_list: list
        :returns: None
        """
        if self.scan_thread != None :
            self.scanq.send_event_update(event_list)
            self.params_last_content[event_list[0]] = event_list[1]

    def _cb_bookmark_add_button(self, silent=False):
        """Callback for UI bookmark add button. Appends the new bookmark
           to the bookmark set and inserts it in the UI tree.

        :param silent: if True suppress messageboxes
        :type silent: boolean
        :raises: none
        :returns: none
        """

        # get values
        frequency = frequency_pp_parse(self.params['txt_frequency'].get())
        mode = self.params['cbb_mode'].get()
        description = self.params['txt_description'].get()
        lockout = 'O'
        entry = [frequency, mode, description, lockout]
        try:
            self.bookmarks.append('test', frequency, mode, description, lockout)
        except InvalidBookmark:
            if not (silent):
                self.bookmarks.delete('test')
                tkMessageBox.showerror("Error",
                                       "Invalid value in Frequency field.")
                self.params["txt_frequency"].focus_set()
            return
        try:
            item = self.bookmarks.insert_bookmark_in_tree(entry)
        except DuplicateBookmark:
            if not (silent):
                tkMessageBox.showerror("Error", "A bookmark with the " \
                                                "same frequency and mode " \
                                                "already exists.", parent=self)
            return
        self.bookmarks.update_id_key('test', item)
        self.bookmarks.save_to_file()
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)

    def _check_scanthread(self):
        """Check it the scan thread has sent us a termination signal.
        :returns: None
        """
        if self.scanq.check_end_of_scan():
            if self.scan_mode == 'frequency':
                self._cb_frequency_scan_button_toggle()
            else:
                self._cb_bookmark_scan_button_toggle()
        else:
            if self.scan_thread != None:
                self.after(UI_EVENT_TIMER_DELAY, self._check_scanthread)

    def _scan(self, mode, action):
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
            logger.error("Supported "\
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
                self._cb_bookmark_scan_button_toggle()
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
                self.after(0, self._check_scanthread)

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

    def _clear_bookmark_form(self):
        """Clear the form.. nothing more.

        :param: none
        :raises: none
        :returns: none
        """

        self.params["txt_frequency"].delete(0, tk.END)
        self.params["txt_description"].delete(0, tk.END)
        self.params["cbb_mode"].delete(0, tk.END)

    def _add_new_bookmarks(self, nbl):
        """Fill in the data, calls uses process_ui_add() and calls clear_form.

        :param nbl: list of new frequencies to bookmark
        :type nbl: list
        :raises: none
        :returns: none
        """

        self._clear_bookmark_form()
        for nb in nbl:
            self.params["txt_description"].insert(0,
                                                  "activity on {}".format(nb["time"]))
            self.params["txt_frequency"].insert(0,
                                                frequency_pp(str(nb["freq"])))
            self.params["cbb_mode"].insert(0,nb["mode"])
            # adding bookmark to the list
            self._cb_bookmark_add_button(True)
            self._clear_bookmark_form()

    def _toggle_cb_top(self, *args):
        """Set window property to be always on top.

        :param: none
        :raises: none
        :returns: none
        """

        self.master.attributes("-topmost", self.ckb_top.val.get())

    def _cb_get_rig_data_button(self, silent = False):
        """Get current rig frequency and mode.

        :param silent: suppress messagebox
        :type silent: boolean
        :raises: none
        :returns: none
        """

        # clear fields
        self._clear_bookmark_form()
        try:
            frequency = self.rigctl.get_frequency()
            mode = self.rigctl.get_mode()
            # update fields
            self.params["txt_frequency"].insert(0,
                                                frequency_pp(frequency))
            self.params["cbb_mode"].insert(0, mode)
        except Exception as err:
            if not silent:
                tkMessageBox.showerror("Error",
                                   "Could not connect to rig.\n%s" % err,
                                   parent=self)

    def _cb_set_frequency_button(self, event, silent = False):
        """Set the rig frequency and mode.

        :param event: not used?
        :type event:
        :param silent: suppress messagebox
        :type silent: boolean
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        values = self.tree.item(item).get('values')
        try:
            self.rigctl.set_frequency(values[0].replace(',', ''))
            self.rigctl.set_mode((values[1]))
        except Exception as err:
            if not silent:
                tkMessageBox.showerror("Error",
                                   "Could not set frequency.\n%s" % err,
                                   parent=self)

    def _cb_autofill_form(self, event):
        """Auto-fill bookmark fields with details
        of currently selected Treeview entry.

        :param event: not used?
        :type event:
        :raises: none
        :returns: none
        """

        self.selected_bookmark = self.tree.focus()
        values = self.tree.item(self.selected_bookmark).get('values')
        self._clear_bookmark_form()
        self.params["cbb_mode"].insert(0, values[1])
        self.params["txt_frequency"].insert(0, values[0])
        self.params["txt_description"].insert(0, values[2])

    def _cb_bookmark_delete_button(self):
        """Delete frequency from tree.

        :param: none
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        if item != '':
            self.tree.delete(item)
            self.bookmarks.delete(item)
        self.bookmarks.save_to_file()
        self._clear_bookmark_form()

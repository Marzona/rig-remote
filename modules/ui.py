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

"""

# import modules

import logging
import datetime
from modules.constants import ALLOWED_BOOKMARK_TASKS
from modules.constants import SUPPORTED_SCANNING_ACTIONS
from modules.constants import CBB_MODES
from modules.constants import BOOKMARKS_FILE
from modules.constants import UNKNOWN_MODE
from modules.constants import LEN_BM
from modules.constants import BM
from modules.app_config import AppConfig
from modules.exceptions import UnsupportedScanningConfigError
from modules.exceptions import InvalidPathError
from modules.disk_io import IO
from modules.rigctl import RigCtl
from modules.scanning import ScanningTask
from modules.scanning import Scanning
import Tkinter as tk
import ttk
from Tkinter import Text
from Tkinter import LabelFrame
from Tkinter import Label
import tkMessageBox
import threading
import itertools

# logging configuration
logger = logging.getLogger(__name__)

# class definition

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

class RigRemote(ttk.Frame):  #pragma: no cover
    """Remote application that interacts with the rig using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.
    :raises: none
    :returns: none
    """

    def __init__(self, root, ac):  #pragma: no cover
        ttk.Frame.__init__(self, root)
        self.bookmarks_file = BOOKMARKS_FILE
        self.log_file = None
        self.build(ac)
        self.cbb_mode.current(0)
        # bookmarks loading on start
        self.bookmark("load", ",")
        self.scan_thread = None
        self.scan_mode = None
        self.scanning = None
        self.selected_bookmark = None


    def build(self, ac):  #pragma: no cover
        """Build and initialize the GUI widgets.
        :param: none
        :raises: none
        :returns: none
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
                            #xscroll=xsb.set
                            )
        self.tree.grid(row=0,
                       column=0,
                       rowspan=5,
                       sticky=tk.NSEW
                       )
        self.tree.bind('<<TreeviewSelect>>',
                       self.cb_autofill_form)
        self.tree.bind('<Double-Button-1>',
                       self.cb_set_frequency)

        # vertical separator between bookmarks and comands
        ttk.Frame(self).grid(row=0,
                             column=2,
                             rowspan=5,
                             padx=5)
#        # right-side container
        self.rig_config_menu = LabelFrame(self,
                               text="Rig configuration")
        self.rig_config_menu.grid(row=0,
                                  column=3,
                                  sticky=tk.NSEW)
        ttk.Label(self.rig_config_menu,
                  text="Hostname:").grid(row=1,
                                         column=2,
                                         sticky=tk.W)
        self.txt_hostname = ttk.Entry(self.rig_config_menu)
        self.txt_hostname.grid(row=1,
                               column=3,
                               columnspan=2,
                               padx=2,
                               pady=2,
                               sticky=tk.EW)
        t_txt_hostname = ToolTip(self.txt_hostname,
                                 follow_mouse=1,
                                 text="Hostname to connect.")

        ttk.Label(self.rig_config_menu,
                  text="Port:").grid(row=2,
                                     column=2,
                                     sticky=tk.W)
        self.txt_port = ttk.Entry(self.rig_config_menu)
        self.txt_port.grid(row=2,
                           column=3,
                           padx=2,
                           pady=2,
                           sticky=tk.EW)
        t_txt_port = ToolTip(self.txt_port,
                                 follow_mouse=1,
                                 text="Port to connect.")

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
        self.txt_frequency = ttk.Entry(self.rig_control_menu)
        self.txt_frequency.grid(row=5,
                                column=1,
                                columnspan=3,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        t_txt_frequency = ToolTip(self.txt_frequency,
                              follow_mouse=1,
                              text="Frequency to tune.")
        ttk.Label(self.rig_control_menu,
                  text="Mhz").grid(row=5,
                                   column=3,
                                   sticky=tk.EW)
        ttk.Label(self.rig_control_menu,
                  text="Mode:").grid(row=6,
                                     column=0,
                                     sticky=tk.W)
        self.cbb_mode = ttk.Combobox(self.rig_control_menu, width=15)
        self.cbb_mode.grid(row=6,
                           column=1,
                           columnspan=3,
                           padx=2,
                           pady=2,
                           sticky=tk.EW)
        t_cbb_mode = ToolTip(self.cbb_mode,
                              follow_mouse=1,
                              text="Mode to use for tuning the frequency.")
        self.cbb_mode['values'] = CBB_MODES

        ttk.Label(self.rig_control_menu,
                  text="Description:").grid(row=7,
                                            column=0,
                                            sticky=tk.EW)
        self.txt_description = ttk.Entry(self.rig_control_menu)
        self.txt_description.grid(row=7,
                                  column=1,
                                  columnspan=3,
                                  padx=2,
                                  pady=2,
                                  sticky=tk.EW)
        t_txt_description = ToolTip(self.txt_description,
                                    follow_mouse=1,
                                    text="Description of the bookmark.")
        self.btn_add = ttk.Button(self.rig_control_menu,
                                  text="Add",
                                  width=7,
                                  command=self.cb_add)
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
                                     command=self.cb_delete)
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
                                   command=self.cb_get_frequency)
        t_btn_load = ToolTip(self.btn_load,
                    follow_mouse=1,
                    text="Get the frequency and mode from the rig.")

        self.btn_load.grid(row=8,
                           column=3,
                           padx=2,
                           pady=2)

#        # horizontal separator
        ttk.Frame(self.rig_control_menu).grid(row=9,
                                  column=0,
                                  columnspan=3,
                                  pady=5)


        self.scanning_conf_menu = LabelFrame(self, text="Scanning options")
        self.scanning_conf_menu.grid(row=2,
                       column=3,
                       #rowspan=3,
                       stick=tk.NSEW)
        ttk.Label(self.scanning_conf_menu,
                  text="Signal level:").grid(row=10,
                                             column=0,
                                             sticky=tk.W)
        self.txt_sgn_level = ttk.Entry(self.scanning_conf_menu,
                                       width=10)
        self.txt_sgn_level.grid(row=10,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        t_txt_sgn_level = ToolTip(self.txt_sgn_level,
                                  follow_mouse=1,
                                  text="Signal level to trigger on.")

        ttk.Label(self.scanning_conf_menu,
                  text=" dBFS").grid(row=10,
                                  column=2,
                                  padx=0,
                                  sticky=tk.W)

        ttk.Label(self.scanning_conf_menu,
                  text="Delay:").grid(row=13,
                                      column=0,
                                      sticky=tk.W)
        self.txt_delay = ttk.Entry(self.scanning_conf_menu,
                                   width=10)
        t_txt_delay = ToolTip(self.txt_delay,
                              follow_mouse=1,
                              text="Delay after finding a signal.")

        self.txt_delay.grid(row=13,
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

        ttk.Label(self.scanning_conf_menu,
                  text="Passes:").grid(row=14,
                                      column=0,
                                      sticky=tk.W)

        self.txt_passes = ttk.Entry(self.scanning_conf_menu,
                                   width=10)
        self.txt_passes.grid(row=14,
                            column=1,
                            columnspan=1,
                            padx=2,
                            pady=2,
                            sticky=tk.W)
        t_txt_passes = ToolTip(self.txt_passes,
                                     follow_mouse=1,
                                     text="Number of scans.")

        ttk.Label(self.scanning_conf_menu,
                  text="  0=Infinite").grid(row=14,
                                       padx=0,
                                       column=2,
                                       sticky=tk.EW)

        self.cb_wait = tk.BooleanVar()
        self.ckb_wait = ttk.Checkbutton(self.scanning_conf_menu,
                                                 text="Wait",
                                                 onvalue=True,
                                                 offvalue=False,
                                                 variable=self.cb_wait)

        self.ckb_wait.grid(row=15,
                                    column=0,
                                    columnspan=1,
                                    sticky=tk.E)
        t_ckb_wait = ToolTip(self.ckb_wait,
                                     follow_mouse=1,
                                     text="Waits after having found an active"\
                                          " frequency.")

        self.cb_record = tk.BooleanVar()
        self.ckb_record = ttk.Checkbutton(self.scanning_conf_menu,
                                                 text="Record",
                                                 onvalue=True,
                                                 offvalue=False,
                                                 variable=self.cb_record)

        self.ckb_record.grid(row=15,
                                    column=1,
                                    columnspan=1,
                                    sticky=tk.E)
        t_ckb_record = ToolTip(self.ckb_record,
                                     follow_mouse=1,
                                     text="Enable the recording of signal to"\
                                     " a file.")

        self.cb_log = tk.BooleanVar()
        self.ckb_log = ttk.Checkbutton(self.scanning_conf_menu,
                                                 text="Log",
                                                 onvalue=True,
                                                 offvalue=False,
                                                 variable=self.cb_log)
        t_ckb_log = ToolTip(self.ckb_log,
                            follow_mouse=1,
                            text="Logs the activities to a file.")

        self.ckb_log.grid(row=15,
                          column=2,
                          columnspan=1,
                          sticky=tk.E)


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

        self.txt_range_min = ttk.Entry(self.freq_scanning_menu,
                                       width=10)

        self.txt_range_min.grid(row=12,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        t_txt_range_min = ToolTip(self.txt_range_min,
                                 follow_mouse=1,
                                 text="Lower bound of the frequency"\
                                      " band to scan.")

        self.txt_range_max = ttk.Entry(self.freq_scanning_menu,
                                       width=10)
        self.txt_range_max.grid(row=12,
                                column=2,
                                columnspan=1,
                                padx=0,
                                pady=0,
                                sticky=tk.W)
        t_txt_range_max = ToolTip(self.txt_range_max,
                                 follow_mouse=1,
                                 text="Lower bound of the frequency"\
                                      " band to scan.")

        ttk.Label(self.freq_scanning_menu,
                  text="Interval:").grid(row=13,
                                         column=0,
                                         sticky=tk.W)
        self.txt_interval = ttk.Entry(self.freq_scanning_menu,
                                      width=10)
        self.txt_interval.grid(row=13,
                               column=1,
                               columnspan=1,
                               padx=2,
                               pady=2,
                               sticky=tk.W)
        t_txt_interval = ToolTip(self.txt_interval,
                                 follow_mouse=1,
                                 text="Tune once every interval khz.")
        ttk.Label(self.freq_scanning_menu,
                  text="Khz").grid(row=13,
                                   padx=0,
                                   column=2,
                                   sticky=tk.EW)

        self.cb_auto_bookmark = tk.BooleanVar()
        self.ckb_auto_bookmark = ttk.Checkbutton(self.freq_scanning_menu,
                                                 text="auto bookmark",
                                                 onvalue=True,
                                                 offvalue=False,
                                                 variable=self.cb_auto_bookmark)
        t_ckb_auto_bookmark = ToolTip(self.ckb_auto_bookmark,
                                      follow_mouse=1,
                                       text="Bookmark any active frequency"\
                                            " found.")

        self.ckb_auto_bookmark.grid(row=16,
                                    column=0,
                                    columnspan=2)

        ttk.Frame(self.freq_scanning_menu).grid(row=17,
                                  column=0,
                                  columnspan=3,
                                  pady=5)

        self.book_scanning_menu = LabelFrame(self, text="Bookmark scanning")
        self.book_scanning_menu.grid(row=4,
                                    column=3,
                                    #rowspan=3,
                                    stick=tk.NSEW)

#        #horrible horizontal placeholder
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
                                          command=self.bookmark_toggle,
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
                                          command=self.bookmark_lockout,
                                          )
        t_book_lockout = ToolTip(self.book_lockout,
                                     follow_mouse=1,
                                     text="Lock the bookmark scan.")
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
                        #rowspan=3,
                       stick=tk.NSEW)
        self.ckb_top = ttk.Checkbutton(self.control_menu,
                                       text="Always on top",
                                       command=self.cb_top)
        self.ckb_top.grid(row=21,
                          column=2,
                          columnspan=1,
                          padx=2,
                          sticky=tk.EW)
        t_ckb_top = ToolTip(self.ckb_top,
                            follow_mouse=1,
                            text="This window is always on top.")


        self.cb_save_exit = tk.BooleanVar()
        self.ckb_save_exit = ttk.Checkbutton(self.control_menu,
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

#        # horizontal separator
        ttk.Frame(self.control_menu).grid(row=22,
                                  column=0,
                                  columnspan=3,
                                  pady=5)

    def apply_config(self, ac):
        """Applies the config to the UI.
        :param ac: object instance for handling the app config
        :type ac: AppConfig object
        :raises : none
        :returns : none
        """

        ac.read_conf()
        self.txt_hostname.insert(0, ac.config["hostname"])
        self.txt_port.insert(0, ac.config["port"])
        self.txt_interval.insert(0, ac.config["interval"])
        self.txt_delay.insert(0, ac.config["delay"])
        self.txt_passes.insert(0, ac.config["passes"])
        self.txt_sgn_level.insert(0, ac.config["sgn_level"])
        self.txt_range_min.insert(0, ac.config["range_min"])
        self.txt_range_max.insert(0, ac.config["range_max"])
        self.cb_save_exit.set(ac.config["save_exit"].lower())
        self.cb_auto_bookmark.set(ac.config["auto_bookmark"].lower())
        if ac.config["always_on_top"].lower() == "true":
            if self.ckb_top.state() != ("selected"):
                self.ckb_top.invoke()
        self.rigctl = RigCtl(self.txt_hostname.get(),
                             self.txt_port.get())

    def _store_conf(self, ac):  #pragma: no cover
        """populates the ac object reading the info from the UI
        :param ac: object used to hold the app configuration.
        :type ac: AppConfig() object
        :returns ac: ac obj updated.
        """

        ac.config["hostname"] = self.txt_hostname.get()
        ac.config["port"] = self.txt_port.get()
        ac.config["interval"] = self.txt_interval.get()
        ac.config["delay"] = self.txt_delay.get()
        ac.config["passes"] = self.txt_passes.get()
        ac.config["sgn_level"] = self.txt_sgn_level.get()
        ac.config["range_min"] = self.txt_range_min.get()
        ac.config["range_max"] = self.txt_range_max.get()
        ac.config["save_exit"] = self.cb_save_exit.get()
        ac.config["auto_bookmark"] = self.cb_auto_bookmark.get()
        if self.ckb_top.state() != ("selected"):
            ac.config["always_on_top"] = "true"
        else:
            ac.config["always_on_top"] = "false"
        return ac


    def shutdown(self,ac):  #pragma: no cover
        """Here we quit. Before exiting, if save_exit checkbox is checked
        we save the configuration of the app and the bookmarks.
        :param ac: object that represent the UI configuration
        :type ac:AppConfig instance
        :returns: none
        """

        if self.cb_save_exit.get():
            self.bookmark("save", ",")
            ac = self._store_conf(ac)
            ac.write_conf()
        self.master.destroy()

    def bookmark(self, task, delimiter):  #pragma: no cover
        """Bookmarks handling. loads and saves the bookmarks as
        a csv file.
        :param task: either load or save
        :type task: string
        :param delimiter: delimiter to use for creating the csv file
        :type delimiter: string
        :raises : none
        :returns : none
        """

        if task not in ALLOWED_BOOKMARK_TASKS:
            logger.info("Not allowed bookmark task requested {}, "\
                        "ignoring.".format(task))

        bookmarks = IO()
        if task == "load":
            try:
                bookmarks.csv_load(self.bookmarks_file, delimiter)
                for line in bookmarks.row_list:
                    if len(line) < LEN_BM:
                        line.append("O")
                    line[BM.freq] = self._frequency_pp(line[BM.freq])
                    item = self.tree.insert('', tk.END, values=line)
                    self.bookmark_bg_tag(item, line[BM.lockout])
            except InvalidPathError:
                logger.info("No bookmarks file found, skipping.")

        if task == "save":
            for item in self.tree.get_children():
                values = self.tree.item(item).get('values')
                values[BM.freq] = self._frequency_pp_parse(values[BM.freq])
                bookmarks.row_list.append(values)
            bookmarks.csv_save(self.bookmarks_file, delimiter)

    def bookmark_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
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
            self.bookmark_bg_tag(self.selected_bookmark, values[BM.lockout])

    def frequency_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle frequency scan Start/Stop button, changing label text as
           appropriate.
        """

        if self.scan_mode == None or self.scan_mode == "frequency" : 
            action = self.freq_scan_toggle.cget('text').lower()
            self.freq_scan_toggle.config(text = next(icycle))
            self._scan("frequency", action)

    def _scan(self, mode, action):  #pragma: no cover
        """Wrapper around the scanning class instance. Creates the task
        object and issues the scan.
        :param mode: bookmark or frequency
        :type mode: string
        :param action: only start, for now
        :type action: string
        :raises: NotImplementedError if action different than "start" is passed
        :returns: None
        """

        if action.lower() not in SUPPORTED_SCANNING_ACTIONS:
            logger.error("Provided action:{}".format(action))
            logger.error("Supported actions:{}".format(
                         SUPPORTED_SCANNING_ACTIONS))
            raise UnsupportedScanningConfigError

        if action.lower() == "stop" and self.scan_thread != None:
            self.scanning.terminate()
            self.scan_thread = None
            self.scan_mode = None
            return
        
        if (action.lower() == "start" and self.scan_thread != None) :
            return
        if (action.lower() == "stop" and self.scan_thread == None) :
            return

        self.scan_mode = mode.lower()
        bookmarks = self.tree
        min_freq = self.txt_range_min.get()
        max_freq = self.txt_range_max.get()
        delay = self.txt_delay.get()
        passes = self.txt_passes.get()
        interval = self.txt_interval.get()
        sgn_level = self.txt_sgn_level.get()
        if (len(self.ckb_record.state()) == 1 and
            self.ckb_record.state()== ('selected',)):
            record = True
        else:
            record = False
        if (len(self.ckb_log.state()) == 1 and
            self.ckb_log.state()== ('selected',)):
            log = True
        else:
            log = False
        if (len(self.ckb_wait.state()) == 1 and
            self.ckb_wait.state()== ('selected',)):
            wait = True
        else:
            wait = False
        if mode == "frequency" :
            button = self.freq_scan_toggle
        else :
            button = self.book_scan_toggle

        task = ScanningTask(mode,
                                     bookmarks,
                                     button,
                                     min_freq,
                                     max_freq,
                                     delay,
                                     passes,
                                     interval,
                                     sgn_level,
                                     record, 
                                     log,
                                     wait)
        self.scanning = Scanning()
        self.scan_thread = threading.Thread(target = self.scanning.scan, 
                                            args = (task,))
        self.scan_thread.start()

# Leaving this code to remind me to deal with this
#        
#        if (task.mode.lower() == "frequency" and 
#            len(task.new_bookmark_list) > 0 and 
#            (len(self.ckb_auto_bookmark.state()) == 1 and
#             self.ckb_auto_bookmark.state()== ('selected',))):
#                 self._add_new_bookmarks(task.new_bookmark_list)

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

    def _clear_form(self):  #pragma: no cover
        """Clear the form.. nothing more.
        :param: none
        :raises: none
        :returns: none
        """

        self.txt_frequency.delete(0, tk.END)
        self.txt_description.delete(0, tk.END)
        self.cbb_mode.delete(0, tk.END)

    def _add_new_bookmarks(self, nbl):  #pragma: no cover
        """Fill in the data, calls uses cb_add() and calls clear_form.
        :param nbl: list of new frequencies to bookmark
        :type nbl: list
        :raises: none
        :returns: none
        """

        self._clear_form()
        now = datetime.datetime.utcnow().strftime("%a %b %d %H:%M %Y")
        for nb in nbl:
            self.txt_description.insert(0, "activity on {}".format(now))
            self.txt_frequency.insert(0, self._frequency_pp(nb[2]))
            self.cbb_mode.insert(0,nb[1])
            # adding bookmark to the list
            self.cb_add()
            self._clear_form()

    def cb_top(self):  #pragma: no cover
        """Set window property to be always on top.
        :param: none
        :raises: none
        :returns: none
        """

        self.master.attributes("-topmost",
                               'selected' in self.ckb_top.state())

    def cb_get_frequency(self):  #pragma: no cover
        """Get current rig frequency and mode.
        :param: none
        :raises: none
        :returns: none
        """

        # clear fields
        self._clear_form()
        try:
            frequency = self.rigctl.get_frequency()
            mode = self.rigctl.get_mode()
            # update fields
            self.txt_frequency.insert(0, self._frequency_pp(frequency))
            self.cbb_mode.insert(0, mode)
        except Exception as err:
            tkMessageBox.showerror("Error",
                                         "Could not connect to rig.\n%s" % err,
                                         parent=self)

    def cb_set_frequency(self, event):  #pragma: no cover
        """Set the rig frequency and mode.
        :param event: not used?
        :type event:
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        values = self.tree.item(item).get('values')
        try:
            self.rigctl.set_frequency(values[0].replace(',', ''))
            self.rigctl.set_mode((values[1]))
        except Exception as err:
            tkMessageBox.showerror("Error",
                                         "Could not set frequency.\n%s" % err,
                                         parent=self)

    def cb_autofill_form(self, event):  #pragma: no cover
        """Auto-fill bookmark fields with details
        of currently selected Treeview entry.
        :param event: not used?
        :type event:
        :raises: none
        :returns: none
        """

        self.selected_bookmark = self.tree.focus()
        values = self.tree.item(self.selected_bookmark).get('values')
        self._clear_form()
        self.cbb_mode.insert(0, values[1])
        self.txt_frequency.insert(0, values[0])
        self.txt_description.insert(0, values[2])

    def cb_add(self):  #pragma: no cover
        """Add frequency to tree and saves the bookmarks.
        :param: none
        :raises: none
        :returns: none
        """

        # get values
        frequency = self._frequency_pp_parse(self.txt_frequency.get())
        mode = self.cbb_mode.get()
        description = self.txt_description.get()
        lockout = "O"
        # find where to insert (insertion sort)
        idx = tk.END
        for item in self.tree.get_children():
            freq = self.tree.item(item).get('values')[BM.freq]
            curr_freq = self._frequency_pp_parse(freq)
            curr_mode = self.tree.item(item).get('values')[BM.mode]
            if frequency < curr_freq:
                idx = self.tree.index(item)
                break
            elif (frequency == curr_freq and
                  mode == curr_mode and
                  mode != UNKNOWN_MODE):
                tkMessageBox.showerror("Error", "A bookmark with the "\
                                             "same frequency and mode "\
                                             "already exists.", parent=self)
                return
        # insert
        item = self.tree.insert('',
                                idx,
                                values=[self._frequency_pp(frequency),
                                        mode,
                                        description,
                                        lockout])

        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        # save
        self.bookmark("save", ",")

    def cb_delete(self):  #pragma: no cover
        """Delete frequency from tree.
        :param: none
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        if item != '':
            self.tree.delete(item)
            # save
        self.bookmark("save", ",")

    def _frequency_pp(self, frequency):  #pragma: no cover
        """Add thousands separator.
        :param frequency: frequency value
        :type frequency: string
        :return: frequency with separator
        :return type: string
        """

        return '{:,}'.format(int(frequency))

    def _frequency_pp_parse(self, frequency):  #pragma: no cover
        """Remove thousands separator.
        :param frequency: frequency value
        :type frequency: string
        :return: frequency without separator
        :return type: string
        """

        return int(str(frequency).replace(',', ''))



#!/usr/bin/env python

"""
Remote application that interacts with gqrx using rigctl protocol.
Gqrx partially implements rigctl since version 2.3.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
License: MIT License

Copyright (c) 2014 Rafael Marmelo
"""

# import modules

import csv
import logging
import datetime
from modules.constants import ALLOWED_BOOKMARK_TASKS
from modules.constants import SUPPORTED_SCANNING_ACTIONS
from modules.constants import CBB_MODES
from modules.constants import MAX_SCAN_THREADS
from modules.app_config import AppConfig
from modules.exceptions import UnsupportedScanningConfigError
from modules.disk_io import IO
from modules.rigctl import RigCtl
from modules.scanning import ScanningTask
from modules.scanning import Scanning
import os.path
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import Text
from tkinter import LabelFrame
import tkinter.messagebox

# logging configuration
logger = logging.getLogger(__name__)

class GqrxRemote(ttk.Frame):
    """Remote application that interacts with gqrx using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.

    :raises: none
    :returns: none
    """

    def __init__(self, root, ac):
        ttk.Frame.__init__(self, root)
        self.bookmarks_file = "gqrx-bookmarks.csv"
        self.log_file = None
        self.build(root, ac)
        self.cbb_mode.current(0)
        # bookmarks loading on start
        self.bookmark("load", ",")
        self.rigctl = RigCtl(self.txt_hostname.get(),
                             self.txt_port.get())

    def build(self,root, ac):
        """Build and initialize the GUI widgets.

        :param ac: object instance for handling the app config
        :type ac: AppConfig object
        :raises: none
        :returns: none
        """

        self.master.title("Gqrx Remote")
        self.master.minsize(800, 244)
        self.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # +------------------------------+------------------------------+
        # |                              | Hostname:    _______________ |
        # |                              | Port:        _______________ |
        # |                              |                              |
        # |                              | Frequency:   _______________ |
        # |        Frequency List        | Mode:        ____________[v] |
        # |                              | Description: _______________ |
        # |                              |                              |
        # |                              |         [add] [delete] [get] |
        # |                              |                              |
        # |                              |  [x] Always on top?   [quit] |
        # +------------------------------+------------------------------+

        # frequency list
        self.tree = ttk.Treeview(self,
                                 columns=('frequency',
                                          'mode',
                                          'description'),
                                 show="headings")
        self.tree.heading('frequency',
                          text='Frequency',
                          anchor=tk.CENTER)
        self.tree.column('frequency',
                         minwidth=100,
                         width=130,
                         stretch=False,
                         anchor=tk.CENTER)
        self.tree.heading('mode',
                          text='Mode',
                          anchor=tk.CENTER)
        self.tree.column('mode',
                         minwidth=80,
                         width=80,
                         stretch=False,
                         anchor=tk.CENTER)
        self.tree.heading('description',
                          text='Description',
                          anchor=tk.W)
        self.tree.column('description',
                         stretch=True,
                         anchor=tk.W,
                         minwidth=70,
                         width=70)
        ysb = ttk.Scrollbar(self,
                            orient=tk.VERTICAL,
                            command=self.tree.yview)
        ysb.grid(row=0,
                 column=1,
                 sticky=tk.NS)
        xsb = ttk.Scrollbar(self,
                            orient=tk.HORIZONTAL,
                            command=self.tree.xview)
        xsb.grid(row=1,
                 column=0,
                 sticky=tk.EW)
        self.tree.configure(yscroll=ysb.set,
                            xscroll=xsb.set)
        self.tree.grid(row=0,
                       column=0,
                       sticky=tk.NSEW)
        self.tree.bind('<<TreeviewSelect>>',
                       self.cb_autofill_form)
        self.tree.bind('<Double-Button-1>',
                       self.cb_set_frequency)

        # vertical separator
        ttk.Frame(self).grid(row=0,
                             column=2,
                             rowspan=2,
                             padx=5)

        # right-side container
        self.menu = ttk.Frame(self)
        self.menu.grid(row=0,
                       column=3,
                       rowspan=2,
                       stick=tk.NSEW)
        self.menu.rowconfigure(7, weight=1)

        ttk.Label(self.menu,
                  text="GQRX Configuration:").grid(row=0,
                                                   column=0,
                                                   sticky=tk.W)


        ttk.Label(self.menu,
                  text="Hostname:").grid(row=1,
                                         column=0,
                                         sticky=tk.W)
        self.txt_hostname = ttk.Entry(self.menu)
        self.txt_hostname.grid(row=1,
                               column=1,
                               columnspan=3,
                               padx=2,
                               pady=2,
                               sticky=tk.EW)

        ttk.Label(self.menu,
                  text="Port:").grid(row=2,
                                     column=0,
                                     sticky=tk.W)
        self.txt_port = ttk.Entry(self.menu)
        self.txt_port.grid(row=2,
                           column=1,
                           columnspan=3,
                           padx=2,
                           pady=2,
                           sticky=tk.EW)

        # horizontal separator
        ttk.Frame(self.menu).grid(row=3,
                                  column=0,
                                  columnspan=3,
                                  pady=5)
        ttk.Label(self.menu,
                  text="Bookmarking:").grid(row=4,
                                            column=0,
                                            sticky=tk.W)

        ttk.Label(self.menu,
                  text="Frequency:").grid(row=5,
                                          column=0,
                                          sticky=tk.W)
        self.txt_frequency = ttk.Entry(self.menu)
        self.txt_frequency.grid(row=5,
                                column=1,
                                columnspan=3,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        ttk.Label(self.menu,
                  text="Mhz").grid(row=5,
                                   column=3,
                                   sticky=tk.EW)
        ttk.Label(self.menu,
                  text="Mode:").grid(row=6,
                                     column=0,
                                     sticky=tk.W)
        self.cbb_mode = ttk.Combobox(self.menu, width=15)
        self.cbb_mode.grid(row=6,
                           column=1,
                           columnspan=3,
                           padx=2,
                           pady=2,
                           sticky=tk.EW)
        self.cbb_mode['values'] = CBB_MODES

        ttk.Label(self.menu,
                  text="Description:").grid(row=7,
                                            column=0,
                                            sticky=tk.EW)
        self.txt_description = ttk.Entry(self.menu)
        self.txt_description.grid(row=7,
                                  column=1,
                                  columnspan=3,
                                  padx=2,
                                  pady=2,
                                  sticky=tk.EW)

        self.btn_add = ttk.Button(self.menu,
                                  text="Add",
                                  width=7,
                                  command=self.cb_add)
        self.btn_add.grid(row=8,
                          column=1,
                          padx=2,
                          pady=2)

        self.btn_delete = ttk.Button(self.menu,
                                     text="Delete",
                                     width=7,
                                     command=self.cb_delete)
        self.btn_delete.grid(row=8,
                             column=2,
                             padx=2,
                             pady=2)

        self.btn_load = ttk.Button(self.menu,
                                   text="Get",
                                   width=7,
                                   command=self.cb_get_frequency)
        self.btn_load.grid(row=8,
                           column=3,
                           padx=2,
                           pady=2)

        ttk.Frame(self.menu).grid(row=9,
                                  column=0,
                                  columnspan=3,
                                  pady=5)
        ttk.Label(self.menu,
                  text="Frequency scan:").grid(row=10,
                                               column=0,
                                               sticky=tk.W)

        self.freq_scan_start = ttk.Button(self.menu,
                                          text="Start",
                                          command=self.frequency_start)
        self.freq_scan_start.grid(row=10,
                                  column=1,
                                  columnspan=1,
                                  padx=2,
                                  sticky=tk.NW)

        ttk.Label(self.menu,
                  text="Signal level:").grid(row=11,
                                             column=0,
                                             sticky=tk.W)
        self.txt_sgn_level = ttk.Entry(self.menu,
                                       width = 10)
        self.txt_sgn_level.grid(row=11,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        ttk.Label(self.menu,
                  text="db").grid(row=11,
                                  column=2,
                                  padx=0,
                                  sticky=tk.W)

        ttk.Label(self.menu,
                  text="Min/Max:").grid(row=12,
                                        column=0,
                                        sticky=tk.W)
        ttk.Label(self.menu,
                  text="Mhz").grid(row=12,
                                   padx=0,
                                   column=3,
                                   sticky=tk.W)
        self.txt_range_min = ttk.Entry(self.menu,
                                       width = 10)
        self.txt_range_min.grid(row=12,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        self.txt_range_max = ttk.Entry(self.menu,
                                       width = 10)
        self.txt_range_max.grid(row=12,
                                column=2,
                                columnspan=1,
                                padx=0,
                                pady=0,
                                sticky=tk.W)

        ttk.Label(self.menu,
                  text="Interval:").grid(row=13,
                                         column=0,
                                         sticky=tk.W)
        self.txt_interval = ttk.Entry(self.menu,
                                      width = 10)
        self.txt_interval.grid(row=13,
                              column=1,
                              columnspan=1,
                              padx=2,
                              pady=2,
                              sticky=tk.W)
        ttk.Label(self.menu,
                  text="Khz").grid(row=13,
                                   padx=0,
                                   column=2,
                                   sticky=tk.EW)

        ttk.Label(self.menu,
                  text="Delay:").grid(row=14,
                                      column=0,
                                      sticky=tk.W)
        self.txt_delay = ttk.Entry(self.menu,
                                   width = 10)
        self.txt_delay.grid(row=14,
                            column=1,
                            columnspan=1,
                            padx=2,
                            pady=2,
                            sticky=tk.W)
        ttk.Label(self.menu,
                  text="Seconds").grid(row=14,
                                       padx=0,
                                       column=2,
                                       sticky=tk.EW)

        self.cb_auto_bookmark = tkinter.BooleanVar()
        self.ckb_auto_bookmark = ttk.Checkbutton(self.menu,
                                                 text="auto bookmark",
                                                 onvalue = True,
                                                 offvalue = False,
                                                 variable = self.cb_auto_bookmark
                                                 )

        self.ckb_auto_bookmark.grid(row=15,
                                    column=1,
                                    columnspan=1,
                                    sticky=tk.EW)

        # horizontal separator
        ttk.Frame(self.menu).grid(row=16,
                                  column=0,
                                  columnspan=3,
                                  pady=5)

        ttk.Label(self.menu,
                  text="Bookmarks scan:").grid(row=17,
                                               column=0,
                                               sticky=tk.W)

        self.book_scan_start = ttk.Button(self.menu,
                                          text="Start",
                                          command=self.bookmark_start)
        self.book_scan_start.grid(row=17,
                                  column=1,
                                  columnspan=1,
                                  padx=2,
                                  sticky=tk.NW)

        # horizontal separator
        ttk.Frame(self.menu).grid(row=18,
                                  column=0,
                                  columnspan=3,
                                  pady=5)

        self.ckb_top = ttk.Checkbutton(self.menu,
                                       text="Always on top",
                                       command=self.cb_top)
        self.ckb_top.grid(row=20,
                          column=2,
                          columnspan=1,
                          sticky=tk.EW)

        self.cb_save_exit = tkinter.BooleanVar()
        self.ckb_save_exit = ttk.Checkbutton(self.menu,
                                             text="Save on exit",
                                             onvalue = True,
                                             offvalue = False,
                                             variable = self.cb_save_exit)

        self.ckb_save_exit.grid(row=20,
                                column=1,
                                columnspan=1,
                                sticky=tk.EW)

        self.btn_quit = ttk.Button(self.menu,
                                   text="Quit",
                                   command = lambda: self.shutdown(ac))
        self.btn_quit.grid(row=20,
                           column=3,
                           columnspan=1,
                           sticky=tk.SE)

        # apply config
        ac.read_conf()
        self.txt_hostname.insert(0, ac.config["hostname"])
        self.txt_port.insert(0, ac.config["port"])
        self.txt_interval.insert(0, ac.config["interval"])
        self.txt_delay.insert(0, ac.config["delay"])
        self.txt_sgn_level.insert(0, ac.config["sgn_level"])
        self.txt_range_min.insert(0, ac.config["range_min"])
        self.txt_range_max.insert(0, ac.config["range_max"])
        self.cb_save_exit.set(ac.config["save_exit"].lower())
        self.cb_auto_bookmark.set(ac.config["auto_bookmark"].lower())
        if ac.config["always_on_top"].lower() == "true":
            if self.ckb_top.state() != ("selected"):
                self.ckb_top.invoke()

    def _store_conf(self,ac):
        """populates the ac object reading the info from the UI

        :param ac: object used to hold the app configuration.
        :type ac: AppConfig() object
        :returns ac: ac obj updated.
        """

        ac.config["hostname"] = self.txt_hostname.get()
        ac.config["port"] = self.txt_port.get()
        ac.config["interval"] = self.txt_interval.get()
        ac.config["delay"] = self.txt_delay.get()
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


    def shutdown(self, ac):
        """Here we quit. Before exiting, if save_exit checkbox is checked
        we save the configuration of the app and the bookmarks.

        :param ac: object that represent the UI configuration
        :type ac:AppConfig instance
        :returns: none
        """

        if self.cb_save_exit.get():
            self.bookmark("save" ,",")
            ac = self._store_conf(ac)
            ac.write_conf()
        self.master.destroy()

    def bookmark(self, task, delimiter):
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
            bookmarks.csv_load(self.bookmarks_file, delimiter)
            for line in bookmarks.row_list:
                line[0] = self._frequency_pp(line[0])
                self.tree.insert('', tk.END, values=line)

        if task == "save":
            for item in self.tree.get_children():
                values = self.tree.item(item).get('values')
                values[0] = self._frequency_pp_parse(values[0])
                bookmarks.row_list.append(values)
            bookmarks.csv_save(self.bookmarks_file, delimiter)

    def bookmark_start(self):
        """Wrapper around _scan() that starts a scan from bookmarks.

        """

        self._scan("bookmarks", "start")

    def frequency_start(self):
        """Wrapper around _scan() that starts a scan from a frequency range.

        """

        self._scan("frequency", "start")

    def _scan(self, mode, action):
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
            logger.error("Supported actions:{}"
                          .format(SUPPORTED_SCANNING_ACTIONS))
            raise UnsupportedScanningConfigError

        bookmark_list = []
        for item in self.tree.get_children():
            values = self.tree.item(item).get('values')
            bookmark_list.append(values)
        min_freq = self.txt_range_min.get()
        max_freq = self.txt_range_max.get()
        delay = self.txt_delay.get()
        interval = self.txt_interval.get()
        sgn_level = self.txt_sgn_level.get()
        scanning_task = ScanningTask(mode, bookmark_list, min_freq, max_freq, delay, interval, sgn_level)


        scanning = Scanning()
        task = scanning.scan(scanning_task)
        logger.info("new activity found:{}".format(task.new_bookmark_list))
        if task.mode.lower() == "bookmarks":
            tkinter.messagebox.showerror("Activity found:{}".format(task.new_bookmark_list),
                                          parent=self)
        if task.mode.lower() == "frequency":
            self._add_new_bookmarks(task.new_bookmark_list)

    def _clear_form(self):
        """Clear the form.. nothing more.

        :param: none
        :raises: none
        :returns: none
        """

        self.txt_frequency.delete(0, tk.END)
        self.txt_description.delete(0, tk.END)
        self.cbb_mode.delete(0, tk.END)

    def _add_new_bookmarks(self, nbl):
        """Fill in the data, calls uses cb_add() and calls clear_form.

        :param nbl: list of new frequencies to bookmark
        :type nbl: list
        :raises: none
        :returns: none
        """

        now = datetime.datetime.utcnow().strftime("%a %b %d %H:%M %Y")
        for nb in nbl:
            self.txt_description.insert(0,"activity on {}".format(now))
            self._frequency_pp_parse(self.txt_frequency.insert(0, self._frequency_pp(frequency)))
            # adding bookmark to the list
            self.cb_add()
            self._clear_form()

    def cb_top(self):
        """Set window property to be always on top.

        :param: none
        :raises: none
        :returns: none
        """

        self.master.attributes("-topmost",
                               'selected' in self.ckb_top.state())

    def cb_get_frequency(self):
        """Get current gqrx frequency and mode.

        :param: none
        :raises: none
        :returns: none
        """

        # clear fields
        self._clear_form()
        try:
            frequency = self.rigctl.get_frequency()
            mode = self.get_mode()
            # update fields
            self.txt_frequency.insert(0, self._frequency_pp(frequency))
            self.cbb_mode.insert(0, mode)
        except Exception as err:
            tkinter.messagebox.showerror("Error",
                                         "Could not connect to gqrx.\n%s" % err,
                                         parent=self)

    def cb_set_frequency(self, event):
        """Set the gqrx frequency and mode.

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
            tkinter.messagebox.showerror("Error",
                                         "Could not set frequency.\n%s" % err,
                                         parent=self)

    def cb_autofill_form(self, event):
        """Auto-fill bookmark fields with details 
        of currently selected Treeview entry.

        :param event: not used?
        :type event:
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        values = self.tree.item(item).get('values')
        self._clear_form()
        self.cbb_mode.insert(0, values[1])
        self.txt_frequency.insert(0, values[0])
        self.txt_description.insert(0, values[2])

    def cb_add(self):
        """Add frequency to tree and saves the bookmarks.

        :param: none
        :raises: none
        :returns: none
        """

        # get values
        frequency = self._frequency_pp_parse(self.txt_frequency.get())
        mode = self.cbb_mode.get()
        description = self.txt_description.get()
        # find where to insert (insertion sort)
        idx = tk.END
        for item in self.tree.get_children():
            curr_freq = self._frequency_pp_parse(self.tree.item(item).get('values')[0])
            curr_mode = self.tree.item(item).get('values')[1]
            if frequency < curr_freq:
                idx = self.tree.index(item)
                break
            elif frequency == curr_freq and mode == curr_mode:
                tkinter.messagebox.showerror("Error", "A bookmark with the "\
                                             "same frequency and mode "\
                                             "already exists.", parent=self)
                return
        # insert
        item = self.tree.insert('',
                                idx,
                                values=[self._frequency_pp(frequency),
                                mode,
                                description])

        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        # save
        self.bookmark("save", ",")

    def cb_delete(self):
        """Delete frequency from tree.

        :param: none
        :raises: none
        :returns: none
        """

        item = self.tree.focus()
        if item != '':
            self.tree.delete(item)
            # save
        self.bookmark("save" ,",")

    def _frequency_pp(self, frequency):
        """Add thousands separator.

        :param frequency: frequency value
        :type frequency: string
        :return: frequency with separator
        :return type: string
        """

        return '{:,}'.format(int(frequency))

    def _frequency_pp_parse(self, frequency):
        """Remove thousands separator.

        :param frequency: frequency value
        :type frequency: string
        :return: frequency without separator
        :return type: string
        """

        return int(str(frequency).replace(',', ''))


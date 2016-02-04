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
"""

# import modules

import logging
import datetime
from modules.constants import ALLOWED_BOOKMARK_TASKS
from modules.constants import SUPPORTED_SCANNING_ACTIONS
from modules.constants import CBB_MODES
from modules.constants import BOOKMARKS_FILE
from modules.constants import UNKNOWN_MODE
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

# logging configuration
logger = logging.getLogger(__name__)

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

        # bookmarks list

        self.tree = ttk.Treeview(self,
                                 columns=("frequency",
                                          "mode",
                                          "description"),
                                 show="headings")
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
                                  stick=tk.NSEW)
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

        self.btn_add = ttk.Button(self.rig_control_menu,
                                  text="Add",
                                  width=7,
                                  command=self.cb_add)
        self.btn_add.grid(row=8,
                          column=1,
                          padx=2,
                          pady=2)

        self.btn_delete = ttk.Button(self.rig_control_menu,
                                     text="Delete",
                                     width=7,
                                     command=self.cb_delete)
        self.btn_delete.grid(row=8,
                             column=2,
                             padx=2,
                             pady=2)

        self.btn_load = ttk.Button(self.rig_control_menu,
                                   text="Get",
                                   width=7,
                                   command=self.cb_get_frequency)
        self.btn_load.grid(row=8,
                           column=3,
                           padx=2,
                           pady=2)

#        # horizontal separator
        ttk.Frame(self.rig_control_menu).grid(row=9,
                                  column=0,
                                  columnspan=3,
                                  pady=5)

        self.freq_scanning_menu = LabelFrame(self, text="Frequency scanning")
        self.freq_scanning_menu.grid(row=2,
                       column=3,
                       #rowspan=3,
                       stick=tk.NSEW)
        self.freq_scan_start = ttk.Button(self.freq_scanning_menu,
                                          text="Start",
                                          command=self.frequency_start)
        self.freq_scan_start.grid(row=15,
                                  column=2,
                                  columnspan=1,
                                  padx=2,
                                  sticky=tk.NW)

        ttk.Label(self.freq_scanning_menu,
                  text="Signal level:").grid(row=10,
                                             column=0,
                                             sticky=tk.W)
        self.txt_sgn_level = ttk.Entry(self.freq_scanning_menu,
                                       width=10)
        self.txt_sgn_level.grid(row=10,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        ttk.Label(self.freq_scanning_menu,
                  text="dBFS").grid(row=10,
                                  column=2,
                                  padx=0,
                                  sticky=tk.W)

        ttk.Label(self.freq_scanning_menu,
                  text="Min/Max:").grid(row=11,
                                        column=0,
                                        sticky=tk.W)
        ttk.Label(self.freq_scanning_menu,
                  text="khz").grid(row=11,
                                   padx=0,
                                   column=3,
                                   sticky=tk.W)
        self.txt_range_min = ttk.Entry(self.freq_scanning_menu,
                                       width=10)
        self.txt_range_min.grid(row=11,
                                column=1,
                                columnspan=1,
                                padx=2,
                                pady=2,
                                sticky=tk.W)
        self.txt_range_max = ttk.Entry(self.freq_scanning_menu,
                                       width=10)
        self.txt_range_max.grid(row=11,
                                column=2,
                                columnspan=1,
                                padx=0,
                                pady=0,
                                sticky=tk.W)

        ttk.Label(self.freq_scanning_menu,
                  text="Interval:").grid(row=12,
                                         column=0,
                                         sticky=tk.W)
        self.txt_interval = ttk.Entry(self.freq_scanning_menu,
                                      width=10)
        self.txt_interval.grid(row=12,
                               column=1,
                               columnspan=1,
                               padx=2,
                               pady=2,
                               sticky=tk.W)
        ttk.Label(self.freq_scanning_menu,
                  text="Khz").grid(row=12,
                                   padx=0,
                                   column=2,
                                   sticky=tk.EW)

        ttk.Label(self.freq_scanning_menu,
                  text="Delay:").grid(row=13,
                                      column=0,
                                      sticky=tk.W)
        self.txt_delay = ttk.Entry(self.freq_scanning_menu,
                                   width=10)
        self.txt_delay.grid(row=13,
                            column=1,
                            columnspan=1,
                            padx=2,
                            pady=2,
                            sticky=tk.W)
        ttk.Label(self.freq_scanning_menu,
                  text="Seconds").grid(row=13,
                                       padx=0,
                                       column=2,
                                       sticky=tk.EW)

        self.cb_auto_bookmark = tk.BooleanVar()
        self.ckb_auto_bookmark = ttk.Checkbutton(self.freq_scanning_menu,
                                                 text="auto bookmark",
                                                 onvalue=True,
                                                 offvalue=False,
                                                 variable=self.cb_auto_bookmark)

        self.ckb_auto_bookmark.grid(row=15,
                                    column=0,
                                    columnspan=1,
                                    sticky=tk.EW)

        ttk.Frame(self.freq_scanning_menu).grid(row=16,
                                  column=0,
                                  columnspan=3,
                                  pady=5)
        self.book_scanning_menu = LabelFrame(self, text="Bookmark scanning")
        self.book_scanning_menu.grid(row=3,
                                    column=3,
                                    #rowspan=3,
                                    stick=tk.NSEW)

#        #horrible horizontal placeholder
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                               column=0,
                               sticky=tk.NSEW)
        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                               column=1,
                               sticky=tk.NSEW)

        ttk.Label(self.book_scanning_menu,
                  width=8).grid(row=17,
                               column=2,
                               sticky=tk.NSEW)

        self.book_scan_start = ttk.Button(self.book_scanning_menu,
                                          text="Start",
                                          command=self.bookmark_start,
                                          )
        self.book_scan_start.grid(row=17,
                                  column=3,
                                  columnspan=1,
                                  padx=2,
                                  sticky=tk.W)

        # horizontal separator
        ttk.Frame(self.book_scanning_menu).grid(row=18,
                                  column=0,
                                  columnspan=3,
                                  rowspan=1,
                                  pady=5)

        self.control_menu = LabelFrame(self, text="Options")

        self.control_menu.grid(row=4,
                       column=3,
                        #rowspan=3,
                       stick=tk.NSEW)
        self.ckb_top = ttk.Checkbutton(self.control_menu,
                                       text="Always on top",
                                       command=self.cb_top)
        self.ckb_top.grid(row=20,
                          column=2,
                          columnspan=1,
                          padx=2,
                          sticky=tk.EW)

        self.cb_save_exit = tk.BooleanVar()
        self.ckb_save_exit = ttk.Checkbutton(self.control_menu,
                                             text="Save on exit",
                                             onvalue=True,
                                             offvalue=False,
                                             variable=self.cb_save_exit)

        self.ckb_save_exit.grid(row=20,
                                column=1,
                                columnspan=1,
                                padx=2,
                                sticky=tk.EW)

        self.btn_quit = ttk.Button(self.control_menu,
                                   text="Quit",
                                   command=lambda: self.shutdown(ac))
        self.btn_quit.grid(row=20,
                           column=3,
                           columnspan=1,
                           sticky=tk.SE)

#        # horizontal separator
        ttk.Frame(self.control_menu).grid(row=21,
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
                    line[0] = self._frequency_pp(line[0])
                    self.tree.insert('', tk.END, values=line)
            except InvalidPathError:
                logger.info("No bookmarks file found, skipping.")

        if task == "save":
            for item in self.tree.get_children():
                values = self.tree.item(item).get('values')
                values[0] = self._frequency_pp_parse(values[0])
                bookmarks.row_list.append(values)
            bookmarks.csv_save(self.bookmarks_file, delimiter)

    def bookmark_start(self):  #pragma: no cover
        """Wrapper around _scan() that starts a scan from bookmarks.
        """

        self._scan("bookmarks", "start")

    def frequency_start(self):  #pragma: no cover
        """Wrapper around _scan() that starts a scan from a frequency range.
        """

        self._scan("frequency", "start")

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
            logger.error("Supported actions:{}".format(SUPPORTED_SCANNING_ACTIONS))
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
        scanning_task = ScanningTask(mode,
                                     bookmark_list,
                                     min_freq,
                                     max_freq,
                                     delay,
                                     interval,
                                     sgn_level)
        scanning = Scanning()
        task = scanning.scan(scanning_task)
        if (task.mode.lower() == "bookmarks" and 
            len(task.new_bookmark_list) > 0):
            message = self._new_activity_message(task.new_bookmark_list)
            tkMessageBox.showinfo("New activity found", message,
                                   parent=self)

        if (task.mode.lower() == "frequency" and 
            len(task.new_bookmark_list) > 0 and 
            (len(self.ckb_auto_bookmark.state()) == 1 and
            self.ckb_auto_bookmark.state()== ('selected',))):
                self._add_new_bookmarks(task.new_bookmark_list)

        elif (task.mode.lower() == "frequency" and 
              len(task.new_bookmark_list) > 0 and 
              len(self.ckb_auto_bookmark.state()) == 0):
                message = self._new_activity_message(task.new_bookmark_list)
                tkMessageBox.showinfo("New activity found", message,
                                       parent=self)

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

        item = self.tree.focus()
        values = self.tree.item(item).get('values')
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
        # find where to insert (insertion sort)
        idx = tk.END
        for item in self.tree.get_children():
            freq = self.tree.item(item).get('values')[0]
            curr_freq = self._frequency_pp_parse(freq)
            curr_mode = self.tree.item(item).get('values')[1]
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
                                        description])

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



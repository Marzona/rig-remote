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
from rig_remote.constants import (
    BM,
)
from rig_remote.exceptions import (
    UnsupportedScanningConfigError,
    UnsupportedSyncConfigError,
    BookmarkFormatError,
)
from rig_remote.bookmarksmanager import BookmarksManager, bookmark_factory
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import Scanning
from rig_remote.syncing import Syncing, SyncTask
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.models.bookmark import Bookmark
from rig_remote.utility import (
    shutdown,
    center_window,
)
from rig_remote.queue_comms import QueueComms
import tkinter as tk
from tkinter import ttk, LabelFrame, messagebox, filedialog
import threading
import itertools
from rig_remote.utility import (
    khertz_to_hertz,
)
from rig_remote.stmessenger import STMessenger
from rig_remote.app_config import AppConfig
logger = logging.getLogger(__name__)


class RigRemote(ttk.Frame): # pragma: no cover
    """Remote application that interacts with the rig using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.

    :returns: none
    """

    _SUPPORTED_SYNC_ACTIONS = ("start", "stop")
    _SUPPORTED_SCANNING_ACTIONS = ("start", "stop")
    _UI_EVENT_TIMER_DELAY = 1000

    _ABOUT = """
    Rig remote is a software for controlling a rig
    via tcp/ip and RigCtl.

    GitHub: https://github.com/Marzona/rig-remote

    Project wiki: https://github.com/Marzona/rig-remote/wiki
    """

    def __init__(self, root:tk.Tk, ac:AppConfig):
        self.rig_control_menu = None
        self.btn_delete1 = None
        self.btn_add1 = None
        self.btn_recall1 = None
        self.scanning_conf_menu = None
        self.btn_tune1 = None
        self.btn_load1 = None
        self.rig_config_menu = None
        self.tree = None
        self.rigctl_one = None
        self.rigctl_two = None
        self.scanq = None
        self.synq = None
        self.scan_thread = None
        self.sync_thread = None
        self.scan_mode = None
        self.scanning = None
        self.selected_bookmark = None
        self.root = root
        self.params = {}
        self.params_last_content = {}
        self.alt_files = {}
        self.log_file = ac.config["log_filename"]
        ttk.Frame.__init__(self, root)
        self.ac = ac
        self._configure_rigs()
        self._build_ac(ac)
        self.params["cbb_mode1"].current(0)
        self.focus_force()
        self.update()
        self._init_queues()
        self.bind_all("<1>", lambda event: self.focus_set(event))
        # bookmarks loading on start
        self.new_bookmark_list = []
        self.bookmarks_file = ""
        self.bookmarks = BookmarksManager()
        self._load_bookmarks()
        self.buildmenu(root)

    def _init_queues(self):
        logger.info("initializiing queues")
        self.scanq = STMessenger(queuecomms=QueueComms())
        self.syncq = STMessenger(queuecomms=QueueComms())
        logger.info("initializiing queues done")

    def _import_bookmarks(self):
        filename = filedialog.askopenfilename(
            initialdir="~/",
            title="Select bookmark file",
            filetypes=(("csv files", "*.csv"), ("all files", "*.*")),
        )
        try:
            bookmark_list = self.bookmarks.import_bookmarks(filename=filename)
        except BookmarkFormatError:
            messagebox.showerror("Error", "Unsupported file format.")
        self._insert_bookmarks(bookmarks=bookmark_list)
        [self.bookmarks.add_bookmark(bookmark) for bookmark in bookmark_list]

    def _export_bookmarks(self):
        """Export bookmarks to a file."""
        filename = filedialog.asksaveasfilename(
            initialdir="~/",
            title="Select bookmark file",
            initialfile="bookmarks-export.csv",
            filetypes=(("csv", "*.csv"), ("all files", "*.*")),
        )
        if filename:
            try:
                self.bookmarks.export_rig_remote(filename=filename)
                messagebox.showinfo("Success", f"Bookmarks exported to {filename}.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export bookmarks.\n{e}")

    def _show_about_popup(self):
        """Display the About popup."""
        from tkinter import messagebox
        messagebox.showinfo("About", "Rig Remote Application\nVersion 1.0")

    def _load_bookmarks(self):
        logger.info("loading bookmarks")
        self.bookmarks_file:str = self.ac.config["bookmark_filename"]
        self._insert_bookmarks(bookmarks=self.bookmarks.load(self.bookmarks_file, ","))
        logger.info("loading bookmarks done")

    def _insert_bookmarks(self, bookmarks: list, silent=False):
        """Method for inserting bookmark data already loaded.

        :param bookmarks: list of bookmark objects
        """

        logger.info("adding %i bookmarks", len(bookmarks))
        for entry in bookmarks:
            item = self.tree.insert(
                "",
                tk.END,
                values=[
                    entry.channel.frequency_as_string,
                    entry.channel.modulation,
                    entry.description,
                    entry.lockout,
                ],
            )

            if entry.lockout == "L":
                self.tree.tag_configure("locked", background="red")
                self.tree.item(item, tags="locked")
            else:
                self.tree.tag_configure("unlocked", background="white")
                self.tree.item(item, tags="unlocked")

    def pop_up_about(self):
        """Describes a pop-up window."""

        # the pop-up needs to be on top
        self.ckb_top.val.set(False)
        panel = tk.Toplevel(self.root)
        center_window(panel, 500, 150)
        text = tk.StringVar()
        label = tk.Label(panel, textvariable=text)
        text.set(self._ABOUT)
        label.pack()

    def buildmenu(self, root):
        """method for building the menu of the main window"""
        logger.info("Building menus")
        menubar = tk.Menu(root)
        appmenu = tk.Menu(menubar, tearoff=0)
        appmenu.add_command(label="About", command=self.pop_up_about)
        appmenu.add_command(label="Quit", command=lambda: shutdown(self))

        bookmarksmenu = tk.Menu(menubar, tearoff=0)
        exportmenu = tk.Menu(menubar, tearoff=0)
        bookmarksmenu.add_command(label="Import", command=self._import_bookmarks)
        bookmarksmenu.add_cascade(label="Export", menu=exportmenu)
        exportmenu.add_command(label="Export GQRX", command=self._export_gqrx)
        exportmenu.add_command(
            label="Export rig-remote", command=self._export_rig_remote
        )

        root.config(menu=menubar)
        menubar.add_cascade(label="Rig Remote", menu=appmenu)
        menubar.add_cascade(label="Bookmarks", menu=bookmarksmenu)
        logger.info("Building menus done")

    @staticmethod
    def _export_panel():
        """handles the popup for selecting the path for saving the file."""

        filename = filedialog.asksaveasfilename(
            initialdir="~/",
            title="Select bookmark file",
            initialfile="bookmarks-export.csv",
            filetypes=(("csv", "*.csv"), ("all files", "*.*")),
        )
        return filename

    def _export_gqrx(self):
        self.bookmarks.export_gqrx(filename=self._export_panel())

    def _export_rig_remote(self):
        self.bookmarks.export_rig_remote(filename=self._export_panel())

    def _toggle_lockout(self, item):
        """Toggle the lockout status of a bookmark."""
        current_lockout = self.tree.set(item, "Lockout")
        new_lockout = "1" if current_lockout == "0" else "0"
        self.tree.set(item, "Lockout", new_lockout)
        self.bookmarks.update_lockout(item, new_lockout)

    def _handle_import_error(self, filename):
        """Handle errors during bookmark import."""
        from tkinter import messagebox
        messagebox.showerror("Error", f"Failed to import bookmarks from {filename}.")

    def _build_ac(self, ac):
        """Build and initialize the GUI widgets.
        :param: ac


        """
        logger.info("building and configuring ui widgets")
        self.master.title("Rig Remote")
        self.master.minsize(800, 244)
        self.pack(fill=tk.BOTH, expand=1, padx=5, pady=5)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # bookmarks list

        self.tree = ttk.Treeview(
            self,
            columns=("frequency", "mode", "description", "lockout"),
            displaycolumns=("frequency", "mode", "description"),
            show="headings",
        )
        _ = ToolTip(self.tree, follow_mouse=1, text="Your bookmark list")

        self.tree.heading("frequency", text="Frequency", anchor=tk.CENTER)
        self.tree.column("frequency", width=100, stretch=True, anchor=tk.CENTER)
        self.tree.heading("mode", text="Mode", anchor=tk.CENTER)
        self.tree.column("mode", width=70, stretch=True, anchor=tk.CENTER)
        self.tree.heading(
            "description",
            text="Description",
        )
        self.tree.column(
            "description",
            stretch=True,
        )
        ysb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        ysb.grid(row=0, column=2, rowspan=6, sticky=tk.NS)
        xsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        xsb.grid(row=6, column=0, sticky=tk.NSEW)
        self.tree.configure(
            yscroll=ysb.set,
        )
        self.tree.grid(row=0, column=0, rowspan=6, sticky=tk.NSEW)

        # vertical separator between bookmarks and comands
        ttk.Frame(self).grid(row=0, column=2, rowspan=5, padx=5)
        # right-side container
        self.rig_config_menu = LabelFrame(self, text="First Rig configuration")
        self.rig_config_menu.grid(row=0, column=3, sticky=tk.NSEW)

        ttk.Label(self.rig_config_menu, text="Hostname:").grid(
            row=1, column=2, sticky=tk.W
        )
        self.params["txt_hostname1"] = ttk.Entry(
            self.rig_config_menu, name="txt_hostname1"
        )
        self.params["txt_hostname1"].grid(
            row=1, column=3, columnspan=2, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["txt_hostname1"], follow_mouse=1, text="Hostname to connect."
        )
        self.params["txt_hostname1"].bind("<Return>", self.process_entry)
        self.params["txt_hostname1"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.rig_config_menu, text="Port:").grid(row=2, column=2, sticky=tk.W)
        self.params["txt_port1"] = ttk.Entry(self.rig_config_menu, name="txt_port1")
        self.params["txt_port1"].grid(row=2, column=3, padx=2, pady=2, sticky=tk.EW)
        _ = ToolTip(self.params["txt_port1"], follow_mouse=1, text="Port to connect.")
        self.params["txt_port1"].bind("<Return>", self.process_entry)
        self.params["txt_port1"].bind("<FocusOut>", self.process_entry)

        # second rig config

        self.rig_config_menu = LabelFrame(self, text="Second Rig configuration")
        self.rig_config_menu.grid(row=0, column=4, sticky=tk.NSEW)

        ttk.Label(self.rig_config_menu, text="Hostname:").grid(
            row=1, column=3, sticky=tk.W
        )
        self.params["txt_hostname2"] = ttk.Entry(
            self.rig_config_menu, name="txt_hostname2"
        )
        self.params["txt_hostname2"].grid(
            row=1, column=4, columnspan=2, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["txt_hostname2"], follow_mouse=1, text="Hostname to connect."
        )
        self.params["txt_hostname2"].bind("<Return>", self.process_entry)
        self.params["txt_hostname2"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.rig_config_menu, text="Port:").grid(row=2, column=3, sticky=tk.W)
        self.params["txt_port2"] = ttk.Entry(self.rig_config_menu, name="txt_port2")
        self.params["txt_port2"].grid(row=2, column=4, padx=2, pady=2, sticky=tk.EW)
        _ = ToolTip(self.params["txt_port2"], follow_mouse=1, text="Port to connect.")
        self.params["txt_port2"].bind("<Return>", self.process_entry)
        self.params["txt_port2"].bind("<FocusOut>", self.process_entry)

        # second rig bookmarking
        # horizontal separator
        ttk.Frame(self.rig_config_menu).grid(row=3, column=1, columnspan=3, pady=5)

        self.rig_control_menu = LabelFrame(self, text="Second Rig Control")
        self.rig_control_menu.grid(row=1, column=4, stick=tk.NSEW)

        ttk.Label(self.rig_control_menu, text="Frequency:").grid(
            row=5, column=1, sticky=tk.W
        )
        self.params["txt_frequency2"] = ttk.Entry(
            self.rig_control_menu, name="txt_frequency2"
        )
        self.params["txt_frequency2"].grid(
            row=5, column=2, columnspan=3, padx=2, pady=2, sticky=tk.W
        )
        _ = ToolTip(
            self.params["txt_frequency2"],
            follow_mouse=1,
            text="Frequency to tune on this rig.",
        )
        ttk.Label(self.rig_control_menu, text="Hz").grid(row=5, column=4, sticky=tk.EW)

        ttk.Label(self.rig_control_menu, text="Mode:").grid(
            row=6, column=1, sticky=tk.W
        )
        self.params["cbb_mode2"] = ttk.Combobox(
            self.rig_control_menu, name="cbb_mode2", width=15
        )
        self.params["cbb_mode2"].grid(
            row=6, column=2, columnspan=3, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["cbb_mode2"],
            follow_mouse=1,
            text="Mode to use for tuning the frequency.",
        )
        self.params["cbb_mode2"]["values"] = [
            mode.value for mode in self.rigctl_two.SUPPORTED_MODULATION_MODES
        ]

        ttk.Label(self.rig_control_menu, text="Description:").grid(
            row=7, column=1, sticky=tk.EW
        )
        self.params["txt_description2"] = ttk.Entry(
            self.rig_control_menu, name="txt_description2"
        )
        self.params["txt_description2"].grid(
            row=7, column=2, columnspan=3, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["txt_description2"],
            follow_mouse=1,
            text="Description of the bookmark.",
        )

        self.btn_add2 = ttk.Button(
            self.rig_control_menu, text="Add", width=7, command=self.cb_second_add
        )
        _ = ToolTip(self.btn_add2, follow_mouse=1, text="Bookmark this frequency.")
        self.btn_add2.grid(row=9, column=2, padx=2, pady=2)

        self.btn_delete2 = ttk.Button(
            self.rig_control_menu, text="Remove", width=7, command=self.cb_delete2
        )
        _ = ToolTip(
            self.btn_delete2,
            follow_mouse=1,
            text="Remove this frequency from bookmarks.",
        )
        self.btn_delete2.grid(row=9, column=1, padx=2, pady=2)

        self.btn_load2 = ttk.Button(
            self.rig_control_menu,
            text="Get",
            width=7,
            command=self.cb_second_get_frequency,
        )
        _ = ToolTip(
            self.btn_load2,
            follow_mouse=1,
            text="Get the frequency and mode from the rig.",
        )
        self.btn_load2.grid(row=8, column=3, padx=2, pady=2)

        self.btn_tune2 = ttk.Button(
            self.rig_control_menu,
            text="Set",
            width=7,
            command=self.cb_second_set_frequency,
        )
        _ = ToolTip(
            self.btn_tune2,
            follow_mouse=1,
            text="Tune the frequency and mode from the " "rig control panel above.",
        )

        self.btn_tune2.grid(row=8, column=1, padx=2, pady=2)

        self.btn_recall2 = ttk.Button(
            self.rig_control_menu,
            text="Recall",
            width=7,
            command=self.cb_second_fill_form,
        )
        _ = ToolTip(
            self.btn_recall2,
            follow_mouse=1,
            text="Recall the frequency and mode from the "
            "bookmarks into this rig control panel.",
        )
        _ = ToolTip(
            self.btn_recall2,
            follow_mouse=1,
            text="Recall the frequency and mode from the "
            "bookmarks into this rig control panel.",
        )

        self.btn_recall2.grid(row=9, column=3, padx=2, pady=2)

        # horizontal separator
        ttk.Frame(self.rig_config_menu).grid(row=3, column=0, columnspan=3, pady=5)

        self.rig_control_menu = LabelFrame(self, text="First Rig Control")
        self.rig_control_menu.grid(row=1, column=3, stick=tk.NSEW)

        ttk.Label(self.rig_control_menu, text="Frequency:").grid(
            row=5, column=0, sticky=tk.W
        )
        self.params["txt_frequency1"] = ttk.Entry(
            self.rig_control_menu, name="txt_frequency1"
        )
        self.params["txt_frequency1"].grid(
            row=5, column=1, columnspan=3, padx=2, pady=2, sticky=tk.W
        )
        _ = ToolTip(
            self.params["txt_frequency1"],
            follow_mouse=1,
            text="Frequency to tune on this rig.",
        )
        ttk.Label(self.rig_control_menu, text="Hz").grid(row=5, column=3, sticky=tk.EW)

        ttk.Label(self.rig_control_menu, text="Mode:").grid(
            row=6, column=0, sticky=tk.W
        )
        self.params["cbb_mode1"] = ttk.Combobox(
            self.rig_control_menu, name="cbb_mode1", width=15
        )
        self.params["cbb_mode1"].grid(
            row=6, column=1, columnspan=3, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["cbb_mode1"],
            follow_mouse=1,
            text="Mode to use for tuning the frequency.",
        )
        self.params["cbb_mode1"]["values"] = [
            mode.value for mode in self.rigctl_one.SUPPORTED_MODULATION_MODES
        ]

        ttk.Label(self.rig_control_menu, text="Description:").grid(
            row=7, column=0, sticky=tk.EW
        )
        self.params["txt_description1"] = ttk.Entry(
            self.rig_control_menu, name="txt_description1"
        )
        self.params["txt_description1"].grid(
            row=7, column=1, columnspan=3, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["txt_description1"],
            follow_mouse=1,
            text="Description of the bookmark.",
        )

        self.btn_add1 = ttk.Button(
            self.rig_control_menu, text="Add", width=7, command=self.cb_first_add
        )
        _ = ToolTip(self.btn_add1, follow_mouse=1, text="Bookmark this frequency.")
        self.btn_add1.grid(row=9, column=1, padx=2, pady=2)

        self.btn_delete1 = ttk.Button(
            self.rig_control_menu, text="Remove", width=7, command=self.cb_delete1
        )
        _ = ToolTip(
            self.btn_delete1, follow_mouse=1, text="Remove the selected bookmark."
        )
        self.btn_delete1.grid(row=9, column=0, padx=2, pady=2)

        self.btn_load1 = ttk.Button(
            self.rig_control_menu,
            text="Get",
            width=7,
            command=self.cb_first_get_frequency,
        )
        _ = ToolTip(
            self.btn_load1,
            follow_mouse=1,
            text="Get the frequency and mode from the rig.",
        )

        self.btn_load1.grid(row=8, column=2, padx=2, pady=2)

        self.btn_tune1 = ttk.Button(
            self.rig_control_menu,
            text="Set",
            width=7,
            command=self.cb_first_set_frequency,
        )
        _ = ToolTip(
            self.btn_tune1,
            follow_mouse=1,
            text="Tune the frequency and mode from the " "rig control panel above.",
        )

        self.btn_tune1.grid(row=8, column=0, padx=2, pady=2)

        self.btn_recall1 = ttk.Button(
            self.rig_control_menu,
            text="Recall",
            width=7,
            command=self.cb_first_fill_form,
        )
        _ = ToolTip(
            self.btn_recall1,
            follow_mouse=1,
            text="Recall the frequency and mode from the "
            "bookmarks into this rig control panel.",
        )

        self.btn_recall1.grid(row=9, column=2, padx=2, pady=2)

        # horizontal separator
        ttk.Frame(self.rig_control_menu).grid(row=9, column=0, columnspan=3, pady=5)

        self.scanning_conf_menu = LabelFrame(self, text="Scanning options")
        self.scanning_conf_menu.grid(row=4, column=3, stick=tk.NSEW)

        ttk.Label(self.scanning_conf_menu, text="Signal level:").grid(
            row=10, column=0, sticky=tk.W
        )
        self.params["txt_sgn_level"] = ttk.Entry(
            self.scanning_conf_menu, name="txt_sgn_level", width=10
        )
        self.params["txt_sgn_level"].grid(
            row=10, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W
        )
        _ = ToolTip(
            self.params["txt_sgn_level"],
            follow_mouse=1,
            text="Signal level to trigger on.",
        )
        self.params["txt_sgn_level"].bind("<Return>", self.process_entry)
        self.params["txt_sgn_level"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.scanning_conf_menu, text=" dBFS").grid(
            row=10, column=2, padx=0, sticky=tk.W
        )

        ttk.Label(self.scanning_conf_menu, text="Delay:").grid(
            row=13, column=0, sticky=tk.W
        )
        self.params["txt_delay"] = ttk.Entry(
            self.scanning_conf_menu, name="txt_delay", width=10
        )
        _ = ToolTip(
            self.params["txt_delay"],
            follow_mouse=1,
            text="Delay after finding a signal.",
        )
        self.params["txt_delay"].grid(
            row=13, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W
        )
        ttk.Label(self.scanning_conf_menu, text=" seconds").grid(
            row=13, padx=0, column=2, sticky=tk.EW
        )
        self.params["txt_delay"].bind("<Return>", self.process_entry)
        self.params["txt_delay"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.scanning_conf_menu, text="Passes:").grid(
            row=14, column=0, sticky=tk.W
        )
        self.params["txt_passes"] = ttk.Entry(
            self.scanning_conf_menu, name="txt_passes", width=10
        )
        self.params["txt_passes"].grid(
            row=14, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W
        )
        _ = ToolTip(self.params["txt_passes"], follow_mouse=1, text="Number of scans.")
        ttk.Label(self.scanning_conf_menu, text="  0=Infinite").grid(
            row=14, padx=0, column=2, sticky=tk.EW
        )
        self.params["txt_passes"].bind("<Return>", self.process_entry)
        self.params["txt_passes"].bind("<FocusOut>", self.process_entry)

        self.cb_wait = tk.BooleanVar()
        self.params["ckb_wait"] = RCCheckbutton(
            self.scanning_conf_menu,
            name="ckb_wait",
            text="Wait",
            onvalue=True,
            offvalue=False,
            variable=self.cb_wait,
        )
        self.params["ckb_wait"].grid(row=15, column=0, columnspan=1, sticky=tk.E)
        _ = ToolTip(
            self.params["ckb_wait"],
            follow_mouse=1,
            text="Waits after having found an active" " frequency.",
        )
        self.params["ckb_wait"].val = self.cb_wait
        self.cb_wait.trace("w", self.process_wait)

        self.cb_record = tk.BooleanVar()
        self.params["ckb_record"] = RCCheckbutton(
            self.scanning_conf_menu,
            name="ckb_record",
            text="Record",
            onvalue=True,
            offvalue=False,
            variable=self.cb_record,
        )
        self.params["ckb_record"].grid(row=15, column=1, columnspan=1, sticky=tk.E)
        _ = ToolTip(
            self.params["ckb_record"],
            follow_mouse=1,
            text="Enable the recording of signal to" " a file.",
        )
        self.params["ckb_record"].val = self.cb_record
        self.cb_record.trace("w", self.process_record)

        self.cb_log = tk.BooleanVar()
        self.params["ckb_log"] = RCCheckbutton(
            self.scanning_conf_menu,
            name="ckb_log",
            text="Log",
            onvalue=True,
            offvalue=False,
            variable=self.cb_log,
        )
        _ = ToolTip(
            self.params["ckb_log"],
            follow_mouse=1,
            text="Logs the activities to a file.",
        )
        self.params["ckb_log"].grid(row=15, column=3, columnspan=1, sticky=tk.E)
        self.params["ckb_log"].val = self.cb_log
        self.cb_log.trace("w", self.process_log)

        self.freq_scanning_menu = LabelFrame(self, text="Frequency scanning")
        self.freq_scanning_menu.grid(
            row=3,
            column=3,
            # rowspan=3,
            stick=tk.NSEW,
        )

        self.freq_scan_toggle = ttk.Button(
            self.freq_scanning_menu,
            text="Start",
            command=self.frequency_toggle,
        )
        _ = ToolTip(
            self.freq_scan_toggle, follow_mouse=1, text="Starts a frequency scan."
        )
        self.freq_scan_toggle.grid(row=17, column=2, padx=2, sticky=tk.W)

        ttk.Label(self.freq_scanning_menu, text="Min/Max:").grid(
            row=12, column=0, sticky=tk.W
        )
        ttk.Label(self.freq_scanning_menu, text="khz").grid(
            row=12, padx=0, column=3, sticky=tk.W
        )
        self.params["txt_range_min"] = ttk.Entry(
            self.freq_scanning_menu, name="txt_range_min", width=8
        )
        self.params["txt_range_min"].grid(
            row=12, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W
        )
        _ = ToolTip(
            self.params["txt_range_min"],
            follow_mouse=1,
            text="Lower bound of the frequency" " band to scan.",
        )
        self.params["txt_range_min"].bind("<Return>", self.process_entry)
        self.params["txt_range_min"].bind("<FocusOut>", self.process_entry)

        self.params["txt_range_max"] = ttk.Entry(
            self.freq_scanning_menu, name="txt_range_max", width=8
        )
        self.params["txt_range_max"].grid(
            row=12, column=2, columnspan=1, padx=0, pady=0, sticky=tk.W
        )
        _ = ToolTip(
            self.params["txt_range_max"],
            follow_mouse=1,
            text="Upper bound of the frequency" " band to scan.",
        )
        self.params["txt_range_max"].bind("<Return>", self.process_entry)
        self.params["txt_range_max"].bind("<FocusOut>", self.process_entry)

        ttk.Label(self.freq_scanning_menu, text="Interval:").grid(
            row=13, column=0, sticky=tk.W
        )
        self.params["txt_interval"] = ttk.Entry(
            self.freq_scanning_menu, name="txt_interval", width=6
        )
        self.params["txt_interval"].grid(
            row=13, column=1, columnspan=1, padx=2, pady=2, sticky=tk.W
        )
        ToolTip(
            self.params["txt_interval"],
            follow_mouse=1,
            text="Tune once every interval khz.",
        )
        ttk.Label(self.freq_scanning_menu, text="Khz").grid(
            row=13, padx=0, column=2, sticky=tk.EW
        )
        self.params["txt_interval"].bind("<Return>", self.process_entry)
        self.params["txt_interval"].bind("<FocusOut>", self.process_entry)

        self.cb_auto_bookmark = tk.BooleanVar()
        self.params["ckb_auto_bookmark"] = RCCheckbutton(
            self.freq_scanning_menu,
            name="ckb_auto_bookmark",
            text="auto bookmark",
            onvalue=True,
            offvalue=False,
            variable=self.cb_auto_bookmark,
        )
        _ = ToolTip(
            self.params["ckb_auto_bookmark"],
            follow_mouse=1,
            text="Bookmark any active frequency" " found.",
        )
        self.params["ckb_auto_bookmark"].grid(row=17, column=0, columnspan=1)
        self.params["ckb_auto_bookmark"].val = self.cb_auto_bookmark
        self.cb_auto_bookmark.trace("w", self.process_auto_bookmark)

        ttk.Label(self.freq_scanning_menu, text="Scan mode:").grid(
            row=16, column=0, sticky=tk.W
        )
        self.params["cbb_freq_modulation"] = ttk.Combobox(
            self.freq_scanning_menu, name="cbb_freq_modulation", width=4
        )
        self.params["cbb_freq_modulation"].grid(
            row=16, column=1, padx=2, pady=2, sticky=tk.EW
        )
        _ = ToolTip(
            self.params["cbb_freq_modulation"],
            follow_mouse=1,
            text="Mode to use for the frequency scan.",
        )
        self.params["cbb_freq_modulation"]["values"] = [
            mode.value for mode in self.rigctl_one.SUPPORTED_MODULATION_MODES
        ]

        ttk.Frame(self.freq_scanning_menu).grid(row=17, column=0, columnspan=3, pady=5)

        self.book_scanning_menu = LabelFrame(self, text="Bookmark scanning")
        self.book_scanning_menu.grid(row=3, column=4, stick=tk.NSEW)

        # horrible horizontal placeholder
        ttk.Label(self.book_scanning_menu, width=8).grid(
            row=17, column=1, sticky=tk.NSEW
        )
        ttk.Label(self.book_scanning_menu, width=8).grid(
            row=17, column=2, sticky=tk.NSEW
        )

        ttk.Label(self.book_scanning_menu, width=8).grid(
            row=17, column=3, sticky=tk.NSEW
        )

        self.book_scan_toggle = ttk.Button(
            self.book_scanning_menu,
            text="Start",
            command=self.bookmark_toggle,
        )
        _ = ToolTip(
            self.book_scan_toggle, follow_mouse=1, text="Starts a bookmark scan."
        )
        self.book_scan_toggle.grid(row=18, column=1, columnspan=1, padx=2, sticky=tk.W)

        self.book_lockout = ttk.Button(
            self.book_scanning_menu,
            text="Lock",
            command=self.bookmark_lockout,
        )
        _ = ToolTip(
            self.book_lockout, follow_mouse=1, text="Toggle skipping selected bookmark."
        )
        self.book_lockout.grid(row=18, column=3, columnspan=1, padx=2, sticky=tk.W)

        self.sync_menu = LabelFrame(self, text="Rig Frequency Sync")
        ttk.Frame(self.sync_menu).grid(row=19, column=0, columnspan=3, pady=5)

        self.sync_menu.grid(row=4, column=4, stick=tk.NSEW)

        # horrible horizontal placeholder

        ttk.Label(self.sync_menu, width=8).grid(row=20, column=2, sticky=tk.NSEW)

        ttk.Label(self.sync_menu, width=8).grid(row=21, column=3, sticky=tk.NSEW)

        self.sync = ttk.Button(
            self.sync_menu,
            text="Start",
            command=self.sync_toggle,
        )
        _ = ToolTip(
            self.sync,
            follow_mouse=1,
            text="Keeps in sync the "
            "frequency/mode. The first rig is "
            "source, the second is the destination.",
        )
        self.sync.grid(row=21, column=1, columnspan=1, padx=2, sticky=tk.W)
        # horizontal separator
        ttk.Frame(self.book_scanning_menu).grid(
            row=22, column=0, columnspan=3, rowspan=1, pady=5
        )

        self.control_menu = LabelFrame(self, text="Options")

        self.control_menu.grid(row=5, column=3, columnspan=2, stick=tk.NSEW)

        self.cb_top = tk.BooleanVar()
        self.ckb_top = RCCheckbutton(
            self.control_menu,
            text="Always on top",
            onvalue=True,
            offvalue=False,
            variable=self.cb_top,
        )
        self.ckb_top.grid(row=23, column=2, columnspan=1, padx=2, sticky=tk.EW)
        _ = ToolTip(self.ckb_top, follow_mouse=1, text="This window is always on top.")
        self.ckb_top.val = self.cb_top
        self.cb_top.trace("w", self.toggle_cb_top)

        self.cb_save_exit = tk.BooleanVar()
        self.ckb_save_exit = RCCheckbutton(
            self.control_menu,
            text="Save on exit",
            onvalue=True,
            offvalue=False,
            variable=self.cb_save_exit,
        )
        self.ckb_save_exit.grid(row=23, column=1, columnspan=1, padx=2, sticky=tk.EW)
        _ = ToolTip(self.ckb_save_exit, follow_mouse=1, text="Save setting on exit.")
        self.ckb_save_exit.val = self.cb_save_exit

        # horizontal separator
        ttk.Frame(self.control_menu).grid(row=24, column=0, columnspan=3, pady=5)

        logger.info("building and configuring ui widgets done")

    def focus_set(self, event):
        """Give focus to screen object in click event. Used to
        force <FocusOut> callbacks.
        """

        if not isinstance(event.widget, str):
            event.widget.focus_set()

    def _configure_rigs(self) -> None:
        if not self.rigctl_one:
            logger.info("rig configuration: rig 1")
            self.rigctl_one = RigCtl(self.ac.rig_endpoints[0])
            logger.info("rig configuration rig 1 done")
        if not self.rigctl_two:
            logger.info("rig configuration: rig 2")
            self.rigctl_two = RigCtl(self.ac.rig_endpoints[1])
            logger.info("rig configuration rig 2 done")

    def apply_config(self, silent=False)->None:
        """Applies the config to the UI.

        :param silent: suppress messagebox
        :raises : none
        :returns : none
        """
        eflag = False

        self.params["txt_hostname1"].insert(0, self.ac.rig_endpoints[0].hostname)
        self.params["txt_hostname2"].insert(0, self.ac.rig_endpoints[1].hostname)

        # Test positive integer values
        for key in (
            "port1",
            "port2",
            "interval",
            "delay",
            "passes",
            "range_min",
            "range_max",
        ):
            ekey = "txt_" + key
            if str.isdigit(self.ac.config[key].replace(",", "")):
                self.params[ekey].insert(0, self.ac.config[key])
            else:
                self.params[ekey].insert(0, self.ac.DEFAULT_CONFIG[key])
                eflag = True
        # Test integer values
        try:
            int(self.ac.config["sgn_level"])
        except ValueError:
            self.params["txt_sgn_level"].insert(0, self.ac.DEFAULT_CONFIG["sgn_level"])
            eflag = True
        else:
            self.params["txt_sgn_level"].insert(0, self.ac.config["sgn_level"])
        if eflag:
            if not silent:
                messagebox.showerror(
                    "Config File Error",
                    "One (or more) "
                    "of the values in the config file was "
                    "invalid, and the default was used "
                    "instead.",
                    parent=self,
                )
        self.params["ckb_auto_bookmark"].set_str_val(
            self.ac.config["auto_bookmark"].lower()
        )
        try:
            self.params["ckb_record"].set_str_val(self.ac.config["record"].lower())
            self.params["ckb_wait"].set_str_val(self.ac.config["wait"].lower())
            self.params["ckb_log"].set_str_val(self.ac.config["log"].lower())
            self.ckb_save_exit.set_str_val(self.ac.config["save_exit"].lower())
        except KeyError:
            pass
        if self.ac.config["always_on_top"].lower() == "true":
            if self.ckb_top.is_checked() is False:
                self.ckb_top.invoke()

        self._configure_rigs()
        # Here we create a copy of the params dict to use when
        # checking validity of new input
        for key in self.params:
            if self.params[key].winfo_class() == "TEntry":
                self.params_last_content[key] = self.params[key].get()
            elif self.params[key].winfo_class() == "TCheckbutton":
                self.params_last_content[key] = self.params[key].is_checked()

    def sync_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        action = self.sync.cget("text").lower()
        self.sync.config(text=next(icycle))
        self._sync(action)

    def _sync(self, action):
        if self.scan_thread:
            self.sync.config(text="Start")
            return

        if action.lower() not in self._SUPPORTED_SYNC_ACTIONS:
            logger.error("Provided action:%s", action)
            logger.error("Supported " "actions:%s", self._SUPPORTED_SYNC_ACTIONS)
            raise UnsupportedSyncConfigError

        if action.lower() == "stop" and self.sync_thread is not None:
            # there is a sync ongoing and we want to terminate it

            self.syncing.terminate()
            self.sync_thread.join()
            self.sync_thread = None
            return

        if action.lower() == "start" and self.sync_thread is not None:
            # we are already scanning, so another start is ignored
            return

        if action.lower() == "stop" and self.sync_thread is None:
            # we already stopped scanning, another stop is ignored

            return

        if action.lower() == "start" and self.sync_thread is None:
            # there is no ongoing scan task and we want to start one

            try:
                task = SyncTask(
                    syncq=self.syncq,
                    src_rig=RigCtl(self.ac.rig_endpoints[0]),
                    dst_rig=RigCtl(self.ac.rig_endpoints[1]),
                )
            except UnsupportedSyncConfigError:
                messagebox.showerror(
                    "Sync error", "Hostname/port of both rigs " "must be specified"
                )
                self.sync_toggle()
                return
            self.syncing = Syncing()
            self.sync_thread = threading.Thread(target=self.syncing.sync, args=(task,))
            self.sync_thread.start()
            self.after(0, self.check_syncthread)

    def bookmark_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle bookmark scan Start/Stop button, changing label text as
        appropriate.
        """

        if self.scan_mode is None or self.scan_mode == "bookmarks":
            action = self.book_scan_toggle.cget("text").lower()
            self.book_scan_toggle.config(text=next(icycle))

            self._scan(
                scan_mode="bookmarks",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].get(),
            )

    def bookmark_lockout(self, icycle=itertools.cycle(["L", "O"])):
        """Toggle lockout of selected bookmark."""

        if self.selected_bookmark is None:
            # will use this in future to support "current scan" lockout
            return
        else:
            values = list((self.tree.item(self.selected_bookmark, "values")))
            if values[BM.lockout] == "L":
                values[BM.lockout] = "O"
            else:
                values[BM.lockout] = "L"
            self.tree.item(self.selected_bookmark, values=values)
            self.bookmarks.bookmark_bg_tag(self.selected_bookmark, values[BM.lockout])

    def frequency_toggle(self, icycle=itertools.cycle(["Stop", "Start"])):
        """Toggle frequency scan Start/Stop button, changing label text as
        appropriate.
        """

        if self.params["cbb_freq_modulation"].get() == "":
            messagebox.showerror(
                "Error", "You must select a mode for " "performing a frequency scan."
            )
            return
        if not self.scan_mode or self.scan_mode == "frequency":
            action = self.freq_scan_toggle.cget("text").lower()
            self.freq_scan_toggle.config(text=next(icycle))
            self._scan(
                scan_mode="frequency",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].get(),
            )

    def _process_port_entry(self, event_value, number, silent=False):
        """Process event for port number entry

        :param event_value: new port number
        :param silent: suppress messagebox
        :return:
        """
        try:
            self.ac.rig_endpoints[number - 1].set_port(event_value)
        except ValueError:
            if not silent:
                messagebox.showerror(
                    "Error",
                    "Invalid input value in "
                    "port. Must be integer and greater than "
                    "1024",
                )
            return

    def _process_hostname_entry(self, event_value, number, silent=False):
        """Process event for hostname entry

        :param event_value: new hostname
        :param silent: suppress messagebox
        :return:
        """

        try:
            self.ac.rig_endpoints[number - 1].set_hostname(event_value)
        except ValueError:
            if not silent:
                messagebox.showerror("Error", "Invalid Hostname")
            return

    def process_entry(self, event, silent=False):
        """Process a change in an entry widget. Check validity of
        numeric data. If empty field, offer the default or return to
        edit. If not valid, display a message and reset
        the widget to its previous state. Otherwise push the
        change onto the queue.

        :param event: event dict generated by widget handler
        :param silent: suppress messagebox

        """

        event_name = str(event.widget).split(".")[-1]
        event_value = event.widget.get()
        ekey = str(event_name.split("_", 1)[1])
        if (event_value == "") or event_value.isspace():
            if not silent:
                answer = messagebox.askyesno(
                    "Error",
                    "{} must have a value " "entered. Use the " "default?".format(ekey),
                )
            else:
                answer = True  # default answer for testing
            if answer:
                event_value = self.ac.DEFAULT_CONFIG[ekey]
                event.widget.delete(0, "end")
                event.widget.insert(0, event_value)
                self.params_last_content[event_name] = event_value
            else:
                if (self.params_last_content[event_name] != "") and (
                    not (self.params_last_content[event_name].isspace())
                ):
                    event.widget.delete(0, "end")
                    event.widget.insert(0, self.params_last_content[event_name])
                else:
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

        try:
            event_value_int = int(event.widget.get().replace(",", ""))
        except ValueError:
            if not silent:
                messagebox.showerror("Error", "Invalid input value in %s" % event_name)
            event.widget.focus_set()
            return
        self.params_last_content[event_name] = event_value
        if self.scan_thread is not None:
            event_list = (event_name, event_value_int)
            self.scanq.send_event_update(event_list)

    def process_wait(self, *args):
        """Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored

        """
        event_list = ("ckb_wait", self.cb_wait.get())
        self._process_checkbutton(event_list)

    def process_record(self, *args):
        """Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored

        """

        event_list = ("ckb_record", self.cb_record.get())
        self._process_checkbutton(event_list)

    def process_log(self, *args):
        """Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored

        """

        event_list = ("ckb_log", self.cb_log.get())
        self._process_checkbutton(event_list)

    def process_auto_bookmark(self, *args):
        """Methods to handle checkbutton updates, it wraps around
        process_checkbutton.

        :param *args: ignored

        """

        event_list = ("ckb_auto_bookmark", self.cb_auto_bookmark.get())
        self._process_checkbutton(event_list)

    def _process_checkbutton(self, event_list):
        """Take the event_list generated by caller and push it on the queue.

        :param event_list: name of param to update, value of param

        """
        if self.scan_thread is not None:
            self.scanq.send_event_update(event_list)
            self.params_last_content[event_list[0]] = event_list[1]

    def check_scanthread(self):
        """Check if the scan thread has sent us a termination signal."""

        if self.scanq.check_end_of_scan():
            if self.scan_mode == "frequency":
                self.frequency_toggle()
            else:
                self.bookmark_toggle()
        else:
            if self.scan_thread is not None:
                self.after(self._UI_EVENT_TIMER_DELAY, self.check_scanthread)

    def check_syncthread(self):
        if not self.syncq.check_end_of_sync():
            # self.sync_toggle()
            #        else:
            if self.sync_thread is not None:
                self.after(self._UI_EVENT_TIMER_DELAY, self.check_syncthread)

    def _scan(
        self, scan_mode: str, action: str, frequency_modulation: str, silent=False
    ):
        """Wrapper around the scanning class instance. Creates the task
        object and issues the scan.

        :param scan_mode: bookmark or frequency
        :param frequency_modulation: am/fm...
        :raises: NotImplementedError if action different than "start" is passed

        """
        logger.info("scan action %s with scan mode %s.", action, scan_mode)
        if action.lower() not in self._SUPPORTED_SCANNING_ACTIONS:
            logger.error("Provided action: %s", action)
            logger.error("Supported " "actions: %s", self._SUPPORTED_SCANNING_ACTIONS)
            raise UnsupportedScanningConfigError

        if self.sync_thread:
            if scan_mode == "bookmarks":
                self.book_scan_toggle.config(text="Start")
            else:
                self.freq_scan_toggle.config(text="Start")
            return

        if action.lower() == "stop" and self.scan_thread is not None:
            # there is a scan ongoing and we want to terminate it
            logger.info("Stopping ongoing scan")
            self.scanning.terminate()
            self.scan_thread.join()
            self.scan_thread = None
            if scan_mode.lower() == "frequency":
                logger.info("adding collected bookmarks...")
                self._add_new_bookmarks(self.new_bookmark_list)
                self.new_bookmark_list = []
            self.scan_mode = None
            return

        if action.lower() == "start" and self.scan_thread is not None:
            # we are already scanning, so another start is ignored
            logger.info(
                "Ignoring scan start command as there is already an ongping scan"
            )
            return

        if action.lower() == "stop" and self.scan_thread is None:
            # we already stopped scanning, another stop is ignored
            logger.info("Ignoring scan stop command as there is no ongoing scan")
            return

        if action.lower() == "start" and self.scan_thread is None:
            # there is no ongoing scan task and we want to start one
            if len(self.tree.get_children()) == 0 and scan_mode == "bookmarks":
                if not silent:
                    messagebox.showerror("Error", "No bookmarks to scan.")
                self.bookmark_toggle()
            else:
                logger.info("Frequency scan start command accepted")
                task = ScanningTask(
                    frequency_modulation=frequency_modulation,
                    scan_mode=scan_mode,
                    new_bookmark_list=self.new_bookmark_list,
                    range_min=khertz_to_hertz(
                        int(self.params["txt_range_min"].get().replace(",", ""))
                    ),
                    range_max=khertz_to_hertz(
                        int(self.params["txt_range_max"].get().replace(",", ""))
                    ),
                    interval=int(self.params["txt_interval"].get()),
                    delay=int(self.params["txt_delay"].get()),
                    passes=int(self.params["txt_passes"].get()),
                    sgn_level=int(self.params["txt_sgn_level"].get()),
                    wait=self.params["ckb_wait"].is_checked(),
                    record=self.params["ckb_record"].is_checked(),
                    auto_bookmark=self.params["ckb_auto_bookmark"].is_checked(),
                    log=self.params["ckb_log"].is_checked(),
                    bookmarks=self._extract_bookmarks(),
                )

                self.scanning = Scanning(
                    scan_queue=self.scanq,
                    log_filename=self.log_file,
                    rigctl=self.rigctl_one,
                )
                self.scan_thread = threading.Thread(
                    target=self.scanning.scan, args=(task,)
                )
                self.scan_thread.start()
                self.after(0, self.check_scanthread)

    @staticmethod
    def _new_activity_message(nbl):
        """Provides a little formatting from the new bookmark list.

        :param nbl: new bookmark list
        :raises : none
        :returns message: message to be printed in an info messagebox.
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


        """

        if source not in (1, 2):
            logger.error("The rig number %s is not supported", source)
            raise NotImplementedError

        frequency = "txt_frequency{}".format(source)
        mode = "cbb_mode{}".format(source)
        description = "txt_description{}".format(source)

        self.params[frequency].delete(0, tk.END)
        self.params[description].delete(0, tk.END)
        self.params[mode].delete(0, tk.END)

    def _add_new_bookmarks(self, nbl):
        """Fill in the data, calls uses cb_add() and calls clear_form.

        :param nbl: list of new frequencies to bookmark
        """
        self._clear_form(1)
        for nb in nbl:
            self.params["txt_description1"].insert(
                0, "activity on {}".format(nb["time"])
            )
            self.params["txt_frequency1"].insert(0, str(nb["freq"]).strip())
            self.params["cbb_mode1"].insert(0, nb["mode"])
            # adding bookmark to the list
            self.cb_first_add(True)
            self._clear_form(1)

    def toggle_cb_top(self, *args):
        """Set window property to be always on top.

        :param: none


        """

        self.master.attributes("-topmost", self.ckb_top.val.get())

    def cb_second_get_frequency(self):
        """Wrapper around cb_set_frequency."""
        self.cb_get_frequency(self.rigctl_two)

    def cb_first_get_frequency(self):
        """Wrapper around cb_set_frequency."""
        self.cb_get_frequency(self.rigctl_one)

    def cb_get_frequency(self, rig_target, silent=False):
        """Get current rig frequency and mode.

        :param silent: suppress messagebox
        """

        # clear fields
        self._clear_form(rig_target.target.number)
        try:
            frequency = rig_target.get_frequency()
            mode = rig_target.get_mode()
            # update fields
            txt_frequency = "txt_frequency{}".format(rig_target.target.number)
            self.params[txt_frequency].insert(0, frequency)
            cbb_mode = "cbb_mode{}".format(rig_target.target.number)
            self.params[cbb_mode].insert(0, mode)
        except Exception as err:
            if not silent:
                messagebox.showerror(
                    "Error", "Could not connect to rig.\n%s" % err, parent=self
                )

    def cb_second_set_frequency(self):
        """Wrapper around cb_set_frequency."""
        self.cb_set_frequency(self.rigctl_two, event=None)

    def cb_first_set_frequency(self):
        """Wrapper around cb_set_frequency."""

        self.cb_set_frequency(self.rigctl_one, event=None)

    def cb_set_frequency(self, rig_target, event, silent=False):
        """Set the rig frequency and mode.

        :param event: not used?
        :param rig_target: rig we are referring to (hostname and port)
        :param silent: suppress messagebox


        """
        txt_frequency = "txt_frequency{}".format(rig_target.target.number)
        cbb_mode = "cbb_mode{}".format(rig_target.target.number)
        frequency = self.params[txt_frequency].get().replace(",", "")
        mode = str(self.params[cbb_mode].get())
        try:
            rig_target.set_frequency(frequency)
            rig_target.set_mode(mode)
        except Exception as err:
            if not silent and (frequency != "" or mode != ""):
                messagebox.showerror(
                    "Error", "Could not set frequency.\n%s" % err, parent=self
                )
            if not silent and (frequency == "" or mode == ""):
                messagebox.showerror(
                    "Error", "Please provide frequency and mode.", parent=self
                )

    def cb_second_fill_form(self):
        """Wrapper around cb_set_frequency."""

        self.cb_autofill_form(2, event=None)

    def cb_first_fill_form(self):
        """Wrapper around cb_set_frequency."""

        self.cb_autofill_form(1, event=None)

    def cb_autofill_form(self, rig_number, event):
        """Auto-fill bookmark fields with details
        of currently selected Treeview entry.

        :param event: not used?
        """

        self.selected_bookmark = self.tree.focus()
        values = self.tree.item(self.selected_bookmark).get("values")
        self._clear_form(rig_number)

        cbb_mode = "cbb_mode{}".format(rig_number)
        txt_frequency = "txt_frequency{}".format(rig_number)
        txt_description = "txt_description{}".format(rig_number)
        self.params[cbb_mode].insert(0, values[1])
        self.params[txt_frequency].insert(0, values[0])
        self.params[txt_description].insert(0, values[2])

    def build_control_source(self, number, silent=False):
        if number not in (1, 2):
            logger.error("The rig number %i is not supported", number)
            raise NotImplementedError

        control_source = {}
        freq = "txt_frequency{}".format(number)
        mode = "cbb_mode{}".format(number)
        description = "txt_description{}".format(number)
        control_source["frequency"] = self.params[freq].get()
        try:
            int(control_source["frequency"])
        except (ValueError, TypeError):
            if not silent:
                messagebox.showerror(
                    "Error",
                    "Invalid value in Frequency field." "Note: '.' isn't allowed.",
                )
                self.params[freq].focus_set()
            return
        control_source["mode"] = self.params[mode].get()
        control_source["description"] = self.params[description].get()
        return control_source

    def cb_second_add(self, silent=False):
        """Wrapper around cb_add."""

        control_source = self.build_control_source(2)
        self.cb_add(control_source, silent)

    def cb_first_add(self, silent=False):
        """Wrapper around cb_add."""

        control_source = self.build_control_source(1)
        self.cb_add(control_source, silent)

    def cb_add(self, control_source, silent=False):
        """Add frequency to tree and saves the bookmarks.

        :param: none


        """
        if not control_source["description"]:
            if not silent:
                messagebox.showerror("Error", "Please add a description")
            return
        bookmark = bookmark_factory(
            input_frequency=int(control_source["frequency"]),
            modulation=control_source["mode"],
            description=control_source["description"],
            lockout="0",
        )

        # find where to insert (insertion sort)
        idx = tk.END
        for item in self.tree.get_children():
            uni_curr_freq = bookmark.channel.frequency
            curr_freq = uni_curr_freq
            if bookmark.channel.frequency < curr_freq:
                idx = self.tree.index(item)
                break
        if self.bookmarks.add_bookmark(bookmark):
            item = self.tree.insert(
                "",
                idx,
                values=[
                    bookmark.channel.frequency,
                    bookmark.channel.modulation,
                    bookmark.description,
                    bookmark.lockout,
                ],
            )

        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        # save
        self.bookmarks.save(
            bookmarks_file=self.bookmarks_file
        )

    def _extract_bookmarks(self) -> list:
        bookmark_list = []
        for item in self.tree.get_children():
            bookmark_list.append(self._get_bookmark_from_item(item))
        return bookmark_list

    def cb_delete2(self):
        """wrapper around cb_delete"""

        self.cb_delete(2)

    def cb_delete1(self):
        """wrapper around cb_delete"""

        self.cb_delete(1)

    def cb_delete(self, source:int):
        """Delete frequency from tree.

        :param: none


        """

        item = self.tree.focus()
        if not item:
            return
        self.bookmarks.delete_bookmark(self._get_bookmark_from_item(item))
        self.tree.delete(item)
        # save
        self.bookmarks.save(
            bookmarks_file=self.bookmarks_file)
        self._clear_form(source)

    def _get_bookmark_from_item(self, item) -> Bookmark:
        values = self.tree.item(item).get("values")
        return bookmark_factory(
            input_frequency=int(values[0].replace(",", "")),
            modulation=values[1],
            description=values[2],
            lockout=str(values[3]),
        )


class ToolTip:
    def __init__(self, master, text="", delay=1500, **opts):
        self.master = master
        self._opts = {
            "anchor": "center",
            "bd": 1,
            "bg": "lightyellow",
            "delay": delay,
            "fg": "black",
            "follow_mouse": 0,
            "font": None,
            "justify": "left",
            "padx": 4,
            "pady": 2,
            "relief": "solid",
            "state": "normal",
            "text": text,
            "textvariable": None,
            "width": 0,
            "wraplength": 150,
        }
        self.configure(**opts)
        self._tipwindow = None
        self._id = None
        self._id1 = self.master.bind("<Enter>", self.enter, "+")
        self._id2 = self.master.bind("<Leave>", self.leave, "+")
        self._id3 = self.master.bind("<ButtonPress>", self.leave, "+")
        self._follow_mouse = 0
        if self._opts["follow_mouse"]:
            self._id4 = self.master.bind("<Motion>", self.motion, "+")
            self._follow_mouse = 1

    def configure(self, **opts):
        for key in opts:
            if key in self._opts:
                self._opts[key] = opts[key]
            else:
                KeyError = 'KeyError: Unknown option: "%s"' % key
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
        if self._opts["state"] == "disabled":
            return
        self._id = self.master.after(self._opts["delay"], self._show)

    def _unschedule(self):
        id = self._id
        self._id = None
        if id:
            self.master.after_cancel(id)

    def _show(self):
        if self._opts["state"] == "disabled":
            self._unschedule()
            return
        if not self._tipwindow:
            self._tipwindow = tw = tk.Toplevel(self.master)
            # hide the window until we know the geometry
            tw.withdraw()
            tw.wm_overrideredirect(1)

            if tw.tk.call("tk", "windowingsystem") == "aqua":
                tw.tk.call(
                    "::tk::unsupported::MacWindowStyle", "style", tw._w, "help", "none"
                )

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

    # ------these methods might be overridden in derived classes:
    def coords(self):
        # The tip window must be completely outside the master widget;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        # or we take care that the mouse pointer is always
        # outside the tipwindow :-)

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
        for opt in ("delay", "follow_mouse", "state"):
            del opts[opt]
        label = tk.Label(self._tipwindow, **opts)
        label.pack()


class RCCheckbutton(ttk.Checkbutton):
    """
    RCCheckbutton is derived from ttk.Checkbutton, and adds an
    "is_checked" method to simplify checking instance's state, and
    new methods to return string state values for config file.
    """

    def __init__(self, *args, **kwargs):
        self.var = kwargs.get("variable", tk.BooleanVar())
        kwargs["variable"] = self.var
        ttk.Checkbutton.__init__(self, *args, **kwargs)

    def is_checked(self):
        return self.var.get()

    def get_str_val(self)->str:
        if self.is_checked():
            return "true"
        else:
            return "false"

    def set_str_val(self, value):
        if value.lower() in ("true", "t"):
            self.var.set(True)
        else:
            self.var.set(False)

import logging
import threading

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QGroupBox,
    QMessageBox, QApplication, 
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QBrush

from rig_remote.constants import RIG_COUNT
from rig_remote.exceptions import (
    UnsupportedScanningConfigError,
    UnsupportedSyncConfigError,
)
from rig_remote.bookmarksmanager import BookmarksManager, bookmark_factory
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import Scanning
from rig_remote.syncing import Syncing, SyncTask
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.models.bookmark import Bookmark
from rig_remote.queue_comms import QueueComms
from rig_remote.utility import (
    shutdown,
)
from rig_remote.stmessenger import STMessenger
from rig_remote.app_config import AppConfig

logger = logging.getLogger(__name__)


class RigRemote(QMainWindow):
    """Remote application that interacts with the rig using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.
    """

    _SUPPORTED_SYNC_ACTIONS = ("start", "stop")
    _SUPPORTED_SCANNING_ACTIONS = ("start", "stop")
    _UI_EVENT_TIMER_DELAY = 1000
    _ORDINAL_NUMBERS = ["First", "Second", "Third", "Fourth"]  # If you want more rigs, add more ordinals here

    _ABOUT = """
    Rig remote is a software for controlling a rig
    via tcp/ip and RigCtl.

    * GitHub: https://github.com/Marzona/rig-remote
    * Project wiki: https://github.com/Marzona/rig-remote/wiki
    """

    def __init__(self, app_config: AppConfig):
        super().__init__()
        self.ac = app_config
        
        # Initialize attributes
        self.params = {}
        self.params_last_content = {}
        self.alt_files = {}
        self.bookmarks = BookmarksManager()
        self.scan_thread = None
        self.sync_thread = None
        self.scan_mode = None
        self.scanning = None
        self.selected_bookmark = None
        self.scanq = STMessenger(queuecomms=QueueComms())
        self.syncq = STMessenger(queuecomms=QueueComms())
        self.new_bookmark_list = []
        self.rigctl = [None] * RIG_COUNT
        
        self._build_ui()
        self._load_bookmarks()
        
        self.apply_config(app_config, silent=True)

    def _build_ui(self):
        """Build the entire UI"""
        self.setWindowTitle("Rig Remote")
        self.setMinimumSize(800, 244)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QGridLayout(central_widget)

        self._build_tree_view(main_layout)
        for i in range(RIG_COUNT):
            self._build_rig(main_layout, i+1)
        self._build_scanning_options(main_layout)
        self._build_frequency_scanning(main_layout)
        self._build_bookmark_scanning(main_layout)
        self._build_sync_menu(main_layout)
        self._build_control_menu(main_layout)
        self._build_menu()

    def _build_tree_view(self, layout):
        """Build the bookmarks tree view"""
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Frequency", "Mode", "Description"])
        self.tree.setColumnWidth(0, 100)
        self.tree.setColumnWidth(1, 70)
        self.tree.setToolTip("Your bookmark list")
        layout.addWidget(self.tree, 0, 0, 6, 1)

    def _build_rig(self, layout: QGridLayout, rig_number: int):
        if rig_number < 0 or rig_number >= len(self._ORDINAL_NUMBERS) + 1:
            raise ValueError(f"Invalid rig number {rig_number}")
        
        self._build_rig_config(layout, rig_number)
        self._build_rig_control(layout, rig_number)
        
    def _build_rig_config(self, layout: QGridLayout, rig_number: int):      
        group = QGroupBox(f"{self._ORDINAL_NUMBERS[rig_number - 1]} Rig configuration")
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Hostname:"), 0, 0)
        txt_hostname = f"txt_hostname{rig_number}"
        self.params[txt_hostname] = QLineEdit()
        self.params[txt_hostname].setToolTip("Hostname to connect.")
        self.params[txt_hostname].editingFinished.connect(
            lambda: self.process_entry_wrapper(txt_hostname)
        )
        grid.addWidget(self.params[txt_hostname], 0, 1, 1, 2)
        
        grid.addWidget(QLabel("Port:"), 1, 0)
        txt_port = f"txt_port{rig_number}"
        self.params[txt_port] = QLineEdit()
        self.params[txt_port].setToolTip("Port to connect.")
        self.params[txt_port].editingFinished.connect(
            lambda: self.process_entry_wrapper(txt_port)
        )
        grid.addWidget(self.params[txt_port], 1, 1)
        
        group.setLayout(grid)
        layout.addWidget(group, 0, 2 + rig_number)

    def _build_rig_control(self, layout: QGridLayout, rig_number: int):
        group = QGroupBox(f"{self._ORDINAL_NUMBERS[rig_number - 1]} Rig Control")
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Frequency:"), 0, 0)
        txt_frequency = f"txt_frequency{rig_number}"
        self.params[txt_frequency] = QLineEdit()
        self.params[txt_frequency].setToolTip("Frequency to tune on this rig.")
        grid.addWidget(self.params[txt_frequency], 0, 1, 1, 3)
        grid.addWidget(QLabel("Hz"), 0, 3)
        
        grid.addWidget(QLabel("Mode:"), 1, 0)
        cbb_mode = f"cbb_mode{rig_number}"
        self.params[cbb_mode] = QComboBox()
        self.params[cbb_mode].addItems(CBB_MODES)
        self.params[cbb_mode].setToolTip("Mode to use for tuning the frequency.")
        grid.addWidget(self.params[cbb_mode], 1, 1, 1, 3)
        
        grid.addWidget(QLabel("Description:"), 2, 0)
        txt_description = f"txt_description{rig_number}"
        self.params[txt_description] = QLineEdit()
        self.params[txt_description].setToolTip("Description of the bookmark.")
        grid.addWidget(self.params[txt_description], 2, 1, 1, 3)
        
        self.btn_tune1 = QPushButton("Set")
        self.btn_tune1.setToolTip("Tune the frequency and mode from the rig control panel above.")
        self.btn_tune1.clicked.connect(
            lambda: self.cb_set_frequency(self.rigctl[rig_number-1].target, None)
        )
        grid.addWidget(self.btn_tune1, 3, 0)

        self.btn_load1 = QPushButton("Get")
        self.btn_load1.setToolTip("Get the frequency and mode from the rig.")
        self.btn_load1.clicked.connect(
            lambda: self.cb_get_frequency(self.rigctl[rig_number-1].target)
        )
        grid.addWidget(self.btn_load1, 3, 2)

        
        self.btn_delete1 = QPushButton("Remove")
        self.btn_delete1.setToolTip("Remove the selected bookmark.")
        self.btn_delete1.clicked.connect(
            lambda: self.cb_delete(rig_number)
        )
        grid.addWidget(self.btn_delete1, 4, 0)
        
        self.btn_add1 = QPushButton("Add")
        self.btn_add1.setToolTip("Bookmark this frequency.")
        self.btn_add1.clicked.connect(
            lambda: self.cb_add(rig_number)
        )
        grid.addWidget(self.btn_add1, 4, 1)
        
        self.btn_recall1 = QPushButton("Recall")
        self.btn_recall1.setToolTip("Recall the frequency and mode from the bookmarks into this rig control panel.")
        self.btn_recall1.clicked.connect(
            lambda: self.cb_autofill_form(rig_number, None)
        )
        grid.addWidget(self.btn_recall1, 4, 2)
        
        group.setLayout(grid)
        layout.addWidget(group, 1, 2+rig_number)

    def _build_scanning_options(self, layout):
        """Build scanning options group"""
        group = QGroupBox("Scanning options")
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Signal level:"), 0, 0)
        self.params["txt_sgn_level"] = QLineEdit()
        self.params["txt_sgn_level"].setToolTip("Signal level to trigger on.")
        self.params["txt_sgn_level"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_sgn_level")
        )
        grid.addWidget(self.params["txt_sgn_level"], 0, 1)
        grid.addWidget(QLabel("dBFS"), 0, 2)
        
        grid.addWidget(QLabel("Delay:"), 1, 0)
        self.params["txt_delay"] = QLineEdit()
        self.params["txt_delay"].setToolTip("Delay after finding a signal.")
        self.params["txt_delay"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_delay")
        )
        grid.addWidget(self.params["txt_delay"], 1, 1)
        grid.addWidget(QLabel("seconds"), 1, 2)
        
        grid.addWidget(QLabel("Passes:"), 2, 0)
        self.params["txt_passes"] = QLineEdit()
        self.params["txt_passes"].setToolTip("Number of scans.")
        self.params["txt_passes"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_passes")
        )
        grid.addWidget(self.params["txt_passes"], 2, 1)
        grid.addWidget(QLabel("0=Infinite"), 2, 2)
        
        self.params["ckb_wait"] = QCheckBox("Wait")
        self.params["ckb_wait"].setToolTip("Waits after having found an active frequency.")
        self.params["ckb_wait"].stateChanged.connect(self.process_wait)
        grid.addWidget(self.params["ckb_wait"], 3, 0)
        
        self.params["ckb_record"] = QCheckBox("Record")
        self.params["ckb_record"].setToolTip("Enable the recording of signal to a file.")
        self.params["ckb_record"].stateChanged.connect(self.process_record)
        grid.addWidget(self.params["ckb_record"], 3, 1)
        
        self.params["ckb_log"] = QCheckBox("Log")
        self.params["ckb_log"].setToolTip("Logs the activities to a file.")
        self.params["ckb_log"].stateChanged.connect(self.process_log)
        grid.addWidget(self.params["ckb_log"], 3, 3)
        
        group.setLayout(grid)
        layout.addWidget(group, 4, 3)

    def _build_frequency_scanning(self, layout):
        """Build frequency scanning group"""
        group = QGroupBox("Frequency scanning")
        grid = QGridLayout()
        
        grid.addWidget(QLabel("Min/Max:"), 0, 0)
        self.params["txt_range_min"] = QLineEdit()
        self.params["txt_range_min"].setToolTip("Lower bound of the frequency band to scan.")
        self.params["txt_range_min"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_range_min")
        )
        grid.addWidget(self.params["txt_range_min"], 0, 1)
        
        self.params["txt_range_max"] = QLineEdit()
        self.params["txt_range_max"].setToolTip("Upper bound of the frequency band to scan.")
        self.params["txt_range_max"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_range_max")
        )
        grid.addWidget(self.params["txt_range_max"], 0, 2)
        grid.addWidget(QLabel("khz"), 0, 3)
        
        grid.addWidget(QLabel("Interval:"), 1, 0)
        self.params["txt_interval"] = QLineEdit()
        self.params["txt_interval"].setToolTip("Tune once every interval khz.")
        self.params["txt_interval"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_interval")
        )
        grid.addWidget(self.params["txt_interval"], 1, 1)
        grid.addWidget(QLabel("Khz"), 1, 2)
        
        grid.addWidget(QLabel("Scan mode:"), 2, 0)
        self.params["cbb_freq_modulation"] = QComboBox()
        self.params["cbb_freq_modulation"].addItems(CBB_MODES)
        self.params["cbb_freq_modulation"].setToolTip("Mode to use for the frequency scan.")
        grid.addWidget(self.params["cbb_freq_modulation"], 2, 1)
        
        self.params["ckb_auto_bookmark"] = QCheckBox("auto bookmark")
        self.params["ckb_auto_bookmark"].setToolTip("Bookmark any active frequency found.")
        self.params["ckb_auto_bookmark"].stateChanged.connect(self.process_auto_bookmark)
        grid.addWidget(self.params["ckb_auto_bookmark"], 3, 0)
        
        self.freq_scan_toggle = QPushButton("Start")
        self.freq_scan_toggle.setToolTip("Starts a frequency scan.")
        self.freq_scan_toggle.clicked.connect(self.frequency_toggle)
        grid.addWidget(self.freq_scan_toggle, 3, 2)
        
        group.setLayout(grid)
        layout.addWidget(group, 3, 3)

    def _build_bookmark_scanning(self, layout):
        """Build bookmark scanning group"""
        group = QGroupBox("Bookmark scanning")
        grid = QGridLayout()
        
        self.book_scan_toggle = QPushButton("Start")
        self.book_scan_toggle.setToolTip("Starts a bookmark scan.")
        self.book_scan_toggle.clicked.connect(self.bookmark_toggle)
        grid.addWidget(self.book_scan_toggle, 0, 1)
        
        self.book_lockout = QPushButton("Lock")
        self.book_lockout.setToolTip("Toggle skipping selected bookmark.")
        self.book_lockout.clicked.connect(self.bookmark_lockout)
        grid.addWidget(self.book_lockout, 0, 3)
        
        group.setLayout(grid)
        layout.addWidget(group, 3, 4)

    def _build_sync_menu(self, layout):
        """Build rig frequency sync group"""
        group = QGroupBox("Rig Frequency Sync")
        grid = QGridLayout()
        
        self.sync_button = QPushButton("Start")
        self.sync_button.setToolTip("Keeps in sync the frequency/mode. The second rig is source, the first is the destination.")
        self.sync_button.clicked.connect(self.sync_toggle)
        grid.addWidget(self.sync_button, 0, 1)
        
        group.setLayout(grid)
        layout.addWidget(group, 4, 4)

    def _build_control_menu(self, layout):
        """Build options group"""
        group = QGroupBox("Options")
        grid = QGridLayout()
        
        self.ckb_save_exit = QCheckBox("Save on exit")
        self.ckb_save_exit.setToolTip("Save setting on exit.")
        grid.addWidget(self.ckb_save_exit, 0, 1)
        
        self.ckb_top = QCheckBox("Always on top")
        self.ckb_top.setToolTip("This window is always on top.")
        self.ckb_top.stateChanged.connect(self.toggle_cb_top)
        grid.addWidget(self.ckb_top, 0, 2)
        
        group.setLayout(grid)
        layout.addWidget(group, 5, 3, 1, 2)

    def _build_menu(self):
        """Build the menu bar"""
        menubar = self.menuBar()
        
        # Rig Remote menu
        app_menu = menubar.addMenu("Rig Remote")
        about_action = app_menu.addAction("About")
        about_action.triggered.connect(self.pop_up_about)
        quit_action = app_menu.addAction("Quit")
        quit_action.triggered.connect(lambda: shutdown(self))
        
        # Bookmarks menu
        bookmarks_menu = menubar.addMenu("Bookmarks")
        import_action = bookmarks_menu.addAction("Import")
        import_action.triggered.connect(self._import_bookmarks)
        
        export_menu = bookmarks_menu.addMenu("Export")
        export_gqrx = export_menu.addAction("Export GQRX")
        export_gqrx.triggered.connect(self.bookmarks.export_gqrx)
        export_rig = export_menu.addAction("Export rig-remote")
        export_rig.triggered.connect(self.bookmarks.export_rig_remote)

    def pop_up_about(self):
        """Display about dialog"""
        self.ckb_top.setChecked(False)
        QMessageBox.about(self, "About Rig Remote", self._ABOUT)

    @property
    def bookmarks_file(self) -> str:
        return self.ac.config["bookmark_filename"]

    def _load_bookmarks(self):
        """Load bookmarks from file"""
        self._insert_bookmarks(bookmarks=self.bookmarks.load(self.bookmarks_file, ","))

    def _import_bookmarks(self):
        """Import bookmarks"""
        bookmark_list = self.bookmarks.import_bookmarks()
        self._insert_bookmarks(bookmarks=bookmark_list)
        [self.bookmarks.add_bookmark(bookmark) for bookmark in bookmark_list]

    def _insert_bookmarks(self, bookmarks: list, silent=False):
        """Insert bookmarks into tree view"""
        logger.info("adding %i bookmarks", len(bookmarks))
        for entry in bookmarks:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, str(entry.channel.frequency))
            item.setText(1, entry.channel.modulation)
            item.setText(2, entry.description)
            item.setData(0, Qt.ItemDataRole.UserRole, entry.lockout)
            
            if entry.lockout == "L":
                item.setBackground(0, QBrush(QColor("red")))
                item.setBackground(1, QBrush(QColor("red")))
                item.setBackground(2, QBrush(QColor("red")))

    def process_entry_wrapper(self, widget_name):
        """Wrapper for process_entry to work with Qt signals"""
        widget = self.params[widget_name]
        
        class EventMock:
            def __init__(self, w, n):
                self.widget = w
                self.widget_name = n
        
        event = EventMock(widget, widget_name)
        self.process_entry(event)

    def process_entry(self, event, silent=False):
        """Process entry widget changes"""
        widget = event.widget
        widget_name = event.widget_name if hasattr(event, 'widget_name') else str(widget.objectName())
        event_value = widget.text() if hasattr(widget, 'text') else widget.currentText()
        
        # Extract key from widget name
        parts = widget_name.split("_", 1)
        if len(parts) > 1:
            ekey = parts[1]
        else:
            return
        
        if not event_value or event_value.isspace():
            if not silent:
                reply = QMessageBox.question(
                    self, "Error",
                    f"{ekey} must have a value entered. Use the default?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    event_value = self.ac.DEFAULT_CONFIG.get(ekey, "")
                    widget.setText(event_value)
                    self.params_last_content[widget_name] = event_value
                else:
                    if self.params_last_content.get(widget_name):
                        widget.setText(self.params_last_content[widget_name])
                    else:
                        widget.setFocus()
                        return
            else:
                event_value = self.ac.get(ekey, "")
                widget.setText(event_value)
                self.params_last_content[widget_name] = event_value
        
        # Handle hostname entries
        if widget_name.startswith("txt_hostname"):
            rig_number = int(widget_name[12:])
            self._process_hostname_entry(event_value, rig_number, silent)
            return
        
        # Handle port entries
        if widget_name.startswith("txt_port"):
            rig_number = int(widget_name[8:])
            self._process_port_entry(event_value, rig_number, silent)
        
        # Handle numeric entries
        try:
            event_value_int = int(event_value.replace(",", ""))
        except ValueError:
            if not silent:
                QMessageBox.critical(self, "Error", f"Invalid input value in {widget_name}")
            widget.setFocus()
            return
        
        self.params_last_content[widget_name] = event_value
        if self.scan_thread is not None:
            event_list = (widget_name, event_value_int)
            self.scanq.send_event_update(event_list)

    def _process_hostname_entry(self, event_value, number, silent=False):
        """Process hostname entry"""
        try:
            is_valid_hostname(event_value)
        except Exception:
            if not silent:
                QMessageBox.critical(self, "Error", "Invalid Hostname")
            return
        if number == 1:
            self.rigctl[0].target["hostname"] = event_value

    def _process_port_entry(self, event_value, number, silent=False):
        """Process port entry"""
        try:
            is_valid_port(event_value)
        except ValueError:
            if not silent:
                QMessageBox.critical(self, "Error", "Invalid input value in port. Must be integer and greater than 1024")
            return
        if number == 1:
            self.rigctl[0].target["port"] = event_value

    def process_wait(self, state):
        """Handle wait checkbox"""
        event_list = ("ckb_wait", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def process_record(self, state):
        """Handle record checkbox"""
        event_list = ("ckb_record", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def process_log(self, state):
        """Handle log checkbox"""
        event_list = ("ckb_log", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def process_auto_bookmark(self, state):
        """Handle auto bookmark checkbox"""
        event_list = ("ckb_auto_bookmark", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def _process_checkbutton(self, event_list):
        """Process checkbox state changes"""
        if self.scan_thread is not None:
            self.scanq.send_event_update(event_list)
            self.params_last_content[event_list[0]] = event_list[1]

    def toggle_cb_top(self, state):
        """Toggle always on top"""
        flags = self.windowFlags()
        if state == Qt.CheckState.Checked.value:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def apply_config(self, ac, silent=False):
        """Apply configuration to UI"""
        eflag = False
        
        # Handle hostnames and ports
        for rig_number in range(1, RIG_COUNT+1):
            hostname = f"hostname{rig_number}"
            widget_name = f"txt_{hostname}"
            try:
                is_valid_hostname(ac.config.get(hostname, ""))
            except ValueError:
                self.params[widget_name].setText(self.ac.DEFAULT_CONFIG[hostname])
                if not silent:
                    QMessageBox.critical(self, "Config File Error", 
                        "One (or more) of the values in the config file was invalid, and the default was used instead.")
            else:
                self.params[widget_name].setText(ac.config[hostname])
        
        # Test positive integer values
        keys = [f"port{r}" for r in range(1, RIG_COUNT+1)]
        keys.extend(["interval", "delay", "passes", "range_min", "range_max"])
        for key in keys:
            ekey = f"txt_{key}"
            if str.isdigit(ac.config[key].replace(",", "")):
                self.params[ekey].setText(ac.config[key])
            else:
                self.params[ekey].setText(self.ac.DEFAULT_CONFIG[key])
                eflag = True
        
        # Test integer values for signal level
        try:
            int(ac.config["sgn_level"])
        except ValueError:
            self.params["txt_sgn_level"].setText(self.ac.DEFAULT_CONFIG["sgn_level"])
            eflag = True
        else:
            self.params["txt_sgn_level"].setText(ac.config["sgn_level"])
        
        if eflag and not silent:
            QMessageBox.critical(self, "Config File Error",
                "One (or more) of the values in the config file was invalid, and the default was used instead.")
        
        # Set checkboxes
        self.params["ckb_auto_bookmark"].setChecked(ac.config.get("auto_bookmark", "false").lower() == "true")
        self.params["ckb_record"].setChecked(ac.config.get("record", "false").lower() == "true")
        self.params["ckb_wait"].setChecked(ac.config.get("wait", "false").lower() == "true")
        self.params["ckb_log"].setChecked(ac.config.get("log", "false").lower() == "true")
        self.ckb_save_exit.setChecked(ac.config.get("save_exit", "false").lower() == "true")
        self.ckb_top.setChecked(ac.config.get("always_on_top", "false").lower() == "true")
        
        # Initialize rig control
        self.rigctl = [
            RigCtl(self.ac.rig_endpoints[i])
            for i in range(RIG_COUNT)
        ]
        
        # Save current params content
        for key in self.params:
            widget = self.params[key]
            if isinstance(widget, QLineEdit):
                self.params_last_content[key] = widget.text()
            elif isinstance(widget, QCheckBox):
                self.params_last_content[key] = widget.isChecked()

    def sync_toggle(self):
        """Toggle sync start/stop"""
        action = self.sync_button.text().lower()
        self.sync_button.setText("Stop" if action == "start" else "Start")
        self._sync(action)

    def _sync(self, action):
        """Handle sync operations"""
        if self.scan_thread:
            self.sync_button.setText("Start")
            return

        if action.lower() not in self._SUPPORTED_SYNC_ACTIONS:
            logger.error("Provided action:{}".format(action))
            logger.error("Supported actions:{}".format(self._SUPPORTED_SYNC_ACTIONS))
            raise UnsupportedSyncConfigError

        if action.lower() == "stop" and self.sync_thread is not None:
            self.syncing.terminate()
            self.sync_thread.join()
            self.sync_thread = None
            return

        if action.lower() == "start" and self.sync_thread is not None:
            return

        if action.lower() == "stop" and self.sync_thread is None:
            return

        if action.lower() == "start" and self.sync_thread is None:
            try:
                task = SyncTask(
                    self.syncq,
                    RigCtl(self.ac.rig_endpoints[2]),
                    RigCtl(self.ac.rig_endpoints[1]),
                )
            except UnsupportedSyncConfigError:
                QMessageBox.critical(self, "Sync error", "Hostname/port of both rigs must be specified")
                self.sync_toggle()
                return
            self.syncing = Syncing()
            self.sync_thread = threading.Thread(target=self.syncing.sync, args=(task,))
            self.sync_thread.start()
            QTimer.singleShot(0, self.check_syncthread)

    def bookmark_toggle(self):
        """Toggle bookmark scan Start/Stop"""
        if self.scan_mode is None or self.scan_mode == "bookmarks":
            action = self.book_scan_toggle.text().lower()
            self.book_scan_toggle.setText("Stop" if action == "start" else "Start")
            self._scan(
                scan_mode="bookmarks",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].currentText(),
            )

    def bookmark_lockout(self):
        """Toggle lockout of selected bookmark"""
        current_item = self.tree.currentItem()
        if current_item is None:
            return
        
        lockout = current_item.data(0, Qt.ItemDataRole.UserRole)
        new_lockout = "O" if lockout == "L" else "L"
        current_item.setData(0, Qt.ItemDataRole.UserRole, new_lockout)
        
        if new_lockout == "L":
            current_item.setBackground(0, QBrush(QColor("red")))
            current_item.setBackground(1, QBrush(QColor("red")))
            current_item.setBackground(2, QBrush(QColor("red")))
        else:
            current_item.setBackground(0, QBrush(QColor("white")))
            current_item.setBackground(1, QBrush(QColor("white")))
            current_item.setBackground(2, QBrush(QColor("white")))

    def frequency_toggle(self):
        """Toggle frequency scan Start/Stop"""
        if self.params["cbb_freq_modulation"].currentText() == "":
            QMessageBox.critical(self, "Error", "You must select a mode for performing a frequency scan.")
            return
        if not self.scan_mode or self.scan_mode == "frequency":
            action = self.freq_scan_toggle.text().lower()
            self.freq_scan_toggle.setText("Stop" if action == "start" else "Start")
            self._scan(
                scan_mode="frequency",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].currentText(),
            )

    def check_scanthread(self):
        """Check if scan thread has terminated"""
        if self.scanq.check_end_of_scan():
            if self.scan_mode == "frequency":
                self.frequency_toggle()
            else:
                self.bookmark_toggle()
        else:
            if self.scan_thread is not None:
                QTimer.singleShot(self._UI_EVENT_TIMER_DELAY, self.check_scanthread)

    def check_syncthread(self):
        """Check if sync thread has terminated"""
        if not self.syncq.check_end_of_sync():
            if self.sync_thread is not None:
                QTimer.singleShot(self._UI_EVENT_TIMER_DELAY, self.check_syncthread)

    def _scan(self, scan_mode: str, action: str, frequency_modulation: str, silent=False):
        """Wrapper around scanning class"""
        logger.info("scan action %s with scan mode %s.", action, scan_mode)
        if action.lower() not in self._SUPPORTED_SCANNING_ACTIONS:
            logger.error("Provided action: {}".format(action))
            logger.error("Supported actions: {}".format(self._SUPPORTED_SCANNING_ACTIONS))
            raise UnsupportedScanningConfigError

        if self.sync_thread:
            if scan_mode == "bookmarks":
                self.book_scan_toggle.setText("Start")
            else:
                self.freq_scan_toggle.setText("Start")
            return

        if action.lower() == "stop" and self.scan_thread is not None:
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
            logger.info("Ignoring scan start command as there is already an ongoing scan")
            return

        if action.lower() == "stop" and self.scan_thread is None:
            logger.info("Ignoring scan stop command as there is no ongoing scan")
            return

        if action.lower() == "start" and self.scan_thread is None:
            if self.tree.topLevelItemCount() == 0 and scan_mode == "bookmarks":
                if not silent:
                    QMessageBox.critical(self, "Error", "No bookmarks to scan.")
                self.bookmark_toggle()
            else:
                logger.info("Scan start command accepted")
                task = ScanningTask(
                    frequency_modulation=frequency_modulation,
                    scan_mode=scan_mode,
                    new_bookmark_list=self.new_bookmark_list,
                    pass_params=dict.copy(self.params),
                    bookmarks=self.tree,
                )

                self.scanning = Scanning(
                    scan_queue=self.scanq,
                    log_filename=self.log_file,
                    rigctl=self.rigctl[0],
                )
                self.scan_thread = threading.Thread(target=self.scanning.scan, args=(task,))
                self.scan_thread.start()
                QTimer.singleShot(0, self.check_scanthread)

    def _clear_form(self, source):
        """Clear the form"""
        if source not in (1, 2):
            logger.error("The rig number {} is not supported".format(source))
            raise NotImplementedError

        frequency = f"txt_frequency{source}"
        mode = f"cbb_mode{source}"
        description = f"txt_description{source}"

        self.params[frequency].clear()
        self.params[description].clear()
        self.params[mode].setCurrentIndex(-1)

    def _add_new_bookmarks(self, nbl):
        """Add new bookmarks from list"""
        self._clear_form(1)
        for nb in nbl:
            self.params["txt_description1"].setText(f"activity on {nb['time']}")
            self.params["txt_frequency1"].setText(str(nb["freq"]).strip())
            self.params["cbb_mode1"].setCurrentText(nb["mode"])
            self.cb_first_add(True)
            self._clear_form(1)

    def cb_get_frequency(self, rig_target, silent=False):
        """Get current rig frequency and mode"""
        self._clear_form(rig_target["rig_number"])
        try:
            frequency = self.rigctl[0].get_frequency()
            mode = self.rigctl[0].get_mode()
            txt_frequency = f"txt_frequency{rig_target['rig_number']}"
            self.params[txt_frequency].setText(frequency.strip())
            cbb_mode = f"cbb_mode{rig_target['rig_number']}"
            self.params[cbb_mode].setCurrentText(mode)
        except Exception as err:
            if not silent:
                QMessageBox.critical(self, "Error", f"Could not connect to rig.\n{err}")

    def cb_set_frequency(self, rig_target, event, silent=False):
        """Set the rig frequency and mode"""
        txt_frequency = f"txt_frequency{rig_target['rig_number']}"
        cbb_mode = f"cbb_mode{rig_target['rig_number']}"
        frequency = self.params[txt_frequency].text().replace(",", "")
        mode = self.params[cbb_mode].currentText()

        try:
            self.rigctl[0].set_frequency(frequency)
            self.rigctl[0].set_mode(mode)
        except Exception as err:
            if not silent and (frequency != "" or mode != ""):
                QMessageBox.critical(self, "Error", f"Could not set frequency.\n{err}")
            if not silent and (frequency == "" or mode == ""):
                QMessageBox.critical(self, "Error", "Please provide frequency and mode.")

    def cb_autofill_form(self, rig_target, event):
        """Auto-fill bookmark fields with selected entry"""
        current_item = self.tree.currentItem()
        if current_item is None:
            return

        self._clear_form(rig_target)

        cbb_mode = f"cbb_mode{rig_target}"
        txt_frequency = f"txt_frequency{rig_target}"
        txt_description = f"txt_description{rig_target}"

        self.params[cbb_mode].setCurrentText(current_item.text(1))
        self.params[txt_frequency].setText(current_item.text(0))
        self.params[txt_description].setText(current_item.text(2))

    def build_control_source(self, number, silent=False):
        """Build control source dictionary"""
        if number not in (1, 2):
            logger.error("The rig number {} is not supported".format(number))
            raise NotImplementedError

        control_source = {}
        freq = f"txt_frequency{number}"
        mode = f"cbb_mode{number}"
        description = f"txt_description{number}"
        control_source["frequency"] = self.params[freq].text()
        
        try:
            int(control_source["frequency"])
        except (ValueError, TypeError):
            if not silent:
                QMessageBox.critical(self, "Error", "Invalid value in Frequency field. Note: '.' isn't allowed.")
                self.params[freq].setFocus()
            return None
        
        control_source["mode"] = self.params[mode].currentText()
        control_source["description"] = self.params[description].text()
        return control_source

    def cb_add(self, rig_number: int, silent: bool = False):
        """Add frequency to tree and save bookmarks"""
        control_source = self.build_control_source(rig_number)
        if not control_source["description"]:
            if not silent:
                QMessageBox.critical(self, "Error", "Please add a description")
            return
        
        bookmark = bookmark_factory(
            input_frequency=control_source["frequency"],
            modulation=control_source["mode"],
            description=control_source["description"],
            lockout="0",
        )

        # Find insertion point (insertion sort)
        idx = self.tree.topLevelItemCount()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            curr_freq = int(item.text(0))
            if int(bookmark.channel.frequency) < curr_freq:
                idx = i
                break

        if self.bookmarks.add_bookmark(bookmark):
            item = QTreeWidgetItem()
            item.setText(0, str(bookmark.channel.frequency))
            item.setText(1, bookmark.channel.modulation)
            item.setText(2, bookmark.description)
            item.setData(0, Qt.ItemDataRole.UserRole, bookmark.lockout)
            self.tree.insertTopLevelItem(idx, item)

        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        
        # Save bookmarks
        self.bookmarks.save(
            bookmarks_file=self.bookmarks_file, 
            bookmarks=self._extract_bookmarks()
        )

    def _extract_bookmarks(self) -> list:
        """Extract bookmarks from tree"""
        bookmark_list = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            bookmark_list.append(self._get_bookmark_from_item(item))
        return bookmark_list

    def cb_delete(self, source):
        """Delete frequency from tree"""
        current_item = self.tree.currentItem()
        if not current_item:
            return
        
        self.bookmarks.delete_bookmark(self._get_bookmark_from_item(current_item))
        index = self.tree.indexOfTopLevelItem(current_item)
        self.tree.takeTopLevelItem(index)
        
        # Save bookmarks
        self.bookmarks.save(
            bookmarks_file=self.bookmarks_file,
            bookmarks=self._extract_bookmarks()
        )
        self._clear_form(source)

    def _get_bookmark_from_item(self, item) -> Bookmark:
        """Get bookmark object from tree item"""
        return bookmark_factory(
            input_frequency=item.text(0),
            modulation=item.text(1),
            description=item.text(2),
            lockout=str(item.data(0, Qt.ItemDataRole.UserRole)),
        )
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self, 'Quit',
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            shutdown(self)
            if self.scan_thread is not None and self.scan_thread.is_alive():
                self.scanning.terminate()
                self.scan_thread.join(timeout=2)  # Wait max 2 seconds
            if self.sync_thread is not None and self.sync_thread.is_alive():
                self.syncing.terminate()
                self.sync_thread.join(timeout=2)  # Wait max 2 seconds
            event.accept()
            QApplication.instance().quit()
        else:
            event.ignore()

    @property
    def log_file(self):
        return self.ac.config["log_filename"]
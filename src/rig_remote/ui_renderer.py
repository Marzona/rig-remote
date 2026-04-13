"""
UI rendering logic for Rig Remote application.

This module contains the UI building methods for the RigRemote application.
It is designed as a mixin class to be used with the main RigRemote class.
"""

import logging

from PySide6.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QTreeWidget,
    QGroupBox,
)

from rig_remote.constants import RIG_COUNT
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rigctl import RigCtl

from rig_remote.models.modulation_modes import ModulationModes
from typing import Any

logger = logging.getLogger(__name__)


class RigRemoteUIBuilder:
    """Mixin class containing UI building methods for RigRemote."""

    _ORDINAL_NUMBERS: list[str]
    params: dict[str, Any]
    params_last_content: dict[str, str]
    rigctl: list[RigCtl]
    tree: QTreeWidget
    ckb_top: QCheckBox
    ckb_save_exit: QCheckBox
    sync_button: QPushButton
    freq_scan_toggle: QPushButton
    book_scan_toggle: QPushButton
    book_lockout: QPushButton

    def setWindowTitle(self, title: str) -> None: ...
    def setMinimumSize(self, width: int, height: int) -> None: ...
    def setCentralWidget(self, widget: QWidget) -> None: ...
    def menuBar(self) -> Any: ...
    def close(self) -> bool: raise NotImplementedError
    def process_entry_wrapper(self, widget_name: str) -> None: ...
    def process_wait(self, state: int) -> None: ...
    def process_record(self, state: int) -> None: ...
    def process_log(self, state: int) -> None: ...
    def process_auto_bookmark(self, state: int) -> None: ...
    def frequency_toggle(self) -> None: ...
    def bookmark_toggle(self) -> None: ...
    def bookmark_lockout(self) -> None: ...
    def sync_toggle(self) -> None: ...
    def toggle_cb_top(self, state: int) -> None: ...
    def add_bookmark_from_rig(self, rig_number: int) -> None: ...
    def cb_set_frequency(self, rig_endpoint: RigEndpoint, silent: bool = False) -> None: ...
    def cb_get_frequency(self, rig_endpoint: RigEndpoint) -> None: ...
    def cb_delete(self, source: int) -> None: ...
    def cb_autofill_form(self, rig_number: int) -> None: ...
    def pop_up_about(self) -> None: ...
    def _import_bookmarks_dialog(self) -> None: ...
    def _export_gqrx(self) -> None: ...
    def _export_rig_remote(self) -> None: ...

    def _build_ui(self) -> None:
        """Build the entire UI"""
        self.setWindowTitle("Rig Remote")
        self.setMinimumSize(800, 244)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QGridLayout(central_widget)

        self._build_tree_view(main_layout)
        for i in range(RIG_COUNT):
            self._build_rig(main_layout, i + 1)
        self._build_scanning_options(main_layout)
        self._build_frequency_scanning(main_layout)
        self._build_bookmark_scanning(main_layout)
        self._build_sync_menu(main_layout)
        self._build_control_menu(main_layout)
        self._build_menu()

    def _build_tree_view(self, layout: QGridLayout) -> None:
        """Build the bookmarks tree view"""
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Frequency", "Mode", "Description"])
        self.tree.setColumnWidth(0, 100)
        self.tree.setColumnWidth(1, 70)
        self.tree.setToolTip("Your bookmark list")
        layout.addWidget(self.tree, 0, 0, 6, 1)

    def _build_rig(self, layout: QGridLayout, rig_number: int) -> None:
        if rig_number < 0 or rig_number >= len(self._ORDINAL_NUMBERS) + 1:
            raise ValueError(f"Invalid rig number {rig_number}")

        self._build_rig_config(layout, rig_number)
        self._build_rig_control(layout, rig_number)

    def _build_rig_config(self, layout: QGridLayout, rig_number: int) -> None:
        group = QGroupBox(f"{self._ORDINAL_NUMBERS[rig_number - 1]} Rig configuration")
        grid = QGridLayout()

        grid.addWidget(QLabel("Hostname:"), 0, 0)
        txt_hostname = f"txt_hostname{rig_number}"
        self.params[txt_hostname] = QLineEdit()
        self.params[txt_hostname].setToolTip("Hostname to connect.")
        self.params[txt_hostname].editingFinished.connect(lambda: self.process_entry_wrapper(txt_hostname))
        grid.addWidget(self.params[txt_hostname], 0, 1, 1, 2)

        grid.addWidget(QLabel("Port:"), 1, 0)
        txt_port = f"txt_port{rig_number}"
        self.params[txt_port] = QLineEdit()
        self.params[txt_port].setToolTip("Port to connect.")
        self.params[txt_port].editingFinished.connect(lambda: self.process_entry_wrapper(txt_port))
        grid.addWidget(self.params[txt_port], 1, 1)

        group.setLayout(grid)
        layout.addWidget(group, 0, 2 + rig_number)

    def _build_rig_control(self, layout: QGridLayout, rig_number: int) -> None:
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
        self.params[cbb_mode].addItems([mode.value for mode in ModulationModes])
        self.params[cbb_mode].setToolTip("Mode to use for tuning the frequency.")
        grid.addWidget(self.params[cbb_mode], 1, 1, 1, 3)

        grid.addWidget(QLabel("Description:"), 2, 0)
        txt_description = f"txt_description{rig_number}"
        self.params[txt_description] = QLineEdit()
        self.params[txt_description].setToolTip("Description of the bookmark.")
        grid.addWidget(self.params[txt_description], 2, 1, 1, 3)

        self.btn_tune1 = QPushButton("Set")
        self.btn_tune1.setToolTip("Tune the frequency and mode from the rig control panel above.")
        self.btn_tune1.clicked.connect(lambda: self.cb_set_frequency(self.rigctl[rig_number - 1].endpoint, False))
        grid.addWidget(self.btn_tune1, 3, 0)

        self.btn_load1 = QPushButton("Get")
        self.btn_load1.setToolTip("Get the frequency and mode from the rig.")
        self.btn_load1.clicked.connect(lambda: self.cb_get_frequency(self.rigctl[rig_number - 1].endpoint))
        grid.addWidget(self.btn_load1, 3, 2)

        self.btn_delete1 = QPushButton("Remove")
        self.btn_delete1.setToolTip("Remove the selected bookmark.")
        self.btn_delete1.clicked.connect(lambda: self.cb_delete(rig_number))
        grid.addWidget(self.btn_delete1, 4, 0)

        self.btn_add1 = QPushButton("Add")
        self.btn_add1.setToolTip("Bookmark this frequency.")
        self.btn_add1.clicked.connect(lambda: self.add_bookmark_from_rig(rig_number))
        grid.addWidget(self.btn_add1, 4, 1)

        self.btn_recall1 = QPushButton("Recall")
        self.btn_recall1.setToolTip("Recall the frequency and mode from the bookmarks into this rig control panel.")
        self.btn_recall1.clicked.connect(lambda: self.cb_autofill_form(rig_number=rig_number))
        grid.addWidget(self.btn_recall1, 4, 2)

        group.setLayout(grid)
        layout.addWidget(group, 1, 2 + rig_number)

    def _build_scanning_options(self, layout: QGridLayout) -> None:
        """Build scanning options group"""
        group = QGroupBox("Scanning options")
        grid = QGridLayout()

        grid.addWidget(QLabel("Signal level:"), 0, 0)
        self.params["txt_sgn_level"] = QLineEdit()
        self.params["txt_sgn_level"].setToolTip("Signal level to trigger on.")
        self.params["txt_sgn_level"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_sgn_level"))
        grid.addWidget(self.params["txt_sgn_level"], 0, 1)
        grid.addWidget(QLabel("dBFS"), 0, 2)

        grid.addWidget(QLabel("Delay:"), 1, 0)
        self.params["txt_delay"] = QLineEdit()
        self.params["txt_delay"].setToolTip("Delay after finding a signal.")
        self.params["txt_delay"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_delay"))
        grid.addWidget(self.params["txt_delay"], 1, 1)
        grid.addWidget(QLabel("seconds"), 1, 2)

        grid.addWidget(QLabel("Passes:"), 2, 0)
        self.params["txt_passes"] = QLineEdit()
        self.params["txt_passes"].setToolTip("Number of scans.")
        self.params["txt_passes"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_passes"))
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

    def _build_frequency_scanning(self, layout: QGridLayout) -> None:
        """Build frequency scanning group"""
        group = QGroupBox("Frequency scanning")
        grid = QGridLayout()

        grid.addWidget(QLabel("Min/Max:"), 0, 0)
        self.params["txt_range_min"] = QLineEdit()
        self.params["txt_range_min"].setToolTip("Lower bound of the frequency band to scan.")
        self.params["txt_range_min"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_range_min"))
        grid.addWidget(self.params["txt_range_min"], 0, 1)

        self.params["txt_range_max"] = QLineEdit()
        self.params["txt_range_max"].setToolTip("Upper bound of the frequency band to scan.")
        self.params["txt_range_max"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_range_max"))
        grid.addWidget(self.params["txt_range_max"], 0, 2)
        grid.addWidget(QLabel("khz"), 0, 3)

        grid.addWidget(QLabel("Interval:"), 1, 0)
        self.params["txt_interval"] = QLineEdit()
        self.params["txt_interval"].setToolTip("Tune once every interval khz.")
        self.params["txt_interval"].editingFinished.connect(lambda: self.process_entry_wrapper("txt_interval"))
        grid.addWidget(self.params["txt_interval"], 1, 1)
        grid.addWidget(QLabel("Khz"), 1, 2)

        grid.addWidget(QLabel("Inner band:"), 2, 0)
        self.params["txt_inner_band"] = QLineEdit()
        self.params["txt_inner_band"].setToolTip(
            "Width in Hz of the inner refinement scan when a signal is found. "
            "Set to 0 to disable. Both Inner band and Inner interval must be set together."
        )
        self.params["txt_inner_band"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_inner_band")
        )
        grid.addWidget(self.params["txt_inner_band"], 2, 1)
        grid.addWidget(QLabel("Hz"), 2, 2)

        grid.addWidget(QLabel("Inner interval:"), 3, 0)
        self.params["txt_inner_interval"] = QLineEdit()
        self.params["txt_inner_interval"].setToolTip(
            "Step size in Hz for the inner refinement scan. "
            "Set to 0 to disable. Both Inner band and Inner interval must be set together."
        )
        self.params["txt_inner_interval"].editingFinished.connect(
            lambda: self.process_entry_wrapper("txt_inner_interval")
        )
        grid.addWidget(self.params["txt_inner_interval"], 3, 1)
        grid.addWidget(QLabel("Hz"), 3, 2)

        grid.addWidget(QLabel("Scan mode:"), 4, 0)
        self.params["cbb_freq_modulation"] = QComboBox()
        self.params["cbb_freq_modulation"].addItems([mode.value for mode in ModulationModes])
        self.params["cbb_freq_modulation"].setToolTip("Mode to use for the frequency scan.")
        grid.addWidget(self.params["cbb_freq_modulation"], 4, 1)

        self.params["ckb_auto_bookmark"] = QCheckBox("auto bookmark")
        self.params["ckb_auto_bookmark"].setToolTip("Bookmark any active frequency found.")
        self.params["ckb_auto_bookmark"].stateChanged.connect(self.process_auto_bookmark)
        grid.addWidget(self.params["ckb_auto_bookmark"], 5, 0)

        self.freq_scan_toggle = QPushButton("Start")
        self.freq_scan_toggle.setToolTip("Starts a frequency scan.")
        self.freq_scan_toggle.clicked.connect(self.frequency_toggle)
        grid.addWidget(self.freq_scan_toggle, 5, 2)

        group.setLayout(grid)
        layout.addWidget(group, 3, 3)

    def _build_bookmark_scanning(self, layout: QGridLayout) -> None:
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

    def _build_sync_menu(self, layout: QGridLayout) -> None:
        """Build rig frequency sync group"""
        group = QGroupBox("Rig Frequency Sync")
        grid = QGridLayout()

        self.sync_button = QPushButton("Start")
        self.sync_button.setToolTip(
            "Keeps in sync the frequency/mode. The second rig is source, the first is the destination."
        )
        self.sync_button.clicked.connect(self.sync_toggle)
        grid.addWidget(self.sync_button, 0, 1)

        group.setLayout(grid)
        layout.addWidget(group, 4, 4)

    def _build_control_menu(self, layout: QGridLayout) -> None:
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

    def _build_menu(self) -> None:
        """Build the menu bar"""
        menubar = self.menuBar()

        # Rig Remote menu
        app_menu = menubar.addMenu("Rig Remote")
        about_action = app_menu.addAction("About")
        about_action.triggered.connect(self.pop_up_about)
        quit_action = app_menu.addAction("Quit")
        quit_action.triggered.connect(lambda: self.close())

        # Bookmarks menu
        bookmarks_menu = menubar.addMenu("Bookmarks")
        import_action = bookmarks_menu.addAction("Import")
        import_action.triggered.connect(self._import_bookmarks_dialog)

        export_menu = bookmarks_menu.addMenu("Export")
        export_gqrx = export_menu.addAction("Export GQRX")
        export_gqrx.triggered.connect(self._export_gqrx)
        export_rig = export_menu.addAction("Export rig-remote")
        export_rig.triggered.connect(self._export_rig_remote)

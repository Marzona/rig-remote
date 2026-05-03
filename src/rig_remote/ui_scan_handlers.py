"""
Scan and sync event-handler mixin for Rig Remote.

Contains scan-toggle callbacks, frequency/bookmark-scan orchestration,
checkbox and form-entry handlers, and sync-thread management.

This module is a mixin (RigRemoteScanHandlersMixin).  Concrete instance
attributes it references are declared as class-level annotations so mypy
can verify types; the actual values are set by RigRemote.__init__.

Qt static methods (QMessageBox) require a QWidget parent.  At runtime
``self`` is always a QMainWindow; use ``self._parent()`` at call sites.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, NamedTuple, cast

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from rig_remote.app_config import AppConfig
from rig_remote.exceptions import (
    UnsupportedScanningConfigError,
    UnsupportedSyncConfigError,
)
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.models.sync_task import SyncTask
from rig_remote.rig_backends.hamlib_rigctl import HamlibRigCtl
from rig_remote.rig_backends.protocol import RigBackend
from rig_remote.scanning import Scanning2, create_scanner
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing

logger = logging.getLogger(__name__)


class _WidgetEvent(NamedTuple):
    """Carries a widget reference and its parameter name to ``_process_entry``."""

    widget: Any
    widget_name: str


class RigRemoteScanHandlersMixin:
    """Mixin providing scan, sync, form-entry, and checkbox event handlers for RigRemote.

    Attribute annotations below are satisfied by RigRemote.__init__ at
    construction time.  Method stubs are concrete implementations provided
    by RigRemote or RigRemoteHandlersMixin.
    """

    # ------------------------------------------------------------------
    # Constants (used only by scan/sync handler methods)
    # ------------------------------------------------------------------
    _SUPPORTED_SYNC_ACTIONS = ("start", "stop")
    _SUPPORTED_SCANNING_ACTIONS = ("start", "stop")
    _UI_TIMER_INTERVAL_MS = 1000

    # ------------------------------------------------------------------
    # Attribute annotations — provided by RigRemote.__init__
    # ------------------------------------------------------------------
    ac: AppConfig
    params: dict[str, Any]
    params_last_content: dict[str, Any]
    scan_thread: threading.Thread | None
    sync_thread: threading.Thread | None
    scan_mode: str | None
    scanning: Scanning2 | None
    syncing: Syncing | None
    new_bookmarks_list: list[Bookmark]
    rigctl: list[RigBackend]
    tree: QTreeWidget
    book_scan_toggle: QPushButton
    freq_scan_toggle: QPushButton
    sync_button: QPushButton
    scan_queue: STMessenger
    sync_queue: STMessenger

    # ------------------------------------------------------------------
    # Method stubs — concrete implementations provided by RigRemote /
    # RigRemoteHandlersMixin
    # ------------------------------------------------------------------
    @property
    def log_file(self) -> str: ...  # type: ignore[empty-body]

    def _add_new_bookmark(self, bookmark: Bookmark) -> None: ...

    def _parent(self) -> QWidget: ...  # type: ignore[empty-body]

    def windowFlags(self) -> Qt.WindowType: ...  # type: ignore[empty-body]
    def setWindowFlags(self, flags: Qt.WindowType) -> None: ...
    def show(self) -> None: ...

    # ------------------------------------------------------------------
    # Entry / form processing
    # ------------------------------------------------------------------

    def process_entry_wrapper(self, widget_name: str) -> None:
        """Wrapper for process_entry to work with Qt signals"""
        widget = self.params[widget_name]
        event_list = _WidgetEvent(widget=widget, widget_name=widget_name)
        self._process_entry(event_list)

    def _process_entry(self, event_list: Any, silent: bool = False) -> None:
        """Process entry widget changes"""
        widget = event_list.widget
        widget_name = event_list.widget_name if hasattr(event_list, "widget_name") else str(widget.objectName())
        event_list_value = widget.text() if hasattr(widget, "text") else widget.currentText()
        logger.debug("Processing entry %s with value %s", widget_name, event_list_value)
        # Widget names follow the "prefix_key" convention (e.g. "txt_range_min" → "range_min")
        if "_" not in widget_name:
            return
        ekey = widget_name.split("_", 1)[1]

        if not event_list_value or event_list_value.isspace():
            if not silent:
                reply = QMessageBox.question(
                    self._parent(),
                    "Error",
                    f"{ekey} must have a value entered. Use the default?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    event_list_value = self.ac.DEFAULT_CONFIG.get(ekey, "")
                    widget.setText(event_list_value)
                    self.params_last_content[widget_name] = event_list_value
                else:
                    if self.params_last_content.get(widget_name):
                        widget.setText(self.params_last_content[widget_name])
                    else:
                        widget.setFocus()
                        return
            else:
                event_list_value = self.ac.config.get(ekey, "")
                widget.setText(event_list_value)
                self.params_last_content[widget_name] = event_list_value

        # Handle hostname entries
        if widget_name.startswith("txt_hostname"):
            rig_number = int(widget_name[12:])
            self._process_hostname_entry(event_list_value, rig_number, silent)
            return

        # Handle port entries
        if widget_name.startswith("txt_port"):
            rig_number = int(widget_name[8:])
            self._process_port_entry(event_list_value, rig_number, silent)

        # Handle numeric entries
        try:
            event_list_value_int = int(event_list_value.replace(",", ""))
        except ValueError:
            if not silent:
                QMessageBox.critical(self._parent(), "Error", f"Invalid input value in {widget_name}")
            widget.setFocus()
            return

        self.params_last_content[widget_name] = event_list_value
        if self.scan_thread is not None:
            event_list = (widget_name, event_list_value_int)
            self.scan_queue.send_event_update(event_list)

    def _process_hostname_entry(self, event_list_value: str, rig_number: int, silent: bool = False) -> None:
        """Process hostname entry"""
        try:
            # rig numbering start from 1
            self.rigctl[rig_number - 1].endpoint = RigEndpoint(
                port=int(self.params["txt_port" + str(rig_number)].text()),
                hostname=event_list_value,
                number=rig_number,
                name="rig_" + str(rig_number),
            )
        except ValueError:
            if not silent:
                QMessageBox.critical(self._parent(), "Error", "Invalid Hostname")
        return

    def _process_port_entry(self, event_list_value: str, rig_number: int, silent: bool = False) -> None:
        """Process port entry"""
        try:
            self.rigctl[rig_number - 1].endpoint = RigEndpoint(
                port=int(event_list_value),
                hostname=self.params["txt_hostname" + str(rig_number)].text(),
                number=rig_number,
                name="rig_" + str(rig_number),
            )
        except ValueError:
            if not silent:
                QMessageBox.critical(
                    self._parent(), "Error", "Invalid input value in port. Must be integer and greater than 1024"
                )
        return

    # ------------------------------------------------------------------
    # Checkboxes
    # ------------------------------------------------------------------

    def process_wait(self, state: int) -> None:
        """Handle wait checkbox"""
        event_list = ("ckb_wait", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def process_record(self, state: int) -> None:
        """Handle record checkbox"""
        event_list = ("ckb_record", state == Qt.CheckState.Checked.value)
        if state == Qt.CheckState.Checked.value:
            for i, rig in enumerate(self.rigctl):
                if isinstance(rig, HamlibRigCtl):
                    QMessageBox.information(
                        self._parent(),
                        "Not supported",
                        f"Recording is not supported by the Hamlib backend (rig {i + 1}).",
                    )
                    self.params["ckb_record"].setChecked(False)
                    return
        self._process_checkbutton(event_list)

    def process_log(self, state: int) -> None:
        """Handle log checkbox"""
        event_list = ("ckb_log", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def process_auto_bookmark(self, state: int) -> None:
        """Handle auto bookmark checkbox"""
        event_list = ("ckb_auto_bookmark", state == Qt.CheckState.Checked.value)
        self._process_checkbutton(event_list)

    def _process_checkbutton(self, event_list: tuple[str, str | bool]) -> None:
        """Process checkbox state changes"""
        if self.scan_thread is not None:
            self.scan_queue.send_event_update(event_list)
            self.params_last_content[event_list[0]] = event_list[1]

    def toggle_cb_top(self, state: int) -> None:
        """Toggle always on top"""
        flags = self.windowFlags()
        if state == Qt.CheckState.Checked.value:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync_toggle(self) -> None:
        """Toggle sync start/stop"""
        action = self.sync_button.text().lower()
        self.sync_button.setText("Stop" if action == "start" else "Start")
        self._sync(action)

    def _sync(self, action: str) -> None:
        """Handle sync operations"""
        self.syncing = Syncing()
        if self.scan_thread:
            self.sync_button.setText("Start")
            return

        if action.lower() not in self._SUPPORTED_SYNC_ACTIONS:
            logger.error("Provided action: %s", action)
            logger.error("Supported actions: %s", self._SUPPORTED_SYNC_ACTIONS)
            raise UnsupportedSyncConfigError

        if action.lower() == "stop" and self.sync_thread is not None:
            if self.syncing is not None:
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
                    self.sync_queue,
                    self.rigctl[1],
                    self.rigctl[0],
                )
            except UnsupportedSyncConfigError:
                QMessageBox.critical(self._parent(), "Sync error", "Hostname/port of both rigs must be specified")
                self.sync_toggle()
                return

            self.sync_thread = threading.Thread(target=self.syncing.sync, args=(task,))
            self.sync_thread.start()
            logger.info("Sync thread started.")
            QTimer.singleShot(0, self.check_sync_thread)

    # ------------------------------------------------------------------
    # Scan toggle buttons
    # ------------------------------------------------------------------

    def bookmark_toggle(self) -> None:
        """Toggle bookmark scan Start/Stop"""
        if self.scan_mode is None or self.scan_mode == "bookmarks":
            action = self.book_scan_toggle.text().lower()
            self.book_scan_toggle.setText("Stop" if action == "start" else "Start")
            self._scan(
                scan_mode="bookmarks",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].currentText(),
            )

    def bookmark_lockout(self) -> None:
        """Toggle lockout of selected bookmark"""
        current_item = cast(QTreeWidgetItem | None, self.tree.currentItem())
        if current_item is None:
            return

        lockout = current_item.data(0, Qt.ItemDataRole.UserRole)
        new_lockout = "O" if lockout == "L" else "L"
        current_item.setData(0, Qt.ItemDataRole.UserRole, new_lockout)
        logger.info("Bookmark lockout toggled: %s → %s", lockout, new_lockout)

        if new_lockout == "L":
            current_item.setBackground(0, QBrush(QColor("red")))
            current_item.setBackground(1, QBrush(QColor("red")))
            current_item.setBackground(2, QBrush(QColor("red")))
        else:
            current_item.setBackground(0, QBrush(QColor("white")))
            current_item.setBackground(1, QBrush(QColor("white")))
            current_item.setBackground(2, QBrush(QColor("white")))

    def frequency_toggle(self) -> None:
        """Toggle frequency scan Start/Stop"""
        if self.params["cbb_freq_modulation"].currentText() == "":
            QMessageBox.critical(self._parent(), "Error", "You must select a mode for performing a frequency scan.")
            return
        if not self.scan_mode or self.scan_mode == "frequency":
            action = self.freq_scan_toggle.text().lower()
            self.freq_scan_toggle.setText("Stop" if action == "start" else "Start")
            self._scan(
                scan_mode="frequency",
                action=action,
                frequency_modulation=self.params["cbb_freq_modulation"].currentText(),
            )

    # ------------------------------------------------------------------
    # Scan thread monitor (timer callbacks)
    # ------------------------------------------------------------------

    def check_scan_thread(self) -> None:
        """Check if scan thread has terminated"""
        if self.scan_queue.check_end_of_scan():
            if self.scan_mode == "frequency":
                self.frequency_toggle()
            else:
                self.bookmark_toggle()
        else:
            if self.scan_thread is not None:
                QTimer.singleShot(self._UI_TIMER_INTERVAL_MS, self.check_scan_thread)

    def check_sync_thread(self) -> None:
        """Check if sync thread has terminated"""
        if not self.sync_queue.check_end_of_sync():
            if self.sync_thread is not None:
                QTimer.singleShot(self._UI_TIMER_INTERVAL_MS, self.check_sync_thread)

    # ------------------------------------------------------------------
    # Scan orchestration
    # ------------------------------------------------------------------

    def _scan(self, scan_mode: str, action: str, frequency_modulation: str, silent: bool = False) -> None:
        """Wrapper around scanning class"""
        logger.info("scan action %s with scan mode %s.", action, scan_mode)
        if action.lower() not in self._SUPPORTED_SCANNING_ACTIONS:
            logger.error("Provided action: %s, supported actions: %s", action, self._SUPPORTED_SCANNING_ACTIONS)
            raise UnsupportedScanningConfigError

        if self.sync_thread:
            if scan_mode == "bookmarks":
                self.book_scan_toggle.setText("Start")
            else:
                self.freq_scan_toggle.setText("Start")
            return

        if action.lower() == "stop" and self.scan_thread is not None:
            logger.info("Stopping ongoing scan")
            if self.scanning is not None:
                self.scanning.terminate()
            self.scan_thread.join()
            self.scan_thread = None
            if scan_mode.lower() == "frequency":
                logger.info("adding %i collected bookmarks...", len(self.new_bookmarks_list))
                for new_bookmark in self.new_bookmarks_list:
                    logger.info("Adding new bookmark: %s, ID: %s", new_bookmark.description, new_bookmark.id)
                    self._add_new_bookmark(bookmark=new_bookmark)
                self.new_bookmarks_list = []
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
                    QMessageBox.critical(self._parent(), "Error", "No bookmarks to scan.")
                self.bookmark_toggle()
            else:
                logger.info("Scan start command accepted")
                task = ScanningTask(
                    frequency_modulation=frequency_modulation,
                    scan_mode=scan_mode,
                    new_bookmarks_list=self.new_bookmarks_list,
                    range_min=int(self.params["txt_range_min"].text().replace(",", "")),
                    range_max=int(self.params["txt_range_max"].text().replace(",", "")),
                    interval=int(self.params["txt_interval"].text().replace(",", "")),
                    sgn_level=int(self.params["txt_sgn_level"].text().replace(",", "")),
                    delay=int(self.params["txt_delay"].text().replace(",", "")),
                    passes=int(self.params["txt_passes"].text().replace(",", "")),
                    wait=self.params["ckb_wait"].isChecked(),
                    record=self.params["ckb_record"].isChecked(),
                    log=self.params["ckb_log"].isChecked(),
                    auto_bookmark=self.params["ckb_auto_bookmark"].isChecked(),
                    bookmarks=self.new_bookmarks_list,
                    inner_band=int(self.params["txt_inner_band"].text().replace(",", "")),
                    inner_interval=int(self.params["txt_inner_interval"].text().replace(",", "")),
                )
                self.scanning = create_scanner(
                    scan_mode=scan_mode,
                    scan_queue=self.scan_queue,
                    log_filename=self.log_file,
                    rigctl=self.rigctl[0],  # all scanning activities are performed using rig 1
                )
                self.scan_thread = threading.Thread(target=self.scanning.scan, args=(task,))
                self.scan_thread.start()
                QTimer.singleShot(0, self.check_scan_thread)

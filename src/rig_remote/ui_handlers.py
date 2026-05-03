"""
UI event-handler mixin for Rig Remote.

Contains bookmark import/export, rig-control, backend-selection, and
window-close callbacks for the RigRemote window.  Scan, sync, form-entry,
and checkbox handlers live in RigRemoteScanHandlersMixin (ui_scan_handlers.py).

This module is a mixin (RigRemoteHandlersMixin).  Concrete instance
attributes it references are declared as class-level annotations so mypy
can verify types; the actual values are set by RigRemote.__init__.

Qt static methods (QMessageBox, QFileDialog) require a QWidget parent.
At runtime ``self`` is always a QMainWindow, but the mixin has no Qt base
class.  Use ``self._parent()`` at call sites — it returns ``self`` cast to
QWidget via a single contained cast.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from rig_remote.app_config import AppConfig
from rig_remote.bookmarksmanager import BookmarksManager, bookmark_factory
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rig_backends.hamlib_rigctl import HamlibRigCtl
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType, RigBackend
from rig_remote.scanning import Scanning2
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing

logger = logging.getLogger(__name__)


class RigRemoteHandlersMixin:
    """Mixin providing bookmark, rig-control, backend, and window-close handlers for RigRemote.

    Attribute annotations below are satisfied by RigRemote.__init__ at
    construction time.  Method stubs (``...`` body) are concrete
    implementations provided by RigRemote or its other mixins.
    """

    # ------------------------------------------------------------------
    # Constants (used only by handler methods)
    # ------------------------------------------------------------------
    _ABOUT = """
    Rig remote is a software for controlling a rig
    via tcp/ip and RigCtl.

    * GitHub: https://github.com/Marzona/rig-remote
    * Project wiki: https://github.com/Marzona/rig-remote/wiki
    """

    # ------------------------------------------------------------------
    # Attribute annotations — provided by RigRemote.__init__
    # ------------------------------------------------------------------
    ac: AppConfig
    params: dict[str, Any]
    params_last_content: dict[str, Any]
    bookmarks: BookmarksManager
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
    ckb_save_exit: QCheckBox
    ckb_top: QCheckBox
    scan_queue: STMessenger
    sync_queue: STMessenger

    # ------------------------------------------------------------------
    # Method stubs — concrete implementations provided by RigRemote
    # ------------------------------------------------------------------
    @property
    def bookmarks_file(self) -> str: ...  # type: ignore[empty-body]

    @property
    def log_file(self) -> str: ...  # type: ignore[empty-body]

    def _add_new_bookmark(self, bookmark: Bookmark) -> None: ...

    def _insert_bookmarks(self, bookmarks: list[Bookmark], silent: bool = False) -> None: ...

    @staticmethod
    def _get_bookmark_from_item(item: QTreeWidgetItem) -> Bookmark: ...  # type: ignore[empty-body]

    # ------------------------------------------------------------------
    # Qt window method stubs — provided by QMainWindow at runtime
    # ------------------------------------------------------------------
    def windowFlags(self) -> Qt.WindowType: ...  # type: ignore[empty-body]
    def setWindowFlags(self, flags: Qt.WindowType) -> None: ...
    def show(self) -> None: ...

    # ------------------------------------------------------------------
    # Qt parent helper
    # ------------------------------------------------------------------

    def _parent(self) -> QWidget:
        """Return self as QWidget for use as a Qt dialog parent argument.

        Safe because RigRemote always inherits QMainWindow (a QWidget) at
        runtime.  Contained here so every call site is type-clean without
        scattered casts.
        """
        return cast(QWidget, self)

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def pop_up_about(self) -> None:
        """Display about dialog"""
        self.ckb_top.setChecked(False)
        QMessageBox.about(self._parent(), "About Rig Remote", self._ABOUT)

    # ------------------------------------------------------------------
    # Bookmark import / export
    # ------------------------------------------------------------------

    def _import_bookmarks_dialog(self) -> None:
        """Prompt the user to select a bookmarks file to import."""
        filename, _ = QFileDialog.getOpenFileName(
            self._parent(),
            "Import bookmarks",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return

        self._import_bookmarks(Path(filename))

    def _import_bookmarks(self, bookmarks_file_path: Path) -> None:
        """Import bookmarks from the selected file."""
        bookmark_list = self.bookmarks.import_bookmarks(bookmarks_file_path)
        if not bookmark_list:
            return
        self._insert_bookmarks(bookmarks=bookmark_list)
        for bookmark in bookmark_list:
            self.bookmarks.add_bookmark(bookmark)

    def _export_rig_remote(self) -> None:
        """Prompt the user for an export destination and export rig-remote bookmarks."""
        default_filename = self.ac.config.get("bookmark_filename", "")
        filename, _ = QFileDialog.getSaveFileName(
            self._parent(),
            "Export rig-remote bookmarks",
            str(default_filename),
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            self.bookmarks.export_rig_remote(path)
        except OSError as err:
            QMessageBox.critical(self._parent(), "Export error", f"Could not export bookmarks:\n{err}")

    def _export_gqrx(self) -> None:
        """Prompt the user for an export destination and export GQRX bookmarks."""
        default_filename = self.ac.config.get("bookmark_filename", "")
        filename, _ = QFileDialog.getSaveFileName(
            self._parent(),
            "Export GQRX bookmarks",
            str(default_filename),
            "CSV files (*.csv);;All files (*)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            self.bookmarks.export_gqrx(path)
        except OSError as err:
            QMessageBox.critical(self._parent(), "Export error", f"Could not export bookmarks:\n{err}")

    # ------------------------------------------------------------------
    # Rig control
    # ------------------------------------------------------------------

    def _clear_form(self, source: int) -> None:
        """Clear the form"""
        if source not in (1, 2):
            logger.error("The rig number %s is not supported", source)
            raise NotImplementedError

        frequency = f"txt_frequency{source}"
        mode = f"cbb_mode{source}"
        description = f"txt_description{source}"

        self.params[frequency].clear()
        self.params[description].clear()
        self.params[mode].setCurrentIndex(-1)

    def cb_get_frequency(self, rig_endpoint: RigEndpoint, silent: bool = False) -> None:
        """Get current rig frequency and mode"""
        self._clear_form(rig_endpoint.number)
        try:
            frequency = self.rigctl[rig_endpoint.number - 1].get_frequency()
            mode = self.rigctl[rig_endpoint.number - 1].get_mode()
            txt_frequency = f"txt_frequency{rig_endpoint.number}"
            self.params[txt_frequency].setText(str(frequency))
            cbb_mode = f"cbb_mode{rig_endpoint.number}"
            self.params[cbb_mode].setCurrentText(mode)
            logger.info("Got frequency %s mode %s from rig %d", frequency, mode, rig_endpoint.number)
        except (OSError, TimeoutError, ValueError) as err:
            if not silent:
                QMessageBox.critical(self._parent(), "Error", f"Could not connect to rig.\n{err}")

    def cb_set_frequency(self, rig_endpoint: RigEndpoint, silent: bool = False) -> None:
        """Set the rig frequency and mode"""
        txt_frequency = f"txt_frequency{rig_endpoint.number}"
        cbb_mode = f"cbb_mode{rig_endpoint.number}"
        frequency = self.params[txt_frequency].text().replace(",", "")
        mode = self.params[cbb_mode].currentText()

        try:
            self.rigctl[0].set_frequency(int(frequency))
            self.rigctl[0].set_mode(mode)
            logger.info("Set frequency %s mode %s on rig 1", frequency, mode)
        except (OSError, TimeoutError, ValueError) as err:
            if not silent and (frequency != "" or mode != ""):
                QMessageBox.critical(self._parent(), "Error", f"Could not set frequency.\n{err}")
            if not silent and (frequency == "" or mode == ""):
                QMessageBox.critical(self._parent(), "Error", "Please provide frequency and mode.")

    def cb_autofill_form(self, rig_number: int) -> None:
        """Auto-fill bookmark fields with selected entry"""
        current_item = cast(QTreeWidgetItem | None, self.tree.currentItem())
        if current_item is None:
            return

        self._clear_form(rig_number)

        cbb_mode = f"cbb_mode{rig_number}"
        txt_frequency = f"txt_frequency{rig_number}"
        txt_description = f"txt_description{rig_number}"

        self.params[cbb_mode].setCurrentText(current_item.text(1))
        self.params[txt_frequency].setText(current_item.text(0))
        self.params[txt_description].setText(current_item.text(2))

    def build_control_source(self, number: int, silent: bool = False) -> dict[str, Any] | None:
        """Build control source dictionary"""
        if number not in (1, 2):
            logger.error("The rig number %s is not supported", number)
            raise NotImplementedError

        control_source = {}
        freq = f"txt_frequency{number}"
        mode = f"cbb_mode{number}"
        description = f"txt_description{number}"
        control_source["frequency"] = self.params[freq].text()

        try:
            int(control_source["frequency"])
        except (ValueError, TypeError):
            logger.info("Control source couldn't be built, aborting add operation.")
            if not silent:
                QMessageBox.critical(
                    self._parent(), "Error", "Invalid value in Frequency field. Note: '.' isn't allowed."
                )
                self.params[freq].setFocus()
            return None

        control_source["mode"] = self.params[mode].currentText()
        control_source["description"] = self.params[description].text()
        return control_source

    def add_bookmark_from_rig(self, rig_number: int, silent: bool = False) -> None:
        """Add frequency to tree and save bookmarks"""
        control_source = self.build_control_source(rig_number)

        if not control_source:
            if not silent:
                QMessageBox.critical(self._parent(), "Error", "Please add a description")
            return

        if not control_source["description"]:
            if not silent:
                QMessageBox.critical(self._parent(), "Error", "Please add a description")
            return

        bookmark = bookmark_factory(
            input_frequency=control_source["frequency"],
            modulation=control_source["mode"],
            description=control_source["description"],
            lockout="0",
        )
        self._add_new_bookmark(bookmark=bookmark)

    # ------------------------------------------------------------------
    # Bookmark deletion
    # ------------------------------------------------------------------

    def cb_delete(self, source: int) -> None:
        """Delete frequency from tree"""
        current_item = self.tree.currentItem()
        if not current_item:
            return

        self.bookmarks.delete_bookmark(self._get_bookmark_from_item(current_item))
        index = self.tree.indexOfTopLevelItem(current_item)
        self.tree.takeTopLevelItem(index)

        # Save bookmarks
        self.bookmarks.save(bookmarks_file=self.bookmarks_file)
        self._clear_form(source)

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _on_backend_changed(self, rig_number: int) -> None:
        """Show GQRX or Hamlib widgets based on the selected backend."""
        key = f"cbb_backend{rig_number}"
        backend_str = self.params[key].currentText()
        is_hamlib = backend_str == "HAMLIB"
        for suffix in (f"cbb_rig_model{rig_number}", f"txt_serial_port{rig_number}",
                       f"txt_baud_rate{rig_number}", f"btn_connect{rig_number}",
                       f"lbl_rig_model{rig_number}", f"lbl_serial_port{rig_number}",
                       f"lbl_baud_rate{rig_number}"):
            widget = self.params.get(suffix)
            if widget is not None:
                widget.setVisible(is_hamlib)
        for suffix in (f"txt_hostname{rig_number}", f"txt_port{rig_number}"):
            widget = self.params.get(suffix)
            if widget is not None:
                widget.setVisible(not is_hamlib)

    def cb_connect_rig(self, rig_number: int) -> None:
        """Build and connect a HamlibRigCtl for the given rig slot."""
        backend_key = f"cbb_backend{rig_number}"
        backend_str = self.params[backend_key].currentText()
        if backend_str != "HAMLIB":
            return

        rig_model_text = self.params[f"cbb_rig_model{rig_number}"].currentText()
        try:
            rig_model = int(rig_model_text.split()[0])
        except (ValueError, IndexError):
            QMessageBox.critical(self._parent(), "Error", "Invalid rig model selection.")
            return

        serial_port = self.params[f"txt_serial_port{rig_number}"].text().strip()
        baud_rate_text = self.params[f"txt_baud_rate{rig_number}"].text().strip()
        try:
            baud_rate = int(baud_rate_text)
        except ValueError:
            QMessageBox.critical(self._parent(), "Error", "Baud rate must be an integer.")
            return

        endpoint = RigEndpoint(
            backend=BackendType.HAMLIB,
            number=rig_number,
            rig_model=rig_model,
            serial_port=serial_port,
            baud_rate=baud_rate,
        )
        translator = ModeTranslator(BackendType.HAMLIB)
        rig = HamlibRigCtl(endpoint=endpoint, mode_translator=translator)
        try:
            self.freq_scan_toggle.setEnabled(False)
            self.book_scan_toggle.setEnabled(False)
            self.sync_button.setEnabled(False)
            rig.connect()
        except OSError as exc:
            logger.error("Hamlib connect failed for rig %d: %s", rig_number, exc)
            QMessageBox.critical(self._parent(), "Connection Error", f"Could not connect to rig:\n{exc}")
            return
        finally:
            self.freq_scan_toggle.setEnabled(True)
            self.book_scan_toggle.setEnabled(True)
            self.sync_button.setEnabled(True)

        self.rigctl[rig_number - 1] = rig
        logger.info("Rig %d connected via Hamlib (model=%d port=%s)", rig_number, rig_model, serial_port)

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event: Any) -> None:  # pylint: disable=invalid-name
        """Handle window close event

        :param event: close event
        """
        logger.info("Close event triggered, asking user for confirmation.")
        reply = QMessageBox.question(
            self._parent(),
            "Quit",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.ckb_save_exit.isChecked():
                logger.info("Saving configuration and bookmarks before exit.")
                self.bookmarks.save(bookmarks_file=self.bookmarks_file)
                self.ac.store_conf(window=cast(Any, self))
            if self.scan_thread is not None and self.scan_thread.is_alive():
                if self.scanning is not None:
                    self.scanning.terminate()
                self.scan_thread.join(timeout=2)  # Wait max 2 seconds
            if self.sync_thread is not None and self.sync_thread.is_alive():
                if self.syncing is not None:
                    self.syncing.terminate()
                self.sync_thread.join(timeout=2)  # Wait max 2 seconds
            event.accept()
        else:
            event.ignore()

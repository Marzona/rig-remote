"""
Main window class for Rig Remote.

RigRemote owns instance state, initialisation, configuration application,
and the bookmark-tree helpers.  All user-interaction callbacks live in
RigRemoteHandlersMixin (ui_handlers.py); all widget-building methods live
in RigRemoteUIBuilder (ui_renderer.py).
"""

import logging
import threading
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTreeWidgetItem,
)

from rig_remote.app_config import AppConfig
from rig_remote.bookmarksmanager import BookmarksManager, bookmark_factory
from rig_remote.constants import RIG_COUNT
from rig_remote.models.bookmark import Bookmark
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.queue_comms import QueueComms
from rig_remote.rigctl import RigCtl
from rig_remote.scanning import Scanning2
from rig_remote.stmessenger import STMessenger
from rig_remote.syncing import Syncing
from rig_remote.ui_handlers import RigRemoteHandlersMixin
from rig_remote.ui_renderer import RigRemoteUIBuilder

logger = logging.getLogger(__name__)


class _BookmarkTreeItem(QTreeWidgetItem):
    """QTreeWidgetItem with column-aware sorting for the bookmarks table.

    Column 0 (Frequency) is compared numerically; columns 1 and 2
    (Mode, Description) are compared case-insensitively as strings.
    """

    _NUMERIC_COLUMNS = {0}

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
        col = tree.sortColumn() if tree is not None else 0
        if col in self._NUMERIC_COLUMNS:
            try:
                return int(self.text(col)) < int(other.text(col))
            except ValueError:
                pass
        return self.text(col).lower() < other.text(col).lower()


class RigRemote(QMainWindow, RigRemoteHandlersMixin, RigRemoteUIBuilder):
    """Remote application that interacts with the rig using rigctl protocol.
    Gqrx partially implements rigctl since version 2.3.
    """

    # If you want more rigs, add more ordinals here
    _ORDINAL_NUMBERS = ["First", "Second", "Third", "Fourth"]

    def __init__(self, app_config: AppConfig) -> None:
        super().__init__()
        self.ac = app_config

        # Initialize attributes
        self.params: dict[str, Any] = {}
        self.params_last_content: dict[str, Any] = {}
        self.bookmarks = BookmarksManager()
        self.scan_thread: threading.Thread | None = None
        self.sync_thread: threading.Thread | None = None
        self.scan_mode: str | None = None
        self.scanning: Scanning2 | None = None
        self.syncing: Syncing | None = None
        self.selected_bookmark = None
        self.scan_queue = STMessenger(queue_comms=QueueComms())
        self.sync_queue = STMessenger(queue_comms=QueueComms())
        self.new_bookmarks_list: list[Bookmark] = []
        self.rigctl: list[RigCtl] = []

        self._build_ui()
        self._load_bookmarks()

        self.apply_config(app_config, silent=True)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def bookmarks_file(self) -> str:
        """returns bookmark filename from config

        Returns:
            str: bookmark filename
        """
        return str(self.ac.config["bookmark_filename"] or "")

    @property
    def log_file(self) -> str:
        """returns log filename from config

        Returns:
            str: log filename
        """
        return str(self.ac.config["log_filename"] or "")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_bookmarks(self) -> None:
        """Load bookmarks from file"""
        self._insert_bookmarks(bookmarks=self.bookmarks.load(self.bookmarks_file, ","))

    def apply_config(self, ac: AppConfig, silent: bool = False) -> None:
        """Apply configuration to UI"""
        eflag = False

        # Handle hostnames and ports
        for rig_number in range(1, RIG_COUNT + 1):
            port = f"port{rig_number}"
            try:
                port_value = int(ac.config[port] or "0")
            except ValueError:
                widget_name = f"txt_{port}"
                port_value = int(self.ac.DEFAULT_CONFIG[port] or "0")
                self.params[widget_name].setText(self.ac.DEFAULT_CONFIG[port] or "")
                if not silent:
                    QMessageBox.critical(
                        self,
                        "Config File Error",
                        "One (or more) of the values in the config file was invalid, and the default was used instead.",
                    )
            widget_name = f"txt_hostname{rig_number}"

            hostname = f"hostname{rig_number}"
            try:
                hostname_value = str(ac.config[f"hostname{rig_number}"] or "")
                logger.debug(
                    "Validating rig endpoint for rig number %s, rig hostname %s and port %s.",
                    rig_number,
                    hostname_value,
                    port_value,
                )
                _ = RigEndpoint(
                    hostname=hostname_value,
                    port=port_value,
                    number=rig_number,
                )
            except (ValueError, KeyError):
                self.params[widget_name].setText(self.ac.DEFAULT_CONFIG[hostname] or "")
                if not silent:
                    QMessageBox.critical(
                        self,
                        "Config File Error",
                        "One (or more) of the values in the config file was invalid, and the default was used instead.",
                    )
            else:
                self.params[widget_name].setText(hostname_value)

        # Test positive integer values
        keys = [f"port{r}" for r in range(1, RIG_COUNT + 1)]
        keys.extend(["interval", "delay", "passes", "range_min", "range_max",
                     "inner_band", "inner_interval"])
        for key in keys:
            ekey = f"txt_{key}"
            config_key_val = str(ac.config[key] or "")
            if str.isdigit(config_key_val.replace(",", "")):
                self.params[ekey].setText(config_key_val)
            else:
                self.params[ekey].setText(self.ac.DEFAULT_CONFIG[key] or "")
                eflag = True

        # Test integer values for signal level
        sgn_val = str(ac.config["sgn_level"] or "")
        try:
            int(sgn_val)
        except ValueError:
            self.params["txt_sgn_level"].setText(str(self.ac.DEFAULT_CONFIG["sgn_level"] or ""))
            eflag = True
        else:
            self.params["txt_sgn_level"].setText(sgn_val)

        if eflag and not silent:
            QMessageBox.critical(
                self,
                "Config File Error",
                "One (or more) of the values in the config file was invalid, and the default was used instead.",
            )

        # Set checkboxes
        self.params["ckb_auto_bookmark"].setChecked(str(ac.config.get("auto_bookmark") or "false").lower() == "true")
        self.params["ckb_record"].setChecked(str(ac.config.get("record") or "false").lower() == "true")
        self.params["ckb_wait"].setChecked(str(ac.config.get("wait") or "false").lower() == "true")
        self.params["ckb_log"].setChecked(str(ac.config.get("log") or "false").lower() == "true")
        self.ckb_save_exit.setChecked(str(ac.config.get("save_exit") or "false").lower() == "true")
        self.ckb_top.setChecked(str(ac.config.get("always_on_top") or "false").lower() == "true")

        # Initialize rig controls
        self.rigctl = [RigCtl(self.ac.rig_endpoints[i]) for i in range(RIG_COUNT)]
        logger.info("Initialized %d rig controls", RIG_COUNT)

        # Save current params content
        for key, widget in self.params.items():
            if isinstance(widget, QLineEdit):
                self.params_last_content[key] = widget.text()
            elif isinstance(widget, QCheckBox):
                self.params_last_content[key] = str(widget.isChecked())

    # ------------------------------------------------------------------
    # Bookmark tree helpers
    # ------------------------------------------------------------------

    def _insert_bookmarks(self, bookmarks: list[Bookmark], silent: bool = False) -> None:
        """Insert bookmarks into tree view"""
        logger.info("adding %i bookmarks", len(bookmarks))
        for entry in bookmarks:
            item = _BookmarkTreeItem(self.tree)
            item.setText(0, str(entry.channel.frequency))
            item.setText(1, entry.channel.modulation)
            item.setText(2, entry.description)
            item.setData(0, Qt.ItemDataRole.UserRole, entry.lockout)

            if entry.lockout == "L":
                item.setBackground(0, QBrush(QColor("red")))
                item.setBackground(1, QBrush(QColor("red")))
                item.setBackground(2, QBrush(QColor("red")))

    def _add_new_bookmark(self, bookmark: Bookmark) -> None:
        """adds new bookmark to the tree, to the bookmark object and saves bookmarks

        Args:
            bookmark (Bookmark): bookmark object to add
        """
        item = _BookmarkTreeItem()
        if self.bookmarks.add_bookmark(bookmark):
            item.setText(0, str(bookmark.channel.frequency))
            item.setText(1, bookmark.channel.modulation)
            item.setText(2, bookmark.description)
            item.setData(0, Qt.ItemDataRole.UserRole, bookmark.lockout)
            self.tree.addTopLevelItem(item)

        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        # add bookmark to bookmarks list
        self.bookmarks.add_bookmark(bookmark)
        # Save bookmarks
        self.bookmarks.save(bookmarks_file=self.bookmarks_file)
        logger.info("Bookmark saved: %s at %s Hz", bookmark.description, bookmark.channel.frequency)

    def _extract_bookmarks(self) -> list[Bookmark]:
        """Extract bookmarks from tree"""
        bookmark_list = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                bookmark_list.append(self._get_bookmark_from_item(item))
        return bookmark_list

    @staticmethod
    def _get_bookmark_from_item(item: QTreeWidgetItem) -> Bookmark:
        """Get bookmark object from tree item"""
        return bookmark_factory(
            input_frequency=int(item.text(0)),
            modulation=item.text(1),
            description=item.text(2),
            lockout=str(item.data(0, Qt.ItemDataRole.UserRole)),
        )

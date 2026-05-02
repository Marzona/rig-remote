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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:  # pragma: no cover
    from rig_remote.ui_qt import RigRemote  # pragma: no cover
import configparser
import logging
import os
import sys

from rig_remote.constants import (
    CONFIG_SECTIONS,
    MAIN_CONFIG,
    MAX_ENDPOINTS,
    MONITOR_CONFIG,
    RIG_COUNT,
    RIG_URI_CONFIG,
    SCANNING_CONFIG,
    SELECTED_RIG_KEYS,
)
from rig_remote.disk_io import IO
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rig_backends.protocol import BackendType

logger = logging.getLogger(__name__)

_ENDPOINT_SECTION_PREFIX = "rigendpoint."
_SELECTED_RIGS_SECTION = "selected rigs"

# Fields persisted per endpoint section, in save order.
_GQRX_ENDPOINT_FIELDS = ("uuid", "backend", "name", "hostname", "port")
_HAMLIB_ENDPOINT_FIELDS = (
    "uuid",
    "backend",
    "name",
    "rig_model",
    "serial_port",
    "baud_rate",
    "data_bits",
    "stop_bits",
    "parity",
)


def _endpoint_to_section(endpoint: RigEndpoint) -> dict[str, str]:
    """Serialise a RigEndpoint to a flat string dict for configparser."""
    base: dict[str, str] = {
        "uuid": endpoint.id,
        "backend": endpoint.backend.value,
        "name": endpoint.name,
        "number": str(endpoint.number),
    }
    if endpoint.backend == BackendType.GQRX:
        base["hostname"] = endpoint.hostname
        base["port"] = str(endpoint.port)
    else:
        base["rig_model"] = str(endpoint.rig_model)
        base["serial_port"] = endpoint.serial_port
        base["baud_rate"] = str(endpoint.baud_rate)
        base["data_bits"] = str(endpoint.data_bits)
        base["stop_bits"] = str(endpoint.stop_bits)
        base["parity"] = endpoint.parity
    return base


def _section_to_endpoint(items: dict[str, str]) -> RigEndpoint | None:
    """Deserialise a configparser section dict to a RigEndpoint.

    Returns None and logs a warning if the section is malformed.
    """
    try:
        raw_backend = items.get("backend", "GQRX").upper()
        backend = BackendType(raw_backend)
        number = int(items.get("number", "0"))
        ep_id = items.get("uuid", "")
        name = items.get("name", "")

        if backend == BackendType.GQRX:
            endpoint = RigEndpoint(
                backend=backend,
                number=number,
                name=name,
                hostname=items.get("hostname", ""),
                port=int(items.get("port", "0")),
            )
        else:
            endpoint = RigEndpoint(
                backend=backend,
                number=number,
                name=name,
                rig_model=int(items.get("rig_model", "0")),
                serial_port=items.get("serial_port", ""),
                baud_rate=int(items.get("baud_rate", "9600")),
                data_bits=int(items.get("data_bits", "8")),
                stop_bits=int(items.get("stop_bits", "1")),
                parity=items.get("parity", "N"),
            )
        if ep_id:
            endpoint.id = ep_id
        return endpoint
    except (ValueError, KeyError) as exc:
        logger.warning("Skipping malformed endpoint section: %s", exc)
        return None


class AppConfig:
    """Reads and writes the application configuration INI file.

    Supports two INI formats:
    - Legacy: ``[Rig URI]`` section with ``hostname1``, ``port1``,
      ``hostname2``, ``port2`` keys.
    - Current: ``[rigendpoint.N]`` sections (one per endpoint) plus a
      ``[selected rigs]`` section that records which UUID is active per rig.

    Both formats are read; the legacy keys bootstrap an initial endpoint list
    when no ``[rigendpoint.*]`` sections exist.
    """

    DEFAULT_CONFIG: ClassVar[dict[str, str | bool | None]] = {
        "hostname1": "127.0.0.1",
        "port1": "7356",
        "hostname2": "127.0.0.1",
        "port2": "7357",
        "interval": "1",
        "delay": "5",
        "passes": "0",
        "inner_band": "0",
        "inner_interval": "0",
        "sgn_level": "-30",
        "range_min": "24,000",
        "range_max": "1800,000",
        "wait": "false",
        "record": "false",
        "log": "false",
        "always_on_top": "true",
        "save_exit": "false",
        "aggr_scan": "false",
        "auto_bookmark": "false",
        "log_filename": None,
        "bookmark_filename": None,
    }
    _UPGRADE_MESSAGE = (
        "This config file may deserve an "
        "upgrade, please execute the "
        "following comand: "
        "python ./config_checker.py -uc ~/.rig-remote/ or "
        "Check https://github.com/Marzona/rig-remote/wiki/User-Manual#config_checker "
        "for more info."
    )

    def __init__(self, config_file: str):
        self._io = IO()
        self.rig_endpoints: list[RigEndpoint] = []
        # UUIDs of the two selected rigs, indexed 0 and 1 (rig 1 and rig 2).
        self.selected_rig_uuids: list[str] = ["", ""]
        self.config_file = config_file
        if not self.config_file:
            self.config = dict.copy(self.DEFAULT_CONFIG)
        else:
            self.config = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_conf(self) -> None:
        """Read the configuration file.

        Falls back to DEFAULT_CONFIG when the file is absent or empty.
        Reads both legacy ``hostname/port`` keys (backward compat) and
        new ``[rigendpoint.N]`` sections.
        """
        logger.debug("Reading configuration file: %s", self.config_file)
        if os.path.isfile(self.config_file):
            logger.info("Using config file:%s", self.config_file)
            config = configparser.RawConfigParser()
            try:
                config.read(self.config_file)
            except configparser.MissingSectionHeaderError:
                logger.error("Missing Sections in the config file.")
                logger.error(self._UPGRADE_MESSAGE)
                sys.exit(1)

            if not config.sections():
                self.config = self.DEFAULT_CONFIG
            else:
                for section in config.sections():
                    for item in config.items(section):
                        self.config[item[0]] = item[1]

            self._load_endpoints(config)
            self._load_selected_rigs(config)
        else:
            logger.info("Using default configuration...")
            self.config = self.DEFAULT_CONFIG

        if not self.rig_endpoints:
            self._bootstrap_legacy_endpoints()

    def store_conf(self, window: RigRemote) -> None:
        """Persist the configuration from the UI to the INI file."""
        self._get_conf(window)
        self._write_conf()

    def add_endpoint(self, endpoint: RigEndpoint) -> None:
        """Add *endpoint* to the in-memory list.

        FIFO eviction to MAX_ENDPOINTS is deferred to save time.
        """
        self.rig_endpoints.append(endpoint)

    def endpoint_by_uuid(self, uuid: str) -> RigEndpoint | None:
        """Return the endpoint matching *uuid*, or None."""
        for ep in self.rig_endpoints:
            if ep.id == uuid:
                return ep
        return None

    def selected_endpoint(self, rig_number: int) -> RigEndpoint | None:
        """Return the selected endpoint for *rig_number* (1-based).

        Falls back to the most recent endpoint when the stored UUID is absent.
        """
        idx = rig_number - 1
        if 0 <= idx < len(self.selected_rig_uuids):
            uuid = self.selected_rig_uuids[idx]
            ep = self.endpoint_by_uuid(uuid)
            if ep is not None:
                return ep
        if self.rig_endpoints:
            logger.info(
                "Stored UUID for rig %d not found — using most recent endpoint.",
                rig_number,
            )
            return self.rig_endpoints[-1]
        return None

    # ------------------------------------------------------------------
    # Internal helpers — load
    # ------------------------------------------------------------------

    def _load_endpoints(self, config: configparser.RawConfigParser) -> None:
        """Populate self.rig_endpoints from [rigendpoint.N] sections."""
        endpoint_sections = sorted(
            (s for s in config.sections() if s.startswith(_ENDPOINT_SECTION_PREFIX)),
            key=lambda s: int(s.split(".", 1)[1]) if s.split(".", 1)[1].isdigit() else 0,
        )
        for section in endpoint_sections:
            items = dict(config.items(section))
            ep = _section_to_endpoint(items)
            if ep is not None:
                self.rig_endpoints.append(ep)

    def _load_selected_rigs(self, config: configparser.RawConfigParser) -> None:
        """Read [selected rigs] UUIDs into self.selected_rig_uuids."""
        if not config.has_section(_SELECTED_RIGS_SECTION):
            return
        for i, key in enumerate(SELECTED_RIG_KEYS):
            if config.has_option(_SELECTED_RIGS_SECTION, key):
                self.selected_rig_uuids[i] = config.get(_SELECTED_RIGS_SECTION, key)

    def _bootstrap_legacy_endpoints(self) -> None:
        """Create RigEndpoint objects from legacy hostname/port keys."""
        for instance_number in range(1, RIG_COUNT + 1):
            hostname_key = f"hostname{instance_number}"
            port_key = f"port{instance_number}"
            hostname = str(self.config.get(hostname_key, "127.0.0.1"))
            raw_port = self.config.get(port_key, "0")
            port = int(raw_port or "0")
            try:
                ep = RigEndpoint(
                    hostname=hostname,
                    port=port,
                    number=instance_number,
                )
                self.rig_endpoints.append(ep)
            except ValueError:
                logger.warning(
                    "Legacy endpoint %d invalid (hostname=%s port=%d) — skipped.",
                    instance_number,
                    hostname,
                    port,
                )

    # ------------------------------------------------------------------
    # Internal helpers — save
    # ------------------------------------------------------------------

    def _write_conf(self) -> None:
        """Write all config, endpoints, and selected rigs to the INI file."""
        try:
            os.makedirs(os.path.dirname(self.config_file))
        except OSError:
            logger.info("skip create config path as %s, already exists?", self.config_file)

        config = configparser.RawConfigParser()
        for section in CONFIG_SECTIONS:
            config.add_section(section)

        for key in self.config.keys():
            raw = self.config[key]
            value: str | None = str(raw).lower() if isinstance(raw, bool) else raw
            if key in RIG_URI_CONFIG:
                config.set("Rig URI", key, value)
            if key in MONITOR_CONFIG:
                config.set("Monitor", key, value)
            if key in MAIN_CONFIG:
                config.set("Main", key, value)
            if key in SCANNING_CONFIG:
                config.set("Scanning", key, value)

        self._write_endpoints(config)
        self._write_selected_rigs(config)

        with open(self.config_file, "w", encoding="utf-8") as cf:
            config.write(cf)

    def _write_endpoints(self, config: configparser.RawConfigParser) -> None:
        """Serialise self.rig_endpoints with FIFO eviction at MAX_ENDPOINTS."""
        endpoints_to_save = self.rig_endpoints
        if len(endpoints_to_save) > MAX_ENDPOINTS:
            evict_count = len(endpoints_to_save) - MAX_ENDPOINTS
            logger.info(
                "Endpoint list exceeds %d — evicting %d oldest endpoint(s).",
                MAX_ENDPOINTS,
                evict_count,
            )
            for ep in endpoints_to_save[:evict_count]:
                logger.info("Evicted endpoint: uuid=%s name=%s", ep.id, ep.name)
            endpoints_to_save = endpoints_to_save[evict_count:]

        for idx, endpoint in enumerate(endpoints_to_save):
            section = f"{_ENDPOINT_SECTION_PREFIX}{idx}"
            config.add_section(section)
            for key, value in _endpoint_to_section(endpoint).items():
                config.set(section, key, value)

    def _write_selected_rigs(self, config: configparser.RawConfigParser) -> None:
        """Write [selected rigs] section."""
        config.add_section(_SELECTED_RIGS_SECTION)
        for i, key in enumerate(SELECTED_RIG_KEYS):
            uuid = self.selected_rig_uuids[i] if i < len(self.selected_rig_uuids) else ""
            config.set(_SELECTED_RIGS_SECTION, key, uuid)

    def _get_conf(self, window: RigRemote) -> None:
        """Populate self.config from the UI window."""
        self.config["hostname1"] = window.params["txt_hostname1"].text()
        self.config["port1"] = window.params["txt_port1"].text()
        self.config["hostname2"] = window.params["txt_hostname2"].text()
        self.config["port2"] = window.params["txt_port2"].text()
        self.config["interval"] = window.params["txt_interval"].text()
        self.config["delay"] = window.params["txt_delay"].text()
        self.config["passes"] = window.params["txt_passes"].text()
        self.config["inner_band"] = window.params["txt_inner_band"].text()
        self.config["inner_interval"] = window.params["txt_inner_interval"].text()
        self.config["sgn_level"] = window.params["txt_sgn_level"].text()
        self.config["range_min"] = window.params["txt_range_min"].text()
        self.config["range_max"] = window.params["txt_range_max"].text()
        self.config["wait"] = window.params["ckb_wait"].isChecked()
        self.config["record"] = window.params["ckb_record"].isChecked()
        self.config["log"] = window.params["ckb_log"].isChecked()
        self.config["always_on_top"] = window.ckb_top.isChecked()
        self.config["save_exit"] = window.ckb_save_exit.isChecked()
        self.config["auto_bookmark"] = window.params["ckb_auto_bookmark"].isChecked()
        self.config["bookmark_filename"] = window.bookmarks_file
        self.config["log_filename"] = window.log_file

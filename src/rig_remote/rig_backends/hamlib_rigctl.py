"""
HamlibRigCtl: Hamlib serial/USB backend.

Uses the Hamlib Python SWIG library (libhamlib4) to control a physical
transceiver over a USB/serial connection.

Connection lifecycle:
  - connect()    — close any existing connection then open the new one.
  - disconnect() — close the current connection.
  - Connection stays open between commands (unlike GQRXRigCtl which
    opens a new socket per command).

Thread safety:
  - Hamlib.Rig is a stateful serial object.  Every call is wrapped in a
    threading.RLock so concurrent access from the main thread and the
    scan thread cannot corrupt the rig state.

Level contract:
  - get_level() multiplies Hamlib.RIG_LEVEL_STRENGTH by 10 to match
    the protocol contract of "dB × 10" used by GQRXRigCtl.
"""

import logging
import threading
import types
from typing import Any

from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rig_backends.mode_translator import ModeTranslator

logger = logging.getLogger(__name__)

# Lazy Hamlib import: allows sys.modules mocking in tests without Hamlib installed.
def _hamlib() -> types.ModuleType:
    import importlib
    try:
        return importlib.import_module("Hamlib")
    except ImportError as exc:
        raise ImportError(
            "The Hamlib Python module is required for the HamLib backend. "
            "Install it with: pip install Hamlib  (also needs libhamlib4 system package)"
        ) from exc


class HamlibRigCtl:
    """Hamlib-based rig backend.  One instance per configured Hamlib endpoint."""

    def __init__(self, endpoint: RigEndpoint, mode_translator: ModeTranslator) -> None:
        self._endpoint = endpoint
        self._translator = mode_translator
        self._lock = threading.RLock()
        self._rig: Any = None

    @property
    def endpoint(self) -> RigEndpoint:
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: RigEndpoint) -> None:
        self._endpoint = value

    # ------------------------------------------------------------------
    # Connection management (called by the UI Connect button)
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Close any existing connection then open the configured endpoint."""
        hl = _hamlib()
        with self._lock:
            if self._rig is not None:
                try:
                    self._rig.close()
                except Exception:
                    logger.warning("Error closing previous Hamlib connection — ignored")
                self._rig = None

            rig = hl.Rig(self._endpoint.rig_model)
            rig.set_conf("rig_pathname", self._endpoint.serial_port)
            rig.set_conf("serial_speed", str(self._endpoint.baud_rate))
            rig.set_conf("data_bits", str(self._endpoint.data_bits))
            rig.set_conf("stop_bits", str(self._endpoint.stop_bits))
            rig.set_conf("serial_parity", self._endpoint.parity)
            try:
                rig.open()
            except Exception as exc:
                logger.error("Failed to open Hamlib connection: %s", exc)
                raise OSError(str(exc)) from exc
            self._rig = rig
            logger.info(
                "Hamlib connected: model=%d port=%s baud=%d",
                self._endpoint.rig_model,
                self._endpoint.serial_port,
                self._endpoint.baud_rate,
            )

    def disconnect(self) -> None:
        """Close the current Hamlib connection."""
        with self._lock:
            if self._rig is not None:
                try:
                    self._rig.close()
                except Exception:
                    logger.error("Error closing Hamlib connection")
                finally:
                    self._rig = None

    def _require_rig(self) -> Any:
        """Return the connected Rig object or raise OSError if not connected."""
        if self._rig is None:
            raise OSError("Hamlib rig is not connected — press Connect first")
        return self._rig

    # ------------------------------------------------------------------
    # RigBackend protocol implementation
    # ------------------------------------------------------------------

    def set_frequency(self, frequency: int) -> None:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_freq(hl.RIG_VFO_CURR, frequency)
            except Exception as exc:
                logger.error("Hamlib error setting frequency to %d: %s", frequency, exc)
                raise

    def get_frequency(self) -> int:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return int(rig.get_freq(hl.RIG_VFO_CURR))
            except Exception as exc:
                logger.error("Hamlib error getting frequency: %s", exc)
                raise

    def set_mode(self, mode: str) -> None:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            hamlib_mode = self._translator.to_backend(mode)  # raises ValueError if unmapped
            try:
                rig.set_mode(hl.RIG_VFO_CURR, hamlib_mode, hl.RIG_PASSBAND_NOCHANGE)
            except Exception as exc:
                logger.error("Hamlib error setting mode %r: %s", mode, exc)
                raise

    def get_mode(self) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                mode_const, _width = rig.get_mode(hl.RIG_VFO_CURR)
            except Exception as exc:
                logger.error("Hamlib error getting mode: %s", exc)
                raise
        # from_backend raises ValueError for unmapped constants → retriable in scan loop
        return self._translator.from_backend(mode_const)

    def get_level(self) -> int:
        """Return signal strength as int in dB × 10 units.

        Multiplies RIG_LEVEL_STRENGTH by 10 to match the protocol contract
        shared with GQRXRigCtl.  Absolute reference levels differ between
        backends; users switching must re-calibrate sgn_level.
        """
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return int(rig.get_level_i(hl.RIG_LEVEL_STRENGTH)) * 10
            except Exception as exc:
                logger.error("Hamlib error getting signal level: %s", exc)
                raise

    def start_recording(self) -> str:
        raise NotImplementedError("Recording is not supported by the Hamlib backend")

    def stop_recording(self) -> str:
        raise NotImplementedError("Recording is not supported by the Hamlib backend")

    def set_rit(self, rit: int) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_rit(hl.RIG_VFO_CURR, rit)
            except Exception as exc:
                logger.error("Hamlib error setting RIT: %s", exc)
                raise
        return ""

    def get_rit(self) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return str(rig.get_rit(hl.RIG_VFO_CURR))
            except Exception as exc:
                logger.error("Hamlib error getting RIT: %s", exc)
                raise

    def set_xit(self, xit: int) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_xit(hl.RIG_VFO_CURR, xit)
            except Exception as exc:
                logger.error("Hamlib error setting XIT: %s", exc)
                raise
        return ""

    def get_xit(self) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return str(rig.get_xit(hl.RIG_VFO_CURR))
            except Exception as exc:
                logger.error("Hamlib error getting XIT: %s", exc)
                raise

    def set_split_freq(self, split_freq: int) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_split_freq(hl.RIG_VFO_CURR, split_freq)
            except Exception as exc:
                logger.error("Hamlib error setting split freq: %s", exc)
                raise
        return ""

    def get_split_freq(self) -> int:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return int(rig.get_split_freq(hl.RIG_VFO_CURR))
            except Exception as exc:
                logger.error("Hamlib error getting split freq: %s", exc)
                raise

    def set_split_mode(self, split_mode: str) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            hamlib_mode = self._translator.to_backend(split_mode)
            try:
                rig.set_split_mode(hl.RIG_VFO_CURR, hamlib_mode, hl.RIG_PASSBAND_NOCHANGE)
            except Exception as exc:
                logger.error("Hamlib error setting split mode: %s", exc)
                raise
        return ""

    def get_split_mode(self) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                mode_const, _width = rig.get_split_mode(hl.RIG_VFO_CURR)
            except Exception as exc:
                logger.error("Hamlib error getting split mode: %s", exc)
                raise
        return self._translator.from_backend(mode_const)

    def set_func(self, func: str) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_func(hl.RIG_VFO_CURR, getattr(hl, f"RIG_FUNC_{func}", 0), 1)
            except Exception as exc:
                logger.error("Hamlib error setting func %r: %s", func, exc)
                raise
        return ""

    def get_func(self) -> str:
        return ""

    def set_parm(self, parm: str) -> str:
        return ""

    def get_parm(self) -> str:
        return ""

    def set_vfo(self, vfo: str) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            vfo_const = getattr(hl, f"RIG_VFO_{vfo.upper()}", None)
            if vfo_const is None:
                raise ValueError(f"Unknown VFO: {vfo!r}")
            try:
                rig.set_vfo(vfo_const)
            except Exception as exc:
                logger.error("Hamlib error setting VFO %r: %s", vfo, exc)
                raise
        return ""

    def get_vfo(self) -> str:
        with self._lock:
            rig = self._require_rig()
            try:
                return str(rig.get_vfo())
            except Exception as exc:
                logger.error("Hamlib error getting VFO: %s", exc)
                raise

    def set_antenna(self, antenna: int) -> str:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                rig.set_ant(hl.RIG_VFO_CURR, antenna)
            except Exception as exc:
                logger.error("Hamlib error setting antenna: %s", exc)
                raise
        return ""

    def get_antenna(self) -> int:
        hl = _hamlib()
        with self._lock:
            rig = self._require_rig()
            try:
                return int(rig.get_ant(hl.RIG_VFO_CURR))
            except Exception as exc:
                logger.error("Hamlib error getting antenna: %s", exc)
                raise

    def rig_reset(self, reset_signal: str) -> str:
        hl = _hamlib()
        _reset_map = {
            "NONE": hl.RIG_RESET_NONE,
            "SOFTWARE_RESET": hl.RIG_RESET_SOFT,
            "VFO_RESET": hl.RIG_RESET_VFO,
            "MEMORY_CLEAR_RESET": hl.RIG_RESET_MCALL,
            "MASTER_RESET": hl.RIG_RESET_MASTER,
        }
        if reset_signal not in _reset_map:
            logger.error("reset_signal must be one of %s", list(_reset_map))
            raise ValueError(f"Unknown reset signal: {reset_signal!r}")
        with self._lock:
            rig = self._require_rig()
            try:
                rig.reset(_reset_map[reset_signal])
            except Exception as exc:
                logger.error("Hamlib error resetting rig: %s", exc)
                raise
        return ""

"""
ModeTranslator: bidirectional gqrx mode string ↔ Hamlib integer constant.

Composed into each backend instance at construction time.
  - BackendType.GQRX  → passthrough: strings pass through unchanged.
  - BackendType.HAMLIB → full mapping table applied in both directions.

Raises ValueError for any mode with no equivalent on the target backend.
The scan core treats these as retriable errors and skips the channel.
"""

import logging
from typing import Any

from rig_remote.rig_backends.protocol import BackendType

logger = logging.getLogger(__name__)

# Hamlib integer constants for each mode.
# Values are stable across Hamlib versions (defined in hamlib/rig.h).
_RIG_MODE_AM = 1
_RIG_MODE_CW = 2
_RIG_MODE_USB = 4
_RIG_MODE_LSB = 8
_RIG_MODE_RTTY = 16
_RIG_MODE_FM = 32
_RIG_MODE_WFM = 64
_RIG_MODE_CWR = 128
_RIG_MODE_RTTYR = 256
_RIG_MODE_AMS = 512
_RIG_MODE_PKTLSB = 1024
_RIG_MODE_PKTUSB = 2048
_RIG_MODE_PKTFM = 4096
_RIG_MODE_ECSSUSB = 8192
_RIG_MODE_ECSSLSB = 16384
_RIG_MODE_FAX = 32768
_RIG_MODE_SAM = 65536
_RIG_MODE_SAL = 131072
_RIG_MODE_SAH = 262144
_RIG_MODE_DSB = 524288

# gqrx string → Hamlib constant (forward direction, for set_mode)
_GQRX_TO_HAMLIB: dict[str, int] = {
    "AM": _RIG_MODE_AM,
    "FM": _RIG_MODE_FM,
    "WFM": _RIG_MODE_WFM,
    "WFM_ST": _RIG_MODE_WFM,       # stereo→mono: Hamlib has no stereo concept
    "WFM_ST_OIRT": _RIG_MODE_WFM,  # OIRT is a broadcast standard, not an RF mode
    "USB": _RIG_MODE_USB,
    "LSB": _RIG_MODE_LSB,
    "CW": _RIG_MODE_CW,
    "CWR": _RIG_MODE_CWR,
    "CWU": _RIG_MODE_CW,    # alias: Hamlib CW is always upper sideband
    "CWL": _RIG_MODE_CWR,   # alias: Hamlib CWR is lower sideband
    "RTTY": _RIG_MODE_RTTY,
    "RTTYR": _RIG_MODE_RTTYR,
    "AMS": _RIG_MODE_AMS,
    "PKTLSB": _RIG_MODE_PKTLSB,
    "PKTUSB": _RIG_MODE_PKTUSB,
    "PKTFM": _RIG_MODE_PKTFM,
    "ECSSUSB": _RIG_MODE_ECSSUSB,
    "ECSSLSB": _RIG_MODE_ECSSLSB,
    "FAX": _RIG_MODE_FAX,
    "SAM": _RIG_MODE_SAM,
    "SAL": _RIG_MODE_SAL,
    "SAH": _RIG_MODE_SAH,
    "DSB": _RIG_MODE_DSB,
    # SB has no Hamlib equivalent — to_backend("SB") raises ValueError
}

# Hamlib constant → gqrx string (reverse direction, for get_mode)
_HAMLIB_TO_GQRX: dict[int, str] = {
    _RIG_MODE_AM: "AM",
    _RIG_MODE_FM: "FM",
    _RIG_MODE_WFM: "WFM",   # cannot determine stereo from rig; always return mono name
    _RIG_MODE_USB: "USB",
    _RIG_MODE_LSB: "LSB",
    _RIG_MODE_CW: "CW",     # canonical name, not "CWU"
    _RIG_MODE_CWR: "CWR",   # canonical name, not "CWL"
    _RIG_MODE_RTTY: "RTTY",
    _RIG_MODE_RTTYR: "RTTYR",
    _RIG_MODE_AMS: "AMS",
    _RIG_MODE_PKTLSB: "PKTLSB",
    _RIG_MODE_PKTUSB: "PKTUSB",
    _RIG_MODE_PKTFM: "PKTFM",
    _RIG_MODE_ECSSUSB: "ECSSUSB",
    _RIG_MODE_ECSSLSB: "ECSSLSB",
    _RIG_MODE_FAX: "FAX",
    _RIG_MODE_SAM: "SAM",
    _RIG_MODE_SAL: "SAL",
    _RIG_MODE_SAH: "SAH",
    _RIG_MODE_DSB: "DSB",
}


class ModeTranslator:
    """Translates mode representations between the UI and a rig backend.

    Composed into each backend at construction time via the BackendType enum.
    GQRX mode is passthrough; HAMLIB mode applies the full mapping tables.
    """

    def __init__(self, backend: BackendType) -> None:
        self._backend = backend

    def to_backend(self, mode: str) -> Any:
        """Translate a gqrx mode string to the backend representation.

        For GQRX: returns the string unchanged.
        For HAMLIB: returns the Hamlib integer constant.

        :raises ValueError: if the mode has no equivalent for HAMLIB backend.
        """
        if self._backend == BackendType.GQRX:
            return mode
        if mode not in _GQRX_TO_HAMLIB:
            logger.error("Mode %r has no Hamlib equivalent", mode)
            raise ValueError(f"Mode {mode!r} has no Hamlib equivalent")
        return _GQRX_TO_HAMLIB[mode]

    def from_backend(self, value: Any) -> str:
        """Translate a backend mode representation to a gqrx mode string.

        For GQRX: returns the value as a string unchanged.
        For HAMLIB: maps the integer constant back to a gqrx string.

        :raises ValueError: if the Hamlib constant has no gqrx equivalent.
        """
        if self._backend == BackendType.GQRX:
            return str(value)
        if value not in _HAMLIB_TO_GQRX:
            logger.error("Hamlib constant %r has no gqrx equivalent", value)
            raise ValueError(f"Hamlib constant {value!r} has no gqrx equivalent")
        return _HAMLIB_TO_GQRX[value]

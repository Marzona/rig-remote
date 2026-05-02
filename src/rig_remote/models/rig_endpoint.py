"""
RigEndpoint: configuration required to connect to a single rig backend.

Supports two backends:
  - GQRX  — TCP/IP; requires hostname + port.
  - HAMLIB — USB/serial; requires rig_model + serial_port + serial parameters.

Port > 1024 and DNS hostname validation apply to GQRX only.
Hamlib-specific fields are ignored when backend == GQRX.
"""

import logging
from dataclasses import dataclass, field
from socket import gaierror, gethostbyname
from uuid import uuid4

from rig_remote.rig_backends.protocol import BackendType

logger = logging.getLogger(__name__)


@dataclass
class RigEndpoint:
    # Shared fields
    backend: BackendType = BackendType.GQRX
    number: int = 0          # rig slot (0 = unassigned, 1 = rig 1, 2 = rig 2)
    id: str = field(default_factory=lambda: str(uuid4()), compare=False)
    name: str = ""

    # GQRX-specific
    hostname: str = ""
    port: int = 0

    # Hamlib-specific
    rig_model: int = 0
    serial_port: str = ""
    baud_rate: int = 9600
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"

    def __post_init__(self) -> None:
        self._is_valid_number()
        if self.backend == BackendType.GQRX:
            if self.port:
                self._is_valid_port(self.port)
            if self.hostname:
                self._is_valid_hostname(self.hostname)
        if not self.name:
            self.name = self._default_name()

    def _default_name(self) -> str:
        if self.backend == BackendType.GQRX:
            return "gqrx"
        return str(self.rig_model)

    def _is_valid_number(self) -> None:
        self.number = int(self.number)
        if self.number < 0:
            logger.error("rig number must be >= 0, got %i", self.number)
            raise ValueError

    @staticmethod
    def _is_valid_port(port: int) -> None:
        if port <= 1024:
            message = f"Privileged port used: {port}"
            logger.error(message)
            raise ValueError(message)

    @staticmethod
    def _is_valid_hostname(hostname: str) -> None:
        try:
            _ = gethostbyname(hostname)
        except gaierror as e:
            logger.error("Hostname error: %s", e)
            raise ValueError(str(e)) from e

    def set_port(self, port: int) -> None:
        self._is_valid_port(port=port)
        self.port = port

    def set_hostname(self, hostname: str) -> None:
        try:
            self._is_valid_hostname(hostname=hostname)
            self.hostname = hostname
        except ValueError:
            logger.error("invalid hostname provided %s", str(hostname))
            raise

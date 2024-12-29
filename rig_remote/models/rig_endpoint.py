from dataclasses import dataclass

from uuid import uuid4
import logging
from socket import gethostbyname, gaierror

logger = logging.getLogger(__name__)


@dataclass
class RigEndpoint:
    hostname: str
    port: int
    rig_number: int
    id: str = str(uuid4())
    name: str = ""

    def __post_init__(self):
        self._is_valid_port(port=self.port)
        self._is_valid_hostname(hostname=self.hostname)

    @staticmethod
    def _is_valid_port(port: int):
        """Checks if the provided port is a valid one.

        :param: port to connect to
        :raises: ValueError if the string can't be converted to integer and
        if the converted ingeger is lesser than 2014 (privileged port)
        """

        try:
            int(port)
        except ValueError:
            logger.error("Incorrect data: port number must be int.")
            raise
        if int(port) <= 1024:
            logger.error("Privileged port used: %i", port)
            raise ValueError

    @staticmethod
    def _is_valid_hostname(hostname: str):
        """Checks if hostname is truly a valid FQDN, or IP address.

        :param hostname: hostname to validate.
        :type hostname: str
        :raises: ValueError if hostname is empty string
        :raises: Exception based on result of gethostbyname() call
        """

        if hostname == "":
            raise ValueError
        try:
            _ = gethostbyname(hostname)
        except gaierror as e:
            logger.error("Hostname error: %s", e)
            raise ValueError

    def set_port(self, port: int):
        try:
            self._is_valid_port(port=port)
            self.port = port
        except ValueError:
            logger.error("invalid port provided %s", str(port))
            raise

    def set_hostname(self, hostname: str):
        try:
            self._is_valid_hostname(hostname=hostname)
            self.hostname = hostname
        except ValueError:
            logger.error("invalid port provided %s", str(hostname))
            raise

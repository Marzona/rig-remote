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

from dataclasses import dataclass

from uuid import uuid4
import logging
from socket import gethostbyname, gaierror

logger = logging.getLogger(__name__)


@dataclass
class RigEndpoint:
    hostname: str
    port: int
    number: int
    id: str = str(uuid4())
    name: str = ""

    def __post_init__(self):
        self._is_valid_port(port=self.port)
        self._is_valid_hostname(hostname=self.hostname)
        self._is_valid_number()

    def _is_valid_number(self):
        self.number = int(self.number)
        if self.number <= 0:
            logger.error("rig number must be >0, got %i", self.number)
            raise ValueError

    @staticmethod
    def _is_valid_port(port: int):
        """Checks if the provided port is a valid one.

        :param: port to connect to
        :raises: ValueError if the string can't be converted to integer and
        if the converted ingeger is lesser than 2014 (privileged port)
        """
        port = int(port)
        if port <= 1024:
            message = f"Privileged port used: {port}"
            logger.error(message)
            raise ValueError(message)

    @staticmethod
    def _is_valid_hostname(hostname: str):
        """Checks if hostname is truly a valid FQDN, or IP address.

        :param hostname: hostname to validate.
        :raises: ValueError if hostname is empty string
        :raises: Exception based on result of gethostbyname() call
        """

        try:
            _ = gethostbyname(hostname)
        except gaierror as e:
            logger.error("Hostname error: %s", e)
            raise ValueError

    def set_port(self, port: int):
        self._is_valid_port(port=port)
        self.port = port

    def set_hostname(self, hostname: str):
        try:
            self._is_valid_hostname(hostname=hostname)
            self.hostname = hostname
        except ValueError:
            logger.error("invalid port provided %s", str(hostname))
            raise

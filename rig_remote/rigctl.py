#!/usr/bin/env python

"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
"""

import logging
import telnetlib
import socket
from rig_remote.constants import DEFAULT_CONFIG

# logging configuration
logger = logging.getLogger(__name__)

class RigCtl(object):
    """Basic rigctl client implementation."""

    def __init__(self,
                 hostname=DEFAULT_CONFIG["hostname"],
                 port=DEFAULT_CONFIG["port"]):
        self.hostname = hostname
        self.port = port

    def _request(self, request):
        """Main method implementing the rigctl protocol. It's  wrapped by the
        more specific methods that offer the specific functions.

        :param request: string to send through the telnet connection
        :type request: string
        :raises: none
        :returns response: response data
        :response type: string
        """

        logger.info("Connecting the rig at: {}:{}".format(self.hostname,
                                                          self.port))
        try:
            con = telnetlib.Telnet(self.hostname, self.port)
        except socket.timeout:
            logger.error("Time out while connecting to {}:{}".format(self.hostname,
                                                                     self.port))
            raise
        except socket.error:
            logger.exception("Connection refused on {}:{}".format(self.hostname,
                                                                  self.port))
            raise
        con.write(('%s\n' % request).encode('ascii'))
        response = con.read_some().decode('ascii').strip()
        con.write('c\n'.encode('ascii'))
        return response

    def set_frequency(self, frequency):
        """Wrapper around _request. It configures the command for setting
        a frequency.

        """

        try:
            float(frequency)
        except ValueError:
            logger.info("Frequency value must be a float, "\
                        "got {}".format(frequency))
            raise
        return self._request('F %s' % frequency)

    def get_frequency(self):
        """Wrapper around _request. It configures the command for getting
        a frequency.

        """

        output = self._request('f')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting radio frequency, "\
                         "got {}".format(output))
            raise ValueError

        return self._request('f')

    def set_mode(self, mode):
        """Wrapper around _request. It configures the command for setting
        the mode.

        """

        if not isinstance(mode, str):
            logger.info("Frequency value must be a string, "\
                        "got {}".format(mode))
            raise ValueError

        return self._request('M %s' % mode)

    def get_mode(self):
        """Wrapper around _request. It configures the command for getting
        the mode.

        """

        output = self._request('m')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting radio mode, "\
                         "got {}".format(output))
            raise ValueError
        return output

    def start_recording(self):
        """Wrapper around _request. It configures the command for starting
        the recording.

        """

        return self._request('AOS')

    def stop_recording(self):
        """Wrapper around _request. It configures the command for stopping
        the recording.

        """

        return self._request('LOS')

    def get_level(self):
        """Wrapper around _request. It configures the command for getting
        the signal level.

        """

        output = self._request('l')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting radio signal level, "\
                         "got {}".format(output))
            raise ValueError

        return output


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
from rig_remote.constants import DEFAULT_CONFIG

# logging configuration
logger = logging.getLogger(__name__)

class RigCtl(object):
    """Basic rigctl client implementation."""

    def __init__(self, hostname=DEFAULT_CONFIG["hostname"],
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
        con = telnetlib.Telnet(self.hostname, self.port)
        con.write(('%s\n' % request).encode('ascii'))
        response = con.read_some().decode('ascii').strip()
        con.write('c\n'.encode('ascii'))
        return response

    def set_frequency(self, frequency):  #pragma: no cover
        """Wrapper around _request. It configures the command for setting
        a frequency.

        """

        return self._request('F %s' % frequency)

    def get_frequency(self):  #pragma: no cover
        """Wrapper around _request. It configures the command for getting
        a frequency.

        """

        return self._request('f')

    def set_mode(self, mode):  #pragma: no cover
        """Wrapper around _request. It configures the command for setting
        the mode.

        """

        return self._request('M %s' % mode)

    def get_mode(self):  #pragma: no cover
        """Wrapper around _request. It configures the command for getting
        the mode.

        """

        return self._request('m')

    def start_recording(self):  #pragma: no cover
        """Wrapper around _request. It configures the command for starting
        the recording.

        """

        return self._request('AOS')

    def stop_recording(self):  #pragma: no cover
        """Wrapper around _request. It configures the command for stopping
        the recording.

        """

        return self._request('LOS')

    def get_level(self):  #pragma: no cover
        """Wrapper around _request. It configures the command for getting
        the signal level.

        """

        return self._request('l')


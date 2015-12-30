#!/usr/bin/env python

"""
Remote application that interacts with gqrx using rigctl protocol.
Gqrx partially implements rigctl since version 2.3.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo <rafael@defying.me>
License: MIT License

Copyright (c) 2014 Rafael Marmelo
"""

import logging
import os.path
import telnetlib

# logging configuration
logger = logging.getLogger(__name__)

class RigCtl(object):
    """Basic rigctl client implementation."""

    def __init__(self, hostname='127.0.0.1', port=7356):
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

        con = telnetlib.Telnet(self.hostname, self.port)
        con.write(('%s\n' % request).encode('ascii'))
        response = con.read_some().decode('ascii').strip()
        con.write('c\n'.encode('ascii'))
        return response

    def set_frequency(self, frequency):
        """Wrapper around _request. It configures the command for setting
        a frequency.

        """

        return self._request('F %s' % frequency)

    def get_frequency(self):
        """Wrapper around _request. It configures the command for getting
        a frequency.

        """

        return self._request('f')

    def set_mode(self, mode):
        """Wrapper around _request. It configures the command for setting
        the mode.

        """

        return self._request('M %s' % mode)

    def get_mode(self):
        """Wrapper around _request. It configures the command for getting
        the mode.

        """

        return self._request('m')


    def get_level(self):
        """Wrapper around _request. It configures the command for getting
        the signal level.

        """

        return self._request('l')


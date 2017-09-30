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
from rig_remote.constants import (
#                                 DEFAULT_CONFIG,
                                 ALLOWED_VFO_COMMANDS,
                                 ALLOWED_SPLIT_MODES,
                                 ALLOWED_PARM_COMMANDS,
                                 ALLOWED_FUNC_COMMANDS,
                                 RESET_CMD_DICT,
                                 ALLOWED_RIGCTL_MODES,
                                 RIG_TIMEOUT,
                                 )

# logging configuration
logger = logging.getLogger(__name__)


# classes definition
class RigCtl(object):
    """Basic rigctl client implementation."""

    def __init__(self, target):
        """implements the rig.


        :param target: rig uri data
        :type target: dict created from build_rig_uri
        :raises TypeError: if the target is not a dict of 3 keys
        """

        if not isinstance(target, dict) or not len(target.keys()) == 3:
            logger.error("target is not of type dict "
                         "but {}".format(type(target)))
            raise TypeError
        self.target = target

    def _request(self, request, target=None):
        """Main method implementing the rigctl protocol. It's  wrapped by the
        more specific methods that offer the specific functions.

        :param request: string to send through the telnet connection
        :type request: string
        :raises: none
        :returns response: response data
        :response type: string
        """

        if not target:
            target = self.target

        try:
            con = telnetlib.Telnet(target["hostname"],
                                   target["port"],
                                   RIG_TIMEOUT)
        except socket.timeout:

            logger.error("Time out while connecting to {}:{}".format(target["hostname"],
                                                                     ["port"]))
            raise
        except socket.error:
            logger.exception("Connection refused on {}:{}".format(["hostname"],
                                                                  ["port"]))
            raise

        con.write(('%s\n' % request).encode('ascii'))
        response = con.read_some().decode('ascii').strip()
        con.write('c\n'.encode('ascii'))
        return response

    def set_frequency(self, frequency, target=None):
        """Wrapper around _request. It configures the command for setting
        a frequency.

        """

        try:
            float(frequency)
        except ValueError:
            logger.error("Frequency value must be a float, "
                         "got {}".format(frequency))
            raise
        return self._request('F %s' % frequency, target)

    def get_frequency(self, target=None):
        """Wrapper around _request. It configures the command for getting
        a frequency.

        """
        output = self._request('f')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting radio "
                         "frequency, got {}".format(output))
            raise ValueError

        return self._request('f', target)

    def set_mode(self, mode, target=None):
        """Wrapper around _request. It configures the command for setting
        the mode.

        """
        if not isinstance(mode, str) or mode not in ALLOWED_RIGCTL_MODES:

            logger.error("Frequency mode must be a string in {}, "\
                        "got {}".format(ALLOWED_RIGCTL_MODES, mode))
            raise ValueError
        return self._request('M %s' % mode, target)

    def get_mode(self, target=None):
        """Wrapper around _request. It configures the command for getting
        the mode.

        """
        # older versions of gqrx replies with only the mode (u'WFM_ST' as an example)
        # newer versions replie with something like u'WFM_ST\n160000'
        if "\n" in self._request('m'):
            output = self._request('m').split("\n")[0]
        else:
            output = self._request('m')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting radio mode, "
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
            logger.error("Expected unicode string while getting radio "
                         "signal level, got {}".format(output))
            raise ValueError

        return output

    def set_vfo(self, vfo):
        """Wrapper around _request. It configures the command for setting
        VFO.

        """

        if vfo not in ALLOWED_VFO_COMMANDS:
            logger.error("VFO value must be a string inclueded in {}, "
                         "got {}".format(ALLOWED_VFO_COMMANDS, vfo))
            raise ValueError

        return self._request('V %s' % vfo)

    def get_vfo(self):
        """Wrapper around _request. It configures the command for getting
        VFO.

        """

        output = self._request('v')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting VFO, "
                         "got {}".format(output))
            raise ValueError

        return output

    def set_rit(self, rit):
        """Wrapper around _request. It configures the command for getting
        RIT.

        """

        if not isinstance(rit, int):
            logger.error("RIT value must be an int, "
                         "got {}".format(type(rit)))
            raise ValueError

        return self._request('J %s' % rit)

    def get_rit(self):
        """Wrapper around _request. It configures the command for getting
        RIT.

        """

        output = self._request('j')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting RIT, "
                         "got {}".format(type(output)))
            raise ValueError

        return output

    def set_xit(self, xit):
        """Wrapper around _request. It configures the command for getting
        XIT.

        """

        if not isinstance(xit, basestring):
            logger.error("XIT value must be a string, "
                         "got {}".format(type(xit)))
            raise ValueError

        return self._request('J %s' % xit)

    def get_xit(self):
        """Wrapper around _request. It configures the command for getting
        XIT.

        """

        output = self._request('j')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting XIT, "
                         "got {}".format(type(output)))
            raise ValueError

        return output

    def set_split_freq(self, split_freq):
        """Wrapper around _request. It configures the command for setting
        split frequency.

        """

        if not isinstance(split_freq, int):
            logger.error("XIT value must be an integer, "
                         "got {}".format(type(split_freq)))
            raise ValueError

        return self._request('I %s' % split_freq)

    def get_split_freq(self):
        """Wrapper around _request. It configures the command for getting
        XIT.

        """

        output = self._request('i')
        if not isinstance(output, int):
            logger.error("Expected int while getting split_frequency, "
                         "got {}".format(type(output)))
            raise ValueError

        return output

    def set_split_mode(self, split_mode):
        """Wrapper around _request. It configures the command for setting
        slit frequency.

        """

        if split_mode not in ALLOWED_SPLIT_MODES:
            logger.error("split_mode value must be a string in {}, "
                         "got {}".format(ALLOWED_SPLIT_MODES,
                                         type(split_mode)))
            raise ValueError

        return self._request('X %s' % split_mode)

    def get_split_mode(self):
        """Wrapper around _request. It configures the command for getting
        the split mode.

        """

        output = self._request('x')
        if not isinstance(output, str):
            logger.error("Expected string while getting split_frequency_mode, "
                         "got {}".format(type(output)))
            raise ValueError

        return output

    def set_func(self, func):
        """Wrapper around _request. It configures the command for getting
        func.

        """

        if func not in ALLOWED_FUNC_COMMANDS:
            logger.error("func value must be a string inclueded in {}, "
                         "got {}".format(ALLOWED_FUNC_COMMANDS, func))
            raise ValueError

        return self._request('U %s' % func)

    def get_func(self):
        """Wrapper around _request. It configures the command for getting
        func.

        """

        output = self._request('u')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting func, "
                         "got {}".format(output))
            raise ValueError
        return output

    def set_parm(self, parm):
        """Wrapper around _request. It configures the command for getting
        parm.

        """

        if parm not in ALLOWED_PARM_COMMANDS:
            logger.error("parm value must be a string inclueded in {}, "
                         "got {}".format(ALLOWED_PARM_COMMANDS, parm))
            raise ValueError
        return self._request('P %s' % parm)

    def get_parm(self):
        """Wrapper around _request. It configures the command for getting
        parm.

        """

        output = self._request('p')
        if not isinstance(output, basestring):
            logger.error("Expected unicode string while getting parm, "
                         "got {}".format(output))
            raise ValueError

        return output

    def set_antenna(self, antenna):
        """Wrapper around _request. It configures the command for setting
        an antenna.

        """

        if not isinstance(antenna, int):
            logger.error("antenna value must be an int, "
                         "got {}".format(antenna))
            raise ValueError

        return self._request('Y %s' % antenna)

    def get_antenna(self):
        """Wrapper around _request. It configures the command for getting
        the antenna in use.

        """

        output = self._request('f')
        if not isinstance(output, int):
            logger.error("Expected integer while getting radio antenna, "
                         "got {}".format(output))
            raise ValueError

        return self._request('y')

    def rig_reset(self, reset_signal):
        """Wrapper around _request. It configures the command for resetting
        the rig with various levels 0  =  None,  1 = Software reset,
        2 = VFO reset, 4 = Memory Clear reset, 8 = Master reset.

        """

        if reset_signal not in RESET_CMD_DICT.keys():
            logger.error("Reset_signal must be one of "
                         "{}.".format(RESET_CMD_DICT.keys()))
            raise ValueError

        return self._request('* %s' % reset_signal)

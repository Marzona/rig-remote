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
Copyright (c) 2016 Tim Sweeney
TAS - Tim Sweeney - mainetim@gmail.com
2016/05/04 - TAS - Moved frequency_pp and frequency_pp_parse here.
2016/05/07 - TAS - Moved is_valid_hostname and is_valid_port here.
2016/05/08 - TAS - Added this_file_exists.
"""


import re
from socket import gethostbyname
import logging


logger = logging.getLogger(__name__)

def frequency_pp(frequency):
    """Filter invalid chars and add thousands separator.
    :param frequency: frequency value
    :type frequency: string
    :return: frequency with separator
    :return type: string
    """

    return '{:,}'.format(int(re.sub("[^0-9]", '', frequency)))


def frequency_pp_parse(frequency):
    """Remove thousands separator and check for invalid chars.
    :param frequency: frequency value
    :type frequency: string
    :return: frequency without separator or None if invalid chars present
    :return type: string or None
    """

    nocommas = frequency.replace(',', '')
    results = re.search("[^0-9]", nocommas)
    if results == None:
        return (nocommas)
    else:
        return (None)


def is_valid_port(port):
    """Checks if the provided port is a valid one.
    :param: port to connect to
    :type port: str as provided by tkinter
    :raises: ValueError if the string can't be converted to integer and
    if the converted ingeger is lesser than 2014 (privileged port)
    """

    try:
        int(port)
    except ValueError:
        logger.error("Incorrect data: port number must be int.")
        raise
    if int(port) <= 1024:
        logger.error("Privileged port used: {}".format(port))
        raise ValueError

def is_valid_hostname(hostname):
    """ Checks if hostname is truly a valid FQDN, or IP address.
    :param hostname:
    :type hostname: str
    :raises: ValueError if hostname is empty string
    :raises: Exception based on result of gethostbyname() call
    """

    if hostname == '':
        raise ValueError
    try:
        address = gethostbyname(hostname)
    except Exception as e:
        logger.error("Hostname error: {}".format(e))
        raise

def this_file_exists(filename):
    """Test if a file will open.
    :param filename:
    :type filename: str
    :returns: filename if open was successful, None otherwise
    """
    try:
        with open(filename) as f:
            f.close()
            return(filename)
    except IOError:
        return None

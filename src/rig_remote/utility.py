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
TAS - Tim Sweeney - mainetim@gmail.com
"""

import logging


logger = logging.getLogger(__name__)


def khertz_to_hertz(value: int) -> int:
    """Convert a kilohertz frequency value to hertz.

    :param value: frequency in kilohertz
    :return: frequency in hertz
    """
    if not isinstance(value, int):
        logger.error("khertz_to_hertz: value must be an integer, got %s", type(value))  # type: ignore[unreachable]
        raise TypeError("value must be an integer")
    return value * 1000

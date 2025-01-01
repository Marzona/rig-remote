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

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class ModulationModes(StrEnum):
    WFM_ST_OIRT = "WFM_ST_OIRT"
    AMS = "AMS"
    CWU = "CWU"
    USB = "USB"
    CWL = "CWL"
    LSB = "LSB"
    CW = "CW"
    CWR = "CWR"
    RTTY = "RTTY"
    RTTYR = "RTTYR"
    AM = "AM"
    FM = "FM"
    WFM = "WFM"
    PKTLSB = "PKTLSB"
    PKTU = "PKTU"
    SB = "SB"
    PKTFM = "PKTFM"
    ECSSUSB = "ECSSUSB"
    ECSSLSB = "ECSSLSB"
    WFM_ST = "WFM_ST"
    FAX = "FAX"
    SAM = "SAM"
    SAL = "SAL"
    SAH = "SAH"
    DSB = "DSB"

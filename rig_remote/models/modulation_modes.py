#!/usr/bin/env python

from dataclasses import dataclass
import logging



logger = logging.getLogger(__name__)

from enum import StrEnum
class ModulationModes(StrEnum):
    WFM_ST_OIRT = "WFM_ST_OIRT"
    AMS= "AMS"
    CWU= "CWU"
    USB= "USB"
    CWL= "CWL"
    LSB= "LSB"
    CW= "CW"
    CWR= "CWR"
    RTTY= "RTTY"
    RTTYR= "RTTYR"
    AM= "AM"
    FM= "FM"
    WFM= "WFM"
    PKTLSB="PKTLSB"
    # "PKTU"=
    # "SB"=
    # "PKTFM"=
    # "ECSSUSB"=
    # "ECSSLSB"=
    # "WFM_ST"=
    # "FAX"=
    # "SAM"=
    # "SAL"=
    # "SAH"=
    # "DSB"=
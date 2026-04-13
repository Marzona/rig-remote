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
"""

import logging
import socket
from logging import Logger
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.models.modulation_modes import ModulationModes

logger: Logger = logging.getLogger(__name__)


class RigCtl:
    SUPPORTED_MODULATION_MODES = ModulationModes
    _RESET_CMD_DICT = {
        "NONE": 0,
        "SOFTWARE_RESET": 1,
        "VFO_RESET": 2,
        "MEMORY_CLEAR_RESET": 4,
        "MASTER_RESET": 8,
    }
    _ALLOWED_FUNC_COMMANDS = [
        "FAGC",
        "NB",
        "COMP",
        "VOX",
        "TONE",
        "TSQL",
        "SBKIN",
        "FBKIN",
        "ANF",
        "NR",
        "AIP",
        "APF",
        "MON",
        "MN",
        "RF",
        "ARO",
        "LOCK",
        "MUTE",
        "VSC",
        "REV",
        "SQL",
        "ABM",
        "BC",
        "MBC",
        "AFC",
        "SATMODE",
        "SCOPE",
        "RESUME",
        "TBURST",
        "TUNER",
    ]
    _ALLOWED_PARM_COMMANDS = [
        "ANN",
        "APO",
        "BACKLIGHT",
        "BEEP",
        "TIME",
        "BAT",
        "KEYLIGHT",
    ]
    _ALLOWED_SPLIT_MODES = [
        "AM",
        "FM",
        "CW",
        "CWR",
        "USB",
        "LSB",
        "RTTY",
        "RTTYR",
        "WFM",
        "AMS",
        "PKTLSB",
        "PKTUSB",
        "PKTFM",
        "ECSSUSB",
        "ECSSLSB",
        "FAX",
        "SAM",
        "SAL",
        "SAH",
        "DSB",
    ]
    _ALLOWED_VFO_COMMANDS = [
        "VFOA",
        "VFOB",
        "VFOC",
        "currVFO",
        "VFO",
        "MEM",
        "Main",
        "Sub",
        "TX",
        "RX",
    ]

    def __init__(self, endpoint: RigEndpoint):
        """Basic rigctl client implementation.

        :param endpoint: rig uri data
        :raises TypeError: if the endpoint is not a dict of 3 keys
        """

        self.endpoint = endpoint

    def _send_message(self, request: str) -> str:
        """sends messages through the socket

        :param request: message to be sent to the rig endpoint
        :return: response from the rig endpoint
        """
        rig_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rig_socket.settimeout(5.0)

        logger.info(
            "sending : %s to endpoint %s, %i",
            request,
            self.endpoint.hostname,
            self.endpoint.port,
        )
        request = f"{request}\n"

        try:
            rig_socket.connect((self.endpoint.hostname, self.endpoint.port))
            rig_socket.sendall(bytearray(request.encode()))
            response = rig_socket.recv(1024)
            rig_socket.close()
        except TimeoutError:
            logger.error(
                "Time out while connecting to %s %s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
        except OSError:
            logger.exception(
                "Connection refused on %s %s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
        logger.info(
            "received %s from endpoint %s %s",
            response,
            self.endpoint.hostname,
            self.endpoint.port,
        )
        return str(response.decode())

    def set_frequency(self, frequency: float) -> None:
        """Wrapper around _request. It configures the command for setting
        a frequency.

        """

        try:
            float(frequency)
        except ValueError:
            logger.error("Frequency value must be a float, got %s", frequency)
            raise
        self._send_message(request=f"F {frequency}")

    def get_frequency(self) -> float:
        """Wrapper around _request. It configures the command for getting
        a frequency.

        """
        output = self._send_message("f")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return float(output)

    def set_mode(self, mode: str) -> None:
        """Wrapper around _request. It configures the command for setting
        the mode.

        """
        if not isinstance(mode, str):
            logger.error("Expected unicode string while setting modulation mode, got %s", mode)  # type: ignore[unreachable]
            raise ValueError
        self._send_message(request=f"M {mode}")

    def get_mode(self) -> str:
        """Wrapper around _request. It configures the command for getting
        the mode.

        """
        # older versions of gqrx replies with only the mode (u'WFM_ST' as an example)
        # newer versions replies with something like u'WFM_ST\n160000'
        output_message = self._send_message(request="m")
        if not isinstance(output_message, str):
            raise ValueError(f"Expected string response, got {type(output_message)}")
        output = output_message
        if "\n" in output_message:
            output = output_message.split("\n")[0]

        return output

    def start_recording(self) -> str:
        """Wrapper around _request. It configures the command for starting
        the recording.

        """

        return self._send_message(request="AOS")

    def stop_recording(self) -> str:
        """Wrapper around _request. It configures the command for stopping
        the recording.

        """

        return self._send_message(request="LOS")

    def get_level(self) -> float:
        """Wrapper around _request. It configures the command for getting
        the signal level.

        """

        output = self._send_message(request="l")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return float(output.strip())

    def set_vfo(self, vfo: str) -> str:
        """Wrapper around _request. It configures the command for setting
        VFO.

        """

        if vfo not in self._ALLOWED_VFO_COMMANDS:
            logger.error(
                "VFO value must be a string included in %s, got %s",
                self._ALLOWED_VFO_COMMANDS,
                vfo,
            )
            raise ValueError
        return self._send_message(f"V {vfo}")

    def get_vfo(self) -> str:
        """Wrapper around _request. It configures the command for getting
        VFO.

        """

        output = self._send_message("v")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_rit(self, rit: int) -> str:
        """Wrapper around _request. It configures the command for getting
        RIT.

        """

        if not isinstance(rit, int):
            logger.error("RIT value must be an int, got %s", type(rit))  # type: ignore[unreachable]
            raise ValueError
        return self._send_message(f"J {rit}")

    def get_rit(self) -> str:
        """Wrapper around _request. It configures the command for getting
        RIT.

        """

        output = self._send_message("j")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_xit(self, xit: str) -> str:
        """Wrapper around _request. It configures the command for getting
        XIT.

        """

        if not isinstance(xit, str):
            logger.error("XIT value must be a string, got %s", type(xit))  # type: ignore[unreachable]
            raise ValueError
        return self._send_message(f"J {xit}")

    def get_xit(self) -> str:
        """Wrapper around _request. It configures the command for getting
        XIT.

        """

        output = self._send_message("j")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_split_freq(self, split_freq: int) -> str:
        """Wrapper around _request. It configures the command for setting
        split frequency.

        """

        if not isinstance(split_freq, int):
            logger.error("XIT value must be an integer, got %s", type(split_freq))  # type: ignore[unreachable]
            raise ValueError
        return self._send_message(f"I {split_freq}")

    def get_split_freq(self) -> int:
        """Wrapper around _request. It configures the command for getting
        XIT.

        """
        try:
            output = self._send_message("i")
            int_output = int(output)
        except (ValueError, TypeError):
            logger.error("Expected int while getting split_frequency, got %s", type(output))
            raise

        return int_output

    def set_split_mode(self, split_mode: str) -> str:
        """Wrapper around _request. It configures the command for setting
        slit frequency.

        """

        if split_mode not in self._ALLOWED_SPLIT_MODES:
            logger.error(
                "split_mode value must be a string in %s, got %s",
                self._ALLOWED_SPLIT_MODES,
                type(split_mode),
            )
            raise ValueError

        return self._send_message(f"X {split_mode}")

    def get_split_mode(self) -> str:
        """Wrapper around _request. It configures the command for getting
        the split mode.

        """

        output = self._send_message("x")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_func(self, func: str) -> str:
        """Wrapper around _request. It configures the command for getting
        func.

        """

        if func not in self._ALLOWED_FUNC_COMMANDS:
            logger.error(
                "func value must be a string inclueded in %s, got %s",
                self._ALLOWED_FUNC_COMMANDS,
                func,
            )
            raise ValueError

        return self._send_message(f"U {func}")

    def get_func(self) -> str:
        """Wrapper around _request. It configures the command for getting
        func.

        """

        output = self._send_message("u")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_parm(self, parm: str) -> str:
        """Wrapper around _request. It configures the command for getting
        parm.

        """

        if parm not in self._ALLOWED_PARM_COMMANDS:
            logger.error(
                "parm value must be a string included in %s, got %s ",
                self._ALLOWED_PARM_COMMANDS,
                parm,
            )
            raise ValueError
        return self._send_message(f"P {parm}")

    def get_parm(self) -> str:
        """Wrapper around _request. It configures the command for getting
        parm.

        """

        output = self._send_message("p")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_antenna(self, antenna: int) -> str:
        """Wrapper around _request. It configures the command for setting
        an antenna.

        """

        if not isinstance(antenna, int):
            logger.error("antenna value must be an int, got %s", antenna)  # type: ignore[unreachable]
            raise ValueError
        return self._send_message(f"Y {antenna}")

    def get_antenna(self) -> int:
        """Wrapper around _request. It configures the command for getting
        the antenna in use.

        """

        output = self._send_message("y")
        try:
            return int(output)
        except ValueError:
            logger.error("Expected integer while getting radio antenna, got %s", output)
            raise

    def rig_reset(self, reset_signal: str) -> str:
        """Wrapper around _request. It configures the command for resetting
        the rig with various levels 0  =  None,  1 = Software reset,
        2 = VFO reset, 4 = Memory Clear reset, 8 = Master reset.

        """

        if reset_signal not in self._RESET_CMD_DICT:
            logger.error("Reset_signal must be one of %s", self._RESET_CMD_DICT.keys())
            raise ValueError

        return self._send_message(f"* {self._RESET_CMD_DICT[reset_signal]}")

"""
GQRXRigCtl: GQRX/rigctl TCP backend.

Opens a new TCP socket per command (connect → send → read → close).
This is intentional: gqrx is single-request-per-connection, and the
per-call model protects against flaky network conditions without any
reconnect logic.

Fixes applied relative to the original RigCtl class:
  - set_frequency / get_frequency use int Hz (not float).
  - get_level returns int (dB × 10 units).
  - set_xit / get_xit use rigctl commands Z / z (not J / j, which is RIT).
  - set_xit parameter is int Hz (same as set_rit).
"""

import logging
import socket
from logging import Logger

from rig_remote.models.modulation_modes import ModulationModes
from rig_remote.models.rig_endpoint import RigEndpoint
from rig_remote.rig_backends.mode_translator import ModeTranslator
from rig_remote.rig_backends.protocol import BackendType

logger: Logger = logging.getLogger(__name__)


class GQRXRigCtl:
    SUPPORTED_MODULATION_MODES = ModulationModes
    _RESET_CMD_DICT = {
        "NONE": 0,
        "SOFTWARE_RESET": 1,
        "VFO_RESET": 2,
        "MEMORY_CLEAR_RESET": 4,
        "MASTER_RESET": 8,
    }
    _ALLOWED_FUNC_COMMANDS = [
        "FAGC", "NB", "COMP", "VOX", "TONE", "TSQL", "SBKIN", "FBKIN",
        "ANF", "NR", "AIP", "APF", "MON", "MN", "RF", "ARO", "LOCK",
        "MUTE", "VSC", "REV", "SQL", "ABM", "BC", "MBC", "AFC",
        "SATMODE", "SCOPE", "RESUME", "TBURST", "TUNER",
    ]
    _ALLOWED_PARM_COMMANDS = [
        "ANN", "APO", "BACKLIGHT", "BEEP", "TIME", "BAT", "KEYLIGHT",
    ]
    _ALLOWED_SPLIT_MODES = [
        "AM", "FM", "CW", "CWR", "USB", "LSB", "RTTY", "RTTYR", "WFM",
        "AMS", "PKTLSB", "PKTUSB", "PKTFM", "ECSSUSB", "ECSSLSB",
        "FAX", "SAM", "SAL", "SAH", "DSB",
    ]
    _ALLOWED_VFO_COMMANDS = [
        "VFOA", "VFOB", "VFOC", "currVFO", "VFO", "MEM", "Main", "Sub", "TX", "RX",
    ]

    def __init__(
        self,
        endpoint: RigEndpoint,
        mode_translator: ModeTranslator | None = None,
    ) -> None:
        self.endpoint = endpoint
        self._translator = mode_translator or ModeTranslator(BackendType.GQRX)

    def _send_message(self, request: str) -> str:
        rig_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rig_socket.settimeout(5.0)
        logger.info(
            "sending: %s to endpoint %s:%i",
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
                "Timeout connecting to %s:%s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
        except OSError:
            logger.exception(
                "Connection error on %s:%s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
        logger.info(
            "received %s from %s:%s",
            response,
            self.endpoint.hostname,
            self.endpoint.port,
        )
        return str(response.decode())

    def set_frequency(self, frequency: int) -> None:
        try:
            freq = int(frequency)
        except (TypeError, ValueError):
            logger.error("Bad frequency parameter: %r", frequency)
            raise ValueError(f"Invalid frequency: {frequency!r}") from None
        self._send_message(request=f"F {freq}")

    def get_frequency(self) -> int:
        output = self._send_message("f")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return int(float(output))

    def set_mode(self, mode: str) -> None:
        backend_mode = self._translator.to_backend(mode)
        self._send_message(request=f"M {backend_mode}")

    def get_mode(self) -> str:
        output_message = self._send_message(request="m")
        if not isinstance(output_message, str):
            raise ValueError(f"Expected string response, got {type(output_message)}")
        raw = output_message.split("\n")[0] if "\n" in output_message else output_message
        return self._translator.from_backend(raw)

    def start_recording(self) -> str:
        return self._send_message(request="AOS")

    def stop_recording(self) -> str:
        return self._send_message(request="LOS")

    def get_level(self) -> int:
        output = self._send_message(request="l")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return int(float(output.strip()))

    def set_vfo(self, vfo: str) -> str:
        if vfo not in self._ALLOWED_VFO_COMMANDS:
            logger.error(
                "VFO value must be in %s, got %s",
                self._ALLOWED_VFO_COMMANDS,
                vfo,
            )
            raise ValueError
        return self._send_message(f"V {vfo}")

    def get_vfo(self) -> str:
        output = self._send_message("v")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_rit(self, rit: int) -> str:
        return self._send_message(f"J {rit}")

    def get_rit(self) -> str:
        output = self._send_message("j")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_xit(self, xit: int) -> str:
        return self._send_message(f"Z {xit}")

    def get_xit(self) -> str:
        output = self._send_message("z")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_split_freq(self, split_freq: int) -> str:
        return self._send_message(f"I {split_freq}")

    def get_split_freq(self) -> int:
        try:
            output = self._send_message("i")
            return int(output)
        except (ValueError, TypeError):
            logger.error("Expected int while getting split_frequency, got %s", type(output))
            raise

    def set_split_mode(self, split_mode: str) -> str:
        if split_mode not in self._ALLOWED_SPLIT_MODES:
            logger.error(
                "split_mode must be in %s, got %s",
                self._ALLOWED_SPLIT_MODES,
                type(split_mode),
            )
            raise ValueError
        return self._send_message(f"X {split_mode}")

    def get_split_mode(self) -> str:
        output = self._send_message("x")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_func(self, func: str) -> str:
        if func not in self._ALLOWED_FUNC_COMMANDS:
            logger.error(
                "func must be in %s, got %s",
                self._ALLOWED_FUNC_COMMANDS,
                func,
            )
            raise ValueError
        return self._send_message(f"U {func}")

    def get_func(self) -> str:
        output = self._send_message("u")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_parm(self, parm: str) -> str:
        if parm not in self._ALLOWED_PARM_COMMANDS:
            logger.error(
                "parm must be in %s, got %s",
                self._ALLOWED_PARM_COMMANDS,
                parm,
            )
            raise ValueError
        return self._send_message(f"P {parm}")

    def get_parm(self) -> str:
        output = self._send_message("p")
        if not isinstance(output, str):
            raise ValueError(f"Expected string response, got {type(output)}")
        return output

    def set_antenna(self, antenna: int) -> str:
        return self._send_message(f"Y {antenna}")

    def get_antenna(self) -> int:
        output = self._send_message("y")
        try:
            return int(output)
        except ValueError:
            logger.error("Expected integer while getting antenna, got %s", output)
            raise

    def rig_reset(self, reset_signal: str) -> str:
        if reset_signal not in self._RESET_CMD_DICT:
            logger.error("reset_signal must be one of %s", self._RESET_CMD_DICT.keys())
            raise ValueError
        return self._send_message(f"* {self._RESET_CMD_DICT[reset_signal]}")

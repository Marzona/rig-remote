"""
Shared gqrx endpoint configuration for functional tests.

Import this module in any test that connects to a live gqrx instance.
"""

import socket

_GQRX_HOST = "127.0.0.1"
_GQRX_PORT = 7356
# Seconds to wait after set_frequency / set_mode before reading back.
_SETTLE_S = 0.3
# Maximum attempts to read back the expected value before declaring a mismatch.
_MAX_READBACK_RETRIES = 5


def _gqrx_reachable() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((_GQRX_HOST, _GQRX_PORT))
        s.close()
        return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False

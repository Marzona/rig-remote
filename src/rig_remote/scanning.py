"""
Scanning module — composition facade and factory.

Design:
    ScanningConfig           — dataclass holding all tuning/signal constants.
                               Defined in scanning_config.py.
    ScannerCore              — shared low-level primitives (tune, signal check,
                               queue management) composed into both strategies.
                               Defined in scanner_core.py.
    BookmarkScannerStrategy  — bookmark-scan strategy, composed with ScannerCore.
                               Defined in bookmark_scanner_strategy.py.
    FrequencyScannerStrategy — frequency-scan strategy, composed with ScannerCore;
                               owns prev-level/freq bookmarking state.
                               Defined in frequency_scanner_strategy.py.
    Scanning2                — public facade; owns the LogFile lifecycle and
                               delegates scan() / terminate() to the strategy.
    create_scanner()         — factory: accepts scan_mode + dependencies,
                               builds ScannerCore, wraps it in the right strategy,
                               returns a ready Scanning2 instance.
"""

import logging
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from rig_remote.bookmark_scanner_strategy import BookmarkScannerStrategy
from rig_remote.disk_io import LogFile
from rig_remote.frequency_scanner_strategy import FrequencyScannerStrategy
from rig_remote.models.scanning_task import ScanningTask
from rig_remote.rigctl import RigCtl
from rig_remote.scanner_core import ScannerCore
from rig_remote.scanning_config import ScanningConfig
from rig_remote.stmessenger import STMessenger

logger = logging.getLogger(__name__)

# Re-export for callers that import directly from this module.
__all__ = [
    "ScanningConfig",
    "ScannerCore",
    "ScannerStrategy",
    "BookmarkScannerStrategy",
    "FrequencyScannerStrategy",
    "Scanning2",
    "create_scanner",
]


# ---------------------------------------------------------------------------
# Scanner strategy protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ScannerStrategy(Protocol):
    """Structural interface every scanner strategy must satisfy."""

    def scan(self, task: ScanningTask, log: LogFile) -> ScanningTask:
        """Execute a full scan and return the (possibly mutated) task.

        :param task: The scanning task describing range, mode, and options.
        :param log: Open LogFile to write activity records into.
        :returns: The ScanningTask after the scan completes.
        """
        ...

    def terminate(self) -> None:
        """Signal the strategy to stop scanning at the next safe opportunity."""
        ...


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------

class Scanning2:
    """Public facade.

    Owns the LogFile lifecycle (open before delegating, close after).
    Delegates scan() and terminate() to the injected strategy.
    """

    def __init__(
        self,
        scanner: ScannerStrategy,
        log: LogFile,
        log_filename: str,
    ) -> None:
        """Initialise the facade with its strategy and log configuration.

        :param scanner: A ScannerStrategy implementation (BookmarkScannerStrategy
            or FrequencyScannerStrategy) to delegate scan work to.
        :param log: LogFile instance whose lifecycle this facade manages.
        :param log_filename: Path to the activity log file; passed to
            ``log.open()`` when ``task.log`` is True.
        """
        self._scanner = scanner
        self._log = log
        self._log_filename = log_filename

    def terminate(self) -> None:
        """Delegate termination to the underlying scanner strategy."""
        self._scanner.terminate()

    def scan(self, task: ScanningTask) -> None:
        """Open the log (if requested), run the scan, then close the log.

        :param task: ScanningTask driving the scan; its ``log`` flag controls
            whether the LogFile is opened and closed around the scan.
        :raises IOError: If ``task.log`` is True and the log file cannot be
            opened.
        """
        if task.log:
            logger.info("Opening scan log: %s", self._log_filename)
            try:
                self._log.open(self._log_filename)
            except OSError:
                logger.exception("Could not open log file.")
                raise

        logger.info("Starting scan, mode: %s", task.scan_mode)
        self._scanner.scan(task, self._log)

        if task.log:
            self._log.close()
            logger.info("Scan log closed.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_SCANNER_REGISTRY: dict[str, Callable[[ScannerCore], ScannerStrategy]] = {
    "bookmarks": BookmarkScannerStrategy,
    "frequency": FrequencyScannerStrategy,
}


def create_scanner(
    scan_mode: str,
    scan_queue: STMessenger,
    log_filename: str,
    rigctl: RigCtl,
    config: ScanningConfig | None = None,
    log: LogFile | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> Scanning2:
    """Factory — returns a fully composed Scanning2 for *scan_mode*.

    Looks up the strategy class in ``_SCANNER_REGISTRY``, builds a
    ScannerCore from the supplied dependencies, wraps it in the chosen
    strategy, and returns a ready-to-use Scanning2 facade.

    :param scan_mode: Scanning mode string — ``"bookmarks"`` or
        ``"frequency"`` (case-insensitive).
    :param scan_queue: Inter-thread messenger between the UI thread and the
        scan thread, used to deliver parameter updates during a scan.
    :param log_filename: Path to the activity log file passed to
        ``Scanning2``.
    :param rigctl: RigCtl instance for the radio hardware being scanned.
    :param config: Optional ScanningConfig; a default ScanningConfig() is
        used when not provided.
    :param log: Optional LogFile; a fresh LogFile() is created when not
        provided.
    :param sleep_fn: Optional sleep callable injected into ScannerCore;
        pass a no-op lambda in tests to eliminate wall-time delays.
    :returns: A fully composed Scanning2 instance ready to call ``scan()``.
    :raises ValueError: If *scan_mode* is not a recognised mode.
    """
    strategy_cls = _SCANNER_REGISTRY.get(scan_mode.lower())
    if strategy_cls is None:
        raise ValueError(
            f"Unsupported scan_mode {scan_mode!r}. "
            f"Supported modes: {list(_SCANNER_REGISTRY)}"
        )

    resolved_config = config or ScanningConfig()
    resolved_log = log or LogFile()

    core = ScannerCore(
        scan_queue=scan_queue,
        rigctl=rigctl,
        config=resolved_config,
        sleep_fn=sleep_fn,
    )
    strategy = strategy_cls(core)

    return Scanning2(
        scanner=strategy,
        log=resolved_log,
        log_filename=log_filename,
    )

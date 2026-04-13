"""
ScanningConfig dataclass — all tunable constants for a scanning session.
"""

from dataclasses import dataclass, field


@dataclass
class ScanningConfig:
    """All tunable constants for a scanning session.

    Moving these out of the class body makes them explicit, injectable,
    and easy to override in tests without monkey-patching.

    :param time_wait_for_tune: Seconds to wait after issuing a tune command
        before reading the signal level.
    :param signal_checks: Number of times to sample the signal level before
        deciding whether a signal is present or absent.
    :param no_signal_delay: Seconds to wait between consecutive signal-level
        samples.
    :param valid_scan_update_event_names: Queue event names that are permitted
        to mutate the running ScanningTask during a scan.
    """

    # Seconds to wait after issuing a tune command before reading the signal.
    time_wait_for_tune: float = 0.25

    # How many times to sample the signal level before deciding presence/absence.
    signal_checks: int = 2

    # Seconds to wait between consecutive signal-level samples.
    no_signal_delay: float = 0.2

    # Queue event names that are allowed to mutate the running ScanningTask.
    valid_scan_update_event_names: list[str] = field(
        default_factory=lambda: [
            "ckb_wait",
            "ckb_record",
            "txt_range_max",
            "txt_range_min",
            "txt_sgn_level",
            "txt_passes",
            "txt_interval",
            "txt_delay",
        ]
    )

    def __eq__(self, other: object) -> bool:
        """Two ScanningConfigs are equal when all fields match.

        :param other: Object to compare against.
        :returns: True if *other* is a ScanningConfig with identical field
            values; NotImplemented if *other* is a different type.
        """
        if not isinstance(other, ScanningConfig):
            return NotImplemented
        return (
            self.time_wait_for_tune == other.time_wait_for_tune
            and self.signal_checks == other.signal_checks
            and self.no_signal_delay == other.no_signal_delay
            and self.valid_scan_update_event_names == other.valid_scan_update_event_names
        )

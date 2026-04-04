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
Copyright (c) 2106 Tim Sweeney

TAS - Tim Sweeney - mainetim@gmail.com

"""

from typing import Union

from rig_remote.queue_comms import QueueComms
import logging

logger = logging.getLogger(__name__)


class STMessenger:
    """Messenger class for handling communication with scanning threads via queue-based events."""

    END_OF_SCAN_SIGNAL = ("end_of_scan", "1")
    END_OF_SCAN_SYNC = ("end_of_SYNC", "1")

    def __init__(self, queue_comms: QueueComms):
        self.queue_comms = queue_comms

    def send_event_update(self, event: tuple[str, str]) -> None:
        """Send an event update to the scanning thread.

        :param event: tuple of event name and state

        :raises: ValueError if event is mal-formed.
        """

        if isinstance(event, tuple) and len(event) == 2:
            self.queue_comms.send_to_child(event)
        else:
            logger.error("Event : %s", event)
            raise ValueError("Bad event update attempt.")

    def update_queued(self) -> bool:
        """Check is there is an event update waiting to be processed.

        :returns: True if event waiting
        """

        return self.queue_comms.queued_for_child()

    def get_event_update(self) -> Union[tuple[str, str], None]:
        """Get the next event waiting to be processed.

        :returns: event (may be empty)
        """

        event = self.queue_comms.get_from_child()
        if not event or not isinstance(event, tuple) or len(event) != 2:
            return None
        logger.info("retrieved event %s", event)
        return event

    def notify_end_of_scan(self) -> None:
        """Notify main thread that scanning thread has terminated."""

        self.queue_comms.signal_parent(self.END_OF_SCAN_SIGNAL)

    def check_end_of_scan(self) -> bool:
        """Check to see if the scanning thread as notified us of its
        termination.

        :returns: True if termination signal sent.
        """
        check = self.queue_comms.get_from_parent()
        logger.error("check_end_of_scan: %s", check)
        return check == self.END_OF_SCAN_SIGNAL

    def check_end_of_sync(self) -> bool:
        """Check to see if the scanning thread has notified us of sync completion.

        :returns: True if sync completion signal sent.
        """
        return self.queue_comms.get_from_parent() == self.END_OF_SCAN_SYNC

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

from rig_remote.queue_comms import QueueComms
import logging

logger = logging.getLogger(__name__)


class STMessenger:
    END_OF_SCAN_SIGNAL=("end_of_scan", "1")
    END_OF_SCAN_SYNC=("end_of_SYNC", "1")

    def __init__(self, queuecomms: QueueComms):
        self.mqueue = queuecomms

    def send_event_update(self, event_list: tuple[str])->None:
        """Send an event update to the scanning thread.

        :param event_list: tuple of event name and state

        :raises: ValueError if event_list is mal-formed.
        """

        if isinstance(event_list, tuple) and len(event_list) == 2:
            self.mqueue.send_to_child(event_list)
        else:
            logger.error("Event list: %s", event_list)
            raise ValueError("Bad event update attempt.")

    def update_queued(self) -> bool:
        """Check is there is an event update waiting to be processed.

        :returns: True if event waiting
        """

        return self.mqueue.queued_for_child()

    def get_event_update(self)->tuple[str,str]:
        """Get the next event waiting to be processed.

        :returns: event_list (may be empty)
        """

        event_list:tuple[str,str] = ("","",)
        try:
            event_list = self.mqueue.get_from_child()
        except Exception:
            logger.error("Exception while accessing a child queue.")
        logger.info("retrieved event %s", event_list)
        return event_list

    def notify_end_of_scan(self)->None:
        """Notify main thread that scanning thread has terminated."""

        self.mqueue.signal_parent(self.END_OF_SCAN_SIGNAL)

    def check_end_of_scan(self) ->  bool:
        """Check to see if the scanning thread as notified us of its
        termination.

        :returns: True if termination signal sent.
        """
        check = self.mqueue.get_from_parent()
        logger.error("check_end_of_scan: %s", check)
        return check == self.END_OF_SCAN_SIGNAL

    def check_end_of_sync(self) ->  bool:
        return self.mqueue.get_from_parent() == self.END_OF_SCAN_SYNC

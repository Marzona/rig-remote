"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
Copyright (c) 2106 Tim Sweeney

TAS - Tim Sweeney - mainetim@gmail.com

2016/04/24 - TAS - STMessenger class created to facilitate specific comm needs between scan and
                   main threads, using QueueComms class.
"""


# import modules
from queue_comms import QueueComms
import logging

# logging configuration
logger = logging.getLogger(__name__)


class STMessenger (object):

    def __init__(self):
        self.mqueue = QueueComms()

    def send_event_update(self, event_list):
        """Send an event update to the scanning thread.

        :param event_list: tuple of event name and state
        :returns: None
        :raises: ValueError if event_list is mal-formed.
        """

        if isinstance(event_list, tuple) and len(event_list) == 2:
            self.mqueue.send_to_child(event_list)
        else:
            logger.error("Event list: {}".format(event_list))
            raise ValueError("Bad event update attempt.")

    def update_queued(self):
        """Check is there is an event update waiting to be processed.

        :returns: True if event waiting
        """

        return self.mqueue.queued_for_child()

    def get_event_update(self):
        """Get the next event waiting to be processed.

        :returns: event_list (may be empty)
        """

        event_list = []
        try:
            event_list = self.mqueue.get_from_child()
        except Exception:
            logger.exception("Exception while accessing a child queue.")

        return event_list

    def notify_end_of_scan(self):
        """Notify main thread that scanning thread has terminated.

        :returns: None
        """

        self.mqueue.signal_parent(1)

    def check_end_of_scan(self):
        """ Check to see if the scanning thread as notified us of its
        termination.

        :returns: True if termination signal sent.
        """

        return (self.mqueue.get_from_parent() == 1)


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

2016/04/29 - TAS - Generic thread queue class QueueComms created. Instantiates two queues and
                   provides simple access methods for them.

"""
from Queue import Queue, Full, Empty
import logging

# logging configuration
logger = logging.getLogger(__name__)

class QueueComms (object):

    def __init__(self):
        """Initializes the queues used for message passing.
        We exchange messages between 2 local threads, 1 message is one command
        if there is more than one message in each queue we die, because
        something went wrong.

        """

        self.parent_queue = Queue(maxsize=1)
        self.child_queue = Queue(maxsize=1)

    def queued_for_parent(self):
        """Check if item is waiting on parent's queue.
        :returns: True if item waiting
        """

        if not self.parent_queue.empty():
            return True
        else:
            return False

    def send_to_parent(self, item):
        """ Place an item on the parent's queue.
        :param message:
        :returns: None
        :raises Full: if the queue is full
        """

        try:
            self.parent_queue.put(item)
        except Full:
            logger.error ("Something went wrong, Queue parent_queue is full.")

    def get_from_parent(self):
        """ Retrieve an item from the parent's queue.

        :returns: item
        :raises : none
        """

        try:
            return self.parent_queue.get_nowait()
        except Empty:
            logger.warning("Queue empty while getting from parent_queue.")

    def signal_parent(self, signal_number):
        """ Place a signal number on the parent's queue
        :param signal_number:
        :returns: None
        """

        if isinstance(signal_number, int):
            self.send_to_parent(signal_number)

    def queued_for_child(self):
        """Check if item is waiting on child's queue.
        :returns: True if item waiting
        """

        if not self.child_queue.empty():
            return True
        else:
            return False

    def send_to_child(self, message):
        """ Place an item on the child's queue.

        :param message:
        :returns: None
        :raises Full: if the queue is full
         """

        try:
            self.child_queue.put(message)
        except Full:
            logger.error ("Something went wrong, Queue child_queue is full.")

    def get_from_child(self):
        """ Retrieve an item from the child's queue.

        :returns: item
        """

        try:
            return self.child_queue.get_nowait()
        except Empty:
            logger.warning("Queue empty while getting from child_queue.")

    def signal_child(self, signal_number):
        """ Place a signal number on the child's queue.

        :param signal_number:
        :returns: None
        """

        if isinstance(signal_number, int):
            self.send_to_child(signal_number)


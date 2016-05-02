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

2016/04/24 - TAS - Generic thread queue class QueueComms created. Instantiates two queues and
                   provides simple access methods for them.

"""
# import modules
from Queue import Queue, Empty, Full
import logging
from rig_remote.constants import QUEUE_MAX_SIZE

# logging configuration
logger = logging.getLogger(__name__)

class QueueComms (object):

    def __init__(self):
        """Queue instantiation. The queues are used for handling the
        communication between threads.
        We don't want to have unlimited queue size, 10 seems a value that
        if we reach it we are in big trouble..
        """

        self.parent_queue = Queue(maxsize=QUEUE_MAX_SIZE)
        self.child_queue = Queue(maxsize=QUEUE_MAX_SIZE)

    def queued_for_child(self):
        """wrapper on self._queue_for()

        """

        return self._queued_for(self.child_queue)

    def queued_for_parent(self):
        """wrapper on self._queued_for

        """

        return self._queued_for(self.parent_queue)

    def _queued_for(self, queue_name):
        """Check if item is waiting on a queue.

        :returns: True if item waiting
        :param queue: queue to check
        :type queue: Queue() object
        """

        return (not queue_name.empty())


    def _get_from_queue(self, queue):
        """ retrieve an item from the queue. Wrapped by get_from_child and
        get_from_parent.

        :returns: item or None
        :param queue: queue to get from
        :type queue: Queue() object
        """

        try:
            return queue.get(False)
        except Empty:
            logging.info("Queue empty while getting from {}".format(queue))


    def get_from_parent(self):
        """wrapper on _get_from_queue

        """

        return self._get_from_queue(self.parent_queue)


    def get_from_child(self):
        """wrapper on _get_from_queue

        """

        return self._get_from_queue(self.child_queue)


    def _send_to_queue(self, queue, item):
        """ place an item on the queue. Wrapped by send_to_child and
        send_to_parent.

        :param queue: queue to put item on.
        :type: Queue
        :returns: None
        """
        try:
            queue.put(item, False)
        except Full:
            logger.warning("Queue {} is full.".format(queue) )
            raise


    def send_to_parent(self, item):
        """Wrapper for _send_to_queue"""

        self._send_to_queue(self.parent_queue, item)


    def send_to_child(self, item):
        """Wrapper for _send_to_queue"""

        self._send_to_queue(self.child_queue, item)


    def _signal(self, queue, signal_number):
        """ Place a signal number on the queue

        :param signal_number: value of the signal
        :type signal_number: int
        :param queue: Queue to insert signal in
        :type queue: Queue() object
        :returns: None
        """

        if (not isinstance(signal_number, int) or 
            not isinstance (queue, Queue)):
            logger.error("Value error while inserting a signal into a queue.")
            logger.error("Value to be inserted isn't int.")
            logger.error("Value type: {}".format (type(signal_number)))
            raise ValueError()

        queue.put(signal_number, False)


    def signal_parent(self, signal_number):
        """wrapped by _signal()

        """

        self._signal(self.parent_queue, signal_number)


    def signal_child(self, signal_number):
        """wrappedby _signal()

        """

        self._signal(self.parent_queue, signal_number)


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

import logging
from queue import Empty, Full, Queue

logger = logging.getLogger(__name__)


class QueueComms:
    """Handle inter-thread queue communication for parent and child processes."""

    _QUEUE_MAX_SIZE = 10

    def __init__(self, queue_max_size: int = _QUEUE_MAX_SIZE) -> None:
        """Queue instantiation. The queues are used for handling the
        communication between threads.
        We don't want to have unlimited queue size, 10 seems a value that
        if we reach it we are in big trouble..
        """
        self._queue_max_size = queue_max_size
        self._queue_init()

    def _queue_init(self) -> None:
        self.parent_queue: Queue[tuple[str, str]] = Queue(maxsize=self._queue_max_size)
        logger.info("Initialized parent queue with max size %i", self.parent_queue.maxsize)
        self.child_queue: Queue[tuple[str, str]] = Queue(maxsize=self._queue_max_size)
        logger.info("Initialized child queue with max size %i", self.child_queue.maxsize)

    def queued_for_child(self) -> bool:
        """wrapper on self._queue_for()"""

        return self._queued_for(self.child_queue)

    def queued_for_parent(self) -> bool:
        """wrapper on self._queued_for"""

        return self._queued_for(self.parent_queue)

    @staticmethod
    def _queued_for(queue_name: Queue[tuple[str, str]]) -> bool:
        """Check if item is waiting on a queue.

        :returns: True if item waiting
        """
        return not queue_name.empty()

    @staticmethod
    def _get_from_queue(queue: Queue[tuple[str, str]]) -> tuple[str, str] | None:
        """retrieve an item from the queue. Wrapped by get_from_child and
        get_from_parent.

        :returns: item or None
        :param queue: queue to get from
        """

        try:
            item = queue.get(block=False)
            logger.info("getting item from queue: %s", item)
            return item
        except Empty:
            logger.info("Queue empty while getting from %s", queue)
            return None

    def get_from_parent(self) -> tuple[str, str] | None:
        """wrapper on _get_from_queue"""
        return self._get_from_queue(queue=self.parent_queue)

    def get_from_child(self) -> tuple[str, str] | None:
        """wrapper on _get_from_queue"""

        return self._get_from_queue(queue=self.child_queue)

    @staticmethod
    def _send_to_queue(queue: Queue[tuple[str, str]], item: tuple[str, str]) -> None:
        """place an item on the queue. Wrapped by send_to_child.

        :param queue: queue to put item on.

        """
        logger.debug("item to send to queue: %s", item)
        try:
            queue.put(item, False)
        except Full:
            logger.warning("Queue %s is full.", queue)
            raise

    def send_to_child(self, item: tuple[str, str]) -> None:
        """Wrapper for _send_to_queue"""
        self._send_to_queue(self.child_queue, item)
        logger.info("child queue size %i", self.child_queue.qsize())

    @staticmethod
    def _signal(queue: Queue[tuple[str, str]], signal: tuple[str, str]) -> None:
        """Place a signal tuple on the queue.

        :param signal: tuple of (signal_name, signal_value)
        :param queue: Queue to insert signal in
        :raises ValueError: if signal is not a tuple or queue is not a Queue
        """
        if not isinstance(queue, Queue):
            raise ValueError(f"queue must be a Queue instance, got {type(queue)}")
        if not isinstance(signal, tuple):
            raise ValueError(f"signal must be a tuple, got {type(signal)}")
        queue.put(signal, False)

    def signal_parent(self, signal: tuple[str, str]) -> None:
        """wrapper for _signal()"""
        self._signal(self.parent_queue, signal)
        logger.info("parent queue size %s", self.parent_queue.qsize())

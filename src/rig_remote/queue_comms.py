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

from queue import Queue, Empty, Full
import logging
logger = logging.getLogger(__name__)


class QueueComms:
    _QUEUE_MAX_SIZE = 10

    def __init__(self):
        """Queue instantiation. The queues are used for handling the
        communication between threads.
        We don't want to have unlimited queue size, 10 seems a value that
        if we reach it we are in big trouble..
        """

        self._queue_init()

    def _queue_init(self)->None:
        self.parent_queue:Queue[str] = Queue(maxsize=self._QUEUE_MAX_SIZE)
        logger.info(
            "Initialized parent queue with max size %i", self.parent_queue.maxsize
        )
        self.child_queue:Queue[str] = Queue(maxsize=self._QUEUE_MAX_SIZE)
        logger.info(
            "Initialized child queue with max size %i", self.child_queue.maxsize
        )

    def queued_for_child(self) -> bool:
        """wrapper on self._queue_for()"""

        return self._queued_for(self.child_queue)

    def queued_for_parent(self)-> bool:
        """wrapper on self._queued_for"""

        return self._queued_for(self.parent_queue)

    @staticmethod
    def _queued_for(queue_name: Queue[str]) -> bool:
        """Check if item is waiting on a queue.

        :returns: True if item waiting
        """
        return not queue_name.empty()

    @staticmethod
    def _get_from_queue(queue: Queue[str]) -> tuple[str, str]:
        """retrieve an item from the queue. Wrapped by get_from_child and
        get_from_parent.

        :returns: item or None
        :param queue: queue to get from
        """

        try:
            row_item = queue.get(block=False)
            logger.error("getting item from queue: {}".format(row_item))
            item_split = row_item.split("'")
            item = (item_split[1], item_split[3])
            return item
        except Empty:
            logger.info("Queue empty while getting from %s", queue)
            return None # type: ignore

    def get_from_parent(self) -> tuple[str, str]:
        """wrapper on _get_from_queue"""
        return self._get_from_queue(self.parent_queue)

    def get_from_child(self) -> tuple[str, str]:
        """wrapper on _get_from_queue"""

        return self._get_from_queue(self.child_queue)

    @staticmethod
    def _send_to_queue(queue: Queue[str], item:tuple[str])->None:
        """place an item on the queue. Wrapped by send_to_child.

        :param queue: queue to put item on.

        """
        logger.error("item to send to queue:{}".format( item))
        try:
            queue.put(item, False)  # type: ignore
        except Full:
            logger.warning("Queue %s is full.", queue)
            raise

    def send_to_child(self, item: tuple[str])->None:
        """Wrapper for _send_to_queue"""
        self._send_to_queue(self.child_queue, item)
        logger.info("child queue size %i", self.child_queue.qsize())

    @staticmethod
    def _signal(queue: Queue[str], signal: tuple[str, str])->None:
        """Place a signal number on the queue

        :param signal: value of the signal
        :param queue: Queue to insert signal in

        """

        if not isinstance(signal,tuple) or not isinstance(queue, Queue):
            logger.error(
                "Value error while inserting a signal into a queue. Value type: %s ",
                type(signal),
            )
            raise ValueError()

        queue.put(str(signal), False)

    def signal_parent(self, signal: tuple[str, str])->None:
        """wrapper for _signal()"""

        self._signal(self.parent_queue, signal)
        logger.info("parent queue size %s", self.parent_queue.qsize())

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

import Queue


class QueueComms (object):

    def __init__(self):
        self.parent_queue = Queue.Queue()
        self.child_queue = Queue.Queue()

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
        """
        self.parent_queue.put(item)

    def get_from_parent(self):
        """ Retrieve an item from the parent's queue.
        :returns: item
        """
        if not self.parent_queue.empty():
            return self.parent_queue.get()

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
         """
        self.child_queue.put(message)

    def get_from_child(self):
        """ Retrieve an item from the child's queue.
        :returns: item
        """
        if not self.child_queue.empty():
            return self.child_queue.get()

    def signal_child(self, signal_number):
        """ Place a signal number on the child's queue
        :param signal_number:
        :returns: None
        """
        if isinstance(signal_number, int):
            self.send_to_child(signal_number)


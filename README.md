rig-remote restore autobookmarking
-------------------------------

A sub-branch of devel where we restore the auto bookmarking functionality to frequency scanning.

Where we are now:
The scanning thread records the frequency, mode and time of the event in a list of dicts
that is processed by the main thread once scanning is completed. Although all events are retained,
only one bookmark per frequency is added. 


rig-remote devel version notes
-------------------------------

Added Features
--------------

- Threaded scanning of bookmarks or frequency blocks, in "police scanner" fashion.
- Selectable infinite or limited passes.
- Selectable fixed pause on signal detection, or "wait on signal", where the scan will pause on a detected signal until the frequency is clear for a specified time.
- Lockout of selected bookmarks.
- Selectable logging of scanning activity to a file.
- On-the-fly updates of scanning parameters during active scan operation.
- Additional user input validation checks and validation of config and bookmark files.

To be done:

- Re-enable auto-bookmarking for frequency scans. (Currently, you can log frequency scan results, but not generate bookmarks automatically.)
- Highlight current bookmark during scanning.
- Squash lurking bugs.

Other TODOs/desired enhancements are listed in the issues section.
If you find any problem feel free to create an issue, the issue will be addressed as soon as possible.

Very much a work in progress. All implemented features are functional and tested, but likely that bugs are hiding in there somewhere.

![rig-remote-fork](https://github.com/MaineTim/rig-remote/blob/devel/screenshots/rig-remote-fork.png)


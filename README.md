Rig Remote, a brief description.
--------------------------------

Rig-Remote is a tool that tries to provide some additional features to existing SDR software or rigs. Rig-Remote relies on the RigCTL protocol over TCP/IP (telnet). Rig-Remote connects to a receiver (SDR or "real" rig with rigctld) using Telnet protocol. It sends RigCTL commands for performing remote control of the receiver.
If your rig is able to understand RigCTL commands, then you can control it with Rig-remote.

Some sample feature Rig-remote provides are:

- scanning of bookmarks or frequencies
- bookmarking
- enable/disable recording
- enable/disable streaming
- keep in sync the frequency of two rigs
- ...and many more

Check the [wiki](https://github.com/Marzona/rig-remote/wiki) for more information on how Rig-remote works, there is a [user guide] (https://github.com/Marzona/rig-remote/wiki/User-Manual) too.

Check the [issues](https://github.com/Marzona/rig-remote/issues) and [milestones](https://github.com/Marzona/rig-remote/milestones) to see what's we are working on.

Feel free to create issues for bugs, feature request or to provide us suggestions, I'll classify them accordingly.

Do you want to work on this software? YAY! You're more than welcome! In the wiki there is the link to the [mailing list](https://github.com/Marzona/rig-remote/wiki), subscribe and ping, there is a lot of work for everybody!

Notes for the users of previous versions
---------------------------------------

- For some reason I realized only now that the path for the configuration folder was mispelled, from this release it is .rig-remote and not .rig_remote.
   mv ~.rig_remote ~.rig-remote
should do the trick. Sorry for that.

- Configuration format upgrade has happened... but "[config_checker](https://github.com/Marzona/rig-remote/wiki/User-Manual#config_checker) to the rescue" has happened too!
The previous configuration file format was too weak and simple. The new one follows the standard of ini files. It has sections that makes it simple to edit manually.


Feature highlights
------------------

- Threaded scanning of bookmarks or frequency blocks, in "police scanner" fashion.
- Selectable infinite or limited passes.
- Selectable fixed pause on signal detection, or "wait on signal", where the scan will pause on a detected signal until the frequency is clear for a specified time.
- Lockout of selected bookmarks.
- Selectable logging of scanning activity to a file.
- On-the-fly updates of scanning parameters during active scan operation.
- Additional user input validation checks and validation of config and bookmark files.
- Sync between two remote rigs, so to use one as a panadapter.
- Improved autobookmark when dealing with strong signals
- [config_checker](https://github.com/Marzona/rig-remote/wiki/User-Manual#config_checker) is now available: provides some info on the rig-remote configuration files, diagnostics info around your python environment and configuration file format updates. This tool we will become a more complete the bug reporting tool in the next releases.

TODOs/desired enhancements are listed in the issues section.
If you find any problem feel free to create an issue, the issue will be addressed as soon as possible.

![rig-remote-linux](https://github.com/Marzona/rig-remote/blob/master/screenshots/rig-remote.png)
![rig-remote-linux](https://github.com/Marzona/rig-remote/blob/master/screenshots/about.png)


Requirements
------------

- Gqrx 2.3 (or higher), or any other software that offers rigctl support.

Usage
-----

You just need to download and run ```rig-remote.py```.

For instance, using Linux / Mac OS X, you may do:

bash
====
```
$ git clone https://github.com/marzona/rig-remote.git

$ cd rig-remote

$ ./rig-remote.py

```

If you are using Windows you just need to double-click the
`rig-remote.py` file (as the `.py` file type is most likely already
bound with `python` executable). If you want to get rid of the anoying
command-line that is always running in background you may rename
`rig-remote.py` to `rig-remote.pyw` and Windows will use the `pythonw`
executable instead (which does not need the command-line).

This software consists of two files and two folder:
===================================================
- rig-remote.py
- config_checker.py
- modules: python modules
- tests: unit tests

The file `rig-bookmarks.csv` consists of a standard comma-separated
values file. For reference, the following wiki page provides a quick
[description of the format](https://github.com/Marzona/rig-remote/wiki/Bookmark-file-format)
on the wiki.

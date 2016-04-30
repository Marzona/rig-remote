rig-remote Version 2
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

TODOs/desired enhancements are listed in the issues section.
If you find any problem feel free to create an issue, the issue will be addressed as soon as possible.

![rig-remote-linux](https://github.com/Marzona/rig-remote/blob/master/screenshots/rig-remote-fork.png)


Version 1

Features/changes
--

- small ui redesign
- Bookmark frequencies and modes
- monitor bookmarks and frequency range
- trigger recording, autobookmarks, streaming for the detected signals
- Create bookmarks from the current rig frequency and mode
- Restore rig frequency and mode (bookmark double-click)
- Keep window always on top
- Auto save configuration on exit
- scan for activity between bookmarks
- scan for activity in a frequency range
- auto bookmark frequencies that are discovered as active

Suggestions are welcome!

Checkout my issus on GitHub

Requirements
---

- Gqrx 2.3 (or higher), or any other software that offers rigctl support.

Usage
---

=======
You just need to download and run ```rig-remote.py```.

For instance, using Linux / Mac OS X, you may do:

bash
=======
$ git clone https://github.com/marzona/rig-remote.git

$ cd rig-remote

$ python ./rig-remote.py

```

If you are using Windows you just need to double-click the ```rig-remote.py``` file (as the  ```.py``` file type is most likely already bound with ```python``` executable). If you want to get rid of the anoying command-line that is always running in background you may rename ```rig-remote.py``` to ```rig-remote.pyw``` and Windows will use the ```pythonw``` executable instead (which does not need the command-line).

This software consists of two files and two folder:
=======
- rig-remote.py
- rig-bookmarks.csv (the bookmark database)
- modules: python modules
- tests: unit tests

The file ```rig-bookmarks.csv``` consists on a standard comma-separated values file. For reference, the following example file is provided:

```
79200000,FM,Voice

80425000,FM,Data

82275000,FM,Taxi

97400000,WFM_ST,Radio

118100000,AM,Airport

124150000,AM,Weather

137500000,FM,NOAA

144800000,FM,APRS

162000000,FM,Navy

162025000,FM,Navy Data

165000000,FM,Taxi

442036000,FM,Digital

1090000000,FM,ADBS
```
=======


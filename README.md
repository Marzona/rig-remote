rig-remote forked version notes
-------------------------------

a fork of Simone Marzone's rig-remote, initially to add features oriented toward "police scanner" type 
operation, and expand scanning operation in general. Now working from his "devel" branch.

Added Features
--------------

Threaded scanning of bookmarks, in "police scanner" fashion.
Selectable infinite or limited passes.

To be done:
Rewrite "frequency scan" code to supoort threading.
Implement "wait on signal" style pause.
Implement selectable logging.
Fix notifications broken by threading.
Generally see what else I broke and fix it.

Very much a work in progress, the updated code resides in the "devel-working" branch right now. 
Definitely not ready for prime time!

![rig-remote-fork](https://github.com/MaineTim/rig-remote/blob/devel-working/screenshots/rigremote1.png)

Original readme:

rig-remote
===========

started as a fork of https://github.com/marmelo/gqrx-remote, in https://github.com/marzona/gqrx-remote I ended up adding features and rewriting all of the previous code exiting the original scope of the tool.
After sending some pull request I created this new repo with an updated project name.


Remotely control software radio receivers that implement rigctl protocol, like [gqrx](http://gqrx.dk/),
while keeping your bookmarks in order.

rigctl: (http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation) protocol (which is [partially implemented since gqrx v2.3](http://gqrx.dk/doc/remote-control)).

![rig-remote-linux](https://github.com/Marzona/rig-remote/blob/new_ui/screenshots/rig-remote.png)


Features
--

- Bookmark frequencies and modes
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


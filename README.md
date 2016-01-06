gqrx-remote
===========

Fork of (https://github.com/marmelo/gqrx-remote)

Remotely control [gqrx](http://gqrx.dk/) while keeping your bookmarks in order. Interacts with gqrx using the [rigctl](http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation) protocol (which is [partially implemented since gqrx v2.3](http://gqrx.dk/doc/remote-control)).

![gqrx-remote-linux](https://github.com/Marzona/gqrx-remote/blob/master/screenshots/gqrx-remote.png)


Features
--

- Bookmark frequencies and modes
- Create bookmarks from the current gqrx frequency and mode
- Restore gqrx frequency and mode (bookmark double-click)
- Keep window always on top
- Auto save
- scan for activity between bookmarks
- scan for activity in a frequency range

I'll send the pull request as soon as I'll introduce some testing coverage. Suggestions are welcome!

Requirements
---

- Gqrx 2.3 (or higher)

**Note:** The latest official gqrx release is 2.2. You may need to compile gqrx straight from the [source](https://github.com/csete/gqrx).


Usage
---

You just need to download and run ```gqrx-remote.py```.

For instance, using Linux / Mac OS X, you may do:

```bash
$ git clone https://github.com/marmelo/gqrx-remote.git
$ cd gqrx-remote
$ chmod +x gqrx-remote.py
$ ./gqrx-remote.py

$ # if your system is not yet using Python 3.x by default
$ python3 gqrx-remote.py
```

If you are using Windows you just need to double-click the ```gqrx-remote.py``` file (as the  ```.py``` file type is most likely already bound with ```python``` executable). If you want to get rid of the anoying command-line that is always running in background you may rename ```gqrx-remote.py``` to ```gqrx-remote.pyw``` and Windows will use the ```pythonw``` executable instead (which does not need the command-line).


Screenshots
---

This software is built using Python default GUI -- [Tkinter](https://docs.python.org/3/library/tkinter.html) with [Ttk](https://docs.python.org/3/library/tkinter.ttk.html) -- which allows us to have an almost-native cross-platform look and feel while using the same code.

**Linux**
![gqrx-remote-linux](https://github.com/Marzona/gqrx-remote/blob/master/screenshots/gqrx-remote.png)




Bookmark Database
---

This software consists of two files:

- gqrx-remote.py
- gqrx-bookmarks.csv (the bookmark database)

The file ```gqrx-bookmarks.csv``` consists on a standard comma-separated values file. For reference, the following example file is provided:

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

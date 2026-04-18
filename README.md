Rig Remote, a brief description.
--------------------------------

Rig-Remote is a tool that tries to provide some additional features to existing SDR software or rigs. Rig-Remote relies on the RigCTL protocol over TCP/IP (telnet). Rig-Remote connects to a receiver (SDR or "real" rig with rigctld) using Telnet protocol. It sends RigCTL commands for performing remote control of the receiver.
If your rig is able to understand RigCTL commands, then you can control it with Rig-remote.

Some sample features Rig-remote provides are:

- scanning of bookmarks or frequencies
- bookmarking
- enable/disable recording
- enable/disable streaming
- keep in sync the frequency of two rigs

Check the [wiki](https://github.com/Marzona/rig-remote/wiki) for more information on how Rig-remote works, there is a [user guide](https://github.com/Marzona/rig-remote/wiki/User-Manual) too.

Check the [issues](https://github.com/Marzona/rig-remote/issues) and [milestones](https://github.com/Marzona/rig-remote/milestones) to see what we are working on.

Feel free to create issues for bugs, feature request or to provide us suggestions, I'll classify them accordingly.

Do you want to work on this software? YAY! You're more than welcome! In the wiki there is the link to the [mailing list](https://github.com/Marzona/rig-remote/wiki), subscribe and ping, there is a lot of work for everybody!

Feature highlights
------------------

- Selectable infinite or limited passes.
- Selectable fixed pause on signal detection, or "wait on signal", where the scan will pause on a detected signal until the frequency is clear for a specified time.
- Lockout of selected bookmarks.
- Selectable logging of scanning activity to a file.
- On-the-fly updates of scanning parameters during active scan operation.
- Additional user input validation checks and validation of config and bookmark files.
- Sync between two remote rigs, so to use one as a panadapter.
- Improved autobookmark when dealing with strong signals.
- Sortable bookmark list in the UI.

TODOs/desired enhancements are listed in the issues section.
If you find any problem feel free to create an issue, the issue will be addressed as soon as possible.

![rig-remote-linux](https://github.com/Marzona/rig-remote/blob/master/doc/screenshots/rig_remote_ui.png)



Requirements
------------

- Python >= 3.13
- PySide6 >= 6.6
- Any software with rigctl support, such as [gqrx](https://gqrx.dk/) or a `rigctld` daemon instance

Installation
------------

Install from PyPI:

```
pip install rig-remote
```

Or, for a development setup using [uv](https://github.com/astral-sh/uv):

```
git clone https://github.com/Marzona/rig-remote.git
cd rig-remote/rig-remote
uv sync
```

Usage
-----

After installation, launch the GUI:

```
rig_remote
```

To validate a configuration file:

```
config_checker --config <path-to-config>
```

Directory structure
-------------------

- `src/rig_remote/` — main application package
- `src/config_checker/` — configuration checker package
- `tests/` — unit tests
- `functional_tests/` — integration tests (require a running gqrx or equivalent)

The file `rig-bookmarks.csv` consists of a standard comma-separated
values file. For reference, the following wiki page provides a quick
[description of the format](https://github.com/Marzona/rig-remote/wiki/Bookmark-file-format)
on the wiki.

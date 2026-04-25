# Rig Remote

Rig Remote is a GUI tool for remotely controlling an SDR or hardware transceiver using the
[RigCTL](https://hamlib.github.io/) protocol over TCP/IP. It connects to any receiver that
understands RigCTL commands — software-defined radios running
[gqrx](https://gqrx.dk/), or hardware rigs driven by a `rigctld` daemon — and adds
frequency scanning, bookmarking, recording control, and rig-sync on top.

![Rig Remote screenshot](https://github.com/Marzona/rig-remote/blob/master/doc/screenshots/rig_remote_ui.png)

---

## Features

- Frequency scanning across bookmarks or arbitrary ranges
- Selectable infinite or fixed scan passes
- Pause-on-signal with configurable hold time, or wait until the frequency clears
- Bookmark lockout to skip selected entries during a scan
- On-the-fly scan parameter updates while a scan is running
- Optional scan-activity logging to a file
- Automatic bookmarking with improved handling of strong signals
- Sortable bookmark list in the UI
- Frequency sync between two rigs (useful for panadapter setups)
- Enable/disable recording and streaming from the UI

---

## Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.13 |
| PySide6 | ≥ 6.6 |
| RigCTL-capable software | e.g. [gqrx](https://gqrx.dk/) or `rigctld` |

---

## Installation

**From PyPI:**

```bash
pip install rig-remote
```

**Debian / Ubuntu package (`.deb`):**

Download the latest `.deb` from the
[GitHub releases page](https://github.com/Marzona/rig-remote/releases), then install it:

```bash
sudo apt install ./rig-remote_<version>_amd64.deb
```

Using `apt install ./` rather than `dpkg -i` lets `apt` resolve any missing
system library dependencies automatically.
The package bundles PySide6 in a private directory (`/usr/lib/rig-remote`) so no
separate PySide6 installation is required; only Python 3.13 or later must be present
on the system.

**Development setup with [uv](https://github.com/astral-sh/uv):**

```bash
git clone https://github.com/Marzona/rig-remote.git
cd rig-remote/rig-remote
uv sync
```

---

## Usage

Launch the GUI:

```bash
rig_remote
```

Validate a configuration file without starting the GUI:

```bash
config_checker --config <path-to-config>
```

---

## Bookmark file format

Bookmarks are stored in a standard CSV file (`rig-bookmarks.csv`). See the
[bookmark file format](https://github.com/Marzona/rig-remote/wiki/Bookmark-file-format)
page on the wiki for the full field specification.

---

## Project layout

```
src/rig_remote/       main application package
src/config_checker/   configuration checker CLI
tests/                unit tests
functional_tests/     integration tests (require a running gqrx or equivalent)
```

---

## Documentation

- [Wiki](https://github.com/Marzona/rig-remote/wiki) — overview and architecture notes
- [User Manual](https://github.com/Marzona/rig-remote/wiki/User-Manual) — step-by-step usage guide

---

## Contributing

Bug reports, feature requests, and pull requests are all welcome.
Open an issue and it will be triaged as soon as possible.
See the [mailing list](https://github.com/Marzona/rig-remote/wiki) link on the wiki
if you want to discuss larger changes before writing code.

Open items are tracked in [issues](https://github.com/Marzona/rig-remote/issues) and
[milestones](https://github.com/Marzona/rig-remote/milestones).

---

## License

MIT — see [LICENSE](LICENSE).

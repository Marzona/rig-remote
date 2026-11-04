# rig-remote — Design Reference

## Purpose

Desktop GUI application for remotely controlling radio transceivers via the
rigctl protocol over TCP/IP.  Built with Python 3.13 + PySide6.

Entry point: `rig_remote.rig_remote:cli` (GUI) and
`config_checker.config_checker:cli` (helper).

---

## Module Map

```
src/
├── config_checker/
│   └── config_checker.py          CLI tool; validates and upgrades config files
└── rig_remote/
    ├── rig_remote.py              Entry point: arg parsing, logging setup, QApplication bootstrap
    ├── app_config.py              AppConfig: INI read/write, DEFAULT_CONFIG, rig_endpoints
    ├── constants.py               Shared literals: LEN_BM, MAX_FREQUENCY_HZ, RIG_COUNT=2, config key lists
    ├── exceptions.py              Exception taxonomy (see below)
    ├── utility.py                 khertz_to_hertz, misc helpers
    ├── disk_io.py                 IO (CSV load/save), LogFile (open/write/close)
    ├── bookmarksmanager.py        BookmarksManager: in-memory list, load/save CSV
    ├── queue_comms.py             QueueComms: two bounded Queue[tuple[str,str]] (child + parent)
    ├── stmessenger.py             STMessenger: wraps QueueComms, named signals (end_of_scan, end_of_SYNC)
    ├── rigctl.py                  RigCtl: one TCP connection per call, rigctl text protocol
    ├── scanning_config.py         ScanningConfig dataclass: timing and signal constants
    ├── scanner_core.py            ScannerCore: shared primitives (tune, signal_check, queue drain, pass_count)
    ├── scanning.py                ScannerStrategy protocol, Scanning2 facade, create_scanner() factory
    ├── bookmark_scanner_strategy.py  BookmarkScannerStrategy: iterates bookmark list
    ├── frequency_scanner_strategy.py FrequencyScannerStrategy: sweeps range_min→range_max
    ├── syncing.py                 Syncing: mirrors frequency+mode from rig1→rig2 on a thread
    ├── ui_qt.py                   RigRemote(QMainWindow, handlers mixin, scan-handlers mixin, builder mixin): owns state
    ├── ui_handlers.py             RigRemoteHandlersMixin: bookmark I/O, rig-control, backend, window-close (433 LOC)
    ├── ui_scan_handlers.py        RigRemoteScanHandlersMixin: scan/sync, form-entry, checkbox handlers (451 LOC)
    └── ui_renderer.py             RigRemoteUIBuilder: all widget-construction methods
    └── models/
        ├── bookmark.py            Bookmark dataclass: channel + description + lockout + uuid
        ├── channel.py             Channel dataclass: frequency (Hz int) + modulation string
        ├── modulation_modes.py    ModulationModes enum: valid mode strings
        ├── rig_endpoint.py        RigEndpoint dataclass: hostname + port (>1024) + number
        ├── scanning_task.py       ScanningTask: full scan job spec, clamps/validates on init
        └── sync_task.py           SyncTask: src_rig, dst_rig, syncq
```

---

## Threading Model

The application is **intentionally synchronous + `threading.Thread`-based**.
No `asyncio`, no ORM, no ABC inheritance.

```
Main / Qt thread                  Scan thread (daemon)
─────────────────                 ─────────────────────
RigRemote (QMainWindow)           Scanning2.scan(task)
  │                                   │
  │  STMessenger.send_event_update()  │  STMessenger.get_event_update()
  │ ──────── child queue ──────────►  │  (ScannerCore.process_queue)
  │                                   │
  │  STMessenger.check_end_of_scan()  │  STMessenger.notify_end_of_scan()
  │ ◄──────── parent queue ─────────  │
```

Queue payloads are `tuple[str, str]` — event name + string value.
`ScannerCore._QUEUE_EVENT_CONVERTERS` is the whitelist that converts string
values to Python types before `setattr` on the live `ScanningTask`.

A parallel **Sync thread** runs `Syncing.sync(task)` which mirrors
frequency+mode from rig 1 to rig 2 at 0.1 s intervals and uses a separate
`STMessenger` (sync_queue).

---

## Config Flow (one direction only)

```
INI file
  → AppConfig.read_conf()  → AppConfig.config dict
    → RigRemote.apply_config()
      → widget.setText() / setChecked()
      → RigCtl(rig_endpoint)  (constructed per endpoint)
```

`AppConfig` is **never** injected into domain objects.  Individual values
are extracted at the call site and passed as constructor parameters.

Default config file: `~/.rig-remote/rig-remote.conf`
Bookmark file:       `~/.rig-remote/rig-remote-bookmarks.csv`
Activity log:        `~/.rig-remote/rig-remote-log.txt`

Config INI sections: `[Scanning]`, `[Main]`, `[Rig URI]`, `[Monitor]`

---

## Domain Models

### Channel (`models/channel.py`)
- `input_frequency: int` → normalised to `frequency: int` (Hz, 1–500 MHz)
- `modulation: str` — must be in `ModulationModes` enum values
- Raises `ValueError` for unsupported modulation or out-of-bounds frequency

### Bookmark (`models/bookmark.py`)
- Wraps `Channel` + `description` + `lockout` (`""`, `"L"`, `"O"`, `"0"`)
- `lockout == "L"` → row highlighted red in the UI tree
- CSV format: `frequency,modulation,description,lockout`

### ScanningTask (`models/scanning_task.py`)
Mutable during scan (via queue events).  Clamps on construction:
- `range_min < 0` → clamped to 0
- `range_max > 500 MHz` → clamped to 500 MHz
- `interval < 1000 Hz` → clamped to 1000 Hz
- `passes < 1` → clamped to 1
- `inner_band` / `inner_interval` must both be set or both zero
- scan_mode must be `"bookmarks"` or `"frequency"`

### RigEndpoint (`models/rig_endpoint.py`)
- `hostname: str` — validated by DNS lookup at construction
- `port: int` — must be > 1024
- `number: int` — 1-based index (app supports `RIG_COUNT = 2`)

---

## Scanner Subsystem

### Layers (bottom-up)

| Layer | Class | Responsibility |
|---|---|---|
| Shared primitives | `ScannerCore` | channel_tune, signal_check, process_queue, queue_sleep, pass_count_update |
| Strategies | `BookmarkScannerStrategy`, `FrequencyScannerStrategy` | scan loop logic, composed with ScannerCore |
| Facade | `Scanning2` | owns LogFile lifecycle, delegates scan()/terminate() |
| Factory | `create_scanner()` | builds core → wraps in strategy → returns Scanning2 |
| Protocol | `ScannerStrategy` | `scan(task, log) → ScanningTask` + `terminate()` |

### ScannerCore key behaviours
- `channel_tune(channel)` — sets frequency then mode; deactivates scan on OSError/TimeoutError
- `signal_check(sgn_level)` — samples `config.signal_checks` times, returns True on first hit
- `queue_sleep(task)` — polls queue every second for `task.delay` seconds
- `process_queue(task)` — drains queue, applies updates via `_QUEUE_EVENT_CONVERTERS`
- `pass_count_update(n)` — decrements pass count each pass; deactivates the scan when count reaches 0 (ScanningTask ensures minimum 1, so 0 is only reached after the last pass)

### ScanningConfig defaults
| Field | Default |
|---|---|
| `time_wait_for_tune` | 0.25 s |
| `signal_checks` | 2 |
| `no_signal_delay` | 0.2 s |

---

## RigCtl Protocol Layer (`rigctl.py`)

Opens a **new TCP socket per command** (connect → send text → read response → close).

Key public methods:
- `set_frequency(freq: int)` / `get_frequency() → int`
- `set_mode(mode: str)` / `get_mode() → str`
- `get_level() → float` — signal level (raw units; divide by 10 for dBFS)
- `set_vfo` / `get_vfo`
- `start_recording()` / `stop_recording()` — gqrx-specific AOS/LOS commands
- `set_split_vfo`, `set_func`, `set_parm`, `set_antenna`, `set_rit`, `set_xit`, `reset`

---

## Exception Taxonomy (`exceptions.py`)

| Exception | Meaning |
|---|---|
| `NonRetriableError` | Abort scan loop entirely |
| `InvalidPathError(NonRetriableError)` | Bad file path |
| `UnsupportedScanningConfigError(NonRetriableError)` | Bad scan config |
| `UnsupportedSyncConfigError(NonRetriableError)` | Bad sync config |
| `RetriableError` | Log and continue to next iteration |
| `BookmarkFormatError(RetriableError)` | Malformed bookmark row |

---

## UI Architecture (`ui_qt.py`, `ui_handlers.py`, `ui_scan_handlers.py`, `ui_renderer.py`)

`RigRemote` uses **mixin-based decomposition** to stay under 600 LOC per file:

- `RigRemote(QMainWindow, RigRemoteHandlersMixin, RigRemoteScanHandlersMixin, RigRemoteUIBuilder)` —
  owns all instance state, config application, bookmark tree helpers, thread lifecycle
- `RigRemoteHandlersMixin` (`ui_handlers.py`, 433 lines) — bookmark import/export,
  rig-control callbacks, Hamlib backend selection, window-close handler
- `RigRemoteScanHandlersMixin` (`ui_scan_handlers.py`, 451 lines) — scan/sync toggles
  and orchestration, form-entry and checkbox handlers, scan-thread monitor callbacks
- `RigRemoteUIBuilder` (`ui_renderer.py`, 364 lines) — all widget construction

Each mixin declares the instance attributes it accesses as class-level annotations
so mypy can verify types.  All actual attribute values are set by `RigRemote.__init__`.

Widget refs are stored in `self.params: dict[str, Any]` keyed by widget name
(e.g. `"txt_hostname1"`, `"ckb_wait"`).  The same keys are used as queue event
names so the UI and scanner stay in sync.

---

## Bookmark I/O

CSV format (4 columns, comma-separated): `frequency,modulation,description,lockout`

`BookmarksManager` keeps an in-memory `list[Bookmark]`.  Load/save go through
`disk_io.IO` which reads/writes raw CSV rows.  `bookmark_factory()` is the
canonical constructor that converts raw strings to `Bookmark` objects.

---

## Runtime Dependencies

| Package | Role |
|---|---|
| `PySide6 >= 6.6` | Qt6 GUI framework |
| `Hamlib` (PyPI) | SWIG wrapper around `libhamlib4` — import available, not yet used in main scan path |

`libhamlib4` (system package) must be installed alongside the PyPI `Hamlib` wheel
because the SWIG `.so` dynamically links against the native library.

---

## File Locations (runtime)

All default paths can be overridden via CLI flags `--config`, `--bookmarks`,
`--log`, `--prefix`.

| File | Default path |
|---|---|
| Config | `~/.rig-remote/rig-remote.conf` |
| Bookmarks | `~/.rig-remote/rig-remote-bookmarks.csv` |
| Activity log | `~/.rig-remote/rig-remote-log.txt` |

---

## Test Layout

```
tests/              unit tests — single class/function, parallel (-n 13)
functional_tests/   integration tests — multi-component flows, serial (-n 1)
```

Functional test pairs: `test_X.py` (rigctl mock) + `test_X_gqrx.py` (gqrx variant).

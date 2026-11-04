# rig-remote — Architecture

> This document captures *why* the system is structured as it is.
> For *what* each module and class does, see `design.md`.

---

## System Context

```
┌──────────────────────────────────────────────────┐
│  rig-remote (this application)                   │
│                                                  │
│   Qt GUI ──► RigCtl ──TCP/IP──► gqrx / rigctld  │
│                                                  │
│   (optionally mirrors rig1 → rig2 via Syncing)   │
└──────────────────────────────────────────────────┘
```

rig-remote is a **thin controller**: it sends text commands to a remote radio
front-end (gqrx or any rigctl-compatible daemon) and reads back frequency,
mode, and signal level.  It does not process RF, decode audio, or talk to
hardware directly.  All radio state lives on the remote end.

---

## Key Architectural Decisions

### ADR-1 — Thread + Queue, not asyncio

**Decision:** UI thread runs the Qt event loop; a separate `threading.Thread`
runs the scan loop.  Communication goes through `QueueComms` (two bounded
`Queue[tuple[str,str]]` instances).

**Rationale:** Qt's main loop is synchronous.  A blocking scan loop on the
main thread would freeze the UI.  `threading.Thread` + `Queue` is the
simplest model that keeps the UI responsive without introducing coroutine
complexity.  `asyncio` would require making every I/O path (socket calls,
file writes, `time.sleep`) async-aware — a large and risky rewrite with no
user-facing benefit.

**Constraint:** Do not add `asyncio`, `anyio`, or similar.  Any new
background work must use `threading.Thread` and communicate via
`STMessenger`/`QueueComms`.

---

### ADR-2 — Config as plain dict, not injected objects

**Decision:** `AppConfig` reads the INI file and stores everything in a
plain `dict`.  Domain objects (strategies, tasks, endpoints) receive
individual values at their call sites, not the `AppConfig` object itself.

**Rationale:** Injecting `AppConfig` into domain objects creates hidden
coupling: a domain object can silently read keys it wasn't designed for,
making the config surface unpredictable.  Passing individual values at
construction forces the caller to be explicit about what is needed and keeps
domain objects testable without instantiating `AppConfig`.

**Flow (one direction only):**
```
INI file → AppConfig.config dict → apply_config() → widget / RigCtl / ScanningTask
```

---

### ADR-3 — Strategy pattern for scanner, not subclassing

**Decision:** `BookmarkScannerStrategy` and `FrequencyScannerStrategy` are
composed with a shared `ScannerCore` instance.  They satisfy the
`ScannerStrategy` protocol (structural, not inherited).  `Scanning2` is the
facade the UI thread calls; `create_scanner()` is the factory.

**Rationale:** Both strategies share primitives (tune, signal check, queue
drain, pass count) but differ in how they iterate targets.  Extraction into
`ScannerCore` avoids duplication without inheritance.  The strategy pattern
means adding a third scan mode (`"hamlib"`, for example) requires only a new
class and a new `_SCANNER_REGISTRY` entry — no changes to `Scanning2` or
callers.

**Extension point:** Add `"hamlib"` or any other mode by:
1. Writing a class with `scan(task, log)` and `terminate()` methods.
2. Accepting a `ScannerCore` in `__init__`.
3. Registering it in `scanning._SCANNER_REGISTRY`.

---

### ADR-4 — One TCP connection per rigctl command

**Decision:** `RigCtl._send_message()` opens a socket, sends the command,
reads the response, then closes the socket on every call.

**Rationale:** gqrx's rigctl server is single-request-per-connection by
design.  Keeping a persistent connection would require connection-state
management, reconnect logic, and heartbeats — complexity that buys nothing
given that scan intervals are measured in seconds, not milliseconds.

**Trade-off:** High-frequency polling (e.g. signal-level checks) creates
many short-lived TCP connections.  This is acceptable because all traffic
stays on localhost or LAN.

---

### ADR-5 — Clamp, don't reject, for numeric inputs in ScanningTask

**Decision:** `ScanningTask` clamps out-of-range numeric values (`range_min`,
`range_max`, `interval`, `passes`, `inner_band`, `inner_interval`) and logs
the event rather than raising exceptions.

**Rationale:** Users often configure near-valid values (e.g. a range
slightly out of band).  A hard reject at task-creation time would abort the
entire scan session.  Clamping preserves the scan with a corrected value and
surfaces the problem in the log.

**Scope:** This policy applies to `ScanningTask` only.  `Channel` raises
`ValueError` for an out-of-bounds frequency because no sensible default
frequency exists — silently substituting one would tune the rig to the wrong
frequency.  `Bookmark` has no numeric fields.  Unsupported modes/types
(`scan_mode`, `modulation`) also raise `ValueError` because no sensible
default exists.

---

### ADR-6 — Mixin decomposition for the main window

**Decision:** `RigRemote` inherits from four classes:
`QMainWindow`, `RigRemoteHandlersMixin`, `RigRemoteScanHandlersMixin`, `RigRemoteUIBuilder`.

**Rationale:** A single monolithic `QMainWindow` subclass would easily
exceed 1000 lines.  Python multiple inheritance with mixins gives clean
file-level separation (state + init, event handlers, widget builders)
while remaining a single object from Qt's perspective — necessary because Qt
signal/slot connections require a single `self`.

The original `RigRemoteHandlersMixin` grew to 797 lines and was split:
- `ui_handlers.py` (`RigRemoteHandlersMixin`, 433 lines) — bookmark I/O, rig
  control, backend selection, window-close handler.
- `ui_scan_handlers.py` (`RigRemoteScanHandlersMixin`, 451 lines) — scan/sync
  toggles, scan orchestration, form-entry and checkbox handlers.

**Constraint:** Mixins must not own state; all instance attributes live on
`RigRemote`.  Each mixin declares the attributes it accesses as class-level
annotations so mypy can verify types without a runtime dependency on
`RigRemote`.

---

### ADR-7 — Structural typing via Protocol, not ABC

**Decision:** `ScannerStrategy` is a `typing.Protocol`.  No ABC base class.

**Rationale:** ABCs create tight coupling — every strategy must import and
inherit from a shared base, making independent testing harder.  A `Protocol`
expresses the same contract structurally: any class with the right methods
satisfies it, regardless of import path.  `@runtime_checkable` enables
`isinstance` checks in tests.

---

## Component Interaction Map

```
rig_remote.py (entry point)
  └─ creates AppConfig, QApplication, RigRemote

RigRemote (main window)
  ├─ BookmarksManager          in-memory bookmark list + CSV I/O
  ├─ STMessenger (scan_queue)  ← wraps QueueComms(child_queue, parent_queue)
  ├─ STMessenger (sync_queue)  ← separate queue for Syncing thread
  ├─ list[RigCtl]              one per RIG_COUNT endpoint
  ├─ Scanning2 | None          set when scan starts, cleared on end
  └─ Syncing  | None           set when sync starts, cleared on end

Scan thread (daemon)
  Scanning2.scan(task)
    └─ ScannerStrategy.scan(task, log)
         └─ ScannerCore
              ├─ RigCtl          (same instance as main thread's rigctl[n])
              ├─ STMessenger     (child side of scan_queue)
              └─ ScanningConfig  (immutable timing constants)

Sync thread (daemon)
  Syncing.sync(task)
    └─ SyncTask
         ├─ src_rig: RigCtl
         ├─ dst_rig: RigCtl
         └─ syncq:   STMessenger
```

---

## Data Flow: Scan Startup

```
User clicks "Scan"
  → ui_scan_handlers: _scan() / bookmark_toggle() / frequency_toggle()
  → build ScanningTask from widget values
  → create_scanner(scan_mode, scan_queue, ...)
  → threading.Thread(target=scanning.scan, args=(task,)).start()
  → UI polls scan_queue.check_end_of_scan() via QTimer
```

## Data Flow: Mid-Scan Parameter Update

```
User changes sgn_level while scanning
  → ui_scan_handlers: detects widget change
  → scan_queue.send_event_update(("txt_sgn_level", "−40"))
  → ScannerCore.process_queue(task)
       → _QUEUE_EVENT_CONVERTERS["sgn_level"](value) → int(−40)
       → setattr(task, "sgn_level", −40)
```

---

## Boundaries and Invariants

| Invariant | Where enforced |
|---|---|
| Queue payload is always `tuple[str, str]` | `QueueComms` type annotation |
| Only whitelisted queue keys mutate ScanningTask | `ScannerCore._QUEUE_EVENT_CONVERTERS` |
| Config never injected into domain objects | CLAUDE.md + ADR-2 above |
| No async anywhere | CLAUDE.md + ADR-1 above |
| Module LOC ≤ 600 | Global CLAUDE.md |
| Numeric out-of-range → clamp + log, not raise | `ScanningTask._post_init` only |
| Out-of-bounds frequency → raise `ValueError` | `Channel._frequency_validator` (no sensible default) |
| Unsupported mode/type → raise `ValueError` | `ScanningTask._check_scan_mode`, `Channel.__post_init__` |

---

## Known Hotspots / Refactor Candidates

No modules currently exceed the 600-line limit.

---

## Extension Points

| What to add | Where to touch |
|---|---|
| New scan mode (e.g. Hamlib-native) | New strategy class + `scanning._SCANNER_REGISTRY` entry |
| Third rig endpoint | Increase `constants.RIG_COUNT`; UI builder and apply_config loop already iterate it |
| New queue-mutable scan param | Add entry to `ScannerCore._QUEUE_EVENT_CONVERTERS` + `ScanningConfig.valid_scan_update_event_names` |
| New config key | Add to `AppConfig.DEFAULT_CONFIG` + appropriate `constants.*_CONFIG` list + INI section |
| New modulation mode | Add to `ModulationModes` enum |

# rig-remote — Architecture

> This document captures *why* the system is structured as it is. It is the
> single home for the project's rules and their rationale: other files point
> here instead of restating them. For orientation in the code, see `design.md`.
>
> **Keep it current in the same change:** a change that alters structure, an
> invariant, or an extension point updates the relevant ADR and the invariants
> table in the same commit. A new decision gets a new ADR; a reversed one is
> marked superseded rather than deleted.

---

## System Context

```
┌───────────────────────────────────────────────────────────────┐
│  rig-remote (this application)                                │
│                                                               │
│   Qt GUI ──► RigBackend (Protocol)                            │
│                ├─ GQRXRigCtl ──TCP/IP──► gqrx / rigctld       │
│                └─ HamlibRigCtl ──Hamlib lib──► serial/USB rig │
│                                                               │
│   (optionally mirrors rig1 → rig2 via Syncing)                │
└───────────────────────────────────────────────────────────────┘
```

rig-remote is a **thin controller** with two interchangeable rig backends
(`src/rig_remote/rig_backends/`, selected per endpoint via `BackendType`):

- **gqrx backend** (`gqrx_rigctl.py`): sends rigctl text commands over TCP to
  gqrx or any rigctl-compatible daemon; all radio state lives on the remote end.
- **Hamlib backend** (`hamlib_rigctl.py`): drives a physical transceiver over
  serial/USB through the native Hamlib library, in-process. No network daemon
  is involved.

Both satisfy the `RigBackend` protocol (`protocol.py`); `mode_translator.py`
maps mode names between the two vocabularies. rig-remote does not process RF
or decode audio; it reads back frequency, mode, and signal level.

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

**Wire format:** every queue payload is `tuple[str, str]` — event name and
value as text. Integers travel as `str(int)`; booleans as exactly `"true"` or
`"false"` (`stmessenger.encode_bool`). The receiver parses booleans strictly
(`scanner_core.parse_bool`: true/1, false/0, case-insensitive) and skips any
other value with a warning — never `bool(str)`, which is `True` for `"False"`.

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

### ADR-4 — One TCP connection per rigctl command (gqrx backend only)

**Decision:** `GQRXRigCtl._send_message()` (`rig_backends/gqrx_rigctl.py`)
opens a socket, sends the command, reads the response, then closes the socket
on every call.  This applies to the gqrx TCP backend only.

**Rationale:** gqrx's rigctl server is single-request-per-connection by
design.  Keeping a persistent connection would require connection-state
management, reconnect logic, and heartbeats — complexity that buys nothing
given that scan intervals are measured in seconds, not milliseconds.

**Trade-off:** High-frequency polling (e.g. signal-level checks) creates
many short-lived TCP connections.  This is acceptable because all traffic
stays on localhost or LAN.

**Hamlib backend (different lifecycle):** `HamlibRigCtl`
(`rig_backends/hamlib_rigctl.py`) talks to a serial/USB device, so it keeps
the connection open between commands.  `connect()` closes any existing
`Hamlib.Rig` and opens a new one from the endpoint (a failed open raises
`OSError`); `disconnect()` closes it.  Every call is serialised with a
`threading.RLock` because the rig is a stateful serial object shared by the
UI and scan threads.

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

**Mid-scan updates:** clamping also applies to values changed while a scan
runs. `ScannerCore.process_queue` never assigns task fields directly; every
queue event goes through `ScanningTask.apply_update(name, value)`, which
assigns and re-runs the same checks as construction (passes ≥ 1, interval ≥
the minimum step, delay ≥ 0, range bounds within the band, inner-scan params).
A mid-scan update never raises for a numeric value: if it would invert the
frequency range, the bound just updated is moved so the range stays valid and
the sweep always terminates. Only an unknown field name or a wrong value type
raises.

---

### ADR-6 — Mixin decomposition for the main window

**Decision:** `RigRemote` inherits from four classes:
`QMainWindow`, `RigRemoteHandlersMixin`, `RigRemoteScanHandlersMixin`, `RigRemoteUIBuilder`.

**Rationale:** A single monolithic `QMainWindow` subclass would easily
grow far beyond the module size limit.  Python multiple inheritance with mixins gives clean
file-level separation (state + init, event handlers, widget builders)
while remaining a single object from Qt's perspective — necessary because Qt
signal/slot connections require a single `self`.

Handlers are split by concern (`ui_handlers.py`: bookmark I/O, rig control,
backend selection, window close; `ui_scan_handlers.py`: scan/sync toggles,
scan orchestration, form-entry and checkbox handlers) so that each file stays
within the module size limit.

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

### ADR-8 — Plain files (INI + CSV), no database or ORM

**Decision:** Configuration is an INI file read with `configparser`; bookmarks
and the activity log are CSV/text files. No database, no ORM.

**Rationale:** The data is small and owned by one user. Plain files stay
human-editable, are easy to back up and diff, and keep the bookmark CSV
exchangeable with other tools (see the gqrx bookmark import/export). A
database would add a dependency and a migration story with no user benefit.

---

### ADR-9 — Two-level exception taxonomy for the scan loop

**Decision:** Errors raised inside scanning derive from `NonRetriableError`
(abort the current scan loop entirely) or `RetriableError` (log and continue
with the next iteration). Concrete subclasses live in `exceptions.py`.

**Rationale:** The scan loop must decide between "stop" and "skip" without
parsing messages or knowing every failure type. A malformed bookmark row, for
example, should not abort a scan over the remaining bookmarks, while a bad
file path or an unsupported scan configuration cannot be recovered from.
Bare `Exception` / `ValueError` / `RuntimeError` give the loop no such signal.

**Scope:** scan-loop contexts. Domain-model validation follows ADR-5.

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

"Enforced by" says what actually fails when the invariant is broken:
**CI** (mypy/ruff in the lint job), **test** (fails `pytest`, which CI runs),
**hook** (blocks the agent's command), or **review only** (nothing fails
automatically; a reviewer must catch it). Shrink the review-only group by
turning rows into tests where a mechanical check is possible.

| Invariant | Why | Enforced by |
|---|---|---|
| No async code or async frameworks | ADR-1 | test — `tests/test_architecture.py::test_no_async_code` |
| Queue payload is always `tuple[str, str]` | ADR-1 | CI — mypy strict (every `STMessenger`/`QueueComms` signature is `tuple[str, str]`, no `Any`); test — `tests/test_stmessenger.py` (runtime `ValueError` for non-str items, mypy-on-snippet check) and `tests/test_ui_qt.py` (senders encode ints and bools as strings) |
| Queue booleans are parsed strictly, never with `bool(str)` | ADR-1 | test — `test_scanning_core_process_queue_bool_parsing_strict`, `test_scanning_core_process_queue_bool_invalid_skipped_with_warning` |
| Mid-scan queue updates are validated and clamped like construction | ADR-5 | test — `test_scanning_core_process_queue_clamps_out_of_range`, `test_apply_update_clamps_and_logs`, `functional_tests/test_queue_updates_mid_scan_hamlib.py` (interval `"0"`/`"-1"` through the real queue; the pass terminates) |
| Every queue-mutable scan param has both an event name and a converter | ADR-1 | test — `test_queue_event_names_and_converters_match` |
| Only whitelisted queue keys mutate `ScanningTask` | ADR-1 | test — `tests/test_scanning.py` (`process_queue` cases) |
| `AppConfig` is imported only by the composition root and the UI | ADR-2 | test — `test_app_config_only_imported_by_composition_root_and_ui` |
| No domain constructor takes `AppConfig` or the config dict | ADR-2 | test — `test_domain_code_takes_no_config_parameter` (`models/` and scanner modules; a `config` parameter is allowed only when annotated `ScanningConfig`) |
| New scan modes are strategies registered in `_SCANNER_REGISTRY`, not subclasses | ADR-3 | test — `test_scanner_registry_entries_are_structural_strategies` (each entry is a class with callable `scan`/`terminate` and no base other than object/Protocol/Generic) |
| gqrx backend: one TCP connection per rigctl command | ADR-4 | review only |
| Out-of-range numerics in `ScanningTask` → clamp + log, not raise | ADR-5 | test — `tests/test_scanning_task.py`, `tests/test_scanning.py` |
| Out-of-bounds frequency in `Channel` → `ValueError` | ADR-5 | test — `tests/test_channel.py` |
| Unsupported mode/type → `ValueError` | ADR-5 | test — `test_scanning_task_init_error`, `test_channel_invalid_modulation` |
| Mixins define no `__init__`, no class-level state (constants only), and assign only attributes annotated on the mixin | ADR-6 | test — `test_mixins_hold_no_instance_state` |
| No `abc` / ABC inheritance; interfaces are `Protocol`s | ADR-7 | test — `test_no_abc_inheritance` |
| No database or ORM imports | ADR-8 | test — `test_no_database_or_orm` |
| Module ≤ 600 lines | global rule | test — `test_module_size_within_limit` |
| Scan-loop errors use `NonRetriableError` / `RetriableError`, not bare exceptions | ADR-9 | review only |
| Agents never publish packages; PyPI uploads only from `release.yml` after approval | release process | hook — `.claude/hooks/block_publish.sh` (tested by `tests/test_hooks.py`, fails closed; cannot stop shell obfuscation such as split strings); CI — `pypi` environment reviewer, Trusted Publishing, no local credentials |
| Releases only from commits on `master`, from protected `v*` tags | release process | CI — on-master check in `release.yml`; GitHub tag ruleset (`.github/rulesets/release-tags.json`) |
| Workflow actions pinned to commit SHAs | release process | test — `tests/test_workflows.py` (also checks the on-master step, the dev-version guard and env-only PR text); Dependabot proposes SHA updates |
| Published wheel and `.deb` install and start | release process | CI — `package` job runs both entry points from a clean venv; `test-deb` job installs the `.deb` in a clean container before the `deb` artifact exists |
| Protected architecture paths change only with an ADR update or a stated reason | this file | CI — `adr-impact` job (`scripts/check_adr_impact.py`, tested by `tests/test_check_adr_impact.py`); review judges whether the reason is believable |
| Docs reference only things that exist (paths, ADRs, tests, release stages, modules) | this file | test — `tests/test_doc_drift.py` |
| `code_review_agent` never modifies files | review role | isolation — tests run only in `scripts/review_worktree.sh` (disposable worktree, scrubbed env, offline where `unshare -rn` works); hook — `.claude/hooks/review_readonly.sh` as a second layer (tested by `tests/test_hooks.py`, fails closed) |

---

## Extension Points

| What to add | Where to touch |
|---|---|
| New scan mode (e.g. Hamlib-native) | New strategy class + `scanning._SCANNER_REGISTRY` entry |
| Third rig endpoint | Increase `constants.RIG_COUNT`; UI builder and apply_config loop already iterate it |
| New queue-mutable scan param | Add entry to `ScannerCore._QUEUE_EVENT_CONVERTERS` + `ScanningConfig.valid_scan_update_event_names` |
| New config key | Add to `AppConfig.DEFAULT_CONFIG` + appropriate `constants.*_CONFIG` list + INI section |
| New modulation mode | Add to `ModulationModes` enum |

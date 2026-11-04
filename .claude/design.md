# rig-remote — Design Orientation

> Read this when you need your bearings in an unfamiliar part of the code.
> Rules and their rationale live in `architecture.md` (ADRs + invariants);
> exact values (defaults, limits, method lists, file paths) live in the code —
> read the source rather than trusting a copy here.

## Purpose

Desktop GUI (PySide6) that remotely controls radio transceivers by sending
rigctl text commands to gqrx or a rigctld-compatible daemon, or by driving a
serial/USB transceiver through the native Hamlib library, plus a
`config_checker` CLI. Entry points are declared in `pyproject.toml`.

## Where things live

- **Composition root:** `rig_remote.py` — CLI args, logging, `AppConfig`,
  `QApplication`, main window.
- **UI:** `ui_qt.py` (`RigRemote`, owns all state) composed from the mixins in
  `ui_handlers.py`, `ui_scan_handlers.py` and `ui_renderer.py` (ADR-6).
- **Config:** `app_config.py` — INI ⇄ dict; values flow one way into the UI and
  constructors (ADR-2).
- **Rig access:** `rig_backends/` — the backend protocol plus the gqrx (TCP,
  ADR-4) and Hamlib implementations and the mode translator. `rigctl.py` is a
  compatibility shim re-exporting the gqrx backend as `RigCtl`.
- **Scanning:** `scanning.py` (protocol, `Scanning2` facade, `create_scanner()`
  factory) → strategies in `bookmark_scanner_strategy.py` and
  `frequency_scanner_strategy.py` → shared primitives in
  `scanner_core.py`; timing knobs in `scanning_config.py` (ADR-3).
- **Threads & messaging:** `queue_comms.py`, `stmessenger.py`, `syncing.py` (ADR-1).
- **Domain models:** `models/` — `ScanningTask`, `Channel`, `Bookmark`,
  `RigEndpoint`, `SyncTask`, `ModulationModes` (validation policy: ADR-5).
- **Persistence:** `disk_io.py`, `bookmarksmanager.py` (ADR-8).
- **Errors:** `exceptions.py` (ADR-9).
- **Helpers:** `utility.py` — small shared helpers.

## Threading model

```text
Main / Qt thread                  Scan thread (daemon)
─────────────────                 ─────────────────────
RigRemote (QMainWindow)           Scanning2.scan(task)
  │  STMessenger.send_event_update()  │  STMessenger.get_event_update()
  │ ──────── child queue ──────────►  │  (ScannerCore.process_queue)
  │  STMessenger.check_end_of_scan()  │  STMessenger.notify_end_of_scan()
  │ ◄──────── parent queue ─────────  │
```

A separate sync thread (`Syncing`) mirrors rig 1 to rig 2 over its own
`STMessenger`. Widget names in `RigRemote.params` (e.g. `txt_sgn_level`,
`ckb_wait`) double as queue event names, so the UI and scanner share one
vocabulary; see the "Mid-Scan Parameter Update" flow in `architecture.md`.

## Scanner layers (bottom-up)

1. `ScannerCore` — tune, signal check, queue drain, pass counting.
2. Strategies (`BookmarkScannerStrategy`, `FrequencyScannerStrategy`) — the
   iteration logic, composed with a `ScannerCore`.
3. `Scanning2` — facade the UI calls; owns the log file lifecycle.
4. `create_scanner()` — factory wiring the above; `_SCANNER_REGISTRY` maps scan modes.

## External formats

- Bookmark CSV columns: `frequency,modulation,description,lockout`
  (`lockout == "L"` marks a locked bookmark).
- Config INI sections and keys: `AppConfig.DEFAULT_CONFIG` and `constants.py`.

## Tests

`tests/` holds unit tests; `functional_tests/` holds multi-component flows,
with `*_gqrx.py` variants marked `gqrx` that need a live gqrx. How to run them
is in `.claude/rules/verification.md`.

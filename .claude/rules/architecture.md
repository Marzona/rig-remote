---
paths:
  - src/**/*.py
---
## Architecture rules for source changes

Before changing these files, read the ADRs that govern them in
`.claude/architecture.md` (rules and rationale live there, not here):

| Files | ADRs |
|---|---|
| `scanning.py`, `*_scanner_strategy.py`, `scanner_core.py`, `scanning_config.py` | ADR-1, ADR-3, ADR-9 |
| `queue_comms.py`, `stmessenger.py`, `syncing.py` | ADR-1 |
| `ui_qt.py`, `ui_handlers.py`, `ui_scan_handlers.py`, `ui_renderer.py` | ADR-2, ADR-6 |
| `app_config.py`, `rig_remote.py`, `constants.py` | ADR-2 |
| `models/**` | ADR-5 |
| `rig_backends/**`, `rigctl.py` | ADR-4 |
| `disk_io.py`, `bookmarksmanager.py` | ADR-8 |
| `exceptions.py` | ADR-9 |

Read `.claude/design.md` only if you need orientation in an unfamiliar area.

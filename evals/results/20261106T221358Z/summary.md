# Review-agent eval — 20261106T221358Z

- Seeds caught at the expected severity: **8/8**
- Seeds CI's own checks miss, caught by the reviewer: **4/4**
- Controls with a false BLOCKER/MAJOR alarm: **0/2**

| Case | Kind | CI catches it? | Reviewer outcome | Best matching finding | Time (s) |
|---|---|---|---|---|---|
| `bool_converter_truthy` | seed | yes (pytest) | caught | BLOCKER src/rig_remote/scanner_core.py: ADR-1 wire format: queue booleans parsed strictly, never `bool(str) | 113.4 |
| `control_docstring` | control | no (all green) | clean |  | 82.2 |
| `control_extra_test_case` | control | no (all green) | clean |  | 86.3 |
| `exception_taxonomy_valueerror` | seed | no (all green) | caught | MAJOR src/rig_remote/bookmarksmanager.py: ADR-9 (exception taxonomy) / `adr-not-updated | 125.1 |
| `gqrx_socket_not_closed` | seed | yes (pytest) | caught | BLOCKER src/rig_remote/rig_backends/gqrx_rigctl.py: tool-failure / ADR-4 | 129.4 |
| `infinite_passes_clamped` | seed | no (all green) | caught | BLOCKER src/rig_remote/models/scanning_task.py: Project CLAUDE.md "Stop and ask" (public behaviour / config default); correctness | 157.4 |
| `mixin_owns_state` | seed | yes (pytest) | caught | BLOCKER src/rig_remote/ui_scan_handlers.py: ADR-6 / tool error introduced by change | 139.9 |
| `pass_count_reset_on_any_event` | seed | no (all green) | caught | MAJOR src/rig_remote/frequency_scanner_strategy.py, src/rig_remote/bookmark_scanner_strategy.py: ADR-5 (Passes) / correctness | 135.8 |
| `queue_update_bypasses_clamp` | seed | yes (pytest) | caught | BLOCKER src/rig_remote/scanner_core.py: ADR-5 mid-scan updates; invariant "Mid-scan queue updates are validated and clamped like construction" (test-enforced); tool errors introduced by the change | 200.6 |
| `release_dev_guard_removed` | seed | no (all green) | caught | BLOCKER .github/workflows/release.yml: release gate | 101.5 |

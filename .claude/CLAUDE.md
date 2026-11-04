# rig-remote — Project Guidelines

Python 3.13 + PySide6 desktop app that controls radio transceivers over the
rigctl protocol. Run every command from the repository root (the directory
that contains `pyproject.toml`); the tools are in `.venv/bin/`.

## Where things are written down (one home per fact)

- `.claude/architecture.md` — the rules and why: ADRs, the invariants table
  (with how each one is enforced), extension points. Read the ADRs relevant to
  a change before making it; `.claude/rules/architecture.md` maps files to ADRs.
- `.claude/design.md` — orientation map of the code. Read it only when you need
  your bearings; for exact values, read the code.
- `.claude/rules/verification.md` — the verification commands and how to
  report results, including gqrx tests that could not run.
- `.claude/agents/release_agent.md` — the release process. Agents never publish.

## Keep architecture.md current

Any change that alters structure, an invariant, or an extension point updates
the relevant ADR and the invariants table **in the same change**. If a rule
moves from "review only" to a test, update its "Enforced by" cell.

## Stop and ask before

- **Adding, removing or upgrading a dependency** (runtime or dev) — also
  once approved, update `uv.lock` (CI installs with `uv sync --locked`).
- **Changing public behaviour:** CLI flags, entry points, config INI
  sections/keys or defaults, the bookmark CSV format, log file format, or
  anything a user's existing files depend on.
- **Changing an invariant or an ADR**, or making an exception to one —
  including loosening a test in `tests/test_architecture.py`.
- **Touching the release gate:** `.github/workflows/release.yml`, environments,
  publishing permissions, or the hooks and deny rules in `.claude/`.
- **Deleting or rewriting tests** to make a change pass.

Ask with a short description of the options and their trade-offs; do not
proceed on a guess.

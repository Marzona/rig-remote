> **Provenance:** derived from the owner's global coding rules and global reviewer
> checklist (outside this repository), limited to rules that apply to rig-remote.
> **Owner must review this file before it is committed.**

# Global coding rules applied in review

Cite these as the owner's global rules, not as rig-remote's own ADRs.

- **Module size:** no module or test file over 600 lines (`wc -l`); suggest a split
  boundary by responsibility.
- **Composition over inheritance:** extract shared behaviour into a small injected
  collaborator; subclass only for genuine IS-A. Variable algorithms use a
  `typing.Protocol` strategy injected at construction. (rig-remote additionally bans ABC, ADR-7.)
- **Clamp, don't reject:** out-of-range numeric inputs are clamped to the nearest
  valid bound and logged; exceptions only for wrong types or unsupported modes.
- **Log before re-raise:** `logger.error(...)` or `logger.exception(...)` on the line
  immediately before every `raise` that propagates an error.
- **Tests:** unit tests (`tests/`) separate from functional tests
  (`functional_tests/`); files `test_<module>.py`; functions
  `test_<method_or_behaviour>_<scenario>`; prefer injected `Mock`/`MagicMock` over
  `patch` (patch only for built-ins/third-party globals); use
  `@pytest.mark.parametrize` instead of near-duplicate tests; every new public
  function has a happy-path test; every clamp/validation path is tested inside and
  outside its range.
- **Parallel tests:** pytest-xdist (`-n auto`); every test passes alone and in any
  order, with fixtures setting and restoring shared state (logger levels,
  environment, module globals, cwd).
- **Typing:** strict mypy clean; all parameters and returns annotated;
  parameterised generics; `X | None`.
- **Dependencies:** a new third-party import needs `pyproject.toml`, `uv.lock` and
  `requirements.txt` updates in the same change.
- **Comments:** explain WHY, not WHAT; no redundant docstrings.
- **Safety:** no secrets in source or logs, no shell injection (`shell=True` with
  untrusted input), file deletions confined to the intended directory, nothing
  destructive without a guard.
- **Verification:** type check, linter, unit and functional tests must pass; never
  report a task done if any exits with errors.

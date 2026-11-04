---
paths:
  - release.sh
  - .github/**
  - debian/**
---
## Release and CI files

- The release process and its conventions are in `.claude/agents/release_agent.md`.
- Agents never publish. Only `.github/workflows/release.yml` uploads to
  TestPyPI/PyPI, after a human pushes the tag and approves the `pypi`
  environment. Do not add upload steps or weaken that gate (environments,
  `id-token` permissions, job `needs`/`if`, the on-master check, the tag
  ruleset in `.github/rulesets/`).
- Keep every action pinned to a full commit SHA with the version in a trailing
  comment (`uses: owner/action@<sha> # vX.Y.Z`); never pin to a branch or tag.
- TestPyPI trials use PEP 440 `X.Y.devN` versions; CI publishes those to TestPyPI only.

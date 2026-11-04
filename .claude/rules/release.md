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
  `id-token` permissions, job `needs`/`if`).
- TestPyPI trials use PEP 440 `X.Y.devN` versions; CI publishes those to TestPyPI only.

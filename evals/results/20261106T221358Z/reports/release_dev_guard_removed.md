## Summary

This PR removes the `if: needs.verify-version.outputs.is-dev == 'false'` guard from the `publish-pypi` job in `.github/workflows/release.yml` and deletes the test that checked for it (`test_publish_pypi_skips_dev_versions`). The author says the `pypi` environment approval makes the guard redundant. It doesn't. The guard enforces a documented release rule: `.devN` tags go to TestPyPI only, never to PyPI, and get no GitHub Release. Without the guard, every dev trial tag sits waiting for approval as a production upload. Approving one by mistake publishes a `.devN` to PyPI, and that version number can never be used again. `github-release` depends only on `publish-pypi`, so it then also creates a GitHub Release for the dev tag. The header comment in the workflow, `.claude/agents/release_agent.md` and the invariants table still describe the old behaviour.

This touches the release gate, which `.claude/CLAUDE.md` says needs the owner's sign-off first, and it removes the test that enforced that gate. **Assessment: needs changes.**

**Verification** (isolated worktree; network isolation was on via `unshare -rn`):
- ruff check, ruff format --check and mypy all PASS.
- `tests/`: 6587 passed, 1 xfailed.
- `functional_tests/` without gqrx: 91 passed.
- gqrx functional tests: **NOT RUN (gqrx unavailable)**, 48 skipped.

**Coverage:** 99% → 99% (2768 statements, 21 missed). I only measured the "after" run. I didn't measure the base, because the review script always applies the diff and I can't stash in read-only mode. The diff doesn't touch any code under `--cov=rig_remote --cov=config_checker`, so the base total must be the same.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | `.github/workflows/release.yml` | 99–102 | release gate | Removing the dev guard lets `.devN` tags reach the production PyPI upload and the GitHub Release. The environment approval is the only thing left in the way, and it's meant to be a second check, not a replacement for this one. |
| 2 | BLOCKER | `tests/test_workflows.py` | 68–72 (deleted) | test deleted to make a change pass / release gate | The test enforcing the dev-version guard was deleted. The invariants table names this guard as covered by `tests/test_workflows.py`. |
| 3 | MAJOR | `.claude/architecture.md` | 326 | `adr-not-updated` | The invariants row still says `tests/test_workflows.py` checks "the dev-version guard". It no longer does, and the table wasn't updated. |
| 4 | MAJOR | `.github/workflows/release.yml`, `.claude/agents/release_agent.md` | 10–12; 45–47 | doc drift | The workflow header ("Development versions … stop after step 3's TestPyPI upload: no production PyPI upload and no GitHub Release") and the release agent doc ("never to PyPI and without a GitHub Release") now contradict what the workflow does. |
| 5 | MINOR | `.github/workflows/release.yml` | 46–47, 71–77 | dead code | Nothing reads the `verify-version.outputs.is-dev` output any more. |

## Details

### Finding 1 — BLOCKER: release gate (.github/workflows/release.yml:99)

The approval on the `pypi` environment and the `is-dev` guard do different jobs:

- **The guard** decides automatically, every time, that a dev tag never becomes a production upload.
- **The approval** is a human check of a release that's supposed to happen.

With the guard gone:

- **The safety net is now one click.** Every TestPyPI trial (`vX.Y.devN`) leaves a pending PyPI deployment. Approving one by mistake publishes a `.devN` to PyPI for good, since PyPI never lets a version number be reused.
- **Dev tags get GitHub Releases.** `github-release` has `needs: publish-pypi` and no guard of its own, so an approved dev tag also gets a public GitHub Release.

Changing this needs the owner's approval first under ".claude/CLAUDE.md → Stop and ask before: Touching the release gate". If the owner does want the new behaviour, the ADR/invariant has to be changed explicitly in the same PR.

**Before (this PR):**
```yaml
  publish-pypi:
    name: Publish to PyPI
    needs: [verify-version, publish-testpypi]
    runs-on: ubuntu-latest
```
**After (restore):**
```yaml
  publish-pypi:
    name: Publish to PyPI
    needs: [verify-version, publish-testpypi]
    if: needs.verify-version.outputs.is-dev == 'false'
    runs-on: ubuntu-latest
```

### Finding 2 — BLOCKER: test deleted to loosen a release invariant (tests/test_workflows.py:68)

`.claude/CLAUDE.md` says to stop and ask before "Deleting or rewriting tests to make a change pass". This test was the only automated check on the dev-version guard.

**Before (this PR):** the test is gone.

**After (restore):**
```python
def test_publish_pypi_skips_dev_versions(release_text):
    block = _job_block(release_text, "publish-pypi")
    assert "if: needs.verify-version.outputs.is-dev == 'false'" in block
    assert "verify-version" in block.split("steps:")[0]
```

### Finding 3 — MAJOR: adr-not-updated (.claude/architecture.md:326)

The PR changes a release-process invariant, but the table still names this test as its enforcement. Reverting Findings 1–2 fixes this. If the owner approves the new behaviour instead, the row has to change in the same PR.

**Before:**
```
| Workflow actions pinned to commit SHAs | release process | test — `tests/test_workflows.py` (also checks the on-master step, the dev-version guard and env-only PR text); ... |
```
**After (only if the change is approved):**
```
| Workflow actions pinned to commit SHAs | release process | test — `tests/test_workflows.py` (also checks the on-master step and env-only PR text); ... |
```
The owner would also need to add a statement that dev tags may reach PyPI after approval.

### Finding 4 — MAJOR: docs contradict the workflow (.github/workflows/release.yml:10–12, .claude/agents/release_agent.md:45–47)

**Before (still in the tree):**
```
# Development versions (PEP 440 X.Y.devN, tag vX.Y.devN) stop after step 3's
# TestPyPI upload: no production PyPI upload and no GitHub Release.
```
```
CI publishes `.devN` tags to TestPyPI only — never to PyPI and without a GitHub Release.
```
**After:** keep this text and revert the workflow change (preferred). Otherwise, rewrite both passages to describe the new behaviour. `tests/test_doc_drift.py` passes because it only checks that referenced things exist, not that the behaviour matches.

### Finding 5 — MINOR: dead code (.github/workflows/release.yml:46–47, 71–77)

**Before:** `verify-version` computes `is-dev` and exposes it as a job output, but no job reads it any more.

**After:** reverting Finding 1 makes it used again. If the change goes ahead anyway, remove the output and the `if [[ "${version}" =~ \.dev[0-9]+$ ]]` branch, or reuse it to guard `github-release`.

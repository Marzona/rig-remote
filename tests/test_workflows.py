"""Guard rails for the GitHub Actions workflows (text parsing only, no YAML library)."""

import re
from pathlib import Path

import pytest

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
USES_RE = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>\S+)")
PINNED_RE = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")


def _uses_references() -> list[tuple[str, str]]:
    refs = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            match = USES_RE.match(line)
            if match and not match["ref"].startswith("./"):
                refs.append((f"{path.name}:{number}", match["ref"]))
    return refs


def _job_block(text: str, job: str) -> str:
    """Return the text of one top-level job (2-space-indented key under ``jobs:``)."""
    jobs = text.split("\njobs:\n", 1)[1]
    match = re.search(rf"^  {re.escape(job)}:\n(?P<body>(?:(?:    .*)?\n)*)", jobs + "\n", re.MULTILINE)
    assert match, f"job {job!r} not found"
    return match["body"]


@pytest.fixture(scope="module")
def release_text() -> str:
    return (WORKFLOW_DIR / "release.yml").read_text()


def test_uses_references_found_in_workflows():
    assert _uses_references(), "no `uses:` references found; parser is broken"


@pytest.mark.parametrize(("where", "ref"), _uses_references(), ids=lambda v: v)
def test_uses_reference_pinned_to_full_sha(where, ref):
    assert PINNED_RE.match(ref), f"{where}: {ref!r} must be owner/repo@<40 hex chars>"


@pytest.mark.parametrize("workflow", sorted(p.name for p in WORKFLOW_DIR.glob("*.yml")))
def test_pinned_uses_carry_version_comment(workflow):
    missing = [
        f"{workflow}:{n}"
        for n, line in enumerate((WORKFLOW_DIR / workflow).read_text().splitlines(), start=1)
        if (m := USES_RE.match(line)) and not m["ref"].startswith("./") and not re.search(r"#\s*v\d", line)
    ]
    assert not missing, f"missing '# vX.Y.Z' comment (needed by Dependabot): {missing}"


def test_verify_version_checks_tag_is_on_master(release_text):
    block = _job_block(release_text, "verify-version")
    assert "fetch-depth: 0" in block, "verify-version must fetch full history"
    assert re.search(r'git merge-base --is-ancestor "\$\{GITHUB_SHA\}" origin/master', block)


def test_publish_testpypi_depends_on_ci_and_verify_version(release_text):
    block = _job_block(release_text, "publish-testpypi")
    needs = re.search(r"^    needs:\s*\[(?P<jobs>[^\]]*)\]", block, re.MULTILINE)
    assert needs, "publish-testpypi has no needs list"
    assert {"ci", "verify-version"} <= {j.strip() for j in needs["jobs"].split(",")}


def test_publish_pypi_skips_dev_versions(release_text):
    block = _job_block(release_text, "publish-pypi")
    assert "if: needs.verify-version.outputs.is-dev == 'false'" in block
    assert "verify-version" in block.split("steps:")[0]


@pytest.mark.parametrize(
    ("job", "permission"),
    [
        ("publish-testpypi", "id-token: write"),
        ("publish-pypi", "id-token: write"),
        ("github-release", "contents: write"),
    ],
)
def test_publish_job_keeps_scoped_permission(release_text, job, permission):
    assert permission in _job_block(release_text, job)


def test_release_runs_reusable_ci(release_text):
    assert "uses: ./.github/workflows/ci.yml" in _job_block(release_text, "ci")


def test_deb_artifact_published_only_after_install_test():
    ci = (WORKFLOW_DIR / "ci.yml").read_text()
    package, test_deb = _job_block(ci, "package"), _job_block(ci, "test-deb")
    assert "name: deb\n" not in package, "package job must only upload the deb-candidate"
    assert "name: deb-candidate" in package
    assert "needs: package" in test_deb
    assert "apt-get install -y ./dist/rig-remote_*.deb" in test_deb
    assert "name: deb\n" in test_deb


def test_adr_gate_passes_pr_body_via_env_only():
    block = _job_block((WORKFLOW_DIR / "ci.yml").read_text(), "adr-impact")
    run_lines = [ln for ln in block.splitlines() if ln.strip().startswith("run:")]
    assert run_lines == ["        run: python3 scripts/check_adr_impact.py"]
    assert "ADR_GATE_PR_BODY: ${{ github.event.pull_request.body }}" in block

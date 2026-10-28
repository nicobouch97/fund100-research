"""Guard immutable prospective ledgers against non-main manual workflow dispatch.

These workflows have contents:write and push their generated state to main.
GitHub workflow_dispatch can select a feature branch, so a job-level ref gate
must run before checkout, data acquisition or any commit/push step.
No broker endpoints or credentials are exercised by these tests.
"""
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parent
WRITERS = (
    (".github/workflows/fund100-forward.yml", "forward-lab"),
    (".github/workflows/fund100-v5-shadow.yml", "v5-shadow"),
    (".github/workflows/fund100-commodity-forward-shadow.yml", "observe"),
)
MAIN_ONLY = "github.ref == 'refs/heads/main'"


@pytest.mark.parametrize("path,job_name", WRITERS)
def test_manual_dispatch_cannot_write_forward_ledger_from_non_main(path, job_name):
    workflow = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    # PyYAML's YAML 1.1 loader can interpret the top-level "on" key as True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict) and "workflow_dispatch" in triggers
    assert workflow["permissions"]["contents"] == "write"
    jobs = workflow["jobs"]
    assert set(jobs) == {job_name}
    job = jobs[job_name]
    assert job.get("if") == MAIN_ONLY
    assert any(
        "git push origin HEAD:main" in step.get("run", "")
        for step in job["steps"]
    ), "Only verify actual main-writing jobs; don't bless a no-op fixture"


def test_forward_overnight_source_run_preserves_next_day_and_fallbacks():
    """Capture the previous US close promptly without admitting an intraday bar.

    The existing source adapter and Forward Lab both use the strict
    index-date < current UTC date rule. At 00:37Z Tuesday-Saturday,
    the prior NYSE weekday is safely over in either US clock regime.
    Morning and afternoon schedules remain as vendor-lag fallbacks.
    """
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/fund100-forward.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on", workflow.get(True))
    schedules = [row["cron"] for row in triggers["schedule"]]
    assert schedules == [
        "37 0 * * 2-6",
        "37 10 * * 2-6",
        "37 13 * * 2-6",
    ]
    assert workflow["jobs"]["forward-lab"]["if"] == MAIN_ONLY
    assert workflow["concurrency"]["cancel-in-progress"] is False

    # Preserve the independent no-current-UTC-day gates; do not permit
    # the source vendor's partial current-day quote into the frozen ledger.
    source = (ROOT / "fund100_forward.py").read_text(encoding="utf-8")
    adapter = (ROOT / "fund100.py").read_text(encoding="utf-8")
    assert "prices.index.date\n        < today_utc" in source
    assert "close.index < today_utc" in adapter


def test_forward_source_repairs_get_authentic_main_branch_rerun_without_loop():
    """A merged source repair should validate real prices, not wait for cron.

    Never trigger on the generated ledger, which the job commits to main;
    that would create a self-triggering, contents-write workflow loop.
    """
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/fund100-forward.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on", workflow.get(True))
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert push["paths"] == [
        "fund100.py",
        "fund100_forward.py",
        "fund100_forward_v1_1.py",
        "fund100_forward_evidence_scorecard_v1_0.py",
        ".github/workflows/fund100-forward.yml",
    ]
    assert all("forward_outputs" not in path for path in push["paths"])
    assert "pull_request" not in triggers
    assert workflow["jobs"]["forward-lab"]["if"] == MAIN_ONLY
    assert workflow["concurrency"]["cancel-in-progress"] is False
    # Keep the original full tests, original-source run, evidence scorecard
    # and main-only append-only state commit in the same guarded job.
    steps = workflow["jobs"]["forward-lab"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    for command in (
        "pytest -q",
        "python fund100_forward_v1_1.py",
        "python fund100_forward_evidence_scorecard_v1_0.py",
        "git push origin HEAD:main",
    ):
        assert command in commands


def test_forward_rerun_workflow_changes_require_full_live_static_audit():
    audit = yaml.safe_load(
        (ROOT / ".github/workflows/fund100-live-static-audit.yml").read_text(
            encoding="utf-8"
        )
    )
    triggers = audit.get("on", audit.get(True))
    for event in ("push", "pull_request"):
        paths = triggers[event]["paths"]
        assert ".github/workflows/fund100-forward.yml" in paths
        assert "fund100_forward_v1_1.py" in paths
        assert "test_fund100_main_only_forward_ledger_workflows.py" in paths


def test_forward_publish_race_recomputes_from_new_main(tmp_path):
    """Real local Git race: stale output must never overwrite newer evidence.

    The workflow script runs against a bare local remote with two clones.
    No network, market data or broker access is involved; the engine and
    pytest commands are replaced by explicit, deterministic test stubs.
    """
    import os
    import subprocess

    def git(*args, cwd=None):
        return subprocess.run(
            ["git", *map(str, args)], cwd=cwd, check=True,
            text=True, capture_output=True,
        ).stdout.strip()

    remote = tmp_path / "remote.git"
    worker = tmp_path / "worker"
    contender = tmp_path / "contender"
    git("init", "--bare", "--initial-branch=main", remote)
    git("clone", remote, worker)
    git("checkout", "-B", "main", cwd=worker)
    git("config", "user.name", "test", cwd=worker)
    git("config", "user.email", "test@example.invalid", cwd=worker)
    output_dir = worker / "forward_outputs"
    output_dir.mkdir()
    (output_dir / "ledger.txt").write_text("baseline\n")
    git("add", "forward_outputs", cwd=worker)
    git("commit", "-m", "baseline", cwd=worker)
    git("push", "-u", "origin", "main", cwd=worker)

    git("clone", remote, contender)
    git("config", "user.name", "test", cwd=contender)
    git("config", "user.email", "test@example.invalid", cwd=contender)
    (contender / "forward_outputs" / "ledger.txt").write_text(
        "baseline\nconcurrent\n"
    )
    git("add", "forward_outputs", cwd=contender)
    git("commit", "-m", "concurrent ledger advance", cwd=contender)
    git("push", "origin", "HEAD:main", cwd=contender)

    # The worker computed an obsolete result before seeing the new main.
    (output_dir / "ledger.txt").write_text("baseline\nstale\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pytest").write_text(
        "#!/bin/sh\nprintf 'tested\n' > .replay-tests-ran\n"
    )
    (bin_dir / "python").write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  fund100_forward_v1_1.py) printf 'replayed\n' >> forward_outputs/ledger.txt ;;\n"
        "  fund100_forward_evidence_scorecard_v1_0.py) printf 'scorecard\n' > forward_outputs/scorecard.txt ;;\n"
        "  *) exit 2 ;;\n"
        "esac\n"
    )
    for tool in ("pytest", "python"):
        (bin_dir / tool).chmod(0o755)

    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/fund100-forward.yml").read_text(
            encoding="utf-8"
        )
    )
    step = next(
        s for s in workflow["jobs"]["forward-lab"]["steps"]
        if s["name"] == "Commit Forward Lab state"
    )
    assert step["id"] == "forward_commit"
    script = step["run"]
    assert "git push --force" not in script
    assert "git pull --rebase" not in script
    assert "for attempt in 1 2 3" in script

    github_output = tmp_path / "github_output"
    env = dict(os.environ)
    env["GITHUB_OUTPUT"] = str(github_output)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=worker, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert github_output.read_text().strip() == "forward_published=true"
    assert (worker / ".replay-tests-ran").read_text().strip() == "tested"

    # A successful replay is derived from the concurrent ledger, never
    # from the stale worker output, and has no duplicate original rows.
    git("fetch", "origin", "main", cwd=worker)
    actual = git("show", "origin/main:forward_outputs/ledger.txt", cwd=worker)
    assert actual.splitlines() == ["baseline", "concurrent", "replayed"]
    assert git("show", "origin/main:forward_outputs/scorecard.txt", cwd=worker) == "scorecard"

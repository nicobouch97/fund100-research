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

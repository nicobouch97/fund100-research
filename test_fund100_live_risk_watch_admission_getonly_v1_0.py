"""Strict offline proof tests: no broker API, no GitHub writes, no real HTTP."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

import fund100_live_risk_watch_admission_getonly_v1_0 as gate

NOW = datetime(2026, 11, 11, 16, 18, tzinfo=timezone.utc)
SHA = "a" * 40
TOKEN = "mock-get-only-actions-token"


def healthy():
    run = {
        "id": 123456789, "name": "Fund-100 V6-S1 Independent First ACWI Risk Watch (NO TRADE)",
        "path": gate.WATCH_PATH, "event": "schedule",
        "head_branch": "main", "head_sha": SHA, "run_attempt": 1,
        "status": "completed", "conclusion": "success",
        "created_at": "2026-11-11T16:04:00Z",
        "updated_at": "2026-11-11T16:04:31Z",
    }
    job = {
        "name": gate.WATCH_JOB_NAME, "run_id": run["id"],
        "head_sha": SHA, "status": "completed", "conclusion": "success",
        "steps": [
            {"name": gate.CHECK_STEP, "status": "completed",
             "conclusion": "success"},
            {"name": gate.PASS_STEP, "status": "completed",
             "conclusion": "success"},
        ],
    }
    return {"workflow_runs": [run]}, {"total_count": 1, "jobs": [job]}


def mock_transport(listing, jobs, *, error=None):
    class Resp:
        status = 200

        def __init__(self, doc):
            self.doc = doc

        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return False

        def read(self, size):
            raw = json.dumps(self.doc).encode("utf-8")
            return raw[:size]

    def send(request, timeout):
        assert request.get_method() == "GET"
        assert request.headers["Authorization"] == "Bearer " + TOKEN
        assert timeout == 10
        if error:
            raise error
        if request.full_url == gate.WORKFLOW_RUNS:
            return Resp(listing)
        assert request.full_url == (
            gate.API + "/actions/runs/123456789/jobs?per_page=100")
        return Resp(jobs)

    return send


def verify(listing=None, jobs=None, *, now=NOW, token=TOKEN,
           main_sha=SHA, error=None):
    baseline_list, baseline_jobs = healthy()
    return gate.require_recent_scheduled_risk_pass(
        token=token, main_sha=main_sha, now_utc=now,
        transport=mock_transport(
            baseline_list if listing is None else listing,
            baseline_jobs if jobs is None else jobs, error=error))


def test_fresh_scheduled_running_broker_risk_pass_is_readonly_admission():
    assert gate.NO_BROKER_ACCESS is True
    assert gate.NO_GITHUB_WRITES is True
    assert gate.NO_TRADE_RELEASE is True
    assert verify() is True


@pytest.mark.parametrize("field,bad", [
    ("event", "workflow_dispatch"),
    ("path", ".github/workflows/attacker.yml"),
    ("name", "Different workflow"),
    ("head_branch", "test"),
    ("head_sha", "b" * 40),
    ("run_attempt", 2),
    ("status", "queued"),
    ("conclusion", "failure"),
    ("id", False),
    ("created_at", "2026-11-11T15:40:00Z"),
    ("created_at", "2026-11-11T16:18:30Z"),
    ("updated_at", "2026-11-11T15:43:00Z"),
    ("updated_at", "2026-11-11T16:18:30Z"),
])
def test_invalid_latest_schedule_always_denied(field, bad):
    runs, jobs = healthy()
    runs["workflow_runs"][0][field] = bad
    with pytest.raises(gate.RiskWatchAdmissionStop):
        verify(runs, jobs)


def test_newer_failed_run_never_falls_back_to_older_pass():
    runs, jobs = healthy()
    newer = deepcopy(runs["workflow_runs"][0])
    newer.update(id=987654321, created_at="2026-11-11T16:17:00Z",
                 updated_at="2026-11-11T16:17:05Z",
                 conclusion="failure")
    runs["workflow_runs"].insert(0, newer)
    with pytest.raises(gate.RiskWatchAdmissionStop, match="latest"):
        verify(runs, jobs)


@pytest.mark.parametrize("change", [
    lambda j: j["steps"].pop(),
    lambda j: j["steps"][1].update(conclusion="skipped"),
    lambda j: j["steps"][0].update(conclusion="failure"),
    lambda j: j["steps"].append(deepcopy(j["steps"][-1])),
    lambda j: j.update(status="in_progress"),
    lambda j: j.update(conclusion="failure"),
    lambda j: j.update(head_sha="b" * 40),
    lambda j: j.update(run_id=13),
    lambda j: j.update(name="Untrusted job"),
])
def test_stopped_or_non_pass_step_never_admitted(change):
    runs, jobs = healthy()
    change(jobs["jobs"][0])
    with pytest.raises(gate.RiskWatchAdmissionStop,
                       match="PASS step"):
        verify(runs, jobs)


def test_incomplete_job_page_is_denied():
    runs, jobs = healthy()
    jobs["total_count"] = 2
    with pytest.raises(gate.RiskWatchAdmissionStop, match="incomplete"):
        verify(runs, jobs)


def test_no_scheduled_runs_is_not_a_healthy_monitor():
    _, jobs = healthy()
    with pytest.raises(gate.RiskWatchAdmissionStop, match="listing"):
        verify({"workflow_runs": []}, jobs)


def test_unknown_or_invalid_api_response_fails_closed():
    runs, jobs = healthy()
    for altered in ({}, {"workflow_runs": "oops"},
                    {"workflow_runs": [42]}):
        with pytest.raises(gate.RiskWatchAdmissionStop):
            verify(altered, jobs)
    with pytest.raises(gate.RiskWatchAdmissionStop, match="unavailable"):
        verify(runs, jobs, error=TimeoutError())


def test_invalid_credentials_expected_sha_or_naive_time_denied():
    for kwargs in (
        {"token": "bad"}, {"token": TOKEN + "\n"},
        {"main_sha": "not-a-sha"},
        {"now": datetime(2026, 11, 11, 16, 18)},
    ):
        with pytest.raises(gate.RiskWatchAdmissionStop):
            verify(**kwargs)


def test_exact_watch_step_and_workflow_contract_is_readonly():
    from pathlib import Path
    workflow = Path(".github/workflows/fund100-v6-s1-independent-risk-watch.yml").read_text()
    monitor = Path("fund100_v6_s1_independent_risk_watch_v1_0.py").read_text()
    entry = Path("fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py").read_text()
    assert "id: v6_risk" in workflow
    assert "name: " + gate.PASS_STEP in workflow
    assert "github.event_name == 'schedule'" in workflow
    assert "steps.v6_risk.outputs.verified_v6_original_acwi_risk == 'YES'" in workflow
    assert 'return EXPECTED_PASS' in monitor
    assert 'return "ALREADY_STOPPED"' in monitor
    assert "live_watch.require_recent_scheduled_risk_pass(" in entry
    assert "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False" in entry
    assert "ONE_ATTEMPT_EXECUTION_RELEASED=False" in Path(
        "fund100_v6_s1_original_one_attempt_chain_locked_v1_0.py").read_text()

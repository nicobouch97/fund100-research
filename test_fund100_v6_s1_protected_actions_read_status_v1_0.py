"""Locked original STOP and authenticated workflow_dispatch on main."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_s1_protected_actions_read_status_v1_0 as s


def run(*, ident=99, created="2026-10-21T11:55:00Z", event="workflow_dispatch",
        branch="main", status="completed", conclusion="success",
        path=s.WORKFLOW_PATH, repo=s.REPO):
    return {"id": ident, "created_at": created, "event": event,
            "head_branch": branch, "status": status, "conclusion": conclusion,
            "path": path, "repository": {"full_name": repo}}


def jobs(*, protected_conclusion="success", missing_step=None,
         bad_step=None, offline_conclusion="success"):
    steps = [
        {"name": x, "status": "completed",
         "conclusion": "failure" if x == bad_step else "success"}
        for x in sorted(s.PROTECTED_STEPS) if x != missing_step
    ]
    return {"jobs": [
        {"name": s.OFFLINE_JOB, "status": "completed",
         "conclusion": offline_conclusion, "steps": []},
        {"name": s.PROTECTED_JOB, "status": "completed",
         "conclusion": protected_conclusion, "steps": steps},
    ]}


def report(run_list, job_data=None):
    return s.assess(run_data={"workflow_runs": run_list},
                    job_data=job_data)


def test_current_repo_stopped_original_cap_and_v6_proposal():
    assert s.original_stop()
    assert not s.BROKER_NETWORK_ALLOWED
    assert not s.PRIVATE_STATE_ACCESS_ALLOWED
    assert not s.TRADE_ALLOWED


def test_no_manual_run_remains_unproven():
    r = report([])
    assert r["protected_private_actions_read_status"] == "NOT_PROVEN"
    assert r["missing_manual_main_run"] is True
    assert not r["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]
    assert not r["live_launch_ready"]
    assert r["live_orders"] == r["private_repository_reads"] == 0


def test_genuine_successful_manual_main_protected_job_is_only_read_proof():
    r = report([run()], jobs())
    assert r["protected_private_actions_read_status"] == (
        "VERIFIED_PROTECTED_ACTIONS_PRIVATE_READ")
    assert r["most_recent_manual_main_run_id"] == 99
    assert r["eligible_successful_protected_main_run"]
    assert r["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]
    assert not r["private_state_CAS_write_permission_proven"]
    assert not r["broker_cash_settlement_or_buying_power_revalidated"]
    assert not r["live_launch_ready"]
    assert not r["paper_or_live_order_authorized"]
    assert r["account_original_ceiling_usd"] == "130.30"


@pytest.mark.parametrize("alter", [
    {"event": "pull_request"},
    {"event": "push"},
    {"branch": "feature"},
    {"status": "in_progress", "conclusion": None},
    {"repo": "other/repository"},
    {"path": ".github/workflows/not-the-right-one.yml"},
    {"created": "2026-10-20T23:59:59Z"},
])
def test_other_event_wrong_repo_or_early_source_not_credential_proof(alter):
    r = report([run(**alter)], jobs())
    assert r["protected_private_actions_read_status"] != (
        "VERIFIED_PROTECTED_ACTIONS_PRIVATE_READ")
    assert not r["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]


def test_older_success_cannot_hide_newer_failed_protected_probe():
    result = report([
        run(ident=100, created="2026-10-21T10:00:00Z"),
        run(ident=101, created="2026-10-21T12:00:00Z",
            conclusion="failure"),
    ], jobs())
    assert result["most_recent_manual_main_run_id"] == 101
    assert result["protected_private_actions_read_status"] == (
        "LATEST_MANUAL_MAIN_RUN_NOT_SUCCESSFUL")
    assert not result["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]


def test_irrelevant_PR_does_not_override_actual_main_manual_run():
    result = report([
        run(ident=100, created="2026-10-21T10:00:00Z"),
        run(ident=101, created="2026-10-21T12:00:00Z",
            event="pull_request", branch="feature"),
    ], jobs())
    assert result["most_recent_manual_main_run_id"] == 100
    assert result["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]


def test_job_and_step_success_necessary_not_only_workflow_green():
    auth = "Authenticate private repo identity and README only (redacted two GET)"
    for kw in ({"protected_conclusion": "skipped"},
               {"protected_conclusion": "failure"},
               {"offline_conclusion": "failure"},
               {"missing_step": auth},
               {"bad_step": auth}):
        r = report([run()], jobs(**kw))
        assert r["protected_private_actions_read_status"] == (
            "LATEST_RUN_PROTECTED_JOB_OR_STEP_NOT_PROVEN")
        assert not r["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]


def test_missing_or_fake_metadata_and_incomplete_pagination_rejected():
    for source in ({}, {"workflow_runs": {}},
                   {"workflow_runs": [run()] * 31}):
        with pytest.raises(s.StatusStop):
            s.select_latest_run(source)
    assert report([run()], None)["protected_private_actions_read_status"] == (
        "LATEST_RUN_PROTECTED_JOB_OR_STEP_NOT_PROVEN")


def test_stop_change_fails_closed_without_any_status_promotion(tmp_path):
    src = s.ROOT
    paths = [
        Path("fund100_live_operator_control.json"),
        Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"),
    ]
    for f in paths:
        (tmp_path/f).parent.mkdir(parents=True, exist_ok=True)
        copy2(src/f, tmp_path/f)
    assert s.original_stop(tmp_path)
    f=tmp_path/paths[0]
    doc=json.loads(f.read_text());doc["trading_enabled"]=True
    f.write_text(json.dumps(doc))
    assert not s.original_stop(tmp_path)
    with pytest.raises(s.StatusStop, match="STOP"):
        s.retrieve(token="synthetic-not-used",root=tmp_path)


def test_retrieve_uses_only_pinned_two_public_actions_metadata_GET(monkeypatch):
    seen=[]
    original=run()
    def fake_get(uri, token):
        seen.append((uri,token))
        if uri==s.RUNS:
            return {"workflow_runs":[original]}
        assert uri==f"https://api.github.com/repos/{s.REPO}/actions/runs/99/jobs?per_page=100"
        return jobs()
    monkeypatch.setattr(s,"_get",fake_get)
    result=s.retrieve(token="test-token-never-logged")
    assert result["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]
    assert len(seen)==2
    assert all("fund100-state-private" not in uri for uri,_ in seen)
    assert all("api.alpaca.markets" not in uri for uri,_ in seen)


def test_missing_action_token_is_evidence_unavailable_never_live():
    r=s.retrieve(token="")
    assert r["protected_private_actions_read_status"] == (
        "GITHUB_ACTIONS_PUBLIC_METADATA_EVIDENCE_UNAVAILABLE")
    assert not r["private_repo_read_proved_via_protected_GITHUB_ACTIONS"]
    assert not r["paper_or_live_order_authorized"]


def test_module_lacks_order_private_repo_tokens_and_write_requests():
    code = Path(s.__file__).read_text()
    for marker in ("fund100-state-private", "ALPACA_LIVE_KEY",
                   "ALPACA_LIVE_SECRET", "/v2/orders", "place_order(",
                   "method=\"POST\"", "method='POST'", "requests.post("):
        assert marker not in code

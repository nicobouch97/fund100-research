"""No-network adversarial tests for explicit GET-only original STOP recovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json

import pytest

import fund100_stop_explicit_original_getonly_v1_0 as x

RUN_ID=43617230118
SHA="a"*40
URL=x.gh.API


@pytest.fixture
def authentic(monkeypatch):
    env={
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":x.REPO,
        "GITHUB_EVENT_NAME":"workflow_dispatch",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_WORKFLOW_REF":x.WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_SHA":SHA,
        "GITHUB_EVENT_PATH":"/home/runner/work/_temp/_github_workflow/event.json",
        "GITHUB_TOKEN":"OFFLINE_GITHUB_READ_TOKEN_1234567890123456",
    }
    for k,v in env.items():
        monkeypatch.setenv(k,v)
    for k in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY","ALPACA_PAPER_SECRET",
        "FUND100_GH_STOP_DISPATCH_TOKEN",
        "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
    ):
        monkeypatch.delenv(k,raising=False)
    event={"inputs":{"original_stop_run_id":str(RUN_ID)}}
    real_open=open
    def fake_open(filename,*args,**kwargs):
        if str(filename).endswith("/event.json"):
            return io.BytesIO(json.dumps(event).encode())
        return real_open(filename,*args,**kwargs)
    monkeypatch.setattr("builtins.open",fake_open)
    now=datetime.now(timezone.utc).replace(microsecond=0)
    def ts(delta):
        return (now+timedelta(seconds=delta)).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc={
        "id":RUN_ID,"name":x.contract.WORKFLOW_NAME,
        "path":x.gh.STOP_PATH,"event":"workflow_dispatch",
        "head_branch":"main","head_sha":SHA,
        "status":"completed","conclusion":"success","run_attempt":1,
        "created_at":ts(-50),"run_started_at":ts(-48),
        "updated_at":ts(-30),
    }
    jobs=[]
    for name,required in x.contract.REQUIRED_JOBS.items():
        jobs.append({
            "run_id":RUN_ID,"name":name,"status":"completed",
            "conclusion":"success","head_sha":SHA,
            "started_at":ts(-45),"completed_at":ts(-35),
            "steps":[{"name":s,"status":"completed","conclusion":"success"}
                     for s in required],
        })
    responses={
        URL+"/actions/runs/"+str(RUN_ID):doc,
        URL+"/actions/runs/"+str(RUN_ID)+"/jobs?per_page=100":
            {"total_count":3,"jobs":jobs},
    }
    calls=[]
    def get(url,*,token):
        calls.append(("get",url,token))
        if url not in responses:
            raise AssertionError("Unexpected GitHub URL")
        return responses[url]
    def control(path,*,token):
        calls.append(("control",path,token))
        if path not in (x.gh.V5_PATH,x.gh.V6_PATH):
            raise AssertionError("Wrong current-main STOP file")
        return {"trading_enabled":False}
    monkeypatch.setattr(x.gh,"_get",get)
    monkeypatch.setattr(x.gh,"_control",control)
    return event,doc,jobs,calls


def test_genuine_original_id_only_proves_three_jobs_current_stop_no_broker(authentic):
    event,doc,jobs,calls=authentic
    out=x.observe_once()
    assert out["original_dispatch_run_id"]==RUN_ID
    assert out["required_jobs_verified"]==3
    assert out["stop_completed"] is False
    assert out["signed_stop_receipt"] is False
    assert out["broker_observed"] is False
    assert out["order_authorized"] is False
    assert [a[0] for a in calls]==[
        "get","get","control","control","control","control"]


@pytest.mark.parametrize("name,value",[
    ("GITHUB_ACTIONS","false"),
    ("GITHUB_EVENT_NAME","workflow_run"),
    ("GITHUB_REF","refs/heads/feature"),
    ("GITHUB_REPOSITORY","other/repo"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_SHA","bad"),
    ("GITHUB_WORKFLOW_REF","other/workflow"),
])
def test_bad_scope_never_reads_github(authentic,monkeypatch,name,value):
    _,_,_,calls=authentic
    monkeypatch.setenv(name,value)
    with pytest.raises(x.ExplicitStopHold,match="scope"):
        x.observe_once()
    assert not calls


@pytest.mark.parametrize("secret",[
    "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
    "FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
])
def test_no_broker_dispatch_signer_colocation(authentic,monkeypatch,secret):
    *_,calls=authentic
    monkeypatch.setenv(secret,"CREDENTIAL_FORBIDDEN")
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert not calls


@pytest.mark.parametrize("bad",[
    "", "0", "-1","01","123e3","1.0", "TRUE", "9"*25,
])
def test_input_is_untrusted_run_locator_only(authentic,bad):
    event,_,_,calls=authentic
    event["inputs"]["original_stop_run_id"]=bad
    with pytest.raises(x.ExplicitStopHold,match="locator"):
        x.observe_once()
    assert not calls


def test_unexpected_input_keys_rejected(authentic):
    event,_,_,calls=authentic
    event["inputs"]["new_orders"]="yes"
    with pytest.raises(x.ExplicitStopHold,match="Unexpected"):
        x.observe_once()
    assert not calls


@pytest.mark.parametrize("field,bad",[
    ("id",RUN_ID+1),("head_branch","evil"),
    ("event","push"),("path",".github/workflows/other.yml"),
    ("conclusion","failure"),("run_attempt",2),
    ("status","in_progress"),("head_sha","bad"),
    ("updated_at","2020-01-01T00:00:00Z"),
])
def test_wrong_or_stale_original_run_fails(authentic,field,bad):
    _,doc,_,calls=authentic
    doc[field]=bad
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert [y[0] for y in calls].count("control")==0


def test_incomplete_job_set_is_not_success(authentic):
    _,_,jobs,calls=authentic
    jobs[0]["conclusion"]="failure"
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert not any(c[0]=="control" for c in calls)


def test_wrong_job_step_is_not_success(authentic):
    _,_,jobs,calls=authentic
    jobs[1]["steps"][0]["conclusion"]="skipped"
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert not any(c[0]=="control" for c in calls)


def test_get_transport_error_has_no_broker_or_completion_claim(authentic,monkeypatch):
    _,_,_,calls=authentic
    def fail(*a,**k):
        raise x.gh.StopEventHold("NO PRIVATE DATA IN LOGS")
    monkeypatch.setattr(x.gh,"_get",fail)
    with pytest.raises(x.ExplicitStopHold,match="authenticated|Authenticated"):
        x.observe_once()


def _switch_to_repository_dispatch(authentic,monkeypatch):
    event,doc,jobs,calls=authentic
    monkeypatch.setenv("GITHUB_EVENT_NAME","repository_dispatch")
    event.clear()
    event.update({
        "action":x.REPOSITORY_EVENT_TYPE,
        "repository":{"full_name":x.REPO},
        "client_payload":{"original_stop_run_id":str(RUN_ID)},
    })
    return event,doc,jobs,calls


def test_repo_dispatch_event_checks_original_status_before_success(
        authentic,monkeypatch):
    event,doc,jobs,calls=_switch_to_repository_dispatch(authentic,monkeypatch)
    orig=x.gh._get
    state={"polls":0}
    def get(url,*,token):
        if url==URL+"/actions/runs/"+str(RUN_ID):
            state["polls"]+=1
            if state["polls"]==1:
                return {**doc,"status":"in_progress"}
        return orig(url,token=token)
    monkeypatch.setattr(x.gh,"_get",get)
    monkeypatch.setattr(x.time,"sleep",lambda seconds: None)
    out=x.observe_once()
    assert state["polls"]==3
    assert out["required_jobs_verified"]==3
    assert out["broker_observed"] is False
    assert out["signed_stop_receipt"] is False
    assert out["stop_completed"] is False
    assert out["order_authorized"] is False


@pytest.mark.parametrize("bad",[
    {"action":"wrong","repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":str(RUN_ID)}},
    {"action":x.REPOSITORY_EVENT_TYPE,"repository":{"full_name":"other/repo"},
     "client_payload":{"original_stop_run_id":str(RUN_ID)}},
    {"action":x.REPOSITORY_EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":str(RUN_ID),"rearm":True}},
    {"action":x.REPOSITORY_EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":"0"}},
])
def test_untrusted_repo_event_fails_before_github_get(authentic,monkeypatch,bad):
    event,doc,jobs,calls=_switch_to_repository_dispatch(authentic,monkeypatch)
    event.clear()
    event.update(bad)
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert not calls


def test_repo_dispatch_pending_expiry_fails_closed(authentic,monkeypatch):
    event,doc,jobs,calls=_switch_to_repository_dispatch(authentic,monkeypatch)
    orig=x.gh._get
    def get(url,*,token):
        if url==URL+"/actions/runs/"+str(RUN_ID):
            return {**doc,"status":"in_progress"}
        return orig(url,token=token)
    monkeypatch.setattr(x.gh,"_get",get)
    ticks=iter([0.0,179.0])
    monkeypatch.setattr(x.time,"monotonic",lambda:next(ticks))
    monkeypatch.setattr(x.time,"sleep",
                        lambda *_:pytest.fail("Should not sleep past bound"))
    with pytest.raises(x.ExplicitStopHold,match="not completed in time"):
        x.observe_once()
    assert not any(c[0]=="control" for c in calls)


def test_repo_dispatch_original_failure_is_not_verified(authentic,monkeypatch):
    event,doc,jobs,calls=_switch_to_repository_dispatch(authentic,monkeypatch)
    doc["conclusion"]="failure"
    with pytest.raises(x.ExplicitStopHold):
        x.observe_once()
    assert not any(c[0]=="control" for c in calls)


def test_workflow_original_verifier_is_credentialless_broker_is_separate():
    from pathlib import Path
    flow=Path(".github/workflows/fund100-stop-explicit-original-getonly.yml").read_text()
    assert "workflow_dispatch:" in flow
    assert "repository_dispatch:" in flow
    assert 'test "$GITHUB_EVENT_NAME" = workflow_dispatch || test "$GITHUB_EVENT_NAME" = repository_dispatch' in flow
    assert x.REPOSITORY_EVENT_TYPE in flow
    assert "test_fund100_stop_repo_dispatch_bridge_v1_0.py" in flow
    assert "original_stop_run_id:" in flow
    assert "  push:" not in flow
    assert "actions: write" not in flow
    assert "contents: write" not in flow
    assert "actions: read" in flow
    assert "contents: read" in flow
    assert "persist-credentials: false" in flow
    assert "python -B fund100_stop_explicit_original_getonly_v1_0.py" in flow
    original=flow.split("  explicit-main-stop-only:",1)[1].split(
        "  offline-explicit-proof-tests:",1)[0]
    broker=flow.split("  protected-repo-stop-broker-postflight:",1)[1].split(
        "  post-broker-repo-stop-recheck:",1)[0]
    after=flow.split("  post-broker-repo-stop-recheck:",1)[1]
    assert "ALPACA_LIVE_KEY:" not in original
    assert "ALPACA_LIVE_SECRET:" not in original
    assert "secrets." not in original
    assert "environment: fund100-live-broker" not in original
    assert "GITHUB_TOKEN: ${{ github.token }}" in original
    assert "environment: fund100-live-broker" in broker
    assert "needs.explicit-main-stop-only.result == 'success'" in broker
    assert "GITHUB_TOKEN:" not in broker
    assert "GITHUB_TOKEN: ${{ github.token }}" in after
    assert "ALPACA_LIVE_KEY:" not in after
    assert "ALPACA_LIVE_SECRET:" not in after
    assert "environment: fund100-live-broker" not in after
    assert "actions: write" not in after
    assert "needs: [explicit-main-stop-only, protected-repo-stop-broker-postflight]" in after
    assert "needs.protected-repo-stop-broker-postflight.result == 'success'" in after
    assert "python -B fund100_stop_explicit_original_getonly_v1_0.py" in after
    assert "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}" in broker
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in broker

"""No-network credentialless STOP workflow_run observer regressions."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha1
import io
import json
import re
from pathlib import Path

import pytest

import fund100_stop_workflow_run_event_getonly_v1_0 as obs
import fund100_v6_emergency_stop_completion_evidence_v1_0 as contract

SHA = "a"*40
ID = 43607294471
V5={"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False}
V6={"schema":"FUND100_V6_S1_OPERATOR_CONTROL_V2","risk_level":"HIGH",
    "pilot_capital_ceiling_usd":"130.30","trading_enabled":False,
    "first_original_acwi_sell_enabled":False}


def timestamp(delta_seconds):
    return (datetime.now(timezone.utc) +
            timedelta(seconds=delta_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def original_run():
    return {
        "id":ID, "name":contract.WORKFLOW_NAME, "path":contract.WORKFLOW,
        "event":"workflow_dispatch", "status":"completed",
        "conclusion":"success", "head_branch":"main", "head_sha":SHA,
        "run_attempt":1,"created_at":timestamp(-60),
        "run_started_at":timestamp(-58),"updated_at":timestamp(-30),
    }


def jobs():
    finished=timestamp(-31)
    started=timestamp(-54)
    return {
        "total_count":3,
        "jobs":[{
            "run_id":ID,"head_sha":SHA,"name":name,"status":"completed",
            "conclusion":"success","started_at":started,
            "completed_at":finished,
            "steps":[{"name":step,"status":"completed","conclusion":"success"}
                     for step in required]
        } for name,required in contract.REQUIRED_JOBS.items()]
    }


def event():
    return {
        "workflow_run":{
            **original_run(),
            "head_repository":{"full_name":obs.REPO},
        }
    }


def contents(path, item):
    raw=json.dumps(item,sort_keys=True).encode()
    digest=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    return {"type":"file","path":path,"encoding":"base64",
            "content":base64.b64encode(raw).decode(),
            "sha":digest}


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS","true")
    monkeypatch.setenv("GITHUB_REPOSITORY",obs.REPO)
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_run")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF",obs.WORKFLOW_REF)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT","1")
    monkeypatch.setenv("GITHUB_SHA",SHA)
    monkeypatch.setenv(
        "GITHUB_EVENT_PATH","/home/runner/work/_temp/_github_workflow/event.json")
    monkeypatch.setenv("GITHUB_TOKEN","SYNTHETIC_NO_WRITES_ACCESS_TOKEN_01234")
    for secret in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET","FUND100_ALPACA_READONLY_OAUTH_BEARER",
        "FUND100_GH_STOP_DISPATCH_TOKEN",
        "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
    ):
        monkeypatch.delenv(secret,raising=False)
    payload={"event":event(),"run":original_run(),
             "jobs":jobs(),"v5":V5.copy(),"v6":V6.copy(),
             "allowlist_get":obs._get}
    real_open=open
    def fake_open(file,*args,**kwargs):
        if str(file).endswith("/event.json"):
            return io.BytesIO(json.dumps(payload["event"]).encode())
        return real_open(file,*args,**kwargs)
    monkeypatch.setattr("builtins.open",fake_open)

    def fake_get(url,*,token):
        assert token=="SYNTHETIC_NO_WRITES_ACCESS_TOKEN_01234"
        assert url.startswith(obs.API)
        if re.fullmatch(re.escape(obs.API)+r"/actions/runs/[1-9][0-9]*",url):
            return payload["run"]
        if url==obs.API+"/actions/runs/"+str(ID)+"/jobs?per_page=100":
            return payload["jobs"]
        if re.fullmatch(re.escape(obs.API)+r"/contents/.*\?ref=main&nonce=[a-f0-9]{16}",url):
            path=url.split("/contents/",1)[1].split("?",1)[0]
            if path==obs.V5_PATH:
                return contents(path,payload["v5"])
            if path==obs.V6_PATH:
                return contents(path,payload["v6"])
        raise AssertionError("Unexpected fake GitHub GET "+url)
    monkeypatch.setattr(obs,"_get",fake_get)
    return payload


def test_genuine_three_job_and_main_stops_observer_no_broker(source):
    result=obs.observe_once()
    assert result=={
        "status":"STOP_WORKFLOW_AND_CONTROLS_ONLY_BROKER_NOT_OBSERVED",
        "original_dispatch_run_id":ID,"required_jobs_verified":3,
        "both_current_controls_stop_observed":True,
        "broker_open_orders_observed":False,
        "broker_fills_verified":False,
        "signed_receipt_produced":False,
        "stop_completed":False,
        "new_order_authorized":False,
    }


@pytest.mark.parametrize("target,value",[
    ("event", "wrong_run"),("event","wrong_repo"),("event","wrong_status"),
    ("event","wrong_head"),("event","wrong_workflow"),
    ("run","wrong_run"),("run","wrong_attempt"),("run","wrong_event"),
    ("run","wrong_branch"),("run","wrong_path"),("run","wrong_conclusion"),
    ("run","old"),("run","too_slow"),
    ("jobs","missing"),("jobs","extra"),("jobs","failed"),
    ("jobs","wrong_head"),("jobs","wrong_run_id"),
    ("jobs","step_failed"),("jobs","step_missing"),
    ("control","v5_go"),("control","v6_go"),
])
def test_event_latch_and_job_negatives_fail_closed(source,target,value):
    if target=="event":
        e=source["event"]["workflow_run"]
        if value=="wrong_run": e["id"]=123
        if value=="wrong_repo": e["head_repository"]["full_name"]="evil/repo"
        if value=="wrong_status": e["status"]="queued"
        if value=="wrong_head": e["head_sha"]="invalid"
        if value=="wrong_workflow": e["path"]="different.yml"
    if target=="run":
        r=source["run"]
        if value=="wrong_run":r["id"]=999
        if value=="wrong_attempt":r["run_attempt"]=2
        if value=="wrong_event":r["event"]="push"
        if value=="wrong_branch":r["head_branch"]="feature"
        if value=="wrong_path":r["path"]="other.yml"
        if value=="wrong_conclusion":r["conclusion"]="failure"
        if value=="old":r.update({"created_at":timestamp(-450),
                                  "run_started_at":timestamp(-445),
                                  "updated_at":timestamp(-350)})
        if value=="too_slow":r.update({"created_at":timestamp(-420),
                                      "run_started_at":timestamp(-420),
                                      "updated_at":timestamp(-30)})
    if target=="jobs":
        j=source["jobs"]
        if value=="missing":j["jobs"].pop();j["total_count"]=2
        if value=="extra":j["jobs"].append(j["jobs"][0]);j["total_count"]=4
        if value=="failed":j["jobs"][0]["conclusion"]="failure"
        if value=="wrong_head":j["jobs"][0]["head_sha"]="b"*40
        if value=="wrong_run_id":j["jobs"][0]["run_id"]=ID+1
        if value=="step_failed":j["jobs"][0]["steps"][0]["conclusion"]="failure"
        if value=="step_missing":j["jobs"][0]["steps"].pop()
    if target=="control":
        if value=="v5_go":source["v5"]["trading_enabled"]=True
        if value=="v6_go":source["v6"]["trading_enabled"]=True
    with pytest.raises(obs.StopEventHold):
        obs.observe_once()


@pytest.mark.parametrize("name,value",[
    ("GITHUB_REF","refs/heads/feature"),
    ("GITHUB_EVENT_NAME","workflow_dispatch"),
    ("GITHUB_WORKFLOW_REF","evil.yml"),
    ("GITHUB_SHA","malformed"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_REPOSITORY","evil/repo"),
])
def test_wrong_provenance_never_calls_github(source,monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    monkeypatch.setattr(obs,"_get",lambda **kw:pytest.fail("No GitHub GET"))
    with pytest.raises(obs.StopEventHold):
        obs.observe_once()


@pytest.mark.parametrize("forbidden",[
    "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
    "FUND100_ALPACA_READONLY_OAUTH_BEARER",
    "FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
])
def test_no_broker_token_signer_or_dispatch_key_in_observer(
        source,monkeypatch,forbidden):
    monkeypatch.setenv(forbidden,"FAKE_SHOULD_NOT_GET_HERE")
    monkeypatch.setattr(obs,"_get",lambda **kw:pytest.fail("No source call"))
    with pytest.raises(obs.StopEventHold):
        obs.observe_once()


def test_reject_non_allowlisted_api_urls_and_methods(source,monkeypatch):
    monkeypatch.setattr(obs,"build_opener",lambda *a:pytest.fail("No transport"))
    for bad in (
        "https://api.alpaca.markets/v2/orders",
        "https://api.github.com/repos/"+obs.REPO+"/actions/workflows/trade.yml/dispatches",
        obs.API+"/contents/other.json?ref=main&nonce="+"a"*16,
        obs.API+"/actions/runs/123/cancel",
    ):
        with pytest.raises(obs.StopEventHold,match="allowlisted"):
            source["allowlist_get"](bad,token="FAKE_READ")


def test_exact_protected_main_blob_digest_mismatch_refused(source,monkeypatch):
    def tamper(url,*,token):
        if "/contents/" not in url:
            return source["run"] if "/jobs?" not in url else source["jobs"]
        path=url.split("/contents/",1)[1].split("?",1)[0]
        a=contents(path,V5 if path==obs.V5_PATH else V6)
        a["sha"]="0"*40
        return a
    monkeypatch.setattr(obs,"_get",tamper)
    with pytest.raises(obs.StopEventHold,match="hash invalid"):
        obs.observe_once()


def test_fully_credentialless_no_trade_or_broker_side_effects():
    source=Path(obs.__file__).read_text()
    assert "NO_BROKER_ACCESS = True" in source
    assert "NO_GITHUB_WRITE = True" in source
    assert "NO_SIGNING = True" in source
    assert "NO_STOP_COMPLETION_CLAIM = True" in source
    assert "def observe_once()" in source
    assert "api.alpaca.markets" not in source
    assert 'method="POST"' not in source
    assert "cancel_open" not in source

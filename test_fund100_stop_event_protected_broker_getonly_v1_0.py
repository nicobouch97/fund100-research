"""Synthetic no-network adversarial tests for protected post-STOP broker GET."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import re
from pathlib import Path

import pytest
import fund100_stop_event_protected_broker_getonly_v1_0 as post


ACCOUNT_ID="synthetic-account-test-567890"
ACCOUNT_HASH=sha256(("FUND100-LIVE-ACCOUNT|"+ACCOUNT_ID).encode()).hexdigest()
RUN_ID=43607294471
SHA="e"*40


@pytest.fixture
def protected(monkeypatch,tmp_path):
    e={
        "GITHUB_ACTIONS":"true", "GITHUB_REPOSITORY":post.REPO,
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_EVENT_NAME":"workflow_run",
        "GITHUB_WORKFLOW_REF":post.WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1", "GITHUB_SHA":SHA,
        "GITHUB_EVENT_PATH":"/home/runner/work/_temp/_github_workflow/event.json",
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
        "FUND100_LIVE_WRITE_MODE":"DISABLED",
    }
    for k,v in e.items():monkeypatch.setenv(k,v)
    for k in ("GITHUB_TOKEN","GH_TOKEN","FUND100_GH_STOP_DISPATCH_TOKEN",
              "FUND100_ALPACA_READONLY_OAUTH_BEARER",
              "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
              "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX"):
        monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(post,"EXPECTED_ACCOUNT_BINDING_SHA256",ACCOUNT_HASH)
    policy=dict(account_binding_sha256=ACCOUNT_HASH,
                capital_ceiling_usd=post.EXPECTED_CAPITAL_CEILING_USD,
                deployment_mode="LIVE_MICRO_PILOT",
                live_order_authorization_present=False,
                leverage_allowed=False,shorting_allowed=False)
    p=tmp_path/"policy.json"
    p.write_text(json.dumps(policy),encoding="utf-8")
    monkeypatch.setattr(post,"POLICY_PATH",p)
    event={"workflow_run":{
        "id":RUN_ID,"name":post.STOP_WORKFLOW,"path":post.STOP_WORKFLOW_PATH,
        "event":"workflow_dispatch","head_branch":"main",
        "head_repository":{"full_name":post.REPO},
        "status":"completed","conclusion":"success","run_attempt":1,
        "head_sha":SHA,"updated_at":(
            datetime.now(timezone.utc)-timedelta(seconds=20)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }}
    original_open=open
    def fake_open(file,*a,**k):
        if str(file).endswith("/event.json"):
            return io.BytesIO(json.dumps(event).encode("utf-8"))
        return original_open(file,*a,**k)
    monkeypatch.setattr("builtins.open",fake_open)
    monkeypatch.setattr(post.broker,"load_credentials",
                        lambda:("OFFLINE_KEY","OFFLINE_SECRET"))
    values={"account":{"id":ACCOUNT_ID,"status":"ACTIVE"},"orders":[]}
    calls=[]
    def fake_get(*,path,key,secret,params=None):
        calls.append((path,key,secret,params))
        if path=="/v2/account" and params is None:
            return values["account"]
        if path=="/v2/orders" and params==post.OPEN_ORDER_PARAMS:
            return values["orders"]
        raise AssertionError("Unexpected GET route")
    monkeypatch.setattr(post.broker,"get_json",fake_get)
    return values,event,policy,calls,p


def test_success_is_ONLY_point_in_time_live_broker_get_no_trade(protected):
    values,event,policy,calls,p=protected
    out=post.observe_broker_once()
    assert out=={
        "schema":post.SCHEMA,
        "status":"LIVE_BROKER_NO_OPEN_FUND100_AT_THIS_GET_ONLY",
        "original_stop_run_id":RUN_ID,
        "live_broker_get_count":2,
        "issuer_level_credential_is_readonly":False,
        "new_broker_orders":0,
        "broker_orders_modified":0,
        "broker_fills_verified":False,
        "signed_stop_completion_receipt":False,
        "stop_completed":False,
        "order_authorized":False,
    }
    assert [(x[0],x[3]) for x in calls]==[
        ("/v2/account",None),("/v2/orders",{"status":"open","limit":500})]
    assert all(x[1:3]==("OFFLINE_KEY","OFFLINE_SECRET") for x in calls)


@pytest.mark.parametrize("field,value",[
    ("GITHUB_REPOSITORY","other/repo"),("GITHUB_REF","refs/heads/test"),
    ("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_WORKFLOW_REF","untrusted/workflow"),
    ("GITHUB_RUN_ATTEMPT","2"),("GITHUB_SHA","bad"),
    ("FUND100_RISK_LEVEL","MEDIUM"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
    ("FUND100_ENABLE_LIVE_READONLY",""),
    ("FUND100_LIVE_WRITE_MODE","ENABLED"),
])
def test_bad_scope_never_reads_broker(protected,monkeypatch,field,value):
    *_,calls,p=protected
    monkeypatch.setenv(field,value)
    with pytest.raises(post.PostStopBrokerHold,match="scope"):
        post.observe_broker_once()
    assert not calls


@pytest.mark.parametrize("name",[
    "GITHUB_TOKEN","GH_TOKEN","FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_ALPACA_READONLY_OAUTH_BEARER",
    "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
])
def test_never_co_locate_broker_with_github_or_signer_secret(
        protected,monkeypatch,name):
    *_,calls,p=protected
    monkeypatch.setenv(name,"SHOULD_NOT_BE_HERE")
    with pytest.raises(post.PostStopBrokerHold,match="scope"):
        post.observe_broker_once()
    assert not calls


@pytest.mark.parametrize("change",[
    ("conclusion","failure"),("conclusion","cancelled"),
    ("run_attempt",2),("event","push"),("head_branch","other"),
    ("name","Other workflow"),("path","another.yml"),
    ("id",True),("id",0),("head_sha","a"),("updated_at","2020-01-01T00:00:00Z"),
])
def test_invalid_original_event_never_enters_broker_job(
        protected,change):
    values,event,policy,calls,p=protected
    field,bad=change
    event["workflow_run"][field]=bad
    with pytest.raises(post.PostStopBrokerHold):
        post.observe_broker_once()
    assert not calls


@pytest.mark.parametrize("order",[
    {"client_order_id":"f100live-abcdefabcdef-b-acwi"},
    {"client_order_id":"f100v6s1-abcdefabcdefabcdefabcdef-s"},
    {"client_order_id":"FUND100-FUTURE-STRATEGY"},
    {"client_order_id":"f100-live-bootstrap-0123456789abcdef-s-acwi"},
    {"client_order_id":None},
    {"client_order_id":""},
    {"client_order_id":33},
])
def test_any_potential_fund100_or_unattributable_open_order_holds(
        protected,order):
    values,event,policy,calls,p=protected
    values["orders"]=[order]
    with pytest.raises(post.PostStopBrokerHold):
        post.observe_broker_once()


def test_other_customer_open_order_is_not_cancelled_or_hidden(protected):
    values,event,policy,calls,p=protected
    values["orders"]=[{"client_order_id":"unrelated-customer-order-123"}]
    result=post.observe_broker_once()
    assert result["broker_orders_modified"]==0
    assert result["stop_completed"] is False


@pytest.mark.parametrize("bad",[
    {"id":"wrong-account-00000000"}, {}, [],
    {"id":None},
    {"id":"<unsafe>"}
])
def test_untrusted_broker_account_never_proves_stop(protected,bad):
    values,event,policy,calls,p=protected
    values["account"]=bad
    with pytest.raises(post.PostStopBrokerHold):
        post.observe_broker_once()


def test_open_order_pagination_fails_closed(protected):
    values,event,policy,calls,p=protected
    values["orders"]=[{"client_order_id":f"unrelated-{i}"} for i in range(500)]
    with pytest.raises(post.PostStopBrokerHold,match="truncated"):
        post.observe_broker_once()


def test_pinned_policy_mismatch_before_broker_credential_load(
        protected):
    values,event,policy,calls,p=protected
    policy["capital_ceiling_usd"]="100000.00"
    p.write_text(json.dumps(policy),encoding="utf-8")
    with pytest.raises(post.PostStopBrokerHold,match="policy changed"):
        post.observe_broker_once()
    assert not calls


def test_broker_transport_errors_are_redacted_and_fail_closed(
        protected,monkeypatch):
    values,event,policy,calls,p=protected
    def leak(*a,**k):
        raise RuntimeError("PRIVATE_ACCOUNT:1234 secret:example")
    monkeypatch.setattr(post.broker,"get_json",leak)
    with pytest.raises(post.PostStopBrokerHold,
                       match="GET-only broker read unavailable") as exc:
        post.observe_broker_once()
    assert "PRIVATE_ACCOUNT" not in str(exc.value)


def test_source_contract_never_claims_broker_issued_readonly_or_stop():
    code=Path(post.__file__).read_text(encoding="utf-8")
    for token in (
        "NO_BROKER_WRITE=True","NO_GITHUB_WRITE=True",
        "NO_GITHUB_TOKEN=True","NO_STOP_DISPATCH=True",
        "NO_SIGNER_KEY=True","NO_STOP_COMPLETION_CLAIM=True",
        "NO_TRADE_RELEASE=True",
        '"issuer_level_credential_is_readonly":False',
        '"signed_stop_completion_receipt":False',
        '"stop_completed":False',
        '"order_authorized":False',
    ):
        assert token in code
    assert 'method="POST"' not in code
    assert 'method="DELETE"' not in code
    assert "requests.post" not in code



def test_live_workflow_is_protected_and_broker_job_depends_on_exact_stop():
    path=Path(".github/workflows/fund100-stop-exact-run-event-getonly.yml")
    workflow=path.read_text(encoding="utf-8")
    assert "types: [completed]" in workflow
    assert "Fund-100 STOP TRADING (operator emergency)" in workflow
    assert "  protected-live-broker-poststop:" in workflow
    broker_job=workflow.split("  protected-live-broker-poststop:",1)[1].split(
        "  post-broker-main-stop-recheck:",1)[0]
    assert "needs: event-stop-observer" in broker_job
    assert "needs.event-stop-observer.result == 'success'" in broker_job
    assert "environment: fund100-live-broker" in broker_job
    assert "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}" in broker_job
    assert "ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}" in broker_job
    assert "FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}" in broker_job
    assert "FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE" in broker_job
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in broker_job
    assert "persist-credentials: false" in broker_job
    assert "GITHUB_TOKEN:" not in broker_job
    assert "actions: write" not in broker_job
    assert "python -B fund100_stop_event_protected_broker_getonly_v1_0.py" in broker_job
    assert "c3e82ebd7cd39d7c9d985b2aeb6c911513b01303" in broker_job
    assert "a8cf058595a960d67055a63e65f574530f7074c8" in broker_job
    assert "ff20cb4950243c64f4d34b68e6e3170ff6cc9421" in broker_job
    post=workflow.split("  post-broker-main-stop-recheck:",1)[1]
    assert "needs: [event-stop-observer, protected-live-broker-poststop]" in post
    assert "GITHUB_TOKEN: ${{ github.token }}" in post
    assert "ALPACA_LIVE_KEY:" not in post
    assert "environment: fund100-live-broker" not in post


def test_live_auditor_pins_only_this_broker_source_in_this_workflow():
    audit=Path("audit_fund100_live_boundary.py").read_text(encoding="utf-8")
    required=(
        '".github/workflows/fund100-stop-exact-run-event-getonly.yml",'
        '\n        "fund100_stop_event_protected_broker_getonly_v1_0.py",'
        '\n    ): "c3e82ebd7cd39d7c9d985b2aeb6c911513b01303",'
    )
    assert required in audit



def test_independent_static_auditor_approves_only_reviewed_exact_broker_job(
        monkeypatch):
    import audit_fund100_live_boundary as audit
    workflow=".github/workflows/fund100-stop-exact-run-event-getonly.yml"
    script="fund100_stop_event_protected_broker_getonly_v1_0.py"
    original=Path(workflow).read_text(encoding="utf-8")
    assert audit.approved_scoped_live_script(workflow,script,original)
    for bad in (
        original.replace("needs: event-stop-observer",
                         "needs: credentialless-static-tests"),
        original.replace("environment: fund100-live-broker",
                         "environment: public"),
        original.replace("needs.event-stop-observer.result == 'success'",
                         "needs.event-stop-observer.result == 'failure'"),
        original.replace("FUND100_LIVE_WRITE_MODE: DISABLED",
                         "FUND100_LIVE_WRITE_MODE: ENABLED"),
        original.replace("  protected-live-broker-poststop:",
                         "  protected-live-broker-poststop:\n    actions: write"),
    ):
        assert not audit.approved_scoped_live_script(workflow,script,bad)
    # Even if the workflow's source text remains unchanged, unreviewed
    # transport/policy drift must revoke live broker credential eligibility.
    monkeypatch.setattr(audit,"git_blob_digest",lambda path: "0"*40)
    assert not audit.approved_scoped_live_script(workflow,script,original)

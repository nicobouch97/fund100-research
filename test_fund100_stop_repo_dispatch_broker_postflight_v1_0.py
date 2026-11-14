"""Adversarial no-network two-GET STOP repository event protected broker tests."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import fund100_stop_repo_dispatch_broker_postflight_v1_0 as x

RUN_ID=43622999065


@pytest.fixture
def valid(monkeypatch):
    env={
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":x.REPO,
        "GITHUB_EVENT_NAME":"repository_dispatch",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_WORKFLOW_REF":x.WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_SHA":"a"*40,
        "GITHUB_EVENT_PATH":"/home/runner/work/_temp/_github_workflow/event.json",
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
        "FUND100_LIVE_WRITE_MODE":"DISABLED",
    }
    for k,v in env.items():
        monkeypatch.setenv(k,v)
    for k in (
        "GITHUB_TOKEN","GH_TOKEN","FUND100_GH_STOP_DISPATCH_TOKEN",
        "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_ALPACA_READONLY_OAUTH_BEARER",
    ):
        monkeypatch.delenv(k,raising=False)
    event={
        "action":x.EVENT_TYPE,
        "repository":{"full_name":x.REPO},
        "client_payload":{"original_stop_run_id":str(RUN_ID)},
    }
    original_open=open
    def open_event(path,*a,**kw):
        if str(path).endswith("/event.json"):
            return io.BytesIO(json.dumps(event).encode())
        return original_open(path,*a,**kw)
    monkeypatch.setattr("builtins.open",open_event)
    calls=[]
    monkeypatch.setattr(x.core,"_pinned_policy",lambda:calls.append("policy"))
    monkeypatch.setattr(
        x.core.broker,"require_readonly_arm",lambda:calls.append("arm"))
    monkeypatch.setattr(
        x.core.broker,"load_credentials",lambda:("OFFLINE_KEY","OFFLINE_SECRET"))
    def get_json(*,path,key,secret,params=None):
        assert (key,secret)==("OFFLINE_KEY","OFFLINE_SECRET")
        calls.append((path,params))
        if path=="/v2/account" and params is None:
            return {"id":"synthetic-account-private-1234"}
        if path=="/v2/orders" and params=={"status":"open","limit":500}:
            return []
        raise AssertionError("Unknown broker GET")
    monkeypatch.setattr(x.core.broker,"get_json",get_json)
    monkeypatch.setattr(x.core,"_read_no_open_targets",
                        lambda *,account,orders:calls.append("check"))
    return event,calls


def test_two_exact_broker_get_only_and_no_stop_claim(valid):
    event,calls=valid
    got=x.observe_once()
    assert got["original_stop_run_id"]==RUN_ID
    assert got["broker_get_count"]==2
    assert got["issuer_level_credentials_are_readonly"] is False
    assert got["broker_orders_mutated"] is False
    assert got["broker_fills_verified"] is False
    assert got["signed_stop_receipt"] is False
    assert got["stop_completed"] is False
    assert got["order_authorized"] is False
    assert calls==[
        "policy","arm",("/v2/account",None),
        ("/v2/orders",{"status":"open","limit":500}),"check",
    ]


@pytest.mark.parametrize("key,bad",[
    ("GITHUB_ACTIONS","false"),("GITHUB_REPOSITORY","another/repo"),
    ("GITHUB_EVENT_NAME","workflow_dispatch"),
    ("GITHUB_REF","refs/heads/feature"),
    ("GITHUB_WORKFLOW_REF","wrong"),("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_SHA","bad"),("FUND100_RISK_LEVEL","MEDIUM"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
    ("FUND100_ENABLE_LIVE_READONLY","NO"),
    ("FUND100_LIVE_WRITE_MODE","ENABLED"),
])
def test_invalid_source_or_risk_fails_before_broker_get(valid,monkeypatch,key,bad):
    event,calls=valid
    monkeypatch.setenv(key,bad)
    with pytest.raises(x.BrokerPostflightHold,match="scope"):
        x.observe_once()
    assert calls==[]


@pytest.mark.parametrize("secret",[
    "GITHUB_TOKEN","GH_TOKEN","FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
    "FUND100_ALPACA_READONLY_OAUTH_BEARER",
])
def test_broker_keys_cannot_share_job_with_github_or_signer(valid,monkeypatch,secret):
    event,calls=valid
    monkeypatch.setenv(secret,"ILLEGAL_COLOCATION")
    with pytest.raises(x.BrokerPostflightHold,match="scope"):
        x.observe_once()
    assert calls==[]


@pytest.mark.parametrize("event",[
    {},
    {"action":"not-STOP","repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":str(RUN_ID)}},
    {"action":x.EVENT_TYPE,"repository":{"full_name":"other/repo"},
     "client_payload":{"original_stop_run_id":str(RUN_ID)}},
    {"action":x.EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":"0"}},
    {"action":x.EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":True}},
    {"action":x.EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":{"original_stop_run_id":str(RUN_ID),"rearm":True}},
    {"action":x.EVENT_TYPE,"repository":{"full_name":x.REPO},
     "client_payload":None},
])
def test_spoofed_event_never_reads_broker(valid,monkeypatch,event):
    original,calls=valid
    original.clear()
    original.update(event)
    with pytest.raises(x.BrokerPostflightHold):
        x.observe_once()
    assert calls==[]


def test_network_transport_error_is_redacted(valid,monkeypatch):
    event,calls=valid
    def fail(*,path,key,secret,params=None):
        raise RuntimeError("REAL_ACCOUNT_NUMBER_PRIVATE SECRET_TOKEN")
    monkeypatch.setattr(x.core.broker,"get_json",fail)
    with pytest.raises(x.BrokerPostflightHold,
                       match="not independently verified") as exc:
        x.observe_once()
    assert "REAL_ACCOUNT_NUMBER" not in str(exc.value)


def test_truncated_or_fund100_order_checked_by_existing_pinned_policy(
        valid,monkeypatch):
    event,calls=valid
    def reject(*,account,orders):
        raise x.core.PostStopBrokerHold("Potential outstanding Fund-100 broker order")
    monkeypatch.setattr(x.core,"_read_no_open_targets",reject)
    with pytest.raises(x.BrokerPostflightHold):
        x.observe_once()


def test_aged_get_snapshot_rejected(valid,monkeypatch):
    tick=iter([0.0,46.0])
    monkeypatch.setattr(x.time,"monotonic",lambda:next(tick))
    with pytest.raises(x.BrokerPostflightHold):
        x.observe_once()


def test_workflow_separates_github_observer_and_protected_broker():
    workflow=Path(".github/workflows/fund100-stop-explicit-original-getonly.yml").read_text()
    assert "  repository_dispatch:" in workflow
    assert "  protected-repo-stop-broker-postflight:" in workflow
    observer=workflow.split("  explicit-main-stop-only:",1)[1].split(
        "  offline-explicit-proof-tests:",1)[0]
    broker=workflow.split("  protected-repo-stop-broker-postflight:",1)[1]
    assert "ALPACA_LIVE_KEY:" not in observer
    assert "environment: fund100-live-broker" not in observer
    assert "GITHUB_TOKEN: ${{ github.token }}" in observer
    assert "needs: explicit-main-stop-only" in broker
    assert "needs.explicit-main-stop-only.result == 'success'" in broker
    assert "github.event_name == 'repository_dispatch'" in broker
    assert "environment: fund100-live-broker" in broker
    assert "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}" in broker
    assert "ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}" in broker
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in broker
    assert "GITHUB_TOKEN:" not in broker
    assert "actions: write" not in broker
    assert "persist-credentials: false" in broker
    assert "python -B fund100_stop_repo_dispatch_broker_postflight_v1_0.py" in broker
    for sha in (
        "a9f66d22948dc7c38a5e8657f19fef41a942e4df",
        "c3e82ebd7cd39d7c9d985b2aeb6c911513b01303",
        "a8cf058595a960d67055a63e65f574530f7074c8",
        "ff20cb4950243c64f4d34b68e6e3170ff6cc9421",
    ):
        assert sha in broker


def test_source_denies_mutation_and_completion():
    source=Path(x.__file__).read_text(encoding="utf-8")
    assert "NO_BROKER_MUTATION=True" in source
    assert "NO_GITHUB_WRITE=True" in source
    assert "NO_ORDER_RELEASE=True" in source
    assert "NO_COMPLETION_CLAIM=True" in source
    assert "NO_FILL_CLAIM=True" in source
    assert '"issuer_level_credentials_are_readonly":False' in source
    assert '"broker_fills_verified":False' in source
    assert '"signed_stop_receipt":False' in source
    assert '"stop_completed":False' in source
    assert '"order_authorized":False' in source
    assert 'method="POST"' not in source
    assert 'method="DELETE"' not in source
    assert "requests.post" not in source
    assert "requests.delete" not in source


def test_auditor_approves_only_pinned_original_verifier_and_broker_get(monkeypatch):
    import audit_fund100_live_boundary as audit
    workflow=".github/workflows/fund100-stop-explicit-original-getonly.yml"
    witness="fund100_stop_explicit_original_getonly_v1_0.py"
    broker="fund100_stop_repo_dispatch_broker_postflight_v1_0.py"
    source=Path(workflow).read_text(encoding="utf-8")
    assert audit.approved_scoped_live_script(workflow,witness,source)
    assert audit.approved_scoped_live_script(workflow,broker,source)
    assert not audit.approved_scoped_live_script(
        ".github/workflows/fund100-live-emergency-stop.yml",broker,source)
    cases=[
        source.replace("needs: explicit-main-stop-only",
                       "needs: offline-explicit-proof-tests"),
        source.replace("needs.explicit-main-stop-only.result == 'success'",
                       "needs.explicit-main-stop-only.result == 'failure'"),
        source.replace(
            "  explicit-main-stop-only:",
            "  explicit-main-stop-only:\n    environment: fund100-live-broker"),
        source.replace(
            "  explicit-main-stop-only:",
            "  explicit-main-stop-only:\n    ALPACA_LIVE_KEY: SECRET"),
        source.replace(
            "  protected-repo-stop-broker-postflight:",
            "  protected-repo-stop-broker-postflight:\n    actions: write"),
        source.replace(
            "  protected-repo-stop-broker-postflight:",
            "  protected-repo-stop-broker-postflight:\n    GITHUB_TOKEN: MALICIOUS"),
        source.replace(
            "FUND100_LIVE_WRITE_MODE: DISABLED",
            "FUND100_LIVE_WRITE_MODE: ENABLED"),
        source.replace(
            "environment: fund100-live-broker",
            "environment: public"),
        source.replace(
            "python -B fund100_stop_repo_dispatch_broker_postflight_v1_0.py",
            "python -B unreviewed_live_writer.py"),
        source.replace("a9f66d22948dc7c38a5e8657f19fef41a942e4df","0"*40),
        source.replace("c3e82ebd7cd39d7c9d985b2aeb6c911513b01303","0"*40),
        source.replace("  repository_dispatch:",
                       "  unreleased_dispatch:"),
    ]
    for index,bad in enumerate(cases):
        assert bad!=source,index
        assert not audit.approved_scoped_live_script(workflow,broker,bad),index
    monkeypatch.setattr(audit,"git_blob_digest",lambda path:"0"*40)
    assert not audit.approved_scoped_live_script(workflow,broker,source)
    assert not audit.approved_scoped_live_script(workflow,witness,source)


def test_auditor_sources_have_exact_sha_and_pinned_dependencies():
    import audit_fund100_live_boundary as audit
    workflow=".github/workflows/fund100-stop-explicit-original-getonly.yml"
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[
        (workflow,"fund100_stop_repo_dispatch_broker_postflight_v1_0.py")
    ]=="a9f66d22948dc7c38a5e8657f19fef41a942e4df"
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[
        (workflow,"fund100_stop_explicit_original_getonly_v1_0.py")
    ]=="6267be4304157d521bb9a49040fa527642ca54c1"

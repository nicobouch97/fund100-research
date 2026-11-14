"""Adversarial offline tests for original STOP -> read-only GitHub event."""
from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest
import fund100_stop_repo_dispatch_bridge_v1_0 as bridge

RUN_ID=43617230118


@pytest.fixture
def valid(monkeypatch):
    for k,v in {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":bridge.REPO,
        "GITHUB_EVENT_NAME":"workflow_dispatch",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_WORKFLOW_REF":bridge.EXPECTED_WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_SHA":"a"*40,
        "GITHUB_RUN_ID":str(RUN_ID),
        "GITHUB_TOKEN":"OFFLINE_GITHUB_TOKEN_123456789012345678",
    }.items():
        monkeypatch.setenv(k,v)
    for k in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY","ALPACA_PAPER_SECRET",
        "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
    ):
        monkeypatch.delenv(k,raising=False)


def test_only_fixed_event_and_exact_original_id(valid,monkeypatch):
    reqs=[]
    class R:
        status=204
        def __init__(self,url): self.url=url
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def geturl(self): return self.url
        def read(self,n): return b""
    class Open:
        def open(self,req,timeout):
            assert timeout==8
            assert req.get_method()=="POST"
            assert req.full_url==bridge.ENDPOINT
            assert req.get_header("X-github-api-version")=="2026-03-10"
            reqs.append(req)
            return R(req.full_url)
    monkeypatch.setattr(bridge,"build_opener",lambda *args:Open())
    bridge.main()
    assert len(reqs)==1
    assert json.loads(reqs[0].data)=={
        "event_type":bridge.EVENT_TYPE,
        "client_payload":{"original_stop_run_id":str(RUN_ID)},
    }


@pytest.mark.parametrize("k,v",[
    ("GITHUB_ACTIONS","false"),
    ("GITHUB_REPOSITORY","other/repo"),
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_REF","refs/heads/unreviewed"),
    ("GITHUB_WORKFLOW_REF","different/workflow@refs/heads/main"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_SHA","BAD"),
    ("GITHUB_RUN_ID","0"),
    ("GITHUB_RUN_ID","1x"),
])
def test_wrong_scope_or_source_never_sends(valid,monkeypatch,k,v):
    monkeypatch.setenv(k,v)
    monkeypatch.setattr(bridge,"build_opener",
                        lambda *args:pytest.fail("Network attempted"))
    with pytest.raises(bridge.BridgeHold):
        bridge._scope()


@pytest.mark.parametrize("k",[
    "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
    "ALPACA_PAPER_KEY","ALPACA_PAPER_SECRET",
    "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
])
def test_no_broker_or_signer_credential_colocation(valid,monkeypatch,k):
    monkeypatch.setenv(k,"WRONG_SCOPE")
    with pytest.raises(bridge.BridgeHold):
        bridge._scope()


@pytest.mark.parametrize("bad",[
    0,-1,True,"123",10**19,
])
def test_noncanonical_original_id_rejected_before_network(valid,monkeypatch,bad):
    monkeypatch.setattr(bridge,"build_opener",
                        lambda *args:pytest.fail("Network attempted"))
    with pytest.raises(bridge.BridgeHold):
        bridge._send_once(run_id=bad,token=bridge._token())


def test_denied_or_ambiguous_send_is_never_a_completion(valid,monkeypatch):
    class Denied:
        def open(self,req,timeout):
            raise HTTPError(req.full_url,403,"denied",{},None)
    monkeypatch.setattr(bridge,"build_opener",lambda *args:Denied())
    with pytest.raises(bridge.BridgeHold,match="NO RETRY"):
        bridge._send_once(run_id=RUN_ID,token=bridge._token())


@pytest.mark.parametrize("status,data",[(200,b"{}"),(201,b""),(204,b"unexpected")])
def test_wrong_status_or_content_rejected(valid,monkeypatch,status,data):
    class R:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def geturl(self): return bridge.ENDPOINT
        def read(self,n): return data[:n]
    class Open:
        def open(self,req,timeout):
            v=R()
            v.status=status
            return v
    monkeypatch.setattr(bridge,"build_opener",lambda *args:Open())
    with pytest.raises(bridge.BridgeHold):
        bridge._send_once(run_id=RUN_ID,token=bridge._token())


def test_repo_dispatch_is_sole_mutating_endpoint():
    source=open(bridge.__file__,encoding="utf-8").read()
    assert 'ENDPOINT = API + "/dispatches"' in source
    assert '"event_type":EVENT_TYPE' in source
    assert '"client_payload":{"original_stop_run_id":str(run_id)}' in source
    assert 'NO_ORDER = True' in source
    assert 'NO_GITHUB_CONTENTS_MUTATION = True' in source
    assert 'NO_STOP_DISPATCH = True' in source
    assert 'NO_SUCCESS_CLAIM = True' in source
    assert 'NO_RETRY = True' in source
    assert "api.alpaca.markets" not in source


def test_static_auditor_only_accepts_pinned_credentialless_stop_notification(
        monkeypatch):
    """The broker-key job's presence is not proof this STOP job has keys."""
    from pathlib import Path
    import audit_fund100_live_boundary as audit

    workflow=".github/workflows/fund100-live-emergency-stop.yml"
    script="fund100_stop_repo_dispatch_bridge_v1_0.py"
    source=Path(workflow).read_text(encoding="utf-8")
    assert audit.approved_scoped_live_script(workflow,script,source)
    assert not audit.approved_scoped_live_script(
        ".github/workflows/fund100-live-risk-watch.yml",script,source)

    tampered=[
        source.replace(
            "  stop-signal:\n",
            "  stop-signal:\n    environment: fund100-live-broker\n"),
        source.replace(
            "  stop-signal:\n",
            "  stop-signal:\n    ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}\n"),
        source.replace(
            "  stop-signal:\n",
            "  stop-signal:\n    FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX: SENSITIVE\n"),
        source.replace(
            "  stop-signal:\n",
            "  stop-signal:\n    actions: write\n"),
        source.replace(
            "      - name: Notify independent GitHub STOP observer via fixed repository event",
            "      - name: Arbitrary command"),
        source.replace(
            "8d46cbe1b2230dc13eccf50c395b877869702673",
            "0"*40),
        source.replace(
            "          python -B fund100_stop_repo_dispatch_bridge_v1_0.py",
            "          python -B fund100_new_unreviewed_broker_writer.py"),
        source.replace(
            "      - name: Notify independent GitHub STOP observer via fixed repository event",
            "      - name: Notify independent GitHub STOP observer via fixed repository event\n"
            "        env:\n          ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}"),
        source.replace(
            "        if: always()\n        env:\n          GITHUB_TOKEN:",
            "        if: success()\n        env:\n          GITHUB_TOKEN:"),
    ]
    for i,bad in enumerate(tampered):
        assert bad != source, i
        assert not audit.approved_scoped_live_script(workflow,script,bad),i
    monkeypatch.setattr(audit,"git_blob_digest",lambda p:"0"*40)
    assert not audit.approved_scoped_live_script(workflow,script,source)


def test_auditor_includes_exact_new_source_pin():
    import audit_fund100_live_boundary as audit
    workflow=".github/workflows/fund100-live-emergency-stop.yml"
    script="fund100_stop_repo_dispatch_bridge_v1_0.py"
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(workflow,script)] == (
        "8d46cbe1b2230dc13eccf50c395b877869702673")

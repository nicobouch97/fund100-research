"""Synthetic permissions/readback tests: no real GitHub PUT or Alpaca request."""
from base64 import b64encode
from copy import deepcopy
from hashlib import sha1
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError
import pytest
import fund100_v6_s1_private_write_permission_probe_once_v1_0 as p

RUN="40720000000"
SHA="c"*40

def env():
    return {
      "GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":"nicobouch97/fund100-research",
      "GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_dispatch",
      "GITHUB_ACTOR":"nicobouch97",
      "FUND100_PRIVATE_WRITE_PROBE_CONFIRM":p.CONFIRMATION,
      "GITHUB_RUN_ATTEMPT":"1","GITHUB_RUN_ID":RUN,"GITHUB_SHA":SHA,
      "FUND100_BROKER_KILL_SWITCH":"ENGAGED","FUND100_RISK_LEVEL":"HIGH",
      "FUND100_PRIVATE_STATE_READ_TOKEN":"dummy-read-private-principal",
      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":"dummy-write-private-principal",
    }

def proof():
    return {
       "status":"FIVE_DISTINCT_GITHUB_PRINCIPALS_AUTHENTICATED_READ_ONLY_NO_WRITE_PROOF",
       "original_private_signed_seq1_and_owner_seq0_verified":True,
       "private_candidate_repository_push_metadata":"PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF",
       "signed_state_mutations":0,
       "public_release_mutations":0,"public_issue_mutations":0,
       "broker_orders":0,"funded_order_authorized":False,
    }

def sha(raw):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

class FakeGithub:
    def __init__(self):
        self.calls=[]
        self.created=None
        self.preexisting=False
        self.put_fail=False
        self.ack_mismatch=False
        self.read_fail=False
    def request(self,*,method,run_id,token,raw=None,transport=None,allow_absent=False):
        self.calls.append(method)
        assert run_id==RUN
        assert transport is None
        assert token==("dummy-read-private-principal" if method=="GET"
            else "dummy-write-private-principal")
        if method=="GET" and self.created is None:
            assert allow_absent
            return {"sha":"existing"} if self.preexisting else None
        if method=="GET" and self.created is not None and allow_absent:
            return {"type":"file","path":p.PATH,"sha":sha(self.created)}
        if method=="PUT":
            assert self.created is None
            assert not allow_absent and type(raw) is bytes
            data=json.loads(raw)
            assert data["branch"]=="main"
            assert "sha" not in data
            assert p.PATH.startswith("audit/")
            self.created=__import__("base64").b64decode(data["content"])
            assert json.loads(self.created)["signed_order_ledger_modified"] is False
            assert json.loads(self.created)["original_owner_claim_modified"] is False
            if self.put_fail:raise p.ProbeStop("lost acknowledgement; no retry")
            return {
                "content":{"path":p.PATH,
                           "sha":"0"*40 if self.ack_mismatch else sha(self.created)},
                "commit":{"sha":"e"*40},
            }
        assert method=="GET" and not allow_absent
        return {
            "type":"file","path":p.PATH,
            "sha":sha(self.created),"encoding":"base64",
            "content":b64encode(b"CORRUPT" if self.read_fail else self.created).decode(),
        }

@pytest.fixture
def ctx(monkeypatch):
    e=env()
    fake=FakeGithub()
    monkeypatch.setattr(p.os,"environ",e)
    monkeypatch.setattr(p.original,"inspect",lambda **kw:proof())
    monkeypatch.setattr(p,"_request",fake.request)
    return e,fake

def test_exactly_one_nontrading_audit_put_with_independent_readback(ctx):
    _,f=ctx
    result=p.run_once()
    assert f.calls==["GET","PUT","GET"]
    assert result["status"]=="PRIVATE_MAIN_CONTENTS_WRITE_ONCE_AND_INDEPENDENT_READBACK_VERIFIED"
    assert result["private_audit_file_created"] is True
    assert result["signed_private_ledger_unchanged_by_this_probe"] is True
    assert result["original_owner_fence_unchanged_by_this_probe"] is True
    assert result["public_issue_or_release_writes"]==0
    assert result["broker_orders"]==result["broker_requests"]==0
    assert result["actual_release_write_permission_proven"] is False
    assert result["signed_ledger_CAS_write_permission_proven"] is False
    assert result["one_time_funded_launch_authorized"] is False
    assert json.loads(f.created)["public_source_sha"]==SHA
    assert result["private_token"] is None

@pytest.mark.parametrize("key,bad",[
    ("GITHUB_ACTIONS","false"),("GITHUB_REPOSITORY","attacker/repo"),
    ("GITHUB_REF","refs/heads/feature"),("GITHUB_EVENT_NAME","push"),
    ("GITHUB_ACTOR","attacker"),
    ("FUND100_PRIVATE_WRITE_PROBE_CONFIRM","UNAUTHORISED"),
    ("GITHUB_RUN_ATTEMPT","2"),("GITHUB_RUN_ID","../../state"),
    ("GITHUB_RUN_ID","0"),("GITHUB_SHA","unreviewed"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),("FUND100_RISK_LEVEL","LOW"),
    ("FUND100_PRIVATE_STATE_READ_TOKEN","dummy-write-private-principal"),
])
def test_no_private_io_when_protected_main_scope_changed(ctx,key,bad):
    e,f=ctx
    e[key]=bad
    with pytest.raises(p.ProbeStop):
        p.run_once()
    assert f.calls==[]

def test_missing_original_signed_fence_source_blocks_before_put(ctx,monkeypatch):
    _,f=ctx
    wrong=proof(); wrong["original_private_signed_seq1_and_owner_seq0_verified"]=False
    monkeypatch.setattr(p.original,"inspect",lambda **kw:wrong)
    with pytest.raises(p.ProbeStop):
        p.run_once()
    assert f.calls==[]

@pytest.mark.parametrize("change",[
    {"private_candidate_repository_push_metadata":"UNDETERMINED"},
    {"signed_state_mutations":1},{"broker_orders":1},
    {"funded_order_authorized":True},
])
def test_no_put_without_real_original_signed_source_and_stopped_readiness(ctx,monkeypatch,change):
    _,f=ctx
    d=proof();d.update(change)
    monkeypatch.setattr(p.original,"inspect",lambda **kw:d)
    with pytest.raises(p.ProbeStop):
        p.run_once()
    assert f.calls==[]

def test_existing_probe_is_never_overwritten(ctx):
    _,f=ctx;f.preexisting=True
    with pytest.raises(p.ProbeStop,match="already exists"):
        p.run_once()
    assert f.calls==["GET"]

@pytest.mark.parametrize("fault",["put_fail","ack_mismatch","read_fail"])
def test_ambiguous_write_or_readback_holds_permanently_without_retry(ctx,fault):
    _,f=ctx
    setattr(f,fault,True)
    with pytest.raises(p.ProbeStop):
        p.run_once()
    assert f.calls in (["GET","PUT"],["GET","PUT","GET"])
    assert f.calls.count("PUT")==1

def test_separate_confirmed_dispatch_cannot_create_second_private_audit_file(ctx):
    _,f=ctx
    first=p.run_once()
    assert first["private_audit_file_created"] is True
    with pytest.raises(p.ProbeStop,match="already exists"):
        p.run_once()
    assert f.calls==["GET","PUT","GET","GET"]
    assert f.calls.count("PUT")==1


def test_no_merge_on_main_automatic_private_write_possible():
    workflow=Path(".github/workflows/fund100-v6-s1-first-private-write-scope-once.yml").read_text()
    assert "  push:" not in workflow and "  schedule:" not in workflow
    assert "  workflow_run:" not in workflow
    assert "  workflow_dispatch:" in workflow
    assert "  pull_request:" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "github.actor == 'nicobouch97'" in workflow
    assert "inputs.confirmation == 'AUTHORIZE_ONE_NONTRADING_PRIVATE_AUDIT_WRITE'" in workflow
    assert "FUND100_PRIVATE_WRITE_PROBE_CONFIRM: ${{ inputs.confirmation }}" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "ALPACA_LIVE_KEY" not in workflow and "ALPACA_LIVE_SECRET" not in workflow
    assert "contents: write" not in workflow
    assert workflow.count("environment: fund100-live-broker")==1


def test_helper_uses_fixed_private_audit_get_put_and_bounded_response():
    class Response:
        status=200
        def __init__(self,doc):self.buf=BytesIO(json.dumps(doc).encode())
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return self.buf.read(n)
    def sender(req,timeout):
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url==p.API+p.PATH+"?ref=main"
        assert req.get_header("Authorization")=="Bearer dummy-read-private-principal"
        return Response({"type":"file","path":p.PATH})
    result=p._request(method="GET",run_id=RUN,
        token="dummy-read-private-principal",transport=sender)
    assert result["type"]=="file"
    assert result["path"]==p.PATH
    with pytest.raises(p.ProbeStop):
        p._request(method="PUT",run_id="../../state",
            token="dummy-write-private-principal",raw=b"{}",transport=sender)
    with pytest.raises(p.ProbeStop):
        p._request(method="PUT",run_id=RUN,
            token="dummy-write-private-principal",raw=b"{}",transport=sender,
            allow_absent=True)
    with pytest.raises(p.ProbeStop):
        p._request(method="GET",run_id=RUN,
            token="dummy-read-private-principal",raw=b"{}",transport=sender)

def test_only_404_before_first_put_is_tolerated():
    def missing(req,timeout):
        raise HTTPError(req.full_url,404,"Not found",{},None)
    assert p._request(method="GET",run_id=RUN,
        token="dummy-read-private-principal",allow_absent=True,
        transport=missing) is None
    with pytest.raises(p.ProbeStop):
        p._request(method="GET",run_id=RUN,
            token="dummy-read-private-principal",transport=missing)
    with pytest.raises(p.ProbeStop):
        p._request(method="PUT",run_id=RUN,
            token="dummy-write-private-principal",raw=b"{}",
            transport=missing)

def test_private_contract_no_broker_or_signed_ledger_access():
    source=Path(p.__file__).read_text()
    assert p.LIVE_BROKER_CALLS_PERMITTED is False
    assert p.SIGNATURE_LEDGER_WRITES_PERMITTED is False
    assert p.PUBLIC_ISSUE_OR_RELEASE_WRITES_PERMITTED is False
    assert p.LIVE_TRADING_AUTHORIZED is False
    assert p.MAX_ONE_REAL_PUT==1
    assert "fund100-state-private/contents/" in source or "PRIVATE_REPO+" in source
    assert "state/v6_s1_original_legacy_sales.json" not in source
    assert "state/v6_s1_first_acwi_execution_owner_fence.json" not in source
    assert "api.alpaca.markets" not in source
    assert "ALPACA_LIVE_KEY" not in source and "ALPACA_LIVE_SECRET" not in source
    assert "method=\"POST\"" not in source
    assert "method=\"PATCH\"" not in source

"""Same-run signed owner -> first ACWI seq2 -> public head: mock HTTP only."""
from base64 import b64decode
from copy import deepcopy
from io import BytesIO
import json

import pytest
from urllib.error import HTTPError,URLError
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as x
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fx
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as initial
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

READ="private-dummy-read-principal-original"
WRITE="different-private-dummy-write-original"
PUBLIC="independent-public-github-issue-token"

class Reply:
    def __init__(self,status,obj):
        self.status=status
        self.raw=BytesIO(json.dumps(obj).encode("utf-8"))
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.raw.read(n)

def config():
    a=fx.setup()
    plan=fence.plan_unique_owner(**a)
    signed=fx.as_fence(b64decode(plan["fake_only_commit"]["content_base64"]))
    params={k:v for k,v in a.items() if k!="fence_source"}
    params["current_fence_source"]=signed
    return params

class GitScenario:
    def __init__(self,mode="ok"):
        self.owner=config()["current_fence_source"]
        self.ledger=deepcopy(config()["reserved_source"])
        self.mode=mode
        self.owner_gets=0
        self.ledger_gets=0
        self.private_puts=0
        self.public_posts=0
        self.public_gets=0
        self.comment=None
    def read(self,req,timeout):
        assert timeout==12 and req.get_method()=="GET"
        auth=req.get_header("Authorization")
        if req.full_url==x.PRIVATE_CONTENTS_URL+"?ref=main":
            assert auth in ("Bearer "+READ,"Bearer "+WRITE)
            self.owner_gets+=1
            ret=deepcopy(self.owner)
            if self.mode=="different_owner" and self.owner_gets==2:
                ret["sha"]="0"*40
            if self.mode=="changed_owner" and self.owner_gets==1:
                ret["content"]="broken"
            return Reply(200,ret)
        if req.full_url==x.ORIGINAL_ORDER_LEDGER_URL+"?ref=main":
            assert auth in ("Bearer "+READ,"Bearer "+WRITE)
            self.ledger_gets+=1
            if self.mode=="ledger_read_denied" and self.ledger_gets==1:
                raise HTTPError(req.full_url,403,"denied",None,None)
            ret=deepcopy(self.ledger)
            if self.mode=="ledger_conflicting_read" and self.ledger_gets==2:
                ret["sha"]="0"*40
            if self.mode=="ledger_readback_missing" and self.ledger_gets==3:
                ret["sha"]="0"*40
            if self.mode=="ledger_readback_timeout" and self.ledger_gets==3:
                raise TimeoutError("uncertain")
            return Reply(200,ret)
        if req.full_url==x.PUBLIC_COMMENT_COLLECTION+"/7891234567":
            assert auth=="Bearer "+PUBLIC
            self.public_gets+=1
            if self.mode=="public_get_forged":
                d=deepcopy(self.comment)
                d["body"]="tampered"
                return Reply(200,d)
            if self.mode=="public_get_denied":
                raise HTTPError(req.full_url,403,"denied",None,None)
            return Reply(200,self.comment)
        raise AssertionError("Unexpected outbound network GET "+req.full_url)
    def write(self,req,timeout):
        assert timeout==12
        assert req.full_url==x.ORIGINAL_ORDER_LEDGER_URL
        assert req.get_method()=="PUT"
        assert req.get_header("Authorization")=="Bearer "+WRITE
        self.private_puts+=1
        assert self.private_puts==1
        payload=json.loads(req.data.decode("ascii"))
        assert set(payload)=={"sha","content","message","branch"}
        assert payload["branch"]=="main"
        assert payload["sha"]==self.ledger["sha"]
        if self.mode=="private_409":
            raise HTTPError(req.full_url,409,"stale",None,None)
        raw=b64decode(payload["content"],validate=True)
        self.ledger=initial.as_source(raw)
        if self.mode=="private_lost_ack":
            raise URLError("response lost after Git accepted signed update")
        if self.mode=="private_bad_reply":
            return Reply(200,{"content":{"path":cas.STATE_PATH,"sha":"0"*40},
                              "commit":{"sha":"c"*40}})
        return Reply(200,{"content":{"path":cas.STATE_PATH,"sha":self.ledger["sha"]},
                          "commit":{"sha":"c"*40}})
    def public(self,req,timeout):
        if req.get_method()=="GET":
            return self.read(req,timeout)
        assert timeout==12
        assert req.full_url==x.PUBLIC_COMMENT_COLLECTION
        assert req.get_method()=="POST"
        assert req.get_header("Authorization")=="Bearer "+PUBLIC
        self.public_posts+=1
        assert self.public_posts==1
        if self.mode=="public_403":
            raise HTTPError(req.full_url,403,"denied",None,None)
        obj=json.loads(req.data.decode("utf-8"))
        assert set(obj)=={"body"}
        self.comment={
            "id":7891234567,"body":obj["body"],
            "issue_url":"https://api.github.com/repos/nicobouch97/fund100-research/issues/8",
            "user":{"login":"github-actions[bot]"},
        }
        if self.mode=="public_lost_ack":
            raise URLError("response lost after public witness created")
        if self.mode=="public_fake_actor":
            self.comment["user"]["login"]="attacker"
        return Reply(201,self.comment)

def args(scenario,owner=None):
    return {
        "owner_sources":config() if owner is None else owner,
        "private_read_token":READ,"private_write_token":WRITE,
        "public_issue_write_token":PUBLIC,
        "read_transport":scenario.read,
        "write_transport":scenario.write,
        "public_transport":scenario.public,
    }

@pytest.fixture(autouse=True)
def actions_context(monkeypatch):
    p=config()
    for name,val in (
        ("GITHUB_REPOSITORY","nicobouch97/fund100-research"),
        ("GITHUB_REF","refs/heads/main"),
        ("GITHUB_EVENT_NAME","workflow_dispatch"),
        ("GITHUB_RUN_ATTEMPT","1"),
        ("GITHUB_RUN_ID",p["owner_run_id"]),
        ("GITHUB_SHA",p["current_main_sha"]),
    ):monkeypatch.setenv(name,val)

def unlocked(monkeypatch):
    monkeypatch.setattr(x,"PREPOST_PRIVATE_CAS_RELEASED",True)
    monkeypatch.setattr(x,"PREPOST_PUBLIC_WITNESS_RELEASED",True)

def test_production_cannot_even_read_private_credentials():
    s=GitScenario()
    with pytest.raises(x.OwnerClaimStop,match="HARD LOCKED"):
        x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    assert s.owner_gets==s.ledger_gets==s.private_puts==s.public_posts==0
    assert x.PREPOST_PRIVATE_CAS_RELEASED is False
    assert x.PREPOST_PUBLIC_WITNESS_RELEASED is False
    assert x.LIVE_BROKER_ORDER_RELEASED is False

def test_signed_owner_then_real_format_prepost_once_and_independent_public_witness(monkeypatch):
    unlocked(monkeypatch)
    s=GitScenario()
    result=x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    assert result["status"]=="SIGNED_ACWI_SEQ2_AND_PUBLIC_HEAD_WITNESSED_BROKER_STILL_BLOCKED"
    assert result["signed_acwi_prepost_private_sequence"]==2
    assert not result["live_broker_order_authorized"]
    assert not result["external_immutable_anti_rollback_anchor_proven"]
    assert result["real_private_git_put_attempts"]==result["real_public_issue_post_attempts"]==1
    assert result["real_broker_post_attempts"]==0
    assert s.owner_gets==2 and s.ledger_gets==3
    assert s.private_puts==1 and s.public_posts==1 and s.public_gets==1
    assert config()["original_qty"] not in str(result)
    assert READ not in str(result) and WRITE not in str(result)
    assert PUBLIC not in str(result)

@pytest.mark.parametrize("failure,private_puts,public_posts",[
    ("different_owner",0,0),("changed_owner",0,0),
    ("ledger_read_denied",0,0),("ledger_conflicting_read",0,0),
    ("private_409",1,0),("private_lost_ack",1,0),
    ("private_bad_reply",1,0),("ledger_readback_missing",1,0),
    ("ledger_readback_timeout",1,0),("public_403",1,1),
    ("public_lost_ack",1,1),("public_get_forged",1,1),
    ("public_get_denied",1,1),("public_fake_actor",1,1),
])
def test_remote_ambiguity_is_terminal_hold_no_retry_and_no_broker(
    failure,private_puts,public_posts,monkeypatch,
):
    unlocked(monkeypatch)
    s=GitScenario(mode=failure)
    with pytest.raises(x.OwnerClaimStop):
        x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    assert s.private_puts==private_puts
    assert s.public_posts==public_posts
    assert s.public_gets<=1

def test_once_seq2_exists_no_second_private_update(monkeypatch):
    unlocked(monkeypatch)
    s=GitScenario()
    x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    with pytest.raises(x.OwnerClaimStop,match="no longer current"):
        x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    assert s.private_puts==1 and s.public_posts==1

@pytest.mark.parametrize("field",[
    "owner_run_id","owner_attempt","owner_nonce","original_qty",
    "reserved_source","current_fence_source",
])
def test_mismatched_owner_is_rejected_before_mutation(field,monkeypatch):
    unlocked(monkeypatch)
    s=GitScenario()
    p=config()
    if field=="owner_run_id":p[field]="39812340002"
    elif field=="owner_attempt":p[field]=2
    elif field=="owner_nonce":p[field]="2"*64
    elif field=="original_qty":p[field]="0.123456788"
    elif field=="reserved_source":p[field]["sha"]="0"*40
    elif field=="current_fence_source":p[field]["sha"]="0"*40
    with pytest.raises(x.OwnerClaimStop):
        x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s,p))
    assert s.private_puts==s.public_posts==0

@pytest.mark.parametrize("name,val",[
    ("GITHUB_RUN_ATTEMPT","2"),("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_REF","refs/heads/other"),("GITHUB_SHA","f"*40),
])
def test_broker_runner_mismatch_never_writes(monkeypatch,name,val):
    unlocked(monkeypatch)
    monkeypatch.setenv(name,val)
    s=GitScenario()
    with pytest.raises(x.OwnerClaimStop):
        x.commit_signed_acwi_prepost_and_witness_same_attempt_only(**args(s))
    assert s.owner_gets==s.private_puts==s.public_posts==0

def test_no_live_alpaca_order_or_executable_release_workflow():
    from pathlib import Path
    source=Path(x.__file__).read_text()
    assert "method=\"POST\"" in source # ONLY public GitHub issue witness, not broker
    assert "https://api.alpaca.markets" not in source
    assert "def main(" not in source
    assert "if __name__" not in source
    assert "PREPOST_PRIVATE_CAS_RELEASED=False" in source
    assert "PREPOST_PUBLIC_WITNESS_RELEASED=False" in source

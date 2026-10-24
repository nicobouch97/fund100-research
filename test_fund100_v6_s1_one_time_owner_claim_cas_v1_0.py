"""Credentialless actual Git Contents owner CAS transport contract; NO LIVE."""
from base64 import b64decode
from copy import deepcopy
from io import BytesIO
import json
from urllib.error import HTTPError, URLError

import pytest

import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as x
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fixture

READ="dummy-original-private-read-token-different"
WRITE="dummy-original-private-write-token-different"

class FakeResponse:
    def __init__(self,status,data):
        self.status=status
        self.body=BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.body.read(n)

class FakeGit:
    def __init__(self,seed,problem=None):
        self.source=deepcopy(seed)
        self.problem=problem
        self.gets=[]
        self.put_count=0
        self.expected_original=fixture.setup()
        self.put_payload=None
    def read(self,req,timeout):
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url==x.PRIVATE_CONTENTS_URL+"?ref=main"
        token=req.get_header("Authorization")
        assert token in ("Bearer "+READ,"Bearer "+WRITE)
        self.gets.append(token)
        if self.problem=="get_first_403" and len(self.gets)==1:
            raise HTTPError(req.full_url,403,"mock unauthorized",None,None)
        if self.problem=="get_prewrite_fork" and len(self.gets)==2:
            forged=deepcopy(self.source)
            forged["sha"]="0"*40
            return FakeResponse(200,forged)
        if self.problem=="get_postwrite_old" and len(self.gets)==3:
            return FakeResponse(200,self.expected_original["fence_source"])
        if self.problem=="get_postwrite_403" and len(self.gets)==3:
            raise HTTPError(req.full_url,403,"mock failed reread",None,None)
        if self.problem=="get_postwrite_forged_winner" and len(self.gets)==3:
            forged=deepcopy(self.source)
            forged["content"]="xxx"
            return FakeResponse(200,forged)
        obj=deepcopy(self.source)
        # GitHub returns 60-char line wrapping; HMAC still checks raw content.
        obj["content"]="\n".join(obj["content"][i:i+60]
                                    for i in range(0,len(obj["content"]),60))
        return FakeResponse(200,obj)
    def write(self,req,timeout):
        self.put_count+=1
        assert self.put_count==1,"No second commit attempt even after ambiguous response"
        assert timeout==12
        assert req.get_method()=="PUT"
        assert req.full_url==x.PRIVATE_CONTENTS_URL
        assert req.get_header("Authorization")=="Bearer "+WRITE
        payload=json.loads(req.data.decode("ascii"))
        self.put_payload=payload
        assert set(payload)=={"branch","content","message","sha"}
        assert payload["branch"]=="main"
        if self.problem in ("conflict_409","conflict_422","post_500"):
            status={"conflict_409":409,"conflict_422":422,"post_500":500}[self.problem]
            raise HTTPError(req.full_url,status,"fake Git CAS conflict",None,None)
        if payload["sha"]!=self.source["sha"]:
            raise HTTPError(req.full_url,409,"fake stale SHA",None,None)
        raw=b64decode(payload["content"],validate=True)
        updated=fixture.as_fence(raw)
        assert updated["sha"]==cas.blob_sha(raw)
        self.source=updated
        if self.problem in ("lost_ack","timeout"):
            if self.problem=="timeout":raise TimeoutError("mock uncertain PUT")
            raise URLError("mock PUT accepted but response lost")
        if self.problem=="wrong_reply":
            return FakeResponse(200,{"content":{"path":fence.PATH,"sha":"f"*40},
                                    "commit":{"sha":"c"*40}})
        return FakeResponse(200,{"content":{"path":fence.PATH,"sha":updated["sha"]},
                                 "commit":{"sha":"c"*40}})

def params(fake):
    a=fixture.setup()
    a.pop("fence_source")
    a["private_read_token"]=READ
    a["private_write_token"]=WRITE
    a["read_transport"]=fake.read
    a["write_transport"]=fake.write
    return a

def test_real_production_lock_blocks_before_any_private_get_or_put():
    fake=FakeGit(fixture.setup()["fence_source"])
    with pytest.raises(x.OwnerClaimStop,match="HARD LOCKED"):
        x.claim_for_same_attempt_only(**params(fake))
    assert not fake.gets and fake.put_count==0
    assert x.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False
    assert x.LIVE_BROKER_ORDER_RELEASED is False
    assert x.RETRY_AFTER_ANY_PUT_RELEASED is False

def test_first_owner_claim_one_git_cas_and_independent_hmac_readback_no_broker(monkeypatch):
    monkeypatch.setattr(x,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED",True)
    fake=FakeGit(fixture.setup()["fence_source"])
    result=x.claim_for_same_attempt_only(**params(fake))
    assert fake.gets==["Bearer "+READ,"Bearer "+WRITE,"Bearer "+READ]
    assert fake.put_count==1
    assert result["status"]=="SIGNED_ONE_OWNER_CAS_READBACK_VERIFIED_BROKER_STILL_BLOCKED"
    assert result["unique_signed_owner_winner_verified"] is True
    assert result["live_broker_order_authorized"] is False
    assert result["real_private_Git_PUTs"]==1
    assert result["real_broker_POSTs"]==0
    assert result["immutable_external_anti_rollback_anchor_proven"] is False
    assert result["original_private_signed_seq2_written"] is False
    assert result["client_order_id"] is result["original_qty"] is None
    assert WRITE not in str(result) and READ not in str(result)
    expected=fixture.setup()
    candidate=fence.plan_unique_owner(**expected)
    assert fake.put_payload["sha"]==candidate["expected_current_sha"]
    assert cas.blob_sha(b64decode(fake.put_payload["content"]))==candidate["proposed_blob_sha"]
    assert x.NO_MAIN_OR_SECRET_WORKFLOW

@pytest.mark.parametrize("problem",[
    "get_first_403","get_prewrite_fork","conflict_409","conflict_422",
    "post_500","lost_ack","timeout","wrong_reply",
    "get_postwrite_old","get_postwrite_403","get_postwrite_forged_winner",
])
def test_failure_never_retries_or_releases_broker(problem,monkeypatch):
    monkeypatch.setattr(x,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED",True)
    fake=FakeGit(fixture.setup()["fence_source"],problem=problem)
    with pytest.raises(x.OwnerClaimStop):
        x.claim_for_same_attempt_only(**params(fake))
    assert fake.put_count<=1
    if problem in ("get_first_403","get_prewrite_fork"):
        assert fake.put_count==0

def test_replayed_original_or_different_owner_cannot_claim_twice(monkeypatch):
    monkeypatch.setattr(x,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED",True)
    fake=FakeGit(fixture.setup()["fence_source"])
    x.claim_for_same_attempt_only(**params(fake))
    original_put_count=fake.put_count
    with pytest.raises(x.OwnerClaimStop,match="already claimed"):
        x.claim_for_same_attempt_only(**params(fake))
    assert fake.put_count==original_put_count

@pytest.mark.parametrize("change",[
    {"owner_run_id":"39812340002"},
    {"owner_attempt":2},
    {"owner_attempt":True},
    {"owner_nonce":"0"*64},
    {"current_main_sha":"bad"},
    {"source_broker_run_id":"fake"},
    {"original_qty":"0.987654321"},
    {"private_write_token":READ},
    {"private_read_token":"x"},
])
def test_invalid_identity_or_private_principals_never_write(change,monkeypatch):
    monkeypatch.setattr(x,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED",True)
    fake=FakeGit(fixture.setup()["fence_source"])
    args=params(fake)
    args.update(change)
    with pytest.raises(x.OwnerClaimStop):
        x.claim_for_same_attempt_only(**args)
    assert fake.put_count==0

@pytest.mark.parametrize("change",[
    {"LIVE_BROKER_ORDER_RELEASED":True},
    {"RETRY_AFTER_ANY_PUT_RELEASED":True},
    {"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED":False},
])
def test_any_real_order_or_retry_enablement_is_an_immediate_stop(change,monkeypatch):
    monkeypatch.setattr(x,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED",True)
    for k,v in change.items():monkeypatch.setattr(x,k,v)
    fake=FakeGit(fixture.setup()["fence_source"])
    with pytest.raises(x.OwnerClaimStop,match="HARD LOCKED"):
        x.claim_for_same_attempt_only(**params(fake))
    assert fake.put_count==0 and fake.gets==[]

def test_candidate_has_no_entrypoint_or_live_order_transport():
    from pathlib import Path
    src=Path(x.__file__).read_text()
    assert 'if __name__' not in src
    assert "def main(" not in src
    assert "ALPACA_LIVE_KEY" not in src
    assert "ALPACA_LIVE_SECRET" not in src
    assert "https://api.alpaca.markets" not in src
    assert "method=\"POST\"" not in src
    assert "MAX_GIT_PUTS=1" in src

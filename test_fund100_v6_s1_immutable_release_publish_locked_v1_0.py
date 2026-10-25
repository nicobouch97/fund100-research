"""Synthetic HTTP against the exact original ACWI signed owner/seq2.

All publisher locks remain FALSE outside a monkeypatched isolated test.
"""
from copy import deepcopy
from io import BytesIO
import json
from hashlib import sha256
from urllib.error import HTTPError, URLError

import pytest

import fund100_v6_s1_immutable_release_publish_locked_v1_0 as p
import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import test_fund100_v6_s1_immutable_release_anchor_v1_0 as f

READ="private-READ-dummy-principal-test-01"
WRITE="private-WRITE-dummy-principal-test-02"
ADMIN="github-ADMIN-READ-dummy-principal-test-03"
PUBLIC="github-RELEASE-WRITE-dummy-principal-test-04"
RELEASE_ID=987654321

class Reply:
    def __init__(self,status,data):
        self.status=status
        self.buffer=BytesIO(json.dumps(data).encode("utf-8"))
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self,lim):return self.buffer.read(lim)

class Scenario:
    def __init__(self,owner,seq2,mode="success"):
        self.owner=deepcopy(owner)
        self.seq2=deepcopy(seq2)
        self.mode=mode
        self.private_reads=0
        self.setting_reads=0
        self.tag_reads=0
        self.drafts=0
        self.uploads=0
        self.publishes=0
        self.asset=None
        self.verification=None
    def private(self,req,timeout):
        assert req.get_method()=="GET" and timeout==12
        assert req.get_header("Authorization") in ("Bearer "+READ,"Bearer "+WRITE)
        self.private_reads+=1
        if self.mode=="missing_private" and self.private_reads==1:
            raise HTTPError(req.full_url,403,"Forbidden",None,None)
        if req.full_url==p.original.PRIVATE_CONTENTS_URL+"?ref=main":
            data=deepcopy(self.owner["current_fence_source"])
            if self.mode=="changed_owner" and self.private_reads==2:
                data["sha"]="0"*40
        elif req.full_url==p.original.ORIGINAL_ORDER_LEDGER_URL+"?ref=main":
            data=deepcopy(self.seq2)
            if self.mode=="changed_seq2" and self.private_reads==4:
                data["sha"]="0"*40
        else:raise AssertionError(req.full_url)
        return Reply(200,data)
    def publisher(self,req,timeout):
        assert timeout==12 and req.get_header("X-github-api-version")=="2026-03-10"
        auth=req.get_header("Authorization")
        method=req.get_method()
        if req.full_url==p.IMMUTABLE_SETTING_URL:
            assert method=="GET" and auth=="Bearer "+ADMIN
            self.setting_reads+=1
            if self.mode in ("disabled","setting_403"):
                raise HTTPError(req.full_url,404 if self.mode=="disabled" else 403,
                                "Not enabled",None,None)
            if self.mode=="setting_false":
                return Reply(200,{"enabled":False,"enforced_by_owner":False})
            return Reply(200,{"enabled":True,"enforced_by_owner":False})
        if req.full_url==anchor.RELEASE_URL:
            assert method=="GET" and auth=="Bearer "+PUBLIC
            self.tag_reads+=1
            if self.mode=="preexisting":
                return Reply(200,{"tag_name":anchor.TAG})
            if self.mode=="tag_403":
                raise HTTPError(req.full_url,403,"Forbidden",None,None)
            raise HTTPError(req.full_url,404,"Not Found",None,None)
        assert auth=="Bearer "+PUBLIC
        if req.full_url==p.METADATA_URL:
            assert method=="POST"
            self.drafts+=1
            assert self.drafts==1
            body=json.loads(req.data)
            assert body["draft"] is True and body["tag_name"]==anchor.TAG
            assert body["target_commitish"]==self.owner["current_main_sha"]
            if self.mode=="draft_lost_ack":
                raise URLError("draft accepted but reply lost")
            data={"id":RELEASE_ID,"draft":True,"assets":[],
                  "tag_name":anchor.TAG,"target_commitish":body["target_commitish"]}
            if self.mode=="draft_wrong":
                data["tag_name"]="wrong"
            return Reply(201,data)
        if req.full_url.startswith("https://uploads.github.com/"):
            assert method=="POST"
            assert req.full_url.endswith("?name="+anchor.ASSET)
            self.uploads+=1
            assert self.uploads==1
            self.asset=req.data
            if self.mode=="upload_lost_ack":
                raise URLError("upload accepted but reply lost")
            data={"name":anchor.ASSET,"state":"uploaded",
                  "size":len(self.asset),"digest":"sha256:"+sha256(self.asset).hexdigest(),
                  "browser_download_url":anchor.DOWNLOAD_URL}
            if self.mode=="upload_wrong":
                data["digest"]="sha256:"+"0"*64
            return Reply(201,data)
        assert req.full_url==p.METADATA_URL+"/"+str(RELEASE_ID)
        assert method=="PATCH" and json.loads(req.data)=={"draft":False}
        self.publishes+=1
        assert self.publishes==1
        if self.mode=="publish_lost_ack":
            raise URLError("publication accepted but reply lost")
        data={"id":RELEASE_ID,"draft":False,"tag_name":anchor.TAG,
              "immutable":True,"published_at":"2026-10-25T13:00:00Z"}
        if self.mode=="publish_mutable":data["immutable"]=False
        return Reply(200,data)
    def immutable(self,req,timeout):
        if self.verification is None:
            self.verification=f.GitHubImmutable(self.asset)
        return self.verification.transport(req,timeout)

@pytest.fixture(autouse=True)
def first_original_actions_run(monkeypatch):
    original,seq2=f.original()
    for k,v in (
        ("GITHUB_REPOSITORY","nicobouch97/fund100-research"),
        ("GITHUB_REF","refs/heads/main"),
        ("GITHUB_EVENT_NAME","workflow_dispatch"),
        ("GITHUB_RUN_ATTEMPT","1"),
        ("GITHUB_RUN_ID",original["owner_run_id"]),
        ("GITHUB_SHA",original["current_main_sha"]),
    ):monkeypatch.setenv(k,v)

def data(mode="success"):
    owner,seq2=f.original()
    s=Scenario(owner,seq2,mode)
    return s,{
        "owner_sources":owner,"prepost_source":seq2,
        "private_read_token":READ,"private_write_token":WRITE,
        "admin_read_token":ADMIN,"public_release_write_token":PUBLIC,
        "private_transport":s.private,
        "public_transport":s.publisher,
        "immutable_read_transport":s.immutable,
    }

def unlock(monkeypatch):
    monkeypatch.setattr(p,"PUBLISH_SIGNED_HEAD_RELEASED",True)

def test_default_production_cannot_contact_ANY_external_endpoint():
    scenario,args=data()
    with pytest.raises(p.PublicationStop,match="HARD LOCKED"):
        p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
    assert scenario.private_reads==scenario.setting_reads==0
    assert scenario.drafts==scenario.uploads==scenario.publishes==0
    assert p.PUBLISH_SIGNED_HEAD_RELEASED is False
    assert p.LIVE_BROKER_ORDER_RELEASED is False

def test_approved_mock_state_one_immutable_draft_asset_publish_then_independent_exact_read(monkeypatch):
    unlock(monkeypatch)
    scenario,args=data()
    got=p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
    assert scenario.private_reads==4
    assert scenario.setting_reads==scenario.tag_reads==1
    assert scenario.drafts==scenario.uploads==scenario.publishes==1
    assert scenario.verification.requests==[anchor.RELEASE_URL,anchor.DOWNLOAD_URL]
    assert got["stage"]=="SIGNED_ORIGINAL_ACWI_SEQ2_PUBLISHED_IMMUTABLE_NO_BROKER"
    assert got["provider_immutable_asset_independent_GET_verified"]
    assert got["live_order_authorized"] is False
    assert got["retry_permitted"] is False
    assert got["broker_POST_attempts"]==0
    for hidden in (READ,WRITE,ADMIN,PUBLIC):
        assert hidden not in repr(got)
    assert args["owner_sources"]["original_qty"].encode() not in scenario.asset

@pytest.mark.parametrize("mode",[
    "missing_private","changed_owner","changed_seq2",
    "disabled","setting_403","setting_false","preexisting","tag_403",
])
def test_failed_private_or_setting_preflight_never_mutates_public_or_private(mode,monkeypatch):
    unlock(monkeypatch)
    scenario,args=data(mode)
    with pytest.raises(p.PublicationStop):
        p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
    assert scenario.drafts==scenario.uploads==scenario.publishes==0
    assert scenario.private_reads<=4

@pytest.mark.parametrize("mode,draft,upload,publish",[
    ("draft_lost_ack",1,0,0),("draft_wrong",1,0,0),
    ("upload_lost_ack",1,1,0),("upload_wrong",1,1,0),
    ("publish_lost_ack",1,1,1),("publish_mutable",1,1,1),
])
def test_uncertain_public_mutations_never_retry_or_send_broker(mode,draft,upload,publish,monkeypatch):
    unlock(monkeypatch)
    scenario,args=data(mode)
    with pytest.raises(p.PublicationStop,match="NEVER RETRY"):
        p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
    assert (scenario.drafts,scenario.uploads,scenario.publishes)==(draft,upload,publish)

def test_wrong_first_run_or_credential_principals_never_touch_network(monkeypatch):
    unlock(monkeypatch)
    for key,val in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_REF","refs/heads/sandbox")):
        scenario,args=data()
        monkeypatch.setenv(key,val)
        with pytest.raises(p.PublicationStop):
            p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
        assert scenario.private_reads==scenario.setting_reads==scenario.drafts==0
        monkeypatch.setenv(key,"1" if key=="GITHUB_RUN_ATTEMPT" else "refs/heads/main")
    scenario,args=data()
    args["admin_read_token"]=args["public_release_write_token"]
    with pytest.raises(p.PublicationStop,match="distinct"):
        p.publish_exact_acwi_signed_seq2_release_same_attempt_only(**args)
    assert scenario.private_reads==scenario.setting_reads==0

def test_no_prod_entrypoint_no_broker_and_pub_locks_stay_false():
    from pathlib import Path
    code=Path(p.__file__).read_text()
    assert "https://api.alpaca.markets" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "def main(" not in code and "if __name__" not in code
    assert "PUBLISH_SIGNED_HEAD_RELEASED=False" in code
    assert "LIVE_BROKER_ORDER_RELEASED=False" in code
    assert "ALLOW_RETRY_AFTER_ANY_RELEASE_POST=False" in code

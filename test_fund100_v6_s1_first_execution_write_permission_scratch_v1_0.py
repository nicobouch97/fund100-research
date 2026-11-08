"""No-network disposable GitHub principal probe tests; no actual repo writes."""
from base64 import b64decode, b64encode
from io import BytesIO
from pathlib import Path
import json
from urllib.error import HTTPError
import pytest

import fund100_v6_s1_first_execution_write_permission_scratch_v1_0 as probe

READ="fake-test-private-read-principal-2222"
WRITE="fake-test-private-write-principal-3333"
RELEASE="fake-test-public-release-write-4444"
RUN="42424242424"
MAIN_SHA="a"*40

class Reply:
    def __init__(self,status,doc=None):
        self.status=status
        self.doc=doc
    def read(self,limit=None):
        data=b"" if self.doc is None else json.dumps(self.doc).encode()
        return data if limit is None else data[:limit]
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False

class FakeGitHub:
    def __init__(self):
        self.trace=[]
        self.private=None
        self.release=None
        self.broken=None
    def __call__(self,req,timeout):
        assert timeout==12
        method=req.get_method()
        url=req.full_url
        token=req.get_header("Authorization").removeprefix("Bearer ")
        request=json.loads(req.data) if req.data is not None else None
        self.trace.append((method,url,token))
        private,tag=probe._paths(RUN)
        if self.broken=="private-write-error" and method=="PUT":
            raise HTTPError(url,403,"synthetic denied",None,None)
        if url in (private,private+"?ref=main"):
            if method=="GET":
                if self.private is None:
                    raise HTTPError(url,404,"synthetic absent",None,None)
                body=dict(self.private)
                if self.broken=="corrupt-private-read":
                    body["sha"]="0"*40
                return Reply(200,body)
            if method=="PUT":
                assert token==WRITE and request["branch"]=="main"
                if "sha" in request:
                    assert self.private is not None
                    if self.broken=="private-cas-conflict":
                        raise HTTPError(url,409,"synthetic stale private CAS",None,None)
                    assert request["sha"]==self.private["sha"]
                    raw=b64decode(request["content"])
                    self.private={
                        "path":"diagnostics/"+probe.PRIVATE_STEM+RUN+".txt",
                        "sha":probe._blob_sha(raw),"encoding":"base64",
                        "content":b64encode(raw).decode(),
                    }
                    if self.broken=="private-cas-reply-lost":
                        from urllib.error import URLError
                        raise URLError("synthetic lost CAS acknowledgement")
                    if self.broken=="private-cas-wrong-ack":
                        return Reply(200,{"content":dict(self.private,sha="0"*40)})
                    return Reply(200,{"content":dict(self.private)})
                assert self.private is None
                raw=b64decode(request["content"])
                self.private={
                    "path":"diagnostics/"+probe.PRIVATE_STEM+RUN+".txt",
                    "sha":probe._blob_sha(raw),"encoding":"base64",
                    "content":b64encode(raw).decode(),
                }
                return Reply(201,{"content":dict(self.private)})
            if method=="DELETE":
                assert token==WRITE and request["branch"]=="main"
                assert request["sha"]==self.private["sha"]
                self.private=None
                return Reply(200,{"commit":{"sha":MAIN_SHA}})
        if url==probe.PUBLIC_RELEASES and method=="POST":
            assert token==RELEASE and request["draft"] is True
            assert request["tag_name"]==tag and self.release is None
            assert request["target_commitish"]==MAIN_SHA
            self.release={
                "id":123456789,"tag_name":tag,"draft":True,"assets":[]}
            return Reply(201,dict(self.release))
        if url==probe.PUBLIC_RELEASES+"/123456789":
            if method=="GET":
                if self.release is None:
                    raise HTTPError(url,404,"synthetic deleted",None,None)
                return Reply(200,dict(self.release))
            if method=="DELETE":
                assert token==RELEASE and self.release is not None
                self.release=None
                return Reply(204)
        raise AssertionError("unexpected GitHub request: "+method+" "+url)

def test_exact_disposable_private_and_draft_writes_and_cleanup(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA",MAIN_SHA)
    fake=FakeGitHub()
    result=probe.inspect(
        run_id=RUN,private_read=READ,private_write=WRITE,
        release_write=RELEASE,transport=fake)
    assert result["status"]=="DISPOSABLE_PRIVATE_CREATE_SHA_CAS_AND_PUBLIC_DRAFT_WRITE_PROVEN"
    assert result["private_contents_existing_sha_cas_update_proven"] is True
    assert result["public_immutable_asset_upload_and_publish_proven"] is False
    assert result["original_signed_state_mutations"]==0
    assert result["original_immutable_release_mutations"]==0
    assert result["broker_orders"]==result["alpaca_requests"]==0
    assert result["live_trading_authorized"] is False
    assert result["permission_to_write_original_signed_state"] is False
    assert fake.private is None and fake.release is None
    assert [x[0] for x in fake.trace]==[
        "GET","PUT","GET","PUT","GET","DELETE","GET","POST","GET","DELETE","GET"]
    private,tag=probe._paths(RUN)
    assert all("/v2/orders" not in url and
               "v6_s1_first_acwi_execution_owner_fence" not in url and
               "v6_s1_private_order_state" not in url and
               "v6-s1-first-acwi" not in url
               for _,url,_ in fake.trace)
    assert all(t in (READ,WRITE,RELEASE) for _,_,t in fake.trace)
    for t in (READ,WRITE,RELEASE):
        assert t not in str(result)

def test_existing_scratch_is_not_overwritten(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA",MAIN_SHA)
    fake=FakeGitHub()
    fake.private={"sha":"not-us","encoding":"base64","content":"AAA","path":"another"}
    with pytest.raises(probe.ScratchStop,match="already present"):
        probe.inspect(run_id=RUN,private_read=READ,private_write=WRITE,
                      release_write=RELEASE,transport=fake)
    assert [x[0] for x in fake.trace]==["GET"]
    assert fake.release is None

@pytest.mark.parametrize("broken",[
    "private-write-error","corrupt-private-read","private-cas-conflict",
    "private-cas-reply-lost","private-cas-wrong-ack",
])
def test_private_write_failure_never_creates_public_release(monkeypatch,broken):
    monkeypatch.setenv("GITHUB_SHA",MAIN_SHA)
    fake=FakeGitHub()
    fake.broken=broken
    with pytest.raises(probe.ScratchStop):
        probe.inspect(run_id=RUN,private_read=READ,private_write=WRITE,
                      release_write=RELEASE,transport=fake)
    assert not any(url==probe.PUBLIC_RELEASES for _,url,_ in fake.trace)
    assert fake.release is None

def test_sha_conditional_cas_is_to_disposable_path_with_exact_prior_sha(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA",MAIN_SHA)
    fake=FakeGitHub()
    probe.inspect(
        run_id=RUN,private_read=READ,private_write=WRITE,
        release_write=RELEASE,transport=fake)
    private,_=probe._paths(RUN)
    writes=[x for x in fake.trace if x[0]=="PUT"]
    assert len(writes)==2
    assert writes[0][1]==writes[1][1]==private
    assert fake.private is None
    assert fake.release is None


def test_duplicate_or_missing_principals_cannot_start_network(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA",MAIN_SHA)
    fake=FakeGitHub()
    with pytest.raises(probe.ScratchStop,match="Distinct"):
        probe.inspect(run_id=RUN,private_read=READ,private_write=READ,
                      release_write=RELEASE,transport=fake)
    assert fake.trace==[]

@pytest.mark.parametrize("changed",[
    {"GITHUB_REF":"refs/heads/dev"},
    {"GITHUB_EVENT_NAME":"workflow_dispatch"},
    {"GITHUB_WORKFLOW_REF":"other/.github/workflows/untrusted.yml@refs/heads/main"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"LOW"},
])
def test_only_original_main_push_stopped_can_access_principals(monkeypatch,changed):
    e={
        "GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":probe.REPO,
        "GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"push",
        "GITHUB_WORKFLOW_REF":probe.EXPECTED_WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1","GITHUB_RUN_ID":RUN,
        "GITHUB_SHA":MAIN_SHA,"FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_RISK_LEVEL":"HIGH",
    }
    e.update(changed)
    with pytest.raises(probe.ScratchStop,match="scope"):
        probe._env(e)

def test_default_original_repo_control_is_stopped_and_script_has_no_broker_routes():
    e={
        "GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":probe.REPO,
        "GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"push",
        "GITHUB_WORKFLOW_REF":probe.EXPECTED_WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT":"1","GITHUB_RUN_ID":RUN,
        "GITHUB_SHA":MAIN_SHA,"FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_RISK_LEVEL":"HIGH",
    }
    assert probe._env(e)==RUN
    src=Path(probe.__file__).read_text()
    assert "https://api.alpaca.markets" not in src
    assert "ALPACA_LIVE_KEY" not in src
    assert "ALPACA_LIVE_SECRET" not in src
    assert "v6_s1_first_acwi_execution_owner_fence.json" not in src
    assert "v6_s1_first_acwi" not in probe.PRIVATE_BASE
    assert probe.LIVE_TRADING_RELEASED is False
    assert probe.NO_ALPACA_NETWORK and probe.NO_ORIGINAL_PRIVATE_STATE_WRITE

"""Offline signed release attempt-fence transition regressions."""
from base64 import b64decode, b64encode
import json
import pytest

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 as chain
import fund100_v6_recurring_seq1_immutable_release_recovery_locked_v1_0 as release
import fund100_v6_recurring_seq1_durable_release_attempt_fence_offline_v1_0 as fence
from test_fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 import candidate, genesis

KEY=b"synthetic-fence-test-key-" + b"x"*40
TARGET="d"*40

@pytest.fixture(autouse=True)
def mock_genesis(monkeypatch):
    monkeypatch.setattr(chain,"GENESIS_BLOB",genesis()["sha"])

def src(raw):
    return {"type":"file","path":fence.PATH,"encoding":"base64",
            "sha":journal.original.blob_sha(raw),
            "content":b64encode(raw).decode("ascii")}

def initial():
    c,_=candidate()
    return c,src(fence.initial_bytes(candidate=c,target_commit=TARGET,key=KEY))

def remote(c, uploaded=False, published=False):
    d=release._release_body(c)
    assets=([{"id":1234,"name":c["asset_name"],
        "size":len(c["asset_bytes"]),
        "digest":"sha256:"+c["asset_sha256"],
        "state":"uploaded",
        "browser_download_url":c["download_url"]}] if uploaded else [])
    return {"id":9876,"tag_name":c["tag"],"name":d["name"],
            "body":d["body"],"target_commitish":TARGET,
            "draft":not published,"prerelease":False,
            "immutable":published,"assets":assets,
            **({"published_at":"2026-10-29T17:00:00Z",
                "author":{"login":"github-actions[bot]"}} if published else {})}

def plan(c, old, change, step, observed=None, independent=None, downloaded=None):
    return fence.propose_transition(
        source=old,candidate=c,target_commit=TARGET,key=KEY,
        change=change,step=step,provider_setting=True,
        provider_release=observed,independently_get_asset=independent,
        published_downloaded_bytes=downloaded,
        synthetic_remote_sources_authenticated=True)

def commit(c,p):
    data=b64decode(p["commit"]["content_base64"],validate=True)
    result=src(data)
    assert result["sha"]==p["expected_new_blob_sha"]
    checked=fence.verify_post_cas(plan=p,source=result,candidate=c,
                                  target_commit=TARGET,key=KEY)
    assert checked["external_rollback_watermark_verified"] is False
    assert checked["provider_release_mutation_authorized"] is False
    return result

def stages():
    c,s=initial()
    outputs=[s]
    steps=[
        ("CLAIM_BEFORE_MUTATION","create",None,None,None),
        ("VERIFY_EXACT_REMOTE_SUCCESS","create",remote(c),None,None),
        ("CLAIM_BEFORE_MUTATION","upload",remote(c),None,None),
        ("VERIFY_EXACT_REMOTE_SUCCESS","upload",remote(c,True),
            remote(c,True)["assets"][0],None),
        ("CLAIM_BEFORE_MUTATION","publish",remote(c,True),
            remote(c,True)["assets"][0],None),
        ("VERIFY_EXACT_REMOTE_SUCCESS","publish",remote(c,True,True),None,c["asset_bytes"]),
    ]
    for seq,(change,step,observed,independent,downloaded) in enumerate(steps,1):
        p=plan(c,s,change,step,observed,independent,downloaded)
        assert p["expected_prior_blob_sha"]==s["sha"]
        assert p["new_sequence"]==seq
        assert p["protected_private_CAS_committed"] is False
        assert p["external_provider_mutation_performed"] is False
        assert p["broker_orders_authorized"] is False
        s=commit(c,p)
        outputs.append(s)
    return c,outputs

def test_six_monotonic_signed_fence_states_and_parent_chain():
    c,states=stages()
    assert len({s["sha"] for s in states})==7
    for seq,s in enumerate(states):
        sha,doc=fence.read_github_source(s,candidate=c,target_commit=TARGET,key=KEY)
        assert sha==s["sha"]
        assert doc["sequence"]==seq
        assert doc["attempts"]==dict(zip(fence.STEPS,fence.STATES[seq]))
        if seq: assert doc["prior_document_git_blob_sha"]==states[seq-1]["sha"]

def test_uncertain_create_and_no_remote_confirmation_prohibit_retries():
    c,old=initial()
    attempt=commit(c,plan(c,old,"CLAIM_BEFORE_MUTATION","create"))
    with pytest.raises(fence.FenceHold):
        plan(c,attempt,"CLAIM_BEFORE_MUTATION","create")
    with pytest.raises(fence.FenceHold):
        plan(c,attempt,"VERIFY_EXACT_REMOTE_SUCCESS","create")
    next_plan=plan(c,attempt,"VERIFY_EXACT_REMOTE_SUCCESS","create",remote(c))
    assert next_plan["observed_provider_next_action"]=="UPLOAD_EXACT_ASSET"

@pytest.mark.parametrize("alter",["path","sha","content","hmac","missing"])
def test_invalid_source_fails_before_any_step(alter):
    c,old=initial()
    a=dict(old)
    if alter=="path": a["path"]="state/foreign.json"
    if alter=="sha": a["sha"]="0"*40
    if alter=="content": a["content"]="!notbase64!"
    if alter=="hmac":
        data=json.loads(b64decode(a["content"]))
        data["signature"]="f"*64
        a=src(fence._canon(data))
    if alter=="missing":a={}
    with pytest.raises(fence.FenceHold):
        fence.read_github_source(a,candidate=c,target_commit=TARGET,key=KEY)

@pytest.mark.parametrize("change,step",[
    ("VERIFY_EXACT_REMOTE_SUCCESS","create"),
    ("CLAIM_BEFORE_MUTATION","upload"),
    ("CLAIM_BEFORE_MUTATION","publish"),
    ("VERIFY_EXACT_REMOTE_SUCCESS","publish"),
])
def test_cannot_skip_or_invent_attempt_state(change,step):
    c,s=initial()
    with pytest.raises(fence.FenceHold):
        plan(c,s,change,step)

def test_attempted_steps_cannot_be_replayed_after_restart():
    c,states=stages()
    for number,step in ((1,"create"),(3,"upload"),(5,"publish")):
        with pytest.raises(fence.FenceHold):
            plan(c,states[number],"CLAIM_BEFORE_MUTATION",step)
    with pytest.raises(fence.FenceHold):
        plan(c,states[-1],"CLAIM_BEFORE_MUTATION","create")

def test_wrong_signing_key_or_unsigned_provider_flag_holds():
    c,s=initial()
    with pytest.raises(fence.FenceHold):
        fence.read_github_source(s,candidate=c,target_commit=TARGET,key=b"z"*40)
    with pytest.raises(fence.FenceHold):
        fence.propose_transition(
            source=s,candidate=c,target_commit=TARGET,key=KEY,
            change="CLAIM_BEFORE_MUTATION",step="create",provider_setting=True,
            provider_release=None,synthetic_remote_sources_authenticated=False)

def test_no_external_authority_and_distinct_private_fence_path():
    c,s=initial()
    p=plan(c,s,"CLAIM_BEFORE_MUTATION","create")
    assert p["commit"]["path"]==fence.PATH
    assert fence.PATH!=journal.PATH
    assert p["immutable_fence_rollback_watermark_verified"] is False
    assert not fence.PRODUCTION_FENCE_INITIALIZATION_RELEASED
    assert not fence.PRODUCTION_SIGNED_CAS_FENCE_WRITES_RELEASED
    assert not fence.PRODUCTION_RECOVERY_SOURCE_AUTHENTICATED
    assert not fence.LIVE_BROKER_ORDER_RELEASED
    assert fence.NO_GITHUB_NETWORK and fence.NO_PRIVATE_MUTATIONS


class FakeFenceResponse:
    status=200
    def __init__(self,data):
        from io import BytesIO
        self.data=BytesIO(json.dumps(data).encode("ascii"))
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.data.read(n)


class FakeFenceHttp:
    synthetic_only=True
    def __init__(self,expected):
        self.expected=expected
        self.calls=[]
        self.lost=False
        self.bad_ack=False
    def __call__(self,req,timeout):
        assert timeout==12
        assert req.get_method()=="PUT"
        assert req.full_url==("https://api.github.com/repos/"
            +fence.REPOSITORY+"/contents/"+fence.PATH)
        d=json.loads(req.data)
        assert set(d)=={"message","sha","branch","content"}
        assert d["branch"]=="main"
        assert d["content"]==self.expected["commit"]["content_base64"]
        assert d["sha"]==self.expected["expected_prior_blob_sha"]
        self.calls.append(d)
        if self.lost:
            raise TimeoutError("accepted but lost acknowledgment")
        return FakeFenceResponse({
            "content":{"path":fence.PATH,"sha":(
                "0"*40 if self.bad_ack else self.expected["expected_new_blob_sha"])},
            "commit":{"sha":"f"*40},
        })


def test_real_http_shape_fake_private_fence_cas_no_external_authority():
    c,old=initial()
    p=plan(c,old,"CLAIM_BEFORE_MUTATION","create")
    fake=FakeFenceHttp(p)
    report=fence._one_synthetic_fence_contents_put(
        old_source=old,plan=p,candidate=c,target_commit=TARGET,
        key=KEY,writer_token="synthetic-fence-write-principal",
        transport=fake)
    assert report["status"]=="SYNTHETIC_ONE_PRIVATE_FENCE_CAS_ACK_AWAIT_INDEPENDENT_READBACK"
    assert report["new_private_fence_blob_sha"]==p["expected_new_blob_sha"]
    assert not report["public_release_action_authorized"]
    assert not report["private_CAS_readback_independently_verified"]
    assert not report["retry_allowed"]
    assert not report["broker_order_authorized"]
    assert len(fake.calls)==1


@pytest.mark.parametrize("failure",["lost","bad_ack"])
def test_uncertain_fence_cas_never_repeats_http_put(failure):
    c,old=initial()
    p=plan(c,old,"CLAIM_BEFORE_MUTATION","create")
    fake=FakeFenceHttp(p)
    setattr(fake,failure,True)
    with pytest.raises(fence.FenceHold,match="NEVER RETRY"):
        fence._one_synthetic_fence_contents_put(
            old_source=old,plan=p,candidate=c,target_commit=TARGET,key=KEY,
            writer_token="synthetic-fence-write-principal",transport=fake)
    assert len(fake.calls)==1


def test_real_fence_transport_requires_future_production_integration():
    c,old=initial()
    p=plan(c,old,"CLAIM_BEFORE_MUTATION","create")
    with pytest.raises(fence.FenceHold,match="HARD LOCKED"):
        fence._one_synthetic_fence_contents_put(
            old_source=old,plan=p,candidate=c,target_commit=TARGET,key=KEY,
            writer_token="synthetic-fence-write-principal",transport=None)
    fake=FakeFenceHttp(p)
    fake.synthetic_only=False
    with pytest.raises(fence.FenceHold,match="HARD LOCKED"):
        fence._one_synthetic_fence_contents_put(
            old_source=old,plan=p,candidate=c,target_commit=TARGET,key=KEY,
            writer_token="synthetic-fence-write-principal",transport=fake)
    assert fake.calls==[]

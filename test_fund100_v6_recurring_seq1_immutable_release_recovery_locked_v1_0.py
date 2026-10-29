"""Exactly-once signed event public release create/upload/publish recovery.

Synthetic GitHub observations, synthetic HMAC journal and fake transports
ONLY. Production private journal and release permissions never available.
"""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import fund100_v6_recurring_seq1_immutable_release_recovery_locked_v1_0 as pub
import fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 as seq1
from test_fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 import (
    candidate as make_candidate, release_for, genesis,
)

TARGET="d"*40
FRESH={"create":"NEVER_ATTEMPTED","upload":"NEVER_ATTEMPTED",
       "publish":"NEVER_ATTEMPTED"}
CREATED={**FRESH,"create":"ATTEMPTED_UNCERTAIN"}
ASSET={**CREATED,"upload":"ATTEMPTED_UNCERTAIN"}
PUBLISH={**ASSET,"publish":"ATTEMPTED_UNCERTAIN"}


@pytest.fixture(autouse=True)
def original_test_genesis(monkeypatch):
    monkeypatch.setattr(seq1,"GENESIS_BLOB",genesis()["sha"])


def plan(candidate, release=None, fence=None, setting=True, asset=None, downloaded=None,
         authenticated=True,target=TARGET):
    return pub.plan_step(
        candidate=candidate,attempts=FRESH if fence is None else fence,
        provider_setting=setting,release=release,target_commit=target,
        independently_get_asset=asset,published_downloaded_bytes=downloaded,
        remote_sources_independently_authenticated=authenticated)


def draft(candidate,with_asset=False):
    return {
        "id":1234,"name":pub._release_body(candidate)["name"],
        "body":pub._release_body(candidate)["body"],
        "tag_name":candidate["tag"],
        "target_commitish":TARGET,"draft":True,"prerelease":False,
        "immutable":False,"assets":([release_for(candidate)["assets"][0]]
                                    if with_asset else []),
    }


def published(candidate):
    result=draft(candidate,True)
    result.update(draft=False,immutable=True,
                  published_at="2026-10-29T16:00:00Z",
                  author={"login":"github-actions[bot]"})
    return result


def test_first_new_signed_head_only_one_create_draft_action():
    c,_=make_candidate()
    a=plan(c)
    assert a["next_action"]=="CREATE_DRAFT"
    assert a["requires_durable_attempt_record_before_action"] is True
    assert a["production_public_mutation_released"] is False
    assert a["broker_order_authorized"] is False
    assert a["private_git_writes"]==a["live_broker_posts"]==0


def test_lost_create_ack_and_no_visible_draft_cannot_blindly_retry():
    c,_=make_candidate()
    p=plan(c,fence=CREATED)
    assert p["next_action"]=="HOLD"
    assert p["reason"]=="MISSING_RELEASE_AFTER_POSSIBLE_POST_NEVER_RETRY"


def test_independently_observed_draft_recovery_skips_create_and_uploads_once():
    c,_=make_candidate()
    p=plan(c,release=draft(c),fence=CREATED)
    assert p["next_action"]=="UPLOAD_EXACT_ASSET"
    assert p["requires_durable_attempt_record_before_action"]
    assert p["broker_order_authorized"] is False


def test_uncertain_upload_no_asset_holds_without_reupload():
    c,_=make_candidate()
    p=plan(c,release=draft(c),fence=ASSET)
    assert p["next_action"]=="HOLD"


def test_asset_uploaded_and_independent_asset_get_skips_reupload_to_publish():
    c,_=make_candidate()
    release=draft(c,True)
    p=plan(c,release=release,fence=ASSET,
           asset=dict(release["assets"][0]))
    assert p["next_action"]=="PUBLISH_EXISTING_DRAFT"
    assert p["remote_provider_immutable_verified"] is False
    assert p["broker_order_authorized"] is False


def test_unknown_publish_ack_draft_still_visible_means_hold_not_patch_again():
    c,_=make_candidate()
    release=draft(c,True)
    p=plan(c,release=release,fence=PUBLISH,
           asset=dict(release["assets"][0]))
    assert p["next_action"]=="HOLD"


def test_published_exact_immutable_asset_and_bytes_recovers_any_ack():
    c,_=make_candidate()
    for fence in (CREATED,ASSET,PUBLISH):
        p=plan(c,release=published(c),fence=fence,
               downloaded=c["asset_bytes"])
        assert p["next_action"]=="COMPLETE_IMMUTABLE"
        assert p["remote_provider_immutable_verified"] is True
        assert p["broker_order_authorized"] is False


@pytest.mark.parametrize("fault",[
    "wrong_tag","wrong_target","wrong_name","wrong_body",
    "extra_asset","mismatched_asset","different_asset_get","mutable",
    "draft_not_published","wrong_download","other_author"])
def test_corrupt_provider_release_or_asset_never_makes_further_mutation(fault):
    c,_=make_candidate()
    release=draft(c,True)
    independent=dict(release["assets"][0])
    download=c["asset_bytes"]
    if fault=="wrong_tag":release["tag_name"]="wrong"
    if fault=="wrong_target":release["target_commitish"]="0"*40
    if fault=="wrong_name":release["name"]="attacker"
    if fault=="wrong_body":release["body"]="unrelated signed event"
    if fault=="extra_asset":release["assets"].append(dict(independent))
    if fault=="mismatched_asset":release["assets"][0]["digest"]="sha256:"+"0"*64
    if fault=="different_asset_get":independent["id"]=555
    if fault=="mutable":release["immutable"]=True
    if fault=="draft_not_published":release["draft"]=None
    if fault=="wrong_download":
        release=published(c)
        download+=b"!"
    if fault=="other_author":
        release=published(c)
        release["author"]["login"]="untrusted-bot"
    try:
        p=plan(c,release=release,fence=ASSET,
               asset=independent,downloaded=download)
    except pub.PublicationHold:
        return
    assert p["next_action"]=="HOLD"


@pytest.mark.parametrize("fault",["unauthenticated","setting_disabled","bad_target",
                                  "missing_fence","invalid_fence"])
def test_no_caller_made_authority_promotes_without_verified_context(fault):
    c,_=make_candidate()
    opts={}
    if fault=="unauthenticated":opts["authenticated"]=False
    if fault=="setting_disabled":opts["setting"]=False
    if fault=="bad_target":opts["target"]="not-a-git-commit"
    if fault=="missing_fence":opts["fence"]={}
    if fault=="invalid_fence":opts["fence"]={**CREATED,"publish":"PUBLISHED_TRUST_ME"}
    with pytest.raises(pub.PublicationHold):
        plan(c,**opts)


class Reply:
    def __init__(self,status,body):
        self.status=status
        self.io=BytesIO(json.dumps(body).encode("utf-8"))
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.io.read(n)


class FakeHttp:
    synthetic_only=True
    def __init__(self,candidate):
        self.candidate=candidate
        self.calls=[]
        self.lost=False
        self.bad_ack=False
        self.temporary_url=True
    def __call__(self,req,timeout):
        assert timeout==12
        assert req.get_header("Authorization")=="Bearer synthetic-public-release-publisher"
        assert req.get_method() in ("POST","PATCH")
        self.calls.append((req.get_method(),req.full_url))
        if self.lost:
            raise TimeoutError("provider accepted mutation but lost response")
        c=self.candidate
        if req.full_url==pub.RELEASES_URL:
            payload=json.loads(req.data)
            assert payload["tag_name"]==c["tag"]
            assert payload["make_latest"]=="false"
            assert type(payload["make_latest"]) is str
            assert payload["target_commitish"]==TARGET
            assert payload["draft"] is True and payload["prerelease"] is False
            return Reply(201,{"id":1234,"draft":not self.bad_ack,
                              "tag_name":c["tag"],"target_commitish":TARGET})
        if req.full_url.startswith(pub.UPLOAD+"/releases/"):
            assert req.data==c["asset_bytes"]
            assert req.get_header("Content-type")=="application/octet-stream"
            a=dict(release_for(c)["assets"][0])
            if self.temporary_url:
                a["browser_download_url"]=(
                    "https://github.com/example/releases/download/untagged-a123/"
                    +c["asset_name"])
            if self.bad_ack:a["digest"]="sha256:"+"0"*64
            return Reply(201,a)
        if req.full_url==pub.RELEASES_URL+"/1234":
            assert req.get_method()=="PATCH"
            assert req.data==b'{"draft":false}'
            return Reply(200,{"id":1234,"draft":self.bad_ack,
                              "tag_name":c["tag"]})
        raise AssertionError("unexpected URL")


@pytest.mark.parametrize("step",["CREATE_DRAFT","UPLOAD_EXACT_ASSET",
                                 "PUBLISH_EXISTING_DRAFT"])
def test_exact_one_github_http_mutation_and_ack_no_retry(step):
    c,_=make_candidate()
    remote=FakeHttp(c)
    a=pub._one_mutation(
        step=step,candidate=c,token="synthetic-public-release-publisher",
        target_commit=TARGET,
        release_id=(None if step=="CREATE_DRAFT" else 1234),
        transport=remote)
    assert a["ack_step"]==step
    assert a["final_immutable_public_head_proven"] is False
    assert a["retry_allowed"] is False
    assert a["broker_order_authorized"] is False
    assert len(remote.calls)==1


@pytest.mark.parametrize("step",["CREATE_DRAFT","UPLOAD_EXACT_ASSET",
                                 "PUBLISH_EXISTING_DRAFT"])
@pytest.mark.parametrize("error",["lost","bad_ack"])
def test_uncertain_remote_acks_stay_at_most_one_mutation(step,error):
    c,_=make_candidate()
    remote=FakeHttp(c)
    setattr(remote,error,True)
    with pytest.raises(pub.PublicationHold,match="NEVER RETRY"):
        pub._one_mutation(
            step=step,candidate=c,token="synthetic-public-release-publisher",
            target_commit=TARGET,
            release_id=(None if step=="CREATE_DRAFT" else 1234),
            transport=remote)
    assert len(remote.calls)==1


def test_unmarked_injected_network_refused_without_touching_github():
    c,_=make_candidate()
    remote=FakeHttp(c)
    remote.synthetic_only=False
    with pytest.raises(pub.PublicationHold,match="synthetic only"):
        pub._one_mutation(
            step="CREATE_DRAFT",candidate=c,
            token="synthetic-public-release-publisher",
            target_commit=TARGET,transport=remote)
    assert not remote.calls


def test_production_release_path_unconditionally_locked():
    c,_=make_candidate()
    with pytest.raises(pub.PublicationHold,match="HARD LOCKED"):
        pub._one_mutation(
            step="CREATE_DRAFT",candidate=c,
            token="synthetic-public-release-publisher",
            target_commit=TARGET,transport=None)


def test_no_broker_and_no_false_immutable_claim_in_repository_module():
    assert not pub.PRODUCTION_PUBLIC_MUTATION_RELEASED
    assert not pub.AUTHENTICATED_SEQ1_REMOTE_HEAD_RELEASED
    assert not pub.DURABLE_PERSISTENT_ATTEMPT_FENCE_RELEASED
    assert not pub.LIVE_BROKER_ORDER_RELEASED
    assert pub.NO_AUTOMATIC_MUTATION_RETRY
    assert pub.NO_PRIVATE_GITHUB_WRITES and pub.NO_BROKER_HTTP
    src=Path(pub.__file__).read_text()
    assert "ALPACA_LIVE_KEY" not in src
    assert "ALPACA_LIVE_SECRET" not in src
    assert 'method="PUT"' not in src
    assert "secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in src
    assert "NEXT_STANDING_LIVE_RELEASE_ALLOWED" not in src
    assert "fund100-v6-recurring-event-publisher-production-once.yml" in src
    wf=Path(".github/workflows/fund100-v6-recurring-seq1-release-recovery-regressions.yml").read_text()
    assert "  pull_request:" in wf and "  push:" not in wf
    assert "  workflow_dispatch:" not in wf and "  schedule:" not in wf
    assert "contents: read" in wf and "contents: write" not in wf
    assert "environment: fund100-live-broker" not in wf
    assert "secrets." not in wf

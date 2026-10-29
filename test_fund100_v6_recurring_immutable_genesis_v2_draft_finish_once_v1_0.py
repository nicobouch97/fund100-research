"""Preexisting signed v2 immutable release draft completion: synthetic only."""
import json
from io import BytesIO
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError

import pytest
import fund100_v6_recurring_immutable_genesis_v2_draft_finish_once_v1_0 as mod
import fund100_v6_recurring_immutable_genesis_v2_once_v1_0 as base
from test_fund100_v6_recurring_immutable_genesis_v2_once_v1_0 import (
    ENV as OLD_ENV, WITNESS, READ, WRITE, original_sources, inspect,
)

ENV = dict(OLD_ENV, GITHUB_WORKFLOW_REF=mod.WORKFLOW_REF)


class Response:
    status=200
    def __init__(self, value):
        self.io=BytesIO(json.dumps(value).encode())
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.io.read(n)


class FakeRelease:
    def __init__(self, expected):
        self.expected=expected
        self.calls=[]
        self.draft=True
        self.published=False
        self.fail_setting=False
        self.wrong_digest=False
        self.wrong_asset_id=False
        self.wrong_target=False
        self.extra_asset=False
        self.lost_ack=False
        self.missing_immutable=False
        self.stale_independent_asset=False
        self.already_published=False

    def asset(self, independently=False):
        return {
            "id":mod.EXACT_ASSET_ID if not self.wrong_asset_id else 12345,
            "name":base.ASSET,
            "size":len(self.expected),
            "digest":"sha256:" + (
                "0"*64 if (self.wrong_digest or (
                    independently and self.stale_independent_asset)) else
                sha256(self.expected).hexdigest()),
            "state":"uploaded",
            "browser_download_url":(
                base.DOWNLOAD_URL if self.published else
                "https://github.com/nicobouch97/fund100-research/releases/download/"
                "untagged-33f812a34b4ea94a9608/" + base.ASSET),
        }

    def draft_doc(self):
        return {
            "id":mod.EXACT_DRAFT_ID, "tag_name":base.TAG,
            "target_commitish": (
                "0"*40 if self.wrong_target else mod.ORIGINAL_V2_CREATE_MAIN_SHA),
            "draft":self.draft, "prerelease":False,
            "assets":[self.asset()] + ([{}] if self.extra_asset else []),
        }

    def __call__(self, req, timeout):
        assert timeout == 12
        url=req.full_url
        method=req.get_method()
        assert method in ("GET", "PATCH")
        assert req.get_header("Authorization") in (
            "Bearer "+ENV["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            "Bearer "+ENV["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"])
        self.calls.append((method,url))
        if method=="GET" and url==base.SETTING_URL:
            return Response({"enabled":not self.fail_setting,
                             "enforced_by_owner":False})
        if method=="GET" and url==mod.DRAFT_GET_URL:
            return Response(self.draft_doc())
        if method=="GET" and url==mod.ASSET_GET_URL:
            return Response(self.asset(independently=True))
        if method=="GET" and url==base.TAG_URL:
            if self.published or self.already_published:
                return Response({
                    "id":mod.EXACT_DRAFT_ID,"tag_name":base.TAG,
                    "draft":False,
                    "immutable":not self.missing_immutable,
                    "assets":[self.asset()],
                })
            raise HTTPError(url,404,"fake",{},None)
        if method=="PATCH" and url==mod.DRAFT_PATCH_URL:
            assert req.data==b'{"draft":false}'
            self.draft=False
            self.published=True
            if self.lost_ack:
                raise TimeoutError("synthetic PATCH accepted but 200 ack lost")
            return Response({
                "id":mod.EXACT_DRAFT_ID,
                "tag_name":base.TAG,
                "draft":False,
                "immutable":not self.missing_immutable,
            })
        raise AssertionError("Unexpected fake source")


def setup(monkeypatch):
    source, blob=original_sources(monkeypatch)
    def private_get(*,token):
        assert token in (READ,WRITE)
        return source
    expected=base._canon(base._signed_current_head(
        env=ENV,witness_doc=WITNESS,inspect_fn=inspect,get_fn=private_get))
    monkeypatch.setattr(mod,"EXACT_ASSET_SIZE",len(expected))
    monkeypatch.setattr(mod,"EXACT_ASSET_DIGEST","sha256:"+sha256(expected).hexdigest())
    return expected,private_get,blob


def run(monkeypatch,fake=None,env=None):
    expected,get,blob=setup(monkeypatch)
    remote=FakeRelease(expected) if fake is None else fake
    result=mod.run_once(
        environ=ENV if env is None else env, transport=remote,
        private_inspect=inspect, private_get=get,witness_doc=WITNESS)
    return result,remote,blob


def test_authentic_signed_seq0_and_exact_existing_asset_one_publish_patch(monkeypatch):
    report,fake,blob=run(monkeypatch)
    assert report["status"]=="PRODUCTION_V2_EXISTING_DRAFT_IMMUTABLE_GENESIS_VERIFIED"
    assert report["verified_private_genesis_blob_sha"]==blob
    assert report["broker_orders_authorized"] is False
    assert report["provider_immutable"] is True
    assert report["future_signed_head_events_anchored"] is False
    assert report["private_mutations"]==report["public_release_posts"]==report["public_asset_posts"]==0
    assert report["public_release_patches"]==1
    assert [method for method,_ in fake.calls]==[
        "GET","GET","GET","GET","GET","GET","PATCH","GET"]
    assert all(method!="POST" for method,_ in fake.calls)
    assert fake.published


@pytest.mark.parametrize("change",[
    {"GITHUB_REF":"refs/heads/some-branch"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"GITHUB_EVENT_NAME":"workflow_dispatch"},
    {"GITHUB_WORKFLOW_REF":"foreign"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"LOW"},
    {"FUND100_PRIVATE_STATE_READ_TOKEN":OLD_ENV["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"]},
])
def test_invalid_context_never_patches(monkeypatch,change):
    expected,get,_=setup(monkeypatch)
    fake=FakeRelease(expected)
    with pytest.raises(Exception):
        mod.run_once(
            environ=dict(ENV,**change),transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    assert not any(method=="PATCH" for method,_ in fake.calls)


@pytest.mark.parametrize("wrong",[
    "wrong_digest","wrong_asset_id","wrong_target","extra_asset",
    "stale_independent_asset","fail_setting","already_published",
])
def test_any_draft_asset_or_provider_difference_prevents_patch(monkeypatch,wrong):
    expected,get,_=setup(monkeypatch)
    fake=FakeRelease(expected)
    setattr(fake,wrong,True)
    with pytest.raises(Exception):
        mod.run_once(
            environ=ENV,transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    assert not any(method=="PATCH" for method,_ in fake.calls)


def test_lost_patch_ack_after_fake_publication_no_second_patch(monkeypatch):
    expected,get,_=setup(monkeypatch)
    fake=FakeRelease(expected)
    fake.lost_ack=True
    with pytest.raises(mod.DraftStop,match="NEVER RETRY"):
        mod.run_once(
            environ=ENV,transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    assert fake.published
    assert sum(m=="PATCH" for m,_ in fake.calls)==1


def test_published_not_immutable_is_permanent_hold(monkeypatch):
    expected,get,_=setup(monkeypatch)
    fake=FakeRelease(expected)
    fake.missing_immutable=True
    with pytest.raises(mod.DraftStop,match="NEVER RETRY"):
        mod.run_once(
            environ=ENV,transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    assert sum(m=="PATCH" for m,_ in fake.calls)==1


def test_real_pinned_original_draft_and_asset_evidence():
    assert mod.ORIGINAL_V2_CREATE_RUN_ID==40892690151
    assert mod.EXACT_DRAFT_ID==427978301
    assert mod.EXACT_ASSET_ID==688837795
    assert mod.EXACT_ASSET_SIZE==680
    assert mod.EXACT_ASSET_DIGEST=="sha256:6aa37278f20e6393d1f33c0a7004377285f53094bd78b046fc3bc574258f0af1"
    assert mod.ORIGINAL_V2_CREATE_MAIN_SHA=="2542cf4521b32564c9b5442c9210f73c8267fd15"


def test_single_patch_recovery_workflow_no_post_no_broker_and_retired_v2_creator():
    src=Path(mod.__file__).read_text()
    assert "method=\"POST\"" not in src and "method=\"PUT\"" not in src
    assert "ALPACA_LIVE_KEY" not in src
    assert mod.NO_PUBLIC_POST and mod.NO_NEW_DRAFT_OR_ASSET
    assert mod.NO_BROKER_NETWORK and mod.NO_PRIVATE_MUTATIONS
    assert mod.NO_AUTOMATIC_RETRY
    old=Path("fund100_v6_recurring_immutable_genesis_v2_once_v1_0.py").read_text()
    assert "production RETIRED" in old
    workflow=Path(".github/workflows/fund100-v6-recurring-immutable-genesis-v2-once.yml").read_text()
    assert "  push:" not in workflow and "environment: fund100-live-broker" not in workflow
    recovery=Path(".github/workflows/fund100-v6-recurring-immutable-genesis-v2-draft-finish-once.yml").read_text()
    assert "  push:" not in recovery and "  pull_request:" in recovery
    assert "  workflow_dispatch:" not in recovery and "  schedule:" not in recovery
    assert "environment: fund100-live-broker" not in recovery
    assert "contents: write" not in recovery
    assert "secrets.ALPACA_LIVE_KEY" not in recovery
    assert ("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: " + chr(36) + "{{ github.token }}") not in recovery


def test_completed_original_draft_publish_runtime_unconditionally_retired():
    with pytest.raises(mod.DraftStop,match="production RETIRED"):
        mod.run_once(environ=ENV)
    with pytest.raises(mod.DraftStop,match="production RETIRED"):
        mod.main()

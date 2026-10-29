"""Immutable original signed seq0 current-head proof; all remote calls injected."""
from io import BytesIO
import json
from pathlib import Path

import pytest

import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as gate
import fund100_v6_recurring_immutable_genesis_v2_once_v1_0 as pub
from test_fund100_v6_recurring_immutable_genesis_v2_once_v1_0 import (
    ENV as BASE, WITNESS, READ, WRITE, original_sources, inspect,
)

ENV = dict(BASE, GITHUB_WORKFLOW_REF=gate.WORKFLOW_REF)


class Response:
    status = 200
    def __init__(self, data):
        self.reader = BytesIO(data)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.reader.read(limit)


class FakeRelease:
    def __init__(self, expected):
        self.expected=expected
        self.calls=[]
        self.invalid_meta=False
        self.invalid_author=False
        self.invalid_immutable=False
        self.invalid_target=False
        self.invalid_asset=False
        self.corrupt_download=False
        self.extra_asset=False
        self.redirect=False
    def __call__(self, req, timeout):
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url in (gate.RELEASE_URL,gate.DOWNLOAD_URL)
        self.calls.append(req.full_url)
        if req.full_url==gate.DOWNLOAD_URL:
            assert req.get_header("Authorization") is None
            return Response(self.expected+b"!" if self.corrupt_download
                            else self.expected)
        assert req.get_header("Authorization")==(
            "Bearer "+ENV["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"])
        asset = {
            "id": gate.EXPECTED_ASSET_ID,
            "name": pub.ASSET,
            "size": gate.EXPECTED_ASSET_SIZE,
            "digest": "sha256:" + gate.EXPECTED_ASSET_SHA256,
            "browser_download_url":gate.DOWNLOAD_URL,
            "state": "uploaded",
        }
        if self.invalid_asset:
            asset["digest"]="sha256:"+"0"*64
        meta = {
            "id":gate.EXPECTED_RELEASE_ID,
            "tag_name": pub.TAG,
            "target_commitish": gate.EXPECTED_MAIN_CREATE_SHA,
            "draft":False,
            "immutable":True,
            "published_at":"2026-10-29T14:43:55Z",
            "author":{"login":"github-actions[bot]"},
            "assets":[asset],
        }
        if self.invalid_meta: meta["draft"]=True
        if self.invalid_author: meta["author"]={"login":"attacker"}
        if self.invalid_immutable: meta["immutable"]=False
        if self.invalid_target: meta["target_commitish"]="0"*40
        if self.extra_asset: meta["assets"].append(dict(asset))
        return Response(json.dumps(meta).encode())


def setup(monkeypatch):
    source,blob=original_sources(monkeypatch)
    reads=[]
    def private_get(*, token):
        assert token in (READ,WRITE)
        reads.append(token)
        return source
    manifest=pub._signed_current_head(
        env=ENV,witness_doc=WITNESS,inspect_fn=inspect,get_fn=private_get)
    raw=pub._canon(manifest)
    monkeypatch.setattr(gate,"EXPECTED_ASSET_SIZE",len(raw))
    monkeypatch.setattr(gate,"EXPECTED_ASSET_SHA256",__import__("hashlib").sha256(raw).hexdigest())
    reads.clear()
    return source,private_get,reads,blob,raw


def run(monkeypatch, remote=None,env=None):
    src,get,reads,blob,raw=setup(monkeypatch)
    f=FakeRelease(raw) if remote is None else remote
    report=gate.inspect(
        environ=ENV if env is None else env,
        transport=f,private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    return report,f,reads,blob


def test_two_private_hmac_reads_both_sides_exact_public_asset(monkeypatch):
    report,f,reads,blob=run(monkeypatch)
    assert report["status"]=="ACTUAL_PRIVATE_SIGNED_GENESIS_SEQ0_MATCHES_PROVIDER_IMMUTABLE_PUBLIC_ASSET"
    assert report["private_seq0_blob_sha1"]==blob
    assert report["private_sequence"]==0
    assert report["immutable_release_id"]==427978301
    assert report["signed_current_genesis_and_immutable_public_asset_verified"]
    assert report["future_signed_event_head_anchored"] is False
    assert report["production_private_CAS_authorized"] is False
    assert report["live_broker_order_authorized"] is False
    assert report["private_git_puts"]==report["public_mutations"]==report["broker_calls"]==0
    assert reads == [READ,WRITE,READ,WRITE]
    assert f.calls == [gate.RELEASE_URL,gate.DOWNLOAD_URL]


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"GITHUB_REF":"refs/heads/dev"},
    {"GITHUB_EVENT_NAME":"workflow_dispatch"},
    {"GITHUB_WORKFLOW_REF":"not-protected"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"LOW"},
    {"FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN":""},
])
def test_wrong_scope_or_token_cannot_verify_new_anchor(monkeypatch,change):
    _,get,_,_,raw=setup(monkeypatch)
    fake=FakeRelease(raw)
    with pytest.raises(Exception):
        gate.inspect(
            environ=dict(ENV,**change),transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)
    assert gate.DOWNLOAD_URL not in fake.calls


@pytest.mark.parametrize("bad",[
    "invalid_meta","invalid_author","invalid_immutable",
    "invalid_target","invalid_asset","extra_asset","corrupt_download",
])
def test_provider_or_asset_tampering_always_holds(monkeypatch,bad):
    _,get,_,_,raw=setup(monkeypatch)
    fake=FakeRelease(raw)
    setattr(fake,bad,True)
    with pytest.raises(gate.HeadStop):
        gate.inspect(
            environ=ENV,transport=fake,
            private_inspect=inspect,private_get=get,witness_doc=WITNESS)


def test_unsigned_or_alternate_private_blob_holds_before_public_call(monkeypatch):
    _,get,_,_,raw=setup(monkeypatch)
    fake=FakeRelease(raw)
    def corrupt(*,token):
        result=dict(get(token=token))
        result["sha"]="0"*40
        return result
    with pytest.raises(gate.HeadStop,match="private signed seq0"):
        gate.inspect(
            environ=ENV,transport=fake,
            private_inspect=inspect,private_get=corrupt,witness_doc=WITNESS)
    assert fake.calls == []


def test_synthetic_sources_must_be_fully_injected(monkeypatch):
    _,get,_,_,raw=setup(monkeypatch)
    fake=FakeRelease(raw)
    with pytest.raises(gate.HeadStop,match="exclusively synthetic"):
        gate.inspect(environ=ENV,transport=fake)
    assert fake.calls==[]


def test_pinned_real_public_release_and_no_mutation_or_broker():
    assert gate.EXPECTED_RELEASE_ID == 427978301
    assert gate.EXPECTED_ASSET_ID == 688837795
    assert gate.EXPECTED_ASSET_SIZE == 680
    assert gate.EXPECTED_ASSET_SHA256 == (
        "6aa37278f20e6393d1f33c0a7004377285f53094bd78b046fc3bc574258f0af1")
    assert gate.EXPECTED_MAIN_CREATE_SHA == (
        "2542cf4521b32564c9b5442c9210f73c8267fd15")
    assert gate.NO_PUBLIC_MUTATIONS and gate.NO_PRIVATE_MUTATIONS
    assert gate.NO_BROKER_HTTP and gate.NO_TRADE_PERMIT and gate.GENESIS_SEQ0_ONLY
    code=Path(gate.__file__).read_text()
    assert 'method="PUT"' not in code
    assert 'method="PATCH"' not in code
    assert 'method="POST"' not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code


def test_protected_workflow_readonly_and_full_live_audit_paths():
    wf=Path(".github/workflows/fund100-v6-recurring-immutable-genesis-current-head-getonly.yml").read_text()
    assert "  push:" in wf and "  pull_request:" in wf
    assert "  workflow_dispatch:" not in wf
    assert "  schedule:" not in wf
    assert "environment: fund100-live-broker" in wf
    assert "contents: read" in wf and "contents: write" not in wf
    assert "secrets.ALPACA_LIVE_KEY" not in wf
    assert "secrets.FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in wf
    assert "secrets.FUND100_PRIVATE_STATE_READ_TOKEN" in wf
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    pr=audit.split("  pull_request:"+chr(10)+"    paths:"+chr(10),1)[1]
    for file in (
        "fund100_v6_recurring_anchored_current_head_getonly_v1_0.py",
        "test_fund100_v6_recurring_anchored_current_head_getonly_v1_0.py",
        ".github/workflows/fund100-v6-recurring-immutable-genesis-current-head-getonly.yml"):
        assert '      - "'+file+'"' in pr

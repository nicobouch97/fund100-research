"""Offline first genuine-format event HEAD immutable release-chain tests."""
from base64 import b64decode
from copy import deepcopy
import hashlib
from pathlib import Path
import pytest

import fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 as mod
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
from test_fund100_v6_recurring_private_cas_once_offline_v1_0 import (
    AUTH, EVENT, CONTEXT, genesis, proposal, source
)


@pytest.fixture(autouse=True)
def fake_first_anchor(monkeypatch):
    # Test fixture only. The real private signed seq0/public immutable
    # RELEASE fingerprint is never changed by this test.
    monkeypatch.setattr(mod,"GENESIS_BLOB",genesis()["sha"])


def candidate():
    plan=proposal()
    after=source(b64decode(plan["commit"]["content_base64"],validate=True))
    return mod.candidate_first_reserved(
        source_seq0=genesis(),source_seq1=after,
        genesis_sha256=AUTH["genesis_sha256"],
        account_binding_sha256=AUTH["account_binding_sha256"],
        key=AUTH["key"]),after


def release_for(cand):
    return {
        "tag_name":cand["tag"],
        "draft":False,
        "immutable":True,
        "published_at":"2026-10-29T16:00:00Z",
        "author":{"login":"github-actions[bot]"},
        "assets":[{
            "id":12345,
            "name":cand["asset_name"],
            "size":len(cand["asset_bytes"]),
            "digest":"sha256:"+cand["asset_sha256"],
            "state":"uploaded",
            "browser_download_url":cand["download_url"],
        }],
    }


def test_signed_first_seq1_reservation_public_asset_is_canonical_and_nonsecret():
    cand,after=candidate()
    assert cand["status"]=="OFFLINE_CANDIDATE_SEQ1_PUBLIC_IMMUTABLE_EVENT_EDGE_NOT_PUBLISHED"
    assert cand["tag"]==mod.TAG_PREFIX+after["sha"]
    assert cand["new_signed_seq1_blob_sha"]==after["sha"]
    assert cand["parent_signed_seq0_blob_sha"]==genesis()["sha"]
    assert cand["private_git_writes"]==cand["public_release_writes"]==0
    assert cand["broker_posts"]==0 and cand["live_order_authorized"] is False
    obj=__import__("json").loads(cand["asset_bytes"])
    assert obj["private_signed_sequence"]==1
    assert obj["signed_stage"]=="RESERVED_NO_ORDER"
    assert obj["prior_immutable_release_tag"]==mod.GENESIS_TAG
    assert obj["prior_immutable_asset_sha256"]==mod.GENESIS_ASSET_SHA256
    assert obj["original_event_identity_commitment_sha256"]==hashlib.sha256(EVENT.encode()).hexdigest()
    assert obj["private_new_signed_document_sha256"]==hashlib.sha256(
        b64decode(after["content"])).hexdigest()
    assert b'"original_intent"' not in cand["asset_bytes"]
    assert b'"symbol"' not in cand["asset_bytes"]
    assert b'"account_binding"' not in cand["asset_bytes"]
    assert b'"signature"' not in cand["asset_bytes"]


def test_actual_shape_provider_immutable_public_asset_verifies_but_not_trading():
    cand,_=candidate()
    report=mod.verify_published_edge(
        candidate=cand,release_metadata=release_for(cand),
        downloaded_asset=cand["asset_bytes"])
    assert report["provider_immutable_meta_and_exact_bytes"] is True
    assert report["original_signed_private_HEAD_remote_authenticated_here"] is False
    assert report["new_sequence"]==1
    assert report["live_order_authorized"] is False


@pytest.mark.parametrize("fault",[
    "draft","mutable","bad_tag","extra_asset","wrong_asset_id","wrong_size",
    "wrong_digest","wrong_url","wrong_author","missing_publish_time","partial_upload",
    "bad_download"])
def test_no_untrusted_public_receipt_can_promote_a_signed_head(fault):
    cand,_=candidate()
    pub=release_for(cand)
    downloaded=cand["asset_bytes"]
    if fault=="draft":pub["draft"]=True
    if fault=="mutable":pub["immutable"]=False
    if fault=="bad_tag":pub["tag_name"]="wrong"
    if fault=="extra_asset":pub["assets"].append(dict(pub["assets"][0]))
    if fault=="wrong_asset_id":pub["assets"][0]["id"]=0
    if fault=="wrong_size":pub["assets"][0]["size"]=100
    if fault=="wrong_digest":pub["assets"][0]["digest"]="sha256:"+"0"*64
    if fault=="wrong_url":pub["assets"][0]["browser_download_url"]="https://example.com"
    if fault=="wrong_author":pub["author"]["login"]="forged-account"
    if fault=="missing_publish_time":pub["published_at"]=None
    if fault=="partial_upload":pub["assets"][0]["state"]="starter"
    if fault=="bad_download":downloaded+=b"!"
    with pytest.raises(mod.ChainStop):
        mod.verify_published_edge(
            candidate=cand,release_metadata=pub,downloaded_asset=downloaded)


@pytest.mark.parametrize("tamper",[
    "wrong_genesis_sha","wrong_parent_doc","wrong_seq1_hmac","unrelated_seq1_sha",
])
def test_signed_private_hmac_and_immutable_genesis_link_required_before_candidate(tamper,monkeypatch):
    old=genesis()
    plan=proposal()
    new=source(b64decode(plan["commit"]["content_base64"]))
    if tamper=="wrong_genesis_sha":
        monkeypatch.setattr(mod,"GENESIS_BLOB","0"*40)
    if tamper=="wrong_parent_doc":
        bad=dict(old)
        bad["content"]="ZGFtYWdlZA=="
        old=bad
    if tamper=="wrong_seq1_hmac":
        new=dict(new,content=new["content"][:-3]+"AA=")
    if tamper=="unrelated_seq1_sha":
        new=dict(new,sha="f"*40)
    with pytest.raises(mod.ChainStop):
        mod.candidate_first_reserved(
            source_seq0=old,source_seq1=new,
            genesis_sha256=AUTH["genesis_sha256"],
            account_binding_sha256=AUTH["account_binding_sha256"],
            key=AUTH["key"])


def test_asset_is_deterministic_for_same_signed_hmac_sources():
    first,_=candidate()
    second,_=candidate()
    assert first==second
    assert first["asset_sha256"]==hashlib.sha256(first["asset_bytes"]).hexdigest()


def test_no_real_publication_private_write_or_broker():
    assert mod.PRODUCTION_IMMUTABLE_SEQ1_PUBLISH_RELEASED is False
    assert mod.NO_GITHUB_NETWORK and mod.NO_PRIVATE_GIT_MUTATION
    assert mod.NO_BROKER_NETWORK and mod.NO_LIVE_ORDER_AUTHORITY
    code=Path(mod.__file__).read_text()
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    for forbidden in ('method="POST"','method="PATCH"','method="PUT"',
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in code

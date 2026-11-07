"""Cross-run first ACWI signed source recovery, no network or new order."""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_s1_first_acwi_postorder_durable_rehydrate_offline_v1_0 as m
import fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 as join
from test_fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 import fixtures


def sources(params):
    signed=params["signed_sources"]
    owner=params["owner_sources"]
    return {
        "current_seq2_source":signed["prepost_source"],
        "current_owner1_source":owner["current_fence_source"],
        "genesis_comment":signed["genesis_comment"],
        "first_comment":signed["first_comment"],
        "prepost_comment":signed["prepost_comment"],
        "key":signed["key"],
    }


def test_rehydrates_durable_signed_state_after_original_ephemeral_nonce_was_lost(monkeypatch):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    inputs=sources(params)
    assert "owner_nonce" not in inputs
    r=m.reconstruct(**inputs)
    assert r["status"]=="OFFLINE_ORIGINAL_ACWI_SIGNED_SEQ2_OWNER1_RECONSTRUCTED_NOT_LIVE"
    recovered_owner=r["owner_sources_for_independent_postorder_reget"]
    recovered_signed=r["signed_sources_for_independent_postorder_reget"]
    assert "owner_nonce" not in recovered_owner
    assert recovered_owner==params["owner_sources"]
    assert recovered_signed==params["signed_sources"]
    assert r["candidate_provider_immutable_asset"]==public.asset
    assert r["original_order_retry_authorized"] is False
    assert r["original_acwi_broker_fill_and_flat_verified"] is False
    assert r["source_authenticated_current_remote"] is False
    assert r["next_original_sell_or_buy_authorized"] is False
    assert r["broker_GETs"]==r["broker_POSTs"]==r["private_Git_PUTs"]==0
    assert private_calls==broker_calls==[]
    assert public.requests==[]
    # Close the real call-boundary gap: reconstructed original signed
    # sources work with the existing ORIGINAL postorder joined verification.
    p=dict(params,signed_sources=recovered_signed,owner_sources=recovered_owner)
    joined=join.inspect_postorder(**p)
    assert joined["status"]=="TEST_ONLY_ALL_SOURCES_STRUCTURALLY_JOINED_NO_LIVE_AUTHORITY"
    assert joined["original_broker_receipt_FILLS_and_flat_positions_verified"] is True
    assert joined["github_provider_immutable_owner_and_seq2_asset_verified"] is True
    assert joined["real_remote_authentication_proven_by_this_run"] is False
    assert joined["next_original_sell_or_buy_authorized"] is False
    assert len(private_calls)==4 and len(broker_calls)==6


@pytest.mark.parametrize("change",[
    lambda x:x.update(current_seq2_source=x["current_owner1_source"]),
    lambda x:x.update(current_owner1_source=x["current_seq2_source"]),
    lambda x:x["current_seq2_source"].update(sha="0"*40),
    lambda x:x["current_owner1_source"].update(sha="0"*40),
    lambda x:x["first_comment"].update(body="unrelated nonoriginal first witness"),
    lambda x:x["prepost_comment"].update(body="unrelated nonoriginal second witness"),
    lambda x:x["genesis_comment"].update(body="unrelated genesis source"),
    lambda x:x["first_comment"].update(id=123),
    lambda x:x["prepost_comment"].update(id=0),
    lambda x:x.update(key=b"wrong"*16),
])
def test_missing_or_forged_original_first_acwi_private_hmac_and_public_witness_holds(monkeypatch,change):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    s=deepcopy(sources(params))
    change(s)
    with pytest.raises(m.DurableRecoveryStop,match="HOLD"):
        m.reconstruct(**s)
    assert private_calls==broker_calls==[]
    assert public.requests==[]


def test_recovery_requires_original_prepost_document_not_reserved_seq1(monkeypatch):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    s=sources(params)
    s["current_seq2_source"]=params["signed_sources"]["reserved_source"]
    with pytest.raises(m.DurableRecoveryStop,match="HOLD"):
        m.reconstruct(**s)


def test_owner_claim_must_refer_to_exact_current_seq2_and_original_source_sha(monkeypatch):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    r=m.reconstruct(**sources(params))
    assert r["owner_sources_for_independent_postorder_reget"]["owner_run_id"]==(
        params["owner_sources"]["owner_run_id"])
    assert r["owner_sources_for_independent_postorder_reget"]["current_main_sha"]==(
        params["owner_sources"]["current_main_sha"])
    assert r["signed_sources_for_independent_postorder_reget"]["prepost_run_id"]==(
        params["signed_sources"]["prepost_run_id"])
    assert r["candidate_provider_immutable_asset"].startswith(b"{")
    assert r["candidate_provider_immutable_asset"].endswith(b"\n")


def test_never_creates_execution_authority_or_adds_credential_network_sinks():
    assert m.NO_HTTP and m.NO_PRIVATE_GIT_WRITE and m.NO_BROKER_ORDER
    assert m.LIVE_POSTORDER_SOURCE_RELEASED is False
    assert m.LIVE_FOLLOW_ON_SELL_OR_BUY_RELEASED is False
    s=Path(m.__file__).read_text()
    for forbidden in (
        "urlopen(", "requests.", "httpx.", "method=\"POST\"",
        "method=\"PUT\"","ALPACA_LIVE_SECRET",
        "ALPACA_LIVE_KEY","GITHUB_TOKEN",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    ):
        assert forbidden not in s
    assert "owner_nonce" in s  # only mentions that ephemeral nonce cannot be rebuilt
    assert "secrets.token_hex" not in s
    assert "LIVE_POSTORDER_SOURCE_RELEASED=False" in s

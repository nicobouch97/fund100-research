"""Full first ACWI postorder source join, all transports fake, zero mutations."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 as join
from test_fund100_v6_s1_original_one_attempt_chain_locked_v1_0 import (
    context_and_heads,READ,WRITE,KEY,SECRET)
from test_fund100_v6_s1_immutable_release_anchor_v1_0 import (
    GitHubImmutable,READ as PUBLIC)
from test_fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 import (
    source as fake_broker, KEY as BROKER_KEY, SECRET as BROKER_SECRET)

def fixtures(monkeypatch):
    ctx,_initial,claimed,seq2,cid,comment=context_and_heads()
    signed={
        "reserved_source":ctx["reserved_source"],"prepost_source":seq2,
        "genesis_comment":ctx["genesis_comment"],
        "first_comment":ctx["first_comment"],"prepost_comment":comment,
        "first_comment_id":ctx["first_comment_id"],
        "first_run_id":ctx["first_run_id"],
        "prepost_comment_id":cid,
        "prepost_run_id":ctx["owner_run_id"],
        "original_qty":ctx["original_qty"],"key":ctx["key"],
    }
    owner=dict(ctx,current_fence_source=claimed)
    asset=join.anchor.original_signed_anchor_asset(
        signed_owner_sources=owner,prepost_source=seq2)
    public=GitHubImmutable(asset)
    fake,docs,broker_calls,broker_transport=fake_broker(monkeypatch)
    # This source is in a closed fixture: synthetic account binding, exact
    # source shape, real signed seq2 and standard 6 GET broker adapter.
    remote={
        join.first.ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main":seq2,
        join.first.ownership.PRIVATE_CONTENTS_URL+"?ref=main":claimed,
    }
    private_calls=[]
    mock_private=object()
    def get(*,url,token,transport=None):
        assert transport is fake_get
        assert token in (READ,WRITE)
        private_calls.append((url,token))
        return deepcopy(remote[url])
    def fake_get(request,timeout):
        raise AssertionError("Unexpected direct HTTP; raw source mocked at Contents adapter")
    monkeypatch.setattr(join.first.ownership,"_get_bounded_json",get)
    params={
        "signed_sources":signed,"owner_sources":owner,
        "private_read_token":READ,"private_write_token":WRITE,
        "public_read_token":PUBLIC,"broker_key":BROKER_KEY,"broker_secret":BROKER_SECRET,
        "private_transport":fake_get,
        "public_transport":public.transport,
        "broker_transport":broker_transport,
        "now_utc":"2026-10-22T13:33:00Z",
    }
    return params,remote,docs,public,private_calls,broker_calls

def test_two_principal_private_immutable_asset_and_actual_broker_adapter_join(monkeypatch):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    # Stage-count assertions on the fake clients identify an unexpected
    # boundary rejection without printing private HMAC or broker material.
    try:
        # Verify the underlying six-GET adapter independently first. This
    # isolates source-shape integration from the private/immutable join.
    direct=join.broker.inspect_original_acwi_after_first_attempt(
        signed_prepost_sources=params["signed_sources"],
        key=params["broker_key"],secret=params["broker_secret"],
        transport=params["broker_transport"],now_utc=params["now_utc"])
    assert direct["status"]=="SIX_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH"
    broker_calls.clear()
    result=join.inspect_postorder(**params)
    except join.JoinStop:
        assert len(private_calls)==4, ("private source GET stage",len(private_calls))
        assert len(public.requests)==2, ("immutable source stage",len(public.requests))
        assert len(broker_calls)==6, ("broker source stage",len(broker_calls))
        raise
    assert result["status"]=="TEST_ONLY_ALL_SOURCES_STRUCTURALLY_JOINED_NO_LIVE_AUTHORITY"
    assert len(private_calls)==4
    assert {token for _,token in private_calls}=={READ,WRITE}
    assert public.requests==[join.anchor.RELEASE_URL,join.anchor.DOWNLOAD_URL]
    assert len(broker_calls)==6
    assert result["private_Git_GETs"]==4
    assert result["provider_immutable_GETs"]==2
    assert result["broker_GETs"]==6
    assert result["broker_POSTs"]==result["private_Git_PUTs"]==0
    assert result["mock_transport_used"] is True
    assert result["real_remote_authentication_proven_by_this_run"] is False
    assert result["original_broker_receipt_FILLS_and_flat_positions_verified"] is True
    assert result["github_provider_immutable_owner_and_seq2_asset_verified"] is True
    assert result["original_ACWI_resubmission_permitted"] is False
    assert result["next_original_sell_or_buy_authorized"] is False
    assert result["sale_proceeds_settled_or_spendable_verified"] is False
    assert all(result[k] is None for k in (
        "private_body","hmac_key","broker_key","account_id",
        "broker_order_id","client_order_id","share_quantity","fill_price"))
    for secret in (READ,WRITE,PUBLIC,KEY,SECRET):
        assert secret not in str(result)

@pytest.mark.parametrize("mode",[
    "ledger_rolled_back","owner_rolled_back",
    "immutable_draft","immutable_asset_changed",
    "broker_not_filled","broker_not_flat",
])
def test_bad_or_stale_source_blocks_reconciliation_no_second_order(monkeypatch,mode):
    params,remote,docs,public,private_calls,broker_calls=fixtures(monkeypatch)
    if mode=="ledger_rolled_back":
        remote[join.first.ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main"]={
            **params["signed_sources"]["reserved_source"]}
    if mode=="owner_rolled_back":
        remote[join.first.ownership.PRIVATE_CONTENTS_URL+"?ref=main"]={
            **params["owner_sources"]["current_fence_source"],"sha":"0"*40}
    if mode=="immutable_draft":
        public.change="draft"
    if mode=="immutable_asset_changed":
        public.change="bad_bytes"
    if mode=="broker_not_filled":
        docs[0]["status"]="partially_filled"
    if mode=="broker_not_flat":
        docs[3].append({"symbol":"ACWI","qty":"1"})
    with pytest.raises(join.JoinStop,match="HOLD"):
        join.inspect_postorder(**params)

def test_different_private_principals_are_not_optional(monkeypatch):
    params,_,_,_,private_calls,_=fixtures(monkeypatch)
    params["private_write_token"]=READ
    with pytest.raises(join.JoinStop,match="independent principals"):
        join.inspect_postorder(**params)
    assert private_calls==[]

def test_current_owner_and_signed_prepost_must_describe_same_runner(monkeypatch):
    params,_,_,_,private_calls,_=fixtures(monkeypatch)
    params["signed_sources"]=dict(params["signed_sources"],prepost_run_id="1234567")
    with pytest.raises(join.JoinStop,match="not same first attempt"):
        join.inspect_postorder(**params)
    assert private_calls==[]

def test_real_transport_requires_source_release_before_private_or_broker_get(monkeypatch):
    params,_,_,_,private_calls,broker_calls=fixtures(monkeypatch)
    for k in ("private_transport","public_transport","broker_transport","now_utc"):
        params[k]=None
    with pytest.raises(join.JoinStop,match="HARD LOCKED"):
        join.inspect_postorder(**params)
    assert private_calls==broker_calls==[]
    assert join.AUTHENTICATED_POSTORDER_GETS_RELEASED is False

def test_mixed_broker_or_provider_mock_and_real_sources_rejected(monkeypatch):
    params,_,_,_,private_calls,broker_calls=fixtures(monkeypatch)
    params["broker_transport"]=None
    with pytest.raises(join.JoinStop,match="Mixed mock"):
        join.inspect_postorder(**params)
    assert private_calls==broker_calls==[]

def test_static_no_order_private_put_or_manual_entry():
    source=Path(join.__file__).read_text()
    assert join.NO_POST_OR_PUT is True
    assert join.NO_SETTLEMENT_OR_FURTHER_ORDER_PERMISSION is True
    assert "AUTHENTICATED_POSTORDER_GETS_RELEASED=False" in source
    assert "first.ownership._get_bounded_json(" in source
    assert "anchor.verify_published_immutable_anchor(" in source
    assert "broker.inspect_original_acwi_after_first_attempt(" in source
    assert "def main(" not in source
    assert 'method="POST"' not in source and 'method="PUT"' not in source
    assert "requests.post(" not in source

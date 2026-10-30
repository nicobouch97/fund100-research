"""One read-only post-ACWI join: current private seq2+owner1, immutable HEAD, broker.

Does NOT enable trading, resubmit an ACWI order, claim settlement, or write to
private GitHub. Future real read-only operator must separately release source
GETs and supply existing segregated READ principals in a protected main job.

Tests pass all three explicit fake transports and cannot turn a mock result
into evidence of genuine LIVE account or current private records.
"""
from __future__ import annotations

import os

import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as first
import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 as broker

SCHEMA="FUND100_V6_S1_FIRST_ACWI_POSTORDER_SIGNED_IMMUTABLE_BROKER_JOIN_V1"
AUTHENTICATED_POSTORDER_GETS_RELEASED=False
NO_POST_OR_PUT=True
NO_SETTLEMENT_OR_FURTHER_ORDER_PERMISSION=True

class JoinStop(RuntimeError):
    pass

def _current_contents(url,token,transport):
    raw=first.ownership._get_bounded_json(
        url=url+"?ref=main",token=token,transport=transport)
    if type(raw) is not dict or type(raw.get("content")) is not str:
        raise JoinStop("Original signed private response malformed")
    doc=dict(raw)
    doc["content"]=doc["content"].replace("\r","").replace("\n","")
    return doc

def inspect_postorder(*,signed_sources:dict,owner_sources:dict,
                      private_read_token:str,private_write_token:str,
                      public_read_token:str,broker_key:str,broker_secret:str,
                      private_transport=None,public_transport=None,
                      broker_transport=None,now_utc=None)->dict:
    """Require independently fresh private HEADs and immutable asset.

    Mock mode: ALL three transports explicitly provided, including test
    timestamp; output never asserts genuine provider or Alpaca authentication.
    Real mode: NO transport injection, source-level HARD LOCK first.
    """
    mock=(private_transport is not None or public_transport is not None
          or broker_transport is not None or now_utc is not None)
    if mock:
        if (not callable(private_transport) or not callable(public_transport)
            or not callable(broker_transport) or type(now_utc) is not str):
            raise JoinStop("Mixed mock/real source transports forbidden")
    elif (AUTHENTICATED_POSTORDER_GETS_RELEASED is not True
          or broker.LIVE_BROKER_GET_SOURCE_RELEASED is not True
          or os.getenv("GITHUB_ACTIONS")!="true"
          or os.getenv("GITHUB_REF")!="refs/heads/main"
          or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
          or os.getenv("GITHUB_RUN_ATTEMPT")!="1"
          or os.getenv("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"):
        raise JoinStop("Postorder authenticated source GETs HARD LOCKED")
    if (any(type(x) is not str or len(x.strip())<10 or x!=x.strip()
            or "\r" in x or "\n" in x
            for x in (private_read_token,private_write_token,public_read_token))
        or len({private_read_token,private_write_token,public_read_token})!=3):
        raise JoinStop("Original first postorder independent principals missing")
    if (type(signed_sources) is not dict or type(owner_sources) is not dict
        or type(broker_key) is not str or not broker_key
        or type(broker_secret) is not str or not broker_secret):
        raise JoinStop("Missing original signed HMAC or broker GET source")
    if (set(owner_sources)!=first.EXPECTED_CONTEXT|{"current_fence_source"}
        or set(signed_sources)!={
            "reserved_source","prepost_source","genesis_comment","first_comment",
            "prepost_comment","first_comment_id","first_run_id",
            "prepost_comment_id","prepost_run_id","original_qty","key"}
        or any(owner_sources.get(k)!=signed_sources.get(k) for k in (
            "reserved_source","genesis_comment","first_comment",
            "first_comment_id","first_run_id","original_qty","key"))
        or signed_sources["prepost_run_id"]!=owner_sources["owner_run_id"]):
        raise JoinStop("Original owner/prepost sources not same first attempt")

    # Independently authenticated current HEAD reads by two distinct private
    # principals. Never trust a claimed owner or stale caller-supplied seq2.
    try:
        ledger_url=first.ownership.ORIGINAL_ORDER_LEDGER_URL
        owner_url=first.ownership.PRIVATE_CONTENTS_URL
        current_ledger_read=_current_contents(
            ledger_url,private_read_token,private_transport)
        current_ledger_write=_current_contents(
            ledger_url,private_write_token,private_transport)
        current_owner_read=_current_contents(
            owner_url,private_read_token,private_transport)
        current_owner_write=_current_contents(
            owner_url,private_write_token,private_transport)
        if (not first._same(current_ledger_read,current_ledger_write)
            or not first._same(current_owner_read,current_owner_write)
            or not first._same(current_ledger_read,signed_sources["prepost_source"])
            or not first._same(current_owner_read,owner_sources["current_fence_source"])):
            raise JoinStop("Original current HMAC seq2/owner HEAD mismatch")
        # Cryptographically cross-bind the exact owner-fence claim, HMAC seq2
        # and signed seq1; then read actual release+asset, not editable notes.
        expected_asset=anchor.original_signed_anchor_asset(
            signed_owner_sources=owner_sources,
            prepost_source=current_ledger_read)
        anchored=anchor.verify_published_immutable_anchor(
            expected_asset=expected_asset,public_read_token=public_read_token,
            transport=public_transport)
        if (anchored.get("status")!=
            "GITHUB_PROVIDER_IMMUTABLE_ACWI_HEAD_MATCHES_ORIGINAL_SIGNED_SEQ2"
            or anchored.get("provider_immutable_release_and_exact_asset_verified")
                is not True
            or anchored.get("first_live_broker_order_authorized") is not False):
            raise JoinStop("Original seq2/owner immutable asset missing")
        observed=broker.inspect_original_acwi_after_first_attempt(
            signed_prepost_sources=signed_sources,
            key=broker_key,secret=broker_secret,
            transport=broker_transport,now_utc=now_utc)
        if (observed.get("status")!=
            "SIX_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH"
            or observed.get("broker_receipt_to_all_FILLS_structurally_verified")
                is not True
            or observed.get("original_ACWI_flat_and_other_three_holdings_unchanged")
                is not True
            or observed.get("broker_GET_count")!=6
            or observed.get("broker_POST_count")!=0
            or observed.get("resend_original_ACWI_permitted") is not False
            or observed.get("credentialless_injected_transport_used") is not mock
            or observed.get("real_broker_source_authenticated_by_this_adapter")
                is not (not mock)):
            raise JoinStop("Original broker filled/flat source not reconciled")
    except Exception:
        raise JoinStop("Original postorder signed/immutable/broker proof uncertain: HOLD") from None

    return {
        "schema":SCHEMA,
        "status":("TEST_ONLY_ALL_SOURCES_STRUCTURALLY_JOINED_NO_LIVE_AUTHORITY"
                  if mock else
                  "REAL_READONLY_ORIGINAL_SIGNED_IMMUTABLE_BROKER_FILL_FLAT_JOIN"),
        "mock_transport_used":mock,
        "current_private_seq2_and_owner1_two_principal_GETs_verified":True,
        "github_provider_immutable_owner_and_seq2_asset_verified":True,
        "original_broker_receipt_FILLS_and_flat_positions_verified":True,
        "real_remote_authentication_proven_by_this_run":not mock,
        "broker_GETs":6,
        "private_Git_GETs":4,
        "provider_immutable_GETs":2,
        "broker_POSTs":0,
        "private_Git_PUTs":0,
        "original_ACWI_resubmission_permitted":False,
        "sale_proceeds_settled_or_spendable_verified":False,
        "next_original_sell_or_buy_authorized":False,
        "private_body":None,"hmac_key":None,"broker_key":None,
        "account_id":None,"broker_order_id":None,"client_order_id":None,
        "share_quantity":None,"fill_price":None,
    }

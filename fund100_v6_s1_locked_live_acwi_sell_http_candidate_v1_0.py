"""LOCKED Alpaca LIVE original ACWI fractional qty SELL HTTP transport candidate.

This module implements wire-shape and receipt validation only. It MUST NOT
be connected to a secret-bearing GitHub workflow, can NEVER automatically
unlock, and has NO main(). Original STOP, HMAC and live permissions remain
separate. Real production adapter release is a FUTURE reviewed change.
"""
from __future__ import annotations

from base64 import b64encode
from decimal import Decimal
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as seller
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prev
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as risk

SCHEMA = "FUND100_V6_S1_ORIGINAL_ACWI_FRACTIONAL_LIVE_HTTP_LOCKED_CANDIDATE_V1"
LIVE_HOST = "api.alpaca.markets"
LIVE_POST_URL = "https://api.alpaca.markets/v2/orders"
ORIGINAL = "ACWI"
ORIGINAL_PUBLIC_GENESIS_COMMENT_ID = "6321330005"
ORIGINAL_PUBLIC_GENESIS_RUN_ID = "39637082911"
RESPONSE_MAX_BYTES = 16_000
TRANSPORT_RELEASED = False
PUBLIC_EXECUTION_ENABLED = False
SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT = False
NO_MAIN_OR_WORKFLOW = True
AUTOMATIC_RETRY_RELEASED = False


class LockedSellStop(RuntimeError):
    pass


def _num(s, *, label):
    try:
        return prev._id(s,label)
    except prev.OneShotStop:
        raise LockedSellStop("Invalid audited comment/run reference") from None


def check_prepost_sources(*,reserved_source:dict,prepost_source:dict,
                          genesis_comment:dict,first_comment:dict,
                          prepost_comment:dict,first_comment_id:str,
                          first_run_id:str,prepost_comment_id:str,
                          prepost_run_id:str,original_qty:str,key:bytes)->dict:
    """Pure account/HMAC/public-head proof of exact seq1->seq2 ACWI.

    No statement here proves real broker account/session/current head or
    grants order authority. All inputs need independently sourced data.
    """
    if (TRANSPORT_RELEASED or PUBLIC_EXECUTION_ENABLED
        or SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT):
        raise LockedSellStop("Original hard LOCK contract changed")
    try:
        parent=prev.check_initial_reserved(
            source=reserved_source,
            genesis_public_comment=genesis_comment,
            first_public_comment=first_comment,
            first_comment_id=first_comment_id,
            first_run_id=first_run_id,
            original_qty=original_qty,key=key)
        pinned=witness.verify()
        next_sha,next_doc=cas._read_source(
            prepost_source,
            private_genesis=pinned["original_public_genesis_nonce"],
            account_binding_sha256=pinned["original_live_account_binding_sha256"],
            key=key)
    except (cas.CasStop,prev.OneShotStop,ValueError,KeyError,TypeError):
        raise LockedSellStop("Original HMAC signed pre-POST ledger/witness rejected") from None
    original_head=parent["source_sha"]
    if (next_sha==original_head
        or next_doc.get("sequence")!=2
        or next_doc.get("prior_document_sha")!=original_head
        or set(next_doc.get("entries",{}))!={ORIGINAL}):
        raise LockedSellStop("Signed pre-POST HEAD does not extend original reservation")
    saved=next_doc["entries"][ORIGINAL]
    if (saved.get("state")!="POST_MAY_HAVE_BEEN_SENT"
        or saved.get("client_order_id")!=cas.CLIENT_IDS[ORIGINAL]
        or saved.get("qty_commitment")!=cas._qty_commit(
            key,pinned["original_live_account_binding_sha256"],
            ORIGINAL,original_qty)):
        raise LockedSellStop("Pre-POST signed quantity/stable ID mismatch")
    expected_body=prev.second_head_comment(
        nonce=pinned["original_public_genesis_nonce"],
        old_blob_sha=original_head,new_blob_sha=next_sha,
        first_comment_id=first_comment_id,
        simulation_run_id=prepost_run_id)
    try:
        prev._comment(prepost_comment,
                      ident=_num(prepost_comment_id,label="prepost comment ID"),
                      body=expected_body)
    except prev.OneShotStop:
        raise LockedSellStop("External signed pre-POST head witness invalid") from None
    # Only for in-memory wire review. No real remote send auth output.
    return {
        "schema": SCHEMA,
        "stage": "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED",
        "signed_private_sequence":2,
        "first_symbol":ORIGINAL,
        "stable_original_client_order_id":cas.CLIENT_IDS[ORIGINAL],
        "canonical_original_fractional_qty":cas._qty(original_qty),
        "first_reservation_HMAC_verified":True,
        "prepost_advance_HMAC_verified":True,
        "public_bot_issue_head_chain_verified":True,
        "immutable_rollback_watermark_verified":False,
        "fresh_live_broker_source_verified":False,
        "live_order_authorized":False,
        "broker_orders_submitted":0,
    }


def build_exact_wire_request(*,original_qty:str,api_key:str,api_secret:str):
    """Construct only a HTTP Request object. NOT a send/permission.

    Method/host/payload/credentials are reviewed with fake values in tests.
    This function never invokes network and is NOT a live-release guard.
    """
    seller._source_lock()
    payload=seller.inspect_sell_shape(symbol=ORIGINAL,original_qty=original_qty)
    if (set(payload)!={"symbol","qty","side","type","time_in_force",
                      "extended_hours","client_order_id"}
        or payload["client_order_id"]!=cas.CLIENT_IDS[ORIGINAL]
        or payload["symbol"]!=ORIGINAL
        or payload["side"]!="sell"
        or payload["type"]!="market"
        or payload["time_in_force"]!="day"
        or payload["extended_hours"] is not False):
        raise LockedSellStop("Original ACWI fractional SELL shape changed")
    parsed=urlparse(LIVE_POST_URL)
    if (parsed.scheme!="https" or parsed.hostname!=LIVE_HOST
        or parsed.path!="/v2/orders" or parsed.query
        or parsed.port is not None or parsed.username is not None):
        raise LockedSellStop("Nonoriginal LIVE broker order host/path")
    if (type(api_key) is not str or len(api_key.strip())<10
        or type(api_secret) is not str or len(api_secret.strip())<10
        or api_key != api_key.strip() or api_secret != api_secret.strip()):
        raise LockedSellStop("Missing privately provided broker credentials")
    body=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("ascii")
    return Request(
        url=LIVE_POST_URL,method="POST",data=body,
        headers={
            "Accept":"application/json",
            "Content-Type":"application/json",
            "APCA-API-KEY-ID":api_key,
            "APCA-API-SECRET-KEY":api_secret,
            "User-Agent":"fund100-v6-s1-original-acwi-one-attempt-LOCKED",
        })


def _validate_receipt(receipt:dict,*,original_qty:str)->dict:
    """Validate a single response in memory without exposing private fields."""
    if type(receipt) is not dict:
        raise LockedSellStop("Broker order response missing")
    expected=seller.inspect_sell_shape(symbol=ORIGINAL,original_qty=original_qty)
    if (receipt.get("client_order_id")!=expected["client_order_id"]
        or receipt.get("symbol")!=ORIGINAL
        or receipt.get("side")!="sell"
        or receipt.get("type")!="market"
        or receipt.get("time_in_force")!="day"
        or receipt.get("notional") is not None):
        raise LockedSellStop("Broker order receipt not identical to original intent")
    if type(receipt.get("id")) is not str:
        raise LockedSellStop("Order receipt has no broker identifier")
    try:
        if str(UUID(receipt["id"]))!=receipt["id"].lower():
            raise ValueError
    except ValueError:
        raise LockedSellStop("Malformed broker order ID") from None
    try:
        actual=seller._qty(receipt.get("qty"))
    except seller.V6SellStop:
        raise LockedSellStop("Broker original fractional qty not authenticated") from None
    if actual!=seller._qty(original_qty):
        raise LockedSellStop("Broker SELL quantity mismatch")
    filled_raw=receipt.get("filled_qty")
    if filled_raw in (None,"0",0):
        filled=Decimal(0)
    else:
        try:filled=seller._qty(filled_raw)
        except seller.V6SellStop:
            raise LockedSellStop("Invalid broker filled quantity") from None
    if filled>actual:
        raise LockedSellStop("Broker original SELL overfilled")
    status=receipt.get("status")
    if type(status) is not str:
        raise LockedSellStop("Broker status missing")
    if status=="filled":
        if filled!=actual or type(receipt.get("filled_at")) is not str or not receipt["filled_at"]:
            raise LockedSellStop("Filled broker receipt lacks complete fill evidence")
        stage="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF"
    elif status in seller.ACTIVE:
        stage="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"
    elif status in seller.TERMINAL or status in seller.AMBIGUOUS:
        raise LockedSellStop("Broker returned terminal/ambiguous result; HOLD never resubmit")
    else:
        raise LockedSellStop("Unknown broker status; HOLD never resubmit")
    return {
        "schema":SCHEMA,"stage":stage,
        "broker_receipt_shape_checked_in_memory":True,
        "broker_position_flat_independently_verified":False,
        "broker_fill_activities_independently_verified":False,
        "sale_proceeds_settled_and_spendable":False,
        "resubmission_permitted":False,
        "live_release_claimed":False,
        "account_id":None,"broker_order_id":None,"order_quantity":None,
        "order_payload":None,
    }


def _hard_locked()->None:
    """First executable action of live entrypoint. Not env controllable."""
    if (TRANSPORT_RELEASED is not True
        or PUBLIC_EXECUTION_ENABLED is not True
        or SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT is not True):
        raise LockedSellStop("LIVE ACWI fractional SELL HTTP candidate HARD LOCKED")


def submit_live_original_acwi_sell(*,original_qty:str,api_key:str,api_secret:str,
                                   signed_review:dict,transport=None)->dict:
    """Actual HTTP POST code path exists for review, but is HARD LOCKED.

    Never wired into any GitHub Actions secret-bearing runner.
    Real execution additionally requires a separate reviewed source of fresh
    account risk and durable external anti-rollback anchor. Neither exists here.
    """
    _hard_locked()  # MUST remain the first executable statement.
    if (type(signed_review) is not dict
        or signed_review.get("schema")!=SCHEMA
        or signed_review.get("signed_private_sequence")!=2
        or signed_review.get("stage")!=
            "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
        or signed_review.get("canonical_original_fractional_qty")!=cas._qty(original_qty)
        or signed_review.get("stable_original_client_order_id")!=cas.CLIENT_IDS[ORIGINAL]
        or signed_review.get("immutable_rollback_watermark_verified") is not False
        or signed_review.get("live_order_authorized") is not False):
        raise LockedSellStop("Signed request preconditions not genuine or reviewed")
    req=build_exact_wire_request(
        original_qty=original_qty,api_key=api_key,api_secret=api_secret)
    sender=urlopen if transport is None else transport
    # Exactly one network invocation, no retry on timeout or non-2xx.
    try:
        with sender(req,timeout=12) as response:
            if getattr(response,"status",None) not in (200,201):
                raise LockedSellStop("Broker SELL HTTP not acknowledged, no retry")
            raw=response.read(RESPONSE_MAX_BYTES+1)
        if len(raw)>RESPONSE_MAX_BYTES:
            raise LockedSellStop("Broker response too large, no retry")
        parsed=json.loads(raw.decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise LockedSellStop("Broker POST response ambiguous/denied; NEVER retry") from None
    return _validate_receipt(parsed,original_qty=original_qty)

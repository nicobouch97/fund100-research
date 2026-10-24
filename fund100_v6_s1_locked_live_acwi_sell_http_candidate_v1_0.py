"""LOCKED Alpaca LIVE original ACWI fractional qty SELL *shape* candidate.

This module implements pure payload-shape and receipt validation only. It MUST NOT
be connected to a secret-bearing GitHub workflow, can NEVER automatically
unlock, and has NO main(). Original STOP, HMAC and live permissions remain
separate. Real HTTP POST belongs exclusively to the separate reviewed writer boundary.
"""
from __future__ import annotations

from base64 import b64encode
from decimal import Decimal
import json
from uuid import UUID

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as seller
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prev
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as risk
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as owner_fence

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
    if risk.contract()["orders_authorized"] is not False:
        raise LockedSellStop("Original account STOP/policy changed")
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


def build_exact_sell_payload(*,original_qty:str)->dict:
    """Return deterministic original qty-SELL JSON shape; NO network/keys.

    The separate, pre-existing reviewed broker writer boundary owns real
    HTTP requests. This module cannot build or send an HTTP Request.
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
    return payload



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



def review_unique_owner_first_ACWI_sell_candidate(
        *,owner_sources:dict,signed_sources:dict,
        simulated_receipt:dict)->dict:
    """Cross-check ONE owner-signed claim with the locked original sell shape.

    This is a source-injected OFFLINE receipt-only review: no live source
    principal, current account mark, external immutable watermark, or
    production SELL release. A genuine owner-fence claim is not permission
    to submit, and 404 cannot establish no historic broker POST.
    The actual LIVE owner fence remains unclaimed.
    """
    if type(owner_sources) is not dict or type(signed_sources) is not dict:
        raise LockedSellStop("Missing independent original owner and private inputs")
    for name in ("reserved_source","genesis_comment","first_comment",
                 "first_comment_id","first_run_id","original_qty","key"):
        if (name not in owner_sources or name not in signed_sources
            or owner_sources[name]!=signed_sources[name]):
            raise LockedSellStop("Owner and pre-POST first HMAC sources differ")
    if (owner_sources.get("owner_attempt") is True
        or type(owner_sources.get("owner_attempt")) is not int
        or owner_sources["owner_attempt"]!=1):
        raise LockedSellStop("Original first-run owner attempt not exact")
    try:
        owner=owner_fence.verify_claimed_owner(**owner_sources)
    except Exception:
        raise LockedSellStop("Signed first owner fence claim did not match ACWI") from None
    if (owner.get("stage")!="OFFLINE_SIGNED_OWNER_MATCHES_ORIGINAL_ACWI_NO_ORDER_RELEASE"
        or owner.get("unique_original_workflow_owner_HMAC_recognized") is not True
        or owner.get("source_signed_reserved_and_prepost_HEADs_bound") is not True
        or owner.get("claimed_fence_signed_current_head_verified") is not True
        or owner.get("claimed_fence_head_immutable_outside_GitHub") is not False
        or owner.get("LIVE_order_released") is not False
        or owner.get("restarted_same_owner_can_submit") is not False
        or owner.get("different_owner_can_submit") is not False
        or owner.get("real_broker_POSTs")!=0):
        raise LockedSellStop("Unverified or released original owner source")
    signed=check_prepost_sources(**signed_sources)
    if (signed.get("signed_private_sequence")!=2
        or signed.get("stable_original_client_order_id")!=cas.CLIENT_IDS[ORIGINAL]
        or signed.get("immutable_rollback_watermark_verified") is not False
        or signed.get("live_order_authorized") is not False):
        raise LockedSellStop("Original prePOST signed state not strictly held")
    payload=build_exact_sell_payload(
        original_qty=signed["canonical_original_fractional_qty"])
    if payload["client_order_id"]!=signed["stable_original_client_order_id"]:
        raise LockedSellStop("Owner/pre-POST/broker payload client IDs disagree")
    receipt=_validate_receipt(
        simulated_receipt,original_qty=payload["qty"])
    if (receipt.get("resubmission_permitted") is not False
        or receipt.get("live_release_claimed") is not False):
        raise LockedSellStop("Original receipt improperly claims resend rights")
    return {
        "schema":SCHEMA,
        "status":"SIGNED_UNIQUE_OWNER_AND_ACWI_SEQ2_LOCKED_SELL_SHAPE_REVIEW_ONLY",
        "original_signed_owner_matches_run_and_nonce":True,
        "original_signed_ACWI_prepost_sequence":2,
        "same_original_first_HMAC_sources_verified":True,
        "original_client_ID_in_owner_prepost_and_broker_shape_bound":True,
        "simulated_receipt_stage":receipt["stage"],
        "production_owner_claimed_by_this_review":False,
        "external_immutable_anti_rollback_verified":False,
        "fresh_live_account_risk_and_broker_reconciliation_verified":False,
        "durable_live_restart_recovery_verified":False,
        "reviewed_REAL_broker_POST_released":False,
        "live_order_authorized":False,
        "live_order_retry_authorized":False,
        "real_broker_POSTs":0,
        "real_private_Git_PUTs":0,
        "original_qty":None,"client_order_id":None,
        "owner_run_id":None,"account_ID":None,
        "private_HMAC":None,"broker_payload":None,
    }


def _hard_locked()->None:
    """First executable action of live entrypoint. Not env controllable."""
    if (TRANSPORT_RELEASED is not True
        or PUBLIC_EXECUTION_ENABLED is not True
        or SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT is not True):
        raise LockedSellStop("LIVE ACWI fractional SELL HTTP candidate HARD LOCKED")


def offline_review_signed_prepost_and_receipt(*,signed_sources:dict,
                                              simulated_receipt:dict)->dict:
    """Pure signed-state → qty payload → fake receipt review.

    It does NOT source a real broker receipt, authenticate a fresh risk
    snapshot, or authorize a trade. Only original synthetic fixtures may be
    used by the credentialless PR workflow.
    """
    if type(signed_sources) is not dict:
        raise LockedSellStop("Signed source fixtures missing")
    checked=check_prepost_sources(**signed_sources)
    expected=build_exact_sell_payload(
        original_qty=checked["canonical_original_fractional_qty"])
    if expected["client_order_id"]!=checked["stable_original_client_order_id"]:
        raise LockedSellStop("Original signed client ID is inconsistent")
    classified=_validate_receipt(
        simulated_receipt,original_qty=expected["qty"])
    return {
        "schema":SCHEMA,
        "status":"PURE_SIGNED_PREPOST_AND_FAKE_BROKER_RECEIPT_VERIFIED_NO_SEND",
        "signed_sequence":checked["signed_private_sequence"],
        "original_symbol":"ACWI",
        "receipt_stage":classified["stage"],
        "independent_real_broker_receipt_verified":False,
        "immutable_rollback_watermark_verified":False,
        "real_live_order_authorized":False,
        "actual_broker_POSTs":0,
        "original_quantity_or_receipt_exported":False,
        "payload":None,
    }


def submit_live_original_acwi_sell(*,original_qty:str,api_key:str,api_secret:str,
                                   signed_sources:dict,transport=None)->dict:
    """PERMANENTLY DISCONNECTED. Do not bypass reviewed writer boundary."""
    _hard_locked()  # MUST be first executable action.
    raise LockedSellStop(
        "The reviewed original LIVE broker writer boundary has NOT approved "
        "the V6 fractional SELL POST transport; no executable HTTP in this module")

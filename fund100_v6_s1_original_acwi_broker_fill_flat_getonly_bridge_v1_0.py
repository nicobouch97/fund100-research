"""First original ACWI sale: six broker GETs -> existing signed fill/flat checker.

REVIEW-ONLY. NOT a LIVE or private-state runner. This implements the missing
post-order BROKER source adapter: closed original receipt by signed client ID,
bounded FILL activities, account, positions, open orders and market clock.
No broker POST, no private Git mutations, no settlement certification, and no
automatic second order. An injected fake transport is for credentialless tests;
real GETs remain source-HARD-LOCKED until independently reviewed release.

The signed source argument is caller-provided: its HMAC/sequence/first witness
are structurally checked, but this adapter CANNOT independently authenticate
the current private remote HEAD or immutable post-send public watermark.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from hashlib import sha256
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_v6_brokerless_transition_preview_v1_0 as origin
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as original_four
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as original_signed
import fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 as proof
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original_ledger

SCHEMA="FUND100_V6_S1_FIRST_ORIGINAL_ACWI_SIX_BROKER_GET_RECEIPT_FILL_FLAT_V1"
LIVE_BROKER_GET_SOURCE_RELEASED=False
NO_BROKER_POST=True
NO_PRIVATE_GIT_MUTATION=True
NO_SETTLED_CASH_OR_NEXT_TRADE_AUTHORITY=True
FILL_QUERY_AFTER="2026-10-01"
FILL_QUERY_AFTER_UTC="2026-10-01T00:00:00Z"
FILL_LIMIT=100
GET_COUNT=6

class ReadStop(RuntimeError):
    pass

def _scope():
    if (LIVE_BROKER_GET_SOURCE_RELEASED is not True
        or os.environ.get("GITHUB_ACTIONS")!="true"
        or os.environ.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.environ.get("GITHUB_REF")!="refs/heads/main"
        or os.environ.get("GITHUB_RUN_ATTEMPT")!="1"
        or os.environ.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or os.environ.get("FUND100_RISK_LEVEL")!="HIGH"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH") not in ("ENGAGED","DISENGAGED")):
        raise ReadStop("Original post-ACWI broker GET source HARD LOCKED")
    live.require_readonly_arm()

def _source_preflight(signed_sources):
    if (type(signed_sources) is not dict
        or set(signed_sources)!={
            "reserved_source","prepost_source","genesis_comment",
            "first_comment","prepost_comment","first_comment_id",
            "first_run_id","prepost_comment_id","prepost_run_id",
            "original_qty","key"}):
        raise ReadStop("Original ACWI signed source fields missing")
    try:
        source=original_signed.check_prepost_sources(**signed_sources)
        if (source.get("stage")!=
                "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
            or source.get("first_symbol")!="ACWI"
            or source.get("live_order_authorized") is not False
            or source.get("stable_original_client_order_id")!=
                original_ledger.CLIENT_IDS["ACWI"]):
            raise ReadStop("Signed original first ACWI source rejected")
    except Exception:
        raise ReadStop("Signed original seq2 / ACWI order identity invalid") from None
    return source

def _same_original_live_account(account):
    # The frozen historical bootstrap policy supplies the account binding.
    # No user-supplied account identifier or rebinding token is admissible.
    historical_policy,_=origin.original(original_four.POLICY)
    bound=sha256(("FUND100-LIVE-ACCOUNT|"+
                  account["id"].strip()).encode()).hexdigest()
    return historical_policy.get("account_binding_sha256")==bound

def _observe(request,*,signed_sources,now_utc):
    if now_utc is not None:
        # Explicit timestamps are test-only; validate before contacting a
        # transport. Genuine broker observations are stamped AFTER all GETs.
        if type(now_utc) is not str:
            raise ReadStop("Postorder source observation missing")
        try:
            fixed=proof._time(now_utc)
            if fixed>datetime.now(timezone.utc)+timedelta(minutes=1):
                raise ReadStop("Future timestamp for postorder broker source")
        except Exception:
            raise ReadStop("Invalid broker observation timestamp") from None
    try:
        cid=original_ledger.CLIENT_IDS["ACWI"]
        docs=(
            request(path="/v2/orders:by_client_order_id",
                    params={"client_order_id":cid}),
            request(path="/v2/account/activities/FILL",params={
                    "after":FILL_QUERY_AFTER,"direction":"asc",
                    "page_size":FILL_LIMIT}),
            request(path="/v2/account",params=None),
            request(path="/v2/positions",params=None),
            request(path="/v2/orders",params={"status":"open","limit":100}),
            request(path="/v2/clock",params=None),
        )
    except Exception:
        raise ReadStop("Original postorder broker GET unavailable; HOLD, no retry POST") from None
    # A real broker market clock can be acquired *after* the beginning of
    # the six GETs. Stamp the completed batch, never its start; otherwise
    # valid late-acquired clock timestamps appear ahead of our observation.
    if now_utc is None:
        now_utc=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    observed=proof._time(now_utc)
    receipt,fills,account,positions,open_orders,clock=docs
    if (type(receipt) is not dict or type(fills) is not list
        or len(fills)>=FILL_LIMIT
        or type(account) is not dict or type(positions) is not list
        or type(open_orders) is not list or type(clock) is not dict
        or type(clock.get("is_open")) is not bool):
        raise ReadStop("Original postorder broker source incomplete/paginated; HOLD")
    if len(positions)>20 or len(open_orders)>100:
        raise ReadStop("Unbounded postorder broker positions or open orders")
    if type(account.get("id")) is not str or not account["id"].strip():
        raise ReadStop("Original postorder account identifier missing")
    try:
        if not _same_original_live_account(account):
            raise ReadStop("Broker postorder account not bound to original LIVE pilot")
        broker_clock=proof._time(clock.get("timestamp"))
        if not timedelta(0)<=observed-broker_clock<=timedelta(minutes=2):
            raise ReadStop("Postorder LIVE broker clock stale or future")
        report=proof.assess(
            signed_prepost_sources=signed_sources,
            closed_receipt=receipt,fill_pages=[fills],
            post_positions=positions,open_orders=open_orders,
            observed_at_utc=now_utc,fill_query_after_utc=FILL_QUERY_AFTER_UTC)
        if (report["stage"]!=
            "SYNTHETIC_ACWI_SELL_RECEIPT_FILLS_AND_FLAT_STRUCTURALLY_MATCH"
            or report["broker_receipt_to_complete_FILLS_structurally_linked"] is not True
            or report["original_ACWI_absent_in_post_positions"] is not True):
            raise ReadStop("Original postorder fill/flat linkage failed")
    except Exception:
        raise ReadStop("Original signed ACWI receipt/FILL/flat source mismatch") from None
    return {
        "schema":SCHEMA,
        "status":"SIX_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH",
        "real_broker_source_authenticated_by_this_adapter":False,
        "credentialless_injected_transport_used":True,
        "signed_ACWI_seq2_public_witness_structure_verified":True,
        "original_broker_account_binding_structurally_verified":True,
        "broker_receipt_to_all_FILLS_structurally_verified":True,
        "original_ACWI_flat_and_other_three_holdings_unchanged":True,
        "signed_current_private_HEAD_independently_verified":False,
        "provider_immutable_postsend_HEAD_independently_verified":False,
        "original_sale_T_plus_one_settled":False,
        "next_legacy_sell_or_any_live_buy_released":False,
        "broker_GET_count":GET_COUNT,
        "broker_POST_count":0,
        "private_Git_PUT_count":0,
        "resend_original_ACWI_permitted":False,
        "account_id":None,"order_id":None,"client_order_id":None,
        "quantity":None,"price":None,"broker_secrets":None,
    }

def inspect_original_acwi_after_first_attempt(*,signed_prepost_sources:dict,
                                               key:str,secret:str,
                                               transport=None,
                                               now_utc:str|None=None)->dict:
    """Read-only structural join. Never claim to settle sale or release buys.

    A genuine future broker read requires a separately released protected
    runner and an authentic private HEAD/immutable witness join *outside*
    this module. Tests may inject callable transport but MUST NEVER turn
    those mock results into authenticated LIVE account evidence.
    """
    if type(key) is not str or not key or type(secret) is not str or not secret:
        raise ReadStop("Broker GET credentials missing")
    _source_preflight(signed_prepost_sources)
    if transport is None:
        _scope()
        if now_utc is not None:
            raise ReadStop("Real broker observation time cannot be caller-provided")
        stamp=None  # _observe derives actual observation time AFTER six GETs.
        def get(*,path,params):
            return live.get_json(path=path,params=params,key=key,secret=secret)
    else:
        if not callable(transport) or type(now_utc) is not str:
            raise ReadStop("Mock-only transport and timestamp must be explicit")
        stamp=now_utc
        def get(*,path,params):
            return transport(path=path,params=params,key=key,secret=secret)
    result=_observe(get,signed_sources=signed_prepost_sources,now_utc=stamp)
    if transport is None:
        # Runtime GETs were genuinely sent by this process with supplied
        # Alpaca credentials, but the signed private head's CURRENT origin
        # and provider-immutable external watermark remain unproven here.
        result["credentialless_injected_transport_used"]=False
        result["real_broker_source_authenticated_by_this_adapter"]=True
    return result

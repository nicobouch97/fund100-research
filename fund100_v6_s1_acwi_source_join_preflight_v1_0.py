"""V6-S1: source-joined first ACWI original signed-genesis + seven-GET risk preflight.

NO networking, secrets, private Git commit, real or simulated broker POST,
live workflow entrypoint, permanent head anchor, or trade authorisation.
Inputs must be freshly fetched independently by a future reviewed protected
reader; caller-provided source dictionaries are NOT authenticated provenance.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256

import fund100_v6_s1_live_original_client_ids_getonly_v1_0 as broker
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as risk
import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as intent
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as seller
import fund100_alpaca_live_writer_candidate_v1_1 as writer

SCHEMA = "FUND100_V6_S1_ACWI_SOURCE_JOINED_INITIAL_PREFLIGHT_V1"
LIVE_EXECUTION_RELEASED = False
PRIVATE_STATE_MUTATION_RELEASED = False
FIRST_SELL_LIMIT = Decimal("65.00")
ILLUSTRATIVE_MARK_BUFFER = Decimal("1.05")
ORIGINAL_GENESIS_COMMENT = "6321330005"
ORIGINAL_GENESIS_RUN = "39637082911"


class SourceJoinStop(ValueError):
    pass


def inspect(*, account:dict,positions:list,orders:list,clock:dict,lookups:dict,
            bootstrap:dict,policy:dict,control:dict,
            observed_at_utc:str,remotely_stopped:bool,kill_switch:str,risk_level:str,
            private_source:dict,genesis_comment:dict,hmac_hex:str)->dict:
    """Combine *in-memory* original seven broker GETs with signed seq0 sources.

    The candidate reservation is inspected only, never returned or applied.
    A later actual reader must prove capture/source provenance at decision time.
    """
    try:
        policy_state=risk.contract()
        if (policy_state["orders_authorized"] is not False
            or policy_state["separately_signed_release_present"] is not False
            or policy_state["retains_original_XLE_subject_to_target"] is not True
            or LIVE_EXECUTION_RELEASED is not False
            or PRIVATE_STATE_MUTATION_RELEASED is not False
            or any(getattr(writer,x) is not False for x in (
                "TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
                "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
                "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
                "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
                "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED"))):
            raise SourceJoinStop("Original V6 stopped policy and six writer locks required")
        original_qty=intent.original_acwi_qty()
        # Enforces actual account identity vs original locked V5 policy, original
        # quantities of four holdings, zero open orders and precisely three
        # interpreted deterministic client-ID responses; 404 is never-post UNKNOWN.
        checked=broker.assess(
            account=account,positions=positions,orders=orders,clock=clock,
            lookups=lookups,bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,risk_level=risk_level,
            observed_at_utc=observed_at_utc)
        if (checked["original_three_client_ids_not_found_404"]!=3
            or checked["original_three_client_ids_observed"]!=0
            or checked["broker_get_requests"]!=7
            or checked["broker_non_get_requests"]!=0
            or checked["real_order_submission_authorized"] is not False):
            raise SourceJoinStop("Original live migration order-ID evidence not clear")
        pinned=witness.verify()
        binding=sha256(("FUND100-LIVE-ACCOUNT|"+account["id"].strip()).encode()).hexdigest()
        if (binding!=pinned["original_live_account_binding_sha256"]
            or policy["account_binding_sha256"]!=binding):
            raise SourceJoinStop("Broker identity, source and signed ledger binding differ")
        genesis=recovery.validate_sources(
            private_source=private_source,issue_comment=genesis_comment,
            public_comment_id=ORIGINAL_GENESIS_COMMENT,
            bootstrap_run_id=ORIGINAL_GENESIS_RUN,
            hmac_hex=hmac_hex,original_witness=pinned)
        if (genesis["private_ledger_sequence"]!=0
            or genesis["original_empty_entries_count"]!=0
            or genesis["independently_immutable_rollback_anchor_proven"] is not False):
            raise SourceJoinStop("Original genesis is not an independently immutable proof")
        held=next(x for x in positions if x["symbol"]=="ACWI")
        qty=seller._qty(held["qty"])
        if qty!=seller._qty(original_qty):
            raise SourceJoinStop("ACWI source fractional quantity differs from held shares")
        # Original current_price is a broker MARK, not a protected execution
        # price. Require a planning buffer; actual order-time bid/ask,
        # portfolio drawdown and 1-day settlement remain NOT PROVEN.
        price=Decimal(str(held["current_price"]))
        if not price.is_finite() or price<=0:
            raise SourceJoinStop("Original broker ACWI mark invalid")
        envelope=qty*price*ILLUSTRATIVE_MARK_BUFFER
        plan=cas.plan_reserve(
            private_source,symbol="ACWI",original_qty=original_qty,
            private_genesis=pinned["original_public_genesis_nonce"],
            account_binding_sha256=binding,key=bytes.fromhex(hmac_hex))
        if (plan.get("stage")!="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
            or plan.get("live_order_authorized") is not False
            or plan.get("old_blob_sha")!=private_source.get("sha")
            or plan.get("commit",{}).get("expected_current_sha")!=private_source.get("sha")):
            raise SourceJoinStop("Private initial ACWI reservation is not clean")
        if clock["is_open"] is not True:
            stage="HALT_MARKET_NOT_IN_REGULAR_SESSION"
        elif envelope>FIRST_SELL_LIMIT:
            stage="HALT_BUFFERED_SELL_VALUE_EXCEEDS_FIRST_ORDER_LIMIT"
        else:
            stage="SOURCE_JOINED_ORIGINAL_ACWI_ENVELOPE_REVIEW_ONLY_NO_TRADING"
    except SourceJoinStop:
        raise
    except Exception:
        # Raw error messages might carry unredacted broker/private source values.
        raise SourceJoinStop("Source-joined authentic-state structure invalid; stopped") from None
    return {
        "schema":SCHEMA,"stage":stage,
        "source_mode":"INJECTED_SOURCES_PROVENANCE_NOT_AUTHENTICATED_BY_THIS_MODULE",
        "seven_broker_GET_shapes_account_quantities_and_original_client_ids_checked":True,
        "original_unmatched_three_404_observed_not_never_POST_proven":True,
        "original_account_binding_matches_original_signed_genesis":True,
        "original_private_genesis_HMAC_and_issue8_head_checked":True,
        "original_private_sequence":0,"original_signed_reservation_only_calculated_in_memory":True,
        "original_XLE_retained":True,
        "buffered_mark_assessed_against_original_65_dollar_max":True,
        "buffered_mark_is_executable_price_proof":False,
        "fresh_order_time_quotes_verified":False,
        "live_drawdown_and_volatility_ceiling_verified":False,
        "future_HEAD_immutable_external_anchor_verified":False,
        "cross_actions_single_writer_lock_independently_proven":False,
        "settled_cash_verified":False,
        "live_v6_separate_operator_GO_verified":False,
        "broker_client_id_404_authorizes_a_trade":False,
        "funded_order_submission_authorized":False,
        "signing_secrets_or_private_quantities_exported":False,
        "real_private_Git_PUTs":0,"broker_requests_by_module":0,
        "real_broker_POSTs":0,"real_orders_placed":0,
        "private_head":None,"private_quantity":None,"client_order_id":None,
        "broker_account_id":None,"executable_order_payload":None,
    }

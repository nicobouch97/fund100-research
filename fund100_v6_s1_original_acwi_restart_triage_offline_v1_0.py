"""V6-S1 restart triage for original signed ACWI state, with NO send path.

A *classification* contract only. Synthetic/injected sources cannot prove
authentic real-time broker transport, fresh risk, external immutable HEAD or
a funded order release. Even exact signed seq2 plus observed broker order
is an instruction to RECONCILE, not send or claim filled/settled positions.
No network, credentials, HMAC logging, file persistence or executable order.
"""
from __future__ import annotations

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as once
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as locked

SCHEMA="FUND100_V6_S1_ORIGINAL_ACWI_RESTART_TRIAGE_OFFLINE_V1"
BROKER_NOT_OBSERVED="NOT_OBSERVED_404"
BROKER_FOUND="BROKER_ORDER_FOUND"
ORIGINAL="ACWI"
ORIGINAL_FIRST_COMMENT="6321330005"
ORIGINAL_GENESIS_RUN="39637082911"
NO_BROKER_NETWORK=True
NO_PRIVATE_GIT_NETWORK=True
NO_BROKER_POST_RETRY=True
NO_ORDER_RELEASE=True

class RecoveryTriageStop(ValueError):
    pass

def classify(*, current_source:dict, original_qty:str, key:bytes,
             genesis_comment:dict, broker_lookup:dict,
             first_proof:dict|None=None, prepost_proof:dict|None=None)->dict:
    """Original seq0/1/2, signed comments, broker lookup -> zero-send decision.

    Returned redacted state is not a LIVE broker assertion or trading permit.
    Missing/mismatched public witness, unknown/unsafe receipt, foreign HMAC
    and any source ambiguity STOP. No rollback can be claimed detected solely
    by a mutable GitHub issue witness.
    """
    try:
        w=witness.verify()
        if type(key) is not bytes or len(key)<32:
            raise RecoveryTriageStop("Private signed HMAC fixture unavailable")
        original=cas._qty(original_qty)
        current_sha,doc=cas._read_source(
            current_source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=key)
        if (type(broker_lookup) is not dict
            or set(broker_lookup)!={"kind","order"}
            or broker_lookup["kind"] not in (BROKER_NOT_OBSERVED,BROKER_FOUND)):
            raise RecoveryTriageStop("Original deterministic client ID GET unqualified")
        kind=broker_lookup["kind"]
        order=broker_lookup["order"]
        if (kind==BROKER_NOT_OBSERVED and order is not None
            or kind==BROKER_FOUND and type(order) is not dict):
            raise RecoveryTriageStop("Original broker order observation contradictory")
        seq=doc["sequence"]
        if seq not in (0,1,2):
            raise RecoveryTriageStop("Unexpected original private sequence cannot release first ACWI")
        if seq==0:
            if first_proof is not None or prepost_proof is not None:
                raise RecoveryTriageStop("Seq0 must not carry later signed HEAD proofs")
            check=recovery.validate_sources(
                private_source=current_source,
                issue_comment=genesis_comment,
                public_comment_id=ORIGINAL_FIRST_COMMENT,
                bootstrap_run_id=ORIGINAL_GENESIS_RUN,
                hmac_hex=key.hex(),original_witness=w)
            if (check["private_ledger_sequence"]!=0
                or check["original_empty_entries_count"]!=0
                or doc["entries"]!={}):
                raise RecoveryTriageStop("Signed original genesis not empty")
            stage=("HOLD_INITIAL_NO_RESERVATION_NO_IMPLIED_ORDER_PERMISSION"
                   if kind==BROKER_NOT_OBSERVED else
                   "QUARANTINE_BROKER_ORDER_WITHOUT_SIGNED_LEDGER_ENTRY")
        elif seq==1:
            if type(first_proof) is not dict or prepost_proof is not None or set(first_proof)!={
                "first_comment","first_comment_id","first_run_id"}:
                raise RecoveryTriageStop("First signed HEAD/public audit proof incomplete")
            bound=once.check_initial_reserved(
                source=current_source,
                genesis_public_comment=genesis_comment,
                first_public_comment=first_proof["first_comment"],
                first_comment_id=first_proof["first_comment_id"],
                first_run_id=first_proof["first_run_id"],
                original_qty=original,key=key)
            if bound["source_sha"]!=current_sha:
                raise RecoveryTriageStop("Initial reservation source unexpectedly changed")
            stage=("HOLD_RESERVED_NO_RESTART_PREPOST_COMMIT"
                   if kind==BROKER_NOT_OBSERVED else
                   "QUARANTINE_BROKER_ORDER_WITH_ONLY_SIGNED_RESERVATION")
        else:
            if (type(first_proof) is not dict or set(first_proof)!={
                "first_comment","first_comment_id","first_run_id"}
                or type(prepost_proof) is not dict or set(prepost_proof)!={
                    "reserved_source","prepost_comment","prepost_comment_id","prepost_run_id"}):
                raise RecoveryTriageStop("Original seq2 requires both signed HEAD chains")
            sources=dict(
                reserved_source=prepost_proof["reserved_source"],
                prepost_source=current_source,
                genesis_comment=genesis_comment,
                first_comment=first_proof["first_comment"],
                prepost_comment=prepost_proof["prepost_comment"],
                first_comment_id=first_proof["first_comment_id"],
                first_run_id=first_proof["first_run_id"],
                prepost_comment_id=prepost_proof["prepost_comment_id"],
                prepost_run_id=prepost_proof["prepost_run_id"],
                original_qty=original,key=key)
            reviewed=locked.check_prepost_sources(**sources)
            if (reviewed["signed_private_sequence"]!=2
                or reviewed["first_symbol"]!=ORIGINAL
                or reviewed["live_order_authorized"] is not False):
                raise RecoveryTriageStop("Seq2 signed state cannot authorize a brokerage order")
            if kind==BROKER_NOT_OBSERVED:
                stage="HOLD_SIGNED_PREPOST_UNKNOWN_BROKER_POST_NO_RETRY"
            else:
                receipt=locked._validate_receipt(order,original_qty=original)
                if receipt.get("stage")=="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF":
                    stage="OBSERVED_FILLED_RECEIPT_HOLD_FOR_INDEPENDENT_FILL_AND_FLAT"
                elif receipt.get("stage")=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY":
                    stage="OBSERVED_EXISTING_ORDER_HOLD_NO_RETRY"
                else:
                    raise RecoveryTriageStop("Original broker receipt status is not supportable")
    except RecoveryTriageStop:
        raise
    except Exception:
        raise RecoveryTriageStop("Original signed restart or broker evidence invalid; HOLD") from None
    return {
        "schema":SCHEMA,
        "stage":stage,
        "original_first_legacy_symbol":ORIGINAL,
        "signed_private_sequence":seq,
        "signed_original_HMAC_and_public_HEAD_chain_verified":True,
        "broker_lookup_is_injected_not_live_proven":True,
        "client_ID_404_proves_no_earlier_POST":False,
        "prior_broker_order_found":kind==BROKER_FOUND,
        "broker_receipt_does_not_prove_flat_positions_or_settlement":True,
        "independent_external_immutable_antirollback_HEAD_proven":False,
        "fresh_order_time_risk_or_quote_proven":False,
        "cross_run_single_writer_ownership_proven":False,
        "new_live_original_ACWI_sell_permitted":False,
        "restart_resubmit_permitted":False,
        "source_mode":"SYNTHETIC_OR_INJECTED_OFFLINE_ONLY",
        "real_broker_GETs":0,"real_broker_POSTs":0,
        "real_private_Git_PUTs":0,"live_orders_submitted":0,
        "original_qty":None,"HMAC_key":None,"signed_private_head_SHA":None,
        "broker_account_id":None,"client_order_id":None,"order_payload":None,
    }

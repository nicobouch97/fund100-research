"""Single-process original V6 ACWI SELL coordinator entry, production HARD LOCKED.

This is NOT wired into any GitHub Actions workflow. Any future execution
requires BOTH a fresh independently signed broker-risk receipt and the old
scheduled-risk PASS, before reading private state or sending an order.
Even a user manually running this module cannot advance state while source release
is False. A future *separately reviewed and explicitly authorised* protected
main-only workflow will supply strictly segregated scopes and invoke this
exact function ONCE; uncertainty permanently holds, with no automatic retry.
"""
from __future__ import annotations

import os
import re

import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_live_risk_watch_admission_getonly_v1_0 as live_watch
import fund100_v6_s1_external_signed_risk_receipt_ingress_v1_0 as external_risk

SCHEMA="FUND100_V6_S1_FIRST_ACWI_ORIGINAL_EXECUTION_ENTRY_HARD_LOCKED_V1"
ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False
# Staged short-lived job public issuer (protected test was previously proven).
# This does NOT release an order: original entry, chain, private owner CAS,
# immutable signed publisher, active HIGH risk and broker writer remain locked.
SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED=True
RETRY_AFTER_UNCERTAIN_OUTCOME=False
MAX_CHAIN_INVOCATIONS=1
# GitHub Actions workflow identity is different from the dispatch actor.
# Only an independently reviewed, protected main-only execution workflow can
# invoke this entry after an eventual release. This target is NOT installed:
# the only currently deployed original first-ACWI workflow is GET ONLY.
EXPECTED_FIRST_ACWI_WORKFLOW_REF=(
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main"
)
# Launch-level funded HIGH mandate (NOT approval for each order).
# This one-shot entry handles only the FIRST ACWI inventory-migration sale;
# autonomous later trades use a separate event-driven production controller.
# Direct schedule on the pinned protected main workflow avoids relying on
# an unverified upstream workflow_dispatch initiator. GitHub's scheduled
# GITHUB_ACTOR is variable and NOT reliable execution provenance.
# Execution still requires source-code release, authenticated current-main V6
# operator GO, broker kill DISENGAGED, immutable signed head, and fresh risk.
REQUIRED_SECRETS=(
    "FUND100_PRIVATE_STATE_READ_TOKEN",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
    "ALPACA_LIVE_KEY",
    "ALPACA_LIVE_SECRET",
    "GITHUB_TOKEN",
    "FUND100_EXTERNAL_RISK_RECEIPT_READ_TOKEN",
)

class EntryStop(RuntimeError):
    """No retry following uncertain private CAS, release or broker response."""


def run_protected_first_acwi_once()->dict:
    """Original read->owner CAS->seq2->immutable release->single broker POST.

    Keeps the entire chain in one original GitHub workflow process. No
    user-supplied context, fake preapproval, dynamic URL or stage reentry.
    The input is the ONCE-only standing pilot activation, not per-order consent.
    The only present production outcome is HARD LOCKED with zero network.
    """
    if (ORIGINAL_ACWI_ENTRYPOINT_RELEASED is not True
        or chain.ONE_ATTEMPT_EXECUTION_RELEASED is not True
        or chain.RESTART_RECOVERY_CAN_RESEND is not False
        or chain.MAX_REAL_ORDER_SENDS!=1
        or MAX_CHAIN_INVOCATIONS!=1
        or RETRY_AFTER_UNCERTAIN_OUTCOME is not False):
        raise EntryStop("Original ACWI protected LIVE entry HARD LOCKED")
    e=os.environ
    if (e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_EVENT_NAME")!="schedule"
        or e.get("GITHUB_WORKFLOW_REF")!=EXPECTED_FIRST_ACWI_WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or type(e.get("GITHUB_RUN_ID")) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",e["GITHUB_RUN_ID"]) is None
        or type(e.get("GITHUB_SHA")) is not str
        or re.fullmatch(r"[0-9a-f]{40}",e["GITHUB_SHA"]) is None
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"
        or e.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"):
        raise EntryStop("Original ACWI protected first-run authorisation STOP")
    combined=(SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED is True)
    required=(tuple(k for k in REQUIRED_SECRETS
                    if k!="FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
              if combined else REQUIRED_SECRETS)
    if (any(type(e.get(name)) is not str or
            len(e[name].strip())<10 or
            e[name]!=e[name].strip() or
            "\r" in e[name] or "\n" in e[name]
            for name in required)
        or re.fullmatch(r"[0-9a-f]{64}",e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]) is None):
        raise EntryStop("Original signed first-run credential contract STOP")
    if combined and "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN" in e:
        raise EntryStop("Obsolete long-lived public publisher still injected; STOP")
    distinct=(
        e["FUND100_PRIVATE_STATE_READ_TOKEN"],
        e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        e["GITHUB_TOKEN"],
        e["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
    )
    if combined:
        if len(set(distinct))!=4:
            raise EntryStop("Original four distinct scoped principals unavailable")
    else:
        distinct=distinct+(e["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],)
        if len(set(distinct))!=5:
            raise EntryStop("Original first-run requires five independent GitHub principals")

    # Mandatory independent Ed25519 broker-risk evidence BEFORE signed source,
    # private CAS, immutable release or any broker POST. GitHub green status,
    # a healthy Railway page, or cached risk MUST NOT be a substitute.
    # No skip or fallback when the monitor is missing. Ingress and Ed25519
    # verifier both remain source-locked on the deployed main branch today.
    external_read_token=e["FUND100_EXTERNAL_RISK_RECEIPT_READ_TOKEN"]
    if external_read_token in set(distinct)|{
        e["ALPACA_LIVE_KEY"],e["ALPACA_LIVE_SECRET"],
        e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]
    }:
        raise EntryStop("External risk receipt read principal not isolated; STOP")
    try:
        signed_ok=external_risk.require_fresh_signed_external_risk_pass(
            main_sha=e["GITHUB_SHA"],readonly_token=external_read_token)
        if signed_ok is not True:
            raise EntryStop("Independent signed risk PASS invalid")
    except Exception:
        raise EntryStop("Fresh independent external signed broker-risk PASS missing; STOP") from None

    # Previously reviewed scheduled PASS is an ADDITIONAL, independent veto.
    # It can never replace the fresh signed risk evidence above.
    # Independent scheduled watcher must have actually inspected LIVE broker
    # risk and produced a fresh PASS-only GitHub job step. A workflow marked
    # successful while ALREADY_STOPPED does NOT satisfy this admission.
    # This veto is applied before reading signed original state, any owner
    # claim, immutable publish or broker POST; never lifts source hard locks.
    try:
        live_watch.require_recent_scheduled_risk_pass(
            token=e["GITHUB_TOKEN"],main_sha=e["GITHUB_SHA"])
    except Exception:
        raise EntryStop("Recent independent scheduled broker-risk PASS missing; STOP") from None

    # Do not log original signed bytes, quantity, public comment bodies,
    # account identifiers, owner nonce or secrets. This call does NO writes.
    try:
        original=chain.prepare_original_acwi_context_getonly(
            private_read_token=e["FUND100_PRIVATE_STATE_READ_TOKEN"],
            public_read_token=e["GITHUB_TOKEN"],
            hmac_hex=e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"],
            active_execution=True)
        if type(original) is not dict or set(original)!=chain.EXPECTED_CONTEXT:
            raise EntryStop("Original protected signed coordinator context absent")
        result=chain.run_exact_first_acwi_attempt(
            context=original,
            private_read_token=e["FUND100_PRIVATE_STATE_READ_TOKEN"],
            private_write_token=e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
            public_issue_write_token=e["GITHUB_TOKEN"],
            admin_read_token=e["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            public_release_write_token=(e["GITHUB_TOKEN"] if combined else
                                        e["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"]),
            broker_key=e["ALPACA_LIVE_KEY"],
            broker_secret=e["ALPACA_LIVE_SECRET"])
        if type(result) is dict and result.get("status")==(
                "ORIGINAL_ACWI_ECONOMIC_NO_TRADE_KEEP_HOLDINGS"):
            if (result.get("schema")!=chain.SCHEMA
                or type(result.get("original_owner_claim_attempts")) is not int
                or result.get("original_owner_claim_attempts")!=0
                or type(result.get("original_signed_possible_POST_attempts")) is not int
                or result.get("original_signed_possible_POST_attempts")!=0
                or type(result.get("immutable_release_publication_attempts")) is not int
                or result.get("immutable_release_publication_attempts")!=0
                or type(result.get("reviewed_broker_order_attempts")) is not int
                or result.get("reviewed_broker_order_attempts")!=0
                or result.get("broker_receipt_validation_proven") is not False
                or result.get("broker_receipt_stage") is not None
                or result.get("owner_fence_consumed") is not False
                or result.get("can_recheck_with_new_economic_evidence") is not True
                or result.get("independent_order_fill_and_settlement_verified") is not False
                or result.get("allow_restart_or_second_order") is not False):
                raise EntryStop("Original NO_TRADE contract inconsistent; STOP")
            return {
                "schema":SCHEMA,
                "status":"FIRST_ORIGINAL_ACWI_NO_TRADE_KEEP_HOLDINGS",
                "broker_send_attempts":0,
                "broker_receipt_stage":None,
                "broker_receipt_validation_proven":False,
                "independent_fill_and_settlement_verified":False,
                "original_owner_fence_consumed":False,
                "can_recheck_with_new_economic_evidence":True,
                "resubmission_permitted":False,
                "first_order_execution_source_released":False,
                "secret_or_private_source_in_report":None,
            }
        if (type(result) is not dict
            or result.get("status")!="ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY"
            or result.get("allow_restart_or_second_order") is not False
            or result.get("reviewed_broker_order_attempts")!=1
            or result.get("broker_receipt_validation_proven") is not True
            or result.get("broker_receipt_stage") not in chain.BROKER_RECEIPT_STAGES
            or result.get("independent_order_fill_and_settlement_verified") is not False):
            raise EntryStop("Original first order acknowledgement ambiguous; NEVER RETRY")
        return {
            "schema":SCHEMA,
            "status":"FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY",
            "broker_send_attempts":1,
            # A fixed post-ACK status is reportable, never private order data.
            # It is not independent fill/position/settlement verification.
            "broker_receipt_stage":result["broker_receipt_stage"],
            "broker_receipt_validation_proven":True,
            "independent_fill_and_settlement_verified":False,
            "resubmission_permitted":False,
            "first_order_execution_source_released":True,
            "secret_or_private_source_in_report":None,
        }
    except Exception:
        # Even if remote Git CAS, release or broker POST happened, any lost
        # acknowledgement is a terminal HOLD. No restart, no second send.
        raise EntryStop("Original first ACWI single attempt uncertain; NEVER RETRY") from None


def main()->None:
    outcome=run_protected_first_acwi_once()
    print(outcome["status"])
    print("Broker send attempts:",outcome["broker_send_attempts"])
    if outcome["status"]=="FIRST_ORIGINAL_ACWI_NO_TRADE_KEEP_HOLDINGS":
        print("Economic NO_TRADE: keep original ACWI; signed owner unclaimed.")
        print("Fresh future evidence can be rechecked; no order to retry.")
    else:
        print("Broker ACK category:",outcome["broker_receipt_stage"])
        print("No restart or resubmit; fills/settlement need independent review.")


if __name__=="__main__":
    main()

"""Single-process original V6 ACWI SELL coordinator entry, production HARD LOCKED.

This is NOT wired into any GitHub Actions workflow. The existing protected
read-only admission stays entirely unchanged. Even a user manually running
this module cannot advance signed state or send an order while source release
is False. A future *separately reviewed and explicitly authorised* protected
main-only workflow will supply strictly segregated scopes and invoke this
exact function ONCE; uncertainty permanently holds, with no automatic retry.
"""
from __future__ import annotations

import os
import re

import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain

SCHEMA="FUND100_V6_S1_FIRST_ACWI_ORIGINAL_EXECUTION_ENTRY_HARD_LOCKED_V1"
ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False
RETRY_AFTER_UNCERTAIN_OUTCOME=False
MAX_CHAIN_INVOCATIONS=1
MANUAL_CONFIRMATION="APPROVE_ONE_ORIGINAL_ACWI_SELL_NO_RETRY"
REQUIRED_SECRETS=(
    "FUND100_PRIVATE_STATE_READ_TOKEN",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
    "ALPACA_LIVE_KEY",
    "ALPACA_LIVE_SECRET",
    "GITHUB_TOKEN",
)

class EntryStop(RuntimeError):
    """No retry following uncertain private CAS, release or broker response."""


def run_protected_first_acwi_once()->dict:
    """Original read->owner CAS->seq2->immutable release->single broker POST.

    Keeps the entire chain in one original GitHub workflow process. No
    user-supplied context, fake preapproval, dynamic URL or stage reentry.
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
        or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or type(e.get("GITHUB_RUN_ID")) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",e["GITHUB_RUN_ID"]) is None
        or type(e.get("GITHUB_SHA")) is not str
        or re.fullmatch(r"[0-9a-f]{40}",e["GITHUB_SHA"]) is None
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"
        or e.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or e.get("FUND100_ORIGINAL_ACWI_FIRST_ORDER_CONFIRM")!=MANUAL_CONFIRMATION):
        raise EntryStop("Original ACWI protected first-run authorisation STOP")
    if (any(type(e.get(name)) is not str or
            len(e[name].strip())<10 or
            e[name]!=e[name].strip() or
            "\r" in e[name] or "\n" in e[name]
            for name in REQUIRED_SECRETS)
        or re.fullmatch(r"[0-9a-f]{64}",e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]) is None):
        raise EntryStop("Original signed first-run credential contract STOP")
    distinct=(
        e["FUND100_PRIVATE_STATE_READ_TOKEN"],
        e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        e["GITHUB_TOKEN"],
        e["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
        e["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
    )
    if len(set(distinct))!=5:
        raise EntryStop("Original first-run requires five independent GitHub principals")

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
            public_release_write_token=e["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
            broker_key=e["ALPACA_LIVE_KEY"],
            broker_secret=e["ALPACA_LIVE_SECRET"])
        if (type(result) is not dict
            or result.get("status")!="ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY"
            or result.get("allow_restart_or_second_order") is not False
            or result.get("reviewed_broker_order_attempts")!=1):
            raise EntryStop("Original first order acknowledgement ambiguous; NEVER RETRY")
        return {
            "schema":SCHEMA,
            "status":"FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY",
            "broker_send_attempts":1,
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
    print("No restart or resubmit; fills/settlement need independent review.")


if __name__=="__main__":
    main()

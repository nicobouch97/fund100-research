"""One-process first original XLK BUY pipeline; production HARD LOCKED.

This is the missing callable CLI between the existing authentic signed
ACWI post-sale 8-GET HIGH-risk source, the first-BUY signed private
genesis/seq1 CAS provisioner, and the independently hard-locked first
XLK seq2 CAS -> ONE Alpaca POST writer.

A protected funded BUY schedule is installed but DORMANT. This module does
not release any of its source/strategy/broker components or authorise trading. No dynamic
user/environment size input is accepted: the provisional first-entry
amount and worst-case cost are fixed and must be approved in code,
then requalified from current broker liquidity and 6/20/35 risk.
"""
from __future__ import annotations

import os
import re

import fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0 as reserve
import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope
import fund100_v6_s1_first_xlk_asof_opportunity_getonly_locked_v1_0 as opportunity

SCHEMA = "FUND100_V6_S1_FIRST_XLK_BUY_ORIGINAL_ONE_PROCESS_ENTRY_LOCKED_V1"
FIRST_XLK_BUY_ENTRY_RELEASED = False
RETRY_ON_AMBIGUOUS_CAS_OR_BROKER_RESULT = False
MAX_FUNDED_BUY_POSTS = 1
FIXED_FIRST_BUY_NOTIONAL_USD = "29.40"
FIXED_FIRST_BUY_WORST_CASE_COST_USD = "0.10"
EXPECTED_WORKFLOW_REF = scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF

REQUIRED_ENV = (
    "FUND100_PRIVATE_STATE_READ_TOKEN",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
    "GITHUB_TOKEN",
    "ALPACA_LIVE_KEY",
    "ALPACA_LIVE_SECRET",
)

class FirstBuyEntryStop(RuntimeError):
    pass

def _preflight() -> dict:
    """Fail without a private Git or broker network request on current main."""
    if (FIRST_XLK_BUY_ENTRY_RELEASED is not True
        or reserve.AUTORESERVE_RUNTIME_RELEASED is not True
        or writer.RUNTIME_RELEASED is not True
        or writer.BROKER_BUY_POST_RELEASED is not True
        or scope.FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is not True
        or opportunity.SOURCE_RELEASED is not True
        or RETRY_ON_AMBIGUOUS_CAS_OR_BROKER_RESULT is not False
        or MAX_FUNDED_BUY_POSTS != 1
        or EXPECTED_WORKFLOW_REF != writer.EXPECTED_REF):
        raise FirstBuyEntryStop("First XLK BUY original pipeline HARD LOCKED")
    writer._locked()
    e = os.environ
    if (e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF
        or e.get("GITHUB_EVENT_NAME") != "schedule"
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or e.get("FUND100_RISK_LEVEL") != "HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH") != "DISENGAGED"
        or e.get("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"):
        raise FirstBuyEntryStop("First BUY must be exact reviewed main schedule")
    for name in REQUIRED_ENV:
        value = e.get(name)
        if (type(value) is not str or len(value.strip()) < 10
            or value != value.strip() or "\r" in value or "\n" in value):
            raise FirstBuyEntryStop("First BUY required credential unavailable")
    if re.fullmatch(r"[0-9a-f]{64}",e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]) is None:
        raise FirstBuyEntryStop("First BUY HMAC key not canonical")
    writer._distinct(
        e["FUND100_PRIVATE_STATE_READ_TOKEN"],
        e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        e["GITHUB_TOKEN"],e["ALPACA_LIVE_KEY"],e["ALPACA_LIVE_SECRET"])
    if (FIXED_FIRST_BUY_NOTIONAL_USD != "29.40"
        or FIXED_FIRST_BUY_WORST_CASE_COST_USD != "0.10"):
        raise FirstBuyEntryStop("First BUY fixed amount requires fresh reviewed source")
    writer._op_go()
    return {name:e[name] for name in REQUIRED_ENV}

def execute_first_xlk_original_once() -> dict:
    """Only possible live path: source-authenticated reserve THEN one CAS/POST.

    Any reservation or writer ambiguity terminates without retry or second
    order. No supplied fake transports or invented account/risk flags.
    """
    e = _preflight()  # FIRST operation, locks deny all production I/O today.
    source_kwargs = {
        "private_read_token":e["FUND100_PRIVATE_STATE_READ_TOKEN"],
        "private_write_token":e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        "public_read_token":e["GITHUB_TOKEN"],
        "hmac_hex":e["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"],
        "broker_key":e["ALPACA_LIVE_KEY"],
        "broker_secret":e["ALPACA_LIVE_SECRET"],
    }
    args = dict(
        amount_usd=FIXED_FIRST_BUY_NOTIONAL_USD,
        cost_usd=FIXED_FIRST_BUY_WORST_CASE_COST_USD,
        private_read_token=source_kwargs["private_read_token"],
        private_write_token=source_kwargs["private_write_token"],
        public_read_token=source_kwargs["public_read_token"],
        broker_key=source_kwargs["broker_key"],
        broker_secret=source_kwargs["broker_secret"],
        hmac_key=bytes.fromhex(source_kwargs["hmac_hex"]),
        source_kwargs=source_kwargs,
    )
    try:
        # The infrastructure's fixed $29.40 is NOT investment alpha. A
        # new source-authenticated, previous-session, costed BUY/NO_BUY
        # decision must qualify the exact amount BEFORE irreversible BUY
        # private genesis/seq1 CAS. No market-data response from a caller
        # may bypass this: production inspect() always runs its own GETs.
        decision=opportunity.inspect(
            broker_key=e["ALPACA_LIVE_KEY"],
            broker_secret=e["ALPACA_LIVE_SECRET"],
            amount_usd=FIXED_FIRST_BUY_NOTIONAL_USD,
            cost_usd=FIXED_FIRST_BUY_WORST_CASE_COST_USD)
        if (type(decision) is not dict
            or decision.get("schema")!=opportunity.SCHEMA
            or decision.get("model")!=opportunity.MODEL
            or decision.get("decision") not in (
                "BUY_XLK_ASOF_AFTER_COST_HEURISTIC",
                "NO_BUY_UNQUALIFIED_COSTED_RELATIVE_STRENGTH")
            or decision.get("source_is_market_api_authenticated") is not True
            or decision.get("first_xlk_exact_amount_usd")!=FIXED_FIRST_BUY_NOTIONAL_USD
            or decision.get("first_xlk_exact_cost_usd")!=FIXED_FIRST_BUY_WORST_CASE_COST_USD
            or decision.get("all_source_sessions_identical") is not True
            or decision.get("observed_completed_sessions")!=opportunity.MIN_SESSIONS
            or type(decision.get("asof_source_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}",decision["asof_source_sha256"]) is None
            or decision.get("authenticated_market_data_GET_count")!=len(opportunity.SYMBOLS)
            or decision.get("alpha_or_forward_outperformance_proven") is not False
            or decision.get("live_buy_sell_authorized") is not False
            or decision.get("private_git_writes")!=0
            or decision.get("broker_orders_submitted")!=0):
            raise FirstBuyEntryStop("First XLK strategy unqualified as-of costed opportunity")
        if decision["decision"]=="NO_BUY_UNQUALIFIED_COSTED_RELATIVE_STRENGTH":
            # A valid absence of opportunity is an ordinary autonomous
            # decision. Never initialise first-buy private genesis/seq1,
            # attempt the broker POST, retry, or convert NO_BUY into a
            # failing GitHub Action alert.
            return {
                "schema":SCHEMA,
                "status":"FIRST_ORIGINAL_XLK_BUY_SKIPPED_VALID_NO_BUY",
                "first_buy_order_send_attempts":0,
                "fully_filled":False,
                "eligible_to_repeat":False,
                "further_trading_authorized":False,
                "private_state":None,
                "broker_account_or_credentials":None,
            }
        reservation=reserve.autoreserve(**args)
        if (type(reservation) is not dict
            or reservation.get("schema") != reserve.SCHEMA
            or reservation.get("status") not in (
                "FIRST_BUY_SIGNED_SEQ1_RESERVED_READY_FOR_SEPARATE_WRITER",
                "EXISTING_SIGNED_FIRST_BUY_RESERVED_NO_NEW_WRITE")
            or reservation.get("first_buy_private_state_sequence") != 1
            or reservation.get("buyer_post_authorized") is not False
            or reservation.get("broker_POSTs") != 0):
            raise FirstBuyEntryStop("First BUY signed reservation not qualified")
        outcome=writer.submit_one_original_xlk_buy(**args)
        if (type(outcome) is not dict
            or outcome.get("schema") != writer.SCHEMA
            or outcome.get("status") != "FIRST_XLK_BUY_POST_ATTEMPTED_NEVER_RETRY"
            or outcome.get("first_buy_order_submissions_in_this_process") != 1
            or outcome.get("repeat_allowed") is not False
            or outcome.get("actual_broker_fill_and_settlement_verified") is not False):
            raise FirstBuyEntryStop("First BUY submit outcome uncertain")
    except Exception:
        raise FirstBuyEntryStop(
            "First XLK BUY reservation/order uncertain: STOP, NEVER RETRY") from None
    return {
        "schema":SCHEMA,
        "status":"FIRST_ORIGINAL_XLK_BUY_SINGLE_POST_ATTEMPT_NO_RETRY",
        "first_buy_order_send_attempts":1,
        "fully_filled":False,
        "eligible_to_repeat":False,
        "further_trading_authorized":False,
        "private_state":None,
        "broker_account_or_credentials":None,
    }

def main() -> None:
    result=execute_first_xlk_original_once()
    print(result["status"])
    if result["first_buy_order_send_attempts"]==1:
        print("First XLK BUY is an irreversible one-shot attempt; reconcile fill separately.")
    else:
        print("Qualified NO_BUY: zero private BUY state writes and zero broker orders.")

if __name__=="__main__":
    main()

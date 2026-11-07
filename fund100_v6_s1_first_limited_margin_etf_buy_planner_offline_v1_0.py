"""Join existing PINNED staged migration + 1x ETF cash screen, OFFLINE only.

The original staged-controller Python blob is hash-pinned to protected LIVE
seven/eight-GET scopes; it MUST NOT be edited to add new research semantics.
This unpinned pure adapter instead consumes its existing default STOP result,
requires all original ACWI/EEM/XLV exit IDs filled/flat, independently checks
the *same synthetic* account/cash/fill observation, then invokes the current
1x limited-margin cash-screen function for one first hypothetical XLK BUY.

Not a broker/source adapter: caller fixtures are unauthenticated; no network,
secrets, live orders, private Git writes, cash settlement or trading release.
No fake substitution of unsettled buying power for "settled_cash_usd".
After one first XLK fill, another separately reconciled snapshot is required.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

import fund100_v6_s1_staged_controller_core_v1_0 as stage
import fund100_v6_s1_trading_api_post_sale_cash_screen_v1_0 as cashscreen

SCHEMA="FUND100_V6_S1_FIRST_1X_ETF_BUY_JOIN_OFFLINE_V1"
NO_BROKER_NETWORK=True
NO_BROKER_POST=True
NO_PRIVATE_STATE_WRITES=True
LIVE_BUY_RELEASED=False
FIRST_BUY="XLK"

class FirstBuyStop(ValueError):
    pass

def _hold(reason,*,notional=None):
    return {
        "schema":SCHEMA,"status":reason,
        "first_etf_candidate":None if notional is None else {
            "symbol":FIRST_BUY,"side":"buy",
            "simulated_client_order_id":stage.candidate_id(FIRST_BUY,"buy"),
            "estimated_notional_usd":format(notional,".2f"),
            "executable":False,
        },
        "original_first_acwi_or_other_sells_executable":False,
        "broker_source_authenticated":False,
        "original_signed_live_head_authenticated":False,
        "original_sell_fills_live_authenticated":False,
        "actual_settled_cash_verified":False,
        "limited_margin_equity_reinvestment_live_authorized":False,
        "live_buy_order_authorized":False,
        "broker_GETs":0,"broker_POSTs":0,"private_Git_writes":0,
        "private_account":None,"broker_receipts":None,
    }

def assess(*,staged_snapshot:dict,limited_margin_snapshot:dict,
           observed_at_utc:str)->dict:
    """One source-consistent hypothetical first BUY, never a LIVE order."""
    # This core validates all original signed order IDs, remaining legacy
    # positions, open orders, current 6/20/35 account stop and cash/NAV.
    # It is the *unchanged* source-hash-pinned pure controller.
    if type(staged_snapshot) is not dict:
        raise FirstBuyStop("Missing staged source-shaped inputs")
    try:
        prior=stage.assess(snap=staged_snapshot,now_utc=observed_at_utc)
    except Exception:
        return _hold("HOLD_ORIGINAL_STAGED_ACCOUNT_OR_RISK_SOURCE_INVALID")
    if (prior.get("stage")!="WAIT_ACTUAL_BROKER_SETTLEMENT_PROOF"
        or prior.get("candidate_instruction") is not None
        or prior.get("new_live_order_release") is not False
        or prior.get("broker_order_posts")!=0):
        return _hold("HOLD_THREE_LEGACY_EXITS_NOT_FULLY_RECONCILED")
    if staged_snapshot.get("independent_t_plus_one_settlement_proven") is not False:
        return _hold("HOLD_CONFLICTING_SETTLEMENT_PROOF_INPUT")
    if type(limited_margin_snapshot) is not dict:
        return _hold("HOLD_MISSING_LIMITED_MARGIN_ACCOUNT_SOURCE")

    try:
        positions=staged_snapshot["positions"]
        account=limited_margin_snapshot["account"]
        fills=limited_margin_snapshot["original_exit_fills"]
        orders=staged_snapshot["order_history"]
        assert type(positions) is dict and set(positions)=={"XLE"}
        assert type(limited_margin_snapshot["positions"]) is dict
        assert set(limited_margin_snapshot["positions"])=={"XLE"}
        assert type(account) is dict and type(fills) is dict
        assert type(orders) is dict and set(orders)=={
            stage.candidate_id(sym,"sell") for sym in stage.OLD}
        assert set(fills)==set(stage.OLD)
        assert limited_margin_snapshot["mode"]==cashscreen.MODE
        assert limited_margin_snapshot["source_authenticated_live"] is False
        assert limited_margin_snapshot["observed_at_utc"]==staged_snapshot["observed_at_utc"]
        assert limited_margin_snapshot["risk_level"]==staged_snapshot["risk_level"]
        assert limited_margin_snapshot["operator_stopped"] is staged_snapshot["operator_stopped"]
        assert limited_margin_snapshot["kill_switch"]==staged_snapshot["kill_switch"]
        for symbol in stage.OLD:
            record=orders[stage.candidate_id(symbol,"sell")]
            fill=fills[symbol]
            assert type(record) is dict and type(fill) is dict
            assert record["status"]==fill["status"]=="filled"
            assert fill["symbol"]==record["symbol"]==symbol
            assert fill["side"]=="sell"
            assert fill["client_order_id"]==stage.candidate_id(symbol,"sell")
            assert stage.amount(record["qty"],"original sold qty",positive=True)>0

        cash=stage.amount(staged_snapshot["cash_usd"],"cash")
        equity=stage.amount(staged_snapshot["equity_usd"],"account equity",positive=True)
        xle=stage.amount(positions["XLE"]["market_value_usd"],"XLE retained",positive=True)
        assert cashscreen._usd(account.get("cash"),"account cash")==cash
        assert cashscreen._usd(account.get("equity"),"account equity")==equity
        assert cashscreen._usd(limited_margin_snapshot["positions"]["XLE"],"XLE")==xle
        buying=cashscreen._usd(account.get("buying_power"),"buying power")
        nonmargin=cashscreen._usd(
            account.get("non_marginable_buying_power"),"nonmarginable buying power")
        assert cash+ xle==equity
        assert xle<=stage.TARGETS["XLE"]*min(equity,stage.CAP)
        fees=staged_snapshot["hypothetical_fee_buffers_usd"]
        assert type(fees) is dict and set(fees)==set(stage.BUYS)
        cost=stage.amount(fees[FIRST_BUY],"XLK first BUY all-in cost")
    except (AssertionError,KeyError,TypeError,ValueError):
        return _hold("HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH")

    nav=min(equity,stage.CAP)
    available=min(cash,buying,nonmargin)
    size=min(
        nav*stage.TARGETS[FIRST_BUY],
        stage.MAX_ORDER,
        stage.MAX_SYMBOL*equity,
        stage.MAX_GROSS*equity-xle,
        available-equity*stage.CASH_FLOOR-cost,
    )
    size=size.quantize(Decimal(".01"),rounding=ROUND_DOWN)
    if size<stage.MIN_ORDER:
        return _hold("HOLD_LIMITED_MARGIN_AVAILABLE_FUNDS_OR_FIVE_PCT_CASH_FLOOR")
    if cost>size*Decimal(".01"):
        return _hold("HOLD_FIRST_BUY_FEES_EXCEED_ONE_PCT")

    # Every risk/available-cash/1x/PDT/fill-history rule belongs to the
    # existing proven offline cash screen. Do NOT accept a caller-injected
    # boolean verdict, and do NOT reinterpret PASS as LIVE or settled.
    try:
        checked=cashscreen.screen(
            snapshot=limited_margin_snapshot,
            now_utc=observed_at_utc,
            buy_symbol=FIRST_BUY,
            buy_usd=format(size,".2f"),
            worst_case_all_in_cost_usd=str(cost),
            equity_reinvest_unsettled=True)
    except Exception:
        return _hold("HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED")
    if (checked.get("schema")!=cashscreen.SCHEMA
        or checked.get("status")!=
            "LIMITED_MARGIN_EQUITY_REINVESTMENT_ENVELOPE_PASSED_NOT_AUTHORIZED"
        or checked.get("one_x_limited_margin_equity_only_reinvestment_math_passed") is not True
        or checked.get("independent_broker_history_authenticated") is not False
        or checked.get("actual_settled_proceeds_certified") is not False
        or checked.get("unsettled_equity_reinvestment_live_permitted") is not False
        or checked.get("eligible_for_separate_approved_live_buy") is not False
        or checked.get("broker_requests")!=0
        or checked.get("broker_post_attempts")!=0):
        return _hold("HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED")
    return _hold("TEST_ONLY_FIRST_XLK_1X_ETF_REINVESTMENT_CANDIDATE_NO_TRANSPORT",
                 notional=size)

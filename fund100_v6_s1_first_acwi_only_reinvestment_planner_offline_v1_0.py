"""A smaller first useful ETF cycle: ACWI sell/FILL -> hypothetical XLK BUY.

The original S1 all-three-sales-first planner remains unchanged and
hash-pinned to real GET-only workflows. This parallel research adapter
tests whether a fully reconciled FIRST ORIGINAL ACWI SELL could be followed
by one SMALL XLK equity BUY while the original EEM, XLV and XLE stay held,
rather than artificially requiring three sales and leaving ACWI proceeds idle.

Inputs are invented source-shaped data, including a TEST-ONLY result from
the source-locked original postorder HMAC/immutable/broker joined reader.
No input authenticates an account, fills, risk, user GO or BUY permission.
No broker/private Git network, no order payload, no live release.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
import re

import fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 as original
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_independent_high_exante_policy_v1_0 as policy
import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as postorder

SCHEMA="FUND100_V6_S1_FIRST_ACWI_ONLY_REINVESTMENT_OFFLINE_V1"
MODE="INVENTED_FIRST_ACWI_FILL_ACCOUNT_FIXTURES_ONLY"
NO_NETWORK=True
NO_BROKER_POST=True
NO_PRIVATE_GIT_WRITE=True
LIVE_BUY_RELEASED=False
TARGET="XLK"
RETAIN=("EEM","XLV","XLE")

class PartialBuyStop(ValueError):
    pass

def _hold(reason,*,size=None):
    return {
        "schema":SCHEMA,"stage":reason,
        "candidate":None if size is None else {
            "symbol":"XLK","side":"buy",
            "fake_client_order_id":"SIM-v6s1-first-ACWI-only-XLK-no-order",
            "notional_usd":format(size,".2f"),
            "executable":False},
        "original_ACWI_fill_live_authenticated":False,
        "first_etf_buy_live_authorized":False,
        "second_legacy_sale_live_authorized":False,
        "original_unsettled_sale_proceeds_settled":False,
        "limited_margin_reinvestment_permission_proven":False,
        "broker_GETs":0,"broker_POSTs":0,"private_Git_PUTs":0,
        "private_account":None,"broker_order":None,"secrets":None,
    }

def _money(raw,label,*,positive=False):
    if (type(raw) is not str or not raw or raw.strip()!=raw
        or "e" in raw.lower()):
        raise PartialBuyStop("Invalid canonical "+label)
    try: n=Decimal(raw)
    except Exception: raise PartialBuyStop("Malformed "+label) from None
    if not n.is_finite() or n<0 or (positive and n==0) or n.as_tuple().exponent<-2:
        raise PartialBuyStop("Non-cent USD "+label)
    return n

def _utc(value):
    if type(value) is not str or not value.endswith("Z"):
        raise PartialBuyStop("Missing canonical time")
    try:
        d=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError:
        raise PartialBuyStop("Invalid UTC time") from None
    if d.utcoffset()!=timedelta(0):
        raise PartialBuyStop("Non-UTC time")
    return d

def assess(*,snapshot:dict,observed_at_utc:str)->dict:
    """One hypothetical ACWI-sale funded XLK buy; never a trade instruction."""
    if type(snapshot) is not dict:
        raise PartialBuyStop("Missing original in-memory account fixture")
    if (snapshot.get("mode")!=MODE
        or snapshot.get("source_authenticated_live") is not False
        or snapshot.get("operator_stopped") is not True
        or snapshot.get("kill_switch")!="ENGAGED"
        or snapshot.get("risk_level")!="HIGH"):
        return _hold("HOLD_NOT_LOCKED_OFFLINE_OR_HIGH")
    try:
        now=_utc(observed_at_utc)
        observed=_utc(snapshot["account_observed_at_utc"])
        if not 0<=(now-observed).total_seconds()<=300:
            return _hold("HOLD_STALE_ACCOUNT_OBSERVATION")
        proof=snapshot["first_acwi_postorder_source"]
        if (type(proof) is not dict
            or proof.get("schema")!=postorder.SCHEMA
            or proof.get("status")!=
                "TEST_ONLY_ORIGINAL_ACWI_ALL_POSTORDER_SOURCES_JOINED_NO_AUTHORITY"
            or proof.get("all_source_transports_explicitly_fake") is not True
            or proof.get("live_source_authenticated_by_this_run") is not False
            or proof.get("first_acwi_receipt_and_fill_flat_verified") is not True
            or proof.get("signed_seq2_and_owner1_current_two_principal_reget_verified") is not True
            or proof.get("provider_immutable_owner_and_seq2_asset_verified") is not True
            or proof.get("original_nonce_recreated") is not False
            or proof.get("broker_POSTs")!=0
            or proof.get("private_Git_PUTs")!=0
            or proof.get("original_ACWI_resubmission_permitted") is not False
            or proof.get("first_ETF_replacement_BUY_authorized") is not False):
            return _hold("HOLD_NO_ORIGINAL_ACWI_SIGNED_FILL_FLAT_MOCK_CHAIN")
        if (type(snapshot.get("original_deposit_count")) is not int
            or snapshot["original_deposit_count"]!=1
            or _money(snapshot["original_deposit_usd"],"deposit",positive=True)>policy.CAP
            or snapshot.get("all_order_pages_complete") is not True
            or snapshot.get("all_fill_pages_complete") is not True
            or snapshot.get("all_cashflow_pages_complete") is not True
            or type(snapshot.get("unreconciled_external_flows")) is not int
            or snapshot["unreconciled_external_flows"]!=0
            or type(snapshot.get("open_orders")) is not int
            or snapshot["open_orders"]!=0):
            return _hold("HOLD_UNPROVEN_OR_UNRECONCILED_PILOT_SOURCE")
        receipt=snapshot["first_original_acwi_fill"]
        expected=original._original_quantities()
        if (type(receipt) is not dict or receipt.get("symbol")!="ACWI"
            or receipt.get("side")!="sell"
            or receipt.get("status")!="filled"
            or receipt.get("client_order_id")!=cas.CLIENT_IDS["ACWI"]
            or receipt.get("filled_original_exact_qty")!=format(expected["ACWI"],"f")
            or receipt.get("complete_broker_fill_activities") is not True
            or receipt.get("post_acwi_flat") is not True
            or _utc(receipt["filled_at"])>observed):
            return _hold("HOLD_FIRST_ORIGINAL_ACWI_FULL_FILL_UNCONFIRMED")
        # EEM/XLV are explicitly STILL HELD. Only the first ACWI sale
        # has occurred, and every other original identity remains unchanged.
        pos=snapshot["positions"]
        if type(pos) is not dict or set(pos)!=set(RETAIN):
            return _hold("HOLD_RETAINED_ORIGINAL_THREE_INVENTORY_CHANGED")
        marks={}
        for symbol in RETAIN:
            row=pos[symbol]
            if (type(row) is not dict
                or row.get("qty")!=format(expected[symbol],"f")):
                return _hold("HOLD_RETAINED_ORIGINAL_THREE_INVENTORY_CHANGED")
            marks[symbol]=_money(row.get("market_value_usd"),symbol,positive=True)
        account=snapshot["account"]
        if (type(account) is not dict
            or account.get("status")!="ACTIVE"
            or account.get("account_blocked") is not False
            or account.get("trading_blocked") is not False
            or account.get("trade_suspended_by_user") is not False
            or account.get("pattern_day_trader") is not False
            or account.get("multiplier")!="1"):
            return _hold("HOLD_ACCOUNT_CLASS_OR_TRADE_RESTRICTIONS")
        for k in ("pending_transfer_in","pending_transfer_out"):
            if k in account and _money(account[k],k)!=0:
                return _hold("HOLD_PENDING_EXTERNAL_TRANSFER")
        cash=_money(account.get("cash"),"cash")
        equity=_money(account.get("equity"),"equity",positive=True)
        buying=_money(account.get("buying_power"),"buying power")
        nonmargin=_money(account.get("non_marginable_buying_power"),"nonmarginable BP")
        fees=_money(snapshot["worst_case_all_in_order_cost_usd"],"all-in execution fees")
        if (cash>equity or nonmargin>equity or buying<nonmargin
            or abs(cash+sum(marks.values())-equity)>max(
                Decimal(".02"),equity*Decimal(".002"))):
            return _hold("HOLD_ORIGINAL_ACCOUNT_CASH_OR_HOLDINGS_NOT_RECONCILED")
        risk=snapshot["HIGH_account_risk"]
        if type(risk) is not dict:
            return _hold("HOLD_MISSING_HIGH_RISK_SOURCE")
        daily=Decimal(str(risk.get("daily_return","nan")))
        drawdown=Decimal(str(risk.get("drawdown","nan")))
        vol=Decimal(str(risk.get("realized_annual_volatility","nan")))
        if (not all(x.is_finite() for x in (daily,drawdown,vol))
            or daily<=-policy.MAX_DAILY_LOSS
            or drawdown<=-policy.MAX_DRAWDOWN
            or vol>policy.MAX_ACTUAL_VOL
            or vol<0 or daily>1 or drawdown>0):
            return _hold("HOLD_HIGH_RISK_6_20_35_BREACHED_OR_UNKNOWN")
        if marks["XLE"]>policy.TARGET["XLE"]*equity:
            return _hold("HOLD_ORIGINAL_XLE_EXCEEDS_TARGET")
        # By requiring exact same snapshot and zero external funding
        # we only compute non-leveraged spare cash. 1x multiplier is NOT
        # settlement proof and can never become buy permission here.
        invested=sum(marks.values())
        available=min(cash,buying,nonmargin)
        target_room=policy.TARGET[TARGET]*min(equity,policy.CAP)
        symbol_room=policy.MAX_SYMBOL*equity
        gross_room=policy.MAX_GROSS*(equity-fees)-invested
        cash_room=available-equity*policy.CASH_FLOOR-fees
        size=min(policy.MAX_ORDER,target_room,symbol_room,gross_room,cash_room)
        size=size.quantize(Decimal(".01"),rounding=ROUND_DOWN)
        if size<policy.MIN_BUY or size<=0:
            return _hold("HOLD_FIRST_ACWI_CASH_CANNOT_SUPPORT_NEW_BUY_AND_FIVE_PCT_RESERVE")
        if fees>size*Decimal(".01"):
            return _hold("HOLD_EXCESS_FIRST_BUY_EXECUTION_COST")
    except (KeyError,TypeError,ValueError,ArithmeticError):
        return _hold("HOLD_ORIGINAL_ACCOUNT_OR_RISK_SOURCE_MALFORMED")
    return _hold("FAKE_FIRST_ACWI_ONLY_XLK_REINVESTMENT_MATH_PASSED_NO_ORDER",
                 size=size)

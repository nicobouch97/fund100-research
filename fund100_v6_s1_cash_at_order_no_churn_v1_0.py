"""S1 source-pinned 5% cash-at-order research diagnostic, NEVER a LIVE permit.

Historical S1 95%-invested target drifted below 5% cash over 2,792
sessions. A continuous 5% floor CANNOT be claimed under monthly 10pp
rebalancing; this module tests an alternative *at-order* cash screen
with pause-on-drift (NO automatic forced sell) for future policy review.

Caller-provided account figures and fee buffers are NOT independently
authenticated, not broker cash-settlement evidence or executable intents.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as s1

SCHEMA="FUND100_V6_S1_BROKERLESS_CASH_AT_ORDER_NO_CHURN_V1"
CAP=Decimal("130.30")
TARGET_GROSS=Decimal("0.95")
MIN_CASH=Decimal("0.05")
MAX_SYMBOL=Decimal("0.50")
BUY_MIN=Decimal("1.00")
BUY_MAX=Decimal("65.00")
MAX_SOURCE_AGE=300
S1_ETFS=frozenset(("XLK","XLE","IWM"))

class CashStop(ValueError): pass

def decimal(v,label,*,allow_zero=True):
    if type(v) not in (str,int,Decimal):
        raise CashStop(label+" is not strict USD numeric")
    try: n=Decimal(str(v))
    except (InvalidOperation,ValueError) as exc:raise CashStop(label+" is invalid") from exc
    if not n.is_finite() or n<0 or (not allow_zero and n==0):
        raise CashStop(label+" non-finite or outside range")
    return n

def utc(value):
    if not isinstance(value,str): raise CashStop("Missing source clock")
    try: d=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:raise CashStop("Noncanonical UTC clock") from exc
    if d.strftime("%Y-%m-%dT%H:%M:%SZ")!=value:raise CashStop("Unexpected timestamp")
    return d

def check(*, snapshot:dict, now_utc:str, hypothetical_new_buy_usd:str|None=None,
          hypothetical_worst_case_total_cost_usd:str|None=None)->dict:
    original=s1.source_controls()
    if (original.get("status")!="PROPOSED_NOT_LIVE"
        or original.get("target_weights")!={"XLK":"0.475","XLE":"0.285","IWM":"0.190"}
        or original.get("cash_reserve_fraction")!="0.05"
        or original.get("maximum_gross_exposure")!="0.95"
        or original.get("original_trial_max_capital_usd")!="130.30"
        or original.get("live_order_execution_released") is not False
        or original.get("live_operator_trading_enabled") is not False
        or original.get("live_environment_kill_switch")!="ENGAGED"):
        raise CashStop("Original S1 research-only control or active STOP altered")
    if not isinstance(snapshot,dict):
        raise CashStop("No signed, live-broker observation available")
    if (snapshot.get("source")!="UNVERIFIED_CALLER_ASSERTED_GET_ONLY"
        or snapshot.get("trading_enabled") is not False
        or snapshot.get("broker_kill_switch")!="ENGAGED"):
        raise CashStop("Research fixture cannot claim LIVE permission")
    age=(utc(now_utc)-utc(snapshot.get("observed_at_utc"))).total_seconds()
    if not 0<=age<=MAX_SOURCE_AGE:raise CashStop("Stale or future account observation")
    if snapshot.get("open_orders") is not None and type(snapshot["open_orders"]) is not int:
        raise CashStop("Invalid open order count")
    open_orders=snapshot.get("open_orders")
    if open_orders is None or open_orders<0:
        raise CashStop("Open orders state unknown")
    equity=decimal(snapshot.get("equity_usd"),"equity",allow_zero=False)
    cash=decimal(snapshot.get("cash_usd"),"account cash")
    settled=decimal(snapshot.get("settled_cash_usd"),"settled cash")
    if cash>equity or settled>cash:
        raise CashStop("Unreconciled account cash/equity values")
    positions=snapshot.get("positions_market_value_usd")
    if not isinstance(positions,dict) or len(positions)>20:
        raise CashStop("Missing all-positions mark set")
    marks={}
    for symbol,value in positions.items():
        if not isinstance(symbol,str) or not symbol or symbol in marks:
            raise CashStop("Invalid position identity")
        marks[symbol]=decimal(value,"symbol marked USD",allow_zero=False)
    if abs(sum(marks.values(),Decimal(0))+cash-equity)>Decimal("0.02"):
        raise CashStop("Incompatible marked equity/cash observation")
    other=set(marks)-S1_ETFS
    gross=sum(marks.values(),Decimal(0))
    frac=gross/equity
    available_fraction=cash/equity
    reasons=[]
    if other:reasons.append("LEGACY_OR_OUT_OF_UNIVERSE_POSITIONS")
    if open_orders:reasons.append("BROKER_OPEN_ORDERS")
    if available_fraction<MIN_CASH:reasons.append("FIVE_PERCENT_CASH_FRACTION_DRIFT")
    if frac>TARGET_GROSS:reasons.append("NINETY_FIVE_PERCENT_GROSS_FRACTION_DRIFT")
    if any(value/equity>MAX_SYMBOL for value in marks.values()):
        reasons.append("SYMBOL_50_PERCENT_MAX_EXCEEDED")
    # Legacy or drift has NO forced rebalance / NO autonomous sale here.
    stage=("NO_NEW_BUYS_HOLD_AND_RECONCILE" if reasons else
           "CASH_FRACTION_CURRENTLY_ABOVE_FLOOR_NO_ACTION")
    hypothetical_screen=None
    if hypothetical_new_buy_usd is not None or hypothetical_worst_case_total_cost_usd is not None:
        if hypothetical_new_buy_usd is None or hypothetical_worst_case_total_cost_usd is None:
            raise CashStop("Both hypothetical buy and conservative ALL-IN cost required")
        buy=decimal(hypothetical_new_buy_usd,"hypothetical notional",allow_zero=False)
        friction=decimal(hypothetical_worst_case_total_cost_usd,"all-in execution cost")
        if buy<BUY_MIN or buy>BUY_MAX or (buy*100)%1!=0 or (friction*100)%1!=0:
            raise CashStop("Only $1-$65 cent-precision notional/cost research examples")
        if not reasons:
            remaining=settled-buy-friction
            # Cash floor tested against pre-spend NAV (conservative for
            # friction), and mark-to-market gross exposure after purchase.
            if remaining<equity*MIN_CASH:
                stage="BLOCK_HYPOTHETICAL_BUY_RESERVED_CASH"
            elif equity<=friction or (gross+buy)/(equity-friction)>TARGET_GROSS:
                stage="BLOCK_HYPOTHETICAL_BUY_GROSS_EXPOSURE"
            elif gross+buy>CAP:
                # CAUTION: Market values do not prove cumulative cost basis.
                # This is an extra conservative mark-based screen only.
                stage="BLOCK_HYPOTHETICAL_BUY_ORIGINAL_CAP"
            else:
                stage="HYPOTHETICAL_BUY_SCREEN_CLEARED_NOT_AUTHORIZED"
        hypothetical_screen="MATHEMATICAL_ONLY_NEVER_BROKER_AUTHORITY"
    return {
        "schema":SCHEMA,
        "status":stage,
        "explanatory_reasons":reasons,
        "cash_is_below_five_percent_of_current_nav":available_fraction<MIN_CASH,
        "exposure_is_above_ninety_five_percent_of_current_nav":frac>TARGET_GROSS,
        "proposed_rule":"FIVE_PERCENT_MINIMUM_ONLY_AT_EACH_NEW_BUY_SCREEN_NOT_CONTINUOUS_GUARANTEE",
        "original_manifest_unchanged":True,
        "historical_daily_cash_floor_fulfilled":False,
        "daily_drift_causes_auto_sales":False,
        "new_buys_pause_on_daily_floor_drift":True,
        "requires_new_versioned_live_risk_policy":True,
        "hypothetical_screen":hypothetical_screen,
        "caller_snapshot_independently_authenticated":False,
        "actual_settled_cash_independently_verified":False,
        "all_in_cost_model_independently_verified":False,
        "risk_stop_inputs_complete":False,
        "paper_fill_verified_by_module":False,
        "new_live_buy_authorized":False,
        "new_live_sale_authorized":False,
        "new_orders":0,
        "broker_requests":0,
        "executable_order_payload":None,
    }

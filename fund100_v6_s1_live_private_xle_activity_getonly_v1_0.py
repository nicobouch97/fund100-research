"""V6-S1 PRIVATE original Alpaca LIVE sixth-GET source, never an order writer.

Reuse the original five-GET risk evidence in memory. Add one specific
account-activities READ to classify historical external funding and
original XLE weight. Privacy-safe labels only; NEVER persist broker data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_live_risk_history_getonly_v1_0 as five

SCHEMA="FUND100_V6_S1_PRIVATE_LIVE_XLE_ACTIVITY_SOURCE_V1"
ACTIVITIES_PATH="/v2/account/activities"
ACTIVITY_PARAMS={"category":"non_trade_activity","after":"2026-09-01",
                 "direction":"asc","page_size":100}
PATHS=five.PATHS+(ACTIVITIES_PATH,)
CAP=Decimal("130.30")
XLE_TARGET=Decimal("0.285")
CASH_ORDER_FLOOR=Decimal("0.05")
TRANSFER_TYPES=frozenset({"CSD","CSW","ACATC","ACATS","JNL","JNLC",
                          "JNLS","TRANS"})
KNOWN_OTHER_NONTRADE_TYPES=frozenset({"DIV","DIVCGL","DIVCGS","DIVFEE",
    "DIVFT","DIVNRA","DIVROC","DIVTW","DIVTXEX","FEE","CFEE","INT",
    "INTNRA","INTTW","MISC","PTC","PTR","MA","NC","REORG","SC","SSO","SSP"})
SOURCE_CLASS="PRIVATE_OBSERVATION_ONLY_NOT_SPENDABLE_T_PLUS_ONE_CASH"

class PrivateActivityStop(RuntimeError):pass


def evaluate(*,account:dict,positions:list,orders:list,clock:dict,
             history:dict,activities:list,bootstrap:dict,policy:dict,
             control:dict,remotely_stopped:bool,kill_switch:str,
             risk_level:str,observed_at_utc:str)->dict:
    """No portfolio values leave this call; reason labels are strictly finite."""
    try:
        core=five.review(
            account=account,positions=positions,orders=orders,clock=clock,
            history=history,bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except Exception:
        raise PrivateActivityStop("Original five-GET account/history source failed") from None
    if (core["broker_get_requests"]!=5 or core["live_orders_submitted"]!=0
        or core["broker_open_order_count"]!=0
        or core["live_v6_buy_or_sale_authorized"] is not False):
        raise PrivateActivityStop("Original read-only controls drifted")
    try:
        cash=four._clean_decimal(account.get("cash"),"live cash",zero=True)
        nav=four._clean_decimal(account.get("equity"),"live equity")
        overlap=[p for p in positions if p.get("symbol")=="XLE"]
        if len(overlap)!=1:
            raise PrivateActivityStop("Missing original XLE position")
        val=four._clean_decimal(overlap[0].get("market_value"),"XLE value")
        original_xle_status=("XLE_BELOW_OR_AT_DRAFT_TARGET"
            if val<=min(nav,CAP)*XLE_TARGET
            else "XLE_ABOVE_DRAFT_TARGET_REVIEW")
        cash_status=("CURRENT_CASH_BELOW_BUY_TIME_FLOOR"
            if cash<nav*CASH_ORDER_FLOOR
            else "CURRENT_CASH_AT_OR_ABOVE_BUY_TIME_FLOOR_NO_SETTLEMENT_PROOF")
    except (four.ReadinessStop,ValueError,TypeError) as exc:
        raise PrivateActivityStop("XLE/cash private exposure source unreadable") from None
    if type(activities) is not list or len(activities)>100:
        raise PrivateActivityStop("Account activities pagination invalid")
    unknown=False; external=False; seen=set()
    for row in activities:
        if not isinstance(row,dict):
            raise PrivateActivityStop("Malformed private account activity")
        t=row.get("activity_type")
        if type(t) is not str or not t or t!=t.strip() or not t.isupper():
            raise PrivateActivityStop("Missing original brokerage activity classification")
        if t not in TRANSFER_TYPES and t not in KNOWN_OTHER_NONTRADE_TYPES:
            unknown=True
        if t in TRANSFER_TYPES:external=True
        activity_id=row.get("id")
        if type(activity_id) is not str or not activity_id:
            raise PrivateActivityStop("Account activity missing unique source identifier")
        if activity_id in seen:
            raise PrivateActivityStop("Duplicated activity in paginated source")
        seen.add(activity_id)
    if len(activities)==100:
        flow="ACTIVITIES_PAGINATION_INCOMPLETE"
    elif unknown:
        flow="UNKNOWN_NONTRADE_TYPE_REVIEW"
    elif external:
        flow="EXTERNAL_TRANSFER_TYPES_SEEN_REQUIRES_CASHFLOW_ADJUSTMENT"
    else:
        flow="NO_EXTERNAL_TRANSFER_TYPES_SEEN_IN_OBSERVED_WINDOW"
    return {
        "schema":SCHEMA,"source_class":SOURCE_CLASS,
        "source_original_account_bound":True,
        "source_original_four_holdings_reconciled":True,
        "source_original_open_orders":0,
        "current_original_xle_target_status":original_xle_status,
        "current_original_cash_floor_status":cash_status,
        "account_activities_source_status":flow,
        "activities_fully_paginated":len(activities)<100,
        "external_transfers_absent_proven_for_all_account_history":False,
        "flow_adjusted_strategy_daily_returns_verified":False,
        "original_raw_risk_history_result":core["raw_broker_portfolio_history_result"],
        "original_raw_risk_guard_passed":core["raw_broker_portfolio_history_guard_passed"],
        "actual_settled_sale_cash_verified":False,
        "current_live_v6_controller_risk_ready":False,
        "live_trade_permitted":False,
        "broker_get_requests":6,"broker_non_get_requests":0,"broker_orders":0,
        "account_id":None,"current_nav_usd":None,"actual_cash_usd":None,
        "xle_value_usd":None,"activity_ids":None,"activity_cash_amounts":None,
        "order_payload":None,
    }


def runtime()->dict:
    if (os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise PrivateActivityStop("Original LIVE main/HIGH/kill must be stopped")
    boots,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise PrivateActivityStop("Source operator not STOPPED")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def fetch(path,params=None):
        if path not in PATHS:
            raise PrivateActivityStop("Outside original six GET endpoints")
        if path==ACTIVITIES_PATH:
            if params!=ACTIVITY_PARAMS:raise PrivateActivityStop("Changed cashflows query")
        elif path==five.HISTORY_PATH:
            if params!=five.HISTORY_PARAMS:raise PrivateActivityStop("Changed history query")
        elif path=="/v2/orders":
            if params!={"status":"open","limit":100}:
                raise PrivateActivityStop("Changed open-order query")
        elif params is not None:
            raise PrivateActivityStop("Extra GET query is forbidden")
        calls.append(path)
        try:
            return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise PrivateActivityStop("Original Alpaca LIVE GET failed; private details withheld") from None
    account=fetch("/v2/account")
    positions=fetch("/v2/positions")
    orders=fetch("/v2/orders",{"status":"open","limit":100})
    clock=fetch("/v2/clock")
    history=fetch(five.HISTORY_PATH,five.HISTORY_PARAMS)
    activities=fetch(ACTIVITIES_PATH,ACTIVITY_PARAMS)
    if tuple(calls)!=PATHS:
        raise PrivateActivityStop("Expected exactly original six GET calls")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise PrivateActivityStop("Main operator stopped state changed during original read")
    return evaluate(
        account=account,positions=positions,orders=orders,clock=clock,
        history=history,activities=activities,bootstrap=boots,policy=policy,
        control=control,remotely_stopped=True,kill_switch="ENGAGED",
        risk_level="HIGH",observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def main():
    r=runtime()
    for name in ("schema","source_original_account_bound",
                 "source_original_four_holdings_reconciled",
                 "source_original_open_orders",
                 "current_original_xle_target_status",
                 "current_original_cash_floor_status",
                 "account_activities_source_status",
                 "activities_fully_paginated",
                 "original_raw_risk_history_result",
                 "flow_adjusted_strategy_daily_returns_verified",
                 "actual_settled_sale_cash_verified",
                 "live_trade_permitted","broker_get_requests","broker_orders"):
        print(name+":",r[name])
    print("Account, XLE values, cash, activity amounts/IDs, order IDs: NEVER PRINTED")


if __name__=="__main__":
    main()

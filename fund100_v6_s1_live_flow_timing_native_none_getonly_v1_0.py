"""V6-S1 private original Alpaca seven-GET cash-flow source-qualification only.

No money values, activity IDs or returns leave this module. Original six
read-only endpoints verified in unchanged reviewed modules; a seventh GET
compares the *shape* of Alpaca's cashflow_types=NONE profit series.
No real-money writer, return adapter, settlement cert or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_live_risk_history_getonly_v1_0 as five
import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as six

SCHEMA="FUND100_V6_S1_AUTHENTIC_CASHFLOW_TIMING_AND_NATIVE_NONE_SOURCE_V1"
EXTRA_PARAMS={"period":"1M","timeframe":"1D","cashflow_types":"NONE"}
PATHS=six.PATHS+(five.HISTORY_PATH,)

class FlowTimingStop(RuntimeError):pass


def decimal(raw)->Decimal:
    if raw is None or type(raw) is bool or type(raw) not in (int,float,str,Decimal):
        raise FlowTimingStop("Missing or malformed account activity decimal")
    try:v=Decimal(str(raw))
    except (InvalidOperation,ValueError) as exc:
        raise FlowTimingStop("Malformed account activity decimal") from None
    if not v.is_finite():raise FlowTimingStop("Nonfinite private activity decimal")
    return v


def original_cashflow_source(activities:list)->str:
    """PRIVATE signed CASH eligibility; no customer values in results."""
    if type(activities) is not list or len(activities)>100:
        raise FlowTimingStop("Original activity source cannot be trusted")
    if len(activities)==100:
        return "PAGINATION_INCOMPLETE"
    found_cash=False;missing_time=False;unsupported=False
    for row in activities:
        if type(row) is not dict:
            raise FlowTimingStop("Invalid activity source item")
        t=row.get("activity_type")
        if type(t) is not str:
            raise FlowTimingStop("Invalid private activity type")
        if t in ("CSD","CSW"):
            found_cash=True
            try:cash=decimal(row.get("net_amount"))
            except FlowTimingStop:
                return "CASH_AMOUNT_SOURCE_INVALID"
            if (t=="CSD" and cash<=0) or (t=="CSW" and cash>=0):
                return "CASH_AMOUNT_SOURCE_INVALID"
            value=row.get("transaction_time")
            if type(value) is not str:
                missing_time=True
            else:
                try:
                    x=datetime.fromisoformat(value.replace("Z","+00:00"))
                except ValueError:
                    missing_time=True
                else:
                    if x.tzinfo is None or x.utcoffset() is None:
                        missing_time=True
        elif t in six.TRANSFER_TYPES or t not in six.KNOWN_OTHER_NONTRADE_TYPES:
            unsupported=True
    # Do not let a date-only CSD conceal a noncash asset journal.
    if unsupported:return "NONCASH_OR_UNKNOWN_TRANSFER_REQUIRES_VALUATION_REVIEW"
    if found_cash and missing_time:
        return "CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ"
    if found_cash:
        return "CASH_TRANSFER_AMOUNT_AND_TRANSACTION_TIME_FIELDS_PRESENT_UNRECONCILED"
    return "NO_EXTERNAL_TRANSFER_DETECTED_IN_WINDOW"



def observed_cash_transfer_category(activities:list,source_status:str)->str:
    """Only zero/one/multiple observed transfer category, never account data.

    This is the fixed nontrade query's observed page since 2026-09-01.
    A unique observed cash transfer is NOT proven to be the only one in the
    complete LIVE account lifetime or in the 1M equity window.
    """
    if (type(activities) is not list or len(activities)>=100
        or source_status=="PAGINATION_INCOMPLETE"):
        return "OBSERVED_FUNDING_PAGE_INCOMPLETE_HOLD"
    if source_status in (
        "CASH_AMOUNT_SOURCE_INVALID",
        "NONCASH_OR_UNKNOWN_TRANSFER_REQUIRES_VALUATION_REVIEW",
    ):
        return "OBSERVED_FUNDING_TYPE_OR_AMOUNT_UNTRUSTED_HOLD"
    if source_status not in (
        "CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ",
        "CASH_TRANSFER_AMOUNT_AND_TRANSACTION_TIME_FIELDS_PRESENT_UNRECONCILED",
        "NO_EXTERNAL_TRANSFER_DETECTED_IN_WINDOW",
    ):
        return "OBSERVED_FUNDING_UNKNOWN_SOURCE_HOLD"
    cash=0
    for row in activities:
        if type(row) is not dict:
            return "OBSERVED_FUNDING_UNKNOWN_SOURCE_HOLD"
        kind=row.get("activity_type")
        if kind in ("CSD","CSW"):
            cash+=1
        elif kind in six.TRANSFER_TYPES or kind not in six.KNOWN_OTHER_NONTRADE_TYPES:
            return "OBSERVED_FUNDING_TYPE_OR_AMOUNT_UNTRUSTED_HOLD"
    if cash==0:
        return "OBSERVED_ZERO_CASH_TRANSFERS_NOT_LIFETIME_PROOF"
    if cash==1:
        return "OBSERVED_ONE_CASH_TRANSFER_NOT_TIMING_PROOF"
    return "OBSERVED_MULTIPLE_CASH_TRANSFERS_SINGLE_FLOW_MODEL_INAPPLICABLE"



def broker_native_none_source(original_history:dict,none_history:dict)->str:
    """Compare source semantics without leaking equities or asserting cash flow adjustment."""
    if not isinstance(original_history,dict) or not isinstance(none_history,dict):
        raise FlowTimingStop("Broker history expected two objects")
    if (original_history.get("timeframe")!="1D"
        or none_history.get("timeframe")!="1D"):
        raise FlowTimingStop("Original 1D observation cadence changed")
    stamps=original_history.get("timestamp")
    other=none_history.get("timestamp")
    if (type(stamps) is not list or len(stamps)<6
        or type(other) is not list or stamps!=other
        or any(type(t) is not int for t in stamps)):
        return "BROKER_NATIVE_NONE_TIME_SERIES_NOT_COMPARABLE"
    a=original_history.get("profit_loss_pct")
    b=none_history.get("profit_loss_pct")
    if (type(a) is not list or type(b) is not list
        or len(a)!=len(stamps) or len(b)!=len(stamps)):
        return "BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE"
    if any(x is None or y is None for x,y in zip(a,b)):
        return "BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE"
    try:
        left=[decimal(x) for x in a]
        right=[decimal(y) for y in b]
    except FlowTimingStop:
        return "BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE"
    return ("BROKER_NATIVE_NONE_PNL_SERIES_DIFFERS"
            if left!=right else "BROKER_NATIVE_NONE_PNL_SERIES_SAME")


def evaluate(*,account:dict,positions:list,orders:list,clock:dict,
             history:dict,activities:list,native_none_history:dict,
             bootstrap:dict,policy:dict,control:dict,
             remotely_stopped:bool,kill_switch:str,risk_level:str,
             observed_at_utc:str)->dict:
    try:
        earlier=six.evaluate(
            account=account,positions=positions,orders=orders,clock=clock,
            history=history,activities=activities,bootstrap=bootstrap,
            policy=policy,control=control,remotely_stopped=remotely_stopped,
            kill_switch=kill_switch,risk_level=risk_level,
            observed_at_utc=observed_at_utc)
    except Exception:
        raise FlowTimingStop("Original account, funding and risk verifier failed") from None
    if (earlier.get("broker_get_requests")!=6 or earlier.get("broker_orders")!=0
        or earlier.get("live_trade_permitted") is not False):
        raise FlowTimingStop("Previous original six read-only checks changed")
    timing=original_cashflow_source(activities)
    count_category=observed_cash_transfer_category(activities,timing)
    none=broker_native_none_source(history,native_none_history)
    return {
       "schema":SCHEMA,
       "source":"PRIVATE_ORIGINAL_SEVEN_GET_SOURCE_QUALIFICATION_ONLY",
       "original_account_and_legacy_positions_verified":True,
       "original_xle_target_status":earlier["current_original_xle_target_status"],
       "original_cash_floor_status":earlier["current_original_cash_floor_status"],
       "original_external_funding_classification":earlier["account_activities_source_status"],
       "cash_transfer_amount_and_timestamp_field_status":timing,
       "observed_cash_transfer_count_class":count_category,
       "broker_cashflow_types_none_pnl_comparison":none,
       "original_raw_equity_risk_status":earlier["original_raw_risk_history_result"],
       "actual_cashflow_adjusted_dietz_returns_calculated":False,
       "broker_native_none_is_validated_true_strategy_return":False,
       "actual_s1_6_20_35_risk_verified":False,
       "actual_sale_proceeds_t_plus_one_settled":False,
       "live_buy_sell_authorized":False,
       "broker_get_requests":7,"broker_non_get_requests":0,"live_orders":0,
       "private_account_id":None,"private_cash_usd":None,
       "private_activity_ids_dates_amounts":None,
       "private_pnl_series":None,"broker_order_payload":None,
    }


def runtime()->dict:
    if (os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise FlowTimingStop("Cannot read brokerage outside reviewed stopped main")
    bootstrap,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise FlowTimingStop("Account not original stopped LIVE pilot")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    called=[]
    def fetch(path,params=None):
        if path not in PATHS:
            raise FlowTimingStop("Unapproved Alpaca endpoint")
        if path=="/v2/orders":
            if params!={"status":"open","limit":100}:
                raise FlowTimingStop("Unexpected order query")
        elif path==five.HISTORY_PATH:
            if params not in (five.HISTORY_PARAMS,EXTRA_PARAMS):
                raise FlowTimingStop("Unapproved portfolio history request")
            if params==EXTRA_PARAMS and called!=list(six.PATHS):
                raise FlowTimingStop("Native cashflow NONE source out of approved order")
        elif path==six.ACTIVITIES_PATH:
            if params!=six.ACTIVITY_PARAMS:
                raise FlowTimingStop("Unapproved nontrade scan")
        elif params is not None:
            raise FlowTimingStop("Unapproved query parameters")
        called.append(path)
        try:return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise FlowTimingStop("Private original broker GET failed") from None
    account=fetch("/v2/account")
    positions=fetch("/v2/positions")
    orders=fetch("/v2/orders",{"status":"open","limit":100})
    clock=fetch("/v2/clock")
    history=fetch(five.HISTORY_PATH,five.HISTORY_PARAMS)
    activities=fetch(six.ACTIVITIES_PATH,six.ACTIVITY_PARAMS)
    none=fetch(five.HISTORY_PATH,EXTRA_PARAMS)
    if tuple(called)!=PATHS:
        raise FlowTimingStop("Original seven GET order not exact")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise FlowTimingStop("Operator STOP unexpectedly changed")
    return evaluate(
        account=account,positions=positions,orders=orders,clock=clock,
        history=history,activities=activities,native_none_history=none,
        bootstrap=bootstrap,policy=policy,control=control,
        remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
        observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def main():
    r=runtime()
    for name in (
        "schema","original_account_and_legacy_positions_verified",
        "original_xle_target_status","original_cash_floor_status",
        "original_external_funding_classification",
        "cash_transfer_amount_and_timestamp_field_status",
        "observed_cash_transfer_count_class",
        "broker_cashflow_types_none_pnl_comparison",
        "original_raw_equity_risk_status",
        "actual_cashflow_adjusted_dietz_returns_calculated",
        "actual_s1_6_20_35_risk_verified",
        "actual_sale_proceeds_t_plus_one_settled","live_buy_sell_authorized",
        "broker_get_requests","broker_non_get_requests","live_orders",
    ):
        print(name+":",r[name])
    print("Private original amounts, timestamps, IDs, equity and PNL not printed")


if __name__=="__main__":
    main()

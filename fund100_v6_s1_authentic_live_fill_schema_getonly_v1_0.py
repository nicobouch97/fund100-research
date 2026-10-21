"""First authentic original LIVE Alpaca trade-FILL *source shape*, five GET.

Original 4 account/position/clock/open-order GET and precisely one FILL GET.
NO order API writer, no source amounts/IDs exported, no T+1 claim.
"""
from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import os
from uuid import UUID

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four

SCHEMA="FUND100_V6_S1_ACTUAL_LIVE_ORIGINAL_TRADE_FILLS_SOURCE_FIVE_GET_V1"
FILL_PATH="/v2/account/activities/FILL"
FILL_PARAMS={"after":"2026-10-01","direction":"asc","page_size":100}
ORIGINAL=frozenset(("ACWI","EEM","XLE","XLV"))
FULL_SOURCE_MAX=100
BROKER_WRITER_RELEASED=False

class FillSourceStop(RuntimeError):pass

def _decimal(value,label,*,zero=False):
    if type(value) not in (str,int,Decimal):
        raise FillSourceStop("Missing valid private "+label)
    try:v=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise FillSourceStop("Invalid private "+label) from None
    if not v.is_finite() or (v<0 if zero else v<=0):
        raise FillSourceStop("Nonfinite/nonpositive private "+label)
    return v

def _utc(value):
    if type(value) is not str:
        raise FillSourceStop("Missing FILL execution timestamp")
    try:d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:raise FillSourceStop("Bad FILL execution timestamp") from None
    if d.tzinfo is None or d.utcoffset() is None:
        raise FillSourceStop("FILL execution timestamp lacks offset")
    return d.astimezone(timezone.utc)

def classify(*,account,positions,orders,clock,fills,bootstrap,policy,control,
             remotely_stopped,kill_switch,risk_level,observed_at_utc):
    """Pure source checker; only source-shape summaries, no authenticated claim."""
    try:
        core=four.check_account(account=account,positions=positions,orders=orders,
            clock=clock,bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except Exception:
        raise FillSourceStop("Original LIVE four-GET brokerage source failed") from None
    if (core["broker_get_requests"]!=4 or core["broker_orders_submitted"]!=0
        or core["open_order_count"]!=0
        or core["historic_four_original_etf_quantities_reconciled"] is not True):
        raise FillSourceStop("Original broker hold/quantity STOP source mismatch")
    if type(fills) is not list or len(fills)>FULL_SOURCE_MAX:
        raise FillSourceStop("Broker FILL activities page response invalid")
    seen_activity=set()
    seen_buys=set()
    any_sell=False
    other_symbol=False
    partial=False
    now=_utc(observed_at_utc)
    floor=_utc("2026-10-01T00:00:00Z")
    for row in fills:
        if type(row) is not dict or row.get("activity_type")!="FILL":
            raise FillSourceStop("Unexpected LIVE brokerage activity classification")
        identity=row.get("id")
        if (type(identity) is not str or "::" not in identity
            or not identity or identity in seen_activity):
            raise FillSourceStop("Missing/duplicate trading activity pagination ID")
        seen_activity.add(identity)
        order_id=row.get("order_id")
        try:
            if type(order_id) is not str or str(UUID(order_id))!=order_id.lower():
                raise ValueError("Malformed FILL broker order id")
        except ValueError:
            raise FillSourceStop("FILL event missing exact broker order identity") from None
        when=_utc(row.get("transaction_time"))
        if when<floor or when>now:
            raise FillSourceStop("FILL time outside requested source window")
        symbol=row.get("symbol")
        side=row.get("side")
        if type(symbol) is not str or not symbol or side not in ("buy","sell"):
            raise FillSourceStop("Malformed private fill symbol/side")
        qty=_decimal(row.get("qty"),"activity quantity")
        cum=_decimal(row.get("cum_qty"),"cumulative fill qty")
        leaves=_decimal(row.get("leaves_qty"),"shares remaining",zero=True)
        _decimal(row.get("price"),"execution price")
        if cum<qty:
            raise FillSourceStop("Cumulative FILL cannot be below this activity")
        if row.get("type") not in ("fill","partial_fill"):
            raise FillSourceStop("Unknown full/partial fill type")
        if row["type"]=="partial_fill":
            partial=True
        if symbol not in ORIGINAL:
            other_symbol=True
        elif side=="sell":
            any_sell=True
        else:
            seen_buys.add(symbol)
    if len(fills)==FULL_SOURCE_MAX:
        stage="FILL_ACTIVITY_PAGE_FULL_PAGINATION_INCOMPLETE_HOLD"
    elif any_sell or other_symbol:
        stage="UNEXPECTED_ORIGINAL_SELL_OR_EXTRA_SYMBOL_FILLS_REVIEW"
    elif not fills:
        stage="NO_ORIGINAL_TRADE_FILLS_OBSERVED_HOLD"
    elif seen_buys!=ORIGINAL:
        stage="SOME_ORIGINAL_BUY_FILL_SYMBOLS_NOT_OBSERVED"
    else:
        stage="ORIGINAL_FILLS_STRUCTURE_SEEN_ORDER_LINKAGE_UNVERIFIED"
    return {
       "schema":SCHEMA,"fill_source_status":stage,
       "original_account_and_four_etf_quantities_reconciled":True,
       "original_open_orders":0,
       "four_original_etf_buy_fill_symbols_seen":seen_buys==ORIGINAL,
       "partial_fill_activity_seen":partial,
       "unexpected_symbol_or_sell_activity_seen":other_symbol or any_sell,
       "source_page_below_100_limit":len(fills)<FULL_SOURCE_MAX,
       "source_page_complete_for_requested_window":len(fills)<FULL_SOURCE_MAX,
       "all_broker_activities_and_cashflows_reconciled":False,
       "source_order_ids_linked_to_original_bootstrap":False,
       "original_sale_fill_and_tplusone_settlement_verified":False,
       "live_buy_sell_authorized":False,
       "private_offhost_order_journal_verified":False,
       "broker_get_requests":5,"broker_non_get_requests":0,"broker_orders_submitted":0,
       "actual_order_ids":None,"private_trade_timestamps":None,
       "activity_ids":None,"account_id":None,
       "fills_qty_price":None,"broker_cash":None,"order_payload":None,
    }

def runtime():
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise FillSourceStop("Main/HIGH/engaged STOP required")
    boot,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise FillSourceStop("Original account operator/release not stopped")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def read(path,params=None):
        if path=="/v2/orders":
            if params!={"status":"open","limit":100}:raise FillSourceStop("Open-order query changed")
        elif path==FILL_PATH:
            if params!=FILL_PARAMS:raise FillSourceStop("FILL source query changed")
        elif path not in four.PATHS or params is not None:
            raise FillSourceStop("Unapproved GET request/params")
        calls.append(path)
        try:return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise FillSourceStop("Authenticated original GET failed; private response suppressed") from None
    account=read("/v2/account")
    positions=read("/v2/positions")
    orders=read("/v2/orders",{"status":"open","limit":100})
    clock=read("/v2/clock")
    fills=read(FILL_PATH,FILL_PARAMS)
    if tuple(calls)!=four.PATHS+(FILL_PATH,):
        raise FillSourceStop("Source must make exactly original four plus one FILL GET")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise FillSourceStop("Original STOP changed during authenticated source")
    return classify(account=account,positions=positions,orders=orders,clock=clock,
        fills=fills,bootstrap=boot,policy=policy,control=control,
        remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
        observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

def main():
    report=runtime()
    for name in (
        "schema","fill_source_status",
        "original_account_and_four_etf_quantities_reconciled",
        "four_original_etf_buy_fill_symbols_seen",
        "partial_fill_activity_seen","unexpected_symbol_or_sell_activity_seen",
        "source_page_below_100_limit",
        "source_order_ids_linked_to_original_bootstrap",
        "all_broker_activities_and_cashflows_reconciled",
        "original_sale_fill_and_tplusone_settlement_verified",
        "live_buy_sell_authorized","broker_get_requests",
        "broker_non_get_requests","broker_orders_submitted"):
        print(name+":",report[name])
    print("ALL private trade amounts, IDs, symbols per trade and times are REDACTED")

if __name__=="__main__":
    main()

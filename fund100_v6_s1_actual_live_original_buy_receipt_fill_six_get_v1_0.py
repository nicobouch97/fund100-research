"""Actual LIVE V5 original BUY order-to-FILL activity proof. Six GET, NO write.

Previous authentic account/FILL five GET source and original bootstrap client IDs
are checked in memory. This NEVER proves future V6 sale settlement/spendability.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_authentic_live_fill_schema_getonly_v1_0 as five

SCHEMA="FUND100_V6_S1_AUTHENTIC_ORIGINAL_V5_BUYS_LINKED_TO_FILLS_SIX_GET_V1"
CLOSED_PARAMS={"status":"closed","after":"2026-10-01T00:00:00Z",
               "direction":"asc","limit":100}
GET_SEQUENCE=four.PATHS+(five.FILL_PATH,"/v2/orders")
TRANSPORT_RELEASED=False
class ClosedSourceStop(RuntimeError):pass

def classify(*,account,positions,orders,clock,fills,closed,bootstrap,
             policy,control,remotely_stopped,kill_switch,risk_level,
             observed_at_utc):
    try:
        evidence=five.classify(
            account=account,positions=positions,orders=orders,clock=clock,
            fills=fills,bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except Exception:
        raise ClosedSourceStop("Original five-GET LIVE source unverified") from None
    if (evidence["broker_get_requests"]!=5
        or evidence["broker_orders_submitted"]!=0
        or evidence["live_buy_sell_authorized"] is not False):
        raise ClosedSourceStop("Original private FILL source changed")
    if type(closed) is not list or len(closed)>100:
        raise ClosedSourceStop("Malformed closed LIVE order page")
    page_full=(len(closed)==100 or not evidence["source_page_below_100_limit"])
    expected=bootstrap.get("orders")
    if type(expected) is not dict or set(expected)!=set(five.ORIGINAL):
        raise ClosedSourceStop("Original immutable BUY order source incomplete")
    original_client_ids={}
    for sym,row in expected.items():
        val=row.get("client_order_id")
        if type(val) is not str or not val or val in original_client_ids.values():
            raise ClosedSourceStop("Original historical broker client order identity missing")
        original_client_ids[sym]=val
    by_order_id={}
    by_client_id={}
    unexpected=False
    for receipt in closed:
        if type(receipt) is not dict:
            raise ClosedSourceStop("Broker closed receipt is not a dict")
        order_id=receipt.get("id")
        client_id=receipt.get("client_order_id")
        if (type(order_id) is not str or not order_id
            or type(client_id) is not str or not client_id
            or order_id in by_order_id or client_id in by_client_id):
            raise ClosedSourceStop("Closed receipt identity absent/duplicated")
        by_order_id[order_id]=receipt
        by_client_id[client_id]=receipt
        if (client_id not in original_client_ids.values()
            or receipt.get("symbol") not in five.ORIGINAL
            or receipt.get("side")!="buy" or receipt.get("status")!="filled"):
            unexpected=True
        if receipt.get("status")=="filled":
            try:
                five._decimal(receipt.get("filled_qty"),"order filled shares")
                five._utc(receipt.get("filled_at"))
            except Exception:
                raise ClosedSourceStop("Completed receipt incomplete") from None
    sums=defaultdict(lambda:Decimal(0))
    for row in fills:
        sums[row["order_id"]]+=five._decimal(row.get("qty"),"private fill shares")
    linked=set()
    unmatched_fill=False
    for id_,quantity in sums.items():
        if id_ not in by_order_id:
            unmatched_fill=True
    for symbol in five.ORIGINAL:
        receipt=by_client_id.get(original_client_ids[symbol])
        if receipt is None:
            continue
        if (receipt["symbol"]!=symbol or receipt.get("side")!="buy"
            or receipt.get("status")!="filled"):
            unexpected=True
            continue
        try:
            actual=five._decimal(receipt.get("filled_qty"),"filled order qty")
            original_qty=five._decimal(expected[symbol]["filled_qty"],"original bootstrap qty")
        except Exception:
            raise ClosedSourceStop("Original order quantities invalid") from None
        if actual!=original_qty or sums.get(receipt["id"],Decimal(0))!=actual:
            unexpected=True
            continue
        linked.add(symbol)
    if page_full:
        status="BROKER_PAGINATION_INCOMPLETE_STOP"
    elif unexpected or unmatched_fill or evidence["unexpected_symbol_or_sell_activity_seen"]:
        status="ORDER_FILL_OR_UNEXPECTED_RECEIPT_RECONCILIATION_STOP"
    elif len(linked)!=4 or not evidence["four_original_etf_buy_fill_symbols_seen"]:
        status="ORIGINAL_BUY_RECEIPTS_OR_FILLED_ACTIVITIES_MISSING_STOP"
    else:
        status="ORIGINAL_V5_BUY_ORDER_IDS_AND_FILLS_LINKED_NO_SETTLEMENT_CLAIM"
    return {
        "schema":SCHEMA,
        "original_live_account_and_four_holdings_verified":True,
        "original_v5_buy_order_receipt_fill_linkage_status":status,
        "all_four_original_client_order_ids_match_receipts":len(linked)==4,
        "unique_order_ids_reconciled_with_fill_activities":len(linked)==4 and not unmatched_fill,
        "original_live_open_orders":0,
        "fill_page_below_limit":evidence["source_page_below_100_limit"],
        "closed_order_page_below_limit":len(closed)<100,
        "complete_external_cashflow_history_verified":False,
        "v6_original_sell_execution_verified":False,
        "tplusone_sale_proceeds_spendable_verified":False,
        "private_cross_run_state_verified":False,
        "live_buy_sell_authorized":False,
        "broker_get_requests":6,"broker_non_get_requests":0,"broker_orders_submitted":0,
        "private_order_ids":None,"private_client_order_ids":None,
        "private_share_quantities":None,"private_prices":None,
        "private_fill_timestamps":None,"private_account_id":None,
    }

def runtime():
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise ClosedSourceStop("Original main HIGH STOP required")
    boot,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise ClosedSourceStop("Original operator not stopped")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    called=[]
    def get(path,params=None):
        if path=="/v2/orders":
            if params not in ({"status":"open","limit":100},CLOSED_PARAMS):
                raise ClosedSourceStop("Unapproved account order query")
        elif path==five.FILL_PATH:
            if params!=five.FILL_PARAMS:raise ClosedSourceStop("Unapproved FILL GET")
        elif path not in four.PATHS or params is not None:
            raise ClosedSourceStop("Unapproved endpoint")
        called.append(path)
        try:return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise ClosedSourceStop("Original broker closed/FILL source unavailable") from None
    account=get("/v2/account")
    positions=get("/v2/positions")
    orders=get("/v2/orders",{"status":"open","limit":100})
    clock=get("/v2/clock")
    fills=get(five.FILL_PATH,five.FILL_PARAMS)
    closed=get("/v2/orders",CLOSED_PARAMS)
    if tuple(called)!=GET_SEQUENCE:
        raise ClosedSourceStop("Original six GET sequence changed")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise ClosedSourceStop("Operator STOP changed during GET")
    return classify(account=account,positions=positions,orders=orders,clock=clock,
                    fills=fills,closed=closed,bootstrap=boot,policy=policy,
                    control=control,remotely_stopped=True,kill_switch="ENGAGED",
                    risk_level="HIGH",observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

def main():
    status=runtime()
    for key in (
        "schema","original_live_account_and_four_holdings_verified",
        "original_v5_buy_order_receipt_fill_linkage_status",
        "all_four_original_client_order_ids_match_receipts",
        "unique_order_ids_reconciled_with_fill_activities",
        "closed_order_page_below_limit",
        "complete_external_cashflow_history_verified",
        "v6_original_sell_execution_verified",
        "tplusone_sale_proceeds_spendable_verified",
        "live_buy_sell_authorized","broker_get_requests",
        "broker_non_get_requests","broker_orders_submitted"):
        print(key+":",status[key])
    print("No private account/order/activity details or numeric balances ever printed")

if __name__=="__main__":
    main()

"""Authentic original LIVE Alpaca Trading-account cash field PRESENCE only.

Exact original four GETs through unchanged/sha-pinned read-only transport.
No spendable-cash/settlement assertions, no outputs of customer cash,
account ID, shares, order details or raw brokerage JSON. Zero orders.
"""
from __future__ import annotations

from datetime import datetime,timezone
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four

SCHEMA="FUND100_V6_S1_REAL_TRADING_ACCOUNT_CASH_FIELD_PRESENCE_FOUR_GET_V1"
FIELDS=("cash","buying_power","non_marginable_buying_power",
        "pending_transfer_in","pending_transfer_out","accrued_fees")
CANDIDATES=("cash_withdrawable","cash_transferable")
LIVE_SELL_BUY_RELEASED=False

class CashPresenceStop(RuntimeError):pass

def assess(*,account,positions,orders,clock,bootstrap,policy,control,
           remotely_stopped,kill_switch,risk_level,observed_at_utc):
    """Original source-bound 4-GET assessment; supplied fixtures are not proof."""
    try:
        status=four.check_account(
            account=account,positions=positions,orders=orders,clock=clock,
            bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except Exception:
        raise CashPresenceStop("Original LIVE account/position and operator STOP source invalid") from None
    if (status.get("broker_get_requests")!=4
        or status.get("broker_orders_submitted")!=0
        or status.get("historic_four_original_etf_quantities_reconciled") is not True
        or status.get("account_binding_matches_original_policy") is not True
        or status.get("open_order_count")!=0
        or type(account) is not dict):
        raise CashPresenceStop("Original source validation incomplete")
    direct={x: x in account and account[x] is not None for x in CANDIDATES}
    if all(direct.values()):
        stage="BOTH_BROKER_STYLE_FIELDS_PRESENT_SEMANTICS_UNVERIFIED"
    elif any(direct.values()):
        stage="PARTIAL_BROKER_STYLE_FIELDS_AMBIGUOUS_HOLD"
    else:
        stage="DIRECT_BROKER_STYLE_SETTLED_FIELDS_ABSENT"
    multiplier=account.get("multiplier")
    multiplier_kind=("1X_NOT_SETTLEMENT_PROOF" if str(multiplier)=="1"
        else "OTHER_NOT_SETTLEMENT_PROOF" if multiplier is not None
        else "NOT_EXPOSED")
    return {
       "schema":SCHEMA,
       "cash_field_capability":stage,
       "original_live_account_four_positions_verified":True,
       "original_operator_stopped":True,
       "original_kill_switch_engaged":True,
       "original_no_open_orders":True,
       "original_xle_still_held":True,
       "withdrawable_field_present":direct["cash_withdrawable"],
       "transferable_field_present":direct["cash_transferable"],
       "documented_trading_fields_present":{
           field:field in account and account[field] is not None for field in FIELDS},
       "margin_multiplier_kind":multiplier_kind,
       "trading_buying_power_is_settlement_proof":False,
       "trading_cash_is_settlement_proof":False,
       "direct_field_semantics_verified":False,
       "account_cashflow_history_reconciled":False,
       "original_sale_orders_placed":False,
       "actual_original_sale_proceeds_settled":False,
       "actual_live_v6_6_20_35_risk_verified":False,
       "private_state_remote_persistence_verified":False,
       "real_buy_sell_authorized":False,
       "broker_get_requests":4,"broker_non_get_requests":0,
       "account_id":None,"cash_amounts":None,"share_quantities":None,
       "original_order_details":None,"executable_order":None,
    }

def runtime():
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise CashPresenceStop("Original stopped HIGH main required")
    boot,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise CashPresenceStop("Original LIVE operator or source not stopped")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def broker_get(path,params=None):
        if path not in four.PATHS:
            raise CashPresenceStop("Unexpected broker endpoint")
        if (path=="/v2/orders" and params!={"status":"open","limit":100}
            or path!="/v2/orders" and params is not None):
            raise CashPresenceStop("Unapproved broker query")
        calls.append(path)
        try:
            return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise CashPresenceStop("Private LIVE source unavailable, details withheld") from None
    account=broker_get("/v2/account")
    positions=broker_get("/v2/positions")
    orders=broker_get("/v2/orders",{"status":"open","limit":100})
    clock=broker_get("/v2/clock")
    if tuple(calls)!=four.PATHS:
        raise CashPresenceStop("Four-GET source sequence changed")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise CashPresenceStop("Operator changed after broker GET")
    return assess(
       account=account,positions=positions,orders=orders,clock=clock,
       bootstrap=boot,policy=policy,control=control,remotely_stopped=True,
       kill_switch="ENGAGED",risk_level="HIGH",
       observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

def main():
    p=runtime()
    for field in (
       "schema","cash_field_capability",
       "original_live_account_four_positions_verified",
       "original_operator_stopped","original_no_open_orders",
       "withdrawable_field_present","transferable_field_present",
       "margin_multiplier_kind","actual_original_sale_proceeds_settled",
       "real_buy_sell_authorized","broker_get_requests","broker_non_get_requests",
    ):
        print(field+":",p[field])
    for field in FIELDS:
        print("source_field_"+field+"_present:",p["documented_trading_fields_present"][field])
    print("Actual account, cash, share quantities, order IDs and credentials NEVER PRINTED")

if __name__=="__main__":
    main()

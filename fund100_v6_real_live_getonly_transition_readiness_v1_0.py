"""V6 real Alpaca LIVE transition readiness, GET-ONLY with private balances redacted.

Only GET /v2/account, /v2/positions, /v2/orders, /v2/clock.
Never writes broker credentials, exact account quantities, cash, market
value, equity, order details, fills or personal identifiers to artifacts.
Zero sell/buy orders. Validates four existing V5 fills BEFORE any
hypothetical future V6 switch, but never authorizes such a switch.
"""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as prior

SCHEMA="FUND100_V6_ACTUAL_LIVE_GET_ONLY_TRANSITION_READINESS_V1"
BOOT=Path("live_activation_outputs/v5_002/live_bootstrap_v1_0.json")
POLICY=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
CONTROL=Path("fund100_live_operator_control.json")
ALLOWED={"ACWI","EEM","XLE","XLV"}
PATHS=("/v2/account","/v2/positions","/v2/orders","/v2/clock")
MAX_AGE_QUOTE_UNVERIFIED=True

class ReadinessStop(RuntimeError):
    pass


def _clean_decimal(value, name:str, *, zero:bool=False)->Decimal:
    try:
        d=prior.positive(value,name,allow_zero=zero)
    except prior.TransitionStop as exc:
        raise ReadinessStop("Malformed or negative broker "+name+".") from exc
    return d


def check_account(*,account:dict,positions:list,orders:list,clock:dict,
                  bootstrap:dict,policy:dict,control:dict,
                  remotely_stopped:bool,
                  kill_switch:str,risk_level:str,
                  observed_at_utc:str)->dict:
    # This is a privacy-safe summary: never return private broker values.
    try:
        originals=prior.check_original(bootstrap,policy,control)
    except prior.TransitionStop as exc:
        raise ReadinessStop("Original 2026 LIVE pilot source chain is not valid.") from exc
    if (kill_switch!="ENGAGED" or risk_level!="HIGH" or remotely_stopped is not True
        or control.get("trading_enabled") is not False):
        raise ReadinessStop("Broker STOP and HIGH profile are mandatory.")
    try:
        observed=prior._at(observed_at_utc)
    except prior.TransitionStop as exc:
        raise ReadinessStop("Invalid UTC acquisition clock.") from exc
    if abs((datetime.now(timezone.utc)-observed).total_seconds())>600:
        raise ReadinessStop("LIVE observation is not recent.")
    if not isinstance(account,dict) or not isinstance(positions,list) or not isinstance(orders,list) or not isinstance(clock,dict):
        raise ReadinessStop("Invalid GET-only response types.")
    if not account.get("id") or not isinstance(account["id"],str):
        raise ReadinessStop("Broker identity missing.")
    binding=sha256(("FUND100-LIVE-ACCOUNT|"+account["id"].strip()).encode()).hexdigest()
    if binding!=policy.get("account_binding_sha256"):
        raise ReadinessStop("Unexpected LIVE account identity.")
    if (account.get("status")!="ACTIVE"
        or account.get("account_blocked") is True
        or account.get("trading_blocked") is True):
        raise ReadinessStop("LIVE account is not in approved ACTIVE state.")
    if len(orders)!=0:
        raise ReadinessStop("Existing LIVE orders must be reconciled first.")
    if len(positions)!=len(ALLOWED):
        raise ReadinessStop("LIVE holdings differ from original four fills.")
    by_symbol={}
    for item in positions:
        if not isinstance(item,dict):
            raise ReadinessStop("Malformed LIVE position.")
        symbol=item.get("symbol")
        if symbol not in ALLOWED or symbol in by_symbol:
            raise ReadinessStop("Unexpected or duplicated LIVE symbol.")
        qty=_clean_decimal(item.get("qty"),"position quantity")
        current=_clean_decimal(item.get("current_price"),"current broker mark")
        market=_clean_decimal(item.get("market_value"),"position market value")
        if abs(qty-originals[symbol])>Decimal("0.00000001"):
            raise ReadinessStop("LIVE quantity changed from original fills; manual reconciliation required.")
        if abs(market-qty*current)>max(Decimal("0.03"),market*Decimal("0.01")):
            raise ReadinessStop("Broker quantity/current-price/market-value incoherent.")
        by_symbol[symbol]=(qty,current,market)
    if set(by_symbol)!=ALLOWED:
        raise ReadinessStop("LIVE original position set incomplete.")
    cash=_clean_decimal(account.get("cash"),"cash",zero=True)
    equity=_clean_decimal(account.get("equity"),"equity")
    exposure=sum(row[2] for row in by_symbol.values())
    if abs(equity-exposure-cash)>max(Decimal("1.00"),equity*Decimal(".02")):
        raise ReadinessStop("LIVE account equity/cash/holdings cannot be reconciled.")
    if type(clock.get("is_open")) is not bool:
        raise ReadinessStop("Alpaca market-clock status invalid.")
    # Cash and unrealized sale estimates cannot be assumed instantly
    # available for repurchase; T+1 and brokerage buying power apply.
    return {
        "schema":SCHEMA,
        "observed_at_utc":observed_at_utc,
        "account_binding_matches_original_policy":True,
        "live_account_active":True,
        "historic_four_original_etf_quantities_reconciled":True,
        "present_symbols_correspond_to_original_four":True,
        "account_cash_and_holdings_reconcile_to_equity":True,
        "open_order_count":0,
        "market_regular_session_open":clock["is_open"],
        "broker_current_price_fields_are_not_executable_ask_quotes":True,
        "equity_usd":None,
        "cash_usd":None,
        "position_quantities":None,
        "account_id":None,
        "unsettled_sale_proceeds_spendable_verified":False,
        "broker_current_cash_and_equity_accessed_but_not_persisted":True,
        "estimated_liquidation_value_persisted":False,
        "holdings_value_plus_cash_above_zero":equity>0,
        "original_live_authorized_cap_usd":"130.30",
        "original_operator_stopped":True,
        "remote_operator_stopped_on_main":True,
        "broker_environment_kill_switch_engaged":True,
        "high_risk_tier_selected":True,
        "current_strategy_decision":"HOLD_EXISTING_FOUR_ETFS_NO_SELL",
        "fresh_account_snapshot_ready_for_private_future_exit_estimate":True,
        "future_v6_replacement_strategy_approved":False,
        "account_real_sell_orders_authorized":False,
        "live_autonomous_order_execution_authorized":False,
        "broker_get_requests":4,
        "broker_non_get_requests":0,
        "broker_orders_submitted":0,
    }


def runtime()->dict:
    if (os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"):
        raise ReadinessStop("Actual LIVE GET-only inspection can run on main only.")
    kill=os.getenv("FUND100_BROKER_KILL_SWITCH","")
    level=os.getenv("FUND100_RISK_LEVEL","")
    if kill!="ENGAGED" or level!="HIGH":
        raise ReadinessStop("LIVE environment must be stopped and HIGH risk selected.")
    boots,_=prior.original(BOOT)
    policy,_=prior.original(POLICY)
    control,_=prior.original(CONTROL)
    if policy.get("live_order_authorization_present") is not False:
        raise ReadinessStop("Original LIVE new-order authorization must stay absent.")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise ReadinessStop("Remote operator on current main not STOPPED.")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def read_exact(path:str,params:dict|None=None):
        if path not in PATHS:
            raise ReadinessStop("LIVE GET-only endpoint not allowed.")
        calls.append(path)
        return live.get_json(path=path,key=key,secret=secret,params=params)
    account=read_exact("/v2/account")
    positions=read_exact("/v2/positions")
    orders=read_exact("/v2/orders",{"status":"open","limit":100})
    clock=read_exact("/v2/clock")
    if calls!=list(PATHS):
        raise ReadinessStop("Unexpected broker GET requests.")
    result=check_account(
        account=account,positions=positions,orders=orders,clock=clock,
        bootstrap=boots,policy=policy,control=control,
        remotely_stopped=True,kill_switch=kill,risk_level=level,
        observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    return result


def main():
    report=runtime()
    # Deliberately write NO account, quantity, cash or equity records to
    # any file or artifact. Only privacy-safe booleans in stdout.
    print("V6 LIVE GET-only account transition inspection:")
    for key in (
        "account_binding_matches_original_policy",
        "historic_four_original_etf_quantities_reconciled",
        "account_cash_and_holdings_reconcile_to_equity",
        "market_regular_session_open",
        "open_order_count",
        "broker_environment_kill_switch_engaged",
        "current_strategy_decision",
        "broker_get_requests",
        "broker_orders_submitted",
    ):
        print(key+":",report[key])
    print("CURRENT CASH/EQUITY/MARKS/QUANTITIES: NOT PRINTED OR SAVED")
    print("REAL MONEY SALES AND NEW BUYS: DISABLED")


if __name__=="__main__":
    main()

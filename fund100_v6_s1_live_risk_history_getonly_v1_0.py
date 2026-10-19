"""V6-S1 actual Alpaca LIVE five-GET risk-evidence inspector, NO ORDERS.

New versioned research source check, no writer, no release. Reuses exact
existing original V5 LIVE account/position source-binding verifier and
existing portfolio history guard, with ONLY boolean/status public output.

Alpaca's raw account equity history may include contributions/withdrawals
and does NOT prove cash-flow-adjusted strategy volatility, T+1 settlement,
future ask prices, or an authorised V6 trading risk profile. The observer
keeps those unresolved even when broker history passes its raw-history gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_live_portfolio_risk_v1_0 as risk
import fund100_v6_brokerless_transition_preview_v1_0 as prior_original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four

SCHEMA="FUND100_V6_S1_REAL_LIVE_RISK_HISTORY_GET_ONLY_V1"
HISTORY_PATH="/v2/account/portfolio/history"
PATHS=("/v2/account","/v2/positions","/v2/orders","/v2/clock",HISTORY_PATH)
HISTORY_PARAMS={"period":"1M","timeframe":"1D"}
CAP=Decimal("130.30")
SOURCE_ONLY="LIVE_PRIVATE_SOURCE_EVIDENCE_NO_EXECUTABLE_INTENT"

class PrivateRiskReadStop(RuntimeError):pass


def review(*, account:dict,positions:list,orders:list,clock:dict,history:dict,
           bootstrap:dict,policy:dict,control:dict,remotely_stopped:bool,
           kill_switch:str,risk_level:str,observed_at_utc:str)->dict:
    """Source-qualified original holdings + broker raw history; never produce orders."""
    try:
        r=four.check_account(
            account=account,positions=positions,orders=orders,clock=clock,
            bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except (four.ReadinessStop, prior_original.TransitionStop, ValueError) as exc:
        raise PrivateRiskReadStop("Original LIVE account source could not be reconciled") from None
    if r["broker_orders_submitted"]!=0 or r["open_order_count"]!=0 or r["broker_get_requests"]!=4:
        raise PrivateRiskReadStop("Original LIVE zero-order boundary changed")
    if not isinstance(account,dict) or not isinstance(history,dict):
        raise PrivateRiskReadStop("Malformed account/portfolio-history source")
    # This read-only observer does not accept even a caller assertion of
    # spendable settled sale proceeds. Alpaca CASH and BUYING_POWER are not
    # enough to certify T+1 or the exact spendable amount.
    multiplier=account.get("multiplier")
    multiplier_ok=isinstance(multiplier,(str,int)) and str(multiplier)=="1"
    raw_history_status="RAW_BROKER_EQUITY_HISTORY_NOT_QUALIFIED"
    raw_guard_pass=False
    try:
        risk.check_account_performance(
            account=account,history=history,profile=risk.get_profile("HIGH"))
    except (risk.PortfolioRiskStop,ValueError,TypeError,ZeroDivisionError,OverflowError):
        raw_history_status="RAW_BROKER_EQUITY_HISTORY_INSUFFICIENT_OR_RISK_STOP"
    else:
        raw_history_status="RAW_BROKER_EQUITY_HISTORY_PASS_NOT_CASHFLOW_ADJUSTED"
        raw_guard_pass=True
    return {
      "schema":SCHEMA,
      "source_class":SOURCE_ONLY,
      "asof_utc":observed_at_utc,
      "source_original_account_binding_matched":True,
      "original_four_positions_quantities_reconciled":True,
      "original_legacy_assets_still_held":True,
      "broker_open_order_count":0,
      "market_regular_session_open":r["market_regular_session_open"],
      "original_live_stop_observed":True,
      "original_broker_kill_switch_engaged":True,
      "original_high_risk_tier_selected":True,
      "original_trial_cap_usd":"130.30",
      "broker_margin_multiplier_one_observed":multiplier_ok,
      "raw_broker_portfolio_history_result":raw_history_status,
      "raw_broker_portfolio_history_guard_passed":raw_guard_pass,
      "raw_equity_history_cashflow_adjusted":False,
      "account_daily_loss_6pct_pretrade_release_proven":False,
      "account_drawdown_20pct_pretrade_release_proven":False,
      "account_realized_volatility_35pct_pretrade_release_proven":False,
      "actual_t_plus_one_spendable_cash_proven":False,
      "current_executable_ask_quotes_and_costs_proven":False,
      "live_order_history_all_client_ids_reconciled":False,
      "s1_target_single_asset_and_gross_reconciled_for_live_order":False,
      "live_v6_buy_or_sale_authorized":False,
      "live_orders_submitted":0,"broker_get_requests":5,"broker_non_get_requests":0,
      "account_id":None,"equity_usd":None,"cash_usd":None,"share_quantities":None,
      "executable_order_payload":None,
      "next_stage":"LIVE_V6_PRIVATE_SOURCE_EVIDENCE_COLLECTED_ONLY",
    }


def runtime()->dict:
    if (os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise PrivateRiskReadStop("Read-only research requires authenticated stopped main and HIGH")
    boots,_=prior_original.original(four.BOOT)
    policy,_=prior_original.original(four.POLICY)
    control,_=prior_original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise PrivateRiskReadStop("Original LIVE order authority must remain disabled")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def fetch(path:str,params:dict|None=None):
        if path not in PATHS:
            raise PrivateRiskReadStop("Unreviewed broker HTTP GET endpoint")
        if path==HISTORY_PATH and params!=HISTORY_PARAMS:
            raise PrivateRiskReadStop("Only original one-month daily broker history allowed")
        if path=="/v2/orders" and params!={"status":"open","limit":100}:
            raise PrivateRiskReadStop("Only open-order read approved")
        if path not in (HISTORY_PATH,"/v2/orders") and params is not None:
            raise PrivateRiskReadStop("Unreviewed GET query params")
        calls.append(path)
        try:
            return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            # Never echo HTTP body, requests, account IDs or balances.
            raise PrivateRiskReadStop("LIVE broker read failed, private details withheld") from None
    account=fetch("/v2/account")
    positions=fetch("/v2/positions")
    orders=fetch("/v2/orders",{"status":"open","limit":100})
    clock=fetch("/v2/clock")
    history=fetch(HISTORY_PATH,HISTORY_PARAMS)
    if tuple(calls)!=PATHS:
        raise PrivateRiskReadStop("Exactly five ordered READ-only calls required")
    # Re-read current GitHub main operator control, fail closed if switched.
    if operator.validate_control(operator.read_current_control()) is not False:
        raise PrivateRiskReadStop("Main branch trading STOP unexpectedly released")
    return review(
        account=account,positions=positions,orders=orders,clock=clock,
        history=history,bootstrap=boots,policy=policy,control=control,
        remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
        observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


def main()->None:
    report=runtime()
    for field in (
        "schema","source_original_account_binding_matched",
        "original_four_positions_quantities_reconciled",
        "broker_open_order_count","market_regular_session_open",
        "broker_margin_multiplier_one_observed",
        "raw_broker_portfolio_history_result",
        "raw_equity_history_cashflow_adjusted",
        "actual_t_plus_one_spendable_cash_proven",
        "live_v6_buy_or_sale_authorized",
        "broker_get_requests","broker_non_get_requests","live_orders_submitted",
        "next_stage",
    ):
        print(field+":",report[field])
    print("No account balances, quantities, cash, account ID or trading intents are saved or emitted.")


if __name__=="__main__":
    main()

"""V7-X3 genuine Alpaca LIVE six-GET-only BTC/USD + GLD availability probe.

Research feasibility, NOT a trading authorisation. The original four LIVE
GETs are independently validated against the exact account/filled-positions
binding and stopped operator. Two additional GETs retrieve only (i) active
crypto asset definitions and (ii) GLD metadata. This intentionally cannot
prove a UK/other customer crypto jurisdiction, trade execution, price,
settlement, buying power, fee, or live-order permission. Never persist
customer financial amounts, account numbers, positions or broker payloads.
"""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation,ROUND_DOWN
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as originals
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four

SCHEMA="FUND100_V7_X3_REAL_LIVE_CRYPTO_GOLD_GET_ONLY_FEASIBILITY_V1"
EXPECTED_PATHS=("/v2/account","/v2/positions","/v2/orders",
                "/v2/clock","/v2/assets","/v2/assets/GLD")
CRYPTO_QUERY={"status":"active","asset_class":"crypto"}
ORDER_QUERY={"status":"open","limit":100}
CAP=Decimal("130.30")
BTC_TARGET=Decimal("0.05")
GLD_TARGET=Decimal("0.05")
BROKER_NON_GETS=BROKER_ORDERS=0
EXECUTION_ALLOWED=False

class AccessStop(ValueError):pass

def _money(raw,label)->Decimal:
    try:
        d=Decimal(str(raw))
        if d.is_finite() and d>=0:
            return d
    except (TypeError,InvalidOperation,ValueError):
        pass
    raise AccessStop("Unqualified "+label+" broker amount")

def _asset(asset:dict, *,symbol:str)->dict:
    if type(asset) is not dict or asset.get("symbol") not in (
        (("BTC/USD","BTCUSD") if symbol=="BTC/USD" else (symbol,))
    ):
        raise AccessStop("Unexpected live broker asset identity")
    status=asset.get("status")
    if status not in ("active","inactive"):
        raise AccessStop("Asset status missing from actual broker source")
    tradable=asset.get("tradable")
    fractional=asset.get("fractionable")
    if type(tradable) is not bool or type(fractional) is not bool:
        raise AccessStop("Broker asset tradable/fractionable fields missing")
    raw_min=asset.get("min_order_size")
    raw_increment=asset.get("min_trade_increment")
    min_present=raw_min is not None
    increment_present=raw_increment is not None
    if min_present:
        if _money(raw_min,"asset minimum")<=0:
            raise AccessStop("Broker minimum order size nonpositive")
    if increment_present:
        if _money(raw_increment,"asset increment")<=0:
            raise AccessStop("Broker minimum trade increment nonpositive")
    return {
        "listed_active":status=="active",
        "market_symbol_tradable":tradable,
        "asset_fractionable":fractional,
        "broker_minimum_qty_field_present":min_present,
        "broker_increment_qty_field_present":increment_present,
        # Original quantities are deliberately never persisted.
        "broker_order_minimum_notional_usd_independently_verified":False,
        "customer_eligible_to_trade_this_asset_proven":False,
    }

def assess(*,account:dict,positions:list,orders:list,clock:dict,
           crypto_assets:list,gold_asset:dict,bootstrap:dict,policy:dict,
           control:dict,observed_at_utc:str)->dict:
    try:
        inspected=four.check_account(
            account=account,positions=positions,orders=orders,clock=clock,
            bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
            observed_at_utc=observed_at_utc)
    except Exception:
        raise AccessStop("Original authenticated LIVE account binding invalid") from None
    if (inspected.get("broker_get_requests")!=4
        or inspected.get("historic_four_original_etf_quantities_reconciled") is not True
        or inspected.get("original_operator_stopped") is not True
        or inspected.get("account_binding_matches_original_policy") is not True
        or inspected.get("open_order_count")!=0
        or policy.get("crypto_allowed") is not False
        or policy.get("live_order_authorization_present") is not False
        or policy.get("capital_ceiling_usd")!="130.30"
        or "GLD" in policy.get("execution_universe",[])
        or control.get("trading_enabled") is not False):
        raise AccessStop("Original fund authorization/STOP cannot be extended")
    if (type(crypto_assets) is not list or len(crypto_assets)>150
        or type(gold_asset) is not dict):
        raise AccessStop("Malformed original live asset source")
    matches=[a for a in crypto_assets if type(a) is dict and
             a.get("symbol") in ("BTC/USD","BTCUSD")]
    if len(matches)>1:
        raise AccessStop("Duplicate/ambiguous BTC USD asset aliases")
    if matches:
        bitcoin=_asset(matches[0],symbol="BTC/USD")
        crypto_present=True
    else:
        bitcoin={
            "listed_active":False,"market_symbol_tradable":False,
            "asset_fractionable":False,
            "broker_minimum_qty_field_present":False,
            "broker_increment_qty_field_present":False,
            "broker_order_minimum_notional_usd_independently_verified":False,
            "customer_eligible_to_trade_this_asset_proven":False}
        crypto_present=False
    gold=_asset(gold_asset,symbol="GLD")
    state=account.get("crypto_status")
    state_known=state in ("ACTIVE","INACTIVE","SUBMISSION_FAILED")
    if state is not None and not state_known:
        # Trading API may omit the Broker API customer crypto-status field.
        state_known=False
    equity=_money(account.get("equity"),"original equity")
    cash=_money(account.get("cash"),"original cash")
    if equity<=0 or cash>equity*Decimal("1.001"):
        raise AccessStop("Unreconciled customer asset/cash ceiling")
    # Publish only the original fixed capital mandate ceiling. Deriving
    # notional from live equity (even at 5%) would disclose the customer
    # balance indirectly; the real equity is checked privately above.
    btc_upper=(CAP*BTC_TARGET).quantize(Decimal(".01"),rounding=ROUND_DOWN)
    gold_upper=(CAP*GLD_TARGET).quantize(Decimal(".01"),rounding=ROUND_DOWN)
    if btc_upper<=0 or gold_upper<=0:
        raise AccessStop("Zero attainable microaccount target")
    # A 5% allocation cannot exceed $6.51 under the original $130.30 cap.
    return {
        "schema":SCHEMA,"status":"REAL_ACCOUNT_GET_ONLY_INSTRUMENT_FEASIBILITY_NOT_AN_ORDER",
        "observed_at_utc":observed_at_utc,
        "original_bound_high_risk_account_verified":True,
        "original_live_positions_and_no_open_orders_reconciled":True,
        "original_high_live_stop_and_engaged_kill":True,
        "BTC_USD_source_present":crypto_present,
        "BTC_USD_asset_capabilities":bitcoin,
        "GLD_asset_capabilities":gold,
        "account_crypto_status_field_present":state_known,
        "account_crypto_status_indicates_active":state=="ACTIVE" if state_known else None,
        "individual_legal_crypto_jurisdiction_eligibility_verified":False,
        "crypto_agreements_independently_verified":False,
        "BTC_USD_account_permission_verified":False,
        "BTC_USD_sufficient_minimum_notional_verified":False,
        "GLD_account_fractional_trade_eligibility_verified":False,
        "5pct_BTC_theoretical_upper_notional_usd":str(btc_upper),
        "5pct_GLD_theoretical_upper_notional_usd":str(gold_upper),
        "original_fund_capital_ceiling_usd":"130.30",
        "reported_account_cash_above_BTC_theoretical_target":bool(cash>=btc_upper),
        "reported_cash_is_settled_funds_proven":False,
        "holdings_sale_settlement_or_same_day_reinvestment_proven":False,
        "broker_original_live_crypto_policy_allowed":False,
        "broker_original_live_GLD_in_whitelist":False,
        "asset_metadata_does_not_prove_individual_customer_access":True,
        "order_book_spread_quote_and_rebalance_tax_not_queried":True,
        "portfolio_performance_backtest_or_alpha_proven":False,
        "user_requested_future_autonomous_decisions_without_per_trade_approval":True,
        "broker_gets":len(EXPECTED_PATHS),
        "broker_non_gets":BROKER_NON_GETS,"broker_orders":BROKER_ORDERS,
        "paper_authorized":False,"live_authorized":False,
        "trading_authorized":False,
        "broker_account_id":None,"position_sizes":None,
        "account_cash":None,"account_equity":None,
        "asset_minimum_quantities":None,"broker_raw_asset_payloads":None,
    }

def runtime():
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"
        or os.getenv("FUND100_LIVE_WRITE_MODE","DISABLED")!="DISABLED"):
        raise AccessStop("Original protected stopped HIGH main only")
    boot,_=originals.original(four.BOOT)
    policy,_=originals.original(four.POLICY)
    control,_=originals.original(four.CONTROL)
    if (operator.validate_control(operator.read_current_control()) is not False
        or policy.get("crypto_allowed") is not False
        or policy.get("live_order_authorization_present") is not False):
        raise AccessStop("Original source policy has not remained stopped")
    live.require_readonly_arm()
    key,secret=live.load_credentials()
    calls=[]
    def read(path,params=None):
        if path not in EXPECTED_PATHS or (path=="/v2/orders"
            and params!=ORDER_QUERY) or (path=="/v2/assets"
            and params!=CRYPTO_QUERY) or (path not in
            ("/v2/orders","/v2/assets") and params is not None):
            raise AccessStop("Unapproved read-only brokerage endpoint")
        calls.append(path)
        try:
            return live.get_json(path=path,key=key,secret=secret,params=params)
        except Exception:
            raise AccessStop("LIVE GET source unavailable; broker private response withheld") from None
    a=read("/v2/account")
    p=read("/v2/positions")
    o=read("/v2/orders",ORDER_QUERY)
    c=read("/v2/clock")
    x=read("/v2/assets",CRYPTO_QUERY)
    gold=read("/v2/assets/GLD")
    if tuple(calls)!=EXPECTED_PATHS or operator.validate_control(
        operator.read_current_control()) is not False:
        raise AccessStop("Six GET order/remote operator STOP invariant violated")
    return assess(
        account=a,positions=p,orders=o,clock=c,crypto_assets=x,gold_asset=gold,
        bootstrap=boot,policy=policy,control=control,
        observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

def main():
    status=runtime()
    for key in ("status","observed_at_utc",
                "original_bound_high_risk_account_verified",
                "BTC_USD_source_present",
                "BTC_USD_asset_capabilities","GLD_asset_capabilities",
                "account_crypto_status_field_present",
                "account_crypto_status_indicates_active",
                "5pct_BTC_theoretical_upper_notional_usd",
                "5pct_GLD_theoretical_upper_notional_usd",
                "reported_account_cash_above_BTC_theoretical_target",
                "BTC_USD_account_permission_verified","BTC_USD_sufficient_minimum_notional_verified",
                "broker_original_live_crypto_policy_allowed",
                "broker_original_live_GLD_in_whitelist",
                "broker_gets","broker_non_gets","broker_orders",
                "live_authorized"):
        print(key+":",status[key])
    print("Original broker account identifiers, portfolio valuations, private fills, and source payloads withheld.")

if __name__=="__main__":main()

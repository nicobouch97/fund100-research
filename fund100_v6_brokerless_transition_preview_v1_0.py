"""Fund-100 V6 no-order LIVE ETF transition *preview*, not a trade planner.

The existing LIVE bootstrap provides historical filled quantities, not
today's mark or cash. Never assume those historical positions are still
held, that sales were permitted, or that sales settle as buying power.
Only source-bound, explicitly read-only CURRENT broker observations can
produce hypothetical exit values; this module has no broker client,
no API URLs and NO order endpoints.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from decimal import Decimal, InvalidOperation,ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path

SCHEMA="FUND100_V6_NO_ORDER_TRANSITION_PREVIEW_V1"
SNAPSHOT_SCHEMA="FUND100_FRESH_GET_ONLY_POSITION_MARKS_V1"
BOOTSTRAP_SCHEMA="FUND100_LIVE_MICRO_PILOT_BOOTSTRAP_V1"
POLICY_SCHEMA="FUND100_LIVE_MICRO_PILOT_POLICY_V1_1"
CONTROL_SCHEMA="FUND100_OPERATOR_CONTROL_V1"
ORIGINAL_CAP=Decimal("130.30")
COST_BPS=(5,15,35)
EXPECTED_SYMBOLS={"ACWI","EEM","XLE","XLV"}


class TransitionStop(ValueError):
    pass


def positive(value,field:str,allow_zero:bool=False)->Decimal:
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):
        raise TransitionStop("Invalid decimal input: "+field)
    try:
        d=Decimal(str(value))
    except InvalidOperation as exc:
        raise TransitionStop("Unparseable decimal: "+field) from exc
    if not d.is_finite() or d<0 or (not allow_zero and d==0):
        raise TransitionStop("Out of range decimal: "+field)
    return d


def original(path:Path)->tuple[dict,str]:
    raw=path.read_bytes()
    if not raw or len(raw)>100_000:
        raise TransitionStop("Missing/oversized exact original repo file.")
    try:
        value=json.loads(raw.decode("utf8"))
    except (ValueError,UnicodeError) as exc:
        raise TransitionStop("Invalid original JSON.") from exc
    if not isinstance(value,dict):
        raise TransitionStop("Original JSON must be object.")
    return value,sha256(raw).hexdigest()


def check_original(bootstrap:dict,policy:dict,control:dict)->dict:
    if (bootstrap.get("schema")!=BOOTSTRAP_SCHEMA
        or policy.get("schema")!=POLICY_SCHEMA
        or control.get("schema")!=CONTROL_SCHEMA
        or control.get("trading_enabled") is not False
        or policy.get("strategy")!="V5-002_SHADOW"
        or bootstrap.get("strategy")!="V5-002_SHADOW"
        or policy.get("deployment_mode")!="LIVE_MICRO_PILOT"
        or bootstrap.get("broker_environment")!="ALPACA_LIVE"
        or bootstrap.get("bootstrap_complete") is not True
        or policy.get("live_order_authorization_present") is not False
        or policy.get("autonomous_strategy_event_execution_enabled") is not False
        or policy.get("leverage_allowed") is not False
        or policy.get("crypto_allowed") is not False
        or policy.get("shorting_allowed") is not False
        or policy.get("options_allowed") is not False
        or policy.get("additional_deposits_automatically_usable") is not False
        or bootstrap.get("duplicate_live_posts")!=0
        or bootstrap.get("live_post_requests")!=4
        or bootstrap.get("reconciliation",{}).get("open_orders")!=0
        or set(bootstrap.get("orders",{}))!=EXPECTED_SYMBOLS
        or set(bootstrap.get("target_notionals_usd",{}))!=EXPECTED_SYMBOLS
        or bootstrap.get("account_binding_sha256")!=policy.get("account_binding_sha256")
        or bootstrap.get("manifest_sha256")!=policy.get("authorized_manifest_sha256")
        or positive(bootstrap.get("pilot_ceiling_usd"),"bootstrap cap")!=ORIGINAL_CAP
        or positive(policy.get("capital_ceiling_usd"),"policy cap")!=ORIGINAL_CAP):
        raise TransitionStop("Original LIVE policy, stops or bootstrap chain changed.")
    amounts={}
    for symbol,item in bootstrap["orders"].items():
        if item.get("status")!="filled":
            raise TransitionStop("Original bootstrap contains nonfilled position.")
        amounts[symbol]=positive(item.get("filled_qty"),symbol+" filled quantity")
        positive(item.get("filled_avg_price"),symbol+" historical filled price")
    return amounts


def _at(time:str)->datetime:
    try:
        d=datetime.strptime(time,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError,TypeError) as exc:
        raise TransitionStop("Snapshot UTC must be canonical ISO second precision.") from exc
    if d.strftime("%Y-%m-%dT%H:%M:%SZ")!=time:
        raise TransitionStop("Noncanonical original snapshot clock.")
    return d


def preview(bootstrap:dict,policy:dict,control:dict,
            *,source_hashes:dict[str,str],
            generated_at_utc:str,
            fresh_broker_snapshot:dict|None=None)->dict:
    filled=check_original(bootstrap,policy,control)
    now=_at(generated_at_utc)
    if set(source_hashes)!={"bootstrap_sha256","policy_sha256","control_sha256"}:
        raise TransitionStop("Missing original checked-in policy provenance.")
    if any(not isinstance(s,str) or len(s)!=64 for s in source_hashes.values()):
        raise TransitionStop("Original SHA fingerprints not provided.")
    result={
        "schema":SCHEMA,
        "source_only_historical_bootstrap":True,
        "original_source_sha256":source_hashes,
        "generated_at_utc":generated_at_utc,
        "original_authorized_usd_cap":str(ORIGINAL_CAP),
        "historical_real_filled_quantities":{k:str(v) for k,v in sorted(filled.items())},
        "historical_fills_are_not_fresh_current_holdings":True,
        "historical_filled_prices_are_not_current_market_prices":True,
        "live_quotes_or_current_cash_known":False,
        "live_position_liquidation_authorized":False,
        "new_strategy_name_verified_and_promoted":False,
        "next_strategy_weights_authorized":False,
        "reinvest_sold_proceeds_or_new_deposits_authorized":False,
        "fresh_broker_cash_settlement_checked":False,
        "broker_kill_switch_current_environment_value_checked":False,
        "broker_orders":0,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
        "estimated_sale_values_are_real_market_observations":False,
        "next_actions":[
            "CHOOSE_NEW_INDEPENDENTLY_EVIDENCED_STRATEGY",
            "EXPLICIT_USER_APPROVAL_FOR_LIVE_PORTFOLIO_SELLS_AND_NEW_RISK",
            "FRESH_GET_ONLY_ACCOUNT_POSITIONS_CASH_ORDERS_QUOTES",
            "VERIFY_US_EQUITY_CASH_SETTLEMENT_AND_MINIMUM_ORDER_NOTIONALS",
            "SEPARATE_CAP_AND_WHITELIST_RELEASE_WITH_KILL_SWITCH",
        ],
    }
    if fresh_broker_snapshot is None:
        result["status"]="NO_FRESH_READ_ONLY_MARKS_NO_EXIT_VALUATION"
        result["hypothetical_sale_proceeds_usd"]=None
        result["current_live_equity_usd"]=None
        return result

    snapshot=fresh_broker_snapshot
    if (not isinstance(snapshot,dict) or snapshot.get("schema")!=SNAPSHOT_SCHEMA
        or snapshot.get("request_method")!="GET_ONLY"
        or snapshot.get("account_binding_sha256")!=policy["account_binding_sha256"]
        or snapshot.get("open_orders")!=0
        or snapshot.get("includes_pending_transfers") is not False
        or snapshot.get("read_only_proven") is not True
        or snapshot.get("real_orders_submitted")!=0):
        raise TransitionStop("No authenticated fresh broker GET-only account observation.")
    when=_at(snapshot.get("observed_at_utc"))
    if now<when or (now-when).total_seconds()>3600*24:
        raise TransitionStop("Broker GET-only observation expired or future dated.")
    current=snapshot.get("positions")
    if not isinstance(current,dict) or set(current)!=EXPECTED_SYMBOLS:
        raise TransitionStop("Four original positions must be reconciled, not assumed.")
    gross=Decimal("0")
    for s,original_qty in filled.items():
        item=current[s]
        if not isinstance(item,dict):
            raise TransitionStop("Invalid position mark row.")
        qty=positive(item.get("quantity"),s+" current quantity")
        price=positive(item.get("last_trade_price_usd"),s+" live mark")
        if abs(qty-original_qty)>Decimal("0.00000001"):
            raise TransitionStop("Position quantity changed since bootstrap; new manual reconciliation needed.")
        gross+=qty*price
    cash=positive(snapshot.get("cash_usd"),"broker cash",allow_zero=True)
    estimated={}
    for bps in COST_BPS:
        charge=gross*Decimal(bps)/Decimal(10_000)
        estimated[str(bps)]={
            "gross_hypothetical_sale_value_usd":str(gross.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
            "modelled_all_in_sale_friction_usd":str(charge.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
            "modelled_net_sale_value_usd":str((gross-charge).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
            "cash_plus_sale_value_usd_before_settlement":str((cash+gross-charge).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
        }
    result["status"]="HYPOTHETICAL_EXIT_ONLY_NOT_ORDER_AUTHORIZED"
    result["live_quotes_or_current_cash_known"]=True
    result["estimated_sale_values_are_real_market_observations"]=True
    result["fresh_broker_cash_settlement_checked"]=False
    result["observed_at_utc"]=snapshot["observed_at_utc"]
    result["current_live_equity_usd"]=None  # Holdings + cash != broker total account equity.
    result["hypothetical_sale_proceeds_usd"]=estimated
    result["hypothetical_exit_uses_unchanged_original_filled_quantities"]=True
    result["estimated_friction_is_not_a_broker_filled_fee_quote"]=True
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bootstrap",type=Path,default=Path("live_activation_outputs/v5_002/live_bootstrap_v1_0.json"))
    p.add_argument("--policy",type=Path,default=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"))
    p.add_argument("--control",type=Path,default=Path("fund100_live_operator_control.json"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    boot,bh=original(a.bootstrap)
    policy,ph=original(a.policy)
    control,ch=original(a.control)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # CLI does not accept quote files. The future read-only broker
    # preflight should call preview() after independent freshness checks.
    report=preview(boot,policy,control,
        source_hashes={"bootstrap_sha256":bh,"policy_sha256":ph,"control_sha256":ch},
        generated_at_utc=now)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("V6 TRANSITION:",report["status"],
          "historical_filled_names",len(report["historical_real_filled_quantities"]),
          "LATEST_MARKS_AVAILABLE",report["live_quotes_or_current_cash_known"])
    print("NO LIQUIDATION, NO NEW STRATEGY SELECTED, NO BROKER GET/POST, NO ORDERS.")


if __name__=="__main__":
    main()

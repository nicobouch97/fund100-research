"""Fund-100 C9: size-aware instrument feasibility, NO BROKER and NO ORDERS.

Reject trading pathways that cannot meet ORIGINAL account capital/risk
scope. CME initial margin data is dated source *estimate*, not a
customer-specific broker quote or order authorisation. Research only.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path

SCHEMA="FUND100_C9_MICROACCOUNT_INSTRUMENT_FEASIBILITY_V1"
EXPECTED_POLICY_SCHEMA="FUND100_LIVE_MICRO_PILOT_POLICY_V1_1"
EXPECTED_OPERATOR_SCHEMA="FUND100_OPERATOR_CONTROL_V1"
EXPECTED_CAP=Decimal("130.30")
# CME https://www.cmegroup.com/markets/energy/wti-crude-oil-futures.html
# Published illustrative margin NOT actual customer broker margin.
CME_MARGIN_ESTIMATE_ASOF="2026-07-07"
CME_OFFICIAL_URL="https://www.cmegroup.com/markets/energy/wti-crude-oil-futures.html"
# Dollar minimum estimates; these can change at any time.
FUTURES=(
    {"symbol":"CL","name":"NYMEX WTI crude oil futures","barrels":1000,
     "margin_usd":"6826","physical_delivery":True},
    {"symbol":"QM","name":"NYMEX E-mini WTI crude oil futures","barrels":500,
     "margin_usd":"3423","physical_delivery":False},
    {"symbol":"MCL","name":"NYMEX Micro WTI crude oil futures","barrels":100,
     "margin_usd":"685","physical_delivery":False},
)
# See CME 2026 "coming soon" with pending regulatory review.
SMALLER_PENDING={
    "symbol":"10_BARREL_WTI_PENDING","barrels":10,"listed_and_tradable_verified":False,
    "margin_usd":None,
    "reference_url":"https://www.cmegroup.com/markets/energy/crude-oil/micro-wti-crude-oil.html",
}
ETP_CANDIDATES=(
    {"symbol":"GLD","category":"gold_etf","underlying":"gold"},
    {"symbol":"USO","category":"oil_futures_fund","underlying":"oil_futures_roll_index"},
    {"symbol":"SHY","category":"short_treasury_etf","underlying":"US_treasury_1_3_year"},
    {"symbol":"XLE","category":"energy_equity_etf","underlying":"energy_company_equity_not_crude_oil"},
)
CRYPTO_CANDIDATES=("BTC/USD","ETH/USD")
EXPECTED_EXISTING={
    "ACWI","SPY","IWM","EFA","EEM","VNQ","XLK","XLF","XLI",
    "XLV","XLP","XLY","XLE","XLU",
}


class FeasibilityStop(ValueError):
    pass


def original_json(path:Path)->tuple[dict,str]:
    raw=path.read_bytes()
    if not raw or len(raw)>50_000:
        raise FeasibilityStop("Missing or oversized source controls.")
    try:
        result=json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeDecodeError) as exc:
        raise FeasibilityStop("Cannot parse original account controls.") from exc
    if not isinstance(result,dict):
        raise FeasibilityStop("Original control document must be an object.")
    return result,sha256(raw).hexdigest()


def examine(policy:dict,operator:dict,*,source_shas:dict[str,str])->dict:
    if (
        policy.get("schema")!=EXPECTED_POLICY_SCHEMA
        or policy.get("deployment_mode")!="LIVE_MICRO_PILOT"
        or policy.get("strategy")!="V5-002_SHADOW"
        or type(policy.get("execution_universe")) is not list
        or len(policy["execution_universe"])!=len(EXPECTED_EXISTING)
        or set(policy["execution_universe"])!=EXPECTED_EXISTING
        or policy.get("additional_deposits_automatically_usable") is not False
        or policy.get("crypto_allowed") is not False
        or policy.get("leverage_allowed") is not False
        or policy.get("shorting_allowed") is not False
        or policy.get("options_allowed") is not False
        or policy.get("live_order_authorization_present") is not False
        or policy.get("autonomous_strategy_event_execution_enabled") is not False
        or operator.get("schema")!=EXPECTED_OPERATOR_SCHEMA
        or operator.get("trading_enabled") is not False
    ):
        raise FeasibilityStop("Original controlled ETF LIVE STOP policy changed: fail closed.")
    try:
        cap=Decimal(str(policy["capital_ceiling_usd"]))
    except (KeyError,InvalidOperation) as exc:
        raise FeasibilityStop("Invalid original broker authorization ceiling.") from exc
    if not cap.is_finite() or cap!=EXPECTED_CAP:
        raise FeasibilityStop("Capital cap changed; do not reuse feasibility judgement.")
    if (set(source_shas)!={"operator_sha256","live_policy_sha256"}
        or any(not isinstance(v,str) or len(v)!=64 for v in source_shas.values())):
        raise FeasibilityStop("Original hash provenance absent.")
    existing=set(policy["execution_universe"])
    futures=[]
    for item in FUTURES:
        required=Decimal(item["margin_usd"])
        futures.append({
            **item,
            "cme_estimate_asof":CME_MARGIN_ESTIMATE_ASOF,
            "cme_official_spec_url":CME_OFFICIAL_URL,
            "published_margin_multiple_of_total_authorized_cap":str((required/cap).quantize(Decimal(".01"))),
            "required_margin_above_ceiling_usd":str(required-cap),
            "margin_estimate_cannot_verify_broker_eligibility":True,
            "fundable_under_entire_cap_estimate":bool(required<=cap),
            "leverage_futures_broker_authorized":False,
            "live_order_permitted":False,
            "reason":"ESTIMATED_MARGIN_EXCEEDS_CAP_AND_FUTURES_NOT_AUTHORIZED",
        })
    etps=[]
    for cand in ETP_CANDIDATES:
        allowed=cand["symbol"] in existing
        etps.append({
            **cand,
            "is_present_in_existing_14_etf_live_universe":allowed,
            "can_buy_without_explicit_operator_strategy_transition":False,
            "fractional_support_and_account_tradability_verified":False,
            "current_available_cash_retrieved":False,
            "is_equivalent_to_direct_CL_futures_contract":False,
            "reason":(
                "EXISTING_EQUITY_SECTOR_ETF_NOT_OIL_FUTURES_AND_OPERATOR_STOPPED"
                if allowed else
                "RESEARCH_ONLY_ETP_NOT_IN_EXISTING_LIVE_UNIVERSE"
            ),
        })
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_MARKET_ACCESS_REVIEW_NO_LIVE_APPROVAL",
        "original_source_controls_sha256":source_shas,
        "original_authorized_cap_usd":str(cap),
        "funds_currently_available_to_buy_usd":None,
        "existing_live_holdings_not_liquidated":True,
        "operator_stopped":True,
        "broker_kill_switch_engaged_from_last_verified_audit":True,
        "broker_kill_switch_fresh_environment_value_measured":False,
        "risk_tier_high_was_operator_selected":True,
        "live_existing_etf_count_allowed":len(existing),
        "existing_live_whitelist_expansion_authorized":False,
        "broker_margin_account_verified":False,
        "futures_margin_are_illustrative_cme_estimates_not_current_broker_quotes":True,
        "futures":futures,
        "proposed_10_barrel_cme_contract":SMALLER_PENDING,
        "commodity_etf_expressions":etps,
        "crypto": [{
            "symbol":s,"current_existing_live_allowed":False,
            "account_crypto_eligibility_verified":False,
            "new_crypto_live_permission":False,
        } for s in CRYPTO_CANDIDATES],
        "next_research_requirements":[
            "ACTUAL_DATED_FINAL_CONTRACT_SETTLEMENT_SERIES",
            "VALIDATED_ROLL_EXPIRY_AND_ETP_TRACKING",
            "COSTED_POSITIVE_EXPECTED_SIGNAL_BEYOND_BACKTEST_SELECTION",
            "FRESH_GET_ONLY_CUSTOMER_TRADABILITY_AND_AVAILABLE_CASH",
            "EXPLICIT_VERSIONED_OPERATOR_SELL_AND_BUY_CONSENT",
        ],
        "direct_physical_or_margin_futures_order_viable":False,
        "live_strategy_transition_authorized":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
        "broker_orders":0,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--live-policy",type=Path,default=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"))
    p.add_argument("--operator",type=Path,default=Path("fund100_live_operator_control.json"))
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    policy,ph=original_json(args.live_policy)
    operator,oh=original_json(args.operator)
    result=examine(policy,operator,source_shas={"live_policy_sha256":ph,"operator_sha256":oh})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    for x in result["futures"]:
        print(x["symbol"],"indicative_margin_USD",x["margin_usd"],
              "vs_authorized_cap",result["original_authorized_cap_usd"],
              "MARGIN_MULTIPLE",x["published_margin_multiple_of_total_authorized_cap"],
              "EXECUTION_PERMIT",x["live_order_permitted"])
    for x in result["commodity_etf_expressions"]:
        print(x["symbol"],x["reason"])
    print("NO BROKER QUOTES / NO CASH READ / NO TRADE ORDERS / NO LIQUIDATION.")


if __name__=="__main__":
    main()

"""Fund-100 V7-X4: executable-sized BTC/GLD targets vs cash/authority.

BROKERLESS, RESEARCH ONLY. All future funding figures are hypothetical,
not evidence that a deposit occurred, settlement completed, or authority
increased. This model is an economic notional feasibility filter, NOT a
prediction, order generator, tax estimate, quote, cash broker adapter or
customer entitlement. Minimums are explicit SCENARIOS: Alpaca's separate
Broker API docs say $10 equivalent for USD crypto; Trading API account
minimum was not authenticated. Never silently take docs as a LIVE quote.
"""
from __future__ import annotations

import argparse
from decimal import Decimal,InvalidOperation,ROUND_DOWN,ROUND_UP
import json
import re
from pathlib import Path

SCHEMA="FUND100_V7_X4_SCALABLE_CRYPTO_GOLD_REBALANCE_CAPITAL_FEASIBILITY_V1"
ORIGINAL_CAP=Decimal("130.30")
ORIGINAL_STOP=True
CENTS=Decimal(".01")
BTC_WEIGHT=Decimal(".05")
GLD_WEIGHT=Decimal(".05")
CASH_WEIGHT=Decimal(".15")
EQUITIES={"XLK":Decimal(".375"),"XLE":Decimal(".225"),"IWM":Decimal(".15")}
SCENARIOS=(("BTC_MIN_1_USD","1.00"),("BTC_MIN_5_USD","5.00"),
           ("BTC_MIN_10_USD","10.00"),("BTC_MIN_20_USD","20.00"))
SIZES=("130.30","200.00","200.70","250.00","500.00","1000.00","5000.00")
BROKER_MIN_NOTIONAL_USD_VERIFIED=False
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
BTC_COST_BPS=Decimal("35")
BTC_HIGH_COST_BPS=Decimal("60")
ETF_COST_BPS=Decimal("15")
GOLD_MIN_USD_SCENARIO=Decimal("1.00")
FUTURE_MANDATE_ENABLED=False

class FundSizingStop(ValueError):pass

def decimal(raw,label:str,*,allow_zero=False):
    if type(raw) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.\d{1,2})?",raw):
        raise FundSizingStop("Invalid canonical decimal "+label)
    try:v=Decimal(raw)
    except InvalidOperation:raise FundSizingStop("Invalid decimal "+label) from None
    if (not v.is_finite() or v<0 or (not allow_zero and v<=0)):
        raise FundSizingStop("Invalid amount "+label)
    return v

def down(v):
    return v.quantize(CENTS,rounding=ROUND_DOWN)

def up(v):
    return v.quantize(CENTS,rounding=ROUND_UP)

def acquisition(*,notional_budget:Decimal,min_notional:Decimal,side_bps:Decimal):
    """Largest cent-order notional whose trade + costs fit risk weight.
    Only modelled cost, not a real crypto spread, tax or minimum quote."""
    if min_notional<=0 or side_bps<0 or notional_budget<0:
        raise FundSizingStop("Invalid size inputs")
    model_fraction=side_bps/Decimal(10000)
    notional=down(notional_budget/(Decimal(1)+model_fraction))
    cost=up(notional*model_fraction)
    # Rounding UP a fee can exceed the budget at the rounded-notional
    # boundary; reduce by one cent until BOTH legs fit.
    while notional>0 and notional+cost>notional_budget:
        notional-=CENTS
        cost=up(notional*model_fraction)
    passed=notional>=min_notional
    return {
        "quoted_minimum_equivalent_notional_scenario_usd":str(min_notional),
        "maximum_gross_order_notional_usd":str(notional),
        "conservative_buy_fee_allowance_usd":str(cost),
        "full_cash_required_if_bought_usd":str(notional+cost),
        "minimum_notional_passes_scenario":passed,
        "BTC_minimum_actual_broker_source_verified":False,
        "broker_order_build_allowed":False,
    }

def inspect(*,hypothetical_account_equity_usd:str,
            prospective_authorized_ceiling_usd:str,
            independently_verified_settled_cash_usd:str,
            btc_minimum_notional_scenario_usd:str,
            btc_fee_bps:Decimal=BTC_COST_BPS)->dict:
    equity=decimal(hypothetical_account_equity_usd,"hypothetical account balance")
    ceiling=decimal(prospective_authorized_ceiling_usd,"candidate capital ceiling")
    settled=decimal(independently_verified_settled_cash_usd,"hypothetical settled cash",allow_zero=True)
    minimum=decimal(btc_minimum_notional_scenario_usd,"hypothetical BTC minimum")
    if (equity<Decimal("20") or ceiling<ORIGINAL_CAP
        or settled>equity or btc_fee_bps not in (BTC_COST_BPS,BTC_HIGH_COST_BPS)):
        raise FundSizingStop("Unqualified funded/capped model or unregistered crypto cost")
    permitted_basis=min(equity,ceiling)
    btc_budget=permitted_basis*BTC_WEIGHT
    gold_budget=permitted_basis*GLD_WEIGHT
    if any(v<0 for v in EQUITIES.values()) or sum(EQUITIES.values(),Decimal(0))+BTC_WEIGHT+GLD_WEIGHT+CASH_WEIGHT!=1:
        raise FundSizingStop("Original 75 equity / 5 BTC / 5 gold /15 cash mismatch")
    btc=acquisition(notional_budget=btc_budget,min_notional=minimum,side_bps=btc_fee_bps)
    gold=acquisition(notional_budget=gold_budget,min_notional=GOLD_MIN_USD_SCENARIO,side_bps=ETF_COST_BPS)
    basket={k:str(down(permitted_basis*w)) for k,w in EQUITIES.items()}
    combined_cash=Decimal(btc["full_cash_required_if_bought_usd"])+Decimal(gold["full_cash_required_if_bought_usd"])
    shortfall=max(Decimal(0),combined_cash-settled)
    funding_status=("ILLUSTRATIVE_SETTLED_CASH_COVERS_BOTH_BUYS"
                    if shortfall<=0 else
                    "ILLUSTRATIVE_SELL_FIRST_AWAIT_AUTHENTICATED_SETTLEMENT")
    minimum_feasible=btc["minimum_notional_passes_scenario"] and gold["minimum_notional_passes_scenario"]
    # Extra deposits must not silently expand the original deployment
    # ceiling. A larger ceiling is a labelled FUTURE hypothetical only.
    original_deployable=min(equity,ORIGINAL_CAP)
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_CAPITAL_TIER_FEASIBILITY_NOT_A_LIVE_ALLOCATION",
        "hypothetical_equity_usd":str(equity),
        "hypothetical_authorized_ceiling_usd":str(ceiling),
        "model_deployable_basis_usd":str(permitted_basis),
        "amount_above_model_authorized_ceiling_usd":str(max(Decimal(0),equity-ceiling)),
        "current_original_authorization_still_usd":str(ORIGINAL_CAP),
        "current_live_policy_deployable_at_this_balance_if_not_changed_usd":str(original_deployable),
        "future_cap_increase_not_granted_by_this_study":True,
        "original_trading_stop_and_kill_remain_engaged":True,
        "original_cash_value_not_fetched":True,
        "original_holdings_not_sold":True,
        "hypothetical_settled_cash_usd":str(settled),
        "synthetic_settlement_input_is_not_authenticated":True,
        "constant_stock_allocation_targets_usd":basket,
        "bitcoin_weight_target_pct":5,
        "gold_weight_target_pct":5,
        "minimum_cash_reserve_weight_pct":15,
        "minimum_cash_reserve_usd":str(down(permitted_basis*CASH_WEIGHT)),
        "bitcoin_buy":btc,
        "gold_buy":gold,
        "two_new_sleeves_total_buy_notional_and_cost_usd":str(combined_cash),
        "hypothetical_remaining_shortfall_to_wait_settlement_usd":str(shortfall),
        "two_leg_funding_status":funding_status,
        "two_legs_pass_declared_order_minimum_scenarios":minimum_feasible,
        "market_price_qty_increment_and_live_crypto_fee_are_unverified":True,
        "short_leg_notional_alone_cannot_determine_executable_crypto_quantity":True,
        "broker_account_crypto_status_last_known_active_but_not_order_proof":True,
        "broker_source_BTC_USD_and_GLD_last_known_listed_fractionable":True,
        "BTC_and_GLD_not_current_live_whitelist":True,
        "cash_from_current_inventory_sell_not_assumed_settled":True,
        "autonomous_eventual_approval_is_by_versioned_strategy_not_each_order":True,
        "no_live_orders_or_permission_issued":True,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,
        "paper_authorized":False,"live_authorized":False,
        "trading_authorized":False,
    }

def required_capital_for_btc_minimum(minimum:str,side_bps:Decimal=BTC_COST_BPS)->str:
    value=decimal(minimum,"BTC minimum notional")
    if side_bps not in (BTC_COST_BPS,BTC_HIGH_COST_BPS):
        raise FundSizingStop("Unreviewed fee sensitivity")
    # BTC notional min and rounded-up per-side cash fee must fit INSIDE
    # the full 5% sleeve notional budget; all figures round to cents.
    funding=up(value+up(value*side_bps/Decimal(10000)))
    return str(up(funding/BTC_WEIGHT))

def analyze()->dict:
    snapshots={}
    for fee in (BTC_COST_BPS,BTC_HIGH_COST_BPS):
        cases={}
        for scenario,minimum in SCENARIOS:
            tiers=[]
            for equity in SIZES:
                # Two explicit deployment-policy states for each tier:
                # original unchanged $130.30 ceiling, versus future
                # separately-reviewed hypothetical ceiling matching equity.
                current=inspect(hypothetical_account_equity_usd=equity,
                    prospective_authorized_ceiling_usd="130.30",
                    independently_verified_settled_cash_usd="0",
                    btc_minimum_notional_scenario_usd=minimum,
                    btc_fee_bps=fee)
                prospective=inspect(hypothetical_account_equity_usd=equity,
                    prospective_authorized_ceiling_usd=equity,
                    independently_verified_settled_cash_usd="0",
                    btc_minimum_notional_scenario_usd=minimum,
                    btc_fee_bps=fee)
                tiers.append({
                    "hypothetical_total_account_usd":equity,
                    "CURRENT_UNCHANGED_130_30_LIMIT":{
                        "deployable_usd":current["model_deployable_basis_usd"],
                        "BTC_min_pass":current["bitcoin_buy"]["minimum_notional_passes_scenario"],
                        "both_leg_min_pass":current["two_legs_pass_declared_order_minimum_scenarios"]},
                    "FUTURE_SEPARATELY_AUTHORIZED_FULL_CEILING":{
                        "deployable_usd":prospective["model_deployable_basis_usd"],
                        "BTC_min_pass":prospective["bitcoin_buy"]["minimum_notional_passes_scenario"],
                        "both_leg_min_pass":prospective["two_legs_pass_declared_order_minimum_scenarios"],
                        "BTC_order_notional_usd":prospective["bitcoin_buy"]["maximum_gross_order_notional_usd"],
                        "GLD_order_notional_usd":prospective["gold_buy"]["maximum_gross_order_notional_usd"],
                        "two_sleeve_cash_required_usd":prospective["two_new_sleeves_total_buy_notional_and_cost_usd"],
                        "cash_settlement_gap_when_no_cash_usd":prospective["hypothetical_remaining_shortfall_to_wait_settlement_usd"]},
                })
            cases[scenario]={
                "bitcoin_minimum_notional_usd":minimum,
                "required_prospective_capital_with_purchase_fee_usd":
                    required_capital_for_btc_minimum(minimum,fee),
                "funding_tiers":tiers}
        snapshots[str(int(fee))]=cases
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_ONLY_ACCOUNT_SIZE_AND_SETTLEMENT_SCENARIOS",
        "original_live_capital_ceiling_usd":"130.30",
        "no_capital_increase_or_future_deposit_authorized":True,
        "BTC_minimum_order_Broker_API_example_may_not_apply_to_Trading_API":True,
        "BTC_USD_min_notional_scenarios":[x[1] for x in SCENARIOS],
        "ETF_GLD_min_notional_1_USD_scenario":str(GOLD_MIN_USD_SCENARIO),
        "future_account_and_capital_values_all_synthetic":True,
        "no_customer_balance_or_private_positions_persisted":True,
        "all_cash_buyability_assumes_independently_settled_cash":True,
        "switch_sell_buy_remains_unqualified":True,
        "real_assets_still_not_whitelisted":True,
        "live_authorized":False,"trading_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "scenarios":snapshots}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    d=analyze()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    for name,case in d["scenarios"]["35"].items():
        print(name, "cash/fee-inclusive 5% BTC funding threshold USD",
              case["required_prospective_capital_with_purchase_fee_usd"])
        print(" Future re-authorized hypotheticals: ",
              ", ".join(f"{x['hypothetical_total_account_usd']} => "
                        f"{'MIN PASS' if x['FUTURE_SEPARATELY_AUTHORIZED_FULL_CEILING']['BTC_min_pass'] else 'HOLD'}"
                        for x in case["funding_tiers"]))
    print("Research only. Additional funding does not lift original LIVE cap.")
if __name__=="__main__":main()

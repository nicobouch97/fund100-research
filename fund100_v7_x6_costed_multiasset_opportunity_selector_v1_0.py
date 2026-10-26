"""V7-X6 brokerless costed opportunity ranking using X5 capacity and V6 economics.

Research scenarios only. A forecast is an unqualified user-supplied hypothesis.
NO broker credentials, quote fetch, live selection, order or capital release.
"""
from __future__ import annotations

from decimal import Decimal
import re

import fund100_v7_x5_capacity_aware_portfolio_router_v1_0 as capacity

SCHEMA="FUND100_V7_X6_COSTED_MULTI_ASSET_OPPORTUNITY_CAPACITY_RESEARCH_V1"
MAX_CANDIDATES=8
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
TRADING_AUTHORIZED=False

class SelectionStop(ValueError):
    pass

def _return_fraction(raw, symbol):
    if type(raw) is not str or re.fullmatch(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",raw) is None:
        raise SelectionStop("Invalid synthetic forecast for "+symbol)
    value=Decimal(raw)
    if not Decimal("-1")<=value<=Decimal("2"):
        raise SelectionStop("Out-of-range synthetic forecast for "+symbol)
    return value

def select(*,capital_nav_usd,prospective_cap_usd,settled_cash_usd,
           current_holdings_usd,candidate_target_weights,
           expected_returns_fraction,asset_spec,forecast_horizon_sessions,
           uncertainty_buffer_bps="50",minimum_edge_bps="25"):
    """Compare HOLD with costed hypothetical switches; NEVER return orders."""
    if (type(candidate_target_weights) is not dict
        or not 1<=len(candidate_target_weights)<=MAX_CANDIDATES
        or type(expected_returns_fraction) is not dict
        or type(current_holdings_usd) is not dict
        or type(asset_spec) is not dict
        or type(forecast_horizon_sessions) is not int
        or forecast_horizon_sessions not in (5,21,63)):
        raise SelectionStop("Invalid bounded research opportunity comparison")
    covered=set(current_holdings_usd)
    for name,weights in candidate_target_weights.items():
        if (type(name) is not str
            or re.fullmatch(r"RESEARCH_[A-Z][A-Z0-9_]{2,35}",name) is None
            or type(weights) is not dict or not weights):
            raise SelectionStop("Invalid research candidate label or targets")
        covered.update(weights)
    if set(expected_returns_fraction)!=covered:
        raise SelectionStop("Common-horizon forecasts must cover each held/proposed symbol")
    forecasts={k:_return_fraction(v,k) for k,v in expected_returns_fraction.items()}
    uncertainty=capacity.num(uncertainty_buffer_bps,"forecast uncertainty bps")
    min_edge=capacity.num(minimum_edge_bps,"switching hysteresis bps")
    if uncertainty>Decimal(3000) or min_edge>Decimal(1000):
        raise SelectionStop("Unbounded research switching assumptions")
    nav=capacity.num(capital_nav_usd,"synthetic NAV",positive=True)
    hurdle=max(Decimal("0.50"),nav*min_edge/Decimal(10000))
    outcomes={}
    eligible=[]
    for name in sorted(candidate_target_weights):
        scenario=capacity.route(
            capital_nav_usd=capital_nav_usd,
            prospective_cap_usd=prospective_cap_usd,
            settled_cash_usd=settled_cash_usd,
            current_holdings_usd=current_holdings_usd,
            target_weights=candidate_target_weights[name],
            asset_spec=asset_spec)
        details=scenario["estimated_trade_side_details"]
        turnover=Decimal(0)
        gross_advantage=Decimal(0)
        for side in details.values():
            notional=Decimal(side["hypothetical_notional_usd"])
            sign=Decimal(1) if side["direction"]=="BUY" else Decimal(-1)
            turnover+=notional
            gross_advantage+=sign*notional*forecasts[side["symbol"]]
        fees=Decimal(scenario["modeled_all_sides_fees_usd"])
        uncertainty_cost=turnover*uncertainty/Decimal(10000)
        net=gross_advantage-fees-uncertainty_cost
        if scenario["too_small_or_infeasible_target_warnings"]:
            state="HOLD_MODEL_CAPACITY_OR_POST_COST_RISK"
        elif turnover==0:
            state="HOLD_NO_MATERIAL_SWITCH"
        elif net<=hurdle:
            state="HOLD_INSUFFICIENT_COSTED_EDGE"
        elif scenario["funding_status"]!="HYPOTHETICAL_SETTLED_CASH_SUFFICIENT_ONLY":
            state="RESEARCH_SWITCH_REQUIRES_FUTURE_SETTLEMENT"
        else:
            state="RESEARCH_SWITCH_SYNTHETIC_CASH_SUFFICIENT"
        outcomes[name]={
            "state":state,
            "hypothetical_gross_advantage_usd":format(gross_advantage,"f"),
            "modeled_execution_cost_usd":format(fees,"f"),
            "forecast_uncertainty_allowance_usd":format(uncertainty_cost,"f"),
            "hypothetical_net_advantage_usd":format(net,"f"),
            "gross_model_turnover_usd":format(turnover,"f"),
            "minimum_net_advantage_usd":format(hurdle,"f"),
            "capacity_and_risk_warnings":scenario["too_small_or_infeasible_target_warnings"],
            "maximum_modeled_capacity_days":scenario["maximum_modeled_capacity_days"],
            "funding_status":scenario["funding_status"],
            "broker_order_intent":None,
        }
        if state.startswith("RESEARCH_SWITCH_"):
            eligible.append(name)
    eligible.sort(key=lambda n:(
        -Decimal(outcomes[n]["hypothetical_net_advantage_usd"]),
        Decimal(outcomes[n]["gross_model_turnover_usd"]),n))
    winner=eligible[0] if eligible else None
    return {
        "schema":SCHEMA,
        "status":"HOLD_NO_COSTED_FEASIBLE_OPPORTUNITY" if winner is None
                 else "PREFERRED_UNQUALIFIED_RESEARCH_SWITCH_NO_TRADE",
        "preferred_research_candidate":winner,
        "preferred_requires_future_settlement":(
            outcomes[winner]["state"]=="RESEARCH_SWITCH_REQUIRES_FUTURE_SETTLEMENT"
            if winner else False),
        "candidate_outcomes":outcomes,
        "forecast_horizon_sessions":forecast_horizon_sessions,
        "all_forecasts_synthetic_and_unqualified":True,
        "no_evidence_of_predictive_alpha":True,
        "all_liquidity_costs_and_broker_mins_unverified":True,
        "prospective_funding_and_cap_not_live_authority":True,
        "current_live_principal_cap_usd":capacity.LIVE_CAP_USD,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,"trading_authorized":False,
        "next_action":"INDEPENDENT_SIGNAL_VALIDATION_AND_AUTHENTICATED_FUNDED_RISK_BEFORE_ANY_ORDERS",
    }

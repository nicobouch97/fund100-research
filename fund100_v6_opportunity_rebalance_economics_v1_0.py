"""Compare HOLD versus an opportunity-driven portfolio SWITCH after costs.

RESEARCH-ONLY pure economic evaluator: never authenticate predictions,
broker positions, settlement, prices or mandate, and never issue orders.
Inputs explicitly declare synthetic/unauthenticated status; arbitrary
caller forecasts MUST NOT become live permissions. The eventual V6 engine
must independently qualify as-of-point-in-time signals, deploy a specific
reviewed model, authenticate broker risk and mandate, reconcile durable
unique event history, and stage sale/settlement before any funded buy.

Purpose: avoid selling current inventory for fixed ETF weights when the
replacement cannot justify switching costs and estimated uncertainty.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
import re

SCHEMA="FUND100_V6_OPPORTUNITY_REBALANCE_ECONOMICS_RESEARCH_ONLY_V1"
MODE="IN_MEMORY_UNAUTHENTICATED_RESEARCH_ONLY"
CAP=Decimal("130.30")
MAX_ORDER=Decimal("65.00")
MAX_SYMBOL=Decimal("0.50")
MAX_GROSS=Decimal("0.95")
MIN_CASH_WEIGHT=Decimal("0.05")
MIN_TRADE=Decimal("1.00")
CENTS=Decimal("0.01")
UNIVERSE=frozenset({"ACWI","EEM","XLV","XLE","XLK","IWM"})
EXECUTION_RELEASED=False
REAL_BROKER_GETS=0
REAL_BROKER_POSTS=0

class OpportunityStop(ValueError):
    pass

def amount(x,label,*,signed=False):
    if type(x) is not str or re.fullmatch(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?",x) is None:
        raise OpportunityStop("Noncanonical decimal: "+label)
    try:
        n=Decimal(x)
    except InvalidOperation:
        raise OpportunityStop("Invalid exact decimal: "+label) from None
    if not n.is_finite() or (not signed and n<0):
        raise OpportunityStop("Negative or nonfinite: "+label)
    return n

def cashfmt(v):
    return str(v.quantize(CENTS,rounding=ROUND_DOWN))

def evaluate(*,snapshot:dict,target_weights:dict,expected_returns:dict,
             round_trip_side_cost_bps:str,forecast_uncertainty_bps:str,
             minimum_net_advantage_usd:str)->dict:
    """All inputs UNAUTHENTICATED hypotheses, all outputs NONEXECUTABLE.

    Expected edge is target-minus-current holding dollar exposures multiplied
    by same-horizon, point-in-time expected fractional returns. Charges each
    side of every transaction once (SELL plus BUY) and a *separate* additional
    forecast-uncertainty buffer on gross turnover. Never count unsettled sale
    proceeds as spendable cash for a same-run BUY.
    """
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("signal_status")!="UNQUALIFIED_RESEARCH_HYPOTHESIS"
        or snapshot.get("open_order_count")!=0
        or snapshot.get("forecast_horizon_sessions") not in (5,21,63)
        or type(target_weights) is not dict
        or type(expected_returns) is not dict
        or not target_weights
        or type(snapshot.get("positions_usd")) is not dict):
        raise OpportunityStop("Not isolated brokerless hypothesis or open order set")
    positions=snapshot["positions_usd"]
    if (not set(positions)<=UNIVERSE or not set(target_weights)<=UNIVERSE
        or not set(expected_returns)==(set(positions)|set(target_weights))
        or len(positions)!=len(set(positions))
        or len(target_weights)!=len(set(target_weights))):
        raise OpportunityStop("Unknown, uncovered or duplicative opportunity symbols")
    equity=amount(snapshot.get("equity_usd"),"account equity")
    cash=amount(snapshot.get("cash_usd"),"available broker cash")
    settled=amount(snapshot.get("settled_cash_usd"),"settled broker cash")
    if not Decimal(0)<equity or cash>equity or settled>cash:
        raise OpportunityStop("Unfunded/excess pilot, cash or unsettled-source breach")
    # Account equity may legitimately grow above the originally funded pilot.
    # Never deploy excess NAV merely because the account appreciated.
    deployable=min(equity,CAP)
    observed={s:amount(v,"position "+s) for s,v in positions.items()}
    if any(v<=0 for v in observed.values()):
        raise OpportunityStop("Zero/negative legacy position is not a holding")
    if abs(sum(observed.values(),cash)-equity)>CENTS:
        raise OpportunityStop("Unreconciled observed equity/positions/cash")
    tw={s:amount(w,"target weight "+s) for s,w in target_weights.items()}
    if any(w>MAX_SYMBOL for w in tw.values()):
        raise OpportunityStop("50 percent individual-symbol HIGH cap breached")
    gross=sum(tw.values(),Decimal(0))
    if gross>MAX_GROSS or (Decimal(1)-gross)<MIN_CASH_WEIGHT:
        raise OpportunityStop("95 percent gross/5 percent reserve HIGH cap breached")
    forecasts={s:amount(v,"forecast "+s,signed=True)
               for s,v in expected_returns.items()}
    if any(not Decimal("-1")<=v<=Decimal("2") for v in forecasts.values()):
        raise OpportunityStop("Implausible/uncapped forecast opportunity")
    side_cost=amount(round_trip_side_cost_bps,"each-side transaction cost bps")
    uncertainty=amount(forecast_uncertainty_bps,"additional forecast error bps")
    min_edge=amount(minimum_net_advantage_usd,"economic switching hurdle USD")
    if side_cost>Decimal("1000") or uncertainty>Decimal("3000") or (
            min_edge<Decimal("0.50") or min_edge>Decimal("10.00")):
        raise OpportunityStop("Unreviewed switching assumption or missing hysteresis")
    symbols=sorted(set(observed)|set(tw))
    targets={s:(deployable*tw.get(s,Decimal(0))).quantize(CENTS,rounding=ROUND_DOWN)
             for s in symbols}
    difference={s:targets[s]-observed.get(s,Decimal(0)) for s in symbols}
    # A tiny drift is not a trade; retain its existing exposure in both
    # the *economic comparison* and the later indicative plan.
    effective={s:(d if abs(d)>=MIN_TRADE else Decimal(0))
               for s,d in difference.items()}
    sells={s:-d for s,d in effective.items() if d<0}
    buys={s:d for s,d in effective.items() if d>0}
    turnover=sum((abs(x) for x in effective.values()),Decimal(0))
    gain=sum((effective[s]*forecasts[s] for s in symbols),Decimal(0))
    cost=turnover*side_cost/Decimal(10000)
    # A notional-funded BUY also consumes cash for its own estimated side
    # costs. Apply a conservative upward cent rounding to EACH hypothetical
    # buy leg, rather than relying on unsettled sale receipts to pay fees.
    # Sell-side costs remain charged in total NAV but can be funded from
    # the separate sale's eventual proceeds. This is NOT broker fee proof.
    buy_side_cost_buffer=sum(
        ((notional*side_cost/Decimal(10000)).quantize(CENTS,rounding=ROUND_UP)
         for notional in buys.values()), Decimal(0))
    settled_buy_cash_required=sum(buys.values(),Decimal(0))+buy_side_cost_buffer
    penalty=turnover*uncertainty/Decimal(10000)
    net=gain-cost-penalty
    required=max(min_edge,deployable*Decimal("0.005"))
    # Dust is deliberately retained, so target-weight caps alone do not
    # prove that the ACTUAL proposed post-trade portfolio respects risk.
    # Transaction costs are real cash outflows, unlike the separate
    # forecast-uncertainty reserve (which is only an economic hurdle).
    post_positions={s:observed.get(s,Decimal(0))+effective[s] for s in symbols}
    post_gross=sum(post_positions.values(),Decimal(0))
    post_equity=equity-cost
    post_cash=post_equity-post_gross
    # Fees shrink post-trade NAV; a 50% pre-cost target can become
    # >50% of actual deployable equity after execution friction.
    post_deployable=min(post_equity,CAP)
    post_risk_ok=(
        post_equity>0
        and post_gross<=post_deployable*MAX_GROSS
        and post_cash>=post_equity-post_deployable*MAX_GROSS
        and all(v<=post_deployable*MAX_SYMBOL for v in post_positions.values())
    )
    if not post_risk_ok:
        state="HOLD_POST_TRADE_RISK_LIMIT_BREACH"
    elif not sells and not buys:
        state="HOLD_NO_MATERIAL_DIFFERENCE"
    elif net<=required:
        state="HOLD_INSUFFICIENT_COSTED_NET_ADVANTAGE"
    elif any(v>MAX_ORDER for v in list(sells.values())+list(buys.values())):
        state="HOLD_SWITCH_EXCEEDS_SINGLE_ORDER_CAP"
    elif settled_buy_cash_required>settled:
        state="HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED"
    else:
        state="HYPOTHETICAL_SWITCH_WITH_SETTLED_CASH"
    return {
        "schema":SCHEMA,
        "state":state,
        "strategy_signal_authenticated":False,
        "broker_snapshot_authenticated":False,
        "live_risk_and_mandate_authenticated":False,
        "investment_decision_live_authorized":False,
        "settled_sale_proceeds_proven":False,
        "manual_per_trade_approval_required":False,
        "live_order_submission_authorized":False,
        "hypothetical_sell_usd_by_symbol":{s:cashfmt(v) for s,v in sells.items()},
        "hypothetical_buy_usd_by_symbol":{s:cashfmt(v) for s,v in buys.items()},
        "expected_gross_opportunity_advantage_usd":cashfmt(gain),
        "both_sides_transaction_cost_usd":cashfmt(cost),
        "additional_forecast_uncertainty_reserve_usd":cashfmt(penalty),
        "estimated_net_opportunity_advantage_usd":cashfmt(net),
        "research_unrounded_model_net_usd":format(net,"f"),
        "required_hysteresis_advantage_usd":cashfmt(required),
        "gross_turnover_usd":cashfmt(turnover),
        "hypothetical_post_trade_gross_usd":cashfmt(post_gross),
        "hypothetical_post_trade_cash_after_costs_usd":cashfmt(post_cash),
        "hypothetical_post_trade_risk_within_limits":post_risk_ok,
        "buy_cash_currently_settled_usd":cashfmt(settled),
        "estimated_buy_side_cost_buffer_usd":cashfmt(buy_side_cost_buffer),
        "settled_cash_required_for_buys_and_buy_side_costs_usd":cashfmt(settled_buy_cash_required),
        "buy_side_cost_buffer_rounded_up_per_order":True,
        "deployable_pilot_capital_usd":cashfmt(deployable),
        "future_sell_proceeds_assumed_spendable":False,
        "real_broker_gets":0,
        "real_broker_posts":0,
        "source_strategy_promoted":False,
        "next_action":"QUALIFY_INDEPENDENT_POINT_IN_TIME_SIGNALS_AND_LIVE_MANDATE_BEFORE_ANY_ORDER",
    }


MAX_RESEARCH_ALTERNATIVES=12
COMPARISON_SCHEMA="FUND100_V6_MULTI_OPPORTUNITY_COMPARISON_RESEARCH_ONLY_V1"
NONEXECUTABLE_SWITCH_STATES=frozenset({
    "HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED",
    "HYPOTHETICAL_SWITCH_WITH_SETTLED_CASH",
})

def select_research_alternative(*,snapshot:dict,candidate_targets:dict,
                                expected_returns:dict,
                                round_trip_side_cost_bps:str,
                                forecast_uncertainty_bps:str,
                                minimum_net_advantage_usd:str)->dict:
    """Compare candidate portfolio allocations against the SAME existing HOLD.

    No proposed target is a strategy signal: all observations, expected
    returns and candidate weights are unverified research hypotheses. This
    is a deterministic costed decision *simulator*, not an order planner or
    a maximizer validated on out-of-sample real investment returns.
    Never treat the hypothetical 'settled cash' stage as real broker proof.
    """
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("signal_status")!="UNQUALIFIED_RESEARCH_HYPOTHESIS"
        or type(snapshot.get("positions_usd")) is not dict
        or type(candidate_targets) is not dict
        or not 1<=len(candidate_targets)<=MAX_RESEARCH_ALTERNATIVES
        or type(expected_returns) is not dict):
        raise OpportunityStop("No bounded, consistent in-memory research proposal set")
    held=set(snapshot["positions_usd"])
    proposal_symbols=set()
    fingerprints=set()
    for name,weights in candidate_targets.items():
        if (type(name) is not str
            or re.fullmatch(r"RESEARCH_[A-Z][A-Z0-9_]{2,35}",name) is None
            or type(weights) is not dict or not weights):
            raise OpportunityStop("Unknown synthetic proposal identity or target")
        # Avoid counting duplicate allocations as independent opportunities.
        fingerprint=tuple(sorted((symbol,str(amount(weight,"target "+symbol)))
                                 for symbol,weight in weights.items()))
        if fingerprint in fingerprints:
            raise OpportunityStop("Duplicate hypothetical portfolio disguised as alternative")
        fingerprints.add(fingerprint)
        proposal_symbols.update(weights)
    if (not (held|proposal_symbols)<=UNIVERSE
        or set(expected_returns)!=(held|proposal_symbols)):
        raise OpportunityStop("Every candidate and existing holding needs one common-horizon forecast")
    for symbol,predicted in expected_returns.items():
        v=amount(predicted,"common forecast "+symbol,signed=True)
        if not Decimal("-1")<=v<=Decimal("2"):
            raise OpportunityStop("Unsupported alternative forecast")
    alternatives={}
    eligible=[]
    # Fail atomically on any structurally invalid proposal rather than
    # selecting among a corrupted/incompletely evaluated universe.
    for name in sorted(candidate_targets):
        weights=candidate_targets[name]
        scoped={symbol:expected_returns[symbol]
                for symbol in held|set(weights)}
        result=evaluate(
            snapshot=snapshot,target_weights=weights,
            expected_returns=scoped,
            round_trip_side_cost_bps=round_trip_side_cost_bps,
            forecast_uncertainty_bps=forecast_uncertainty_bps,
            minimum_net_advantage_usd=minimum_net_advantage_usd)
        alternatives[name]=result
        if result["state"] in NONEXECUTABLE_SWITCH_STATES:
            eligible.append(name)
    # Use the true, unrounded model result, not an already-truncated
    # cents display; if economic edges tie prefer less turnover, then
    # stable research candidate name. None of these provide live authority.
    eligible.sort(key=lambda name:(
        -Decimal(alternatives[name]["research_unrounded_model_net_usd"]),
        Decimal(alternatives[name]["gross_turnover_usd"]),name))
    selected=eligible[0] if eligible else None
    return {
        "schema":COMPARISON_SCHEMA,
        "status":("RESEARCH_PREFERRED_COSTED_SWITCH_NOT_AUTHORIZED" if selected
                  else "HOLD_NO_COSTED_RISK_ELIGIBLE_ALTERNATIVE"),
        "research_preferred_candidate_id":selected,
        "candidate_count":len(alternatives),
        "eligible_costed_switch_count":len(eligible),
        "candidate_outcomes":alternatives,
        "preferred_hypothetical_economics":(
            alternatives[selected] if selected else None),
        "shared_forecast_horizon_sessions":snapshot.get("forecast_horizon_sessions"),
        "all_portfolio_forecasts_unqualified_and_unauthenticated":True,
        "candidate_generation_has_no_backtest_or_live_alpha_validation":True,
        "historic_survivorship_free_model_skill_proven":False,
        "original_live_pilot_cap_usd":cashfmt(CAP),
        "standing_mandate_authenticated":False,
        "current_broker_holdings_and_settled_cash_authenticated":False,
        "live_order_submission_authorized":False,
        "manual_per_trade_approval_required":False,
        "real_broker_gets":0,
        "real_broker_posts":0,
        "next_action":"VALIDATE_SIGNAL_PROVENANCE_AND_EXECUTION_JOURNAL_BEFORE_LIVE_SWITCH",
    }

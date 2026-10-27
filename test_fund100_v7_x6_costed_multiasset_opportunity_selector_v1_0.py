"""Brokerless regression tests for future-capital opportunity selection."""
from decimal import Decimal
import pytest
import fund100_v7_x5_capacity_aware_portfolio_router_v1_0 as x5
import fund100_v7_x6_costed_multiasset_opportunity_selector_v1_0 as x6

def query(nav="1000.00",cash=None,held=None,targets=None,forecasts=None,spec=None):
    return x6.select(
        capital_nav_usd=nav,prospective_cap_usd=nav,
        settled_cash_usd=cash if cash is not None else nav,
        current_holdings_usd=held or {},
        candidate_target_weights=targets or {
            "RESEARCH_GROWTH":{"XLK":"0.45","XLE":"0.30"},
            "RESEARCH_VALUE":{"XLK":"0.25","XLE":"0.45"}},
        expected_returns_fraction=forecasts or {"XLK":"0.10","XLE":"0.05"},
        asset_spec=spec or x5.sample_spec(),
        forecast_horizon_sessions=21)

def test_costed_edge_ranks_divergent_allocations_but_never_trades():
    r=query()
    assert r["preferred_research_candidate"]=="RESEARCH_GROWTH"
    assert r["candidate_outcomes"]["RESEARCH_GROWTH"]["state"]=="RESEARCH_SWITCH_SYNTHETIC_CASH_SUFFICIENT"
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0
    assert not r["trading_authorized"] and r["all_forecasts_synthetic_and_unqualified"]

def test_low_forecast_edge_requires_hold_instead_of_turnover():
    r=query(forecasts={"XLK":"0.0005","XLE":"0.0005"})
    assert r["preferred_research_candidate"] is None
    assert r["status"]=="HOLD_NO_COSTED_FEASIBLE_OPPORTUNITY"
    assert all(v["state"]=="HOLD_INSUFFICIENT_COSTED_EDGE"
               for v in r["candidate_outcomes"].values())

def test_reinvestment_using_unsold_settled_cash_is_not_implied():
    r=query(cash="300.00",held={"XLK":"350.00","XLE":"350.00"},
            targets={"RESEARCH_ROTATE":{"XLK":"0.10","XLE":"0.15","IWM":"0.45"}},
            forecasts={"XLK":"-0.05","XLE":"-0.05","IWM":"0.20"})
    assert r["preferred_research_candidate"]=="RESEARCH_ROTATE"
    assert r["preferred_requires_future_settlement"]
    assert r["candidate_outcomes"]["RESEARCH_ROTATE"]["funding_status"]=="SELL_OR_DEPOSIT_FIRST_THEN_REVERIFY_SETTLEMENT"
    assert r["broker_orders"]==0

def test_aggregate_ticket_liquidity_blocks_premature_big_capital_rotation():
    spec=x5.sample_spec()
    for meta in spec.values():
        meta["maximum_ticket_usd"]="10"
    r=query(nav="100000.00",spec=spec)
    assert r["preferred_research_candidate"] is None
    assert all(v["maximum_modeled_capacity_days"]>1 for v in r["candidate_outcomes"].values())
    assert all(v["state"]=="HOLD_MODEL_CAPACITY_OR_POST_COST_RISK"
               for v in r["candidate_outcomes"].values())

def test_invalid_or_incomplete_signal_is_rejected_not_live_promoted():
    with pytest.raises(x6.SelectionStop):
        query(forecasts={"XLK":"0.10"})
    with pytest.raises(x6.SelectionStop):
        query(forecasts={"XLK":"NaN","XLE":"0.01"})
    assert x6.BROKER_GETS==x6.BROKER_POSTS==x6.BROKER_ORDERS==0
    assert x6.TRADING_AUTHORIZED is False


def test_unfillable_ticket_split_cannot_be_ranked_as_profitable_switch():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["maximum_ticket_usd"]="10"
    result=query(spec=spec,targets={"RESEARCH_SPLIT":{"XLK":"0.015","XLE":"0.20"}},
                 forecasts={"XLK":"1.0","XLE":"0.20"})
    candidate=result["candidate_outcomes"]["RESEARCH_SPLIT"]
    assert Decimal(candidate["hypothetical_net_advantage_usd"])>Decimal("0")
    assert candidate["state"]=="HOLD_MODEL_CAPACITY_OR_POST_COST_RISK"
    assert any(w["reason"]=="MODELED_TICKET_SPLIT_VIOLATES_MINIMUM"
               for w in candidate["capacity_and_risk_warnings"])
    assert result["preferred_research_candidate"] is None
    assert result["broker_orders"]==0 and not result["trading_authorized"]


def test_cash_feasible_costed_opportunity_beats_higher_unsettled_forecast():
    # Synthetic $1,000 NAV: $900 is held and only $100 is settled.
    # The larger paper edge needs a $500 BUY financed by unsettled SELLs.
    # A smaller positive, SELL-only de-risking opportunity is feasible
    # without those proceeds and should not be hidden by the deferred one.
    kwargs=dict(
        capital_nav_usd="1000.00",prospective_cap_usd="1000.00",
        settled_cash_usd="100.00",
        current_holdings_usd={"XLK":"450.00","XLE":"450.00"},
        asset_spec=x5.sample_spec(),
        expected_returns_fraction={"XLK":"-0.10","XLE":"-0.10","IWM":"0.20"},
        forecast_horizon_sessions=21,
    )
    deferred={"XLK":"0.10","XLE":"0.10","IWM":"0.50"}
    ready={"XLK":"0.40","XLE":"0.45"}
    result=x6.select(**kwargs,candidate_target_weights={
        "RESEARCH_HIGH_EDGE_DEFERRED":deferred,
        "RESEARCH_SMALL_EDGE_CASH_READY":ready,
    })
    outcomes=result["candidate_outcomes"]
    assert outcomes["RESEARCH_HIGH_EDGE_DEFERRED"]["state"]==(
        "RESEARCH_SWITCH_REQUIRES_FUTURE_SETTLEMENT")
    assert outcomes["RESEARCH_SMALL_EDGE_CASH_READY"]["state"]==(
        "RESEARCH_SWITCH_SYNTHETIC_CASH_SUFFICIENT")
    assert Decimal(outcomes["RESEARCH_HIGH_EDGE_DEFERRED"][
        "hypothetical_net_advantage_usd"])>Decimal(outcomes[
        "RESEARCH_SMALL_EDGE_CASH_READY"]["hypothetical_net_advantage_usd"])
    assert result["preferred_research_candidate"]=="RESEARCH_SMALL_EDGE_CASH_READY"
    assert result["best_deferred_research_candidate"]=="RESEARCH_HIGH_EDGE_DEFERRED"
    assert result["cash_feasible_candidates_ranked_before_deferred"]
    assert result["cash_feasible_is_synthetic_not_authenticated_buying_power"]
    assert not result["preferred_requires_future_settlement"]
    assert result["broker_orders"]==0 and not result["trading_authorized"]

    # Preserve existing contract: if no feasible positive edge exists,
    # surface the deferred hypothesis, explicitly marked as unsettled.
    only_deferred=x6.select(**kwargs,candidate_target_weights={
        "RESEARCH_HIGH_EDGE_DEFERRED":deferred})
    assert only_deferred["preferred_research_candidate"]=="RESEARCH_HIGH_EDGE_DEFERRED"
    assert only_deferred["best_deferred_research_candidate"]=="RESEARCH_HIGH_EDGE_DEFERRED"
    assert only_deferred["preferred_requires_future_settlement"]
    assert only_deferred["broker_orders"]==0

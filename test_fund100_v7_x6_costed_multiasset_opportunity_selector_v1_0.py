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
            "RESEARCH_VALUE":{"XLK":"0.25","XLE":"0.50"}},
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

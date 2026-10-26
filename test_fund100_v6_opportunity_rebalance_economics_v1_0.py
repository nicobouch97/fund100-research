"""Pure economic hold/switch comparison: zero broker order authority."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_opportunity_rebalance_economics_v1_0 as m

def case():
    return {
        "snapshot":{
            "mode":m.MODE,
            "signal_status":"UNQUALIFIED_RESEARCH_HYPOTHESIS",
            "forecast_horizon_sessions":21,
            "open_order_count":0,
            "equity_usd":"100.00",
            "cash_usd":"50.00",
            "settled_cash_usd":"10.00",
            "positions_usd":{"ACWI":"50.00"},
        },
        "target_weights":{"XLK":"0.50"},
        "expected_returns":{"ACWI":"0.02","XLK":"0.15"},
        "round_trip_side_cost_bps":"15",
        "forecast_uncertainty_bps":"50",
        "minimum_net_advantage_usd":"0.50",
    }

def run(inputs=None):
    return m.evaluate(**(case() if inputs is None else inputs))

def test_strong_alternative_recognised_after_two_sided_costs_but_settlement_stops_buy():
    z=run()
    assert z["state"]=="HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED"
    assert z["hypothetical_sell_usd_by_symbol"]=={"ACWI":"50.00"}
    assert z["hypothetical_buy_usd_by_symbol"]=={"XLK":"50.00"}
    assert z["gross_turnover_usd"]=="100.00"
    assert z["expected_gross_opportunity_advantage_usd"]=="6.50"
    assert z["both_sides_transaction_cost_usd"]=="0.15"
    assert z["additional_forecast_uncertainty_reserve_usd"]=="0.50"
    assert z["estimated_net_opportunity_advantage_usd"]=="5.85"
    assert z["required_hysteresis_advantage_usd"]=="0.50"
    assert z["buy_cash_currently_settled_usd"]=="10.00"
    assert z["deployable_pilot_capital_usd"]=="100.00"
    assert z["manual_per_trade_approval_required"] is False
    assert z["broker_snapshot_authenticated"] is False
    assert z["strategy_signal_authenticated"] is False
    assert z["live_risk_and_mandate_authenticated"] is False
    assert z["live_order_submission_authorized"] is False
    assert z["source_strategy_promoted"] is False
    assert z["real_broker_gets"]==z["real_broker_posts"]==0

def test_available_settled_cash_changes_hypothetical_only_not_live_permission():
    c=case()
    c["snapshot"]["settled_cash_usd"]="50.00"
    z=run(c)
    assert z["state"]=="HYPOTHETICAL_SWITCH_WITH_SETTLED_CASH"
    assert z["live_order_submission_authorized"] is False
    assert z["settled_sale_proceeds_proven"] is False

def test_small_unreliable_edge_holds_existing_holdings():
    c=case()
    c["expected_returns"]={"ACWI":"0.06","XLK":"0.07"}
    z=run(c)
    assert z["state"]=="HOLD_INSUFFICIENT_COSTED_NET_ADVANTAGE"
    assert z["estimated_net_opportunity_advantage_usd"]=="-0.15"

def test_no_meaningful_difference_never_fabricates_trade():
    c=case()
    c["target_weights"]={"ACWI":"0.50"}
    c["expected_returns"]={"ACWI":"0.05"}
    z=run(c)
    assert z["state"]=="HOLD_NO_MATERIAL_DIFFERENCE"
    assert z["hypothetical_sell_usd_by_symbol"]=={}
    assert z["hypothetical_buy_usd_by_symbol"]=={}
    assert z["gross_turnover_usd"]=="0.00"

def test_existing_position_can_be_partially_rotated_not_forced_liquidation():
    c=case()
    c["target_weights"]={"ACWI":"0.25","XLK":"0.25"}
    z=run(c)
    assert z["hypothetical_sell_usd_by_symbol"]=={"ACWI":"25.00"}
    assert z["hypothetical_buy_usd_by_symbol"]=={"XLK":"25.00"}
    assert z["state"]=="HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED"

def test_no_cashflow_before_settlement_even_with_high_expected_upside():
    c=case()
    c["snapshot"]["settled_cash_usd"]="0.00"
    c["expected_returns"]["XLK"]="1.00"
    z=run(c)
    assert z["state"]=="HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED"
    assert z["future_sell_proceeds_assumed_spendable"] is False

def test_single_order_above_65_is_not_silently_authorized():
    c=case()
    c["snapshot"].update({
        "equity_usd":"125.00","cash_usd":"45.00",
        "settled_cash_usd":"45.00","positions_usd":{"ACWI":"80.00"}})
    c["target_weights"]={"XLK":"0.50"}
    c["expected_returns"]={"ACWI":"0.00","XLK":"0.40"}
    z=run(c)
    assert z["state"]=="HOLD_SWITCH_EXCEEDS_SINGLE_ORDER_CAP"
    assert z["hypothetical_sell_usd_by_symbol"]["ACWI"]=="80.00"
    assert z["live_order_submission_authorized"] is False

def test_account_growth_cannot_increase_investable_base_above_original_130_30():
    c=case()
    c["snapshot"].update({
        "equity_usd":"200.00","cash_usd":"140.00",
        "settled_cash_usd":"140.00","positions_usd":{"ACWI":"60.00"}})
    c["target_weights"]={"XLK":"0.50"}
    c["expected_returns"]={"ACWI":"0.00","XLK":"0.30"}
    z=run(c)
    assert z["deployable_pilot_capital_usd"]=="130.30"
    assert z["hypothetical_buy_usd_by_symbol"]["XLK"]=="65.15"
    assert z["state"]=="HOLD_SWITCH_EXCEEDS_SINGLE_ORDER_CAP"

def test_dust_trades_do_not_count_as_alpha_or_orders():
    c=case()
    c["snapshot"]["positions_usd"]={"ACWI":"50.00"}
    c["target_weights"]={"ACWI":"0.495"}
    c["expected_returns"]={"ACWI":"0.20"}
    z=run(c)
    assert z["state"]=="HOLD_NO_MATERIAL_DIFFERENCE"
    assert z["hypothetical_sell_usd_by_symbol"]=={}

def test_retained_dust_cannot_overrun_95pct_gross_or_5pct_cash():
    c=case()
    c["snapshot"].update({
        "equity_usd":"100.00","cash_usd":"50.00",
        "settled_cash_usd":"50.00",
        "positions_usd":{"ACWI":"49.50","EEM":"0.50"}})
    c["target_weights"]={"XLK":"0.50","XLE":"0.45"}
    c["expected_returns"]={"ACWI":"0.00","EEM":"0.00",
                           "XLK":"0.40","XLE":"0.30"}
    c["round_trip_side_cost_bps"]="0"
    c["forecast_uncertainty_bps"]="0"
    z=run(c)
    assert z["hypothetical_sell_usd_by_symbol"]=={"ACWI":"49.50"}
    assert z["hypothetical_buy_usd_by_symbol"]=={"XLE":"45.00","XLK":"50.00"}
    assert z["hypothetical_post_trade_gross_usd"]=="95.50"
    assert z["hypothetical_post_trade_cash_after_costs_usd"]=="4.50"
    assert z["hypothetical_post_trade_risk_within_limits"] is False
    assert z["state"]=="HOLD_POST_TRADE_RISK_LIMIT_BREACH"
    assert z["live_order_submission_authorized"] is False


def test_retained_dust_cannot_overrun_single_name_50pct_cap():
    c=case()
    c["snapshot"].update({
        "equity_usd":"100.00","cash_usd":"49.50",
        "settled_cash_usd":"49.50","positions_usd":{"ACWI":"50.50"}})
    c["target_weights"]={"ACWI":"0.50","XLK":"0.40"}
    c["expected_returns"]={"ACWI":"0.00","XLK":"0.50"}
    c["round_trip_side_cost_bps"]="0"
    z=run(c)
    assert z["hypothetical_sell_usd_by_symbol"]=={}
    assert z["hypothetical_buy_usd_by_symbol"]=={"XLK":"40.00"}
    assert z["hypothetical_post_trade_gross_usd"]=="90.50"
    assert z["hypothetical_post_trade_risk_within_limits"] is False
    assert z["state"]=="HOLD_POST_TRADE_RISK_LIMIT_BREACH"


def test_transaction_costs_reduce_actual_cash_reserve_before_switch():
    c=case()
    c["snapshot"].update({
        "equity_usd":"100.00","cash_usd":"100.00",
        "settled_cash_usd":"100.00","positions_usd":{}})
    c["target_weights"]={"XLK":"0.50","XLE":"0.45"}
    c["expected_returns"]={"XLK":"0.40","XLE":"0.30"}
    c["round_trip_side_cost_bps"]="35"
    c["forecast_uncertainty_bps"]="0"
    z=run(c)
    assert z["hypothetical_post_trade_gross_usd"]=="95.00"
    assert z["hypothetical_post_trade_cash_after_costs_usd"]=="4.66"
    assert z["hypothetical_post_trade_risk_within_limits"] is False
    assert z["state"]=="HOLD_POST_TRADE_RISK_LIMIT_BREACH"
    assert z["live_order_submission_authorized"] is False


@pytest.mark.parametrize("bad",[
    {"mode":"LIVE_AUTHENTICATED"},
    {"signal_status":"DEPLOYED_CERTIFIED_ALPHA"},
    {"forecast_horizon_sessions":1},
    {"open_order_count":1},
    {"equity_usd":"0.00"},
    {"cash_usd":"101.00"},
    {"settled_cash_usd":"51.00"},
    {"positions_usd":{"ACWI":"50.00","CRYPTO":"0.01"}},
    {"positions_usd":{"ACWI":"51.00"}},
    {"positions_usd":{"ACWI":"-1.00"}},
])
def test_unverified_or_unsafe_snapshot_never_becomes_an_order(bad):
    c=case()
    c["snapshot"].update(bad)
    with pytest.raises(m.OpportunityStop):
        run(c)

@pytest.mark.parametrize("targets",[
    {"XLK":"0.51"},
    {"XLK":"0.50","XLE":"0.50"},
    {"XLK":"0.50","XLE":"0.46"},
    {"BTC":"0.40"},
    {},
    {"XLK":"1.00"},
    {"XLK":"-0.10"},
])
def test_unbounded_or_unknown_target_rejected(targets):
    c=case()
    c["target_weights"]=targets
    with pytest.raises(m.OpportunityStop):
        run(c)

@pytest.mark.parametrize("returns",[
    {"XLK":"0.40"},
    {"ACWI":"0.00","XLK":"NaN"},
    {"ACWI":"0.00","XLK":"3.00"},
    {"ACWI":"0.00","XLK":"-1.50"},
    {"ACWI":"0.00","XLK":"1e-2"},
    {"ACWI":"0.00","XLK":" 0.50"},
])
def test_forecast_gap_noncanonical_or_unsupported_rejected(returns):
    c=case()
    c["expected_returns"]=returns
    with pytest.raises(m.OpportunityStop):
        run(c)

@pytest.mark.parametrize("name,value",[
    ("round_trip_side_cost_bps","1001"),
    ("round_trip_side_cost_bps","-5"),
    ("round_trip_side_cost_bps","1e2"),
    ("forecast_uncertainty_bps","3001"),
    ("forecast_uncertainty_bps","-1"),
    ("minimum_net_advantage_usd","0"),
    ("minimum_net_advantage_usd","10.01"),
])
def test_cost_and_hysteresis_must_be_explicit_and_conservative(name,value):
    c=case()
    c[name]=value
    with pytest.raises(m.OpportunityStop):
        run(c)

def test_research_only_never_connects_broker_or_secret_or_sends():
    s=Path(m.__file__).read_text()
    assert m.EXECUTION_RELEASED is False
    assert m.REAL_BROKER_GETS==m.REAL_BROKER_POSTS==0
    for banned in ("import requests","import urllib","import socket",
                   "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "git push","method=\"POST\"","import os",
                   "def main("):
        assert banned not in s

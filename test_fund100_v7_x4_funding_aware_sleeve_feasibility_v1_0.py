"""No-network funding-limit, tiny-size, and settlement-stage adversarial tests."""
from decimal import Decimal
from pathlib import Path
import pytest
import fund100_v7_x4_funding_aware_sleeve_feasibility_v1_0 as x4

def quote(equity="130.30",ceiling="130.30",cash="0",btc_min="10.00",
          fee=x4.BTC_COST_BPS):
    return x4.inspect(
        hypothetical_account_equity_usd=equity,
        prospective_authorized_ceiling_usd=ceiling,
        independently_verified_settled_cash_usd=cash,
        btc_minimum_notional_scenario_usd=btc_min,
        btc_fee_bps=fee)

def test_user_may_add_money_but_old_130_30_cap_stays_unchanged():
    old=quote("130.30")
    add=quote("5000.00")
    assert old["model_deployable_basis_usd"]=="130.30"
    assert add["model_deployable_basis_usd"]=="130.30"
    assert add["amount_above_model_authorized_ceiling_usd"]=="4869.70"
    assert add["current_live_policy_deployable_at_this_balance_if_not_changed_usd"]=="130.30"
    assert add["future_cap_increase_not_granted_by_this_study"]
    assert add["two_legs_pass_declared_order_minimum_scenarios"] is False
    assert add["broker_gets"]==add["broker_posts"]==add["broker_orders"]==0
    assert not add["live_authorized"] and not add["trading_authorized"]

def test_five_pct_btc_10_dollar_documentation_minimum_requires_200_80_with_cent_fee():
    assert x4.required_capital_for_btc_minimum("10.00")=="200.80"
    before=quote("200.70","200.70",btc_min="10.00")
    after=quote("200.80","200.80",btc_min="10.00")
    assert not before["bitcoin_buy"]["minimum_notional_passes_scenario"]
    assert before["bitcoin_buy"]["maximum_gross_order_notional_usd"]=="9.99"
    assert after["bitcoin_buy"]["minimum_notional_passes_scenario"]
    assert after["bitcoin_buy"]["maximum_gross_order_notional_usd"]=="10.00"
    assert after["bitcoin_buy"]["conservative_buy_fee_allowance_usd"]=="0.04"
    assert after["bitcoin_buy"]["full_cash_required_if_bought_usd"]=="10.04"
    assert after["gold_buy"]["minimum_notional_passes_scenario"]
    assert after["minimum_cash_reserve_weight_pct"]==15

def test_high_btc_side_cost_and_many_minimum_scenarios():
    assert x4.required_capital_for_btc_minimum("10.00",x4.BTC_HIGH_COST_BPS)=="201.20"
    assert x4.required_capital_for_btc_minimum("1.00")=="20.20"
    assert x4.required_capital_for_btc_minimum("20.00")=="401.40"
    sizes={x["hypothetical_total_account_usd"]:x
           for x in x4.analyze()["scenarios"]["35"]["BTC_MIN_10_USD"]["funding_tiers"]}
    assert not sizes["200.70"]["FUTURE_SEPARATELY_AUTHORIZED_FULL_CEILING"]["BTC_min_pass"]
    assert sizes["250.00"]["FUTURE_SEPARATELY_AUTHORIZED_FULL_CEILING"]["BTC_min_pass"]
    assert not sizes["5000.00"]["CURRENT_UNCHANGED_130_30_LIMIT"]["BTC_min_pass"]
    assert sizes["5000.00"]["FUTURE_SEPARATELY_AUTHORIZED_FULL_CEILING"]["BTC_min_pass"]

def test_settled_cash_funding_gate_does_not_reuse_sale_proceeds_same_run():
    no_cash=quote("500.00","500.00",cash="0")
    need=no_cash["two_new_sleeves_total_buy_notional_and_cost_usd"]
    assert Decimal(need)>Decimal("49")
    assert no_cash["two_leg_funding_status"]=="ILLUSTRATIVE_SELL_FIRST_AWAIT_AUTHENTICATED_SETTLEMENT"
    enough=quote("500.00","500.00",cash=need)
    assert enough["two_leg_funding_status"]=="ILLUSTRATIVE_SETTLED_CASH_COVERS_BOTH_BUYS"
    assert enough["hypothetical_remaining_shortfall_to_wait_settlement_usd"]=="0"
    assert enough["cash_from_current_inventory_sell_not_assumed_settled"]
    assert enough["synthetic_settlement_input_is_not_authenticated"]
    assert not enough["trading_authorized"]

def test_original_whitelist_and_75_5_5_15_portfolio_conserved():
    x=quote("1000.00","1000.00",cash="0")
    assert x["constant_stock_allocation_targets_usd"]=={
        "XLK":"375.00","XLE":"225.00","IWM":"150.00"}
    assert x["bitcoin_weight_target_pct"]==5
    assert x["gold_weight_target_pct"]==5
    assert x["minimum_cash_reserve_usd"]=="150.00"
    assert x["BTC_and_GLD_not_current_live_whitelist"] is True
    assert x["market_price_qty_increment_and_live_crypto_fee_are_unverified"]

@pytest.mark.parametrize("patch",[
    {"hypothetical_account_equity_usd":"130.300001"},
    {"hypothetical_account_equity_usd":"-1"},
    {"hypothetical_account_equity_usd":"NaN"},
    {"prospective_authorized_ceiling_usd":"100.00"},
    {"independently_verified_settled_cash_usd":"130.31"},
    {"btc_minimum_notional_scenario_usd":"0"},
    {"btc_minimum_notional_scenario_usd":"unknown"},
    {"btc_fee_bps":Decimal("3")},
])
def test_malformed_unfunded_or_unreviewed_policy_is_rejected(patch):
    args={"hypothetical_account_equity_usd":"130.30",
          "prospective_authorized_ceiling_usd":"130.30",
          "independently_verified_settled_cash_usd":"0",
          "btc_minimum_notional_scenario_usd":"10.00"}
    args.update(patch)
    with pytest.raises(x4.FundSizingStop):
        x4.inspect(**args)

def test_no_crypto_asset_or_account_data_and_original_cap_not_mutated():
    report=x4.analyze()
    assert report["original_live_capital_ceiling_usd"]=="130.30"
    assert report["no_capital_increase_or_future_deposit_authorized"] is True
    assert report["BTC_minimum_order_Broker_API_example_may_not_apply_to_Trading_API"] is True
    assert report["future_account_and_capital_values_all_synthetic"]
    assert report["broker_gets"]==report["broker_posts"]==report["broker_orders"]==0
    assert set(report["scenarios"])=={"35","60"}
    assert all(len(rows["funding_tiers"])==len(x4.SIZES)
               for bymin in report["scenarios"].values() for rows in bymin.values())
    s=Path(x4.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY",
                "api.alpaca.markets","place_order","submit_order"):
        assert bad not in s

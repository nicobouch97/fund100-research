"""Scalability is invariant to amount; no broker, data provider or FX API."""
from decimal import Decimal
from pathlib import Path
import copy
import pytest
import fund100_v7_x5_capacity_aware_portfolio_router_v1_0 as x5

TARGET={"XLK":"0.375","XLE":"0.225","IWM":"0.15","GLD":"0.05","BTC/USD":"0.05"}

def plan(capital="1000.00",spec=None,target=None,gbp="1000",cash=None,
         positions=None,prospective_cap=None):
    n=Decimal(capital)
    if positions is None:
        positions={s:x5.nstr(n*w) for s,w in (
            ("XLK",Decimal("0.40")),("XLE",Decimal("0.30")),
            ("IWM",Decimal(".24")))}
    if cash is None:cash=x5.nstr(n-sum(map(Decimal,positions.values())))
    return x5.route(
        capital_nav_usd=capital,
        prospective_cap_usd=prospective_cap or capital,
        settled_cash_usd=cash,current_holdings_usd=positions,
        target_weights=TARGET if target is None else target,
        asset_spec=x5.sample_spec() if spec is None else spec,
        intention_gbp=gbp)

def test_broker_authority_not_increased_by_anticipated_one_thousand_pounds():
    r=plan("1000.00")
    assert r["funding_intention_original_currency"]=="GBP"
    assert r["potential_unfunded_GBP_contribution"]=="1000"
    assert r["GBP_not_converted_into_broker_deployable_USD"] is True
    assert not r["actual_deposit_posted_and_cleared"]
    assert not r["actual_broker_GBP_USD_rate_authenticated"]
    assert r["current_LIVE_authorized_principal_USD"]=="130.30"
    assert r["USD_hypothetical_future_cap_not_authorized"]=="1000.00"
    assert not r["funding_ceiling_raise_executed"]
    assert not r["live_authorized"] and not r["trading_authorized"]
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0

def test_same_weights_and_number_of_positions_at_thousand_to_million():
    sample=x5.illustrative_scenarios()
    assert set(sample["scenarios"])==set(x5.USD_TEST_CAPITAL)
    assert sample["GBP_1000_USER_INTENT_NOT_CONVERTED_TO_USD"]
    assert len(x5.GBP_INTENTION_TIERS)>=4
    for tier,r in sample["scenarios"].items():
        assert r["target_asset_count"]==5
        assert Decimal(r["target_non_cash_weight_sum"])==Decimal("0.85")
        assert Decimal(r["target_cash_reserve_weight"])==Decimal("0.15")
        assert Decimal(r["crypto_allocation_weight"])==Decimal("0.05")
        assert r["funding_status"]=="SELL_OR_DEPOSIT_FIRST_THEN_REVERIFY_SETTLEMENT"
        assert r["proceeds_of_unsettled_sales_used_for_buys"] is False
        assert r["current_LIVE_authorized_principal_USD"]=="130.30"
        assert r["model_net_cash_reserve_after_all_rebalances_usd"]>"0.00"
    assert any(w["reason"].startswith("MODELED_NOTIONAL_BELOW")
               for w in sample["scenarios"]["130.30"]["too_small_or_infeasible_target_warnings"])
    assert not any(w["reason"].startswith("MODELED_NOTIONAL_BELOW")
                   for w in sample["scenarios"]["1000.00"]["too_small_or_infeasible_target_warnings"])

def test_liquidity_and_ticket_count_scale_with_capital_not_assumed_instant():
    small=plan("1000.00")
    large=plan("100000000.00")
    assert large["maximum_modeled_capacity_days"]>1
    assert small["maximum_modeled_capacity_days"]==1
    assert sum(v["modelled_ticket_count"] for v in large["estimated_trade_side_details"].values())>500
    assert any(x["reason"]=="MULTI_SESSION_LIQUIDITY_CAPACITY_REQUIRES_REEVALUATION"
               for x in large["too_small_or_infeasible_target_warnings"])
    assert not large["model_liquidity_not_verified_with_market_data"] is False
    assert not large["trading_authorized"]

def test_sales_do_not_increase_current_buy_cash_until_settled():
    incomplete=plan()
    assert Decimal(incomplete["combined_hypothetical_sell_proceeds_after_costs_usd"])>0
    assert Decimal(incomplete["combined_hypothetical_buys_and_rounded_costs_usd"])>Decimal("100")
    assert incomplete["funding_status"]=="SELL_OR_DEPOSIT_FIRST_THEN_REVERIFY_SETTLEMENT"
    assert not incomplete["real_broker_settlement_authenticated"]
    # Fully cash-funded starting point: still no real permission.
    ready=plan(cash="1000.00",positions={})
    assert ready["funding_status"]=="HYPOTHETICAL_SETTLED_CASH_SUFFICIENT_ONLY"
    assert ready["actual_positions_traded"] is False
    assert not ready["live_authorized"]

def test_per_order_round_up_is_conservative_for_ticket_splitting():
    fee=x5.fee_upper_by_ticket(Decimal("25.00"),Decimal("10"),Decimal("15"))
    assert fee==Decimal("0.05") # each $10 order 2 cents, final $5 1 cent
    assert x5.count_to_fit(Decimal("25"),Decimal("10"))==3
    assert x5.fee_upper_by_ticket(Decimal("0"),Decimal("10"),Decimal("15"))==0
    with pytest.raises(x5.CapacityStop):
        x5.fee_upper_by_ticket(Decimal("1"),Decimal("0"),Decimal("15"))

def test_strategy_independent_authorized_future_universe_remains_untrusted():
    spec=x5.sample_spec()
    spec["AGG"]={**spec["IWM"],"asset_class":"BOND_ETF"}
    spec["SPY"]={**spec["XLK"],"asset_class":"EQUITY_ETF"}
    result=plan(spec=spec,target={"SPY":"0.40","AGG":"0.30","GLD":"0.05","BTC/USD":"0.05"},
                positions={},cash="1000.00")
    assert result["target_asset_count"]==4
    assert result["target_cash_reserve_weight"]=="0.20"
    assert result["forecast_strategy_alpha_not_authenticated"]
    assert result["crypto_and_GLD_live_whitelist_unmodified"]
    assert not result["no_live_capital_deployment_permission"] is False

def test_actual_market_volume_or_crypto_client_permission_cannot_be_claimed():
    for change in [
        {"asof_authenticated":True},
        {"actual_client_order_minimum_verified":True},
        {"actual_customer_fractional_quantity_allowed_verified":True},
        {"liquidity_source":"AUTHENTICATED_VENDOR_AVG_DAILY_VOLUME"},
        {"assumed_average_daily_volume_usd":"0"},
        {"minimum_notional_usd":"30000"},
        {"modeled_side_cost_bps":"5000"},
    ]:
        spec=x5.sample_spec()
        spec["BTC/USD"].update(change)
        with pytest.raises(x5.CapacityStop):
            plan(spec=spec)

@pytest.mark.parametrize("change",[
    {"target":{"XLK":"0.51","XLE":"0.20"}},
    {"target":{"BTC/USD":"0.11","XLK":"0.30"}},
    {"target":{"XLK":"0.50","XLE":"0.46"}},
    {"target":{"XLK":"-0.2","GLD":"0.01"}},
    {"target":{"XLK":"NaN"}},
    {"cash":"1000.01"},
    {"prospective_cap":"100.00"},
    {"gbp":"£1000"},
    {"positions":{"XLK":"1000.01"}},
])
def test_invalid_allocation_funding_fx_or_risk_does_not_create_trade(change):
    kw={k:v for k,v in change.items()}
    with pytest.raises(x5.CapacityStop):
        plan(**kw)

def test_no_real_live_writer_credentials_fx_or_private_payloads():
    assert x5.BROKER_GETS==x5.BROKER_POSTS==x5.BROKER_ORDERS==0
    assert x5.LIVE_ENABLED is False
    assert x5.MODE=="SYNTHETIC_CAPITAL_MARKET_LIQUIDITY_SCENARIOS_ONLY"
    assert x5.LIVE_CAP_USD=="130.30"
    source=Path(x5.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY",
                "api.alpaca.markets","submit_order(","place_order(","requests.post("):
        assert bad not in source

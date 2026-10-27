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

def test_per_order_round_up_bounds_any_minimum_ticket_partition():
    fee=x5.fee_upper_by_ticket(Decimal("25.00"),Decimal("10"),Decimal("15"))
    assert fee==Decimal("0.06") # three $8.33-ish tickets each round to 2 cents
    assert x5.count_to_fit(Decimal("25"),Decimal("10"))==3
    assert x5.fee_upper_by_ticket(Decimal("0"),Decimal("10"),Decimal("15"))==0
    with pytest.raises(x5.CapacityStop):
        x5.fee_upper_by_ticket(Decimal("1"),Decimal("0"),Decimal("15"))
    # Max-first would use $20+$5 (invalid $5 ticket) and understate
    # 35bp fees at $0.09; valid $15+$10 costs $0.10 after rounding.
    assert x5.fee_upper_by_ticket(
        Decimal("25"),Decimal("20"),Decimal("35"),Decimal("10"))==Decimal("0.10")
    with pytest.raises(x5.CapacityStop):
        x5.fee_upper_by_ticket(
            Decimal("11"),Decimal("10"),Decimal("15"),Decimal("10"))

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


def test_shared_daily_ticket_limit_counts_every_symbol_not_just_largest_symbol():
    spec=x5.sample_spec()
    for row in spec.values():
        row["maximum_ticket_usd"]="10"
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.25","XLE":"0.25","IWM":"0.25",
                        "GLD":"0.10","BTC/USD":"0.10"})
    assert all(x["modelled_ticket_count"]<=30
               for x in result["estimated_trade_side_details"].values())
    assert result["aggregate_modelled_ticket_count"]==95
    assert result["global_shared_ticket_capacity_minimum_days"]==4
    assert result["maximum_modeled_capacity_days"]>=4
    assert any(w["reason"]=="MULTI_SESSION_LIQUIDITY_CAPACITY_REQUIRES_REEVALUATION"
               for w in result["too_small_or_infeasible_target_warnings"])


def test_untraded_dust_reduces_actual_post_trade_cash_and_preserves_concentration():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="5"
    result=plan("1000.00",spec=spec,positions={"XLK":"501.00"},
                cash="499.00",target={"XLK":"0.50","XLE":"0.449"})
    warnings={x["reason"] for x in result["too_small_or_infeasible_target_warnings"]}
    assert "UNEXECUTABLE_DUST_MAKES_TARGET_APPROXIMATE" in warnings
    assert "POST_COST_CAPITAL_RESERVE_WOULD_BE_BREACHED" in warnings
    assert "POST_COST_SINGLE_POSITION_LIMIT_BREACH" in warnings
    assert "XLK_SELL" not in result["estimated_trade_side_details"]
    # $501 XLK stays held. $449 XLE purchase plus its rounded fee
    # comes out of the original $499 settled cash, not an imaginary sale.
    assert Decimal(result["model_net_cash_reserve_after_all_rebalances_usd"])<Decimal("50")
    assert Decimal(result["post_cost_model_nav_usd"])<Decimal("1000")
    assert not result["live_authorized"]


def test_post_fee_crypto_concentration_is_measured_against_actual_equity():
    result=plan("1000.00",positions={},cash="1000.00",
                target={"XLK":"0.50","XLE":"0.35","BTC/USD":"0.10"})
    warnings={x["reason"] for x in result["too_small_or_infeasible_target_warnings"]}
    assert "POST_COST_CRYPTO_EXPOSURE_LIMIT_BREACH" in warnings
    assert "POST_COST_SINGLE_POSITION_LIMIT_BREACH" in warnings
    assert "POST_COST_GROSS_EXPOSURE_LIMIT_BREACH" in warnings
    assert not result["trading_authorized"]


def test_no_real_live_writer_credentials_fx_or_private_payloads():
    assert x5.BROKER_GETS==x5.BROKER_POSTS==x5.BROKER_ORDERS==0
    assert x5.LIVE_ENABLED is False
    assert x5.MODE=="SYNTHETIC_CAPITAL_MARKET_LIQUIDITY_SCENARIOS_ONLY"
    assert x5.LIVE_CAP_USD=="130.30"
    source=Path(x5.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY",
                "api.alpaca.markets","submit_order(","place_order(","requests.post("):
        assert bad not in source


def test_impossible_buy_ticket_partition_does_not_invent_holdings_or_fees():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["maximum_ticket_usd"]="10"
    # A $15 XLK buy cannot become two tickets of at least $10 each.
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.015","XLE":"0.20"})
    warnings={w["reason"] for w in result["too_small_or_infeasible_target_warnings"]}
    assert "MODELED_TICKET_SPLIT_VIOLATES_MINIMUM" in warnings
    assert "UNEXECUTABLE_MIN_TICKET_SPLIT_MAKES_TARGET_APPROXIMATE" in warnings
    assert "XLK_BUY" not in result["estimated_trade_side_details"]
    assert result["estimated_trade_side_details"]["XLE_BUY"]["hypothetical_notional_usd"]=="200.00"
    assert result["modeled_all_sides_fees_usd"]=="0.30"
    assert result["model_net_cash_reserve_after_all_rebalances_usd"]=="799.70"
    assert result["post_cost_model_nav_usd"]=="999.70"
    assert result["broker_orders"]==0 and not result["trading_authorized"]


def test_impossible_sell_ticket_partition_retains_existing_position():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["maximum_ticket_usd"]="10"
    result=plan("1000.00",spec=spec,positions={"XLK":"15.00"},
                cash="985.00",target={"XLE":"0.20"})
    warnings={w["reason"] for w in result["too_small_or_infeasible_target_warnings"]}
    assert "MODELED_TICKET_SPLIT_VIOLATES_MINIMUM" in warnings
    assert "XLK_SELL" not in result["estimated_trade_side_details"]
    assert result["combined_hypothetical_sell_proceeds_after_costs_usd"]=="0.00"
    assert result["model_net_cash_reserve_after_all_rebalances_usd"]=="784.70"
    assert result["post_trade_holdings_include_untraded_dust"] is True
    assert not result["live_authorized"]


def test_exact_feasible_min_max_ticket_partition_remains_modeled():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["maximum_ticket_usd"]="10"
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.02"})
    assert result["estimated_trade_side_details"]["XLK_BUY"]["modelled_ticket_count"]==2
    assert not any(w["reason"]=="MODELED_TICKET_SPLIT_VIOLATES_MINIMUM"
                   for w in result["too_small_or_infeasible_target_warnings"])


def test_feasible_non_maximal_split_uses_actual_valid_ticket_fee():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["maximum_ticket_usd"]="20"
    spec["XLK"]["modeled_side_cost_bps"]="35"
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.025"})
    assert result["estimated_trade_side_details"]["XLK_BUY"]["modelled_ticket_count"]==2
    assert result["modeled_all_sides_fees_usd"]=="0.10"
    assert result["model_net_cash_reserve_after_all_rebalances_usd"]=="974.90"
    assert not any(w["reason"]=="MODELED_TICKET_SPLIT_VIOLATES_MINIMUM"
                   for w in result["too_small_or_infeasible_target_warnings"])


def test_daily_volume_cap_limits_individual_tickets_and_rounding_costs():
    spec=x5.sample_spec()
    spec["XLK"]["assumed_average_daily_volume_usd"]="2100"  # 0.5% = $10.50/day
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.02101"})
    order=result["estimated_trade_side_details"]["XLK_BUY"]
    assert order["hypothetical_notional_usd"]=="21.01"
    assert order["modeled_effective_max_ticket_after_daily_liquidity_usd"]=="10.50"
    assert order["modelled_ticket_count"]==3
    assert order["modelled_minimum_distinct_execution_days"]>=3
    # Packing ($10.50, $9.51, $1.00) costs 5c, but three roughly
    # equal valid tickets each round to 2c. Bound the unknown split at 6c.
    assert order["modeled_fee_per_ticket_rounded_up_usd"]=="0.06"
    assert result["aggregate_modelled_ticket_count"]==3
    assert result["modeled_all_sides_fees_usd"]=="0.06"
    assert result["ticket_fees_include_per_asset_daily_participation_limit"]
    assert result["modeled_days_are_lower_bound_not_feasible_joint_schedule"]
    assert not result["trading_authorized"]


def test_daily_liquidity_forces_infeasible_minimum_ticket_partition_to_abstain():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["assumed_average_daily_volume_usd"]="2000"  # $10/day
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.015","XLE":"0.20"})
    warnings={x["reason"] for x in result["too_small_or_infeasible_target_warnings"]}
    assert "MODELED_TICKET_SPLIT_VIOLATES_MINIMUM" in warnings
    assert "UNEXECUTABLE_MIN_TICKET_SPLIT_MAKES_TARGET_APPROXIMATE" in warnings
    assert "XLK_BUY" not in result["estimated_trade_side_details"]
    assert result["modeled_all_sides_fees_usd"]=="0.30"
    assert result["model_net_cash_reserve_after_all_rebalances_usd"]=="799.70"
    assert not result["live_authorized"]


def test_daily_participation_below_minimum_ticket_fails_closed():
    spec=x5.sample_spec()
    spec["XLK"]["minimum_notional_usd"]="10"
    spec["XLK"]["assumed_average_daily_volume_usd"]="1999"  # $9.995/day
    with pytest.raises(x5.CapacityStop,match="daily liquidity below minimum ticket"):
        plan("1000.00",spec=spec,positions={},cash="1000.00",
             target={"XLK":"0.20"})


def test_fee_bound_covers_multiple_valid_partitions_not_only_max_first():
    def rounded_fees(parts, bps):
        return sum((x5.up(Decimal(part)*Decimal(bps)/Decimal("10000"))
                    for part in parts), Decimal("0"))
    # Both plans use the MINIMUM three tickets, each <= $10 and >= $1.
    # The old max-first fee estimator reported 5c, understating the
    # equally split feasible plan by 1c.
    bound=x5.fee_upper_by_ticket(
        Decimal("25"),Decimal("10"),Decimal("15"),Decimal("1"))
    assert rounded_fees(["10","10","5"],"15")==Decimal("0.05")
    assert rounded_fees(["8.33","8.33","8.34"],"15")==Decimal("0.06")
    assert bound==Decimal("0.06")
    # Liquidity-constrained example: three separate <=$10.50/day tickets.
    daily_bound=x5.fee_upper_by_ticket(
        Decimal("21.01"),Decimal("10.50"),Decimal("15"),Decimal("1"))
    assert rounded_fees(["10.50","9.51","1.00"],"15")==Decimal("0.05")
    assert rounded_fees(["7.00","7.00","7.01"],"15")==Decimal("0.06")
    assert daily_bound==Decimal("0.06")
    assert x5.fee_upper_by_ticket(
        Decimal("21.01"),Decimal("10.50"),Decimal("0"),Decimal("1"))==0


def test_conservative_fee_bound_preserves_no_trading_and_post_cost_equity():
    spec=x5.sample_spec()
    spec["XLK"]["assumed_average_daily_volume_usd"]="2100"
    result=plan("1000.00",spec=spec,positions={},cash="1000.00",
                target={"XLK":"0.02101"})
    assert result["modeled_all_sides_fees_usd"]=="0.06"
    assert result["post_cost_model_nav_usd"]=="999.94"
    assert result["model_net_cash_reserve_after_all_rebalances_usd"]=="978.93"
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0
    assert result["current_LIVE_authorized_principal_USD"]=="130.30"
    assert not result["trading_authorized"]

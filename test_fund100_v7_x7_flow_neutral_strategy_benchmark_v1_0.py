"""Adversarial synthetic capital-flow versus actual performance tests."""
import pytest
import fund100_v7_x7_flow_neutral_strategy_benchmark_v1_0 as x

def mark(date,nav,index,flow="0.00",boundary="NONE"):
    return {"asof_utc":date,"account_nav_usd":nav,
            "external_flow_usd":flow,"flow_boundary":boundary,
            "benchmark_adjusted_index":index,"mode":x.MODE}

T0="2026-10-01T21:00:00Z"
T1="2026-10-02T21:00:00Z"
T2="2026-10-05T21:00:00Z"

def test_deposit_and_withdrawal_are_not_strategy_returns():
    out=x.evaluate(marks=[
        mark(T0,"100.00","100.00"),
        mark(T1,"220.00","110.00","100.00","BEFORE_PERIOD_RETURN"),
        mark(T2,"181.00","121.00","-50.00","AFTER_PERIOD_RETURN")])
    assert out["fund_flow_neutral_cumulative_return_pct"]=="15.500"
    assert out["benchmark_same_period_cumulative_return_pct"]=="21.00"
    assert out["fund_minus_benchmark_cumulative_return_pp"]=="-5.500"
    assert out["net_external_contributions_usd"]=="50.00"
    assert out["accounting_gain_excluding_net_external_flows_usd"]=="31.00"
    assert out["funded_principal_ceiling_usd_unchanged"]=="130.30"
    assert not out["live_authorized"]

def test_only_deposit_and_no_market_gain_yields_zero_performance():
    v=x.evaluate(marks=[mark(T0,"100.00","100.00"),
                        mark(T1,"1100.00","100.00","1000.00","AFTER_PERIOD_RETURN")])
    assert v["fund_flow_neutral_cumulative_return_pct"]=="0"
    assert v["accounting_gain_excluding_net_external_flows_usd"]=="0.00"
    assert v["capital_ceiling_increase_authorized"] is False

def test_ambiguous_intraperiod_flow_fails_closed():
    with pytest.raises(x.PerformanceStop):
        x.evaluate(marks=[mark(T0,"100.00","100.00"),
                          mark(T1,"200.00","101.00","100.00","UNKNOWN")])
    with pytest.raises(x.PerformanceStop):
        x.evaluate(marks=[mark(T0,"100.00","100.00"),
                          mark(T1,"200.00","101.00","100.00","NONE")])

def test_impossible_withdrawal_and_stale_price_chronology_fail():
    for rows in [
        [mark(T0,"100.00","100.00"),mark(T1,"1.00","99.00","-101.00","BEFORE_PERIOD_RETURN")],
        [mark(T0,"100.00","100.00"),mark(T0,"101.00","99.00")],
        [mark(T0,"100.00","100.00"),mark(T1,"101.00","0.00")],
        [mark(T0,"100.00","100.00"),mark(T1,"101.00","NaN")]]:
        with pytest.raises(x.PerformanceStop):
            x.evaluate(marks=rows)

def test_no_flow_drawdown_reflects_returns_not_deposit_jumps():
    v=x.evaluate(marks=[mark(T0,"100.00","100.00"),
                        mark(T1,"80.00","90.00"),
                        mark(T2,"90.00","99.00")])
    assert v["fund_unitised_max_drawdown_pct"]=="-20.0"
    assert v["fund_flow_neutral_cumulative_return_pct"]=="-10.0000"
    assert v["broker_gets"]==v["broker_posts"]==v["broker_orders"]==0

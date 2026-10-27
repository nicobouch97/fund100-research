"""F1 research factor basket accounting, static benchmark parity, fail closed."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest

import fund100_v7_f1_literature_factor_baseline_v1_0 as f1
import fund100_v7_listed_factor_etf_returns_v1_0 as source

@pytest.fixture(scope="module")
def prices():
    idx=source._nyse_dates(source.FIRST,source.ASOF)
    n=np.arange(len(idx),dtype=float)
    values={
        "MTUM":100*np.exp(.00053*n),
        "QUAL":100*np.exp(.00035*n),
        "SPY":100*np.exp(.00044*n),
        "ACWI":100*np.exp(.00036*n)
    }
    return pd.DataFrame(values,index=idx)

def test_exact_predeclared_portfolio_has_95percent_gross():
    assert sum(f1.FACTOR_WEIGHTS.values())==.95
    assert max(f1.FACTOR_WEIGHTS.values())<=.50
    assert f1.CASH_WEIGHT==.05
    assert set(f1.ARMS)=={"FIXED_FACTOR_QUARTERLY_REBALANCE",
       "FACTOR_BUY_AND_HOLD","SPY_95_BENCHMARK","ACWI_95_BENCHMARK"}

def test_initial_rebalance_conserves_postcost_capital_without_margin():
    original={t:0. for t in source.TICKERS}
    end,cash,fee,turn=f1._costed_rebalance(
        holdings=original,cash=100.,
        prices=pd.Series({t:100. for t in source.TICKERS}),
        target=f1.FACTOR_WEIGHTS,bps=15)
    nav=cash+sum(end.values())
    assert nav+fee==pytest.approx(100.,abs=1e-9)
    assert cash/nav==pytest.approx(.05,abs=1e-9)
    assert end["MTUM"]/nav==pytest.approx(.475,abs=1e-9)
    assert end["QUAL"]/nav==pytest.approx(.475,abs=1e-9)
    assert fee==pytest.approx(turn*.0015,abs=1e-9)

@pytest.mark.parametrize("era",f1.WINDOWS)
def test_each_preset_era_has_same_notional_and_costed_controls(prices,era):
    _,start,end=era
    calc={arm:f1.simulate(prices,start=start,end=end,arm=arm,bps=15)
          for arm in f1.ARMS}
    for arm,record in calc.items():
        assert record["opening_nav_units"]==100
        assert record["closing_nav_after_terminal_sell"]>0
        assert record["charged_total_trade_fees_units"]>0
        assert record["no_actual_orders"] is True
        assert record["same_close_hypothetical_rebalance_execution_not_verified"]
    assert calc["FIXED_FACTOR_QUARTERLY_REBALANCE"]["initial_and_quarterly_rebalance_events"]>1
    assert calc["FACTOR_BUY_AND_HOLD"]["initial_and_quarterly_rebalance_events"]==1
    assert calc["SPY_95_BENCHMARK"]["initial_and_quarterly_rebalance_events"]==1
    assert calc["ACWI_95_BENCHMARK"]["initial_and_quarterly_rebalance_events"]==1
    assert calc["FIXED_FACTOR_QUARTERLY_REBALANCE"]["gross_turnover_of_initial_nav"] > calc["FACTOR_BUY_AND_HOLD"]["gross_turnover_of_initial_nav"]

def test_pure_signal_with_no_score_fitting_and_matched_market_costs(prices):
    r=f1.analyze(prices,captured_utc="2026-10-27T16:00:00Z",
                original_factor_source_id="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE")
    assert r["schema"]==f1.SCHEMA
    assert r["expected_alpha_proven"] is False
    assert r["prospective_return_forecast_available"] is False
    assert r["trading_authorized"] is False
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0
    assert r["original_factor_price_source_sha256"]
    assert r["exact_fixed_portfolio_weights"]=={
        "MTUM":"0.475","QUAL":"0.475","CASH":"0.050"}
    assert "2026_YTD_NOT_A_MODEL_SELECTION_HOLDOUT" in r["historical_hypothetical_comparisons"]
    for era,detail in r["historical_hypothetical_comparisons"].items():
        assert set(detail)=={"5","15","35"}
        for c,arm in detail.items():
            rows=arm["comparators"]
            assert set(rows)==set(f1.ARMS)
            assert arm["factor_quarterly_minus_costed_spy_cagr_percentage_points"]==pytest.approx(
                round(rows["FIXED_FACTOR_QUARTERLY_REBALANCE"]["net_cagr_pct"]-
                      rows["SPY_95_BENCHMARK"]["net_cagr_pct"],7))
            assert arm["factor_quarterly_minus_costed_acwi_cagr_percentage_points"]==pytest.approx(
                round(rows["FIXED_FACTOR_QUARTERLY_REBALANCE"]["net_cagr_pct"]-
                      rows["ACWI_95_BENCHMARK"]["net_cagr_pct"],7))

def test_more_expensive_trading_cannot_make_identical_price_path_more_wealthy(prices):
    values=[f1.simulate(prices,start=f1.WINDOWS[0][1],
                        end=f1.WINDOWS[0][2],arm=f1.ARMS[0],
                        bps=b)["closing_nav_after_terminal_sell"] for b in f1.COSTS]
    assert values[0]>values[1]>values[2]

def test_factor_quarterly_rebalance_does_not_equal_simple_buy_hold(prices):
    _,start,end=f1.WINDOWS[2]
    active=f1.simulate(prices,start=start,end=end,arm=f1.ARMS[0],bps=15)
    passive=f1.simulate(prices,start=start,end=end,arm=f1.ARMS[1],bps=15)
    assert active["charged_total_trade_fees_units"]>passive["charged_total_trade_fees_units"]
    assert active["net_total_return_pct"]!=passive["net_total_return_pct"]

@pytest.mark.parametrize("bad",[
    lambda a:a.drop(columns=["QUAL"]),
    lambda a:a.drop(index=a.index[55]),
    lambda a:a.assign(MTUM=lambda d:d["MTUM"].mask(d.index==d.index[-1],np.nan)),
    lambda a:a.rename(columns={"SPY":"SPYA"}),
])
def test_missing_original_source_and_prices_fail_closed(prices,bad):
    with pytest.raises((f1.FactorBaselineStop,source.ListedFactorStop)):
        f1.analyze(bad(prices),captured_utc="2026-10-27T16:00:00Z",
                   original_factor_source_id="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE")

def test_invalid_original_timestamp_provider_and_hypothetical_costs_rejected(prices):
    with pytest.raises((f1.FactorBaselineStop,source.ListedFactorStop)):
        f1.analyze(prices,captured_utc="2026-10-23T16:00:00Z",
                   original_factor_source_id="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE")
    with pytest.raises(f1.FactorBaselineStop):
        f1.analyze(prices,captured_utc="2026-10-27T16:00:00Z",
                   original_factor_source_id="SYNTHETIC_INVENTED_TRADE_FEED")
    for v in (0,100,True,"15"):
        with pytest.raises(f1.FactorBaselineStop):
            f1.simulate(prices,start=f1.WINDOWS[0][1],
                        end=f1.WINDOWS[0][2],arm=f1.ARMS[0],bps=v)

def test_does_not_permit_hindsight_selected_start_end_or_unknown_strategy(prices):
    for args in (("2017-01-01","2019-12-31",f1.ARMS[0]),
                 (f1.WINDOWS[0][1],f1.WINDOWS[0][2],"RISK_FREE_ALPHA")):
        with pytest.raises(f1.FactorBaselineStop):
            f1.simulate(prices,start=args[0],end=args[1],arm=args[2],bps=15)

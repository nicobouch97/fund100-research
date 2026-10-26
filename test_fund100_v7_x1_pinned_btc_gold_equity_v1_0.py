"""V7-X1 real-shape synthetic tests. No provider network or broker access."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
import exchange_calendars as xcals

import fund100_v7_x1_pinned_btc_gold_equity_v1_0 as x1
import fund100_v6_crossasset_stress_diagnostic_v1_0 as c13

def fixture(*,btc_daily=0.0007,gold_daily=.0002,equity_daily=.0004,rate=4.0):
    etfdates=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2014-01-02"),pd.Timestamp("2026-10-23")).tz_localize(None)
    rate_dates=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2013-12-02"),pd.Timestamp("2026-10-23")).tz_localize(None)
    crypto_dates=pd.date_range("2018-01-01","2026-10-16",freq="D")
    symbols=c13.SYMBOLS
    returns={k:(gold_daily if k=="GLD" else equity_daily) for k in symbols}
    etf=pd.DataFrame({k:100*np.exp(v*np.arange(len(etfdates)))
                      for k,v in returns.items()},index=etfdates)
    crypto=pd.DataFrame({"BTC-USD":100*np.exp(btc_daily*np.arange(len(crypto_dates))),
                         "ETH-USD":100*np.exp(0.0005*np.arange(len(crypto_dates)))},
                        index=crypto_dates)
    rates=pd.DataFrame({"IRX":rate},index=rate_dates)
    return crypto,etf,rates

def test_study_is_distinct_five_registered_nonlevered_portfolios():
    assert set(x1.CANDIDATES)=={
        "CASH_CONTROL_75","GOLD_10","BTC_5","BTC_10","BTC_5_GOLD_5"}
    for name,weights in x1.CANDIDATES.items():
        assert weights[:3]==x1.EQUITY
        assert sum(weights)==pytest.approx(1.)
        assert weights[4]<=.1
        assert max(weights)<.5
    assert x1.FIRST=="2020-01-02" and x1.LAST=="2026-10-16"
    assert x1.ETF_SIDE_BPS==15
    assert x1.COSTS_CRYPTO_BPS==(35,60)

def test_previous_UTC_crypto_bar_only_and_a_future_price_cannot_change_prior():
    btc,etf,rate=fixture()
    baseline,yielded=x1.market_view(btc,etf,rate)
    d=pd.Timestamp("2026-10-16")
    assert d in baseline.index
    unchanged=float(baseline.loc[d,"BTC"])
    assert unchanged==pytest.approx(float(btc.loc["2026-10-15","BTC-USD"]))
    newer=btc.copy()
    newer.loc["2026-10-16","BTC-USD"]*=1.2
    v,_=x1.market_view(newer,etf,rate)
    assert float(v.loc[d,"BTC"])==pytest.approx(unchanged)
    assert baseline.equals(v)
    assert set(yielded)==set(x1.CASH_SCENARIOS)

def test_crypto_cost_increase_strictly_reduces_btc_nav_not_other_controls():
    btc,etf,rate=fixture()
    prices,yields=x1.market_view(btc,etf,rate)
    for name,weights in x1.CANDIDATES.items():
        lo=x1.simulate(prices,yields["IRX_MINUS_50BP"],weights,35)
        hi=x1.simulate(prices,yields["IRX_MINUS_50BP"],weights,60)
        assert len(lo["path"])==len(prices)
        assert len(lo["monthly_rebalances"])>=75
        if weights[4]:
            assert hi["path"].iloc[-1]<lo["path"].iloc[-1]
            assert lo["turnover_abs_weight_sum"]>0
        else:
            assert hi["path"].equals(lo["path"])
        assert lo["path"].min()>0
        assert all(row["crypto_abs_weight_turnover"]>=0
                   for row in lo["monthly_rebalances"])

def test_btc_bull_scenario_positive_but_not_future_alpha():
    btc,etf,rate=fixture(btc_daily=.003,equity_daily=.0001,gold_daily=.0001)
    prices,yields=x1.market_view(btc,etf,rate)
    control=x1.simulate(prices,yields["IRX_MINUS_50BP"],x1.CANDIDATES["CASH_CONTROL_75"],35)
    btc10=x1.simulate(prices,yields["IRX_MINUS_50BP"],x1.CANDIDATES["BTC_10"],35)
    assert btc10["path"].iloc[-1]>control["path"].iloc[-1]
    z=x1.year_log_contribution({"CASH_CONTROL_75":control["path"],
                                "BTC_10":btc10["path"],
                                **{n:control["path"] for n in x1.CANDIDATES
                                   if n not in ("CASH_CONTROL_75","BTC_10")}})
    assert z["BTC_10"]["terminal_relative_log_wealth_pct"]>0
    assert sum(z["BTC_10"]["calendar_year_relative_log_wealth_pct"].values()
               )==pytest.approx(z["BTC_10"]["terminal_relative_log_wealth_pct"],abs=.00001)

def test_btc_bear_scenario_can_be_negative_and_always_shows_drawdown():
    btc,etf,rate=fixture(btc_daily=-.0004,gold_daily=.001,equity_daily=.0004)
    prices,yields=x1.market_view(btc,etf,rate)
    zero=x1.simulate(prices,yields["ZERO"],x1.CANDIDATES["CASH_CONTROL_75"],60)
    btc10=x1.simulate(prices,yields["ZERO"],x1.CANDIDATES["BTC_10"],60)
    gold=x1.simulate(prices,yields["ZERO"],x1.CANDIDATES["GOLD_10"],60)
    assert btc10["path"].iloc[-1]<zero["path"].iloc[-1]<gold["path"].iloc[-1]
    report=x1.path_report(btc10["path"],"2020-01-02","2022-12-30")
    assert report["annualized_volatility_pct"]>=0

def test_crypto_absence_and_missing_market_session_rejected_not_repaired():
    btc,etf,rate=fixture()
    with pytest.raises(x1.AllocationStop,match="validation"):
        x1.market_view(btc.drop(pd.Timestamp("2021-07-04")),etf,rate)
    with pytest.raises(x1.AllocationStop,match="validation"):
        x1.market_view(btc,etf.drop(pd.Timestamp("2020-03-16")),rate)
    bad_btc=btc.copy()
    bad_btc.loc["2020-03-16","BTC-USD"]=np.nan
    with pytest.raises(x1.AllocationStop,match="validation"):
        x1.market_view(bad_btc,etf,rate)

def test_vendor_rate_scenarios_are_lagged_and_no_cash_at_broker_claimed():
    btc,etf,rate=fixture(rate=5.0)
    prices,yields=x1.market_view(btc,etf,rate)
    assert (yields["IRX_GROSS"]>=yields["IRX_MINUS_50BP"]).all()
    assert (yields["IRX_MINUS_50BP"]>=yields["ZERO"]).all()
    alt=rate.copy()
    # Latest IRX quote is not allowed to affect LAST equity session due lag.
    alt.loc["2026-10-23","IRX"]=24.
    data,yields2=x1.market_view(btc,etf,alt)
    for k in x1.CASH_SCENARIOS:
        assert yields[k].equals(yields2[k])

def test_unknown_weights_research_crypto_fee_and_source_hash_fail():
    btc,etf,rate=fixture()
    prices,yields=x1.market_view(btc,etf,rate)
    with pytest.raises(x1.AllocationStop,match="Unregistered"):
        x1.simulate(prices,yields["IRX_GROSS"],(.9,0.,0.,0.,.1,0.),35)
    with pytest.raises(x1.AllocationStop,match="Unregistered"):
        x1.simulate(prices,yields["IRX_GROSS"],x1.CANDIDATES["BTC_5"],0)
    with pytest.raises(x1.AllocationStop,match="Unregistered"):
        x1.simulate(prices,yields["IRX_GROSS"].iloc[:-1],x1.CANDIDATES["BTC_5"],35)

def test_actual_source_roster_sha_pinned_and_zero_broker_order():
    assert x1.ORIGINAL_C1_RUN==39027912139
    assert x1.ORIGINAL_C13_RUN==40298967469
    assert x1.ORIGINAL_C1_ARTIFACT==12099261808
    assert x1.ORIGINAL_C13_ARTIFACT==12638779034
    assert len(x1.CRYPTO_SHA)==len(x1.ETF_SHA)==len(x1.IRX_SHA)==64
    assert x1.RESEARCH_ONLY
    assert x1.BROKER_GETS==x1.BROKER_POSTS==x1.BROKER_ORDERS==0
    from pathlib import Path
    s=Path(x1.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                "api.alpaca.markets","submit_order","place_order"):
        assert bad not in s


def test_passive_spy_same_underlying_matches_costed_sector_control_without_crypto():
    btc,etf,rate=fixture()
    prices,yields=x1.market_view(btc,etf,rate)
    spy=x1.passive_spy_75_reference(etf,yields["IRX_MINUS_50BP"])
    control=x1.simulate(prices,yields["IRX_MINUS_50BP"],
                        x1.CANDIDATES["CASH_CONTROL_75"],35)["path"]
    # In this synthetic source SPY, XLK, XLE and IWM have IDENTICAL returns.
    # Any divergence would mean benchmark fees, cash carry or timing differ.
    assert spy.index.equals(control.index)
    assert float((spy-control).abs().max())<1e-10
    assert spy.iloc[0]==pytest.approx(1.-.75*x1.ETF_SIDE_BPS/10000.)
    faster=etf.copy()
    faster["SPY"]*=np.exp(.00015*np.arange(len(faster)))
    changed=x1.passive_spy_75_reference(faster,yields["IRX_MINUS_50BP"])
    assert changed.iloc[-1]>spy.iloc[-1]
    with pytest.raises(x1.AllocationStop):
        x1.passive_spy_75_reference(etf.drop(pd.Timestamp("2020-03-16")),
                                     yields["IRX_MINUS_50BP"])
    with pytest.raises(x1.AllocationStop):
        x1.passive_spy_75_reference(etf,yields["IRX_MINUS_50BP"].iloc[:-1])


def test_report_contains_source_matched_passive_spy_risk_return_comparator():
    btc,etf,rate=fixture()
    report=x1.inspect(btc,etf,rate)
    assert report["passive_SPY_reference_matches_75pct_equity_and_25pct_cash"]
    assert report["SPY_comparison_is_not_sector_or_factor_risk_matched_alpha"]
    for cost,scenarios in report["results"].items():
        for name,study in scenarios.items():
            ref=study["passive_75pct_SPY_25pct_cash_reference"]
            assert set(ref)=={"2020_2022","2023_2025",
                              "2026_YTD_DESCRIPTIVE_ONLY","full"}
            for window,group in study["return_and_risk_periods"].items():
                for strategy in x1.CANDIDATES:
                    row=group[strategy]
                    assert row["minus_passive_75pct_SPY_25pct_cash_net_cagr_pp"]==pytest.approx(
                        row["net_cagr_pct"]-ref[window]["net_cagr_pct"],abs=.000001)
                    assert row["minus_passive_75pct_SPY_25pct_cash_drawdown_pp"]==pytest.approx(
                        row["max_drawdown_pct"]-ref[window]["max_drawdown_pct"],abs=.000001)
    assert report["broker_gets"]==report["broker_posts"]==report["broker_orders"]==0
    assert not report["candidate_live_promoted"]



def test_same_sleeve_spy_reference_exact_parity_when_equity_prices_identical():
    btc,etf,rate=fixture()
    prices,yields=x1.market_view(btc,etf,rate)
    for coin_cost in x1.COSTS_CRYPTO_BPS:
        reference=x1.same_sleeve_passive_spy_references(
            etf,prices,yields["IRX_MINUS_50BP"],coin_cost)
        for name,weights in x1.CANDIDATES.items():
            original=x1.simulate(
                prices,yields["IRX_MINUS_50BP"],weights,coin_cost)["path"]
            assert reference[name].index.equals(original.index)
            assert float((reference[name]-original).abs().max())<1e-10
        assert float((reference["CASH_CONTROL_75"]-
                      x1.passive_spy_75_reference(
                          etf,yields["IRX_MINUS_50BP"])).abs().max())<1e-10


def test_same_sleeve_spy_comparator_changes_only_equity_and_rejects_mismatched_sources():
    btc,etf,rate=fixture(btc_daily=.002,gold_daily=.0003,equity_daily=.0002)
    prices,yields=x1.market_view(btc,etf,rate)
    cash=yields["IRX_GROSS"]
    original=x1.simulate(prices,cash,x1.CANDIDATES["BTC_5_GOLD_5"],35)["path"]
    faster=etf.copy()
    faster["SPY"]*=np.exp(.0002*np.arange(len(faster)))
    benchmark=x1.same_sleeve_passive_spy_references(
        faster,prices,cash,35)["BTC_5_GOLD_5"]
    assert benchmark.iloc[-1]>original.iloc[-1]
    # Both the sector and passive counterfactual retain identical BTC,
    # gold, cash and crypto-cost assumptions; a different SPY trend
    # affects only the passive equity counterfactual.
    with pytest.raises(x1.AllocationStop,match="calendar, gold or cash"):
        wrong=prices.copy()
        wrong["GLD"]*=1.001
        x1.same_sleeve_passive_spy_references(etf,wrong,cash,35)
    with pytest.raises(x1.AllocationStop):
        x1.same_sleeve_passive_spy_references(
            etf.drop(pd.Timestamp("2020-03-16")),prices,cash,35)
    with pytest.raises(x1.AllocationStop,match="calendar, gold or cash"):
        x1.same_sleeve_passive_spy_references(etf,prices,cash.iloc[:-1],35)


def test_report_separates_sector_selection_from_same_sleeve_asset_allocation():
    btc,etf,rate=fixture()
    result=x1.inspect(btc,etf,rate)
    assert result["same_sleeve_SPY_reference_preserves_BTC_GLD_cash_weights"]
    assert result["same_sleeve_sector_effect_is_retrospective_not_predictive_alpha"]
    for cost,scenarios in result["results"].items():
        for scenario,study in scenarios.items():
            matched=study["same_BTC_GLD_cash_sleeve_SPY_references"]
            assert set(matched)==set(study["return_and_risk_periods"])
            for period,group in study["return_and_risk_periods"].items():
                assert set(matched[period])==set(x1.CANDIDATES)
                for name,metrics in group.items():
                    ref=matched[period][name]
                    for metric,base in (
                        ("net_cagr_pp","net_cagr_pct"),
                        ("drawdown_pp","max_drawdown_pct"),
                        ("volatility_pp","annualized_volatility_pct")):
                        assert metrics["minus_same_sleeve_SPY_"+metric]==pytest.approx(
                            metrics[base]-ref[base],abs=.000001)
                    assert abs(metrics["minus_same_sleeve_SPY_net_cagr_pp"])<1e-5
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0
    assert not result["trading_authorized"]

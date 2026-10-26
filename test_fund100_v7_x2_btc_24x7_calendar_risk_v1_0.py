"""Full-calendar Bitcoin risk tests vs unchanged original X1 session fills."""
import pandas as pd
import numpy as np
import pytest

import fund100_v7_x1_pinned_btc_gold_equity_v1_0 as x1
import fund100_v7_x2_btc_24x7_calendar_risk_v1_0 as x2
from test_fund100_v7_x1_pinned_btc_gold_equity_v1_0 import fixture

def test_calendar_source_really_marks_full_btc_weekends_and_not_future_bars():
    crypto,etf,rate=fixture()
    market,yields,dates,cal,cash=x2.calendar_sources(crypto,etf,rate)
    assert dates.equals(pd.date_range(x1.FIRST,x1.LAST,freq="D"))
    assert len(dates)>len(market)+500
    assert cal.loc["2020-03-15","BTC"]==pytest.approx(
        crypto.loc["2020-03-14","BTC-USD"])
    assert cal.loc["2020-03-15","XLK"]==pytest.approx(
        market.loc["2020-03-13","XLK"])
    assert cal.loc["2020-03-16","BTC"]==pytest.approx(
        crypto.loc["2020-03-15","BTC-USD"])
    assert cal.loc["2020-03-16","XLK"]==pytest.approx(
        market.loc["2020-03-16","XLK"])
    assert set(cash)==set(x1.CASH_SCENARIOS)
    assert all(v.index.equals(dates) for v in cash.values())
    assert cal.loc[market.index,"BTC"].equals(market["BTC"])

def test_unchanged_trades_returns_and_costs_on_every_NYSE_mark():
    crypto,etf,rate=fixture()
    market,yields,dates,cal,cash=x2.calendar_sources(crypto,etf,rate)
    for name in ("CASH_CONTROL_75","BTC_5","BTC_5_GOLD_5","BTC_10"):
        for cost in (35,60):
            old=x1.simulate(market,yields["IRX_MINUS_50BP"],x1.CANDIDATES[name],cost)
            new=x2.mark_every_calendar_day(
                market,dates,cal,cash["IRX_MINUS_50BP"],x1.CANDIDATES[name],cost)
            err=(new["path"].reindex(market.index)-old["path"]).abs()
            assert float(err.max())<1e-8
            assert new["monthly_rebalances"]==len(old["monthly_rebalances"])
            assert new["total_abs_traded_weight"]==pytest.approx(
                old["turnover_abs_weight_sum"],abs=1e-6)
            assert new["nonmarket_calendar_days"]==len(dates)-len(market)
            assert new["path"].iloc[-1]==pytest.approx(old["path"].iloc[-1])

def test_weekend_crash_rebound_hidden_between_friday_and_monday():
    crypto,etf,rate=fixture(btc_daily=0,equity_daily=0,gold_daily=0,rate=0)
    # Saturday UTC bar +50% on a normally closed stock market weekend,
    # then Sunday UTC bar returns to the same baseline before the Monday
    # US close. Quote labelled Saturday is first visible Sunday calendar
    # mark, while Saturday and Monday XNYS session marks don't exist.
    # Uses <=65% BTC one-day source jump and no missing crypto bar.
    crypto.loc["2021-07-10","BTC-USD"]*=1.5
    market,yields,dates,cal,cash=x2.calendar_sources(crypto,etf,rate)
    prior=x1.simulate(market,yields["ZERO"],x1.CANDIDATES["BTC_10"],35)
    actual=x2.mark_every_calendar_day(
        market,dates,cal,cash["ZERO"],x1.CANDIDATES["BTC_10"],35)
    assert actual["btc_cap_exceeded_nonmarket_days_before_next_trade"]>0
    assert float(actual["btc_fraction"].loc["2021-07-11"])>.10
    # The original NYSE only study remains insensitive to a hidden
    # completed UTC Saturday jump fully reversed before Monday.
    unshocked=crypto.copy()
    unshocked.loc["2021-07-10","BTC-USD"]/=1.5
    old_market,old_yields,_,_,_=x2.calendar_sources(unshocked,etf,rate)
    original=x1.simulate(old_market,old_yields["ZERO"],
                         x1.CANDIDATES["BTC_10"],35)
    assert (prior["path"]-original["path"]).abs().max()==pytest.approx(0.)
    assert actual["path"].loc["2021-07-11"]>actual["path"].loc["2021-07-10"]
    assert actual["path"].loc["2021-07-12"]<actual["path"].loc["2021-07-11"]
    assert actual["path"].loc["2021-07-12"]==pytest.approx(
        prior["path"].loc["2021-07-12"],abs=1e-8)

def test_missing_original_Sunday_or_NYSE_quote_fails_without_interpolation():
    crypto,etf,rate=fixture()
    with pytest.raises((x1.AllocationStop,x2.FullCalendarStop),match="source|validation|Bitcoin"):
        x2.calendar_sources(crypto.drop(pd.Timestamp("2021-07-04")),etf,rate)
    with pytest.raises((x1.AllocationStop,x2.FullCalendarStop),match="source|validation|NYSE"):
        x2.calendar_sources(crypto,etf.drop(pd.Timestamp("2021-07-06")),rate)

def test_current_day_btc_quote_never_used_at_same_date_market_close():
    crypto,etf,rate=fixture()
    market,_,_,cal,_=x2.calendar_sources(crypto,etf,rate)
    amended=crypto.copy()
    amended.loc["2026-10-16","BTC-USD"]*=1.5
    _,_,_,changed,_=x2.calendar_sources(amended,etf,rate)
    assert cal.loc["2026-10-16","BTC"]==changed.loc["2026-10-16","BTC"]
    assert cal.loc["2026-10-15","BTC"]==changed.loc["2026-10-15","BTC"]

def test_reject_missing_calendar_and_unregistered_trading_cost():
    crypto,etf,rate=fixture()
    market,yields,days,cal,cash=x2.calendar_sources(crypto,etf,rate)
    with pytest.raises(x2.FullCalendarStop,match="Unqualified"):
        x2.mark_every_calendar_day(
            market,days[:-1],cal,cash["ZERO"],x1.CANDIDATES["BTC_5"],35)
    with pytest.raises(x2.FullCalendarStop,match="Unqualified"):
        x2.mark_every_calendar_day(
            market,days,cal,cash["ZERO"],x1.CANDIDATES["BTC_5"],0)

def test_offline_no_broker_no_new_strategy_promotion():
    assert x2.NO_TRADE and x2.BROKER_ORDERS==0
    assert x2.BROKER_GETS==x2.BROKER_POSTS==0
    assert x2.SCHEMA.startswith("FUND100_V7_X2_")
    from pathlib import Path
    source=Path(x2.__file__).read_text()
    for banned in ("TradingClient","ALPACA_LIVE_SECRET","api.alpaca.markets",
                   "place_order","submit_order","market_order"):
        assert banned not in source


def test_exact_component_dollar_pnl_reconciles_each_day_and_peak_to_trough():
    crypto,etf,rate=fixture(btc_daily=-.0004,equity_daily=-.0002,
                            gold_daily=.0001,rate=0)
    market,_,dates,daily,annual=x2.calendar_sources(crypto,etf,rate)
    study=x2.mark_every_calendar_day(
        market,dates,daily,annual["ZERO"],x1.CANDIDATES["BTC_5_GOLD_5"],35)
    pnl=study["pnl_components"]
    assert tuple(pnl.columns)==(*x1.SLEEVE_ASSETS,"CASH","TRADE_FEES")
    assert (1+pnl.sum(axis=1).cumsum()-study["path"]).abs().max()<1e-8
    assert pnl.loc[dates[0],"TRADE_FEES"]<0
    assert (pnl["TRADE_FEES"]<=0).all()
    d=x2.describe(study["path"],study["btc_fraction"],pnl)
    assert d["component_pnl_reconciled_to_every_calendar_nav"]
    assert sum(d["max_drawdown_component_contribution_pp"].values()
               )==pytest.approx(d["calendar_close_mark_max_drawdown_pct"],abs=1e-5)
    assert d["max_drawdown_component_contribution_pp"]["BTC"]<0
    assert sum(d["full_history_component_pnl_pct_initial_capital"].values()
               )==pytest.approx(d["terminal_net_profit_pct_initial_capital"],abs=1e-5)


def test_btc_weekend_reversal_is_visible_in_exact_dollar_attribution():
    crypto,etf,rate=fixture(btc_daily=0,equity_daily=0,gold_daily=0,rate=0)
    crypto.loc["2021-07-10","BTC-USD"]*=1.5
    market,_,dates,daily,annual=x2.calendar_sources(crypto,etf,rate)
    study=x2.mark_every_calendar_day(
        market,dates,daily,annual["ZERO"],x1.CANDIDATES["BTC_10"],35)
    pnl=study["pnl_components"]
    assert pnl.loc["2021-07-11","BTC"]>0
    assert pnl.loc["2021-07-12","BTC"]<0
    assert pnl.loc["2021-07-11","XLK"]==pytest.approx(0)
    assert pnl.loc["2021-07-11","TRADE_FEES"]==pytest.approx(0)
    assert (1+pnl.sum(axis=1).cumsum()-study["path"]).abs().max()<1e-8


def test_incremental_pnl_reconciles_against_matched_cash_control():
    crypto,etf,rate=fixture(btc_daily=.0008,equity_daily=.0003,
                            gold_daily=.0001,rate=3)
    report=x2.assess(crypto,etf,rate)
    for cost in ("35","60"):
        for scenario in x1.CASH_SCENARIOS:
            control=report["results"][cost][scenario]["CASH_CONTROL_75"]
            assert control["component_pnl_reconciled_to_every_calendar_nav"]
            for name in x1.CANDIDATES:
                if name=="CASH_CONTROL_75":
                    continue
                item=report["results"][cost][scenario][name]
                assert item["incremental_pnl_reconciled_to_cash_control"]
                assert sum(item["incremental_component_pnl_pp_initial_capital"].values()
                           )==pytest.approx(
                    item["incremental_terminal_wealth_pp_initial_capital"],abs=1e-5)
    assert report["trading_authorized"] is False
    assert report["broker_orders"]==0

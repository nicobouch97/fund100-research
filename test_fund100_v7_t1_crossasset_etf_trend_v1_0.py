"""V7 T1 deterministic source/causality/cost/cap/no-broker tests."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

import fund100_v7_t1_crossasset_etf_trend_v1_0 as t

def sample(*,decline=False,short=False):
    import exchange_calendars as xcals
    end="2017-01-10" if short else "2026-10-26"
    ix=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2012-01-03"),pd.Timestamp(end)
    ).tz_localize(None).normalize()
    v=np.arange(len(ix),dtype=float)
    if decline:
        r=np.stack([(1.-.0003*(i+1))**v for i in range(4)],axis=1)
    else:
        r=np.stack([(1.+.00015*(i+1))**v for i in range(4)],axis=1)
    return pd.DataFrame(100*r,columns=t.ASSETS,index=ix)

def test_momentum_uses_prior_close_not_contemporaneous_winner():
    df=sample(short=True)
    i=df.index.get_loc(pd.Timestamp("2014-01-02"))
    target,winners=t._selection(df,i)
    df.loc[df.index[i],"SPY"]*=1.3
    after,winners2=t._selection(df,i)
    assert winners2==winners
    assert np.array_equal(after,target)
    assert max(target[:4])<=.475
    assert target[-1]>=.05
    assert abs(target.sum()-1)<1e-12

def test_fee_dollars_conserve_nav_and_exact_post_trade_cash():
    for b in t.COSTS:
        fee=b/10000.
        nav,position,cash,expense,turnover=t._reweight(
            100.,np.zeros(4),np.array([.475,.475,0.,0.,.05]),fee)
        assert nav<100 and expense>0
        assert abs(nav+expense-100)<1e-9
        assert abs(sum(position)+cash-nav)<1e-9
        assert cash/nav==pytest.approx(.05)
        assert max(position/nav)==pytest.approx(.475)
        assert expense==pytest.approx(fee*turnover)

def test_exact_zero_positive_momentum_goes_to_cash_without_future_signals():
    df=sample(decline=True,short=True)
    i=df.index.get_loc(pd.Timestamp("2014-01-02"))
    weight,winners=t._selection(df,i)
    assert winners==[]
    assert np.array_equal(weight,np.array([0.,0.,0.,0.,1.]))
    r=t.simulate(df,start="2014-01-02",end="2016-12-30",
                 side_bps=15,strategy="CROSS_ASSET_12_1")
    assert r["transaction_dates"]>=1
    assert r["modeled_fees_usd_per_100_initial_usd"]==pytest.approx(0.)
    assert r["net_annualized_return_pct"]==pytest.approx(0.)

def test_posthoc_exposure_matched_four_equal_control_has_same_signal_budget():
    df=sample(short=True)
    trend=t.simulate(df,start="2014-01-02",end="2016-12-30",
                     side_bps=15,strategy="CROSS_ASSET_12_1")
    matched=t.simulate(df,start="2014-01-02",end="2016-12-30",
                       side_bps=15,strategy="EXPOSURE_MATCHED_FOUR_EQUAL")
    left,right=trend["signal_trade_log"],matched["signal_trade_log"]
    assert len(left)==len(right)>10
    assert trend["transaction_dates"]==matched["transaction_dates"]
    for a,b in zip(left,right):
        assert a["close"]==b["close"]
        assert a["source_signal_previous_complete_session"]==(
            b["source_signal_previous_complete_session"])
        assert a["target_gross_fraction"]==b["target_gross_fraction"]
        assert a["same_decision_positive_momentum_count"]==(
            b["same_decision_positive_momentum_count"])
        assert a["target_gross_fraction"]==.95
        assert len(a["hypothetical_positions"])==2
        assert b["hypothetical_positions"]==list(t.ASSETS)
    # Four-ETF matched control incurs a separate costed trading path,
    # rather than copying the trend strategy's return or fee drag.
    assert matched["modeled_fees_usd_per_100_initial_usd"]>0
    assert matched["net_total_return_pct"]!=trend["net_total_return_pct"]


def test_exposure_matched_control_remains_all_cash_if_no_positive_momentum():
    df=sample(decline=True,short=True)
    result=t.simulate(df,start="2014-01-02",end="2016-12-30",
                      side_bps=35,strategy="EXPOSURE_MATCHED_FOUR_EQUAL")
    assert result["net_total_return_pct"]==0
    assert result["modeled_fees_usd_per_100_initial_usd"]==0
    assert all(x["target_gross_fraction"]==0 for x in result["signal_trade_log"])
    assert all(x["hypothetical_positions"]==[] for x in result["signal_trade_log"])


def test_same_asset_passive_four_vs_standalone_spy_friction_distinguished():
    df=sample(short=True)
    r=t.simulate(df,start="2014-01-02",end="2016-12-30",
                 side_bps=15,strategy="STATIC_FOUR_EQUAL")
    s=t.simulate(df,start="2014-01-02",end="2016-12-30",
                 side_bps=15,strategy="STATIC_SPY")
    assert r["transaction_dates"]==s["transaction_dates"]==1
    assert r["modeled_fees_usd_per_100_initial_usd"]>0
    assert s["modeled_fees_usd_per_100_initial_usd"]>0
    assert r["net_annualized_return_pct"]!=s["net_annualized_return_pct"]
    assert r["original_high_risk_breach_sessions"]["single_50pct"]==0

def test_flat_market_fee_risk_uses_actual_entry_and_exit_sessions():
    # No price movement: risk comes ONLY from entry and terminal liquidation.
    # Previously annualized volatility was zero because both fees were
    # excluded from daily returns, and the terminal fee was appended as an
    # invented extra market observation.
    df=sample(short=True)
    df.loc[:,list(t.ASSETS)]=100.
    first="2014-01-02"
    last="2016-12-30"
    result=t.simulate(df,start=first,end=last,
                      side_bps=15,strategy="STATIC_SPY")
    n=len(df.loc[first:last])
    entry,holdings,cash,fee,turnover=t._reweight(
        100.,np.zeros(4),np.array([.95,0.,0.,0.,.05]),.0015)
    terminal=entry-.0015*sum(holdings)
    expected_daily=np.r_[entry/100.-1.,np.zeros(n-2),terminal/entry-1.]
    assert result["risk_path_observed_session_count"]==n
    assert result["risk_path_includes_entry_and_exit_fees_on_actual_close_sessions"]
    assert result["net_total_return_pct"]==pytest.approx(terminal-100,abs=1e-6)
    assert result["max_drawdown_pct"]==pytest.approx(
        100*(terminal/100.-1.),abs=1e-6)
    assert result["annualized_volatility_fraction"]==pytest.approx(
        np.std(expected_daily,ddof=1)*np.sqrt(252),abs=1e-8)
    assert result["annualized_volatility_fraction"]>0
    assert result["worst_modeled_session_return_including_fees_pct"]==pytest.approx(
        100*min(expected_daily),abs=1e-6)
    assert result["worst_close_to_close_return_pct"]==(
        result["worst_modeled_session_return_including_fees_pct"])


def test_terminal_liquidation_can_trigger_daily_risk_breach():
    # A 6.2% final-day SPY fall becomes a 5.89% portfolio decline before
    # liquidation; 35bp final SELL friction pushes the day below -6%.
    df=sample(short=True)
    df.loc[:,list(t.ASSETS)]=100.
    df.loc[pd.Timestamp("2016-12-30"),"SPY"]=93.8
    result=t.simulate(df,start="2014-01-02",end="2016-12-30",
                      side_bps=35,strategy="STATIC_SPY")
    assert result["worst_modeled_session_return_including_fees_pct"]< -6.
    assert result["original_high_risk_breach_sessions"][
        "account_day_below_minus_6pct"]==1


def test_fee_stress_reduces_total_net_returns():
    df=sample(short=True)
    lo=t.simulate(df,start="2014-01-02",end="2016-12-30",
                  side_bps=5,strategy="CROSS_ASSET_12_1")
    hi=t.simulate(df,start="2014-01-02",end="2016-12-30",
                  side_bps=35,strategy="CROSS_ASSET_12_1")
    assert lo["net_total_return_pct"]>hi["net_total_return_pct"]
    assert lo["transaction_dates"]==hi["transaction_dates"]
    assert lo["signal_trade_log"][0]["source_signal_previous_complete_session"]<lo["signal_trade_log"][0]["close"]

def test_source_gaps_nans_hindsight_windows_and_instrument_additions_refused():
    df=sample(short=True)
    cases=[
        df.drop(df.index[300]),
        df.assign(DBC=np.nan),
        df.assign(BTC=100),
        df.sort_index(ascending=False),
    ]
    for corrupt in cases:
        with pytest.raises(t.CrossAssetTrendStop):
            # Data shape catches all except a common missing XNYS session.
            t.analyze(corrupt,"2017-01-11T09:30:00Z")
    with pytest.raises(t.CrossAssetTrendStop):
        t.simulate(df,start="2015-01-02",end="2016-12-30",
                   side_bps=15,strategy="CROSS_ASSET_12_1")
    with pytest.raises(t.CrossAssetTrendStop):
        t.simulate(df,start="2014-01-02",end="2016-12-30",
                   side_bps=0,strategy="CROSS_ASSET_12_1")

def test_future_dated_vendor_receipt_rejected_against_actual_utc_clock(monkeypatch):
    # The price panel is otherwise valid, the date is within the allowed
    # five-day source freshness window, and the claimed receipt is T+1.
    # It must NOT pass if the stated acquisition has not actually occurred.
    df=sample()
    monkeypatch.setattr(t,"_now_utc",lambda:datetime(
        2026,10,27,11,0,0,tzinfo=timezone.utc))
    with pytest.raises(t.CrossAssetTrendStop,match="Stale or future-dated"):
        t.analyze(df,"2026-10-28T09:00:00Z")
    accepted=t.analyze(df,"2026-10-27T11:00:00Z")
    assert accepted["trading_authorized"] is False
    assert accepted["real_broker_orders"]==0


def test_frozen_research_report_labels_not_forward_alpha_or_trade():
    df=sample()
    r=t.analyze(df,"2026-10-27T11:00:00Z")
    assert r["schema"]==t.SCHEMA
    assert r["trading_authorized"] is False
    assert r["real_broker_gets"]==r["real_broker_posts"]==r["real_broker_orders"]==0
    assert r["favorable_result_is_not_forward_alpha_qualification"] is True
    assert r["exposure_matched_control_uses_same_momentum_equity_budget"] is True
    assert r["exposure_matched_control_added_post_hoc_not_new_alpha_gate"] is True
    assert set(r["fixed_era_results"])==set(t.REGISTERED_WINDOWS)
    assert set(r["fixed_era_results"]["2014_2016"]["15"])=={
        "CROSS_ASSET_12_1","EXPOSURE_MATCHED_FOUR_EQUAL",
        "STATIC_FOUR_EQUAL","STATIC_SPY"}
    for row in r["fixed_era_results"].values():
        for v in row.values():
            for portfolio in v.values():
                assert portfolio["no_actual_orders"]
                assert portfolio["transaction_dates"]>=1
    with pytest.raises(t.CrossAssetTrendStop):
        t.analyze(df,"2026-10-26T16:00:00Z")

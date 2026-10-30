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


def test_yearly_log_wealth_reconciles_costed_entry_and_exit_without_fake_day():
    # Flat SPY: only first-year entry fee and last-year liquidation fee.
    df=sample(short=True)
    df.loc[:,list(t.ASSETS)]=100.
    out=t.simulate(df,start="2014-01-02",end="2016-12-30",
                   side_bps=15,strategy="STATIC_SPY")
    years=out["annual_net_log_wealth_pct"]
    assert list(years)==["2014","2015","2016"]
    assert years["2014"]<0 and years["2016"]<0
    assert years["2015"]==pytest.approx(0,abs=1e-8)
    assert sum(years.values())==pytest.approx(
        out["terminal_net_log_wealth_pct"],abs=1e-7)
    assert out["annual_log_wealth_includes_entry_and_exit_costs"]


def test_paired_annual_relative_wealth_is_additive_and_diagnostic_only():
    df=sample(short=True)
    candidate=t.simulate(df,start="2014-01-02",end="2016-12-30",
                         side_bps=15,strategy="CROSS_ASSET_12_1")
    static=t.simulate(df,start="2014-01-02",end="2016-12-30",
                      side_bps=15,strategy="STATIC_FOUR_EQUAL")
    matched=t.simulate(df,start="2014-01-02",end="2016-12-30",
                       side_bps=15,strategy="EXPOSURE_MATCHED_FOUR_EQUAL")
    for control in (static,matched):
        report=t._paired_yearly_relative_log_wealth(candidate,control)
        annual=report["calendar_year_relative_net_log_wealth_pp"]
        assert list(annual)==["2014","2015","2016"]
        assert sum(annual.values())==pytest.approx(
            report["terminal_relative_net_log_wealth_pp"],abs=1e-6)
        assert report["terminal_relative_net_log_wealth_pp"]==pytest.approx(
            candidate["terminal_net_log_wealth_pct"]
            -control["terminal_net_log_wealth_pct"],abs=1e-7)
        assert report["descriptive_posthoc_not_independent_alpha_evidence"]
        if report["strongest_positive_year"] is not None:
            y=report["strongest_positive_year"]
            assert report["relative_log_wealth_ex_strongest_positive_year_pp"]==(
                pytest.approx(report["terminal_relative_net_log_wealth_pp"]
                              -annual[y],abs=1e-7))
    bad=dict(matched)
    bad["annual_net_log_wealth_pct"]={"2015":0.}
    with pytest.raises(t.CrossAssetTrendStop,match="Nonmatching"):
        t._paired_yearly_relative_log_wealth(candidate,bad)
    tampered=dict(matched)
    tampered["terminal_net_log_wealth_pct"]+=10.
    with pytest.raises(t.CrossAssetTrendStop,match="reconciliation"):
        t._paired_yearly_relative_log_wealth(candidate,tampered)


def test_annual_diagnostic_does_not_change_original_all_era_promotion_rule():
    df=sample()
    report=t.analyze(df,"2026-10-27T11:00:00Z")
    assert report["annual_concentration_diagnostic_not_promotion_gate"]
    assert set(report["posthoc_15bps_annual_relative_log_wealth"])==(
        set(t.REGISTERED_WINDOWS))
    assert report["tested_15bps_strong_all_three_eras"]==all(
        report["fixed_era_results"][era]["15"]["CROSS_ASSET_12_1"][
            "net_annualized_return_pct"]>
        report["fixed_era_results"][era]["15"]["STATIC_FOUR_EQUAL"][
            "net_annualized_return_pct"]
        for era in ("2014_2016","2017_2020","2021_2025"))
    for controls in report["posthoc_15bps_annual_relative_log_wealth"].values():
        assert set(controls)=={
            "vs_original_static_four_equal",
            "vs_posthoc_exposure_matched_four_equal"}
        assert all(row["same_sessions_and_separately_costed"]
                   for row in controls.values())


def test_next_session_execution_stress_preserves_frozen_signals_and_fees():
    df=sample(short=True)
    base=t.simulate(df,start="2014-01-02",end="2016-12-30",
                    side_bps=15,strategy="CROSS_ASSET_12_1")
    delayed=t.simulate(df,start="2014-01-02",end="2016-12-30",
                       side_bps=15,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    assert delayed["next_close_execution_diagnostic_only"]
    assert not base["next_close_execution_diagnostic_only"]
    assert delayed["unexecuted_terminal_decisions"]==0
    assert delayed["transaction_dates"]==base["transaction_dates"]
    for original,lagged in zip(base["signal_trade_log"],
                               delayed["signal_trade_log"],strict=True):
        for key in ("close","source_signal_previous_complete_session",
                    "hypothetical_positions","target_gross_fraction",
                    "same_decision_positive_momentum_count"):
            assert original[key]==lagged[key]
        decision=pd.Timestamp(lagged["close"])
        assert lagged["modeled_execution_close"]==(
            df.index[df.index.get_loc(decision)+1].date().isoformat())
        assert original["modeled_execution_close"]==original["close"]
        assert original["same_close_idealized_fee_charged"]
        assert not lagged["same_close_idealized_fee_charged"]
    assert delayed["modeled_fees_usd_per_100_initial_usd"]>0
    assert delayed["no_actual_orders"]


def test_next_session_stress_exposes_unfillable_first_close_shock():
    df=sample(short=True)
    # On the first modeled entry, DBC and GLD have the strongest positive
    # predeclared momentum. A one-session 20% price jump is already earned
    # by a same-close hypothetical fill, but NOT by the next-close fill.
    day=pd.Timestamp("2014-01-03")
    df.loc[day,["DBC","GLD"]]*=1.20
    original=t.simulate(df,start="2014-01-02",end="2016-12-30",
                        side_bps=15,strategy="CROSS_ASSET_12_1")
    lagged=t.simulate(df,start="2014-01-02",end="2016-12-30",
                      side_bps=15,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    assert original["signal_trade_log"][0]["hypothetical_positions"]==[
        "DBC","GLD"]
    assert lagged["net_total_return_pct"]<original["net_total_return_pct"]
    assert lagged["signal_trade_log"][0]["modeled_execution_close"]=="2014-01-03"


def test_terminal_month_first_decision_is_not_fabricated_as_filled(monkeypatch):
    # If the study ends on a new month's first session, no future close
    # exists in the registered window: record a pending, unfilled decision.
    monkeypatch.setattr(t,"REGISTERED_WINDOWS",
                        {"TEST":("2014-01-02","2014-04-01")})
    result=t.simulate(sample(short=True),start="2014-01-02",
                      end="2014-04-01",side_bps=35,
                      strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    assert result["unexecuted_terminal_decisions"]==1
    assert result["signal_trade_log"][-1]["close"]=="2014-04-01"
    assert result["signal_trade_log"][-1]["modeled_execution_close"] is None
    assert result["transaction_dates"]==len(result["signal_trade_log"])-1


def test_execution_stress_is_diagnostic_not_an_alpha_promotion_gate():
    report=t.analyze(sample(),"2026-10-27T11:00:00Z")
    assert report["next_close_stress_not_a_new_promotion_gate"]
    assert set(report["next_close_execution_stress"])==set(t.REGISTERED_WINDOWS)
    for era,fees in report["next_close_execution_stress"].items():
        assert set(fees)=={"5","15","35"}
        for bps,stress in fees.items():
            assert stress["same_frozen_signal_decisions"]
            assert stress["diagnostic_only_not_new_promotion_gate"]
            delayed=stress["next_close_costed_path"]
            base=report["fixed_era_results"][era][bps]["CROSS_ASSET_12_1"]
            assert stress["next_close_minus_same_close_net_cagr_pp"]==pytest.approx(
                delayed["net_annualized_return_pct"]-
                base["net_annualized_return_pct"],abs=1e-6)
            assert delayed["no_actual_orders"]
    assert report["tested_15bps_strong_all_three_eras"]==all(
        report["fixed_era_results"][era]["15"]["CROSS_ASSET_12_1"][
            "net_annualized_return_pct"]>
        report["fixed_era_results"][era]["15"]["STATIC_FOUR_EQUAL"][
            "net_annualized_return_pct"]
        for era in ("2014_2016","2017_2020","2021_2025"))
    assert not report["trading_authorized"]


def test_delayed_cross_asset_all_cash_regime_never_invents_trades():
    # A negative-momentum regime must not turn an execution delay into
    # invented buying, turnover or cost. It must respect the same frozen
    # all-cash decision at all originally registered fee levels.
    panel=sample(decline=True,short=True)
    for bps in t.COSTS:
        immediate=t.simulate(panel,start="2014-01-02",end="2016-12-30",
                             side_bps=bps,strategy="CROSS_ASSET_12_1")
        delayed=t.simulate(panel,start="2014-01-02",end="2016-12-30",
                           side_bps=bps,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
        assert immediate["net_total_return_pct"]==0
        assert delayed["net_total_return_pct"]==0
        assert delayed["modeled_fees_usd_per_100_initial_usd"]==0
        assert delayed["gross_traded_notional_per_100_initial_usd"]==0
        assert delayed["unexecuted_terminal_decisions"]==0
        assert len(delayed["signal_trade_log"])==len(immediate["signal_trade_log"])
        assert all(x["hypothetical_positions"]==[]
                   and x["target_gross_fraction"]==0
                   and x["modeled_execution_close"] is not None
                   for x in delayed["signal_trade_log"])
        assert delayed["no_actual_orders"]


def test_next_close_queued_trade_on_terminal_session_is_not_round_tripped(monkeypatch):
    # April 1 is the first trading session of the month. Its target is
    # queued for April 2, but April 2 is also the study's terminal close.
    # A buy followed by an immediate liquidation has zero holding period,
    # and must not incur artificial two-sided churn.
    df=sample(short=True)
    df.loc[pd.Timestamp("2014-04-02"),list(t.ASSETS)]=(
        df.loc[pd.Timestamp("2014-04-01"),list(t.ASSETS)].to_numpy())
    monkeypatch.setattr(t,"REGISTERED_WINDOWS",
                        {"BEFORE":("2014-01-02","2014-04-01"),
                         "TERMINAL":("2014-01-02","2014-04-02")})
    before=t.simulate(df,start="2014-01-02",end="2014-04-01",
                      side_bps=35,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    terminal=t.simulate(df,start="2014-01-02",end="2014-04-02",
                        side_bps=35,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    assert terminal["unexecuted_terminal_decisions"]==1
    assert terminal["signal_trade_log"][-1]["close"]=="2014-04-01"
    assert terminal["signal_trade_log"][-1]["modeled_execution_close"] is None
    assert terminal["transaction_dates"]==before["transaction_dates"]
    assert terminal["gross_traded_notional_per_100_initial_usd"]==(
        before["gross_traded_notional_per_100_initial_usd"])
    assert terminal["modeled_fees_usd_per_100_initial_usd"]==(
        before["modeled_fees_usd_per_100_initial_usd"])
    assert terminal["net_total_return_pct"]==pytest.approx(
        before["net_total_return_pct"],abs=1e-6)


def test_next_close_nonterminal_session_still_executes_queued_trade(monkeypatch):
    # A real intervening holding interval is different: the April 1
    # decision executes on April 2 if April 3 remains in the window.
    monkeypatch.setattr(t,"REGISTERED_WINDOWS",
                        {"INTERVAL":("2014-01-02","2014-04-03")})
    result=t.simulate(sample(short=True),start="2014-01-02",
                      end="2014-04-03",side_bps=15,
                      strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    assert result["unexecuted_terminal_decisions"]==0
    assert result["signal_trade_log"][-1]["close"]=="2014-04-01"
    assert result["signal_trade_log"][-1]["modeled_execution_close"]=="2014-04-02"
    assert result["transaction_dates"]==len(result["signal_trade_log"])
    assert result["no_actual_orders"]


def test_invalid_vendor_adjusted_return_identifies_asset_and_dates_fail_closed():
    panel=sample(short=True)
    date=pd.Timestamp("2015-05-05")
    panel.loc[date,"GLD"]*=1.6
    with pytest.raises(t.CrossAssetTrendStop,
                       match=r"GLD 2015-05-04 to 2015-05-05 adjusted_return=\+0\.60"):
        t.prices_validate(panel)


def test_invalid_vendor_nonfinite_value_identifies_asset_and_date():
    panel=sample(short=True)
    panel.loc[pd.Timestamp("2015-05-05"),"TLT"]=float("nan")
    with pytest.raises(t.CrossAssetTrendStop,match=r"TLT 2015-05-05 value=nan"):
        t.prices_validate(panel)


def test_rejected_vendor_panel_is_quarantined_not_accepted(monkeypatch,tmp_path):
    import sys
    from types import SimpleNamespace
    panel=sample(short=True)
    panel.loc[pd.Timestamp("2015-05-05"),"DBC"]*=1.6
    vendor=pd.DataFrame({("Close",asset):panel[asset] for asset in t.ASSETS})
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(
        download=lambda **kwargs: vendor))
    rejected=tmp_path/"quarantine"/"rejected.csv"
    accepted=tmp_path/"accepted.csv"
    with pytest.raises(t.CrossAssetTrendStop,match="DBC"):
        t.download_prices(rejected_source_csv=rejected)
    assert rejected.is_file()
    assert not accepted.exists()
    actual=pd.read_csv(rejected,index_col="Date")
    assert actual.loc["2015-05-05","DBC"]==pytest.approx(
        panel.loc[pd.Timestamp("2015-05-05"),"DBC"])
    panel.loc[pd.Timestamp("2015-05-05"),"DBC"]/=1.6
    clean=pd.DataFrame({("Close",asset):panel[asset] for asset in t.ASSETS})
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(
        download=lambda **kwargs: clean))
    t.download_prices(rejected_source_csv=tmp_path/"clean-must-not-exist.csv")
    assert not (tmp_path/"clean-must-not-exist.csv").exists()


def _recent_vendor_panel():
    # Complete genuine XNYS dates through 29 Oct 2026; only the terminal
    # SPY observation is withheld to model the observed vendor defect.
    df=sample()
    for day in ("2026-10-27","2026-10-28","2026-10-29"):
        df.loc[pd.Timestamp(day),list(t.ASSETS)]=(
            df.iloc[-1].to_numpy(dtype=float)*1.0001)
    return df.sort_index()


def test_recent_terminal_missing_vendor_value_excludes_only_last_session():
    raw=_recent_vendor_panel()
    raw.loc[pd.Timestamp("2026-10-29"),"SPY"]=float("nan")
    complete,excluded=t._accept_recent_incomplete_vendor_tail(
        raw,observed_utc=datetime(2026,10,30,2,0,tzinfo=timezone.utc))
    assert excluded=="2026-10-29"
    assert complete.index[-1]==pd.Timestamp("2026-10-28")
    assert len(complete)==len(raw)-1
    assert complete.notna().all().all()
    assert list(complete.columns)==list(t.ASSETS)
    t._calendar(complete.index)
    assert not t.TRADING_AUTHORIZED


def test_vendor_tail_exclusion_rejects_stale_and_not_yet_closed_sessions():
    raw=_recent_vendor_panel()
    raw.loc[pd.Timestamp("2026-10-29"),"SPY"]=float("nan")
    for stamp in (datetime(2026,10,30,13,0,tzinfo=timezone.utc),
                  datetime(2026,10,29,19,0,tzinfo=timezone.utc)):
        with pytest.raises(t.CrossAssetTrendStop,match="12 hours"):
            t._accept_recent_incomplete_vendor_tail(raw,observed_utc=stamp)


def test_vendor_tail_never_hides_historical_gap_or_two_missing_sessions():
    raw=_recent_vendor_panel()
    raw.loc[pd.Timestamp("2026-10-29"),"SPY"]=float("nan")
    raw.loc[pd.Timestamp("2019-01-03"),"TLT"]=float("nan")
    with pytest.raises(t.CrossAssetTrendStop,match="TLT 2019-01-03"):
        t._accept_recent_incomplete_vendor_tail(
            raw,observed_utc=datetime(2026,10,30,2,0,tzinfo=timezone.utc))
    raw.loc[pd.Timestamp("2019-01-03"),"TLT"]=sample().loc[
        pd.Timestamp("2019-01-03"),"TLT"]
    raw.loc[pd.Timestamp("2026-10-28"),"GLD"]=float("nan")
    with pytest.raises(t.CrossAssetTrendStop,match="GLD 2026-10-28"):
        t._accept_recent_incomplete_vendor_tail(
            raw,observed_utc=datetime(2026,10,30,2,0,tzinfo=timezone.utc))


def test_vendor_tail_does_not_hide_price_jump_or_missing_market_session():
    raw=_recent_vendor_panel()
    raw.loc[pd.Timestamp("2026-10-29"),"SPY"]=float("nan")
    raw.loc[pd.Timestamp("2026-10-29"),"DBC"]*=1.6
    with pytest.raises(t.CrossAssetTrendStop,match="also contains invalid"):
        t._accept_recent_incomplete_vendor_tail(
            raw,observed_utc=datetime(2026,10,30,2,0,tzinfo=timezone.utc))
    raw.loc[pd.Timestamp("2026-10-29"),"DBC"]/=1.6
    raw=raw.drop(pd.Timestamp("2026-10-27"))
    with pytest.raises(t.CrossAssetTrendStop,match="calendar"):
        t._accept_recent_incomplete_vendor_tail(
            raw,observed_utc=datetime(2026,10,30,2,0,tzinfo=timezone.utc))


def test_original_vendor_bytes_and_excluded_date_are_preserved(monkeypatch,tmp_path):
    import sys
    from hashlib import sha256
    from types import SimpleNamespace
    raw=_recent_vendor_panel()
    raw.loc[pd.Timestamp("2026-10-29"),"SPY"]=float("nan")
    vendor=pd.DataFrame({("Close",asset):raw[asset] for asset in t.ASSETS})
    monkeypatch.setitem(sys.modules,"yfinance",SimpleNamespace(
        download=lambda **kwargs: vendor))
    monkeypatch.setattr(t,"_now_utc",lambda:datetime(
        2026,10,30,2,0,tzinfo=timezone.utc))
    original=tmp_path/"raw-vendor.csv"
    rejected=tmp_path/"rejected.csv"
    accepted=t.download_prices(rejected_source_csv=rejected,
                               raw_vendor_csv=original)
    assert accepted.index[-1]==pd.Timestamp("2026-10-28")
    assert accepted.attrs["excluded_recent_incomplete_vendor_session"]==(
        "2026-10-29")
    assert original.is_file() and not rejected.exists()
    assert sha256(original.read_bytes()).hexdigest()==(
        accepted.attrs["vendor_raw_csv_sha256"])
    vendor_rows=pd.read_csv(original)
    assert vendor_rows["Date"].iloc[-1]=="2026-10-29"
    assert pd.isna(vendor_rows["SPY"].iloc[-1])
    assert len(vendor_rows)==len(accepted)+1


def test_next_close_policy_repair_sells_only_after_prior_breach():
    # Original top-two monthly signal selects GLD/DBC. A persistent 25%
    # GLD repricing creates >50% single-name weight after the entry.
    # Repair must be requested on a completed prior close and sold only
    # at a subsequent close, with post-fee caps and no new purchases.
    df=sample(short=True)
    shock=pd.Timestamp("2014-01-07")
    df.loc[df.index>=shock,"GLD"]*=1.25
    baseline=t.simulate(df,start="2014-01-02",end="2016-12-30",
                        side_bps=15,strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
    repaired=t.simulate(df,start="2014-01-02",end="2016-12-30",
                        side_bps=15,
                        strategy="CROSS_ASSET_12_1_NEXT_CLOSE_RISK_REPAIR")
    assert repaired["risk_repair_requested_closes"]>=1
    assert repaired["risk_repair_actual_sell_closes"]>=1
    completed=[r for r in repaired["risk_repair_log"]
               if r["sell_only_notional_per_100_initial_usd"] is not None
               and r["sell_only_notional_per_100_initial_usd"]>0]
    assert completed
    for row in completed:
        assert row["modeled_execution_close"]>row["breach_observed_close"]
        assert row["post_repair_max_single_weight"]<=.5+1e-8
        assert row["post_repair_gross_weight"]<=.95+1e-8
        assert row["repair_cost_per_100_initial_usd"]>0
    assert repaired["modeled_fees_usd_per_100_initial_usd"]>0
    assert repaired["signal_trade_log"]==baseline["signal_trade_log"]
    assert repaired["no_actual_orders"]
    assert repaired["risk_repair_posthoc_policy_feasibility_not_alpha"]


def test_policy_repair_is_sell_only_fee_conserving_and_skips_healed_breach():
    pos=np.array([60.,20.,10.,0.])
    for bps in t.COSTS:
        post,new,cash,paid,sold=t._sell_only_policy_repair(100.,pos,bps/10000.)
        assert (new<=pos+1e-10).all()
        assert max(new)/post<=.5+1e-9
        assert sum(new)/post<=.95+1e-9
        assert cash/post>=.05-1e-9
        assert 100.-post==pytest.approx(paid,abs=1e-8)
        assert paid==pytest.approx(sold*bps/10000.,abs=1e-8)
    post,new,cash,paid,sold=t._sell_only_policy_repair(
        100.,np.array([40.,35.,10.,0.]),.0015)
    assert post==100. and paid==sold==0.
    assert np.array_equal(new,np.array([40.,35.,10.,0.]))
    with pytest.raises(t.CrossAssetTrendStop):
        t._sell_only_policy_repair(100.,np.array([120.,0.,0.,0.]),.0015)


def test_policy_repair_all_cash_never_invents_trades_or_promotion():
    df=sample(decline=True,short=True)
    repaired=t.simulate(df,start="2014-01-02",end="2016-12-30",
        side_bps=35,strategy="CROSS_ASSET_12_1_NEXT_CLOSE_RISK_REPAIR")
    assert repaired["risk_repair_requested_closes"]==0
    assert repaired["risk_repair_actual_sell_closes"]==0
    assert repaired["net_total_return_pct"]==0
    assert repaired["modeled_fees_usd_per_100_initial_usd"]==0
    report=t.analyze(sample(),"2026-10-27T11:00:00Z")
    assert report["policy_repair_not_a_new_promotion_gate"]
    assert set(report["posthoc_next_close_high_policy_repair"])==set(t.REGISTERED_WINDOWS)
    for era,by_cost in report["posthoc_next_close_high_policy_repair"].items():
        assert set(by_cost)=={"5","15","35"}
        for bps,diagnostic in by_cost.items():
            assert diagnostic["posthoc_not_promotion_or_broker_risk_enforcement"]
            assert diagnostic["sell_only_next_close_policy_repair_path"]["no_actual_orders"]
            assert diagnostic["sell_only_next_close_policy_repair_path"][
                "signal_trade_log"]==report["next_close_execution_stress"][era][bps][
                    "next_close_costed_path"]["signal_trade_log"]
    assert not report["trading_authorized"]


def test_policy_repair_sells_only_overweight_name_not_healthy_assets():
    # Previous proportional liquidation unnecessarily sold all three assets.
    # The binding 50% cap requires a sale of only the overweight position.
    for bps in t.COSTS:
        fee=bps/10000.
        nav,pos,cash,charged,sold=t._sell_only_policy_repair(
            100.,np.array([60.,20.,10.,0.]),fee)
        assert pos[1]==pytest.approx(20.)
        assert pos[2]==pytest.approx(10.)
        assert pos[3]==pytest.approx(0.)
        assert pos[0]==pytest.approx(.50*nav,abs=1e-9)
        assert sold==pytest.approx((60.-50.)/(1.-.50*fee),abs=1e-9)
        assert charged==pytest.approx(fee*sold,abs=1e-9)
        assert cash==pytest.approx(nav-sum(pos),abs=1e-9)
        assert sold<15.  # Old proportional model sold ~15, unnecessarily.


def test_policy_repair_exact_minimum_gross_cap_and_deterministic_allocation():
    for bps in t.COSTS:
        fee=bps/10000.
        positions=np.array([40.,35.,20.,0.])
        nav,pos,cash,charged,sold=t._sell_only_policy_repair(
            100.,positions,fee)
        # Gross is exactly 95% pre-fee; fee-free rebalance is unnecessary.
        assert sold==pytest.approx(0.,abs=1e-9)
        assert np.array_equal(pos,positions)
        # Above 95% gross, no single name above 50%: minimum aggregate sale
        # goes to largest name only; healthy other positions are preserved.
        positions=np.array([40.,35.,22.,0.])
        nav,pos,cash,charged,sold=t._sell_only_policy_repair(
            100.,positions,fee)
        expected=(sum(positions)-95.)/(1.-.95*fee)
        assert sold==pytest.approx(expected,abs=1e-9)
        assert pos[0]==pytest.approx(40.-expected,abs=1e-9)
        assert pos[1]==pytest.approx(35.)
        assert pos[2]==pytest.approx(22.)
        assert sum(pos)/nav==pytest.approx(.95,abs=1e-9)
        assert cash/nav==pytest.approx(.05,abs=1e-9)
        assert charged==pytest.approx(sold*fee,abs=1e-9)


def test_policy_repair_both_concentration_and_gross_bind_without_overselling():
    for bps in t.COSTS:
        fee=bps/10000.
        positions=np.array([52.,44.,3.,0.])
        nav,pos,cash,charged,sold=t._sell_only_policy_repair(
            100.,positions,fee)
        assert pos[0]/nav<=.50+1e-9
        assert sum(pos)/nav<=.95+1e-9
        assert cash/nav>=.05-1e-9
        assert (pos<=positions+1e-10).all()
        assert sold==pytest.approx(sum(positions-pos),abs=1e-9)
        assert nav==pytest.approx(100.-fee*sold,abs=1e-9)
        # This lower bound is unavoidable for any sell-only feasible repair.
        gross_floor=(sum(positions)-95.)/(1.-.95*fee)
        assert sold>=gross_floor-1e-9
        assert sold<6.  # Do not liquidate every position pro rata.

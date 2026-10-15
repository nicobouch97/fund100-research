"""C4 deterministic no broker, synthetic lag/no-lookahead and costs."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_c4_equity_stress_v1_0 as c4
import fund100_commodity_etp_research_v1_0 as base


def prices(n=950, *, stress=False, gold_corr=False):
    idx = pd.bdate_range("2012-01-03", periods=n)
    t = np.arange(n, dtype=float)
    wave = np.sin(t*1.8)
    spy_ret = .0003 + (.027 if stress else .003)*wave
    dbc_ret = .0002 + (.020 if stress else .003)*wave + .0002*np.cos(t*2.2)
    gld_ret = .00015 + (.012*wave if gold_corr else -.003*wave) + .001*np.cos(t*1.1)
    shy_ret = np.full(n, .00006)
    return pd.DataFrame({
        "GLD": 100*np.cumprod(1+gld_ret),
        "DBC": 100*np.cumprod(1+dbc_ret),
        "SHY": 100*np.cumprod(1+shy_ret),
        "SPY": 100*np.cumprod(1+spy_ret),
    }, index=idx)


def test_default_static_target_in_calm_equity_market():
    p = prices()
    d = c4.decision(p, 900)
    assert d.weights == {"GLD": .2, "DBC": .15, "SHY": .65}
    assert not d.dbc_stress_reduced
    assert not d.gold_stress_reduced
    assert d.spy_annualized_vol < .25


def test_db_futures_fund_weight_cut_only_on_correlated_equity_stress():
    p = prices(stress=True)
    d = c4.decision(p, 900)
    assert d.dbc_stress_reduced
    assert not d.gold_stress_reduced
    assert d.weights == {"GLD": .2, "DBC": .05, "SHY": .75}
    assert d.spy_annualized_vol >= .25
    assert d.dbc_spy_corr >= .4
    assert d.gold_spy_corr < .3


def test_both_commodity_etfs_can_be_dampened_if_gold_loses_hedge_effect():
    d = c4.decision(prices(stress=True, gold_corr=True), 900)
    assert d.dbc_stress_reduced and d.gold_stress_reduced
    assert d.weights == {"GLD": .1, "DBC": .05, "SHY": .85}


def test_previous_63_returns_exclude_same_day_bar():
    p = prices(stress=True, gold_corr=True)
    old = c4.decision(p, 900)
    moved = p.copy()
    for sym in base.PRICES:
        moved.iloc[900, moved.columns.get_loc(sym)] *= 1.20
    new = c4.decision(moved, 900)
    assert new == old


def test_future_prices_do_not_rewrite_prior_signal():
    p = prices(stress=True)
    old = c4.decision(p, 900)
    moved = p.copy()
    moved.iloc[905:, moved.columns.get_loc("DBC")] *= 1.10
    assert c4.decision(moved, 900) == old


def test_no_leverage_single_instrument_caps_and_minimum_shy_monthly():
    for kind in ({}, {"stress":True}, {"stress":True,"gold_corr":True}):
        p = prices(**kind)
        d = c4.decision(p, 900)
        assert sum(d.weights.values()) == pytest.approx(1)
        assert 0 <= d.weights["GLD"] <= .2
        assert 0 <= d.weights["DBC"] <= .15
        assert .65 <= d.weights["SHY"] <= 1


def test_c4_backtest_has_same_cash_flow_convention_and_higher_cost_hurts():
    p = prices(stress=True)
    cheap, n1 = c4.backtest(p, cost_bps=5)
    costly, n2 = c4.backtest(p, cost_bps=35)
    assert len(cheap.nav) == len(p)
    assert cheap.nav.iloc[0] == 100
    assert costly.nav.iloc[-1] <= cheap.nav.iloc[-1]
    assert n1 == n2
    assert n1["rebalance_count"] > 20
    assert n1["dbc"] > 0
    assert cheap.turnover.ge(0).all()
    # Long-only positions drift naturally within the month. Targets, not
    # intramonth weights, have a frozen 65% minimum.
    month_open_after_start = [
        idx for idx in range(1, len(p))
        if p.index[idx].month != p.index[idx-1].month
    ]
    assert (cheap.close_weights["SHY"].iloc[month_open_after_start] >= .65 - 1e-9).all()
    assert (cheap.close_weights.min(axis=1) >= 0).all()
    assert (cheap.close_weights.sum(axis=1) - 1).abs().max() < 1e-9


def test_rebalance_targets_only_change_monthly():
    p = prices(stress=True, gold_corr=True)
    path, counts = c4.backtest(p, cost_bps=15)
    nonzero = path.turnover[path.turnover > 0]
    assert len(nonzero) > 0
    assert all(p.index.get_loc(day) > 0 and
               day.month != p.index[p.index.get_loc(day)-1].month
               for day in nonzero.index)
    assert (path.close_weights.sum(axis=1) - 1).abs().max() < 1e-8


def test_c4_rejects_invalid_signal_window_and_cost():
    p = prices()
    with pytest.raises(c4.CommodityC4Stop):
        c4.decision(p, -1)
    with pytest.raises(c4.CommodityC4Stop):
        c4.decision(p, 950)
    with pytest.raises(c4.CommodityC4Stop):
        c4.decision(p, 900.0)
    with pytest.raises(c4.CommodityC4Stop):
        c4.backtest(p, cost_bps=1)


def test_repeated_history_no_hindsight_performance_or_paper_promotion():
    result = c4.analyze(prices(stress=True))
    assert result["status"] == "EXPLORATORY_HISTORY_ALREADY_EXAMINED_NO_PROMOTION"
    assert result["all_later_historical_periods_already_explored_in_C1_C2"]
    assert result["retrospective_holdout_is_not_independent_validation"]
    assert result["no_real_futures_carry_signal_computed"]
    assert result["prospective_evidence_required"]
    assert result["broker_order_count"] == 0
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
    assert set(result["cost_results"]) == {"5", "15", "35"}
    assert len(result["source_sha256"]) == 64


def test_candidate_avoids_futures_index_methodology_proxies():
    p = prices()
    r = c4.analyze(p)
    assert r["max_gl_dbc_target"] == .35
    assert r["fund_dbc_roll_already_embedded_in_adjusted_etf_close"] is True
    assert r["vendor_adjustments_are_not_point_in_time_proven"] is True
    assert r["all_later_historical_periods_already_explored_in_C1_C2"] is True

"""Offline fixture tests for Phase 3 GLD vs DBC product-specific research."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_etp_research_v1_0 as c


def prices(n=1000):
    days = pd.bdate_range("2014-01-02", periods=n)
    t = np.arange(n, dtype=float)
    return pd.DataFrame({
        "GLD": 100*np.exp(.00024*t+.014*np.sin(t/21)),
        "DBC": 100*np.exp(.00013*t+.022*np.sin(t/31)),
        "SHY": 100*np.exp(.00009*t+.0003*np.sin(t/62)),
        "SPY": 100*np.exp(.00035*t+.016*np.sin(t/22)),
    }, index=days)


def test_exact_non_live_research_data_universe():
    assert set(c.PRICES) == {"GLD", "DBC", "SHY", "SPY"}
    assert set(c.TRADED) == {"GLD", "DBC", "SHY"}
    assert "SPY" not in c.TRADED
    assert c.GLD_CAP == .20 and c.DBC_CAP == .15


def test_validations_reject_wrong_symbols_gaps_and_bad_prices():
    d = prices()
    for change in (
        lambda x: x.drop(columns=["DBC"]),
        lambda x: x.assign(DOGE=100),
        lambda x: x.assign(DBC=np.nan),
        lambda x: x.assign(GLD=-1),
        lambda x: x.iloc[::-1],
        lambda x: x.iloc[:100],
        lambda x: x.assign(GLD=x["GLD"].where(x.index != x.index[222], x["GLD"]*1.5)),
    ):
        with pytest.raises(c.CommodityResearchStop):
            c.validate_prices(change(d))


def test_source_hash_reproducible_and_sensitive():
    d = prices()
    one = c.data_hash(d)
    assert one == c.data_hash(d.copy())
    d.iloc[-1, d.columns.get_loc("GLD")] *= 1.00005
    assert c.data_hash(d) != one


def test_trend_reference_uses_prior_close_not_today_or_future():
    d = prices()
    now = 333
    base = c.reference_weights(d, now)
    modified = d.copy()
    modified.loc[d.index[now]:, "DBC"] *= 1.35
    modified.loc[d.index[now]:, "GLD"] *= .8
    assert c.reference_weights(modified, now) == base
    assert c.reference_weights(d, 40) == {"GLD": 0., "DBC": 0., "SHY": 1.}


def test_monthly_rebalance_target_caps_and_no_leverage():
    d = prices()
    r = c.backtest(d, cost_bps=15)
    assert (r.close_weights >= 0).all().all()
    assert np.allclose(r.close_weights.sum(axis=1), 1.)
    first_of_month = [
        d.index[i] for i in range(1, len(d))
        if d.index[i-1].month != d.index[i].month
    ]
    targets = r.close_weights.loc[first_of_month]
    assert (targets["GLD"] <= .20+1e-10).all()
    assert (targets["DBC"] <= .15+1e-10).all()
    assert ((targets["GLD"] + targets["DBC"]) <= .35+1e-10).all()
    assert (targets["SHY"] >= .65-1e-10).all()
    assert (r.nav > 0).all()
    trades = r.turnover[r.turnover > 1e-12]
    for day in trades.index:
        i = d.index.get_loc(day)
        assert d.index[i-1].month != day.month


def test_turnover_costs_monotonically_reduce_net_wealth():
    d = prices()
    runs = [c.backtest(d, cost_bps=cost) for cost in c.COSTS_BPS]
    assert runs[0].nav.iloc[-1] >= runs[1].nav.iloc[-1] >= runs[2].nav.iloc[-1]
    assert runs[0].shy_nav.equals(runs[2].shy_nav)
    assert runs[0].spy_nav.equals(runs[2].spy_nav)
    assert runs[0].turnover.equals(runs[2].turnover)


def test_static_comparison_is_capped_and_cost_aware():
    d = prices()
    r = c.backtest(d, cost_bps=15, mode="static")
    first_of_month = [
        d.index[i] for i in range(1, len(d))
        if d.index[i-1].month != d.index[i].month
    ]
    w = r.close_weights.loc[first_of_month]
    assert (np.isclose(w["GLD"], c.GLD_CAP)).all()
    assert (np.isclose(w["DBC"], c.DBC_CAP)).all()
    assert (np.isclose(w["SHY"], 1. - c.MAX_COMMODITY_EXPOSURE)).all()


def test_future_price_change_preserves_prior_reported_weights():
    d = prices()
    a = c.backtest(d, cost_bps=15)
    altered = d.copy()
    altered.iloc[-1, altered.columns.get_loc("GLD")] *= 1.05
    b = c.backtest(altered, cost_bps=15)
    pd.testing.assert_frame_equal(
        a.close_weights.iloc[:-1], b.close_weights.iloc[:-1]
    )


def test_diagnostic_correlation_and_drawdown_are_bounded():
    d = prices()
    r = c.backtest(d, cost_bps=15)
    m = c.metrics(r, 400, len(d)-1)
    assert m["sessions"] > 0
    assert -1. <= m["equity_daily_correlation"] <= 1.
    assert m["spy_equity_down_2pct_day_count"] >= 0
    assert m["max_drawdown_pct"] >= 0
    assert m["total_one_way_turnover"] >= 0


def test_research_analyze_rejects_automatic_promotion_and_separates_periods():
    d = prices()
    r = c.analyze(d)
    assert r["scope"] == "RESEARCH_ONLY_NO_BROKER"
    assert r["broker_order_count"] == 0
    assert r["strategy_promoted_to_paper"] is False
    assert r["strategy_promoted_to_live"] is False
    assert r["universe_extended_for_live"] is False
    assert r["fixed_before_holdout_no_parameter_selection"] is True
    assert r["holdout_start"] > r["train_end"]
    assert set(r["results"]) == {"5", "15", "35"}
    assert r["data_sha256"] == c.data_hash(d)


def test_costs_are_brokerage_friction_not_double_counted_dbc_roll():
    report = c.analyze(prices())
    assert report["fund_expenses_and_DBC_roll_already_reflected_in_price_history"] is True
    assert report["no_added_futures_roll_penalty_to_avoid_double_counting"] is True


def test_invalid_evaluation_rejects_missing_periods():
    p = prices()
    r = c.backtest(p, cost_bps=15)
    with pytest.raises(c.CommodityResearchStop):
        c.metrics(r, 400, 400)
    with pytest.raises(c.CommodityResearchStop):
        c.backtest(p, cost_bps=0)
    with pytest.raises(c.CommodityResearchStop):
        c.reference_weights(p, 400, mode="leveraged")

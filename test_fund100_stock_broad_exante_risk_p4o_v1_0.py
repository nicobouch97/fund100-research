"""P4O deterministic original-vintage risk tests; no broker or network."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_exante_risk_p4o_v1_0 as p4o
import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_frozen_forward_marks_p4m_v1_0 as p4m


def original_fixture():
    idx = pd.bdate_range(end="2026-10-23", periods=160)
    t = np.arange(len(idx), dtype=float)
    leaders = dict(zip(p4m.ORIGINAL_SELECTION,
                       (0.0018, 0.0017, 0.0016, 0.0015, 0.0014, 0.0013)))
    prices = {}
    for n, symbol in enumerate(p4l.SECTORS):
        base = leaders.get(symbol, 0.00012)
        daily = base + 0.00010 * np.sin(t / (6 + n % 5) + n / 4)
        prices[symbol] = 100 * np.cumprod(1 + daily)
    prices["SPY"] = 100 * np.cumprod(1 + 0.0003 + 0.00016 * np.sin(t / 7))
    prices["SHY"] = 100 * np.cumprod(1 + 0.00005 + 0.00001 * np.cos(t / 9))
    frame = pd.DataFrame(prices, index=idx)
    report = p4l.evaluate(
        frame, acquired_at_utc="2026-10-24T04:00:00Z",
        provider_reference="Synthetic deterministic fixture, not a real market vintage",
    )
    assert report["momentum_only_watchlist"] == p4m.ORIGINAL_SELECTION
    return report, frame


def test_original_six_lookback_covariance_and_no_trade_contract():
    doc, prices = original_fixture()
    out = p4o.analyze(doc, prices)
    m = out["risk_metrics"]
    assert out["original_source_run_id"] == p4m.ORIGINAL_RUN_ID
    assert out["original_source_price_sha256"] == doc["canonical_price_csv_sha256"]
    assert out["selection"] == p4m.ORIGINAL_SELECTION
    assert m["observed_trailing_return_intervals"] == 126
    assert m["selection_count"] == 6
    assert m["selected_spy_beta"] is not None
    assert 0 < m["selected_effective_correlation_dimensions"] <= 6
    assert -1 <= m["selected_pairwise_mean_correlation"] <= 1
    assert m["spy_worst_5pct_session_count"] == 7
    assert m["contemporary_sector_equal_weight_shares"]["Energy"] == pytest.approx(2 / 6)
    assert m["contemporary_sector_equal_weight_shares"]["Financials"] == pytest.approx(2 / 6)
    assert m["risk_flags_descriptive_not_live_guards"][
        "contemporary_sector_weight_over_30pct"]
    assert m["equal_weight_daily_rebalanced_covariance_proxy_not_executable"]
    assert out["historical_selection_conditioning_bias"]
    assert out["no_costed_trading_return_or_alpha_claim"]
    assert not out["independent_alpha_validated"]
    assert not out["live_authorized"] and not out["paper_authorized"]
    assert out["broker_orders"] == out["broker_requests"] == 0


def test_report_cannot_be_swapped_or_revised_without_detecting_it():
    doc, prices = original_fixture()
    tampered = dict(doc)
    tampered["momentum_only_watchlist"] = list(reversed(doc["momentum_only_watchlist"]))
    with pytest.raises(p4o.P4OStop, match="disagree"):
        p4o.analyze(tampered, prices)
    revised = prices.copy()
    revised.loc[revised.index[-1], "MSFT"] *= 1.02
    with pytest.raises(p4o.P4OStop, match="disagree"):
        p4o.analyze(doc, revised)
    missing = prices.drop(columns="MA")
    with pytest.raises(p4o.P4OStop, match="not independently reproducible"):
        p4o.analyze(doc, missing)


def test_post_selection_sessions_cannot_enter_original_exante_window():
    doc, prices = original_fixture()
    next_day = prices.iloc[[-1]].copy()
    next_day.index = [pd.Timestamp("2026-10-26")]
    future = pd.concat([prices, next_day])
    later_doc = p4l.evaluate(
        future, acquired_at_utc="2026-10-27T04:00:00Z",
        provider_reference="Synthetic future vintage only, not original source",
    )
    with pytest.raises(p4o.P4OStop, match="Frozen 23-Oct"):
        p4o.analyze(later_doc, future)


def test_correlated_names_are_not_six_independent_dimensions():
    idx = pd.bdate_range("2026-01-01", periods=p4o.LOOKBACK_RETURNS)
    t = np.arange(len(idx))
    common = 0.001 + 0.0004 * np.sin(t / 5)
    data = {s: common.copy() for s in p4l.SECTORS}
    data["SPY"] = common.copy()
    data["SHY"] = np.full(len(idx), 0.0001)
    returns = pd.DataFrame(data, index=idx)
    m = p4o._metrics(returns, p4m.ORIGINAL_SELECTION)
    assert m["selected_effective_correlation_dimensions"] == pytest.approx(1)
    assert m["selected_pairwise_max_correlation"] == pytest.approx(1)
    assert m["selected_spy_beta"] == pytest.approx(1)
    assert m["selected_spy_daily_r_squared"] == pytest.approx(1)


def test_zero_variance_benchmark_is_not_reported_as_predictive_beta():
    idx = pd.bdate_range("2026-01-01", periods=p4o.LOOKBACK_RETURNS)
    t = np.arange(len(idx))
    data = {s: 0.001 + 0.0002 * np.sin(t / (3 + n % 5) + n)
            for n, s in enumerate(p4l.SECTORS)}
    data["SPY"] = np.zeros(len(idx))
    data["SHY"] = np.zeros(len(idx))
    m = p4o._metrics(pd.DataFrame(data, index=idx), p4m.ORIGINAL_SELECTION)
    assert m["selected_spy_beta"] is None
    assert m["selected_spy_daily_r_squared"] is None
    assert m["spy_worst_5pct_selected_loss_capture_ratio"] is None
    assert not m["risk_flags_descriptive_not_live_guards"][
        "selected_spy_beta_at_least_0_90"]


def test_missing_or_nonfinite_returns_fail_closed():
    idx = pd.bdate_range("2026-01-01", periods=p4o.LOOKBACK_RETURNS)
    r = pd.DataFrame(0.001, index=idx,
                     columns=list(p4l.SECTORS) + ["SPY", "SHY"])
    r.loc[idx[0], "CVX"] = np.nan
    with pytest.raises(p4o.P4OStop, match="Invalid original"):
        p4o._metrics(r, p4m.ORIGINAL_SELECTION)
    r.loc[idx[0], "CVX"] = -1.01
    with pytest.raises(p4o.P4OStop, match="Invalid trailing"):
        p4o._metrics(r, p4m.ORIGINAL_SELECTION)

"""Pure synthetic-fixture tests; never represent these as actual performance."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_bond_etf_research_v1_0 as b


def prices(n=840) -> pd.DataFrame:
    # Deterministic synthetic sessions, NOT real bond price history.
    dates = pd.bdate_range("2017-01-02", periods=n)
    x = np.arange(n, dtype=float)
    return pd.DataFrame({
        "TLT": 100 * np.exp(0.00019*x + 0.011*np.sin(x/24)),
        "IEF": 100 * np.exp(0.00013*x + 0.005*np.sin(x/35)),
        "SHY": 100 * np.exp(0.00008*x),
        "TIP": 100 * np.exp(0.00012*x + 0.004*np.sin(x/60)),
        "LQD": 100 * np.exp(0.00015*x + 0.006*np.sin(x/38)),
    }, index=dates)


def test_universe_is_entirely_distinct_from_live_policy():
    assert set(b.UNIVERSE) == {"TLT", "IEF", "SHY", "TIP", "LQD"}
    assert b.MAX_TLT_WEIGHT < b.MAX_NON_SHY_WEIGHT


def test_prices_cannot_be_missing_or_corrupted():
    clean = prices()
    for mod in (
        lambda d: d.drop(columns=["TIP"]),
        lambda d: d.assign(TLT=np.nan),
        lambda d: d.assign(LQD=0.0),
        lambda d: d.iloc[::-1],
        lambda d: d.iloc[:100],
        lambda d: d.assign(IEF=-1),
    ):
        with pytest.raises(b.BondResearchStop):
            b.validate_prices(mod(clean))


def test_source_hash_is_stable_and_changes_with_prices():
    clean = prices()
    a = b.source_hash(clean)
    assert a == b.source_hash(clean.copy())
    modified = clean.copy()
    modified.loc[modified.index[-1], "LQD"] *= 1.001
    assert b.source_hash(modified) != a


def test_signal_never_uses_current_or_future_session():
    clean = prices()
    day = 505
    weights = b.reference_weights(clean, day, 126, 0.25)
    changed = clean.copy()
    changed.iloc[day:, changed.columns.get_loc("LQD")] *= 1.25
    assert b.reference_weights(changed, day, 126, 0.25) == weights


def test_research_holds_defensive_shy_before_signal_warmup():
    weights = b.reference_weights(prices(), 30, 126, 0.25)
    assert weights["SHY"] == 1.0
    assert all(weights[s] == 0 for s in b.SATELLITES)


def test_portfolio_caps_and_long_only_at_each_month_end():
    clean = prices()
    result = b.backtest(clean, lookback=63, cap=0.25, cost_bps=15)
    weights = result.weights
    assert np.allclose(weights.sum(axis=1), 1.0)
    assert (weights >= 0).all().all()
    assert (weights["TLT"] <= 0.15 + 1e-10).all()
    assert (weights[list(b.SATELLITES)].sum(axis=1) <= 0.50 + 1e-10).all()
    assert (weights["SHY"] >= 0.50 - 1e-10).all()
    assert (result.nav > 0).all()


def test_cost_increase_reduces_strategy_nav_not_shy_control():
    clean = prices()
    low = b.backtest(clean, lookback=63, cap=0.25, cost_bps=5)
    high = b.backtest(clean, lookback=63, cap=0.25, cost_bps=35)
    assert high.nav.iloc[-1] <= low.nav.iloc[-1]
    assert high.control_nav.equals(low.control_nav)
    assert high.turnover.equals(low.turnover)


def test_first_session_of_month_only_rebalances():
    clean = prices()
    path = b.backtest(clean, lookback=63, cap=0.25, cost_bps=15)
    changes = path.turnover[path.turnover > 1e-10].index
    for day in changes:
        offset = clean.index.get_loc(day)
        assert clean.index[offset - 1].month != day.month


def test_one_day_future_price_change_cannot_change_previous_weights():
    clean = prices()
    first = b.backtest(clean, lookback=126, cap=0.25, cost_bps=15)
    changed = clean.copy()
    changed.iloc[-1, changed.columns.get_loc("IEF")] *= 1.2
    after = b.backtest(changed, lookback=126, cap=0.25, cost_bps=15)
    pd.testing.assert_frame_equal(first.weights.iloc[:-1], after.weights.iloc[:-1])


def test_holdout_winner_is_train_selected_only_and_unpromoted(monkeypatch):
    clean = prices()
    report = b.analyze(clean)
    assert report["schema"] == "FUND100_BOND_ETF_RESEARCH_V1"
    assert report["strategy_promoted_to_live"] is False
    assert report["strategy_promoted_to_paper"] is False
    assert report["live_orders_authorized"] is False
    assert set(report["evaluation"]) == {"5", "15", "35"}
    assert report["holdout_first_session"] > report["train_last_session"]
    split = int(len(clean) * 0.70)
    altered = clean.copy()
    for symbol in b.UNIVERSE:
        altered.iloc[split:, altered.columns.get_loc(symbol)] *= (
            1.0 + 0.002 * np.arange(len(clean) - split)
        )
    changed = b.analyze(altered)
    assert report["chosen_on_training_only"] == changed["chosen_on_training_only"]
    assert report["data_sha256"] != changed["data_sha256"]


def test_bad_candidate_and_insufficient_window_fail_closed():
    clean = prices()
    with pytest.raises(b.BondResearchStop):
        b.reference_weights(clean, 200, 10, 0.25)
    with pytest.raises(b.BondResearchStop):
        b.backtest(clean, lookback=63, cap=0.25, cost_bps=0)
    with pytest.raises(b.BondResearchStop):
        b.metrics(b.backtest(clean, lookback=63, cap=0.25, cost_bps=15), 25, 25)


def test_no_extra_assets_pass_data_validation():
    x = prices()
    x["BTCUSD"] = 100
    result = b.validate_prices(x)
    assert set(result.columns) == set(b.UNIVERSE)

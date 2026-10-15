"""Independent fixtures for the Phase 2 MACRO bond research contract.

All synthetic series are invented fixtures; no past or future performance
may be inferred from their values.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import fund100_bond_macro_regime_v1_0 as macro
import fund100_bond_macro_source_v1_0 as source


def fixture(n=800):
    dates = pd.bdate_range("2018-01-01", periods=n)
    x = np.arange(n, dtype=float)
    prices = pd.DataFrame({
        "TLT": 100*np.exp(.00012*x + .008*np.sin(x/35)),
        "IEF": 100*np.exp(.00010*x + .004*np.sin(x/50)),
        "SHY": 100*np.exp(.000065*x),
        "TIP": 100*np.exp(.00009*x + .003*np.sin(x/28)),
        "LQD": 100*np.exp(.00013*x + .005*np.sin(x/42)),
    }, index=dates)
    rows = pd.DataFrame({
        "observation_date": dates,
        "available_date": dates + pd.offsets.BDay(2),
        "DGS2": 2.5 + .004*np.sin(x/30),
        "DGS10": 3.5 + .35*np.sin(x/51),
        "T10YIE": 2.0 + .25*np.sin(x/75),
        "BAA10Y": 2.25 + .35*np.sin(x/40),
    })
    return prices, rows


def test_macro_input_requires_explicit_availability_and_no_missing_series():
    _, rows = fixture()
    assert len(macro.validate_macro(rows)) == len(rows)
    with pytest.raises(macro.MacroResearchStop):
        macro.validate_macro(rows.drop(columns=["BAA10Y"]))
    altered = rows.copy()
    altered.loc[0, "available_date"] = altered.loc[0, "observation_date"] - pd.Timedelta(days=1)
    with pytest.raises(macro.MacroResearchStop):
        macro.validate_macro(altered)
    altered = rows.copy()
    altered.loc[0, "BAA10Y"] = np.nan
    with pytest.raises(macro.MacroResearchStop):
        macro.validate_macro(altered)
    altered = pd.concat([rows, rows.iloc[-1:]], ignore_index=True)
    with pytest.raises(macro.MacroResearchStop):
        macro.validate_macro(altered)


def test_asof_join_is_one_complete_session_behind_release_date():
    prices, rows = fixture()
    aligned = macro.align_available_macro(prices.index, rows)
    # Row t reflects information known by CLOSE of t-1, never t itself.
    assert pd.isna(aligned.iloc[0]["observation_date"])
    for i in (5, 31, 300, 700):
        used = aligned.iloc[i]
        assert used["available_date"] <= prices.index[i-1]
        assert used["observation_date"] <= prices.index[i-1]


def test_future_macro_changes_do_not_change_previous_decisions():
    prices, rows = fixture()
    original = macro.align_available_macro(prices.index, rows)
    idx = 400
    saved = macro.decision(original, idx)
    altered = rows.copy()
    altered.loc[altered["observation_date"] >= prices.index[idx], "DGS10"] = 25
    after = macro.align_available_macro(prices.index, altered)
    assert macro.decision(after, idx) == saved
    assert original.iloc[idx]["DGS10"] == after.iloc[idx]["DGS10"]


def test_stale_macro_defaults_to_shy_not_fabricated_value():
    prices, rows = fixture()
    truncated = rows.iloc[:270].copy()
    aligned = macro.align_available_macro(prices.index, truncated)
    weights = macro.decision(aligned, 400)
    assert weights["SHY"] == 1.0
    assert sum(weights[s] for s in ("TLT", "IEF", "TIP", "LQD")) == 0


def test_fixed_macro_signal_regimes_and_limits():
    prices, rows = fixture()
    aligned = macro.align_available_macro(prices.index, rows)
    for i in range(60, len(prices), 23):
        w = macro.decision(aligned, i)
        assert abs(sum(w.values()) - 1.0) < 1e-9
        assert 0 <= w["TLT"] <= 0.15
        assert sum(w[s] for s in ("TLT", "IEF", "TIP", "LQD")) <= 0.35 + 1e-9
        assert w["SHY"] >= 0.65 - 1e-9


def test_broker_free_backtest_costs_and_monthly_rebalance():
    prices, rows = fixture()
    low = macro.run(prices, rows, 5)
    high = macro.run(prices, rows, 35)
    assert high.nav.iloc[-1] <= low.nav.iloc[-1]
    assert high.benchmark.equals(low.benchmark)
    assert high.turnover.equals(low.turnover)
    assert (high.nav > 0).all()
    assert np.allclose(high.weights.sum(axis=1), 1)
    for date in high.turnover[high.turnover > 0].index:
        i = prices.index.get_loc(date)
        assert prices.index[i-1].month != date.month


def test_exploratory_report_explicitly_non_promoted_and_hash_bound():
    prices, rows = fixture()
    report = macro.compare(prices, rows)
    assert report["portfolio_status"] == "RESEARCH_ONLY_NO_PROMOTION"
    assert report["live_authorized"] is False
    assert report["paper_authorized"] is False
    assert report["no_broker_orders"] is True
    assert report["historical_holdout_not_independent"] is True
    assert set(report["results"]) == {"5", "15", "35"}
    assert report["macro_source_sha256"] == macro._hash_macro(rows)
    assert report["bond_price_source_sha256"]
    altered = rows.copy()
    altered.loc[0, "BAA10Y"] += 0.1
    assert macro._hash_macro(altered) != report["macro_source_sha256"]


def test_no_mutation_or_authorization_via_run():
    prices, rows = fixture()
    before_price, before_rows = prices.copy(), rows.copy()
    macro.run(prices, rows, 15)
    pd.testing.assert_frame_equal(prices, before_price)
    pd.testing.assert_frame_equal(rows, before_rows)


def test_csv_source_rejects_unexpected_columns_and_symbols():
    with pytest.raises(macro.MacroResearchStop):
        source.parse_fred_series(b"DATE,INVALID\n2020-01-01,4.00\n", "DGS10")
    with pytest.raises(macro.MacroResearchStop):
        source.fetch("BTCUSD")


def test_csv_source_parses_missing_as_nan_then_requires_complete_days():
    raw = b"DATE,DGS2\n2020-01-02,1.70\n2020-01-03,.\n"
    data = source.parse_fred_series(raw, "DGS2")
    assert data.iloc[0] == 1.7
    assert np.isnan(data.iloc[1])


def test_two_day_assumed_availability_never_equal_observation():
    prices, _ = fixture()
    series = {}
    for name, value in (("DGS2", 2.0), ("DGS10", 3.0),
                        ("T10YIE", 2.0), ("BAA10Y", 2.5)):
        series[name] = pd.Series(value, index=prices.index)
    last = (prices.index[-1] + pd.Timedelta(days=14)).date().isoformat()
    result = source.consolidate(series, end_exclusive=last)
    assert (result["available_date"] > result["observation_date"]).all()
    assert result["available_date"].is_monotonic_increasing
    assert set(result.columns) == {"observation_date", "available_date", *macro.SERIES}

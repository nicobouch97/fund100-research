"""Deterministic causal and fail-closed tests for C13 gold/cash trend study."""
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_v6_c13_dynamic_gold_cash_v1_0 as mod
import fund100_v6_crossasset_stress_diagnostic_v1_0 as c13
from test_fund100_v6_crossasset_stress_diagnostic_v1_0 import (
    prices as source_prices, cash_rates as source_rates,
)


def source():
    prices = c13.validate_prices(source_prices())
    rates = source_rates().loc["2013-12-01":prices.index[-1]]
    prior = {
        "schema": c13.SCHEMA,
        "acquired_at_utc": "2025-01-02T12:00:00Z",
        "last_completed_session": prices.index[-1].date().isoformat(),
        "price_sha256": sha256(c13.canonical_prices(prices).encode()).hexdigest(),
        "cash_rate_sha256": sha256(c13.canonical_cash_rates(rates).encode()).hexdigest(),
    }
    return prices, rates, prior


def test_same_source_full_historical_report_no_orders():
    p, rates, prior = source()
    result = mod.evaluate(p, rates, prior)
    assert result["schema"].endswith("_V1")
    assert result["price_sha256"] == prior["price_sha256"]
    assert result["cash_rate_sha256"] == prior["cash_rate_sha256"]
    assert result["historical_data_previously_inspected_no_clean_holdout"]
    assert result["broker_requests"] == result["live_orders"] == result["paper_orders"] == 0
    assert result["private_state_writes"] == 0
    assert set(result["results"]) == {"5", "15", "35"}
    for scenarios in result["results"].values():
        assert set(scenarios) == set(mod.CASH_SCENARIOS)
        for row in scenarios.values():
            assert set(row["metrics"]) == {
                "DYNAMIC_GOLD_OR_CASH", "STATIC_10_GOLD", "CASH_CONTROL"}
            assert row["monthly_decisions"] == len(row["decision_log"])
            assert row["gold_cash_switches"] <= row["monthly_decisions"]
            assert row["dynamic_turnover_per_initial_nav"] >= .75
            assert result["year_concentration_is_post_result_not_an_independent_test"]
            concentration = row["post_result_calendar_year_relative_log_wealth"]
            assert set(concentration) == {
                "DYNAMIC_MINUS_CASH", "DYNAMIC_MINUS_STATIC_GOLD"}
            for item in concentration.values():
                assert item["ex_largest_year_is_arithmetic_not_executable_or_out_of_sample"]
                assert abs(sum(item["calendar_year_log_relative_wealth_pct"].values())
                           - item["terminal_relative_log_wealth_pct"]) < 0.00002
            assert set(row["chronological_periods_already_inspected_not_holdout"]) == {
                "2014_TO_2019", "2020_ONWARD"}


def test_signal_uses_only_previous_close_and_126_prior_sessions():
    p, _, _ = source()
    p["GLD"] = 100 * np.power(1.001, np.arange(len(p)))
    rate = pd.Series(0., index=p.index)
    out = mod.simulate_trend(p, rate, 15)
    assert out["decisions"][0]["gold_target_pct"] == 0
    assert out["gold_target_months"] > 0
    for row in out["decisions"]:
        assert pd.Timestamp(row["signal_latest_close"]) < pd.Timestamp(row["rebalance_close"])
        if row["gold_target_pct"] == 10:
            assert row["trailing_gld_minus_cash_pct"] > 0
    assert out["switches"] == 1


def test_interest_bearing_cash_can_reject_positive_nominal_gold_trend():
    p, _, _ = source()
    p["GLD"] = 100 * np.power(1.00005, np.arange(len(p)))
    zero = pd.Series(0., index=p.index)
    high = pd.Series(5., index=p.index)
    assert mod.simulate_trend(p, zero, 15)["gold_target_months"] > 0
    assert mod.simulate_trend(p, high, 15)["gold_target_months"] == 0


def test_future_price_change_cannot_change_earlier_nav_or_decisions():
    p, _, _ = source()
    rate = pd.Series(2., index=p.index)
    a = mod.simulate_trend(p, rate, 15)
    changed = p.copy()
    changed.iloc[-1, changed.columns.get_loc("GLD")] *= 1.10
    b = mod.simulate_trend(changed, rate, 15)
    pd.testing.assert_series_equal(a["nav"].iloc[:-1], b["nav"].iloc[:-1])
    assert a["decisions"] == b["decisions"]


def test_future_cash_rate_change_cannot_change_earlier_nav_or_decisions():
    p, _, _ = source()
    rate = pd.Series(2., index=p.index)
    a = mod.simulate_trend(p, rate, 15)
    changed = rate.copy()
    changed.iloc[-1] = 20.
    b = mod.simulate_trend(p, changed, 15)
    pd.testing.assert_series_equal(a["nav"], b["nav"])
    assert a["decisions"] == b["decisions"]


def test_etf_only_costs_monotonic_and_cash_control_inception_parity():
    p, _, _ = source()
    rate = pd.Series(0., index=p.index)
    lo = mod.simulate_trend(p, rate, 5)
    hi = mod.simulate_trend(p, rate, 35)
    assert hi["nav"].iloc[-1] < lo["nav"].iloc[-1]
    assert lo["decisions"] == hi["decisions"]
    assert lo["nav"].iloc[0] == pytest.approx(
        c13.simulate(p, c13.WEIGHTS[c13.CASH_CONTROL], 5)["nav"].iloc[0])
    assert lo["turnover"].iloc[0] == pytest.approx(.75)


@pytest.mark.parametrize("tamper", ["price", "rate", "schema", "timestamp", "date"])
def test_source_binding_fails_closed(tamper):
    p, rates, prior = source()
    if tamper == "price":
        p.iloc[-1, 0] *= 1.001
    elif tamper == "rate":
        rates.loc["2024-10-01", "IRX"] += .1
    elif tamper == "schema":
        prior["schema"] = "old"
    elif tamper == "timestamp":
        prior["acquired_at_utc"] = "2024-01-01T00:00:00Z"
    else:
        prior["last_completed_session"] = "2024-12-30"
    with pytest.raises(mod.TrendStudyStop):
        mod.verify_original_source(p, rates, prior)


@pytest.mark.parametrize("bad", [-1, 0, 10, 100, 15.0])
def test_invalid_cost_rejected(bad):
    p, _, _ = source()
    with pytest.raises(mod.TrendStudyStop):
        mod.simulate_trend(p, pd.Series(0., index=p.index), bad)


def test_bad_cash_rate_or_changed_equity_policy_rejected(monkeypatch):
    p, _, _ = source()
    rate = pd.Series(0., index=p.index)
    rate.iloc[10] = np.nan
    with pytest.raises(mod.TrendStudyStop):
        mod.simulate_trend(p, rate, 15)
    rate.iloc[10] = 0.
    monkeypatch.setitem(c13.WEIGHTS, c13.GOLD_ONLY,
                        (.40, .20, .15, .10, 0., .15))
    with pytest.raises(mod.TrendStudyStop, match="equity"):
        mod.simulate_trend(p, rate, 15)


def test_no_execution_paths_or_broker_credentials():
    src = Path(mod.__file__).read_text()
    for forbidden in ("import requests", "urlopen(", "api.alpaca.markets",
                      "/v2/orders", "FUND100_LIVE_KEY", "FUND100_PRIVATE_STATE"):
        assert forbidden not in src
    assert mod.NO_BROKER_OR_PRIVATE_STATE_ACCESS
    assert mod.NO_LIVE_OR_PAPER_AUTHORITY


def test_dynamic_year_attribution_reconciles_inception_cost_and_single_winning_year():
    dates = pd.DatetimeIndex(["2024-12-30", "2024-12-31",
                              "2025-01-02", "2025-12-31"])
    base = pd.Series([100., 100., 100., 100.], index=dates)
    active = pd.Series([99., 98., 100., 120.], index=dates)
    out = mod._relative_year_concentration(active, base)
    assert out["inception_cost_relative_log_wealth_pct"] == pytest.approx(
        100 * np.log(.99), abs=1e-5)
    assert out["terminal_relative_log_wealth_pct"] == pytest.approx(
        100 * np.log(1.2), abs=1e-5)
    assert out["largest_positive_year"] == 2025
    assert out["positive_years"] == out["negative_years"] == 1
    assert out["total_ex_largest_positive_year_log_relative_wealth_pct"] == pytest.approx(
        100 * np.log(.98), abs=1e-5)
    assert sum(out["calendar_year_log_relative_wealth_pct"].values()) == pytest.approx(
        out["terminal_relative_log_wealth_pct"], abs=2e-6)
    changed = active.copy()
    changed.iloc[-1] = 150.
    later = mod._relative_year_concentration(changed, base)
    assert (out["calendar_year_log_relative_wealth_pct"]["2024"]
            == later["calendar_year_log_relative_wealth_pct"]["2024"])


def test_dynamic_year_attribution_rejects_unmatched_or_invalid_nav():
    dates = pd.bdate_range("2024-01-02", periods=10)
    good = pd.Series(np.linspace(100., 110., 10), index=dates)
    with pytest.raises(mod.TrendStudyStop, match="sessions"):
        mod._relative_year_concentration(good, good.iloc[1:])
    bad = good.copy()
    bad.iloc[3] = float("nan")
    with pytest.raises(mod.TrendStudyStop, match="relative NAV"):
        mod._relative_year_concentration(bad, good)
    bad.iloc[3] = 0.
    with pytest.raises(mod.TrendStudyStop, match="relative NAV"):
        mod._relative_year_concentration(good, bad)


def test_year_concentration_with_no_winning_year_does_not_invent_one():
    dates = pd.DatetimeIndex(["2024-01-02", "2024-12-31", "2025-12-31"])
    baseline = pd.Series([100., 100., 100.], index=dates)
    candidate = pd.Series([99., 95., 90.], index=dates)
    result = mod._relative_year_concentration(candidate, baseline)
    assert result["largest_positive_year"] is None
    assert result["largest_positive_year_log_relative_wealth_pct"] is None
    assert result["positive_years"] == 0
    assert result["negative_years"] == 2
    assert result["total_ex_largest_positive_year_log_relative_wealth_pct"] == (
        result["terminal_relative_log_wealth_pct"])

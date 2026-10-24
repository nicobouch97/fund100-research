"""Offline causal switching tests; artificial NAV paths are NOT alpha evidence."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_four_model_walkforward_selector_v1_0 as w
import fund100_v6_existing_four_model_economics_v1_0 as economics
import fund100_v6_aggressive_rotation_research_v1_0 as original


def paths(n=3500):
    dates = pd.bdate_range("2013-01-02", periods=n)
    t = np.arange(n)
    benchmark = 100 * (1.00025 ** t)
    out = {}
    for i, model in enumerate(w.MODELS):
        daily = .0002 + (.0006 if i == 0 else -.0001 * i)
        nav = 100 * (1 + daily) ** t
        out[model] = pd.DataFrame({"nav": nav, "benchmark": benchmark}, index=dates)
    return out


def test_causal_quarterly_selection_and_no_same_close_hindsight():
    baseline = paths()
    a = w.evaluate(baseline, switch_side_cost_bps=15)
    assert a["training_ends_at_previous_session_close"]
    assert a["new_model_first_earns_next_session_return"]
    assert a["comparison_windows"]["since_2014"]["sessions"] >= 260
    dates = next(iter(baseline.values())).index
    t = next(i for i in range(300, len(dates))
             if dates[i].to_period("Q") != dates[i - 1].to_period("Q"))
    _, b, navs = w._verified_paths(baseline)
    before = w._lagged_choice(b, navs, t)
    modified = paths()
    # A giant move at decision day's close is not yet available to rank.
    modified[w.MODELS[1]].iloc[t, 0] *= 10
    _, b2, navs2 = w._verified_paths(modified)
    assert w._lagged_choice(b2, navs2, t) == before


def test_switch_costs_are_charged_for_entry_and_not_on_no_change():
    p = paths()
    a = w.evaluate(p, switch_side_cost_bps=5)
    b = w.evaluate(p, switch_side_cost_bps=35)
    assert a["comparison_windows"]["since_2014"]["switches"] >= 1
    assert a["terminal_hypothetical_selector_nav"] > b["terminal_hypothetical_selector_nav"]
    assert a["comparison_windows"]["since_2014"]["model_switch_one_way_notional_NAV"] == b["comparison_windows"]["since_2014"]["model_switch_one_way_notional_NAV"]


def test_cash_when_no_model_beats_benchmark():
    p = paths()
    for frame in p.values():
        frame["nav"] = 100 * (1.0001 ** np.arange(len(frame)))
    result = w.evaluate(p, switch_side_cost_bps=15)
    assert result["comparison_windows"]["since_2014"]["switches"] == 0
    assert result["comparison_windows"]["since_2014"]["historical_selector_cagr_pct"] == 0.0
    assert result["comparison_windows"]["since_2014"]["cash_held_sessions"] == result["comparison_windows"]["since_2014"]["sessions"]


def test_bad_history_or_cost_refused():
    p = paths()
    for invalid in (0, 12, True, 100):
        with pytest.raises(w.WalkforwardStop, match="cost"):
            w.evaluate(p, switch_side_cost_bps=invalid)
    q = paths()
    q[w.MODELS[1]].iloc[-1, 1] *= 2
    with pytest.raises(w.WalkforwardStop, match="benchmark"):
        w.evaluate(q, switch_side_cost_bps=15)
    q = paths()
    q[w.MODELS[0]].iloc[10, 0] = np.nan
    with pytest.raises(w.WalkforwardStop, match="NAV"):
        w.evaluate(q, switch_side_cost_bps=15)
    q = paths()
    q[w.MODELS[0]] = q[w.MODELS[0]].iloc[:-1]
    with pytest.raises(w.WalkforwardStop, match="sessions"):
        w.evaluate(q, switch_side_cost_bps=15)


def test_real_frozen_four_model_source_still_not_live_or_independent_holdout():
    prices, sha = original.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    original_models = economics._all_paths(prices, 15)
    report = w.evaluate(original_models, switch_side_cost_bps=15)
    assert report["historical_universe_and_models_already_inspected"]
    assert not report["independent_out_of_sample_alpha_proven"]
    assert report["strategy_promoted_for_funded_trading"] is None
    assert report["paper_or_live_orders"] == 0
    assert report["comparison_windows"].keys() == w.START_WINDOWS.keys()
    assert sha == original.FROZEN_FILE_SHA256
    assert all(v["sessions"] >= 260 for v in report["comparison_windows"].values())


def test_equal_model_comparator_starts_at_same_first_eligible_quarter_close():
    p = paths()
    dates, _, navs = w._verified_paths(p)
    t = next(i for i in range(w.TRAINING_RETURNS + 1, len(dates))
             if dates[i].to_period("Q") != dates[i - 1].to_period("Q"))
    blend = w._fixed_equal_model_blend(dates, navs, 15)
    assert np.all(blend[:t] == 100.0)  # no pre-eligibility advantage
    assert blend[t] == pytest.approx(100 * (1 - 15 / 10000))
    next_day = 100 * (1 - 15 / 10000) * sum(
        navs[m][t + 1] / navs[m][t] for m in w.MODELS
    ) / 4
    assert blend[t + 1] == pytest.approx(next_day)
    # No quarterly rebalancing or repeated entry cost.
    later = t + 150
    expected = 100 * (1 - 15 / 10000) * sum(
        navs[m][later] / navs[m][t] for m in w.MODELS
    ) / 4
    assert blend[later] == pytest.approx(expected)


def test_equal_blend_is_fixed_and_cannot_reweight_using_future_winners():
    original = paths()
    dates, _, navs = w._verified_paths(original)
    a = w._fixed_equal_model_blend(dates, navs, 5)
    future = paths()
    t = 800
    future[w.MODELS[2]].iloc[t:, 0] *= 1.05
    _, _, modified = w._verified_paths(future)
    b = w._fixed_equal_model_blend(dates, modified, 5)
    np.testing.assert_array_equal(a[:t], b[:t])
    assert b[t] > a[t]
    report = w.evaluate(original, switch_side_cost_bps=15)
    window = report["comparison_windows"]["since_2020"]
    assert "historical_selector_minus_equal_blend_cagr_pp" in window
    assert "historical_equal_blend_max_drawdown_pct" in window
    assert report["equal_model_blend_rebalances_after_entry"] is False
    assert report["equal_model_blend_one_synthetic_entry_side_charged"]


def test_fixed_blend_is_nontrivial_benchmark_when_selector_stays_cash():
    p = paths()
    for frame in p.values():
        frame["nav"] = 100 * (1.0001 ** np.arange(len(frame)))
    report = w.evaluate(p, switch_side_cost_bps=15)
    window = report["comparison_windows"]["since_2020"]
    assert window["historical_selector_cagr_pct"] == 0.0
    assert window["historical_equal_model_blend_cagr_pct"] > 0
    assert window["historical_selector_minus_equal_blend_cagr_pp"] < 0


def test_vol_target_matches_fixed_blend_when_synthetic_volatility_is_low():
    p = paths()
    dates, _, navs = w._verified_paths(p)
    fixed = w._fixed_equal_model_blend(dates, navs, 15)
    risk, exposure, turnover = w._vol_target_fixed_blend(dates, navs, 15)
    np.testing.assert_allclose(risk, fixed, rtol=1e-10, atol=1e-8)
    first = next(i for i in range(w.TRAINING_RETURNS + 1, len(dates))
                 if dates[i].to_period("Q") != dates[i-1].to_period("Q"))
    assert (exposure[:first] == 0).all()
    assert (exposure[first:] == 1).all()
    assert turnover[first] == 1
    assert turnover.sum() == pytest.approx(1)


def test_vol_target_reacts_only_after_shock_close_and_never_leverages():
    baseline = paths()
    dates, _, navs = w._verified_paths(baseline)
    original, exposure, _ = w._vol_target_fixed_blend(dates, navs, 15)
    shocked = paths()
    t = 600
    shocked[w.MODELS[1]].iloc[t:, 0] *= 3
    _, _, new_navs = w._verified_paths(shocked)
    changed, new_exposure, turnover = w._vol_target_fixed_blend(dates, new_navs, 15)
    np.testing.assert_array_equal(original[:t], changed[:t])
    np.testing.assert_array_equal(exposure[:t], new_exposure[:t])
    assert changed[t] != original[t]  # old exposure earned the shock
    assert new_exposure[t] < exposure[t]  # scale down only at this close
    assert np.all((new_exposure >= 0) & (new_exposure <= 1))
    assert turnover[t] > 0
    assert np.isfinite(changed).all()


def test_vol_target_costs_reduce_wealth_and_report_downside():
    p = paths()
    dates, _, navs = w._verified_paths(p)
    a, ea, ta = w._vol_target_fixed_blend(dates, navs, 5)
    b, eb, tb = w._vol_target_fixed_blend(dates, navs, 35)
    np.testing.assert_array_equal(ea, eb)
    np.testing.assert_array_equal(ta, tb)
    assert a[-1] > b[-1]
    report = w.evaluate(p, switch_side_cost_bps=15)
    assert report["vol_target_blend_is_exploratory_cash_only_synthetic"]
    assert report["vol_target_blend_annual_volatility_target_pct"] == 10
    assert report["vol_target_blend_lookback_completed_sessions"] == 63
    assert report["vol_target_blend_decision_after_close_applies_next_session"]
    assert report["vol_target_blend_no_leverage_or_shorting"]
    assert report["strategy_promoted_for_funded_trading"] is None
    assert report["paper_or_live_orders"] == 0
    for window in report["comparison_windows"].values():
        assert "historical_vol_target_blend_cagr_pct" in window
        assert -100 < window["historical_vol_target_blend_max_drawdown_pct"] <= 0
        assert 0 <= window["historical_vol_target_blend_average_exposure_pct"] <= 100


def test_vol_target_rejects_bad_original_model_returns():
    p = paths()
    dates, _, navs = w._verified_paths(p)
    navs[w.MODELS[0]][700] = float("nan")
    with pytest.raises(w.WalkforwardStop, match="blend NAV"):
        w._vol_target_fixed_blend(dates, navs, 15)


def test_original_model_dependence_identifies_duplicate_return_sleeves():
    p = paths()
    dates = next(iter(p.values())).index
    t = np.arange(len(dates))
    returns = .0002 + .004 * np.sin(t / 13)
    nav = 100 * np.cumprod(1 + returns)
    for model in w.MODELS:
        p[model]["nav"] = nav
    _, _, navs = w._verified_paths(p)
    result = w._model_return_dependence(dates, navs, "2014-01-01")
    assert result["status"] == "DESCRIPTIVE_ORIGINAL_MODEL_RETURN_DEPENDENCE"
    assert result["effective_correlated_return_dimensions"] == pytest.approx(1)
    assert result["maximum_pairwise_return_correlation"] == pytest.approx(1)
    assert result["after_common_first_eligible_quarter_close"]


def test_original_model_dependence_detects_distinct_returns_and_future_isolation():
    p = paths()
    dates = next(iter(p.values())).index
    t = np.arange(len(dates))
    for i, model in enumerate(w.MODELS):
        # Four deterministic, nonidentical return patterns; synthetic only.
        returns = .0002 + .005 * np.sin(t / (11 + i * 7) + i)
        p[model]["nav"] = 100 * np.cumprod(1 + returns)
    _, _, navs = w._verified_paths(p)
    result = w._model_return_dependence(dates, navs, "2014-01-01")
    assert 1.5 < result["effective_correlated_return_dimensions"] <= 4
    assert result["maximum_pairwise_return_correlation"] < .5
    cutoff = 1200
    before = w._model_return_dependence(
        dates[:cutoff], {m: n[:cutoff] for m, n in navs.items()}, "2014-01-01")
    changed = {m: n.copy() for m, n in navs.items()}
    changed[w.MODELS[0]][cutoff:] *= 1.5
    unchanged_prefix = w._model_return_dependence(
        dates[:cutoff], {m: n[:cutoff] for m, n in changed.items()}, "2014-01-01")
    assert before == unchanged_prefix


def test_original_model_dependence_never_invents_correlation_for_constant_sleeve():
    p = paths()
    dates, _, navs = w._verified_paths(p)
    result = w._model_return_dependence(dates, navs, "2014-01-01")
    assert result["status"] == "UNIDENTIFIABLE_NEAR_CONSTANT_MODEL"
    assert result["effective_correlated_return_dimensions"] is None
    assert result["maximum_pairwise_return_correlation"] is None


def test_original_model_dependence_real_frozen_paths_are_descriptive_only():
    prices, sha = original.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    assert sha == original.FROZEN_FILE_SHA256
    models = economics._all_paths(prices, 15)
    report = w.evaluate(models, switch_side_cost_bps=15)
    dependence = report["model_return_dependence_by_window"]
    assert set(dependence) == set(w.START_WINDOWS)
    for window in dependence.values():
        assert window["descriptive_not_holdings_lookthrough_or_independent_alpha"]
        assert window["return_observations"] >= 259
        if window["effective_correlated_return_dimensions"] is not None:
            assert 1 <= window["effective_correlated_return_dimensions"] <= 4
    assert report["paper_or_live_orders"] == 0


def _beta_fixture(benchmark_daily, blend_daily):
    dates = pd.bdate_range("2013-01-02", periods=len(benchmark_daily))
    return pd.DataFrame({
        "acwi_nav": 100 * np.cumprod(1 + benchmark_daily),
        "equal_model_blend_nav": 100 * np.cumprod(1 + blend_daily),
    }, index=dates)


def test_fixed_blend_acwi_beta_one_for_identical_return_streams():
    t = np.arange(3500)
    returns = .00025 + .008 * np.sin(t / 13)
    frame = _beta_fixture(returns, returns)
    d = w._fixed_blend_acwi_beta_diagnostics(frame, "2014-01-01")
    assert d["status"] == "DESCRIPTIVE_FIXED_BLEND_ACWI_EQUITY_BETA"
    assert d["acwi_daily_beta"] == pytest.approx(1)
    assert d["acwi_explained_daily_variance_pct"] == pytest.approx(100)
    assert d["zero_cash_rate_ols_intercept_annual_pp"] == pytest.approx(0)
    assert d["worst_5pct_acwi_day_blend_capture_pct"] == pytest.approx(100)
    assert d["annualized_active_tracking_error_pct"] == pytest.approx(0)
    assert d["identical_post_eligibility_sessions"]


def test_fixed_blend_acwi_beta_distinct_sleeve_and_prefix_isolation():
    t = np.arange(3500)
    benchmark = .0002 + .007 * np.sin(t / 11)
    sleeve = .0002 + .006 * np.sin(t / 37 + 1)
    frame = _beta_fixture(benchmark, sleeve)
    d = w._fixed_blend_acwi_beta_diagnostics(frame, "2014-01-01")
    assert abs(d["acwi_daily_beta"]) < .15
    assert d["acwi_explained_daily_variance_pct"] < 3
    cutoff = 1400
    before = w._fixed_blend_acwi_beta_diagnostics(
        frame.iloc[:cutoff], "2014-01-01")
    modified = frame.copy()
    modified.iloc[cutoff:, modified.columns.get_loc("equal_model_blend_nav")] *= 2
    after = w._fixed_blend_acwi_beta_diagnostics(
        modified.iloc[:cutoff], "2014-01-01")
    assert before == after


def test_fixed_blend_acwi_beta_fails_closed_on_flat_or_corrupt_benchmark():
    t = np.arange(3500)
    benchmark = .0002 + .007 * np.sin(t / 11)
    frame = _beta_fixture(benchmark, benchmark)
    frame["acwi_nav"] = 100.
    result = w._fixed_blend_acwi_beta_diagnostics(frame, "2014-01-01")
    assert result["status"] == "UNIDENTIFIABLE_NEAR_CONSTANT_ACWI"
    assert result["acwi_daily_beta"] is None
    frame.loc[frame.index[-1], "acwi_nav"] = np.nan
    with pytest.raises(w.WalkforwardStop, match="attribution NAV"):
        w._fixed_blend_acwi_beta_diagnostics(frame, "2014-01-01")


def test_fixed_blend_acwi_beta_real_original_source_not_promotion():
    prices, sha = original.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    assert sha == original.FROZEN_FILE_SHA256
    models = economics._all_paths(prices, 15)
    report = w.evaluate(models, switch_side_cost_bps=15)
    beta = report["fixed_blend_acwi_beta_by_window"]
    assert set(beta) == set(w.START_WINDOWS)
    for window in beta.values():
        assert window["descriptive_in_sample_not_independent_alpha"]
        assert window["identical_post_eligibility_sessions"]
        assert window["return_observations"] >= 259
        assert window["status"] == "DESCRIPTIVE_FIXED_BLEND_ACWI_EQUITY_BETA"
        assert 0 <= window["acwi_explained_daily_variance_pct"] <= 100
    assert report["strategy_promoted_for_funded_trading"] is None
    assert report["paper_or_live_orders"] == 0

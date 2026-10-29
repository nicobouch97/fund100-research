"""P4P pure offline tests; synthetic prices never imply investment returns."""
from __future__ import annotations

from hashlib import sha256

import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_rotation_feasibility_p4p_v1_0 as p4p


def prices(*, flat=False):
    dates = xcals.get_calendar("XNYS").sessions_in_range(
        "2025-10-01", "2026-10-23").tz_localize(None).normalize()
    t = np.arange(len(dates), dtype=float)
    series = {}
    for j, ticker in enumerate(p4l.SECTORS):
        drift = 0.0 if flat else 0.00005 + (j % 9) * 0.00017
        series[ticker] = 100.0 * np.exp(drift * t)
    series["SPY"] = 100.0 * np.exp((0 if flat else 0.00035) * t)
    series["SHY"] = 100.0 * np.exp((0 if flat else 0.00008) * t)
    return pd.DataFrame(series, index=dates)


def analyze(frame):
    sha = sha256(p4l.canonical_csv(frame).encode()).hexdigest()
    return p4p.analyze(frame, source_sha256=sha)


def test_month_end_signals_execute_next_close_without_lookahead():
    r = analyze(prices())
    assert r["schema"] == p4p.SCHEMA
    assert r["historical_roster_selected_only_on_2026_10_24"]
    assert r["survivorship_and_sector_history_not_point_in_time"]
    assert not r["trading_authorized"] and not r["live_authorized"]
    assert r["broker_requests"] == r["paper_orders"] == r["live_orders"] == 0
    first = r["scenarios"]["15"]
    assert first["observed_return_intervals"] > 20
    assert first["month_end_signal_count"] >= 3
    assert first["entry_execution_close"] > r["initial_month_end_signal"]
    for decision in first["signals_and_next_close_execution"]:
        assert decision["signal_session"] < decision["execution_close_session"]
        assert len(decision["selected"]) <= p4l.MAX_NAMES
        sectors = [p4l.SECTORS[s] for s in decision["selected"]]
        assert all(sectors.count(s) <= p4l.MAX_PER_SECTOR for s in sectors)


def test_higher_costs_reduce_strategy_and_passive_net_returns():
    r = analyze(prices())["scenarios"]
    for key in ("strategy_net_return_pct", "spy_passive_net_return_pct",
                "equal24_passive_net_return_pct"):
        assert r["5"][key] >= r["15"][key] >= r["35"][key]
    assert r["5"]["total_one_way_turnover_including_entry_exit"] == r["35"][
        "total_one_way_turnover_including_entry_exit"]
    assert r["15"]["total_one_way_turnover_including_entry_exit"] >= 2


def test_no_momentum_means_cash_not_forced_stock_positions():
    r = analyze(prices(flat=True))["scenarios"]["15"]
    assert r["strategy_net_return_pct"] == 0
    assert r["total_one_way_turnover_including_entry_exit"] == 0
    assert r["average_cash_weight_pct"] == 100
    assert all(not d["selected"] for d in r["signals_and_next_close_execution"])
    assert r["spy_passive_net_return_pct"] < 0


def test_future_price_changes_do_not_rewrite_past_month_end_decisions():
    original = prices()
    r1 = analyze(original)["scenarios"]["15"]
    modified = original.copy()
    modified.loc[modified.index[-1], "NVDA"] *= 1.02
    r2 = analyze(modified)["scenarios"]["15"]
    assert r1["signals_and_next_close_execution"] == r2[
        "signals_and_next_close_execution"]
    assert r1["strategy_net_return_pct"] != r2["strategy_net_return_pct"] or (
        "NVDA" not in r1["signals_and_next_close_execution"][-1]["selected"])


def test_wrong_source_sha_and_missing_nyse_session_fail_closed():
    p = prices()
    with pytest.raises(p4p.FeasibilityStop, match="fingerprint"):
        p4p.analyze(p, source_sha256="0" * 64)
    missing = p.drop(index=p.index[70])
    with pytest.raises(p4p.FeasibilityStop, match="NYSE"):
        analyze(missing)
    with pytest.raises(p4p.FeasibilityStop, match="Insufficient"):
        analyze(p.iloc[:130])


def test_gross_selection_return_is_identical_across_costs_and_friction_reconciles():
    result = analyze(prices())
    assert result["pre_cost_selection_vs_friction_attribution_same_decisions"]
    assert result["pre_cost_is_not_a_tradeable_zero_friction_strategy"]
    scenarios = result["scenarios"]
    for key in ("strategy_pre_cost_return_pct",
                "spy_passive_pre_cost_return_pct",
                "equal24_passive_pre_cost_return_pct",
                "strategy_pre_cost_minus_spy_pp",
                "strategy_pre_cost_minus_equal24_pp"):
        assert scenarios["5"][key] == scenarios["15"][key] == scenarios["35"][key]
    for bps in ("5", "15", "35"):
        row = scenarios[bps]
        assert row["pre_cost_result_not_evidence_of_point_in_time_alpha"]
        assert row["strategy_modelled_cost_drag_pp"] >= 0
        assert row["spy_passive_modelled_cost_drag_pp"] >= 0
        assert row["strategy_pre_cost_return_pct"] - row[
            "strategy_net_return_pct"] == pytest.approx(
                row["strategy_modelled_cost_drag_pp"], abs=2e-6)
        assert row["spy_passive_pre_cost_return_pct"] - row[
            "spy_passive_net_return_pct"] == pytest.approx(
                row["spy_passive_modelled_cost_drag_pp"], abs=2e-6)
        assert row["strategy_pre_cost_minus_spy_pp"] - row[
            "strategy_minus_spy_net_pp"] == pytest.approx(
                row["strategy_vs_spy_incremental_cost_drag_pp"], abs=2e-6)
    assert scenarios["5"]["strategy_modelled_cost_drag_pp"] < scenarios["15"][
        "strategy_modelled_cost_drag_pp"] < scenarios["35"]["strategy_modelled_cost_drag_pp"]
    assert scenarios["5"]["signals_and_next_close_execution"] == scenarios["35"][
        "signals_and_next_close_execution"]


def test_all_cash_strategy_has_zero_cost_drag_even_if_passive_benchmark_trades():
    row = analyze(prices(flat=True))["scenarios"]["15"]
    assert row["strategy_pre_cost_return_pct"] == row["strategy_net_return_pct"] == 0
    assert row["strategy_modelled_cost_drag_pp"] == 0
    assert row["spy_passive_pre_cost_return_pct"] == 0
    assert row["spy_passive_modelled_cost_drag_pp"] > 0
    assert row["strategy_vs_spy_incremental_cost_drag_pp"] < 0


def test_chain_linked_gross_attribution_reconciles_by_stock_sector_and_cost():
    result = analyze(prices())
    assert result["gross_stock_sector_attribution_uses_same_decisions_and_prices"]
    scenarios = result["scenarios"]
    for bps, row in scenarios.items():
        assert row["gross_attribution_method"] == (
            "CHAIN_LINKED_DAILY_RETURN_TO_TERMINAL_WEALTH")
        assert row["gross_attribution_is_path_dependent_not_causal_alpha"]
        assert set(row["gross_symbol_contribution_pct"]) == set(p4l.SECTORS)
        assert set(row["gross_active_vs_equal24_symbol_pp"]) == set(p4l.SECTORS)
        assert row["gross_attribution_reconciliation_error_pp"] == pytest.approx(
            0, abs=1e-7)
        assert row["gross_active_attribution_reconciliation_error_pp"] == pytest.approx(
            0, abs=1e-7)
        assert sum(row["gross_symbol_contribution_pct"].values()) == pytest.approx(
            row["strategy_pre_cost_return_pct"], abs=2e-5)
        assert sum(row["gross_sector_contribution_pct"].values()) == pytest.approx(
            row["strategy_pre_cost_return_pct"], abs=2e-5)
        assert sum(row["gross_active_vs_equal24_symbol_pp"].values()) == pytest.approx(
            row["strategy_pre_cost_minus_equal24_pp"], abs=2e-5)
        assert sum(row["gross_active_vs_equal24_sector_pp"].values()) == pytest.approx(
            row["strategy_pre_cost_minus_equal24_pp"], abs=2e-5)
        for sector in set(p4l.SECTORS.values()):
            tickers = [s for s, group in p4l.SECTORS.items() if group == sector]
            assert row["gross_sector_contribution_pct"][sector] == pytest.approx(
                sum(row["gross_symbol_contribution_pct"][s] for s in tickers),
                abs=2e-5)
            assert row["gross_active_vs_equal24_sector_pp"][sector] == pytest.approx(
                sum(row["gross_active_vs_equal24_symbol_pp"][s] for s in tickers),
                abs=2e-5)
    for field in ("gross_symbol_contribution_pct", "gross_sector_contribution_pct",
                  "gross_active_vs_equal24_symbol_pp",
                  "gross_active_vs_equal24_sector_pp"):
        assert scenarios["5"][field] == scenarios["15"][field] == scenarios["35"][field]


def test_all_cash_attribution_has_no_invented_stock_return_or_active_edge():
    row = analyze(prices(flat=True))["scenarios"]["15"]
    for field in ("gross_symbol_contribution_pct", "gross_sector_contribution_pct",
                  "gross_active_vs_equal24_symbol_pp",
                  "gross_active_vs_equal24_sector_pp"):
        assert all(value == 0 for value in row[field].values())
    assert row["gross_attribution_reconciliation_error_pp"] == 0
    assert row["gross_active_attribution_reconciliation_error_pp"] == 0


def test_costed_risk_paths_include_entry_and_final_exit_without_extra_day():
    r = analyze(prices(flat=True))["scenarios"]["15"]
    assert r["risk_paths_include_entry_and_exit_costs_on_actual_sessions"]
    assert r["risk_path_observed_sessions"] == r["observed_return_intervals"] + 1
    assert r["max_drawdown_hypothetical_pct"] == 0
    assert r["strategy_worst_session_return_pct"] == 0
    # A flat 100%-equity benchmark still loses both modeled trading fees.
    # Prior drawdown logic silently dropped the first-close entry fee.
    cost = .0015
    expected_drawdown = 100 * ((1 - cost) ** 2 - 1)
    for arm in ("spy_passive", "equal24_passive"):
        assert r[arm + "_max_drawdown_hypothetical_pct"] == pytest.approx(
            expected_drawdown, abs=.0001)
        assert r[arm + "_worst_session_return_pct"] == pytest.approx(-.15, abs=1e-6)
        assert r[arm + "_annualized_volatility_fraction"] > 0


def test_relative_risk_uses_same_window_but_not_falsely_cash_matched():
    frame = prices()
    frame.loc[frame.index[-1], "SPY"] *= .90
    result = analyze(frame)
    for bps, r in result["scenarios"].items():
        assert r["passive_benchmarks_100pct_equity_not_cash_matched"]
        assert r["risk_paths_include_entry_and_exit_costs_on_actual_sessions"]
        assert r["spy_passive_max_drawdown_hypothetical_pct"] < -9
        assert r["spy_passive_worst_session_return_pct"] < -9
        assert r["spy_passive_annualized_volatility_fraction"] > 0
        assert r["strategy_annualized_volatility_fraction"] >= 0
        assert r["equal24_passive_annualized_volatility_fraction"] >= 0
        assert r["risk_path_observed_sessions"] > 20
    # The final SPY mark does not rewrite the preceding stock decisions.
    original = analyze(prices())["scenarios"]["15"]
    assert original["signals_and_next_close_execution"] == result[
        "scenarios"]["15"]["signals_and_next_close_execution"]


def test_risk_path_rejects_missing_or_fictitious_session_and_nonfinite_wealth():
    with pytest.raises(p4p.FeasibilityStop, match="wealth path"):
        p4p._risk_path([1.0, .99], sessions=2)
    with pytest.raises(p4p.FeasibilityStop, match="wealth path"):
        p4p._risk_path([1.0, float("nan"), 1.0], sessions=2)


def test_decision_exposure_spy_control_is_costed_and_uses_same_signal_budget():
    # Three out of six names selected => 50% SPY, 50% zero-yield cash.
    # The +20% SPY move then grows gross wealth by 10%, not 20%.
    dates = pd.to_datetime(["2026-01-02", "2026-01-05",
                            "2026-01-06", "2026-01-07"])
    frame = pd.DataFrame({"SPY": [100.0, 100.0, 120.0, 120.0]}, index=dates)
    selected = list(p4l.SECTORS)[:3]
    decisions = [{"execution_close_session": "2026-01-05",
                  "selected": selected}]
    c = .0015
    net = p4p._spy_at_strategy_decision_exposure(frame, 1, decisions, c)
    gross = p4p._spy_at_strategy_decision_exposure(frame, 1, decisions, 0)
    # At final close the SPY weight has drifted to 0.6 / 1.1.
    expected = (1 - c * .5) * 1.1 * (1 - c * (.6 / 1.1))
    assert gross["terminal_wealth"] == pytest.approx(1.1)
    assert net["terminal_wealth"] == pytest.approx(expected)
    assert net["one_way_turnover"] == pytest.approx(.5 + .6 / 1.1)
    assert len(net["path"]) == 4
    assert net["path"][-1] == pytest.approx(expected)


def test_decision_exposure_spy_control_zero_equity_and_full_equity_boundaries():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05",
                            "2026-01-06", "2026-01-07"])
    frame = pd.DataFrame({"SPY": [100., 100., 120., 120.]}, index=dates)
    empty = [{"execution_close_session": "2026-01-05", "selected": []}]
    all_six = [{"execution_close_session": "2026-01-05",
                "selected": list(p4l.SECTORS)[:p4l.MAX_NAMES]}]
    zero = p4p._spy_at_strategy_decision_exposure(frame, 1, empty, .0015)
    full = p4p._spy_at_strategy_decision_exposure(frame, 1, all_six, .0015)
    assert zero["terminal_wealth"] == 1
    assert zero["one_way_turnover"] == 0
    assert full["terminal_wealth"] == pytest.approx(1.2 * (1 - .0015)**2)
    assert full["one_way_turnover"] == pytest.approx(2.0)
    with pytest.raises(p4p.FeasibilityStop, match="decision exposure"):
        p4p._spy_at_strategy_decision_exposure(
            frame, 1, all_six + all_six, .0015)


def test_decision_exposure_comparator_is_reported_separately_from_full_spy():
    scenarios = analyze(prices())["scenarios"]
    for bps, row in scenarios.items():
        assert row["spy_decision_exposure_control_not_daily_cash_matched"]
        assert row["spy_decision_exposure_control_uses_same_strategy_signals"]
        assert row["spy_decision_exposure_control_cash_zero_yield"]
        assert row["spy_decision_exposure_one_way_turnover"] >= 0
        assert row["spy_decision_exposure_modelled_cost_drag_pp"] >= 0
        assert row["strategy_minus_spy_decision_exposure_net_pp"] == pytest.approx(
            row["strategy_net_return_pct"] -
            row["spy_decision_exposure_net_return_pct"], abs=2e-6)
        assert row["spy_decision_exposure_annualized_volatility_fraction"] >= 0
        assert row["spy_decision_exposure_max_drawdown_hypothetical_pct"] <= 0
        assert row["spy_decision_exposure_worst_session_return_pct"] <= 1e6
    assert scenarios["5"]["spy_decision_exposure_net_return_pct"] >= (
        scenarios["15"]["spy_decision_exposure_net_return_pct"]) >= (
        scenarios["35"]["spy_decision_exposure_net_return_pct"])
    # When the strategy holds all cash, the matching SPY/cash control
    # also holds cash and incurs no fictional equity entry/exit fees.
    cash = analyze(prices(flat=True))["scenarios"]["15"]
    assert cash["spy_decision_exposure_net_return_pct"] == 0
    assert cash["spy_decision_exposure_one_way_turnover"] == 0
    assert cash["strategy_minus_spy_decision_exposure_net_pp"] == 0


def test_spy_shy_etf_control_charges_both_sides_and_earns_shy_return():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05",
                            "2026-01-06", "2026-01-07"])
    frame = pd.DataFrame({"SPY": [100., 100., 120., 120.],
                          "SHY": [100., 100., 102., 102.]}, index=dates)
    decisions = [{"execution_close_session": "2026-01-05",
                  "selected": list(p4l.SECTORS)[:3]}]
    c = .0015
    gross = p4p._spy_shy_at_strategy_decision_exposure(frame, 1, decisions, 0)
    net = p4p._spy_shy_at_strategy_decision_exposure(frame, 1, decisions, c)
    # 50% SPY (+20%) and 50% SHY (+2%): +11% before costs.
    # Both ETFs are bought at entry and liquidated on the final real close.
    assert gross["terminal_wealth"] == pytest.approx(1.11)
    assert net["terminal_wealth"] == pytest.approx(1.11 * (1 - c) ** 2)
    assert net["one_way_turnover"] == pytest.approx(2)
    assert len(net["path"]) == 4
    assert net["path"][-1] == pytest.approx(net["terminal_wealth"])
    assert net["terminal_wealth"] < gross["terminal_wealth"]


def test_spy_shy_control_rebalances_drifted_etfs_with_two_sided_turnover():
    dates = pd.to_datetime(["2026-01-02", "2026-01-05",
                            "2026-01-06", "2026-01-07"])
    frame = pd.DataFrame({"SPY": [100., 100., 120., 120.],
                          "SHY": [100., 100., 100., 100.]}, index=dates)
    decisions = [
        {"execution_close_session": "2026-01-05",
         "selected": list(p4l.SECTORS)[:3]},
        {"execution_close_session": "2026-01-06",
         "selected": list(p4l.SECTORS)[:p4l.MAX_NAMES]},
    ]
    gross = p4p._spy_shy_at_strategy_decision_exposure(frame, 1, decisions, 0)
    # 50/50 becomes 6/11 SPY and 5/11 SHY; moving to all SPY
    # trades 5/11 of each ETF, not just the net equity increment.
    assert gross["terminal_wealth"] == pytest.approx(1.1)
    assert gross["one_way_turnover"] == pytest.approx(1 + 10/11 + 1)
    with pytest.raises(p4p.FeasibilityStop, match="decision exposure"):
        p4p._spy_shy_at_strategy_decision_exposure(
            frame, 1, decisions + decisions[:1], .0015)


def test_spy_shy_comparison_is_separate_from_zero_yield_cash_and_costed():
    scenarios = analyze(prices())["scenarios"]
    for row in scenarios.values():
        assert row["spy_shy_decision_exposure_control_is_fully_invested_etfs"]
        assert row["spy_shy_decision_exposure_control_shy_is_not_cash_or_risk_free"]
        assert row["spy_shy_decision_exposure_control_uses_same_strategy_signals"]
        assert row["spy_shy_decision_exposure_one_way_turnover"] >= 2
        assert row["spy_shy_decision_exposure_modelled_cost_drag_pp"] > 0
        assert row["strategy_minus_spy_shy_decision_exposure_net_pp"] == pytest.approx(
            row["strategy_net_return_pct"] -
            row["spy_shy_decision_exposure_net_return_pct"], abs=2e-6)
        assert row["spy_shy_decision_exposure_annualized_volatility_fraction"] >= 0
        assert row["spy_shy_decision_exposure_max_drawdown_hypothetical_pct"] <= 0
    assert scenarios["5"]["spy_shy_decision_exposure_net_return_pct"] > (
        scenarios["15"]["spy_shy_decision_exposure_net_return_pct"]) > (
        scenarios["35"]["spy_shy_decision_exposure_net_return_pct"])
    # All-cash stock strategy does not incur fees; all-SHY ETF alternative
    # earns SHY adjusted-price returns but pays actual modeled ETF costs.
    cash = analyze(prices(flat=True))["scenarios"]["15"]
    assert cash["strategy_net_return_pct"] == 0
    assert cash["spy_decision_exposure_net_return_pct"] == 0
    assert cash["spy_shy_decision_exposure_net_return_pct"] == pytest.approx(
        100 * ((1 - .0015) ** 2 - 1), abs=2e-6)
    assert cash["spy_shy_decision_exposure_one_way_turnover"] == pytest.approx(2)

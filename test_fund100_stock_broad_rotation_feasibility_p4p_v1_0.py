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
    with pytest.raises(p4p.FeasibilityStop, match="NYSE"):
        analyze(p.iloc[:130])

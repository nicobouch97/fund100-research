"""P4M original selection, same-vintage forward marks, and no-order tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_frozen_forward_marks_p4m_v1_0 as p4m



@pytest.fixture(autouse=True)
def synthetic_source_clock(monkeypatch):
    # Some forward-mark fixtures intentionally model later October sessions.
    # Freeze receipt validation after those sessions instead of relying on
    # whichever real date the CI runner happens to execute the test.
    from datetime import datetime, timezone

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(p4l, "datetime", FixedClock)


def snapshot(through="2026-10-23", *, capture=None):
    baseline = pd.bdate_range(end="2026-10-23", periods=150)
    later = pd.date_range("2026-10-26", through, freq="B")
    index = baseline.append(later)
    t = np.arange(len(index), dtype=float)
    rates = {name: 0.00005 for name in p4l.SECTORS}
    for i, symbol in enumerate(p4m.ORIGINAL_SELECTION):
        rates[symbol] = 0.0020 - 0.0001 * i
    data = {symbol: 100 * np.power(1 + rate, t)
            for symbol, rate in rates.items()}
    data["SPY"] = 100 * np.power(1.0001, t)
    data["SHY"] = 100 * np.power(1.00001, t)
    prices = pd.DataFrame(data, index=index)
    if capture is None:
        capture = ("2026-10-24T03:11:53Z" if through == "2026-10-23"
                   else (index[-1] + pd.Timedelta(days=1)).strftime(
                       "%Y-%m-%dT04:15:00Z"))
    doc = p4l.evaluate(
        prices, acquired_at_utc=capture,
        provider_reference="Synthetic unit-test fixture only, no original market data",
    )
    return doc, prices


def test_synthetic_baseline_matches_actual_frozen_names():
    doc, _ = snapshot()
    assert doc["momentum_only_watchlist"] == p4m.ORIGINAL_SELECTION


def test_baseline_weekend_has_no_earned_return():
    doc, prices = snapshot()
    later, new = snapshot(capture="2026-10-24T04:15:00Z")
    result = p4m.window_mark(doc, prices, later, new)
    assert result["status"] == "WAITING_FOR_FIRST_POST_SELECTION_CLOSE"
    assert result["observed_forward_return_intervals"] == 0
    assert result["costed_marks_percent"] is None
    assert result["first_post_selection_entry_session"] is None
    assert not result["trading_authorized"]
    assert result["broker_requests"] == result["paper_orders"] == result["live_orders"] == 0


def test_first_monday_close_is_entry_not_a_backfilled_return():
    doc, prices = snapshot()
    later, new = snapshot("2026-10-26")
    result = p4m.window_mark(doc, prices, later, new)
    assert result["status"] == "ENTRY_CLOSE_ONLY_NO_RETURN"
    assert result["first_post_selection_entry_session"] == "2026-10-26"
    assert result["observed_forward_return_intervals"] == 0
    assert result["costed_marks_percent"] is None


def test_real_post_selection_intervals_costed_and_benchmarked():
    doc, prices = snapshot()
    later, new = snapshot("2026-10-28")
    result = p4m.window_mark(doc, prices, later, new)
    assert result["status"] == "SOURCE_CONSISTENT_POST_SELECTION_MARKS"
    assert result["first_post_selection_entry_session"] == "2026-10-26"
    assert result["last_post_selection_mark_session"] == "2026-10-28"
    assert result["observed_forward_return_intervals"] == 2
    assert result["observed_post_selection_sessions"] == 3
    assert result["all_post_selection_nyse_sessions_verified"]
    assert result["frozen_selection"] == p4m.ORIGINAL_SELECTION
    assert result["costed_marks_percent"]["15"]["frozen_six_minus_spy_net_pp"] > 0
    for key in ("frozen_six_net_mark_pct", "equal_weight_24_net_mark_pct",
                "spy_net_mark_pct"):
        marks = result["costed_marks_percent"]
        assert marks["5"][key] > marks["15"][key] > marks["35"][key]
    assert result["gross_path_downside"]["frozen_six"]["observed_return_intervals"] == 2
    assert result["historical_survivorship_safe"] is False
    assert result["statistically_valid_alpha_or_future_profit_proven"] is False


def test_revised_historical_adjusted_prices_never_splice_entry_and_exit():
    doc, prices = snapshot()
    later, new = snapshot("2026-10-28")
    initial = p4m.window_mark(doc, prices, later, new)
    revised = new.copy()
    revised.loc[revised.index[25], "MSFT"] *= 1.01
    new_doc = p4l.evaluate(
        revised, acquired_at_utc=later["source_acquired_at_utc"],
        provider_reference=later["source_reference"],
    )
    result = p4m.window_mark(doc, prices, new_doc, revised)
    assert result["historical_adjusted_price_cells_revised"] == 1
    assert result["costed_marks_percent"] == initial["costed_marks_percent"]


def test_original_watchlist_and_report_cannot_be_rewritten():
    doc, prices = snapshot()
    later, new = snapshot("2026-10-28")
    bad = deepcopy(doc)
    bad["momentum_only_watchlist"] = ["NVDA"]
    with pytest.raises(p4m.P4MStop, match="report"):
        p4m.window_mark(bad, prices, later, new)
    bad = deepcopy(later)
    bad["paper_authorized"] = True
    with pytest.raises(p4m.P4MStop, match="report"):
        p4m.window_mark(doc, prices, bad, new)


def test_missing_first_or_interior_nyse_session_fails_closed():
    doc, prices = snapshot()
    later, new = snapshot("2026-10-28")
    for missing in ("2026-10-26", "2026-10-27"):
        altered = new.drop(pd.Timestamp(missing))
        later_doc = p4l.evaluate(
            altered, acquired_at_utc=later["source_acquired_at_utc"],
            provider_reference=later["source_reference"],
        )
        with pytest.raises(p4m.P4MStop, match="XNYS sessions"):
            p4m.window_mark(doc, prices, later_doc, altered)


def test_backward_capture_fails_closed():
    doc, prices = snapshot()
    later, new = snapshot(capture="2026-10-24T03:00:00Z")
    with pytest.raises(p4m.P4MStop, match="predates"):
        p4m.window_mark(doc, prices, later, new)


def test_csv_and_report_archive_round_trip(tmp_path):
    doc, prices = snapshot()
    later, new = snapshot("2026-10-28")
    for stem, report, frame in (
        ("old", doc, prices), ("new", later, new)
    ):
        (tmp_path / (stem + ".json")).write_text(
            __import__("json").dumps(report), encoding="utf-8")
        (tmp_path / (stem + ".csv")).write_text(
            p4l.canonical_csv(frame), encoding="utf-8")
    result = p4m.evaluate(
        tmp_path / "old.json", tmp_path / "old.csv",
        tmp_path / "new.json", tmp_path / "new.csv",
    )
    assert result["observed_forward_return_intervals"] == 2
    with (tmp_path / "new.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(p4m.P4MStop, match="Noncanonical"):
        p4m.evaluate(
            tmp_path / "old.json", tmp_path / "old.csv",
            tmp_path / "new.json", tmp_path / "new.csv",
        )


def test_research_module_has_no_broker_network_or_private_state_access():
    code = Path(p4m.__file__).read_text(encoding="utf-8")
    for forbidden in ("urlopen(", "requests.get(", "requests.post(",
                      "/v2/orders", "ALPACA_LIVE_KEY",
                      "FUND100_PRIVATE_STATE_READ_TOKEN", "place_order("):
        assert forbidden not in code

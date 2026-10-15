"""DBC C3D pre/post index redesign: genuine SEC public source fixtures."""
from __future__ import annotations

from copy import deepcopy
import pandas as pd
import pytest

import fund100_dbc_index_break_c3d_v1_0 as d
import fund100_dbc_sec_holdings_c3c_v1_0 as c3c


@pytest.fixture
def sources():
    pre = d.read_prechange()
    post = pd.read_csv(
        d.POSTCHANGE_CSV,
        dtype={col: "string" for col in c3c.COLUMNS
               if col not in ("contracts", "notional_usd")},
    )
    return pre, post


def test_actual_2025_sec_14_open_futures_positions_and_balance_sheet(sources):
    pre, _ = sources
    result = d.validate_prechange(pre)
    assert len(result) == 14
    assert set(result["commodity"]) == d.CORE_EXPOSURES
    assert int(result["notional_usd"].sum()) == 1288934852
    assert d.FILING["shareholders_equity_usd"] == 1289445913
    assert abs(result["notional_usd"].sum()/d.FILING["shareholders_equity_usd"] - 1) < .03
    assert d.prechange_sha256()
    assert len(d.prechange_sha256()) == 64


def test_precisely_14_new_index_commodities_in_2026_not_14_futures_rolls(sources):
    pre, post = sources
    summary = d.compare(pre, post, d.prechange_sha256(), "postdigest")
    assert summary["real_2025_prechange_index_descriptions"] == 14
    assert summary["real_2026_postchange_futures_descriptions"] == 28
    assert summary["added_commodity_count"] == 14
    assert set(summary["newly_included_commodity_descriptions"]) == d.NEW_EXPOSURES
    for name in ("ICE Cocoa", "ICE Coffee", "COMEX Copper",
                 "CME Live Cattle", "CBOT Wheat KCB"):
        assert name in summary["newly_included_commodity_descriptions"]


def test_exact_prechange_commodity_holdings_not_retroactive_2026_expansion(sources):
    pre, post = sources
    s = d.compare(pre, post, d.prechange_sha256(), "post")
    assert s["may_not_assign_q1_or_q2_future_holdings_to_2025"] is True
    assert s["prechange_filing_cannot_be_prospective_prechange_strategy_signal"] is True
    assert s["prechange_positions_first_publicly_usable_same_day_as_index_change"] is True
    assert s["historical_curve_or_dbc_roll_pnl_computed"] is False
    assert s["official_daily_index_optimization_replication"] is False


def test_sec_filing_lag_at_change_day_and_two_later_quarters(sources):
    pre, post = sources
    expected = {
        "2025-09-30": None,
        "2025-11-07": None,
        "2025-11-10": "2025-09-30",
        "2026-03-31": "2025-09-30",
        "2026-05-08": "2026-03-31",
        "2026-06-30": "2026-03-31",
        "2026-08-10": "2026-06-30",
    }
    for day, statement in expected.items():
        assert d.asof_disclosed_snapshot(pre, post, day) == statement


def test_quarterly_reported_sectors_normalized_not_index_returns(sources):
    pre, post = sources
    result = d.compare(pre, post, d.prechange_sha256(), "post")
    periods = result["published_statement_periods"]
    assert set(periods) == {"2025-09-30", "2026-03-31", "2026-06-30"}
    assert periods["2025-09-30"]["futures_position_count"] == 14
    assert periods["2026-03-31"]["futures_position_count"] == 28
    assert periods["2026-06-30"]["futures_position_count"] == 28
    for row in periods.values():
        assert sum(row["notional_sector_weights_not_index_weights"].values()) == pytest.approx(1, abs=5e-6)
        assert row["gross_reported_notional_usd"] > 1_000_000_000
    assert periods["2025-09-30"]["conservative_first_usable_date"] == "2025-11-10"


def test_prechange_exact_sec_source_identity_and_release_date(sources):
    pre, _ = sources
    assert d.validate_prechange(pre) is not None
    for col, val in (
        ("statement_date", "2025-09-29"),
        ("sec_filing_date", "2025-09-30"),
        ("available_date", "2025-10-01"),
        ("accession", "0000000000-00-000001"),
        ("sec_filing_url", "https://example.com/unknown"),
    ):
        altered = pre.copy()
        altered[col] = val
        with pytest.raises(d.FilingBreakStop):
            d.validate_prechange(altered)


def test_missing_or_duplicated_prechange_record_never_accepted(sources):
    pre, _ = sources
    cases = [
        pre.iloc[:-1].copy(),
        pd.concat([pre, pre.iloc[-1:]], ignore_index=True),
        pre.assign(commodity="CBOT Invalid"),
        pre.assign(sector="Unapproved"),
        pre.assign(delivery_month="2025-99"),
        pre.assign(delivery_month="2012-01"),
        pre.assign(contracts=-10),
        pre.assign(notional_usd=0),
        pre.assign(notional_usd=100),
        pre.assign(notional_usd=1.5),
    ]
    for raw in cases:
        with pytest.raises(d.FilingBreakStop):
            d.validate_prechange(raw)


def test_2026_c3c_history_is_independently_validated_and_unchanged(sources):
    pre, post = sources
    pre_old, post_old = pre.copy(), post.copy()
    d.compare(pre, post, d.prechange_sha256(), "postdigest")
    pd.testing.assert_frame_equal(pre, pre_old)
    pd.testing.assert_frame_equal(post, post_old)


def test_research_cannot_auto_authorize_trading(sources):
    pre, post = sources
    out = d.compare(pre, post, d.prechange_sha256(), "post")
    assert out["trading_authorized"] is False
    assert out["paper_authorized"] is False
    assert out["live_authorized"] is False
    assert out["broker_order_count"] == 0
    assert out["notional_changes_are_not_strategy_pnl"] is True
    assert out["filing_snapshots_are_not_intraperiod_positions"] is True


def test_invalid_asof_date_rejected(sources):
    pre, post = sources
    for value in ("2025-02-30", "10/11/2025", "2025-1-1", None):
        with pytest.raises(d.FilingBreakStop):
            d.asof_disclosed_snapshot(pre, post, value)

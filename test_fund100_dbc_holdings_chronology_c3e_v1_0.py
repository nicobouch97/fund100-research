"""C3E source-verified five DBC SEC period regression tests, offline only."""
from __future__ import annotations

import pandas as pd
import pytest

import fund100_dbc_holdings_chronology_c3e_v1_0 as c


@pytest.fixture
def sources():
    return c.read_inputs()


def test_five_real_sec_statement_snapshots_and_112_lines(sources):
    frames, hashes = sources
    result = c.compare(frames, hashes)
    assert set(result["periods"]) == set(c.SOURCES)
    assert result["count_snapshots"] == 5
    assert result["count_actual_reported_open_futures_lines"] == 112
    assert set(p["reported_futures_positions"] for p in result["periods"].values()) == {14, 28}
    assert result["periods"]["2025-06-30"]["reported_futures_notional_usd"] == 1230805407
    assert result["periods"]["2025-12-31"]["reported_futures_notional_usd"] == 1223550999
    assert all(len(p["manually_transcribed_csv_sha256"]) == 64 for p in result["periods"].values())


def test_asof_does_not_see_non_public_q2_or_q4_futures(sources):
    dates = {
        "2025-06-30": None,
        "2025-08-07": None,
        "2025-08-08": "2025-06-30",
        "2025-11-07": "2025-06-30",
        "2025-11-10": "2025-09-30",
        "2025-12-31": "2025-09-30",
        "2026-03-02": "2025-09-30",
        "2026-03-03": "2025-12-31",
        "2026-03-31": "2025-12-31",
        "2026-05-08": "2026-03-31",
        "2026-08-07": "2026-03-31",
        "2026-08-10": "2026-06-30",
    }
    for day, expected in dates.items():
        assert c.known_snapshot_at(day) == expected


def test_no_claim_daily_index_carry_or_broker_authorization(sources):
    frames, hashes = sources
    result = c.compare(frames, hashes)
    assert result["status"] == "OFFICIAL_SEC_HOLDINGS_HISTORY_NOT_TRADE_READY"
    assert result["backtest_eligible"] is False
    assert result["quarterly_filings_are_delayed_and_not_daily_holdings"] is True
    assert result["issuer_position_notional_is_NOT_DB_INDEX_weights"] is True
    assert result["reported_delivery_months_not_exact_exchange_expiry"] is True
    assert result["cannot_infer_roll_timing_or_earned_futures_carry"] is True
    assert result["fund_change_of_notional_not_profit"] is True
    assert result["live_authorized"] is False
    assert result["paper_authorized"] is False
    assert result["broker_order_count"] == 0


def test_index_break_statement_time_separate_from_public_use_time(sources):
    frames, hashes = sources
    r = c.compare(frames, hashes)
    assert r["index_reform_effective"] == "2025-11-10"
    assert r["last_prechange_disclosure_first_knowable_on_reform_date"] is True
    assert r["first_postchange_disclosure_first_knowable_2026_03_03"] is True
    assert r["not_knowable_as_of_2025_12_31"] == "2025-09-30"
    assert r["periods"]["2025-12-31"]["index_methodology_as_of_statement"] == "POST_2025_11_10"


def test_real_2025_q2_is_14_positions_and_reconciled(sources):
    frames, _ = sources
    q2 = c.validate_period("2025-06-30", frames["2025-06-30"])
    assert set(q2["commodity"]) == c.c3d.CORE_EXPOSURES
    assert int(q2["notional_usd"].sum()) == 1230805407
    assert c.SOURCES["2025-06-30"]["shareholders_equity_usd"] == 1230605532


def test_real_2025_q4_is_28_positions_reconciled(sources):
    frames, _ = sources
    q4 = c.validate_period("2025-12-31", frames["2025-12-31"])
    assert set(q4["commodity"]) == c.c3c.COMMODITIES
    assert int(q4["notional_usd"].sum()) == 1223550999
    assert c.SOURCES["2025-12-31"]["shareholders_equity_usd"] == 1223200118
    assert q4.loc[q4["commodity"] == "CME Feeder Cattle", "contracts"].iloc[0] == 147


def test_all_historical_period_notional_sector_weights_normalize(sources):
    frames, hashes = sources
    r = c.compare(frames, hashes)
    for period, item in r["periods"].items():
        assert sum(item["reported_sector_notional_fraction_NOT_index_weights"].values()) == pytest.approx(1, abs=0.000005)
        assert item["reported_futures_notional_usd"] > 1_000_000_000
        assert item["sec_filed_on"] < item["first_conservative_public_use"]


def test_changed_filing_date_url_or_accession_rejected(sources):
    frames, _ = sources
    for col, val in (
        ("sec_filing_date", "2025-06-30"),
        ("available_date", "2025-12-31"),
        ("accession", "0000000000-00-000001"),
        ("sec_filing_url", "https://example.org/not-a-filing"),
        ("statement_date", "2025-12-30"),
    ):
        mod = frames["2025-12-31"].copy()
        mod[col] = val
        with pytest.raises(c.FiveSnapshotStop):
            c.validate_period("2025-12-31", mod)


def test_duplicate_or_missing_real_disclosed_futures_refused(sources):
    frames, _ = sources
    base = frames["2025-12-31"]
    for bad in (
        base.iloc[:-1],
        pd.concat([base, base.iloc[-1:]], ignore_index=True),
        base.assign(commodity="FAKE GOLD"),
        base.assign(delivery_month="2025-99"),
        base.assign(delivery_month="2020-01"),
        base.assign(contracts=-5),
        base.assign(notional_usd=0),
        base.assign(notional_usd=100),
    ):
        with pytest.raises(c.FiveSnapshotStop):
            c.validate_period("2025-12-31", bad)


def test_source_and_derived_frames_not_mutated(sources):
    frames, hashes = sources
    pristine = {k: v.copy(deep=True) for k, v in frames.items()}
    c.compare(frames, hashes)
    for k in frames:
        pd.testing.assert_frame_equal(frames[k], pristine[k])


def test_missing_one_period_is_not_silently_approximated(sources):
    frames, hashes = sources
    cut = dict(frames)
    cut.pop("2025-06-30")
    with pytest.raises(c.FiveSnapshotStop):
        c.compare(cut, hashes)


def test_reject_noncanonical_historical_decision_date():
    for invalid in ("2025-1-1", "2025-02-30", "11/10/2025", None):
        with pytest.raises(c.FiveSnapshotStop):
            c.known_snapshot_at(invalid)

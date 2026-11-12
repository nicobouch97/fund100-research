"""Read-only LEAN reference-format tests, entirely synthetic fixtures.

Synthetic CSV rows model the publicly documented LEAN sample columns.
No licensed ETF constituent rows or Algoseek proprietary data copied.
"""

from dataclasses import asdict
from datetime import date

import pytest

from fund100_v2.provider_sample_inspector import (
    NOT_BACKTEST_READY,
    inspect_lean_etf_constituents,
    inspect_lean_map_file,
)


SNAPSHOT = date(2020, 12, 1)


def sample_holdings():
    return (
        "AAA,AAA ABCD123456,20201130,0.60,120000,\n"
        "BBB,BBB WXYZ654321,20201130,0.40,25000,\n"
    )


def test_public_reference_format_is_inspectable_but_never_verified():
    report = inspect_lean_etf_constituents(
        sample_holdings(), snapshot_day=SNAPSHOT
    )
    assert report.constituents == 2
    assert report.duplicate_sid_distinct_tickers == ()
    assert report.holdings_first_date == "2020-11-30"
    assert report.gross_reported_weights == pytest.approx(1.0)
    assert len(report.raw_sha256) == 64
    assert report.research_readiness == NOT_BACKTEST_READY
    for key in (
        "source_authenticity_verified",
        "historical_publication_timestamp_verified",
        "full_market_membership_verified",
        "individual_security_prices_verified",
        "delisting_settlements_verified",
    ):
        assert asdict(report)[key] is False


def test_reference_samples_with_reused_sid_are_flagged_not_conflated():
    rows = (
        "AAA,AAA TESTDUPLICATE,20201130,0.60,120000,\n"
        "BBB,BBB TESTDUPLICATE,20201130,0.40,25000,\n"
    )
    report = inspect_lean_etf_constituents(rows, snapshot_day=SNAPSHOT)
    assert report.duplicate_sid_distinct_tickers == ("TESTDUPLICATE",)
    assert report.research_readiness == NOT_BACKTEST_READY


def test_sample_fingerprint_changes_with_weight_change():
    original = inspect_lean_etf_constituents(
        sample_holdings(), snapshot_day=SNAPSHOT
    )
    modified = inspect_lean_etf_constituents(
        sample_holdings().replace("0.40", "0.39"),
        snapshot_day=SNAPSHOT,
    )
    assert original.raw_sha256 != modified.raw_sha256


@pytest.mark.parametrize("row,reason", [
    ("aaa,aaa ABCD1234,20201130,0.5,1000,\n", "ticker"),
    ("AAA,BBB ABCD1234,20201130,0.5,1000,\n", "identity"),
    ("AAA,AAA invalid-sid,20201130,0.5,1000,\n", "SID"),
    ("AAA,AAA ABCD1234,20201202,0.5,1000,\n", "Future"),
    ("AAA,AAA ABCD1234,invalid,0.5,1000,\n", "date"),
    ("AAA,AAA ABCD1234,20201130,nan,1000,\n", "numeric"),
    ("AAA,AAA ABCD1234,20201130,1.01,1000,\n", "numeric"),
    ("AAA,AAA ABCD1234,20201130,0.5,-1,\n", "numeric"),
    ("AAA,AAA ABCD1234,20201130,0.5,1000,extra\n", "final"),
    ("AAA,AAA ABCD1234,20201130,0.5,1000\n", "column"),
    ("", "nonempty"),
])
def test_invalid_etf_sample_fails_closed(row, reason):
    with pytest.raises(ValueError, match=reason):
        inspect_lean_etf_constituents(row, snapshot_day=SNAPSHOT)


def test_duplicate_ticker_in_holdings_file_is_not_double_counted():
    row = "AAA,AAA ABCD1234,20201130,0.5,1000,\n"
    with pytest.raises(ValueError, match="Duplicate ticker"):
        inspect_lean_etf_constituents(row + row, snapshot_day=SNAPSHOT)


def test_map_file_ticker_changes_do_not_become_live_permissions():
    sample = (
        "20181001,abc,Q\n"
        "20190715,xyz,Q\n"
        "20501231,xyz,Q\n"
    )
    result = inspect_lean_map_file(sample, filename_symbol="ABC")
    assert len(result.events) == 2
    assert result.events[0].ticker == "ABC"
    assert result.events[1].ticker == "XYZ"
    assert result.sentinel_record_present is True
    assert len(result.raw_sha256) == 64
    assert result.research_readiness == NOT_BACKTEST_READY
    assert result.historical_publication_timestamp_verified is False
    assert all(
        event.effective_date.year != 2050 for event in result.events
    )


@pytest.mark.parametrize("rows,match", [
    ("", "nonempty"),
    ("20501231,abc,Q\n", "no actual"),
    ("20190101,abc,Q\n20180101,xyz,Q\n", "ordered"),
    ("20190101,abc,Q\n20190101,xyz,Q\n", "ordered"),
    ("20190101,abc,Q\n20501231,abc,Q\n20510101,abc,Q\n", "post-sentinel"),
    ("20190101,abc,Exchange\n", "exchange"),
    ("20190101,abc\n", "column"),
    ("20191301,abc,Q\n", "calendar"),
    ("20190101,abc/xyz,Q\n", "mapped ticker"),
])
def test_corrupt_map_history_rejected(rows, match):
    with pytest.raises(ValueError, match=match):
        inspect_lean_map_file(rows, filename_symbol="ABC")


def test_vendor_format_does_not_create_trades_or_backtest_panel():
    audit = inspect_lean_etf_constituents(
        sample_holdings(), snapshot_day=SNAPSHOT
    )
    for field in (
        "orders", "target_weights", "price_history",
        "total_return_close", "live_execution_authorized", "panel"
    ):
        assert not hasattr(audit, field)


def test_missing_full_market_coverage_not_rescued_by_etf_weights():
    audit = inspect_lean_etf_constituents(
        sample_holdings(), snapshot_day=SNAPSHOT
    )
    assert audit.gross_reported_weights == pytest.approx(1.0)
    # Weights adding up to 1.0 prove no universe coverage or price quality.
    assert audit.full_market_membership_verified is False

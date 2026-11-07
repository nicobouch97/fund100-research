"""Offline mock tests for QC ETF constituents; not ETF-trading evidence."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from fund100_v2.qc_cloud_feasibility import CloudWindow
from fund100_v2.qc_etf_cloud_feasibility import (
    NOT_ETF_PRICE_EVIDENCE,
    check_etf_constituent_coverage,
)


class Row:
    def __init__(self, symbol, weight=0.1, when=date(2020, 11, 27)):
        self.symbol = symbol
        self.weight = weight
        self.last_update = datetime(when.year, when.month, when.day)


class UniverseMethods:
    def etf(self, symbol, *, universe_filter_func):
        assert symbol == "SPY"
        return universe_filter_func


class OfflineQuantBook:
    def __init__(self, rows_by_call):
        self.universe = UniverseMethods()
        self.rows_by_call = rows_by_call
        self.callback = None
        self.sent = []
        self.calls = 0

    def add_universe(self, selection):
        self.callback = selection
        return selection

    def universe_history(self, universe, start, end):
        self.calls += 1
        batches = []
        for records in self.rows_by_call:
            batches.append(universe(records))
        self.sent = batches
        return batches


def interval():
    return CloudWindow(date(2020, 11, 23), date(2020, 12, 4))


def test_etf_constituent_coverage_is_not_etf_price_evidence():
    book = OfflineQuantBook([[
        Row("AAA", 0.50), Row("BBB", 0.25), Row("CCC", 0.0)
    ]])
    report = check_etf_constituent_coverage(book)
    assert book.calls == 1
    assert len(book.sent[0]) == 2
    assert report.etf == "SPY"
    assert len(report.dated_snapshots) == 1
    day = report.dated_snapshots[0]
    assert day.observed_constituent_rows == 3
    assert day.valid_positive_weights == 2
    assert day.total_valid_reported_weight == pytest.approx(0.75)
    assert report.evidence == NOT_ETF_PRICE_EVIDENCE
    assert report.etf_share_prices_verified is False
    assert report.historic_release_times_verified is False
    assert report.dividend_adjustments_verified is False
    assert report.delisting_proceeds_verified is False
    assert report.cloud_runtime_execution_verified is False
    assert report.raw_provider_data_exported is False
    assert report.account_orders_sent == 0
    assert len(report.audit_sha256) == 64


def test_detects_identifier_collisions_without_claiming_unique_issuers():
    qb = OfflineQuantBook([[
        Row("AAA", 0.30), Row("AAA", 0.20), Row("BBB", 0.10)
    ]])
    report = check_etf_constituent_coverage(qb)
    record = report.dated_snapshots[0]
    assert record.duplicate_symbol_keys == 1
    assert record.distinct_symbol_keys == 2
    assert record.selected_for_temporary_research == 2


def test_bounded_selection_sorts_by_weight():
    qb = OfflineQuantBook([[
        Row("AAA", 0.1), Row("BBB", 0.8), Row("CCC", 0.2)
    ]])
    result = check_etf_constituent_coverage(qb, max_select=1)
    assert result.dated_snapshots[0].selected_for_temporary_research == 1
    assert qb.sent[0] == ["BBB"]


@pytest.mark.parametrize("weight", [float("nan"), float("inf"), -1, 1.1, None])
def test_invalid_weights_never_select(weight):
    qb = OfflineQuantBook([[
        Row("INVALID", weight), Row("VALID", 0.2)
    ]])
    result = check_etf_constituent_coverage(qb)
    assert result.dated_snapshots[0].valid_positive_weights == 1
    assert qb.sent[0] == ["VALID"]


@pytest.mark.parametrize("cap", [0, -1, 11, True, 1.5])
def test_cap_limits_are_enforced(cap):
    qb = OfflineQuantBook([[Row("AAA")]])
    with pytest.raises(ValueError, match="selection limit"):
        check_etf_constituent_coverage(qb, max_select=cap)


def test_wrong_etf_rejected():
    with pytest.raises(ValueError, match="SPY"):
        check_etf_constituent_coverage(
            OfflineQuantBook([[Row("AAA")]]), etf="QQQ"
        )


def test_absent_etf_cloud_runtime_is_not_claimed_available():
    with pytest.raises(TypeError, match="QuantBook-like"):
        check_etf_constituent_coverage(object())


def test_empty_cloud_history_rejected():
    qb = OfflineQuantBook([])
    with pytest.raises(ValueError, match="not materialized"):
        check_etf_constituent_coverage(qb)


def test_empty_constituents_not_valid_evidence():
    qb = OfflineQuantBook([[]])
    with pytest.raises(ValueError, match="empty or unbounded"):
        check_etf_constituent_coverage(qb)


def test_bad_or_mixed_update_dates_fail():
    qb = OfflineQuantBook([[
        Row("AAA", when=date(2020, 11, 27)),
        Row("BBB", when=date(2020, 11, 30)),
    ]])
    with pytest.raises(ValueError, match="Inconsistent"):
        check_etf_constituent_coverage(qb)


def test_missing_last_update_fails():
    row = Row("AAA")
    row.last_update = None
    qb = OfflineQuantBook([[row]])
    with pytest.raises(ValueError, match="last_update"):
        check_etf_constituent_coverage(qb)


def test_no_price_data_or_order_fields_exposed():
    report = check_etf_constituent_coverage(
        OfflineQuantBook([[Row("AAA")]])
    )
    for field in (
        "prices", "orders", "target_weights",
        "total_return_close", "live_execution_authorized",
        "price_history",
    ):
        assert not hasattr(report, field)

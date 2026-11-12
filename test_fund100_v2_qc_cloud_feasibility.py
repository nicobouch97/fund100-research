"""Offline mock tests for QC Cloud feasibility; NOT a real QC Cloud run."""

from datetime import date, datetime

import pytest

from fund100_v2.qc_cloud_feasibility import (
    CloudWindow,
    DEFAULT_WINDOWS,
    NOT_VALIDATED,
    aggregate_report_json,
    run_cloud_coverage_probe,
)


class FundamentalFake:
    def __init__(self, ticker, when, price=40.0, volume=15_000_000.0):
        self.symbol = ticker
        self.end_time = datetime(when.year, when.month, when.day)
        self.price = price
        self.dollar_volume = volume


class CloudResearchMock:
    """In-memory stand-in. It has no position, order or network methods."""

    def __init__(self, rows):
        self.rows = rows
        self.selection_functions = []
        self.subscription_batches = []
        self.calls = 0

    def add_universe(self, fn):
        self.selection_functions.append(fn)
        return fn

    def universe_history(self, universe, start, end):
        self.calls += 1
        day = date(start.year, start.month, start.day)
        entries = self.rows.get(day, ())
        outputs = []
        for rows in entries:
            outputs.append(universe(rows))
        return outputs


def fixture_data():
    return {
        date(*period[:3]): ((
            FundamentalFake("AAA", date(*period[:3]), price=25),
            FundamentalFake("BBB", date(*period[:3]), price=30),
            FundamentalFake("CCC", date(*period[:3]), price=1),
        ),)
        for period in (
            (2018, 9, 4),
            (2020, 11, 23),
            (2024, 6, 3),
        )
    }


def test_bounded_three_window_coverage_has_no_alpha_or_order_capability():
    qb = CloudResearchMock(fixture_data())
    report = run_cloud_coverage_probe(qb)
    assert qb.calls == 3
    assert len(report.windows) == 3
    assert len(report.audit_sha256) == 64
    assert report.research_status == NOT_VALIDATED
    assert report.used_live_credentials is False
    assert report.broker_orders_submitted == 0
    assert report.csv_export_performed is False
    assert report.historic_vintages_verified is False
    assert report.delisting_cashflows_verified is False
    assert report.actual_cloud_execution_verified_by_github_ci is False
    for window in report.windows:
        assert window.research_ready is False
        assert window.raw_history_materialized is True
        assert window.observed_source_dates == 1
        row = window.daily[0]
        assert row.visible_universe_rows == 3
        assert row.passing_price_and_volume == 2
        assert row.selected_for_research_subscription == 2
    text = aggregate_report_json(report)
    assert NOT_VALIDATED in text
    assert "\"broker_orders_submitted\":0" in text
    assert "AAA" not in text
    assert "BBB" not in text


def test_liquidity_ranking_and_research_subscription_cap():
    rows = [(FundamentalFake(chr(65+i)*3, date(2024, 6, 3),
                volume=8_000_000 + i * 100_000)
             for i in range(30))]
    windows = (CloudWindow(date(2024, 6, 3), date(2024, 6, 8)),)
    qb = CloudResearchMock({
        date(2024, 6, 3): (tuple(rows[0]),),
    })
    report = run_cloud_coverage_probe(qb, windows=windows, max_subscriptions=5)
    item = report.windows[0].daily[0]
    assert item.passing_price_and_volume == 30
    assert item.selected_for_research_subscription == 5


def test_duplicate_symbols_diagnosed_without_double_selection():
    window = CloudWindow(date(2024, 6, 3), date(2024, 6, 7))
    qb = CloudResearchMock({
        date(2024, 6, 3): ((
            FundamentalFake("AAA", date(2024, 6, 3)),
            FundamentalFake("AAA", date(2024, 6, 3)),
            FundamentalFake("BBB", date(2024, 6, 3)),
        ),)
    })
    report = run_cloud_coverage_probe(qb, windows=(window,))
    day = report.windows[0].daily[0]
    assert day.duplicate_symbol_keys == 1
    assert day.distinct_symbol_keys == 2
    assert day.selected_for_research_subscription == 2


def test_unbounded_window_refused_before_any_provider_read():
    with pytest.raises(ValueError, match="Refuse bulk"):
        CloudWindow(date(2019, 1, 2), date(2020, 1, 2))


@pytest.mark.parametrize("invalid", (0, 21, True, -1, "10"))
def test_invalid_subscription_caps_rejected(invalid):
    with pytest.raises(ValueError, match="Bounded"):
        run_cloud_coverage_probe(CloudResearchMock(fixture_data()),
                                 max_subscriptions=invalid)


def test_cloud_client_required_not_mocked_into_success():
    with pytest.raises(TypeError, match="QuantBook-like"):
        run_cloud_coverage_probe(object())


def test_empty_day_is_not_independently_verified_coverage():
    qb = CloudResearchMock({
        date(2024, 6, 3): ((),)
    })
    with pytest.raises(ValueError, match="empty day"):
        run_cloud_coverage_probe(qb, windows=(
            CloudWindow(date(2024, 6, 3), date(2024, 6, 7)),
        ))


def test_empty_historical_response_fails():
    qb = CloudResearchMock({})
    with pytest.raises(ValueError, match="not materialized"):
        run_cloud_coverage_probe(qb, windows=(
            CloudWindow(date(2024, 6, 3), date(2024, 6, 7)),
        ))


def test_nan_and_negative_data_never_pass_bounded_liquidity():
    day = date(2024, 6, 3)
    qb = CloudResearchMock({day: ((
        FundamentalFake("BAD", day, price=float("nan")),
        FundamentalFake("VOL", day, volume=-1),
        FundamentalFake("LOW", day, price=1),
        FundamentalFake("GOOD", day, price=5, volume=5_000_000),
    ),)})
    report = run_cloud_coverage_probe(
        qb, windows=(CloudWindow(day, date(2024, 6, 8)),)
    )
    item = report.windows[0].daily[0]
    assert item.visible_universe_rows == 4
    assert item.passing_price_and_volume == 1


def test_conflicting_same_day_research_snapshots_fail():
    day = date(2024, 6, 3)
    qb = CloudResearchMock({day: (
        (FundamentalFake("AAA", day),),
        (FundamentalFake("BBB", day), FundamentalFake("CCC", day)),
    )})
    with pytest.raises(ValueError, match="Conflicting"):
        run_cloud_coverage_probe(
            qb, windows=(CloudWindow(day, date(2024, 6, 8)),)
        )


def test_mixed_provider_dates_are_not_a_valid_single_snapshot():
    day = date(2024, 6, 3)
    qb = CloudResearchMock({day: ((
        FundamentalFake("AAA", day),
        FundamentalFake("BBB", date(2024, 6, 4)),
    ),)})
    with pytest.raises(ValueError, match="mixes"):
        run_cloud_coverage_probe(
            qb, windows=(CloudWindow(day, date(2024, 6, 8)),)
        )


def test_report_hash_changes_when_coverage_changes():
    original = CloudResearchMock(fixture_data())
    modified = fixture_data()
    modified[date(2024, 6, 3)] = ((
        FundamentalFake("AAA", date(2024, 6, 3)),
    ),)
    before = run_cloud_coverage_probe(original)
    after = run_cloud_coverage_probe(CloudResearchMock(modified))
    assert before.audit_sha256 != after.audit_sha256


def test_date_outside_requested_window_cannot_be_passed_off_as_coverage():
    day = date(2024, 6, 3)
    qb = CloudResearchMock({day: ((
        FundamentalFake("AAA", date(2024, 6, 30)),
    ),)})
    with pytest.raises(ValueError, match="Unexpected historical"):
        run_cloud_coverage_probe(
            qb, windows=(CloudWindow(day, date(2024, 6, 8)),)
        )


def test_missing_source_period_cannot_be_claimed_as_historical():
    day = date(2024, 6, 3)
    bad = FundamentalFake("AAA", day)
    bad.end_time = None
    qb = CloudResearchMock({day: ((bad,),)})
    with pytest.raises(ValueError, match="source period"):
        run_cloud_coverage_probe(
            qb, windows=(CloudWindow(day, date(2024, 6, 8)),)
        )

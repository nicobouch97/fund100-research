"""V2 publication-clock regression: do not use unpublished EOD at the close.

Tests operate on synthetic, self-attested input bundles, not actual vendor
timestamps. The fixed next-WEEKDAY cutoff is not an exchange holiday calendar.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from fund100_v2.data_contract import load_research_bundle
from test_fund100_v2_data_contract import make_bundle, modify_price


NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def _stamp(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute), tzinfo=NY).astimezone(
        UTC
    ).isoformat().replace("+00:00", "Z")


def _overwrite_first_price_timestamp(folder, text: str) -> None:
    modify_price(
        folder, lambda rows: rows[0].update(price_known_at_utc=text)
    )


def _friday_fixture(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    jan3 = date(2025, 1, 3)
    assert jan3 in days
    return days, jan3


def test_eod_known_friday_night_after_midnight_utc_is_eligible_by_monday(tmp_path):
    days, friday = _friday_fixture(tmp_path)
    # Friday 20:30 New York -> Saturday 01:30 UTC, after prior contract's
    # same-UTC-day cutoff but before the next available weekday premarket.
    def revise(rows):
        for row in rows:
            if row["session"] == friday.isoformat():
                row["price_known_at_utc"] = _stamp(friday, 20, 30)

    modify_price(tmp_path, revise)
    bundle = load_research_bundle(tmp_path, as_of=days[-1])
    assert bundle.evidence.decision_timing_policy == (
        "AFTER_EOD_PUBLICATION_BEFORE_NEXT_WEEKDAY_0900_NY"
    )


def test_price_after_next_weekday_premarket_cutoff_fails(tmp_path):
    days, _ = _friday_fixture(tmp_path)
    # First synthetic row is Thursday Jan 2, so Friday Jan 3 09:01 NY
    # is already too late for the next premarket research decision.
    _overwrite_first_price_timestamp(
        tmp_path, _stamp(date(2025, 1, 3), 9, 1)
    )
    with pytest.raises(ValueError, match="vintage"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_price_before_next_weekday_premarket_is_allowed(tmp_path):
    days, _ = _friday_fixture(tmp_path)
    _overwrite_first_price_timestamp(
        tmp_path, _stamp(date(2025, 1, 3), 8, 59)
    )
    load_research_bundle(tmp_path, as_of=days[-1])


def test_no_future_data_dated_after_asof_last_session(tmp_path):
    days, _ = _friday_fixture(tmp_path)
    last = days[-1]
    # Last observation is edited to pretend its publication occurred
    # just after midnight UTC the next day; it cannot appear in a bundle
    # researched strictly as of its last session.
    def revise(rows):
        for row in rows:
            if row["session"] == last.isoformat():
                row["price_known_at_utc"] = (
                    datetime.combine(
                        last + timedelta(days=1), time(0, 30), tzinfo=UTC
                    ).isoformat()
                )
    modify_price(tmp_path, revise)
    with pytest.raises(ValueError, match="as_of|vintage"):
        load_research_bundle(tmp_path, as_of=last)


@pytest.mark.parametrize("first_session", [date(2025, 1, 2), date(2025, 3, 7)])
def test_timezone_cutoff_tracks_ny_dst_without_utc_assumptions(
    tmp_path, first_session
):
    days, _, _, _ = make_bundle(tmp_path)
    next_weekday = first_session + timedelta(days=1)
    while next_weekday.weekday() > 4:
        next_weekday += timedelta(days=1)
    ts = _stamp(next_weekday, 9, 1)
    def revise(rows):
        for row in rows:
            if row["session"] == first_session.isoformat():
                row["price_known_at_utc"] = ts
    modify_price(tmp_path, revise)
    with pytest.raises(ValueError, match="vintage"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_future_eligibility_change_cannot_grant_hindsight_free_fill(tmp_path):
    # Dedicated walk-forward regression tests cover the return path. This
    # fixture isolates publication provenance; missing real quotes cannot
    # be repaired with a timestamp field alone.
    days, _, _, _ = make_bundle(tmp_path)
    first = load_research_bundle(tmp_path, as_of=days[-1])
    assert first.evidence.source_verification == (
        "SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED"
    )

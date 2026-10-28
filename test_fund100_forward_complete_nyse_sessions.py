"""Forward Lab must not silently skip an entire completed NYSE session."""
from datetime import date, datetime, timezone

import exchange_calendars as xcals
import pandas as pd
import pytest

import fund100_forward as forward


def _sessions(start: str, end: str) -> pd.DatetimeIndex:
    return xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp(start), pd.Timestamp(end)
    ).tz_localize(None).normalize()


def test_complete_sessions_accept_weekend_and_nyse_holiday():
    # Thanksgiving is not a trading day; the following Friday is.
    observed = _sessions("2026-11-25", "2026-11-27")
    assert list(observed.strftime("%Y-%m-%d")) == [
        "2026-11-25", "2026-11-27"
    ]
    forward.verify_complete_forward_nyse_sessions(
        observed,
        first_session=pd.Timestamp("2026-11-25"),
        last_completed_date=date(2026, 11, 29),
    )


@pytest.mark.parametrize("missing", ["2026-10-20", "2026-10-27"])
def test_whole_missing_completed_market_day_is_rejected(missing):
    observed = _sessions("2026-10-19", "2026-10-27").drop(
        pd.Timestamp(missing)
    )
    with pytest.raises(RuntimeError, match=missing):
        forward.verify_complete_forward_nyse_sessions(
            observed,
            first_session=pd.Timestamp("2026-10-19"),
            last_completed_date=date(2026, 10, 27),
        )


def test_invalid_duplicate_or_out_of_order_sessions_are_rejected():
    original = _sessions("2026-10-26", "2026-10-27")
    for bad in (
        original.append(original[-1:]),
        original[::-1],
        original + pd.Timedelta(hours=1),
    ):
        with pytest.raises(RuntimeError, match="Invalid prospective market"):
            forward.verify_complete_forward_nyse_sessions(
                bad,
                first_session=pd.Timestamp("2026-10-26"),
                last_completed_date=date(2026, 10, 27),
            )


@pytest.mark.parametrize("missing", [None, "2026-10-20", "2026-10-27"])
def test_real_forward_loader_rejects_whole_missing_source_session(
    monkeypatch, missing
):
    """Test the actual loader path, not only the isolated calendar helper."""
    dates = _sessions("2026-09-16", "2026-10-27")
    if missing is not None:
        dates = dates.drop(pd.Timestamp(missing))
    prices = pd.DataFrame(
        100.0, index=dates, columns=forward.EQUITY_UNIVERSE
    )
    benchmark = pd.Series(100.0, index=dates)

    monkeypatch.setattr(
        forward, "download_prices",
        lambda cfg, **kwargs: (prices.copy(), benchmark.copy()),
    )

    class FrozenClock:
        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return datetime(2026, 10, 28, 0, 40, tzinfo=timezone.utc)

    monkeypatch.setattr(forward, "datetime", FrozenClock)
    if missing:
        with pytest.raises(RuntimeError, match=missing):
            forward.load_completed_market_data({})
    else:
        actual, control = forward.load_completed_market_data({})
        assert actual.index.equals(dates)
        assert control.index.equals(dates)

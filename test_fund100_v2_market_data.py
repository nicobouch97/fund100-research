"""Offline as-of history ingestion tests; never connect to the broker."""

from datetime import date, timedelta

import pytest

from fund100_v2.market_data import (
    DatedAsset,
    DailyBar,
    observations_from_history,
    read_bars_csv,
)
from fund100_v2.universe import AssetObservation, UniversePolicy, select_universe


AS_OF = date(2026, 10, 9)


def catalog(symbol="SPY", **overrides):
    data = dict(
        symbol=symbol,
        asset_class="etf",
        observed_on=AS_OF,
        listed_on=date(2000, 1, 1),
        active=True,
        tradable=True,
    )
    data.update(overrides)
    return DatedAsset(**data)


def history(symbol="SPY", sessions=260, close=100.0, volume=100000.0):
    days = []
    day = AS_OF
    while len(days) < sessions:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return tuple(
        DailyBar(
            symbol=symbol,
            session=day,
            close_usd=close,
            volume_shares=volume,
            quoted_spread_bps=3.0,
        )
        for day in reversed(days)
    )


def test_ingests_valid_history_into_existing_universe_screen():
    rows = observations_from_history([catalog()], history(), as_of=AS_OF)
    assert len(rows) == 1
    row = rows[0]
    assert row.history_sessions == 260
    assert row.price_usd == 100.0
    assert row.avg_dollar_volume_20d_usd == pytest.approx(10_000_000)
    result = select_universe(rows, UniversePolicy(as_of=AS_OF))
    assert result.symbols == ("SPY",)


def test_trailing_liquidity_uses_last_20_sessions_not_full_history():
    bars = list(history())
    bars[-1] = DailyBar("SPY", AS_OF, 200.0, 100000.0, 3.0)
    result = observations_from_history([catalog()], bars, as_of=AS_OF)
    assert result[0].avg_dollar_volume_20d_usd == pytest.approx(
        (19 * 10_000_000 + 20_000_000) / 20
    )


def test_catalog_order_does_not_affect_output():
    a = catalog("SPY")
    b = catalog("AAPL", asset_class="equity")
    rows = history("AAPL") + history("SPY")
    first = observations_from_history([a, b], rows, as_of=AS_OF)
    second = observations_from_history([b, a], reversed(rows), as_of=AS_OF)
    assert first == second


def test_csv_loader_accepts_expected_schema(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
        "SPY,2026-10-09,100,120000,3.5\n", encoding="utf-8"
    )
    assert read_bars_csv(path, as_of=AS_OF) == (
        DailyBar("SPY", AS_OF, 100.0, 120000.0, 3.5),
    )


@pytest.mark.parametrize(
    "csv_text,error",
    [
        ("symbol,date,price,volume_shares,quoted_spread_bps\n", "schema"),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
            "SPY,2026-10-10,100,1000,3\n",
            "Future",
        ),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
            "SPY,2026-10-09,nan,1000,3\n",
            "Invalid",
        ),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
            "SPY,2026-10-09,100,-10,3\n",
            "Invalid",
        ),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
            "SPY,2026-10-09,100,1000,-3\n",
            "Invalid",
        ),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n"
            "spy,2026-10-09,100,1000,3\n",
            "Invalid symbol",
        ),
        (
            "symbol,date,close_usd,volume_shares,quoted_spread_bps\n",
            "Empty",
        ),
    ],
)
def test_csv_input_fails_closed(tmp_path, csv_text, error):
    path = tmp_path / "bars.csv"
    path.write_text(csv_text, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        read_bars_csv(path, as_of=AS_OF)


def test_future_daily_bar_rejected_even_if_series_has_valid_history():
    bars = list(history())
    bars.append(DailyBar("SPY", date(2026, 10, 12), 101, 100000, 3))
    with pytest.raises(ValueError, match="Future"):
        observations_from_history([catalog()], bars, as_of=AS_OF)


def test_duplicate_daily_bar_rejected():
    bars = list(history())
    bars.append(bars[-1])
    with pytest.raises(ValueError, match="Duplicate"):
        observations_from_history([catalog()], bars, as_of=AS_OF)


def test_duplicate_catalog_entry_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        observations_from_history(
            [catalog(), catalog()], history(), as_of=AS_OF
        )


def test_unknown_symbol_bar_rejected():
    bars = list(history())
    bars.append(DailyBar("UNKNOWN", AS_OF, 40, 100000, 3))
    with pytest.raises(ValueError, match="without catalog"):
        observations_from_history([catalog()], bars, as_of=AS_OF)


def test_missing_history_aborts_whole_batch():
    with pytest.raises(ValueError, match="insufficient bars"):
        observations_from_history(
            [catalog("SPY"), catalog("QQQ")], history("SPY"), as_of=AS_OF
        )


def test_future_catalog_state_rejected():
    future = catalog(observed_on=date(2026, 10, 10))
    with pytest.raises(ValueError, match="future"):
        observations_from_history([future], history(), as_of=AS_OF)


def test_bar_predating_listing_rejected():
    recently_listed = catalog(listed_on=date(2026, 1, 1))
    with pytest.raises(ValueError, match="before listing"):
        observations_from_history([recently_listed], history(), as_of=AS_OF)


def test_sparse_history_cannot_forge_20d_liquidity():
    bars = tuple(
        DailyBar(
            "SPY", AS_OF - timedelta(days=i * 5), 100.0, 100000.0, 3
        )
        for i in range(20)
    )
    with pytest.raises(ValueError, match="gaps"):
        observations_from_history([catalog()], bars, as_of=AS_OF)


def test_combined_availability_does_not_backdate_catalog():
    rows = observations_from_history(
        [catalog()], history()[:-5], as_of=AS_OF
    )
    assert rows[0].observed_on == AS_OF
    # The independent ten-day bar-age gate enforces market freshness.
    # observed_on represents combined availability, not the last bar date.


def test_catalog_freshness_cannot_mask_stale_market_session():
    # 3 October bar / 9 October catalog: ten-day ingestion permits it,
    # but a one-day downstream market freshness policy must reject it.
    bars = tuple(b for b in history() if b.session <= date(2026, 10, 3))
    rows = observations_from_history([catalog(observed_on=AS_OF)], bars, as_of=AS_OF)
    assert rows[0].observed_on == AS_OF
    assert rows[0].market_session_on == date(2026, 10, 2)
    result = select_universe(
        rows, UniversePolicy(as_of=AS_OF, max_observation_age_days=1)
    )
    assert result.symbols == ()
    assert "market_price_bar_missing_stale_or_future" in result.rejected[0].reasons


def test_recent_market_session_passes_independent_freshness():
    bars = tuple(b for b in history() if b.session <= date(2026, 10, 8))
    rows = observations_from_history([catalog()], bars, as_of=AS_OF)
    assert rows[0].market_session_on == date(2026, 10, 8)
    result = select_universe(
        rows, UniversePolicy(as_of=AS_OF, max_observation_age_days=1)
    )
    assert result.symbols == ("SPY",)


def test_module_never_returns_executable_order_payload():
    rows = observations_from_history([catalog()], history(), as_of=AS_OF)
    assert not hasattr(rows[0], "orders")
    assert not hasattr(rows[0], "target_weights")
    assert not hasattr(rows[0], "broker_write_mode")


def test_old_but_contiguous_20_bar_window_is_rejected():
    # A complete historical window must not masquerade as current liquidity.
    old_bars = tuple(
        DailyBar(b.symbol, b.session - timedelta(days=30), b.close_usd,
                 b.volume_shares, b.quoted_spread_bps)
        for b in history()
    )
    with pytest.raises(ValueError, match="stale"):
        observations_from_history([catalog()], old_bars, as_of=AS_OF)


def test_recent_weekend_lag_is_accepted():
    bars = tuple(b for b in history() if b.session <= AS_OF - timedelta(days=3))
    rows = observations_from_history([catalog()], bars, as_of=AS_OF)
    assert rows[0].price_usd == 100.0


def test_catalog_observed_after_market_bar_cannot_be_backdated():
    bars = tuple(b for b in history() if b.session <= date(2026, 10, 6))
    rows = observations_from_history(
        [catalog(observed_on=date(2026, 10, 9))], bars, as_of=AS_OF
    )
    assert rows[0].observed_on == date(2026, 10, 9)
    result = select_universe(rows, UniversePolicy(as_of=date(2026, 10, 7)))
    assert result.symbols == ()
    assert "market_snapshot_missing_stale_or_future" in result.rejected[0].reasons


def test_strict_pit_rejects_missing_market_session_without_broker_access():
    row = observations_from_history([catalog()], history(), as_of=AS_OF)[0]
    legacy = AssetObservation(**{
        **row.__dict__, "market_session_on": None,
    })
    strict = UniversePolicy(as_of=AS_OF, require_market_session=True)
    result = select_universe([legacy], strict)
    assert result.symbols == ()
    assert "market_price_bar_missing_stale_or_future" in result.rejected[0].reasons
    # Explicit legacy mode remains available but is not PIT certified.
    assert select_universe([legacy], UniversePolicy(as_of=AS_OF)).symbols == ("SPY",)


def test_strict_pit_accepts_real_recent_bar_and_rejects_stale_bar():
    row = observations_from_history([catalog()], history(), as_of=AS_OF)[0]
    strict = UniversePolicy(as_of=AS_OF, max_observation_age_days=1,
                            require_market_session=True)
    assert select_universe([row], strict).symbols == ("SPY",)
    stale = AssetObservation(**{
        **row.__dict__, "market_session_on": AS_OF - timedelta(days=3),
    })
    result = select_universe([stale], strict)
    assert result.symbols == ()
    assert "market_price_bar_missing_stale_or_future" in result.rejected[0].reasons


def test_pit_policy_validation_and_fingerprint_binding():
    with pytest.raises(ValueError, match="boolean"):
        UniversePolicy(as_of=AS_OF, require_market_session="true")
    row = observations_from_history([catalog()], history(), as_of=AS_OF)[0]
    legacy = select_universe([row], UniversePolicy(as_of=AS_OF))
    strict = select_universe([row], UniversePolicy(as_of=AS_OF,
                                                 require_market_session=True))
    assert legacy.symbols == strict.symbols
    assert legacy.selection_sha256 != strict.selection_sha256


def test_strict_pit_rejects_market_bar_before_listing_date():
    row = observations_from_history([catalog()], history(), as_of=AS_OF)[0]
    impossible = AssetObservation(**{
        **row.__dict__, "listed_on": AS_OF - timedelta(days=1),
        "market_session_on": AS_OF - timedelta(days=2),
    })
    result = select_universe([impossible], UniversePolicy(
        as_of=AS_OF, require_market_session=True,
    ))
    assert result.symbols == ()
    assert "market_price_bar_missing_stale_or_future" in result.rejected[0].reasons


def test_strict_pit_rejects_future_market_session_even_with_current_catalog():
    # A manually assembled observation cannot use tomorrow's closing price.
    row = observations_from_history([catalog()], history(), as_of=AS_OF)[0]
    future = AssetObservation(**{
        **row.__dict__, "market_session_on": AS_OF + timedelta(days=1),
    })
    result = select_universe([future], UniversePolicy(
        as_of=AS_OF, require_market_session=True,
    ))
    assert result.symbols == ()
    assert "market_price_bar_missing_stale_or_future" in result.rejected[0].reasons

"""No broker dependency; V2 asset screening can only return research symbols."""

from dataclasses import replace
from datetime import date

import pytest

from fund100_v2.universe import (
    AssetObservation,
    UniversePolicy,
    select_universe,
)


AS_OF = date(2026, 10, 9)


def policy(**overrides):
    base = dict(as_of=AS_OF)
    base.update(overrides)
    return UniversePolicy(**base)


def asset(symbol="SPY", **overrides):
    base = dict(
        symbol=symbol,
        asset_class="etf",
        observed_on=AS_OF,
        listed_on=date(2000, 1, 1),
        active=True,
        tradable=True,
        price_usd=500.0,
        avg_dollar_volume_20d_usd=100_000_000.0,
        quoted_spread_bps=2.0,
        history_sessions=4000,
        fractionable=True,
    )
    base.update(overrides)
    return AssetObservation(**base)


def test_liquid_equity_and_etf_research_candidates():
    result = select_universe(
        [asset("SPY"), asset("AAPL", asset_class="equity")],
        policy(),
    )
    assert result.symbols == ("AAPL", "SPY")
    assert result.rejected == ()
    assert len(result.selection_sha256) == 64


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"asset_class": "crypto"}, "unsupported_asset_class"),
        ({"asset_class": "option"}, "unsupported_asset_class"),
        ({"active": False}, "not_active_and_tradable"),
        ({"tradable": False}, "not_active_and_tradable"),
        ({"price_usd": 1.0}, "price_below_floor_or_invalid"),
        ({"price_usd": float("nan")}, "price_below_floor_or_invalid"),
        ({"avg_dollar_volume_20d_usd": 1_000}, "liquidity_below_floor_or_invalid"),
        ({"quoted_spread_bps": 60}, "spread_above_limit_or_invalid"),
        ({"quoted_spread_bps": float("inf")}, "spread_above_limit_or_invalid"),
        ({"history_sessions": 100}, "insufficient_usable_history"),
        ({"history_sessions": True}, "insufficient_usable_history"),
        ({"observed_on": date(2026, 10, 10)}, "market_snapshot_missing_stale_or_future"),
        ({"observed_on": date(2026, 10, 1)}, "market_snapshot_missing_stale_or_future"),
        ({"listed_on": date(2026, 10, 10)}, "listing_not_verified_as_of"),
        ({"symbol": "AAPL/USDT"}, "invalid_symbol"),
    ],
)
def test_research_screen_fails_closed(changes, reason):
    result = select_universe([asset(**changes)], policy())
    assert result.symbols == ()
    assert reason in result.rejected[0].reasons


def test_duplicate_symbols_stop_ambiguous_ingest():
    with pytest.raises(ValueError, match="duplicate"):
        select_universe([asset("SPY"), asset("SPY", price_usd=499)], policy())


def test_result_is_deterministic_under_input_shuffle():
    a = asset("SPY", avg_dollar_volume_20d_usd=100_000_000)
    b = asset("AAPL", asset_class="equity", avg_dollar_volume_20d_usd=120_000_000)
    c = asset("PENNY", price_usd=0.5)
    first = select_universe([a, b, c], policy())
    second = select_universe([c, b, a], policy())
    assert first == second


def test_liquidity_capacity_limit_is_audited():
    result = select_universe(
        [
            asset("AAA", avg_dollar_volume_20d_usd=200_000_000),
            asset("BBB", avg_dollar_volume_20d_usd=150_000_000),
        ],
        policy(max_symbols=1),
    )
    assert result.symbols == ("AAA",)
    assert result.rejected[0].reasons == ("research_capacity_limit",)


def test_changed_policy_changes_reproducibility_fingerprint():
    rows = [asset()]
    before = select_universe(rows, policy())
    after = select_universe(rows, policy(max_quoted_spread_bps=30.0))
    assert before.symbols == after.symbols
    assert before.selection_sha256 != after.selection_sha256


def test_weekend_eligibility_is_calendar_age_based():
    monday = date(2026, 10, 12)
    result = select_universe(
        [asset(observed_on=date(2026, 10, 9))],
        UniversePolicy(as_of=monday),
    )
    assert result.symbols == ("SPY",)


@pytest.mark.parametrize(
    "bad_policy",
    [
        {"allowed_asset_classes": ("equity", "crypto")},
        {"allowed_asset_classes": ()},
        {"allowed_asset_classes": ("etf", "etf")},
        {"max_symbols": 0},
        {"max_observation_age_days": -1},
        {"min_price_usd": float("nan")},
        {"min_avg_dollar_volume_20d_usd": 0},
    ],
)
def test_reject_invalid_screen_policy(bad_policy):
    with pytest.raises(ValueError):
        policy(**bad_policy)


def test_no_target_weights_or_execution_fields_exposed():
    result = select_universe([asset()], policy())
    assert result.symbols == ("SPY",)
    assert not hasattr(result, "target_weights")
    assert not hasattr(result, "orders")
    assert not hasattr(result, "live_execution_authorized")


def test_empty_universe_is_valid_no_op():
    result = select_universe([], policy())
    assert result.symbols == ()
    assert result.rejected == ()


def test_fractional_trading_flag_not_treated_as_live_permission():
    result = select_universe([asset(fractionable=False)], policy())
    assert result.symbols == ("SPY",)

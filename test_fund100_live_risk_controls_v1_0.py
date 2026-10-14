"""Offline tests: no broker credentials or network calls required."""

from decimal import Decimal

import pytest

from fund100_live_risk_controls_v1_0 import (
    RiskControlStop,
    enforce_event_budget,
    resolve_risk_budget,
)


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("LOW", "32.57"),
        ("medium", "65.15"),
        ("HIGH", "130.30"),
        (" high ", "130.30"),
    ],
)
def test_risk_tiers_are_bounded_by_frozen_pilot_cap(level, expected):
    result = resolve_risk_budget(
        level=level,
        pilot_capital_ceiling=Decimal("130.30"),
    )
    assert result == Decimal(expected)


@pytest.mark.parametrize("level", ["", " ", "OFF", "MAX", "0", None])
def test_risk_level_must_be_explicit(level):
    with pytest.raises(RiskControlStop):
        resolve_risk_budget(
            level=level,
            pilot_capital_ceiling=Decimal("130.30"),
        )


@pytest.mark.parametrize("cap", ["0", "-1", "NaN", "Infinity", "oops"])
def test_bad_pilot_ceiling_fails_closed(cap):
    with pytest.raises(RiskControlStop):
        resolve_risk_budget(level="LOW", pilot_capital_ceiling=cap)


def test_gross_event_budget_includes_buys_and_sells():
    orders = [
        {"side": "sell", "notional_usd": "16.50"},
        {"side": "buy", "notional_usd": "16.00"},
    ]
    assert enforce_event_budget(
        orders=orders, risk_budget=Decimal("32.57")
    ) == Decimal("32.50")


def test_gross_event_over_risk_budget_fails_closed():
    orders = [
        {"side": "sell", "notional_usd": "20.00"},
        {"side": "buy", "notional_usd": "20.00"},
    ]
    with pytest.raises(RiskControlStop):
        enforce_event_budget(
            orders=orders, risk_budget=Decimal("32.57")
        )


@pytest.mark.parametrize(
    "order",
    [
        {"side": "buy", "notional_usd": "NaN"},
        {"side": "buy", "notional_usd": "-1"},
        {"side": "buy", "notional_usd": "0"},
        {"side": "sell", "notional_usd": "Infinity"},
        {"side": "short", "notional_usd": "10"},
        {"side": "buy"},
    ],
)
def test_invalid_orders_fail_closed(order):
    with pytest.raises(RiskControlStop):
        enforce_event_budget(
            orders=[order], risk_budget=Decimal("130.30")
        )


def test_empty_event_is_safe_and_no_order():
    assert enforce_event_budget(
        orders=[], risk_budget=Decimal("32.57")
    ) == Decimal("0")

"""Fail-closed risk-tier budget for the Fund-100 LIVE micro-pilot.

This caps the gross notional of a single authorized strategy event.
It does not claim to enforce drawdown, volatility or portfolio exposure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN


class RiskControlStop(RuntimeError):
    """An invalid or over-budget LIVE trade must not proceed."""


RISK_FRACTIONS = {
    "LOW": Decimal("0.25"),
    "MEDIUM": Decimal("0.50"),
    "HIGH": Decimal("1.00"),
}

_CENTS = Decimal("0.01")


def resolve_risk_budget(*, level: str, pilot_capital_ceiling: Decimal) -> Decimal:
    """Return maximum total event notional under the fixed pilot ceiling."""
    normalized = str(level or "").strip().upper()

    if normalized not in RISK_FRACTIONS:
        raise RiskControlStop(
            "FUND100_RISK_LEVEL must explicitly be LOW, MEDIUM, or HIGH."
        )

    try:
        pilot_cap = Decimal(str(pilot_capital_ceiling))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskControlStop("Invalid pilot capital ceiling.") from exc

    if not pilot_cap.is_finite() or pilot_cap <= 0:
        raise RiskControlStop("Pilot capital ceiling must be finite and positive.")

    budget = (pilot_cap * RISK_FRACTIONS[normalized]).quantize(
        _CENTS, rounding=ROUND_DOWN
    )

    if budget <= 0 or budget > pilot_cap:
        raise RiskControlStop("Resolved risk budget is invalid.")

    return budget


def enforce_event_budget(*, orders: list[dict], risk_budget: Decimal) -> Decimal:
    """Validate every proposed order and return its aggregate gross notional."""
    try:
        budget = Decimal(str(risk_budget))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskControlStop("Invalid risk budget.") from exc

    if not budget.is_finite() or budget <= 0:
        raise RiskControlStop("Risk budget must be finite and positive.")

    if not isinstance(orders, list):
        raise RiskControlStop("Orders must be a list.")

    total = Decimal("0")

    for order in orders:
        if not isinstance(order, dict):
            raise RiskControlStop("Order must be an object.")
        if order.get("side") not in ("buy", "sell"):
            raise RiskControlStop("Order side must be buy or sell.")

        try:
            notional = Decimal(str(order["notional_usd"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            raise RiskControlStop("Order notional is missing or invalid.") from exc

        if not notional.is_finite() or notional <= 0:
            raise RiskControlStop("Order notional must be finite and positive.")

        total += notional

        if total > budget:
            raise RiskControlStop(
                "Planned event gross notional exceeds selected risk tier."
            )

    return total

"""Fail-closed portfolio-level guardrails for the Fund-100 LIVE pilot.

LOW/MEDIUM/HIGH are constraints on exposure, concentration and account
loss/volatility. They are NOT return forecasts or promises that losses
cannot exceed the thresholds. Trade-size control remains independent.

No broker access on import; all broker data is injected into functions.
No account balance, positions or portfolio history is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import stdev
from time import time


class PortfolioRiskStop(RuntimeError):
    """Fail closed on missing inputs or breached portfolio limits."""


@dataclass(frozen=True)
class RiskProfile:
    name: str
    max_gross_exposure: Decimal
    max_acwi_core_weight: Decimal
    max_satellite_weight: Decimal
    max_daily_loss: Decimal
    max_rolling_drawdown: Decimal
    max_realized_volatility: Decimal


PROFILES = {
    "LOW": RiskProfile(
        "LOW", Decimal("0.80"), Decimal("0.80"), Decimal("0.10"),
        Decimal("0.020"), Decimal("0.050"), Decimal("0.12")
    ),
    "MEDIUM": RiskProfile(
        "MEDIUM", Decimal("0.90"), Decimal("0.80"), Decimal("0.15"),
        Decimal("0.035"), Decimal("0.100"), Decimal("0.20")
    ),
    "HIGH": RiskProfile(
        "HIGH", Decimal("1.00"), Decimal("0.80"), Decimal("0.25"),
        Decimal("0.060"), Decimal("0.200"), Decimal("0.35")
    ),
}

MIN_OBSERVATIONS = 6  # at least five daily returns, until a longer track record exists
MAX_HISTORY_OBSERVATIONS = 70
MAX_DAILY_RETURN_MAGNITUDE = Decimal("0.25")
# 30-day window; this is a rolling drawdown guard, NOT lifetime drawdown.


def finite_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise PortfolioRiskStop(f"Missing/invalid {label}.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PortfolioRiskStop(f"Missing/invalid {label}.") from exc
    if not result.is_finite():
        raise PortfolioRiskStop(f"Non-finite {label}.")
    return result


def get_profile(level: object) -> RiskProfile:
    if not isinstance(level, str) or level.strip().upper() not in PROFILES:
        raise PortfolioRiskStop("Risk level must explicitly be LOW, MEDIUM or HIGH.")
    return PROFILES[level.strip().upper()]


def check_projected_allocation(
    *, target_weights: dict, profile: RiskProfile
) -> None:
    """Prevent a new event whose FINAL weights violate tier concentration."""
    if not isinstance(target_weights, dict) or not target_weights:
        raise PortfolioRiskStop("Missing target portfolio weights.")

    gross = Decimal("0")
    for symbol, raw_weight in target_weights.items():
        if not isinstance(symbol, str) or not symbol.isupper():
            raise PortfolioRiskStop("Invalid target symbol.")
        weight = finite_decimal(raw_weight, "target weight")
        if weight < 0:
            raise PortfolioRiskStop("Shorting is forbidden.")
        limit = (
            profile.max_acwi_core_weight
            if symbol == "ACWI"
            else profile.max_satellite_weight
        )
        if weight > limit:
            raise PortfolioRiskStop(f"{symbol} concentration exceeds selected risk tier.")
        gross += weight

    if gross > profile.max_gross_exposure:
        raise PortfolioRiskStop("Target gross exposure exceeds selected risk tier.")


def check_actual_exposure(
    *, positions: dict, equity: object, capital_ceiling: object,
    profile: RiskProfile
) -> None:
    """Guard existing exposure using broker market values and restricted NAV."""
    nav = finite_decimal(equity, "account equity")
    cap = finite_decimal(capital_ceiling, "pilot capital ceiling")
    if nav <= 0 or cap <= 0 or not isinstance(positions, dict):
        raise PortfolioRiskStop("Invalid LIVE portfolio exposure inputs.")
    deployable_nav = min(nav, cap)
    gross = Decimal("0")

    for symbol, details in positions.items():
        if not isinstance(details, dict) or not isinstance(symbol, str):
            raise PortfolioRiskStop("Invalid LIVE position.")
        value = finite_decimal(details.get("market_value"), "position market value")
        if value < 0:
            raise PortfolioRiskStop("Negative position value / short detected.")
        weight = value / deployable_nav
        limit = (
            profile.max_acwi_core_weight
            if symbol == "ACWI"
            else profile.max_satellite_weight
        )
        # A small market-move tolerance is intentionally NOT used:
        # breaches must fail closed rather than silently permit more buying.
        if weight > limit:
            raise PortfolioRiskStop(f"{symbol} current concentration exceeds tier.")
        gross += value

    if gross / deployable_nav > profile.max_gross_exposure:
        raise PortfolioRiskStop("Existing gross exposure exceeds selected risk tier.")


def validated_equity_history(response: object) -> list[Decimal]:
    """Validate Alpaca portfolio-history 1D shape; reject data quality gaps."""
    if not isinstance(response, dict) or response.get("timeframe") != "1D":
        raise PortfolioRiskStop("Daily portfolio history unavailable.")
    timestamps = response.get("timestamp")
    equities = response.get("equity")
    if not isinstance(timestamps, list) or not isinstance(equities, list):
        raise PortfolioRiskStop("Malformed portfolio history.")
    if len(timestamps) != len(equities) or len(equities) > MAX_HISTORY_OBSERVATIONS:
        raise PortfolioRiskStop("Incomplete or oversized portfolio history.")

    funded = []
    last_timestamp = None
    seen_positive = False
    for timestamp, value in zip(timestamps, equities):
        if type(timestamp) is not int or timestamp <= 0:
            raise PortfolioRiskStop("Invalid history timestamp.")
        if last_timestamp is not None and timestamp <= last_timestamp:
            raise PortfolioRiskStop("Non-monotonic account history.")
        last_timestamp = timestamp
        if value is None and not seen_positive:
            continue
        if value is None:
            raise PortfolioRiskStop("Missing funded account history.")
        equity = finite_decimal(value, "historical equity")
        if equity <= 0:
            if seen_positive:
                raise PortfolioRiskStop("Zero/negative equity during funded history.")
            continue
        seen_positive = True
        funded.append(equity)

    if len(funded) < MIN_OBSERVATIONS:
        raise PortfolioRiskStop("Insufficient funded daily portfolio history.")
    # Don't accept a disconnected/stale broker history as live risk evidence.
    current_timestamp = int(time())
    if last_timestamp is None or not (
        current_timestamp - 10 * 86400 <= last_timestamp <= current_timestamp + 3600
    ):
        raise PortfolioRiskStop("Portfolio history is stale or future-dated.")
    return funded


def check_account_performance(
    *, account: dict, history: object, profile: RiskProfile
) -> None:
    """Enforce daily loss, rolling equity drawdown and realized volatility.

    Cashflows can distort the broker's unadjusted daily equity series.
    Large changes are rejected rather than assumed to be returns.
    """
    if not isinstance(account, dict):
        raise PortfolioRiskStop("Malformed broker account.")
    current = finite_decimal(account.get("equity"), "current equity")
    previous = finite_decimal(account.get("last_equity"), "previous close equity")
    if current <= 0 or previous <= 0:
        raise PortfolioRiskStop("Invalid account equity for loss controls.")

    daily_return = current / previous - Decimal("1")
    if abs(daily_return) > MAX_DAILY_RETURN_MAGNITUDE:
        raise PortfolioRiskStop("Daily equity move/cashflow ambiguity exceeds 25%.")
    if daily_return < -profile.max_daily_loss:
        raise PortfolioRiskStop("Account daily-loss circuit breaker triggered.")

    equities = validated_equity_history(history)
    # Latest LIVE equity must be included; broker daily history may lag.
    if abs(equities[-1] / current - Decimal("1")) > Decimal("0.25"):
        raise PortfolioRiskStop("Current account/history equity materially diverged.")
    equities.append(current)

    returns = []
    for older, newer in zip(equities, equities[1:]):
        change = newer / older - Decimal("1")
        if abs(change) > MAX_DAILY_RETURN_MAGNITUDE:
            raise PortfolioRiskStop("History contains probable cashflow/outlier.")
        returns.append(float(change))

    peak = max(equities)
    drawdown = Decimal("1") - current / peak
    if drawdown > profile.max_rolling_drawdown:
        raise PortfolioRiskStop("Rolling account drawdown limit breached.")

    realized_vol = Decimal(str(stdev(returns) * sqrt(252)))
    if realized_vol > profile.max_realized_volatility:
        raise PortfolioRiskStop("Realized account volatility ceiling breached.")


def check_portfolio_risk(
    *, snapshot: dict, target_weights: dict, capital_ceiling: object,
    history: object, level: str
) -> None:
    profile = get_profile(level)
    if not isinstance(snapshot, dict):
        raise PortfolioRiskStop("Invalid broker snapshot.")
    check_projected_allocation(target_weights=target_weights, profile=profile)
    check_actual_exposure(
        positions=snapshot.get("positions"),
        equity=snapshot.get("equity"),
        capital_ceiling=capital_ceiling,
        profile=profile,
    )
    check_account_performance(
        account=snapshot.get("account"),
        history=history,
        profile=profile,
    )

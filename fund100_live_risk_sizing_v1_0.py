"""Deterministic risk-aware allocation overlay; no broker I/O.

The optimizer only SHRINKS a frozen strategy's long-only weights and
leaves unassigned NAV in cash. It cannot open new symbols, increase any
target weight, short, or enable leverage. It must not turn a risk overlay
into an unreviewed signal generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from math import sqrt
from statistics import stdev

from fund100_live_portfolio_risk_v1_0 import (
    PortfolioRiskStop,
    RiskProfile,
    check_projected_allocation,
    finite_decimal,
    get_profile,
    validated_equity_history,
)

# Tentative sizing objectives, strictly BELOW the hard rejection ceilings.
VOLATILITY_TARGETS = {
    "LOW": Decimal("0.10"),
    "MEDIUM": Decimal("0.16"),
    "HIGH": Decimal("0.28"),
}
ROUND_WEIGHTS = Decimal("0.000000000001")


@dataclass(frozen=True)
class SizingPlan:
    profile: str
    weights: dict[str, Decimal]
    uninvested_weight: Decimal
    scale_factor: Decimal
    volatility_target: Decimal



def estimate_observed_volatility(*, history: object, equity: object) -> Decimal:
    """Measure equity-return volatility from validated recent broker data.

    Missing/stale history, potential deposits or unbounded daily returns
    DENY sizing rather than silently select maximum leverage.
    """
    values = validated_equity_history(history)
    current = finite_decimal(equity, "current equity")
    if current <= 0:
        raise PortfolioRiskStop("Invalid current equity.")
    if abs(values[-1] / current - Decimal("1")) > Decimal("0.25"):
        raise PortfolioRiskStop("Equity and portfolio history diverge.")

    samples = values + [current]
    returns = []
    for previous, latest in zip(samples, samples[1:]):
        change = latest / previous - Decimal("1")
        if abs(change) > Decimal("0.25"):
            raise PortfolioRiskStop("Ambiguous portfolio cashflow in volatility.")
        returns.append(float(change))

    return Decimal(str(stdev(returns) * sqrt(252)))


def size_strategy_targets(
    *,
    strategy_targets: dict,
    risk_level: str,
    observed_annualized_volatility: object,
) -> SizingPlan:
    """Conservatively shrink ALL strategy exposures by a common factor.

    Scaling by a single multiplier preserves the strategy's relative
    ranking and directions. Cash absorbs any clipped exposure.
    """
    profile: RiskProfile = get_profile(risk_level)
    if not isinstance(strategy_targets, dict) or not strategy_targets:
        raise PortfolioRiskStop("Strategy targets are missing.")
    clean: dict[str, Decimal] = {}
    for symbol, value in strategy_targets.items():
        if not isinstance(symbol, str) or not symbol.isupper():
            raise PortfolioRiskStop("Invalid strategy symbol.")
        weight = finite_decimal(value, "strategy target weight")
        if weight < 0:
            raise PortfolioRiskStop("Short strategy targets are forbidden.")
        clean[symbol] = weight

    total = sum(clean.values(), Decimal("0"))
    if total <= 0 or total > Decimal("1.002"):
        raise PortfolioRiskStop("Invalid gross strategy target.")
    volatility = finite_decimal(
        observed_annualized_volatility, "observed annualised volatility"
    )
    if volatility < 0:
        raise PortfolioRiskStop("Negative observed volatility.")

    target_vol = VOLATILITY_TARGETS[profile.name]
    scale = min(Decimal("1"), profile.max_gross_exposure / total)

    # A portfolio at zero observed volatility needs no vol-driven shrink.
    if volatility:
        scale = min(scale, target_vol / volatility)

    for symbol, weight in clean.items():
        if weight:
            cap = (
                profile.max_acwi_core_weight
                if symbol == "ACWI"
                else profile.max_satellite_weight
            )
            scale = min(scale, cap / weight)

    if scale <= 0 or scale > 1:
        raise PortfolioRiskStop("Invalid strategy scaling factor.")

    sized = {
        symbol: (weight * scale).quantize(
            ROUND_WEIGHTS, rounding=ROUND_DOWN
        )
        for symbol, weight in sorted(clean.items())
    }
    check_projected_allocation(target_weights=sized, profile=profile)
    remaining = Decimal("1") - sum(sized.values(), Decimal("0"))
    if remaining < 0:
        raise PortfolioRiskStop("Risk sizing produced leverage.")
    return SizingPlan(
        profile=profile.name,
        weights=sized,
        uninvested_weight=remaining,
        scale_factor=scale,
        volatility_target=target_vol,
    )


def verify_existing_strategy_authorizations(
    *,
    sized_weights: dict[str, Decimal],
    positions: dict,
    deployable_nav: object,
    compiler_candidates: dict,
    tolerance_usd: Decimal = Decimal("0.50"),
) -> None:
    """Fail closed if the risk overlay creates a trade the compiler didn't sign.

    For each material target change there MUST be a compiler-authored
    candidate with the matching side. DO NOT manufacture client IDs.
    """
    nav = finite_decimal(deployable_nav, "deployable NAV")
    if nav <= 0 or not isinstance(positions, dict):
        raise PortfolioRiskStop("Invalid broker portfolio.")
    if not isinstance(compiler_candidates, dict):
        raise PortfolioRiskStop("Missing compiler candidates.")

    for symbol in set(sized_weights) | set(positions):
        details = positions.get(symbol, {})
        if not isinstance(details, dict):
            raise PortfolioRiskStop("Malformed broker position.")
        current = finite_decimal(
            details.get("market_value", "0"), "position value"
        )
        desired = sized_weights.get(symbol, Decimal("0")) * nav
        delta = desired - current
        if abs(delta) <= tolerance_usd:
            continue

        candidate = compiler_candidates.get(symbol)
        side = "buy" if delta > 0 else "sell"
        if not isinstance(candidate, dict) or candidate.get("side") != side:
            raise PortfolioRiskStop(
                "Risk-sized portfolio requires an unsigned order; "
                "compiler authorisation missing."
            )
        if not isinstance(candidate.get("client_order_id"), str):
            raise PortfolioRiskStop("Missing deterministic client order ID.")

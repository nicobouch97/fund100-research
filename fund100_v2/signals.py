"""Fund-100 V2 signal families: entirely offline *research diagnostics*.

Adjusted total-return-like close series and historically valid eligibility
must be supplied by a trusted data-preparation stage. In particular the
unadjusted `market_data.DailyBar.close_usd` must NOT be directly used to
measure historical returns without corporate-action adjustment.

No trading account, broker permissions, allocation, or order route exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import re
from statistics import pstdev
from types import MappingProxyType
from typing import Mapping, Sequence


RESEARCH_FAMILIES = (
    "medium_momentum",
    "short_reversal",
    "risk_scaled_trend",
)
REQUIRED_LOOKBACK = 60
_SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9.\-]{0,13}\Z")


@dataclass(frozen=True)
class ResearchPanel:
    """Synchronized dated adjusted prices, historical spreads and membership.

    Price observations must be corporate-action-adjusted and comparable for
    returns. Each eligible_symbols entry describes membership known on that
    *same* session; future eligibility must never influence past decisions.
    """

    sessions: tuple[date, ...]
    adjusted_prices: Mapping[str, Sequence[float]]
    spread_bps: Mapping[str, Sequence[float]]
    eligible_symbols: tuple[frozenset[str], ...]

    def __post_init__(self) -> None:
        days = tuple(self.sessions)
        if len(days) < REQUIRED_LOOKBACK + 4:
            raise ValueError("Insufficient synchronized research sessions")
        if any(not isinstance(day, date) or day.weekday() >= 5 for day in days):
            raise ValueError("Equity research sessions must be weekday dates")
        if any(a >= b for a, b in zip(days, days[1:])):
            raise ValueError("Research sessions must be strictly increasing")

        prices = {name: tuple(values) for name, values in self.adjusted_prices.items()}
        spreads = {name: tuple(values) for name, values in self.spread_bps.items()}
        if not prices or set(prices) != set(spreads):
            raise ValueError("Price and spread universes must be identical")
        if any(not isinstance(name, str) or not _SYMBOL_PATTERN.fullmatch(name)
               for name in prices):
            raise ValueError("Invalid research symbol")

        for sym in prices:
            if len(prices[sym]) != len(days) or len(spreads[sym]) != len(days):
                raise ValueError("Every symbol needs a complete dated price/spread grid")
            for price in prices[sym]:
                if not _positive_finite(price):
                    raise ValueError("Invalid or non-finite adjusted price")
            for spread in spreads[sym]:
                if not _nonnegative_finite(spread):
                    raise ValueError("Invalid or non-finite quoted spread")

        membership = tuple(frozenset(x) for x in self.eligible_symbols)
        if len(membership) != len(days):
            raise ValueError("Historical eligibility must cover every session")
        if any(not group.issubset(prices) for group in membership):
            raise ValueError("Eligibility contains unknown symbol")

        object.__setattr__(self, "sessions", days)
        object.__setattr__(self, "adjusted_prices", MappingProxyType(prices))
        object.__setattr__(self, "spread_bps", MappingProxyType(spreads))
        object.__setattr__(self, "eligible_symbols", membership)


def _nonnegative_finite(value: object) -> bool:
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return False
    return math.isfinite(number) and number >= 0


def _positive_finite(value: object) -> bool:
    return _nonnegative_finite(value) and float(value) > 0


def score_on_close(
    panel: ResearchPanel,
    family: str,
    index: int,
    symbol: str,
) -> float:
    """Score using closes at indices <= index; never consume future data."""
    if family not in RESEARCH_FAMILIES:
        raise ValueError("Unknown V2 research signal family")
    if not isinstance(index, int) or index < REQUIRED_LOOKBACK:
        raise ValueError("Signal requires 60 past sessions")
    if index >= len(panel.sessions) or symbol not in panel.adjusted_prices:
        raise ValueError("Invalid research signal index/symbol")
    prices = panel.adjusted_prices[symbol]

    if family == "medium_momentum":
        # 60-session momentum excluding the most recent 5 sessions.
        return prices[index - 5] / prices[index - 60] - 1.0

    if family == "short_reversal":
        # Hypothesized reversal of the last 5-session move.
        return 1.0 - prices[index] / prices[index - 5]

    # 20-session total return normalized by 20 daily-return observations.
    returns = [
        prices[t] / prices[t - 1] - 1.0
        for t in range(index - 19, index + 1)
    ]
    vol = pstdev(returns)
    raw = prices[index] / prices[index - 20] - 1.0
    # The research-only denominator floor keeps perfectly smooth
    # synthetic trends finite; it is not a risk/position-size limit.
    return raw / max(vol, 0.0001)


def top_research_candidate(
    panel: ResearchPanel,
    family: str,
    index: int,
) -> str | None:
    """Choose a single positive-score *research label*, or cash.

    This is not a trade signal or an approved portfolio position. No
    eligible member on a date => cash, not implicit forward-fill.
    """
    if family not in RESEARCH_FAMILIES:
        raise ValueError("Unknown V2 research signal family")
    if index < REQUIRED_LOOKBACK or index >= len(panel.sessions):
        raise ValueError("Research signal date out of range")

    names = sorted(panel.eligible_symbols[index])
    scores = [(score_on_close(panel, family, index, name), name)
              for name in names]
    if not scores:
        return None
    # Alphabetic tie-break is stable irrespective of dictionary ordering.
    best_score = max(score for score, _ in scores)
    if best_score <= 0:
        return None
    return min(name for score, name in scores if score == best_score)

"""Fund-100 V2 research-only, point-in-time candidate universe screen.

No broker client, secrets, orders, portfolio allocations, or LIVE eligibility.
A caller must supply historically correct asset observations as of `as_of`.
This screen cannot cure survivorship bias in the supplied vendor snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import math
import re
from typing import Iterable


SUPPORTED_CLASSES = frozenset({"equity", "etf"})
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,13}\Z")


@dataclass(frozen=True)
class AssetObservation:
    """Provider input, *not* permission to trade at the broker."""

    symbol: str
    asset_class: str
    observed_on: date
    listed_on: date
    active: bool
    tradable: bool
    price_usd: float
    avg_dollar_volume_20d_usd: float
    quoted_spread_bps: float
    history_sessions: int
    fractionable: bool = False


@dataclass(frozen=True)
class UniversePolicy:
    """Exploratory screening criteria; these are NOT trading risk limits."""

    as_of: date
    min_history_sessions: int = 252
    min_price_usd: float = 5.0
    min_avg_dollar_volume_20d_usd: float = 5_000_000.0
    max_quoted_spread_bps: float = 40.0
    max_observation_age_days: int = 5
    max_symbols: int = 250
    allowed_asset_classes: tuple[str, ...] = ("equity", "etf")

    def __post_init__(self) -> None:
        if not isinstance(self.as_of, date):
            raise ValueError("as_of must be a calendar date")
        if (
            not self.allowed_asset_classes
            or set(self.allowed_asset_classes) - SUPPORTED_CLASSES
            or len(set(self.allowed_asset_classes)) != len(self.allowed_asset_classes)
        ):
            raise ValueError("Only explicit US equity/ETF research is supported")
        if (
            self.min_history_sessions < 1
            or self.max_observation_age_days < 0
            or self.max_symbols < 1
            or not _finite_positive(self.min_price_usd)
            or not _finite_positive(self.min_avg_dollar_volume_20d_usd)
            or not _finite_positive(self.max_quoted_spread_bps)
        ):
            raise ValueError("Invalid V2 research universe policy")


@dataclass(frozen=True)
class RejectedAsset:
    symbol: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class UniverseResult:
    """Candidate symbols only. No target weights or executable instructions."""

    as_of: date
    symbols: tuple[str, ...]
    rejected: tuple[RejectedAsset, ...]
    selection_sha256: str


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _finite_nonnegative(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number >= 0


def _reasons(row: AssetObservation, policy: UniversePolicy) -> tuple[str, ...]:
    reasons: list[str] = []

    if not isinstance(row.symbol, str) or not _SYMBOL.fullmatch(row.symbol):
        reasons.append("invalid_symbol")
    if row.asset_class not in policy.allowed_asset_classes:
        reasons.append("unsupported_asset_class")
    if row.active is not True or row.tradable is not True:
        reasons.append("not_active_and_tradable")

    if not isinstance(row.listed_on, date) or row.listed_on > policy.as_of:
        reasons.append("listing_not_verified_as_of")
    if not isinstance(row.observed_on, date) or (
        row.observed_on > policy.as_of
        or (policy.as_of - row.observed_on).days > policy.max_observation_age_days
    ):
        reasons.append("market_snapshot_missing_stale_or_future")

    if not _finite_positive(row.price_usd) or (
        float(row.price_usd) < policy.min_price_usd
    ):
        reasons.append("price_below_floor_or_invalid")
    if not _finite_positive(row.avg_dollar_volume_20d_usd) or (
        float(row.avg_dollar_volume_20d_usd)
        < policy.min_avg_dollar_volume_20d_usd
    ):
        reasons.append("liquidity_below_floor_or_invalid")
    if not _finite_nonnegative(row.quoted_spread_bps) or (
        float(row.quoted_spread_bps) > policy.max_quoted_spread_bps
    ):
        reasons.append("spread_above_limit_or_invalid")
    if (
        not isinstance(row.history_sessions, int)
        or isinstance(row.history_sessions, bool)
        or row.history_sessions < policy.min_history_sessions
    ):
        reasons.append("insufficient_usable_history")

    return tuple(reasons)


def select_universe(
    observations: Iterable[AssetObservation],
    policy: UniversePolicy,
) -> UniverseResult:
    """Deterministic selection from supplied, dated observations only.

    Duplicate symbols are rejected as ambiguous instead of choosing a snapshot.
    A passing row is a *research candidate*, never LIVE broker authorisation.
    """
    if not isinstance(policy, UniversePolicy):
        raise TypeError("Explicit UniversePolicy required")

    rows = list(observations)
    symbols = [row.symbol for row in rows]
    if len(set(symbols)) != len(symbols):
        raise ValueError("Ambiguous duplicate asset observations")

    passed: list[AssetObservation] = []
    rejected: list[RejectedAsset] = []

    for row in sorted(rows, key=lambda item: item.symbol):
        reasons = _reasons(row, policy)
        if reasons:
            rejected.append(RejectedAsset(str(row.symbol), reasons))
        else:
            passed.append(row)

    # Liquidity ranking is a capacity filter, NOT an alpha model.
    passed.sort(
        key=lambda row: (-float(row.avg_dollar_volume_20d_usd), row.symbol)
    )
    eligible = passed[: policy.max_symbols]
    for row in passed[policy.max_symbols :]:
        rejected.append(RejectedAsset(row.symbol, ("research_capacity_limit",)))

    selected = tuple(row.symbol for row in eligible)
    rejected.sort(key=lambda row: row.symbol)
    rejected_tuple = tuple(rejected)

    # Stable reproducibility fingerprint; no broker state is recorded.
    canonical = {
        "as_of": policy.as_of.isoformat(),
        "policy": {
            "allowed_asset_classes": policy.allowed_asset_classes,
            "min_history_sessions": policy.min_history_sessions,
            "min_price_usd": policy.min_price_usd,
            "min_avg_dollar_volume_20d_usd":
                policy.min_avg_dollar_volume_20d_usd,
            "max_quoted_spread_bps": policy.max_quoted_spread_bps,
            "max_observation_age_days": policy.max_observation_age_days,
            "max_symbols": policy.max_symbols,
        },
        "selected": selected,
        "rejected": [
            {"symbol": x.symbol, "reasons": x.reasons}
            for x in rejected_tuple
        ],
    }
    fingerprint = sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()

    return UniverseResult(
        as_of=policy.as_of,
        symbols=selected,
        rejected=rejected_tuple,
        selection_sha256=fingerprint,
    )

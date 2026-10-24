"""QuantConnect Cloud ETF-constituent *coverage only* feasibility probe.

This inspects the underlying equities in one ETF, not historical
tradability/prices of ETF shares. The dated constituent snapshots may be
published late; source timestamps are NOT authenticated. No broker,
internet client, raw-row export, account secret, or trading order exists.
Requires a QuantBook-like Cloud Research environment supplied by caller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import math

from fund100_v2.qc_cloud_feasibility import CloudWindow, _number


NOT_ETF_PRICE_EVIDENCE = "ETF_CONSTITUENTS_ONLY_NOT_ETF_PRICES_OR_PIT_ALPHA"
MAX_ETF_ROWS = 3000


@dataclass(frozen=True)
class EtfConstituentCoverage:
    last_update_date: str
    observed_constituent_rows: int
    distinct_symbol_keys: int
    duplicate_symbol_keys: int
    valid_positive_weights: int
    total_valid_reported_weight: float
    selected_for_temporary_research: int


@dataclass(frozen=True)
class EtfCoverageReport:
    etf: str
    requested_start: str
    requested_end_exclusive: str
    dated_snapshots: tuple[EtfConstituentCoverage, ...]
    audit_sha256: str
    evidence: str = NOT_ETF_PRICE_EVIDENCE
    etf_share_prices_verified: bool = False
    historic_release_times_verified: bool = False
    dividend_adjustments_verified: bool = False
    delisting_proceeds_verified: bool = False
    cloud_runtime_execution_verified: bool = False
    raw_provider_data_exported: bool = False
    account_orders_sent: int = 0


def _update_day(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError("ETF constituent lacks dated last_update field")


def _snapshot(
    values: object, *, limit: int,
) -> tuple[EtfConstituentCoverage, list[object]]:
    rows = list(values)
    if not rows or len(rows) > MAX_ETF_ROWS:
        raise ValueError("ETF constituent dataset empty or unbounded")
    days = {_update_day(getattr(row, "last_update", None)) for row in rows}
    if len(days) != 1:
        raise ValueError("Inconsistent ETF constituent update dates")
    seen: set[str] = set()
    duplicates = 0
    valid: list[tuple[float, str, object]] = []
    total = 0.0
    for row in rows:
        symbol = getattr(row, "symbol", None)
        if symbol is None:
            raise ValueError("ETF constituent missing symbol")
        key = str(symbol)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        weight = _number(getattr(row, "weight", None))
        if weight is not None and 0 < weight <= 1:
            valid.append((weight, key, symbol))
            total += weight
    valid.sort(key=lambda item: (-item[0], item[1]))
    selected = [sym for _, _, sym in valid[:limit]]
    record = EtfConstituentCoverage(
        last_update_date=next(iter(days)),
        observed_constituent_rows=len(rows),
        distinct_symbol_keys=len(seen),
        duplicate_symbol_keys=duplicates,
        valid_positive_weights=len(valid),
        total_valid_reported_weight=round(total, 8),
        selected_for_temporary_research=len(selected),
    )
    return record, selected


def check_etf_constituent_coverage(
    quantbook: object,
    *,
    etf: str = "SPY",
    window: CloudWindow = CloudWindow(
        date(2020, 11, 23), date(2020, 12, 4)
    ),
    max_select: int = 5,
) -> EtfCoverageReport:
    """Probe a short licensed-cloud universe without persisting constituents.

    This *never* claims that SPY ETF share-price history is available,
    that holdings publication times are proven, or that copied SID strings
    are stable issuer identifiers.
    """
    if etf != "SPY":
        raise ValueError("Only the bounded SPY ETF sample is supported")
    if not isinstance(window, CloudWindow):
        raise TypeError("Bounded CloudWindow required")
    if (not isinstance(max_select, int) or isinstance(max_select, bool)
            or not 1 <= max_select <= 10):
        raise ValueError("ETF research selection limit must be 1..10")
    universe_api = getattr(quantbook, "universe", None)
    if (
        not callable(getattr(universe_api, "etf", None))
        or not callable(getattr(quantbook, "add_universe", None))
        or not callable(getattr(quantbook, "universe_history", None))
    ):
        raise TypeError("Requires a QuantBook-like ETF research environment")

    observed: dict[str, EtfConstituentCoverage] = {}

    def select_constituents(constituents):
        item, selected = _snapshot(constituents, limit=max_select)
        if item.last_update_date in observed:
            if observed[item.last_update_date] != item:
                raise ValueError("Contradictory ETF constituent snapshot")
        else:
            observed[item.last_update_date] = item
        return selected

    spec = quantbook.universe.etf(
        etf, universe_filter_func=select_constituents
    )
    universe = quantbook.add_universe(spec)
    history = quantbook.universe_history(
        universe,
        datetime(window.start.year, window.start.month, window.start.day),
        datetime(window.end.year, window.end.month, window.end.day),
    )
    if history is None or not hasattr(history, "__len__") or len(history) == 0:
        raise ValueError("ETF cloud universe history not materialized")
    if not observed:
        raise ValueError("ETF selector was not evaluated by Cloud history")

    records = tuple(observed[key] for key in sorted(observed))
    for item in records:
        stamp = date.fromisoformat(item.last_update_date)
        # A holdings last-update date is NOT a publication timestamp; up to
        # a week delay may exist. This is a coarse request feasibility check.
        if stamp >= window.end or (
            stamp < window.start
            and (window.start - stamp).days > 10
        ):
            raise ValueError("ETF holdings source date outside allowed range")
    payload = {
        "etf": etf,
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "snapshots": [asdict(x) for x in records],
    }
    digest = sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()

    return EtfCoverageReport(
        etf=etf,
        requested_start=window.start.isoformat(),
        requested_end_exclusive=window.end.isoformat(),
        dated_snapshots=records,
        audit_sha256=digest,
    )

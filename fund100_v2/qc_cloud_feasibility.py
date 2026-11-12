"""QuantConnect Cloud *coverage feasibility* probe, not a trading model.

Pass a QuantBook-like research object supplied INSIDE QuantConnect Cloud.
No QuantConnect credentials, API calls, account access, orders, exports,
data resale, strategy signals, or broker connections are made here.

Calls to qb.add_universe and qb.universe_history use the platform's
documented current Fundamental Universe research API. Historical data
publication vintages, delisting settlement and usable spread data remain
UNVERIFIED. Actual QuantConnect Cloud execution is NOT claimed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import math


NOT_VALIDATED = "CLOUD_COVERAGE_ONLY_NOT_PIT_ALPHA_EVIDENCE"
DEFAULT_WINDOWS = (
    (date(2018, 9, 4), date(2018, 9, 11)),
    (date(2020, 11, 23), date(2020, 12, 2)),
    (date(2024, 6, 3), date(2024, 6, 12)),
)


@dataclass(frozen=True)
class CloudWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if (
            not isinstance(self.start, date)
            or not isinstance(self.end, date)
            or self.start >= self.end
            or self.start.weekday() >= 5
        ):
            raise ValueError("Invalid bounded cloud research window")
        if (self.end - self.start).days > 35:
            raise ValueError("Refuse bulk cloud universe download")


@dataclass(frozen=True)
class DayCoverage:
    reported_source_date: str
    visible_universe_rows: int
    distinct_symbol_keys: int
    passing_price_and_volume: int
    selected_for_research_subscription: int
    duplicate_symbol_keys: int


@dataclass(frozen=True)
class WindowCoverage:
    start: str
    end_exclusive: str
    observed_source_dates: int
    daily: tuple[DayCoverage, ...]
    raw_history_materialized: bool
    research_ready: bool = False


@dataclass(frozen=True)
class CloudCoverageReport:
    windows: tuple[WindowCoverage, ...]
    audit_sha256: str
    research_status: str = NOT_VALIDATED
    used_live_credentials: bool = False
    broker_orders_submitted: int = 0
    csv_export_performed: bool = False
    historic_vintages_verified: bool = False
    delisting_cashflows_verified: bool = False
    adjusted_price_basis_verified: bool = False
    quoted_spreads_verified: bool = False
    actual_cloud_execution_verified_by_github_ci: bool = False


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _row_source_date(row: object) -> str:
    time = getattr(row, "end_time", None)
    if time is None:
        raise ValueError("Provider row lacks source period metadata")
    if isinstance(time, (datetime, date)):
        return time.date().isoformat() if isinstance(time, datetime) else time.isoformat()
    raise ValueError("Unsupported source period metadata")


def _snapshot(
    records: object, *,
    max_subscriptions: int,
) -> tuple[DayCoverage, list[object]]:
    """Return only aggregate counts and bounded research subscriptions.

    LEAN symbols are used temporarily as in-memory selection keys;
    they are never persisted, printed, or exported.
    """
    rows = list(records)
    if not rows:
        raise ValueError("Cloud universe returned an empty day")
    dates = {_row_source_date(row) for row in rows}
    if len(dates) != 1:
        raise ValueError("Cloud universe mixes source dates in one session")

    seen: set[str] = set()
    duplicate_count = 0
    valid: list[tuple[float, str, object]] = []
    for row in rows:
        symbol = getattr(row, "symbol", None)
        if symbol is None:
            raise ValueError("Cloud universe row has no security identifier")
        # QuantConnect Symbol string is not independent issuer identity proof.
        key = str(symbol)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        price = _number(getattr(row, "price", None))
        dollar_volume = _number(getattr(row, "dollar_volume", None))
        if (
            price is not None and price >= 5
            and dollar_volume is not None and dollar_volume >= 5_000_000
        ):
            valid.append((dollar_volume, key, symbol))

    valid.sort(key=lambda entry: (-entry[0], entry[1]))
    selected = [entry[2] for entry in valid[:max_subscriptions]]
    item = DayCoverage(
        reported_source_date=next(iter(dates)),
        visible_universe_rows=len(rows),
        distinct_symbol_keys=len(seen),
        passing_price_and_volume=len(valid),
        selected_for_research_subscription=len(selected),
        duplicate_symbol_keys=duplicate_count,
    )
    return item, selected


def run_cloud_coverage_probe(
    quantbook: object,
    *,
    windows: tuple[CloudWindow, ...] = tuple(
        CloudWindow(start, end) for start, end in DEFAULT_WINDOWS
    ),
    max_subscriptions: int = 10,
) -> CloudCoverageReport:
    """Run 3 small QC Research-only universe requests and summarize coverage.

    The supplied research object must support add_universe and
    universe_history, as documented by QuantConnect. No orders ever sent.
    A successful GitHub mock test is NOT a successful QuantConnect query.
    """
    if not windows or any(not isinstance(w, CloudWindow) for w in windows):
        raise ValueError("Explicit valid cloud windows required")
    if (
        not isinstance(max_subscriptions, int)
        or isinstance(max_subscriptions, bool)
        or not 1 <= max_subscriptions <= 20
    ):
        raise ValueError("Bounded research subscriptions required")
    if not callable(getattr(quantbook, "add_universe", None)) or not callable(
        getattr(quantbook, "universe_history", None)
    ):
        raise TypeError("A QuantBook-like research environment is required")

    outputs = []
    for window in windows:
        observed: dict[str, DayCoverage] = {}

        def selection_function(fundamentals):
            coverage, selected = _snapshot(
                fundamentals, max_subscriptions=max_subscriptions
            )
            key = coverage.reported_source_date
            if key in observed:
                if observed[key] != coverage:
                    raise ValueError("Conflicting repeat universe snapshot")
            else:
                observed[key] = coverage
            return selected

        universe = quantbook.add_universe(selection_function)
        history = quantbook.universe_history(
            universe,
            datetime(window.start.year, window.start.month, window.start.day),
            datetime(window.end.year, window.end.month, window.end.day),
        )
        # Force an eager materialization of the bounded universe request.
        if history is None:
            raise ValueError("Cloud universe history is unavailable")
        if hasattr(history, "empty") and bool(history.empty):
            raise ValueError("Cloud universe history is empty")
        # Historical pandas Series exposes len; no underlying rows exported.
        if not hasattr(history, "__len__") or len(history) == 0:
            raise ValueError("Cloud universe history is not materialized")
        if not observed:
            raise ValueError(
                "Cloud callback was not evaluated: no coverage evidence"
            )
        entries = tuple(observed[key] for key in sorted(observed))
        for item in entries:
            d = date.fromisoformat(item.reported_source_date)
            # Fundamental end_time is the data period end, not guaranteed
            # release time, so allow the prior day (including weekends).
            if d >= window.end or (
                d < window.start and (window.start - d).days > 7
            ):
                raise ValueError("Unexpected historical source period")
        outputs.append(WindowCoverage(
            start=window.start.isoformat(),
            end_exclusive=window.end.isoformat(),
            observed_source_dates=len(entries),
            daily=entries,
            raw_history_materialized=True,
        ))

    canonical = {
        "windows": [asdict(window) for window in outputs],
        "status": NOT_VALIDATED,
    }
    digest = sha256(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    return CloudCoverageReport(
        windows=tuple(outputs),
        audit_sha256=digest,
    )


def aggregate_report_json(report: CloudCoverageReport) -> str:
    if not isinstance(report, CloudCoverageReport):
        raise TypeError("Cloud coverage report required")
    return json.dumps(
        asdict(report), sort_keys=True, separators=(",", ":"), allow_nan=False
    )

"""Offline, point-in-time daily-bar adapter for V2 universe research.

Inputs are caller-supplied historical daily bars and as-of asset metadata.
This module performs NO HTTP requests, reads NO Alpaca secrets, and cannot
submit orders. Historical truth/survivorship still depends on the data vendor.
"""

from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date
import math
from pathlib import Path
from typing import Iterable

from fund100_v2.universe import AssetObservation


CSV_FIELDS = (
    "symbol",
    "date",
    "close_usd",
    "volume_shares",
    "quoted_spread_bps",
)
MIN_TRAILING_SESSIONS = 20
MAX_TRAILING_WINDOW_DAYS = 45


@dataclass(frozen=True)
class DatedAsset:
    """The catalog entry must have existed *as of* the research date."""

    symbol: str
    asset_class: str
    observed_on: date
    listed_on: date
    active: bool
    tradable: bool
    fractionable: bool = False


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    session: date
    close_usd: float
    volume_shares: float
    quoted_spread_bps: float


def _nonnegative_finite(value: float) -> bool:
    try:
        n = float(value)
    except (ValueError, OverflowError, TypeError):
        return False
    return math.isfinite(n) and n >= 0


def _positive_finite(value: float) -> bool:
    return _nonnegative_finite(value) and float(value) > 0


def read_bars_csv(path: str | Path, *, as_of: date) -> tuple[DailyBar, ...]:
    """Parse a local file; reject duplicate, malformed and future-dated rows.

    This rejects, rather than silently dropping, any future row in a file.
    It also refuses extra columns so a vendor schema change is visible.
    """
    if not isinstance(as_of, date):
        raise ValueError("Valid as_of date is mandatory")

    results: list[DailyBar] = []
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != CSV_FIELDS:
            raise ValueError("Unexpected daily-bar CSV schema")

        for row_number, row in enumerate(reader, start=2):
            try:
                symbol = str(row["symbol"])
                session = date.fromisoformat(str(row["date"]))
                close = float(row["close_usd"])
                volume = float(row["volume_shares"])
                spread = float(row["quoted_spread_bps"])
            except (ValueError, OverflowError, TypeError, KeyError) as exc:
                raise ValueError(f"Malformed daily-bar CSV row {row_number}") from exc

            if not symbol or symbol != symbol.strip().upper():
                raise ValueError(f"Invalid symbol in CSV row {row_number}")
            if session > as_of:
                raise ValueError(f"Future-dated bar in CSV row {row_number}")
            if not (_positive_finite(close)
                    and _nonnegative_finite(volume)
                    and _nonnegative_finite(spread)):
                raise ValueError(f"Invalid price/volume/spread in CSV row {row_number}")
            results.append(DailyBar(symbol, session, close, volume, spread))

    if not results:
        raise ValueError("Empty daily-bar dataset")
    return tuple(results)


def observations_from_history(
    catalog: Iterable[DatedAsset],
    bars: Iterable[DailyBar],
    *,
    as_of: date,
) -> tuple[AssetObservation, ...]:
    """Make date-consistent observations for the research-only screen.

    A 20-session dollar-volume average is computed from close*volume at
    each historical session. This is a LIQUIDITY measure, not an alpha score.
    No missing row may be forward-filled. A catalog entry without sufficient
    recent bars aborts the batch rather than disappearing silently.
    """
    if not isinstance(as_of, date):
        raise ValueError("Valid as_of date is mandatory")

    catalog_rows = list(catalog)
    symbols = [row.symbol for row in catalog_rows]
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("Empty or duplicate point-in-time catalog")

    mapping = {row.symbol: row for row in catalog_rows}
    per_symbol: dict[str, list[DailyBar]] = defaultdict(list)
    seen: set[tuple[str, date]] = set()

    for bar in bars:
        if not isinstance(bar, DailyBar):
            raise TypeError("DailyBar entries required")
        if bar.symbol not in mapping:
            raise ValueError(f"Bar without catalog entry: {bar.symbol}")
        if not isinstance(bar.session, date) or bar.session > as_of:
            raise ValueError("Future or invalid bar session")
        if (bar.symbol, bar.session) in seen:
            raise ValueError("Duplicate daily-bar symbol/session")
        seen.add((bar.symbol, bar.session))
        if (
            not _positive_finite(bar.close_usd)
            or not _nonnegative_finite(bar.volume_shares)
            or not _nonnegative_finite(bar.quoted_spread_bps)
        ):
            raise ValueError("Invalid historical daily-bar numeric field")
        per_symbol[bar.symbol].append(bar)

    output: list[AssetObservation] = []
    for row in sorted(catalog_rows, key=lambda item: item.symbol):
        if (
            not isinstance(row.observed_on, date)
            or row.observed_on > as_of
            or not isinstance(row.listed_on, date)
            or row.listed_on > as_of
        ):
            raise ValueError("Catalog contains future or invalid as-of metadata")

        history = sorted(per_symbol[row.symbol], key=lambda item: item.session)
        if len(history) < MIN_TRAILING_SESSIONS:
            raise ValueError(f"{row.symbol}: insufficient bars for 20d liquidity")
        if any(bar.session < row.listed_on for bar in history):
            raise ValueError(f"{row.symbol}: bar before listing date")

        latest = history[-1]
        tail = history[-MIN_TRAILING_SESSIONS:]
        if (latest.session - tail[0].session).days > MAX_TRAILING_WINDOW_DAYS:
            raise ValueError(f"{row.symbol}: trailing data contains gaps")

        adv = sum(
            float(bar.close_usd) * float(bar.volume_shares) for bar in tail
        ) / MIN_TRAILING_SESSIONS

        output.append(AssetObservation(
            symbol=row.symbol,
            asset_class=row.asset_class,
            observed_on=min(row.observed_on, latest.session),
            listed_on=row.listed_on,
            active=row.active,
            tradable=row.tradable,
            price_usd=float(latest.close_usd),
            avg_dollar_volume_20d_usd=adv,
            quoted_spread_bps=float(latest.quoted_spread_bps),
            history_sessions=len(history),
            fractionable=row.fractionable,
        ))
    return tuple(output)

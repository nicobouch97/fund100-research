"""Offline public-format inspector for QuantConnect LEAN reference samples.

The LEAN public repository contains examples of ETF constituent snapshots
and security map/factor files. Some data have explicit third-party copyright
notices. Do NOT copy or redistribute vendor rows into Fund-100.

This module accepts caller-supplied local text only. It never downloads,
connects to brokers, grants trading eligibility, or labels format samples
as independently authenticated historical source vintages.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import io
import math
import re


SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,13}\Z")
SENTINEL_DAY = date(2050, 12, 31)
NOT_BACKTEST_READY = "FORMAT_ONLY_NOT_HISTORICAL_EVIDENCE"


@dataclass(frozen=True)
class LeanEtfConstituent:
    ticker: str
    vendor_sid: str
    holdings_date: date
    fraction_of_nav: float
    shares: float


@dataclass(frozen=True)
class LeanEtfSampleAudit:
    """Sufficient to check format, explicitly insufficient for alpha."""

    sample_session: str
    holdings_first_date: str
    holdings_last_date: str
    constituents: int
    duplicate_sid_distinct_tickers: tuple[str, ...]
    gross_reported_weights: float
    raw_sha256: str
    source_authenticity_verified: bool = False
    historical_publication_timestamp_verified: bool = False
    full_market_membership_verified: bool = False
    individual_security_prices_verified: bool = False
    delisting_settlements_verified: bool = False
    research_readiness: str = NOT_BACKTEST_READY


@dataclass(frozen=True)
class LeanMapEvent:
    effective_date: date
    ticker: str
    exchange_code: str


@dataclass(frozen=True)
class LeanMapSampleAudit:
    source_filename_symbol: str
    events: tuple[LeanMapEvent, ...]
    sentinel_record_present: bool
    raw_sha256: str
    historical_publication_timestamp_verified: bool = False
    research_readiness: str = NOT_BACKTEST_READY


def _day(text: str) -> date:
    if len(text) != 8 or not text.isascii() or not text.isdigit():
        raise ValueError("LEAN date must be YYYYMMDD")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError as exc:
        raise ValueError("Invalid LEAN calendar day") from exc


def _rows(text: str, *, expected: int) -> tuple[tuple[str, ...], ...]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("LEAN sample text must be a nonempty string")
    try:
        values = [
            tuple(row)
            for row in csv.reader(io.StringIO(text), strict=True)
        ]
    except csv.Error as exc:
        raise ValueError("Malformed LEAN sample CSV") from exc
    if not values or any(len(row) != expected for row in values):
        raise ValueError("Unexpected LEAN sample column count")
    return tuple(values)


def _finite(text: str, *, minimum: float, upper: float | None = None) -> float:
    try:
        value = float(text)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Invalid LEAN numeric value") from exc
    if (not math.isfinite(value)
            or value < minimum
            or (upper is not None and value > upper)):
        raise ValueError("Invalid LEAN numeric value")
    return value


def inspect_lean_etf_constituents(
    csv_text: str,
    *,
    snapshot_day: date,
) -> LeanEtfSampleAudit:
    """Inspect LEAN six-column ETF holdings fixture.

    Observed sample format: ticker, ticker+SID, holdings_date,
    fractional_weight, shares, blank. Filename's date is the
    apparent snapshot day; it DOES NOT prove publication time.

    A duplicate vendor SID mapped to distinct tickers is flagged,
    never silently merged as the same stock identifier.
    """
    if not isinstance(snapshot_day, date):
        raise ValueError("Explicit snapshot day required")
    rows = _rows(csv_text, expected=6)
    records: list[LeanEtfConstituent] = []
    seen_tickers: set[str] = set()
    sid_to_tickers: dict[str, set[str]] = {}

    for ticker, vendor_identity, day_text, weight, shares, suffix in rows:
        if not SYMBOL.fullmatch(ticker):
            raise ValueError("Invalid LEAN ETF constituent ticker")
        if ticker in seen_tickers:
            raise ValueError("Duplicate ticker in LEAN ETF sample")
        seen_tickers.add(ticker)
        if suffix.strip():
            raise ValueError("Unexpected nonempty final LEAN ETF column")
        prefix = ticker + " "
        if not vendor_identity.startswith(prefix):
            raise ValueError("LEAN vendor identity does not match ticker")
        sid = vendor_identity[len(prefix):]
        if not re.fullmatch(r"[A-Z0-9]{4,24}", sid):
            raise ValueError("Invalid LEAN vendor SID")
        holdings_day = _day(day_text)
        if holdings_day > snapshot_day:
            raise ValueError("Future ETF holdings referenced in sample")
        fraction = _finite(weight, minimum=0.0, upper=1.0)
        quantity = _finite(shares, minimum=0.0)
        records.append(LeanEtfConstituent(
            ticker=ticker, vendor_sid=sid, holdings_date=holdings_day,
            fraction_of_nav=fraction, shares=quantity
        ))
        sid_to_tickers.setdefault(sid, set()).add(ticker)

    distinct_sids = tuple(sorted(
        sid for sid, tickers in sid_to_tickers.items() if len(tickers) > 1
    ))
    holdings = [record.holdings_date for record in records]
    return LeanEtfSampleAudit(
        sample_session=snapshot_day.isoformat(),
        holdings_first_date=min(holdings).isoformat(),
        holdings_last_date=max(holdings).isoformat(),
        constituents=len(records),
        duplicate_sid_distinct_tickers=distinct_sids,
        gross_reported_weights=sum(x.fraction_of_nav for x in records),
        raw_sha256=sha256(csv_text.encode("utf-8")).hexdigest(),
    )


def inspect_lean_map_file(
    csv_text: str,
    *,
    filename_symbol: str,
) -> LeanMapSampleAudit:
    """Parse three-column LEAN map file; never infer a 2050 delisting.

    The 20501231 sentinel means continuation in a reference map. It
    is not a dated delisting, a payout or proof of availability in 2050.
    """
    if not isinstance(filename_symbol, str) or not SYMBOL.fullmatch(
        filename_symbol.upper()
    ):
        raise ValueError("Invalid LEAN map file symbol")
    rows = _rows(csv_text, expected=3)
    events = []
    sentinel = False
    last_day = None
    for day_text, ticker_raw, exchange in rows:
        ticker = ticker_raw.upper()
        if not SYMBOL.fullmatch(ticker):
            raise ValueError("Invalid mapped ticker")
        day = _day(day_text)
        if last_day is not None and day <= last_day:
            raise ValueError("LEAN map events must be strictly ordered")
        last_day = day
        if len(exchange) != 1 or not exchange.isascii() or not exchange.isalpha():
            raise ValueError("Invalid LEAN exchange mapping code")
        if day == SENTINEL_DAY:
            sentinel = True
            continue
        if day > SENTINEL_DAY:
            raise ValueError("Unexpected post-sentinel map date")
        events.append(LeanMapEvent(day, ticker, exchange.upper()))
    if not events:
        raise ValueError("LEAN map contains no actual dated events")
    return LeanMapSampleAudit(
        source_filename_symbol=filename_symbol.upper(),
        events=tuple(events),
        sentinel_record_present=sentinel,
        raw_sha256=sha256(csv_text.encode("utf-8")).hexdigest(),
    )

"""Strict offline V2 research-data bundle loader.

Requires source-DECLARED vintage timestamps, total-return-adjusted prices,
a per-date complete historical eligibility grid, and hashed input files.
Passing a structural check does not independently verify vendor truth.
No network or broker interaction and no LIVE execution permissions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from fund100_v2.signals import ResearchPanel


BUNDLE_SCHEMA = "FUND100_V2_RESEARCH_BUNDLE_V1"
PRICE_COLUMNS = (
    "session", "symbol", "total_return_close", "spread_bps",
    "price_known_at_utc",
)
MEMBERSHIP_COLUMNS = (
    "session", "symbol", "eligible", "membership_known_at_utc",
)
NEW_YORK = ZoneInfo("America/New_York")
UTC = timezone.utc


@dataclass(frozen=True)
class BundleEvidence:
    """Provenance metadata, *not* independent vendor validation."""

    source_vendor: str
    snapshot_id: str
    source_record: str
    symbols: tuple[str, ...]
    first_session: str
    last_session: str
    sessions: int
    eligible_observations: int
    price_sha256: str
    membership_sha256: str
    combined_sha256: str
    source_verification: str = "SELF_ATTESTED_NOT_INDEPENDENTLY_VERIFIED"


@dataclass(frozen=True)
class ResearchBundle:
    panel: ResearchPanel
    evidence: BundleEvidence


def _utc_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {field} timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(None):
        raise ValueError(f"{field} timestamp must explicitly use UTC")
    return parsed.astimezone(UTC)


def _session_day(raw: str) -> date:
    try:
        day = date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid research session date") from exc
    if day.weekday() > 4:
        raise ValueError("Weekend research session is not supported")
    return day


def _close_utc(day: date) -> datetime:
    return datetime.combine(day, time(16), tzinfo=NEW_YORK).astimezone(UTC)


def _day_end_utc(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=UTC)


def _finite_price(raw: str) -> float:
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid total-return-adjusted price") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Invalid total-return-adjusted price")
    return number


def _finite_spread(raw: str) -> float:
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid quoted spread") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("Invalid quoted spread")
    return number


def _read_rows(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"Unexpected research CSV columns: {path.name}")
        try:
            rows = list(reader)
        except csv.Error as exc:
            raise ValueError(f"Invalid CSV records: {path.name}") from exc
    if not rows:
        raise ValueError(f"Empty research CSV: {path.name}")
    if any(
        set(row) != set(columns)
        or any(not isinstance(row.get(k), str) or not row[k].strip()
               for k in columns)
        for row in rows
    ):
        raise ValueError(f"Missing or extra research CSV value: {path.name}")
    return rows


def _validate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema") != BUNDLE_SCHEMA:
        raise ValueError("Research bundle schema mismatch")
    fields = (
        "source_vendor", "snapshot_id", "source_record",
        "prices_sha256", "membership_sha256",
    )
    if any(
        not isinstance(manifest.get(key), str)
        or not manifest[key].strip()
        for key in fields
    ):
        raise ValueError("Incomplete research source provenance")
    for key in ("prices_sha256", "membership_sha256"):
        value = manifest[key]
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Invalid source file SHA256")
    if manifest.get("price_basis") != "SPLIT_AND_DIVIDEND_ADJUSTED_TOTAL_RETURN":
        raise ValueError("Total-return-adjusted series explicitly required")
    if manifest.get("membership_basis") != "HISTORICAL_POINT_IN_TIME":
        raise ValueError("Historical point-in-time eligibility required")
    if manifest.get("includes_delisted_instrument_history") is not True:
        raise ValueError("Delisted-history coverage must be source-attested")
    return manifest


def load_research_bundle(
    folder: str | Path,
    *,
    as_of: date,
) -> ResearchBundle:
    """Validate a local bundle, build a dated research panel; never download.

    File names are fixed: manifest.json, prices.csv and membership.csv.
    Price availability is after session close, by 23:59 UTC that day;
    eligibility must have been known no later than the session close.
    Missing price rows are permitted ONLY when dated eligibility is FALSE,
    with no holes inside an instrument's observed real-price lifetime.
    A missing delisting exit price may NEVER be valued as cash or zero.
    This conservative assumption excludes special half-day closes.
    """
    if not isinstance(as_of, date):
        raise ValueError("Explicit research as_of date required")

    folder = Path(folder)
    manifest = _validate_manifest(json.loads(
        (folder / "manifest.json").read_text(encoding="utf-8")
    ))
    price_bytes = (folder / "prices.csv").read_bytes()
    membership_bytes = (folder / "membership.csv").read_bytes()
    price_hash = sha256(price_bytes).hexdigest()
    membership_hash = sha256(membership_bytes).hexdigest()

    if (
        price_hash != manifest["prices_sha256"]
        or membership_hash != manifest["membership_sha256"]
    ):
        raise ValueError("Research source checksum mismatch")

    prices: dict[tuple[date, str], tuple[float, float]] = {}
    members: dict[tuple[date, str], bool] = {}

    for row in _read_rows(folder / "prices.csv", PRICE_COLUMNS):
        day = _session_day(row["session"])
        if day > as_of:
            raise ValueError("Future research price session")
        symbol = row["symbol"]
        if not symbol.isascii() or not symbol or not symbol.isupper():
            raise ValueError("Invalid historical price symbol")
        key = (day, symbol)
        if key in prices:
            raise ValueError("Duplicate research price observation")
        known = _utc_timestamp(row["price_known_at_utc"], "price")
        if not _close_utc(day) <= known <= _day_end_utc(day):
            raise ValueError("Research price arrived outside allowed vintage")
        prices[key] = (
            _finite_price(row["total_return_close"]),
            _finite_spread(row["spread_bps"]),
        )

    for row in _read_rows(folder / "membership.csv", MEMBERSHIP_COLUMNS):
        day = _session_day(row["session"])
        if day > as_of:
            raise ValueError("Future research membership session")
        symbol = row["symbol"]
        if not symbol.isascii() or not symbol or not symbol.isupper():
            raise ValueError("Invalid historical membership symbol")
        key = (day, symbol)
        if key in members:
            raise ValueError("Duplicate historical membership observation")
        if row["eligible"] not in {"TRUE", "FALSE"}:
            raise ValueError("Membership flag must be TRUE or FALSE")
        known = _utc_timestamp(row["membership_known_at_utc"], "membership")
        if known > _close_utc(day):
            raise ValueError("Lookahead: membership not known at decision close")
        members[key] = row["eligible"] == "TRUE"

    if not set(prices).issubset(members):
        raise ValueError("Historical price without dated membership evidence")

    days = tuple(sorted({day for day, _ in members}))
    symbols = tuple(sorted({symbol for _, symbol in members}))
    if len(members) != len(days) * len(symbols):
        raise ValueError("Incomplete historical membership date/symbol grid")
    if any(eligible and (day, sym) not in prices
           for (day, sym), eligible in members.items()):
        raise ValueError("Missing price for historically eligible asset")
    if any(not any((day, sym) in prices for day in days) for sym in symbols):
        raise ValueError("No observed historical price for catalogued asset")

    # None is genuine absence, not an imputed historical price.
    # ResearchPanel validates paired price/spread gaps and disallows
    # interior missing prices even on temporarily ineligible days.
    price_panel = {
        s: tuple(
            prices[(day, s)][0] if (day, s) in prices else None
            for day in days
        ) for s in symbols
    }
    spread_panel = {
        s: tuple(
            prices[(day, s)][1] if (day, s) in prices else None
            for day in days
        ) for s in symbols
    }
    eligibility = tuple(
        frozenset(s for s in symbols if members[(day, s)])
        for day in days
    )
    panel = ResearchPanel(
        sessions=days,
        adjusted_prices=price_panel,
        spread_bps=spread_panel,
        eligible_symbols=eligibility,
    )
    # The digest binds the manifest fields and the exact input file bytes.
    fingerprint = sha256(json.dumps({
        "manifest": manifest,
        "prices_sha256": price_hash,
        "membership_sha256": membership_hash,
        "as_of": as_of.isoformat(),
    }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )).hexdigest()

    return ResearchBundle(
        panel=panel,
        evidence=BundleEvidence(
            source_vendor=manifest["source_vendor"],
            snapshot_id=manifest["snapshot_id"],
            source_record=manifest["source_record"],
            symbols=symbols,
            first_session=days[0].isoformat(),
            last_session=days[-1].isoformat(),
            sessions=len(days),
            eligible_observations=sum(map(len, eligibility)),
            price_sha256=price_hash,
            membership_sha256=membership_hash,
            combined_sha256=fingerprint,
        ),
    )

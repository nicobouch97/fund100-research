"""Credential-free, source-dated US exchange listing DISCOVERY, not a stock universe.

Official Nasdaq Trader Nasdaq/other-exchange daily directory bytes. Save only
non-reconstructible coverage totals and byte fingerprints; never source rows.
No broker, SEC companyfacts, historical security master or trading permissions.
A current non-ETF listing is NOT proved to be a US common share or historically
eligible security, and source snapshots cannot be retroactively backfilled.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo
import argparse
import csv
import json
import re

SCHEMA = "FUND100_V9_OFFICIAL_CURRENT_LISTING_DISCOVERY_V1"
BASE = "https://www.nasdaqtrader.com/dynamic/SymDir/"
FILES = ("nasdaqlisted.txt", "otherlisted.txt")
MAX_BYTES = 4_000_000
MAX_AGE = timedelta(hours=96)
NO_BROKER_ORDERS = NO_BROKER_READS = NO_PRIVATE_STATE_WRITES = 0
LIVE_ORDER_AUTHORIZED = False
REQUIRED = {
    "nasdaqlisted.txt": {"Symbol", "Security Name", "Market Category", "ETF", "Test Issue"},
    "otherlisted.txt": {"ACT Symbol", "Security Name", "Exchange", "ETF", "Test Issue"},
}
SYMBOL_FIELD = {"nasdaqlisted.txt": "Symbol", "otherlisted.txt": "ACT Symbol"}
MARKET_FIELD = {"nasdaqlisted.txt": "Market Category", "otherlisted.txt": "Exchange"}
KNOWN_MARKETS = {"nasdaqlisted.txt": {"Q", "G", "S"},
                 "otherlisted.txt": {"N", "A", "P", "Z", "V"}}
FOOTER = re.compile(r"File Creation Time: (\d{8})(\d{2}:\d{2})\|*")
NY = ZoneInfo("America/New_York")


class ListingsStop(ValueError):
    pass


def _asof(observed):
    if type(observed) is not datetime or observed.tzinfo is None:
        raise ListingsStop("Missing timezone-aware source receipt")
    utc = observed.astimezone(timezone.utc)
    if utc.utcoffset() != timedelta(0):
        raise ListingsStop("Invalid source time")
    return utc


def inspect_bytes(raw: bytes, filename: str, *, observed: datetime, min_rows=1):
    """Strict, offline parse; return only counts/time/fingerprint, never names."""
    if (filename not in FILES or type(raw) is not bytes
        or not 40 <= len(raw) <= MAX_BYTES):
        raise ListingsStop("Unqualified listing source")
    now = _asof(observed)
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ListingsStop("Non-UTF8 official directory") from None
    if "\x00" in source or not source.endswith("\n"):
        raise ListingsStop("Truncated or binary directory")
    lines = source.splitlines()
    if len(lines) < 3:
        raise ListingsStop("Missing source header, rows or footer")
    match = FOOTER.fullmatch(lines[-1].strip())
    if match is None:
        raise ListingsStop("Missing exact official source creation footer")
    try:
        created_local = datetime.strptime(
            match[1] + match[2], "%m%d%Y%H:%M").replace(tzinfo=NY)
    except ValueError:
        raise ListingsStop("Unparseable official creation clock") from None
    age = now - created_local.astimezone(timezone.utc)
    if not timedelta(minutes=-10) <= age <= MAX_AGE:
        raise ListingsStop("Stale or future official symbol directory")
    reader = csv.DictReader(StringIO("\n".join(lines[:-1]) + "\n"), delimiter="|")
    if (reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames))
        or not REQUIRED[filename].issubset(reader.fieldnames)):
        raise ListingsStop("Official directory field contract changed")
    seen = set()
    counts = Counter()
    markets = Counter()
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ListingsStop("Malformed or extra delimiter in directory row")
        sym = row[SYMBOL_FIELD[filename]]
        if (type(sym) is not str or not 1 <= len(sym) <= 32
            or sym != sym.strip() or any(ch.isspace() for ch in sym)
            or sym in seen or not row["Security Name"].strip()):
            raise ListingsStop("Duplicate/invalid listing identifier")
        seen.add(sym)
        etf, test, market = row["ETF"], row["Test Issue"], row[MARKET_FIELD[filename]]
        if etf not in ("Y", "N") or test not in ("Y", "N") or market not in KNOWN_MARKETS[filename]:
            raise ListingsStop("Unknown listing flag or market value")
        counts["total"] += 1
        counts["etf_" + etf] += 1
        counts["test_" + test] += 1
        markets[market] += 1
        if etf == "N" and test == "N":
            counts["non_etf_non_test"] += 1
    if counts["total"] < min_rows:
        raise ListingsStop("Insufficient official listing rows")
    return {
        "source_sha256": sha256(raw).hexdigest(),
        "source_byte_count": len(raw),
        "source_creation_date_ny": created_local.date().isoformat(),
        "listed_rows": counts["total"],
        "etf_flag_Y_rows": counts["etf_Y"],
        "test_issue_Y_rows": counts["test_Y"],
        "non_etf_non_test_listing_candidates_not_common_stock": counts["non_etf_non_test"],
        "market_codes": dict(sorted(markets.items())),
    }


def report(raw_by_filename: dict, *, observed: datetime, min_rows=1):
    if type(raw_by_filename) is not dict or set(raw_by_filename) != set(FILES):
        raise ListingsStop("Both original Nasdaq sources required")
    utc = _asof(observed)
    files = {filename: inspect_bytes(raw_by_filename[filename], filename,
                                    observed=utc, min_rows=min_rows)
             for filename in FILES}
    candidate_count = sum(
        v["non_etf_non_test_listing_candidates_not_common_stock"] for v in files.values())
    if candidate_count == 0:
        raise ListingsStop("No original listing candidates")
    return {
        "schema": SCHEMA,
        "status": "SOURCE_DATED_CURRENT_NON_ETF_LISTING_DISCOVERY_ONLY",
        "captured_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": files,
        "current_non_etf_non_test_listing_rows_total_not_stock_count": candidate_count,
        "US_common_share_security_identity_verified": False,
        "historical_listed_and_delisted_universe_authenticated": False,
        "corporate_actions_and_cik_mapped": False,
        "price_liquidity_spread_eligible": False,
        "issuer_fundamentals_and_valuation_available": False,
        "expected_alpha_estimated": False,
        "broker_READs": 0, "broker_POSTs": 0, "broker_orders": 0,
        "live_order_authorized": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_official(filename: str) -> bytes:
    if filename not in FILES:
        raise ListingsStop("Unapproved directory path")
    url = BASE + filename
    request = Request(url, method="GET", headers={
        "User-Agent": "Fund100-Credentialless-Prospective-Research/1.0",
        "Accept": "text/plain", "Cache-Control": "no-cache",
    })
    try:
        with build_opener(_NoRedirect).open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != url:
                raise ListingsStop("Official direct HTTPS source mismatch")
            raw = response.read(MAX_BYTES + 1)
    except (OSError, TimeoutError, ValueError):
        raise ListingsStop("Official listing fetch failed") from None
    if len(raw) > MAX_BYTES:
        raise ListingsStop("Oversized official listing source")
    return raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    utc = datetime.now(timezone.utc)
    result = report({name: _get_official(name) for name in FILES},
                    observed=utc, min_rows=1000)
    # No overwrite of an already pinned daily observation, even with a
    # later vendor revision. A new observed vintage needs separate lineage.
    if args.out.exists():
        raise ListingsStop("Dated source already frozen; no overwrite")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("Current official non-ETF listing candidates (NOT common stocks):",
          result["current_non_etf_non_test_listing_rows_total_not_stock_count"])
    print("Timestamped source digests only; no raw listing, broker or trades.")


if __name__ == "__main__":
    main()

"""P4T: official 2017-Q1 SEC 10-K filing-population census, NOT a stock backtest.

Start with every 10-K in an archived EDGAR quarter instead of selecting
companies that survive in today's ticker list. An EDGAR filer is NOT proof
of a historically exchange-listed, liquid, investable common share.
Absence from the current SEC ticker registry is NOT proof of delisting.
This source-only study cannot rank stocks, request broker access or trade.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCHEMA = "FUND100_P4T_OFFICIAL_2017Q1_SEC_10K_POPULATION_V1"
INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/2017/QTR1/master.idx"
REGISTRY_URL = "https://www.sec.gov/files/company_tickers.json"
HEADER = "CIK|Company Name|Form Type|Date Filed|Filename"
# Official SEC 2017-Q1 master.idx is 26,803 KiB; allow bounded raw transfer.
MAX_INDEX = 40_000_000
MAX_REGISTRY = 6_000_000
START, END = "2017-01-01", "2017-03-31"


class PopulationStop(ValueError):
    pass


def parse_index(raw: bytes) -> dict[int, dict]:
    """Validate every archived filing line; retain all original 10-K CIKs."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_INDEX:
        raise PopulationStop("Original SEC quarterly master index missing or oversized")
    try:
        lines = raw.decode("latin-1").splitlines()
        header = lines.index(HEADER)
    except (ValueError, UnicodeError) as exc:
        raise PopulationStop("Original SEC master-index header missing") from exc
    if (header < 1 or re.fullmatch(
            r"Description:\s+Master Index of EDGAR Dissemination Feed\s*",
            lines[0]) is None
        or header + 1 >= len(lines)
        or not lines[header + 1].strip()
        or set(lines[header + 1].strip()) != {"-"}):
        raise PopulationStop("Invalid SEC index identity or separator")
    found: dict[int, dict] = {}
    paths = set()
    all_rows = 0
    tenk = 0
    for line in lines[header + 2:]:
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) != 5:
            raise PopulationStop("Malformed original SEC filing row")
        cik, company, form, filed, path = fields
        if (not re.fullmatch(r"[0-9]{1,10}", cik)
            or int(cik) == 0 or not company.strip()
            or len(company) > 250 or not form.strip()
            or not START <= filed <= END
            or not re.fullmatch(r"edgar/data/[0-9]+/[0-9-]+\.txt", path)
            or int(path.split("/")[2]) != int(cik)
            or path in paths):
            raise PopulationStop("Unverifiable, duplicated or out-of-quarter SEC filing")
        paths.add(path)
        all_rows += 1
        if form == "10-K":
            tenk += 1
            ident = int(cik)
            entry = found.setdefault(ident, {"company_names": set(), "filings": []})
            entry["company_names"].add(company.strip())
            entry["filings"].append((filed, path))
    if not found or tenk != sum(len(x["filings"]) for x in found.values()):
        raise PopulationStop("No reconciled original SEC 10-K filings")
    return found


def parse_current_registry(raw: bytes) -> set[int]:
    """Current SEC ticker list is only a *comparison*, never 2017 membership."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REGISTRY:
        raise PopulationStop("Current official SEC ticker registry unavailable")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise PopulationStop("Invalid SEC ticker registry JSON") from exc
    if type(data) is not dict or not data:
        raise PopulationStop("Unexpected SEC ticker registry shape")
    ciks = set()
    tickers = set()
    for row in data.values():
        if (type(row) is not dict or type(row.get("cik_str")) is not int
            or not 0 < row["cik_str"] < 10**10
            or type(row.get("ticker")) is not str
            or not re.fullmatch(r"[A-Za-z0-9.\-]{1,15}", row["ticker"])
            or row["ticker"] in tickers):
            raise PopulationStop("Malformed or duplicate current SEC ticker identity")
        tickers.add(row["ticker"])
        ciks.add(row["cik_str"])
    return ciks


def evaluate(index_raw: bytes, registry_raw: bytes, *, captured_utc: str) -> dict:
    try:
        stamp = datetime.strptime(captured_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        if stamp.strftime("%Y-%m-%dT%H:%M:%SZ") != captured_utc or stamp.year < 2017:
            raise ValueError("invalid capture date")
    except (ValueError, TypeError) as exc:
        raise PopulationStop("Noncanonical UTC acquisition timestamp") from exc
    historic = parse_index(index_raw)
    current = parse_current_registry(registry_raw)
    historical_ciks = set(historic)
    overlap = historical_ciks & current
    unmatched = historical_ciks - current
    total = sum(len(x["filings"]) for x in historic.values())
    return {
        "schema": SCHEMA,
        "historical_index_url": INDEX_URL,
        "contemporary_registry_url": REGISTRY_URL,
        "capture_timestamp_utc": captured_utc,
        "historical_master_index_sha256": sha256(index_raw).hexdigest(),
        "contemporary_registry_sha256": sha256(registry_raw).hexdigest(),
        "original_2017_q1_10k_filing_count": total,
        "original_2017_q1_distinct_10k_ciks": len(historical_ciks),
        "2017_q1_10k_ciks_also_in_current_ticker_registry": len(overlap),
        "2017_q1_10k_ciks_absent_from_current_ticker_registry": len(unmatched),
        "cik_count_reconciled": len(overlap) + len(unmatched) == len(historical_ciks),
        "historical_population_selected_without_2026_ticker_filter": True,
        "sec_10k_filer_not_proven_historically_listed_common_stock": True,
        "current_registry_absence_not_proof_of_delisting_or_failure": True,
        "missing_historical_listing_security_master_and_total_return_prices": True,
        "no_survivorship_safe_investable_backtest_or_alpha_claim": True,
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_requests": 0,
        "broker_orders": 0,
    }


def _official_get(url: str, agent: str, limit: int) -> bytes:
    if url not in (INDEX_URL, REGISTRY_URL):
        raise PopulationStop("Only predeclared official SEC source URLs permitted")
    if (type(agent) is not str or len(agent) < 10 or "@" not in agent
        or "\r" in agent or "\n" in agent):
        raise PopulationStop("SEC contact user agent not configured")
    req = Request(url, headers={"User-Agent": agent, "Accept": "text/plain, application/json"})
    try:
        with urlopen(req, timeout=40) as response:
            if response.status != 200:
                raise PopulationStop("Official SEC source did not return HTTP 200")
            raw = response.read(limit + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise PopulationStop("Official SEC source acquisition failed") from None
    if not 0 < len(raw) <= limit:
        raise PopulationStop("Official SEC source truncated or oversized")
    return raw


def capture(output_dir: Path, agent: str) -> dict:
    """Read only SEC endpoints; write only local research artifacts."""
    original = _official_get(INDEX_URL, agent, MAX_INDEX)
    registry = _official_get(REGISTRY_URL, agent, MAX_REGISTRY)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = evaluate(original, registry, captured_utc=now)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "original-sec-2017q1-master.idx").write_bytes(original)
    (output_dir / "original-sec-current-tickers.json").write_bytes(registry)
    (output_dir / "historical-filer-census.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Official SEC filing census, no broker")
    cli.add_argument("--output-dir", required=True, type=Path)
    args = cli.parse_args()
    result = capture(args.output_dir, os.environ.get("SEC_USER_AGENT", ""))
    print(json.dumps(result, sort_keys=True))

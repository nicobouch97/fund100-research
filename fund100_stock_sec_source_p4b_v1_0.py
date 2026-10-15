"""P4B real SEC ingestion: identifiable, bounded, prospective, broker-free.

The requester MUST configure their own identifying SEC User-Agent
(org/person name + real contact email) before ANY network request.
The tool does not invent identity, contact, original document vintages,
analyst consensus revisions, universe survival or stock performance.

Fetches only the two SEC public endpoints per approved CIK, verifies
identity and data chronology, preserves raw bytes and SHA256, and computes
P4A filing-lagged descriptive quality AS OF the CURRENT retrieval date.
A re-downloaded 2026 source is not a contemporaneously archived 2016
source. Never use this to claim historical point-in-time backtesting.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_stock_sec_quality_p4a_v1_0 as quality

SCHEMA = "FUND100_PHASE4B_SEC_PROSPECTIVE_CAPTURE_V1"
UNIVERSE_PATH = Path("research_lab/stocks/p4a_contemporary_universe_2026_10_15.csv")
BASE = "https://data.sec.gov"
MAX_COMPANIES = 8
MAX_JSON_BYTES = 24_000_000
ENDPOINTS = {
    "companyfacts": "/api/xbrl/companyfacts/CIK{cik}.json",
    "submissions": "/submissions/CIK{cik}.json",
}


class SecIntakeStop(ValueError):
    pass


def contact_user_agent(value: object) -> str:
    """Requires actual configured legal contact; no default or placeholder."""
    if not isinstance(value, str) or len(value) > 150 or len(value.strip()) < 12:
        raise SecIntakeStop("SEC_USER_AGENT must identify a real organization/person and contact email.")
    if any(c in value for c in ("\n", "\r", "\x00")):
        raise SecIntakeStop("Invalid SEC contact header.")
    val = value.strip()
    chunks = val.split()
    if len(chunks) < 2 or not any(
        re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", token)
        for token in chunks[1:]
    ):
        raise SecIntakeStop("Use real SEC requester name and actual contact email.")
    if re.search(r"(example\.com|example\.org|test\.com|localhost|noreply|anonymous|replace-me)", val, re.I):
        raise SecIntakeStop("SEC_USER_AGENT must not use a placeholder identity.")
    return val


def read_cohort(path: Path = UNIVERSE_PATH) -> list[dict]:
    if not path.is_file():
        raise SecIntakeStop("Frozen contemporary research cohort missing.")
    with path.open(encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        expected = {
            "ticker", "cik_10_digit", "company_name", "illustrative_sector",
            "current_research_cohort_start", "approved_for_backtest",
            "approved_for_paper", "approved_for_live",
        }
        if set(reader.fieldnames or []) != expected:
            raise SecIntakeStop("Contemporary stock cohort data schema changed.")
        data = list(reader)
    if len(data) != MAX_COMPANIES:
        raise SecIntakeStop("Expected exactly 8 frozen research stock identities.")
    if len({r["ticker"] for r in data}) != MAX_COMPANIES or len({
        r["cik_10_digit"] for r in data
    }) != MAX_COMPANIES:
        raise SecIntakeStop("Duplicate ticker/CIK in prospective research cohort.")
    for row in data:
        if (not re.fullmatch(r"[A-Z]{1,5}", row["ticker"])
            or not re.fullmatch(r"\d{10}", row["cik_10_digit"])
            or row["current_research_cohort_start"] != "2026-10-15"
            or any(row[k] != "false" for k in (
                "approved_for_backtest", "approved_for_paper", "approved_for_live"
            ))):
            raise SecIntakeStop("Cohort contains invalid identifier or trade permission.")
    return data


def sec_url(cik: str, endpoint: str) -> str:
    if not re.fullmatch(r"\d{10}", cik) or endpoint not in ENDPOINTS:
        raise SecIntakeStop("Only fixed SEC original official API endpoints allowed.")
    return BASE + ENDPOINTS[endpoint].format(cik=cik)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_source(raw: bytes, *, expected_cik: str) -> dict:
    if not isinstance(raw, bytes) or not 2 <= len(raw) <= MAX_JSON_BYTES:
        raise SecIntakeStop("SEC source bytes missing or exceed bounded size.")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise SecIntakeStop("SEC endpoint did not deliver valid UTF-8 JSON.") from exc
    if (not isinstance(obj, dict)
        or not quality.cik_matches_expected(obj.get("cik"), expected_cik)):
        raise SecIntakeStop("SEC fetched source CIK identity mismatch.")
    return obj


def fetch_one(url: str, user_agent: str, *, opener: Callable = urlopen) -> bytes:
    contact_user_agent(user_agent)
    if not (url.startswith(BASE + "/") and
            re.fullmatch(r"https://data\.sec\.gov/(?:submissions|api/xbrl/companyfacts)/CIK\d{10}\.json", url)):
        raise SecIntakeStop("SEC request outside preapproved public API origin/path.")
    request = Request(url, headers={
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, method="GET")
    try:
        with opener(request, timeout=20) as response:
            if response.geturl() != url:
                raise SecIntakeStop("SEC endpoint redirect not approved.")
            if response.status != 200:
                raise SecIntakeStop(f"SEC public endpoint returned HTTP {response.status}.")
            content_type = response.headers.get("Content-Type", "").lower()
            if "json" not in content_type:
                raise SecIntakeStop("SEC endpoint content is not JSON.")
            raw = response.read(MAX_JSON_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SecIntakeStop(
            f"SEC source unavailable ({type(exc).__name__}); no research snapshot created."
        ) from exc
    if len(raw) > MAX_JSON_BYTES or not raw:
        raise SecIntakeStop("SEC JSON source download size invalid.")
    return raw


def collect(
    *, user_agent: str, limit: int,
    cohort: list[dict] | None = None,
    loader: Callable[[str, str], bytes] | None = None,
    captured_utc: str | None = None,
) -> tuple[dict, dict[str, bytes]]:
    """In-memory atomic cohort capture; no data written if any source fails."""
    agent = contact_user_agent(user_agent)
    cohort = read_cohort() if cohort is None else cohort
    if type(limit) is not int or not 1 <= limit <= MAX_COMPANIES:
        raise SecIntakeStop("Choose 1 through 8 frozen research companies.")
    if len(cohort) != MAX_COMPANIES:
        raise SecIntakeStop("Frozen cohort incomplete.")
    selected = cohort[:limit]
    acquired = captured_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", acquired):
        raise SecIntakeStop("Missing precise UTC acquisition timestamp.")
    asof = acquired[:10]
    quality.iso_date(asof, "capture as-of")
    # Injected loader is ONLY for deterministic offline tests. Never used
    # in deployed workflow; network path always calls fetch_one.
    get = loader or fetch_one
    observations, blobs = [], {}
    for i, row in enumerate(selected):
        cik = row["cik_10_digit"]
        paths = {k: sec_url(cik, k) for k in ENDPOINTS}
        source_bytes = {}
        for kind in ("companyfacts", "submissions"):
            raw = get(paths[kind], agent)
            decode_source(raw, expected_cik=cik)
            source_bytes[kind] = raw
            if loader is None:
                time.sleep(.3)  # far below SEC's 10 rps allowance
        facts = decode_source(source_bytes["companyfacts"], expected_cik=cik)
        sub = decode_source(source_bytes["submissions"], expected_cik=cik)
        quality.validate_identity(facts, sub, cik)
        result = quality.asof_quality(facts, sub, cik, asof)
        if result["paper_authorized"] or result["live_authorized"]:
            raise SecIntakeStop("Upstream quality engine attempted broker promotion.")
        safe_ticker = row["ticker"]
        files = {
            kind: f"raw/CIK{cik}-{safe_ticker}-{kind}.json"
            for kind in ("companyfacts", "submissions")
        }
        blobs[files["companyfacts"]] = source_bytes["companyfacts"]
        blobs[files["submissions"]] = source_bytes["submissions"]
        observations.append({
            "ticker": safe_ticker,
            "company_name": row["company_name"],
            "cik": cik,
            "quality_state": result["state"],
            "quality_score": result["score"],
            "quality_maximum": 3 if result["score"] is not None else None,
            "quality_revenue_growth_yoy": result["revenue_growth_yoy"],
            "quality_operating_margin": result["operating_margin"],
            "quality_free_cash_flow_margin": result["free_cash_flow_margin"],
            "last_eligible_fiscal_year": result["annual_asof_source_period"],
            "last_eligible_filing_accession": result["source_accession"],
            "last_eligible_filing_available_date": result["source_available_date"],
            "report_data_provenance": {
                k: {"official_url": paths[k], "raw_sha256": sha256(source_bytes[k]),
                    "source_file": files[k], "byte_count": len(source_bytes[k])}
                for k in ENDPOINTS
            },
            "raw_full_source_captured_at_utc": acquired,
            "analyst_earnings_revision_signal": None,
            "source_historical_vintage_independently_archived": False,
            "survivorship_safe_historical_backtest_eligible": False,
            "paper_authorized": False,
            "live_authorized": False,
        })
    report = {
        "schema": SCHEMA,
        "status": "PROSPECTIVE_SEC_SOURCE_CAPTURE_RESEARCH_ONLY",
        "capture_timestamp_utc": acquired,
        "contemporary_cohort_started": "2026-10-15",
        "observation_asof_utc_date": asof,
        "selection_is_contemporary_survivor_biased_if_backtested_historically": True,
        "raw_current_sec_download_is_not_historical_archived_source_vintage": True,
        "filing_lag_2_weekdays_is_proxy_not_verified_legal_availability": True,
        "market_prices_and_corporate_actions_not_included": True,
        "analyst_estimates_and_revisions_not_included": True,
        "full_universe_survey_not_yet_performed": limit < MAX_COMPANIES,
        "source_count": len(blobs),
        "companies_attempted": limit,
        "companies": observations,
        "broker_orders": 0, "paper_authorized": False, "live_authorized": False,
    }
    return report, blobs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--limit", type=int, default=2)
    args = p.parse_args()
    # NEVER print contact email or response body in logs.
    agent = contact_user_agent(os.environ.get("SEC_USER_AGENT", ""))
    report, blobs = collect(user_agent=agent, limit=args.limit)
    directory = Path(args.output_dir)
    if directory.exists() and any(directory.iterdir()):
        raise SecIntakeStop("Refuse to overwrite an existing archived source capture.")
    for name, data in blobs.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (directory / "manifest-and-quality.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("P4B real captured SEC API facts:", report["source_count"],
          "for", report["companies_attempted"], "contemporary companies.")
    print("Snapshot acquired UTC:", report["capture_timestamp_utc"])
    print("Missing SEC financial values remain unavailable; no analyst revisions.")
    print("PAPER/LIVE orders and permissions: ZERO.")


if __name__ == "__main__":
    main()

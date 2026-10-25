"""P4U: source-backed 2017 10-K cover-page listing evidence, research only.

A historical SEC filer CIK is not a listed share. This deliberately small,
predeclared, reproducible source audit samples original 2017 10-K submissions
from BOTH contemporary-registry strata. It is NOT a historical security
master, a population estimate, a delisting census, or a trading backtest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fund100_stock_historical_sec_population_p4t_v1_0 import parse_current_registry

SCHEMA = "FUND100_P4U_2017_ORIGINAL_10K_COVER_SOURCE_AUDIT_V1"
MAX_FILING_BYTES = 12_000_000
MAX_SAMPLES_PER_STRATUM = 8
ARCHIVE_PATH = re.compile(r"edgar/data/([0-9]+)/([0-9-]+)\.txt\Z")
SEC_PREFIX = "https://www.sec.gov/Archives/"
SECTION_B = re.compile(
    r"securities\s+registered\s+pursuant\s+to\s+section\s*12\s*\(\s*b\s*\)",
    re.IGNORECASE)
SECTION_G = re.compile(
    r"securities\s+registered\s+pursuant\s+to\s+section\s*12\s*\(\s*g\s*\)",
    re.IGNORECASE)
COMMON = re.compile(r"\bcommon\s+(?:stock|shares)\b", re.IGNORECASE)
EXCHANGE = re.compile(
    r"\b(?:new\s+york\s+stock\s+exchange|nasdaq(?:\s+(?:global|capital|stock))?"
    r"|nyse(?:\s+(?:mkt|american|arca))?|american\s+stock\s+exchange)\b",
    re.IGNORECASE)


class ListingEvidenceStop(ValueError):
    pass


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise ListingEvidenceStop("Original P4T source artifact missing")
    return path.read_bytes()


def select_sample(source_dir: Path, *, per_stratum: int = 6) -> tuple[list[dict], dict]:
    """Predeclare a CIK-deduplicated, SHA-ranked stratified diagnostic sample.

    Present-day registry membership is used ONLY to stratify the audit, not
    to define historical investment eligibility or infer delistings.
    """
    if type(per_stratum) is not int or not 1 <= per_stratum <= MAX_SAMPLES_PER_STRATUM:
        raise ListingEvidenceStop("Invalid bounded historical cover sample size")
    try:
        annual = json.loads(_read(source_dir / "historical-2017-annual-filer-census.json"))
        raw_manifest = _read(source_dir / "historical-2017-10k-filings.jsonl")
        registry_raw = _read(source_dir / "original-sec-current-tickers.json")
        if (annual["historical_filing_manifest_sha256"] != sha256(raw_manifest).hexdigest()
            or annual["contemporary_registry_sha256"] != sha256(registry_raw).hexdigest()):
            raise ListingEvidenceStop("P4T original-source hash mismatch")
        rows = [json.loads(line) for line in raw_manifest.decode("utf-8").splitlines()]
        if (len(rows) != annual["historical_filing_manifest_rows"]
            or len({r["cik"] for r in rows}) != annual["annual_distinct_10k_ciks"]):
            raise ListingEvidenceStop("P4T original accession/issuer reconciliation failed")
        current = parse_current_registry(registry_raw)
        first_by_cik: dict[int, dict] = {}
        paths = set()
        for row in rows:
            if (type(row) is not dict
                or set(row) != {"cik", "company_name_in_original_index",
                                "filing_date", "quarter", "sec_archive_path"}
                or type(row["cik"]) is not int or row["cik"] <= 0
                or not re.fullmatch(r"2017-\d\d-\d\d", row["filing_date"])
                or row["quarter"] not in {"2017_Q1", "2017_Q2", "2017_Q3", "2017_Q4"}
                or type(row["company_name_in_original_index"]) is not str
                or not row["company_name_in_original_index"].strip()
                or type(row["sec_archive_path"]) is not str):
                raise ListingEvidenceStop("Invalid historical filing identity")
            m = ARCHIVE_PATH.fullmatch(row["sec_archive_path"])
            if (m is None or int(m.group(1)) != row["cik"]
                or row["sec_archive_path"] in paths):
                raise ListingEvidenceStop("Invalid or repeated historical SEC accession path")
            paths.add(row["sec_archive_path"])
            cik = row["cik"]
            if cik not in first_by_cik or (
                    row["filing_date"], row["sec_archive_path"]) < (
                    first_by_cik[cik]["filing_date"],
                    first_by_cik[cik]["sec_archive_path"]):
                first_by_cik[cik] = row
        groups = {"in_current_registry": [], "absent_from_current_registry": []}
        for cik, row in first_by_cik.items():
            group = ("in_current_registry" if cik in current
                     else "absent_from_current_registry")
            groups[group].append(row)
        if any(len(g) < per_stratum for g in groups.values()):
            raise ListingEvidenceStop("Insufficient historical source sample stratum")
        selected = []
        for group in sorted(groups):
            ranked = sorted(groups[group], key=lambda row: (
                sha256(("P4U-2017-FIXED-SEED|" + row["sec_archive_path"]).encode()).hexdigest(),
                row["cik"]))
            for row in ranked[:per_stratum]:
                selected.append({**row, "current_registry_stratum": group})
        selected.sort(key=lambda row: (row["current_registry_stratum"], row["cik"]))
        return selected, annual
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        if isinstance(exc, ListingEvidenceStop):
            raise
        raise ListingEvidenceStop("P4T source manifest invalid") from exc


def inspect_original_10k(raw: bytes) -> dict:
    """Conservative text diagnostic; does not approve an investable security."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FILING_BYTES:
        raise ListingEvidenceStop("Original filing missing or oversized")
    tenk = None
    for match in re.finditer(rb"<DOCUMENT>(.*?)</DOCUMENT>", raw, re.IGNORECASE | re.DOTALL):
        doc = match.group(1)
        if re.search(rb"(?im)<TYPE>\s*10-K\s*(?:\r?\n|<)", doc):
            tenk = doc
            break
    if tenk is None:
        return {"cover_state": "NO_VERIFIED_ORIGINAL_10K_DOCUMENT",
                "section_12b_excerpt": ""}
    match = re.search(rb"<TEXT>(.*?)</TEXT>", tenk, re.IGNORECASE | re.DOTALL)
    if match is None:
        return {"cover_state": "NO_VERIFIED_10K_TEXT",
                "section_12b_excerpt": ""}
    cover = match.group(1)[:250_000].decode("latin-1", errors="replace")
    cover = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", cover)
    clean = unescape(re.sub(r"(?s)<[^>]+>", " ", cover))
    clean = re.sub(r"\s+", " ", clean)
    heading = SECTION_B.search(clean)
    if heading is None:
        return {"cover_state": "SECTION_12B_NOT_LOCATED_IN_COVER",
                "section_12b_excerpt": ""}
    block = clean[heading.end():heading.end() + 6000]
    end = SECTION_G.search(block)
    if end is not None:
        block = block[:end.start()]
    # A joint textual mention is NOT an authenticated class-to-exchange
    # mapping: debt may share a cover table with common shares. Human
    # row-level review and independent listing records remain mandatory.
    possible = bool(COMMON.search(block) and EXCHANGE.search(block))
    return {
        "cover_state": ("POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED"
                        if possible else "NO_JOINT_12B_COMMON_EXCHANGE_TEXT_EVIDENCE"),
        "section_12b_excerpt": block[:1200],
    }


def _official_filing_get(path: str, agent: str) -> bytes:
    if (type(path) is not str or ARCHIVE_PATH.fullmatch(path) is None
        or type(agent) is not str or len(agent) < 10
        or "@" not in agent or "\r" in agent or "\n" in agent):
        raise ListingEvidenceStop("Unapproved original SEC filing request")
    url = SEC_PREFIX + path
    try:
        with urlopen(Request(url, headers={
                "User-Agent": agent, "Accept": "text/plain"}), timeout=35) as response:
            if response.status != 200 or response.geturl() != url:
                raise ListingEvidenceStop("SEC filing source response not authenticated")
            raw = response.read(MAX_FILING_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ListingEvidenceStop("Original SEC filing request unavailable") from exc
    if not 0 < len(raw) <= MAX_FILING_BYTES:
        raise ListingEvidenceStop("Original SEC filing unavailable or oversized")
    return raw


def capture(source_dir: Path, output_dir: Path, agent: str,
            *, per_stratum: int = 6, getter=None) -> dict:
    selected, annual = select_sample(source_dir, per_stratum=per_stratum)
    if getter is None:
        getter = _official_filing_get
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = []
    for row in selected:
        result = {**row, "original_filing_url": SEC_PREFIX + row["sec_archive_path"]}
        try:
            raw = getter(row["sec_archive_path"], agent)
            if type(raw) is not bytes or not 0 < len(raw) <= MAX_FILING_BYTES:
                raise ListingEvidenceStop("Original SEC filing source invalid")
            evidence = inspect_original_10k(raw)
            filename = "original-10k-" + str(row["cik"]) + "-" + (
                row["sec_archive_path"].split("/")[-1])
            (output_dir / filename).write_bytes(raw)
            result.update({
                "source_state": "ORIGINAL_10K_BYTES_CAPTURED",
                "original_sha256": sha256(raw).hexdigest(),
                "original_bytes": len(raw),
                "local_original_file": filename,
                **evidence,
            })
        except ListingEvidenceStop:
            result.update({
                "source_state": "SOURCE_UNAVAILABLE_OR_UNVERIFIABLE",
                "cover_state": "NOT_EVALUATED",
            })
        observations.append(result)
    count = sum(r["source_state"] == "ORIGINAL_10K_BYTES_CAPTURED"
                for r in observations)
    report = {
        "schema": SCHEMA,
        "capture_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "p4t_manifest_sha256": annual["historical_filing_manifest_sha256"],
        "historical_issuer_population": annual["annual_distinct_10k_ciks"],
        "sample_per_current_registry_stratum": per_stratum,
        "predeclared_filing_samples": len(selected),
        "original_filing_sources_captured": count,
        "unavailable_or_unverifiable_sources": len(selected) - count,
        "possible_section12b_common_equity_exchange_covers": sum(
            r["cover_state"] == "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED"
            for r in observations),
        "sample_not_universe_or_delisting_estimate": True,
        "cover_text_not_independent_listing_or_security_master": True,
        "no_verified_historical_total_returns_or_investable_backtest": True,
        "research_only": True,
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_requests": 0,
        "broker_orders": 0,
        "observations": observations,
    }
    (output_dir / "historical-2017-original-cover-evidence.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--source-dir", type=Path, required=True)
    cli.add_argument("--output-dir", type=Path, required=True)
    cli.add_argument("--per-stratum", type=int, default=6)
    args = cli.parse_args()
    result = capture(args.source_dir, args.output_dir,
                     os.environ.get("SEC_USER_AGENT", ""),
                     per_stratum=args.per_stratum)
    print("P4U original 2017 10-K cover source audit:",
          result["original_filing_sources_captured"], "verified source captures of",
          result["predeclared_filing_samples"], "predeclared samples;",
          result["possible_section12b_common_equity_exchange_covers"],
          "possible Section 12(b) common-share/exchange mentions, REVIEW REQUIRED.")
    print("NO historical listed-security eligibility, alpha, broker access or orders.")

"""P4T: official 2017-Q1 SEC 10-K filing-population census, NOT a stock backtest.

Start with every 10-K in an archived EDGAR quarter instead of selecting
companies that survive in today's ticker list. An EDGAR filer is NOT proof
of a historically exchange-listed, liquid, investable common share.
Absence from the current SEC ticker registry is NOT proof of delisting.
This source-only study cannot rank stocks, request broker access or trade.
"""
from __future__ import annotations

import argparse
from calendar import monthrange
from datetime import date, datetime, timezone
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
INDEX_URLS = {q: f"https://www.sec.gov/Archives/edgar/full-index/2017/QTR{q}/master.idx"
              for q in (1, 2, 3, 4)}
QUARTER_BOUNDS = {
    1: ("2017-01-01", "2017-03-31"),
    2: ("2017-04-01", "2017-06-30"),
    3: ("2017-07-01", "2017-09-30"),
    4: ("2017-10-01", "2017-12-31"),
}
ANNUAL_SCHEMA = "FUND100_P4T_ORIGINAL_2017_FULL_YEAR_10K_CENSUS_V1"


class PopulationStop(ValueError):
    pass


def parse_index(raw: bytes, *, quarter: int = 1) -> dict[int, dict]:
    """Validate original 10-K filings in a specified 2017 SEC quarter."""
    if type(quarter) is not int or quarter not in QUARTER_BOUNDS:
        raise PopulationStop("Unsupported original SEC quarter")
    start, end = QUARTER_BOUNDS[quarter]
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
        # A full SEC master index includes hundreds of thousands of other
        # forms. The research population is strictly original 10-K filings;
        # non-10-K filing-agent metadata must not censor this cohort.
        all_rows += 1
        if form != "10-K":
            continue
        if (not re.fullmatch(r"[0-9]{1,10}", cik)
            or int(cik) == 0 or not company.strip()
            or len(company) > 250 or not form.strip()
            or not start <= filed <= end
            or not re.fullmatch(r"edgar/data/[0-9]+/[0-9-]+\.txt", path)
            or int(path.split("/")[2]) != int(cik)
            or path in paths):
            raise PopulationStop("Unverifiable, duplicated or out-of-quarter SEC filing")
        paths.add(path)
        tenk += 1
        ident = int(cik)
        entry = found.setdefault(ident, {
            "company_names": set(), "filings": [], "filing_names": {}})
        entry["company_names"].add(company.strip())
        entry["filings"].append((filed, path))
        # Keep the filing-date name attached to its accession, including
        # historical renames; a set of names alone loses that relationship.
        entry["filing_names"][path] = company.strip()
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
    if url not in (*INDEX_URLS.values(), REGISTRY_URL):
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


def annual_filing_manifest(index_by_quarter: dict[int, bytes]) -> list[dict]:
    """Original 2017 10-K accession-level identity, without a present-day ticker join.

    CIK is an SEC issuer identifier, not a security/share-class identifier.
    The filing index name and date are original-source observations; neither
    exchange listing nor executable stock returns are established here.
    """
    if (type(index_by_quarter) is not dict
        or set(index_by_quarter) != set(QUARTER_BOUNDS)
        or any(type(q) is not int for q in index_by_quarter)):
        raise PopulationStop("Exactly four original 2017 quarter indexes required")
    rows = []
    paths = set()
    for quarter in sorted(QUARTER_BOUNDS):
        cohort = parse_index(index_by_quarter[quarter], quarter=quarter)
        for cik, entry in cohort.items():
            for filed, path in entry["filings"]:
                if path in paths:
                    raise PopulationStop("Repeated SEC accession across quarters")
                paths.add(path)
                rows.append({
                    "cik": cik,
                    "company_name_in_original_index": entry["filing_names"][path],
                    "filing_date": filed,
                    "quarter": f"2017_Q{quarter}",
                    "sec_archive_path": path,
                })
    rows.sort(key=lambda r: (r["filing_date"], r["cik"], r["sec_archive_path"]))
    return rows


def _manifest_bytes(rows: list[dict]) -> bytes:
    """Stable UTF-8 JSONL bytes; independent of SEC registry capture vintage."""
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
        for row in rows
    ).encode("utf-8")



def first_2017_10k_filing_events(rows: list[dict]) -> list[dict]:
    """Earliest ORIGINAL 2017 10-K per issuer, never a historical listing date.

    The annual census contains all four quarters, so using its full-year
    membership at a January or March decision would leak later filings.
    This is a dated *2017 filing-observation* bridge only. A CIK can have
    filed before 2017, can represent multiple securities, and may not have
    had listed common stock at any time in 2017.
    """
    if type(rows) is not list or not rows:
        raise PopulationStop("Missing original annual 10-K filing manifest")
    first = {}
    seen_paths = set()
    expected = {"cik", "company_name_in_original_index", "filing_date",
                "quarter", "sec_archive_path"}
    for row in rows:
        if type(row) is not dict or set(row) != expected:
            raise PopulationStop("Malformed original 2017 filing event")
        cik, filed, path = row["cik"], row["filing_date"], row["sec_archive_path"]
        if (type(cik) is not int or not 0 < cik < 10**10
            or type(filed) is not str or type(path) is not str
            or type(row["company_name_in_original_index"]) is not str
            or not row["company_name_in_original_index"].strip()
            or not re.fullmatch(r"edgar/data/[0-9]+/[0-9-]+\\.txt", path)
            or int(path.split("/")[2]) != cik or path in seen_paths):
            raise PopulationStop("Unverifiable original 2017 filing event")
        try:
            day = date.fromisoformat(filed)
        except ValueError as exc:
            raise PopulationStop("Invalid original 2017 filing date") from exc
        if (day.year != 2017 or day.isoformat() != filed
            or row["quarter"] != f"2017_Q{(day.month - 1) // 3 + 1}"):
            raise PopulationStop("Original filing date/quarter mismatch")
        seen_paths.add(path)
        event = {
            "cik": cik,
            "first_observed_2017_10k_filing_date": filed,
            "first_observed_2017_10k_archive_path": path,
        }
        if (cik not in first or
            (filed, path) < (first[cik]["first_observed_2017_10k_filing_date"],
                             first[cik]["first_observed_2017_10k_archive_path"])):
            first[cik] = event
    return sorted(first.values(), key=lambda row: (
        row["first_observed_2017_10k_filing_date"], row["cik"]))


def month_end_2017_filing_observability(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Twelve as-of counts, excluding SAME-DAY filings with unknown release time.

    The conservative cutoff is the start of the calendar month-end date.
    A first observed 2017 10-K on that date is not available in this
    diagnostic until the next cutoff. No filing absence is an issuer exit.
    """
    events = first_2017_10k_filing_events(rows)
    total = len(events)
    panel = []
    prior_seen = 0
    for month in range(1, 13):
        cutoff = date(2017, month, monthrange(2017, month)[1]).isoformat()
        seen = sum(e["first_observed_2017_10k_filing_date"] < cutoff for e in events)
        filings_seen = sum(r["filing_date"] < cutoff for r in rows)
        if not prior_seen <= seen <= total or filings_seen < seen:
            raise PopulationStop("Historical filing observability reconciliation failed")
        panel.append({
            "asof_month_end_date": cutoff,
            "cutoff_convention": "ONLY_FILINGS_DATED_BEFORE_ASOF_DATE",
            "distinct_ciks_with_2017_10k_observed_before_cutoff": seen,
            "original_2017_10k_filings_observed_before_cutoff": filings_seen,
            "newly_observed_2017_10k_ciks_since_prior_month_end": seen - prior_seen,
            "future_or_same_day_2017_first_10k_ciks_excluded": total - seen,
        })
        prior_seen = seen
    return events, panel


def evaluate_annual(index_by_quarter: dict[int, bytes], registry_raw: bytes,
                    *, captured_utc: str) -> dict:
    """Reconcile all 2017 10-K filings and preserve a source-bound issuer manifest.

    This is an issuer/filing population, NOT a point-in-time listed-stock
    universe or an investable survivorship-safe backtest.
    """
    first = evaluate(index_by_quarter[1], registry_raw, captured_utc=captured_utc) if (
        type(index_by_quarter) is dict and 1 in index_by_quarter
    ) else None
    rows = annual_filing_manifest(index_by_quarter)
    current = parse_current_registry(registry_raw)
    all_ciks = {r["cik"] for r in rows}
    all_paths = {r["sec_archive_path"] for r in rows}
    counts = {f"2017_Q{q}": sum(r["quarter"] == f"2017_Q{q}" for r in rows)
              for q in QUARTER_BOUNDS}
    distinct = {f"2017_Q{q}": len({
        r["cik"] for r in rows if r["quarter"] == f"2017_Q{q}"})
        for q in QUARTER_BOUNDS}
    hashes = {f"2017_Q{q}": sha256(index_by_quarter[q]).hexdigest()
              for q in QUARTER_BOUNDS}
    q1_ciks = {r["cik"] for r in rows if r["quarter"] == "2017_Q1"}
    total = len(rows)
    if (first is None or total != len(all_paths)
        or counts["2017_Q1"] != first["original_2017_q1_10k_filing_count"]
        or distinct["2017_Q1"] != first["original_2017_q1_distinct_10k_ciks"]
        or not q1_ciks.issubset(all_ciks)):
        raise PopulationStop("Original SEC annual filing reconciliation failed")
    overlap = all_ciks & current
    absent = all_ciks - current
    manifest = _manifest_bytes(rows)
    first_events, dated_panel = month_end_2017_filing_observability(rows)
    first_event_manifest = _manifest_bytes(first_events)
    if (len(first_events) != len(all_ciks)
        or dated_panel[-1]["distinct_ciks_with_2017_10k_observed_before_cutoff"]
           > len(all_ciks)):
        raise PopulationStop("Dated SEC issuer observation reconciliation failed")
    return {
        "schema": ANNUAL_SCHEMA,
        "source_index_urls": {f"2017_Q{q}": INDEX_URLS[q] for q in QUARTER_BOUNDS},
        "capture_timestamp_utc": captured_utc,
        "quarter_source_sha256": hashes,
        "contemporary_registry_url": REGISTRY_URL,
        "contemporary_registry_sha256": sha256(registry_raw).hexdigest(),
        "quarter_10k_filing_counts": counts,
        "quarter_distinct_10k_ciks": distinct,
        "annual_10k_filing_count": total,
        "annual_distinct_10k_ciks": len(all_ciks),
        "annual_ciks_also_in_current_ticker_registry": len(overlap),
        "annual_ciks_absent_from_current_ticker_registry": len(absent),
        "annual_new_ciks_outside_q1": len(all_ciks - q1_ciks),
        "annual_filing_and_cik_counts_reconciled": (
            total == len(all_paths) and len(overlap) + len(absent) == len(all_ciks)),
        "historical_filing_manifest_file": "historical-2017-10k-filings.jsonl",
        "historical_filing_manifest_sha256": sha256(manifest).hexdigest(),
        "historical_filing_manifest_rows": len(rows),
        "historical_filing_manifest_distinct_ciks": len(all_ciks),
        "historical_filing_manifest_uses_current_tickers": False,
        "first_observed_2017_10k_events_file": "historical-2017-first-10k-events.jsonl",
        "first_observed_2017_10k_events_sha256": sha256(first_event_manifest).hexdigest(),
        "first_observed_2017_10k_event_ciks": len(first_events),
        "month_end_asof_2017_filing_observability": dated_panel,
        "asof_cutoff_excludes_same_day_unknown_release_time": True,
        "first_observed_2017_10k_not_first_ever_filing_or_listing": True,
        "2017_filing_observability_not_investable_stock_universe": True,
        "historical_population_selected_without_2026_ticker_filter": True,
        "current_registry_absence_not_proof_of_delisting_or_failure": True,
        "quarterly_10k_absence_not_proof_of_company_exit": True,
        "sec_10k_filer_not_proven_historically_listed_common_stock": True,
        "missing_historical_listing_security_master_and_total_return_prices": True,
        "no_survivorship_safe_investable_backtest_or_alpha_claim": True,
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_requests": 0,
        "broker_orders": 0,
    }



# SEC master.idx identifies Form 25 filing *events*, not the security class,
# exchange action, effective delisting date, or an investment return.
FORM25_FORMS = ("25", "25/A", "25-NSE", "25-NSE/A")
FORM25_INDEX_SCHEMA = "FUND100_P4X_ORIGINAL_2017_FORM25_INDEX_EVIDENCE_V1"


def form25_index_manifest(index_by_quarter: dict[int, bytes]) -> list[dict]:
    """Link original Form 25 index entries to the 2017 10-K filer CIK cohort.

    Keep every original accession, including amendments and exchange-filed
    25-NSE records. A matching issuer CIK is NOT evidence that its common
    shares were delisted: a Form 25 may concern a bond or other security.
    The dated 10-K crosscheck prevents later filings being represented as
    information already available on the Form 25 filing date.
    """
    tenk = annual_filing_manifest(index_by_quarter)
    tenk_dates: dict[int, list[str]] = {}
    for row in tenk:
        tenk_dates.setdefault(row["cik"], []).append(row["filing_date"])
    events = []
    seen = set()
    for quarter in sorted(QUARTER_BOUNDS):
        raw = index_by_quarter[quarter]
        # Reuse the strict original quarter/header/10-K source validation.
        parse_index(raw, quarter=quarter)
        lines = raw.decode("latin-1").splitlines()
        start, end = QUARTER_BOUNDS[quarter]
        for line in lines[lines.index(HEADER) + 2:]:
            if not line.strip():
                continue
            fields = line.split("|")
            if len(fields) != 5:
                raise PopulationStop("Malformed original SEC index event row")
            cik, name, form, filed, path = fields
            if form not in FORM25_FORMS:
                continue
            if (not re.fullmatch(r"[0-9]{1,10}", cik)
                or int(cik) == 0 or not name.strip() or len(name) > 250
                or not start <= filed <= end
                or not re.fullmatch(r"edgar/data/[0-9]+/[0-9-]+\.txt", path)
                or int(path.split("/")[2]) != int(cik) or path in seen):
                raise PopulationStop("Unverifiable or duplicated original Form 25 index entry")
            seen.add(path)
            issuer = int(cik)
            events.append({
                "filer_cik": issuer,
                "filer_name_in_original_index": name.strip(),
                "form_type": form,
                "filing_date": filed,
                "quarter": f"2017_Q{quarter}",
                "sec_archive_path": path,
                "same_cik_in_full_2017_10k_filer_population": issuer in tenk_dates,
                "same_cik_10k_filed_on_or_before_form25": any(
                    date <= filed for date in tenk_dates.get(issuer, [])),
            })
    events.sort(key=lambda row: (
        row["filing_date"], row["filer_cik"], row["sec_archive_path"]))
    return events


def evaluate_form25_index(index_by_quarter: dict[int, bytes]) -> dict:
    """Source-bound index-only event census; NEVER a common-share exit census."""
    events = form25_index_manifest(index_by_quarter)
    payload = _manifest_bytes(events)
    forms = {form: sum(row["form_type"] == form for row in events)
             for form in FORM25_FORMS}
    matched = [row for row in events
               if row["same_cik_in_full_2017_10k_filer_population"]]
    prior = [row for row in matched
             if row["same_cik_10k_filed_on_or_before_form25"]]
    return {
        "schema": FORM25_INDEX_SCHEMA,
        "source_index_sha256": {
            f"2017_Q{quarter}": sha256(index_by_quarter[quarter]).hexdigest()
            for quarter in QUARTER_BOUNDS
        },
        "original_form25_manifest_file": "historical-2017-form25-index-events.jsonl",
        "original_form25_manifest_sha256": sha256(payload).hexdigest(),
        "original_form25_index_entries": len(events),
        "form_type_index_entries": forms,
        "original_form25_distinct_filer_ciks": len({
            row["filer_cik"] for row in events}),
        # 25 is issuer-filed; 25-NSE is exchange-filed. The SEC index
        # CIK is not independently verified as the affected share issuer.
        "form25_filing_role_counts": {
            "issuer_filed_including_amendments": sum(
                row["form_type"] in {"25", "25/A"} for row in events),
            "exchange_filed_including_amendments": sum(
                row["form_type"] in {"25-NSE", "25-NSE/A"} for row in events),
        },
        "form25_role_10k_cik_overlap": {
            role: {
                "index_entries": len(group),
                "same_cik_2017_10k_entries": sum(
                    row["same_cik_in_full_2017_10k_filer_population"]
                    for row in group),
                "same_cik_prior_or_same_day_10k_entries": sum(
                    row["same_cik_10k_filed_on_or_before_form25"]
                    for row in group),
                "same_cik_2017_10k_distinct_ciks": len({
                    row["filer_cik"] for row in group
                    if row["same_cik_in_full_2017_10k_filer_population"]}),
            }
            for role, group in (
                ("issuer_filed_25", [
                    row for row in events if row["form_type"] in {"25", "25/A"}]),
                ("exchange_filed_25_nse", [
                    row for row in events if row["form_type"] in {"25-NSE", "25-NSE/A"}]))
        },
        "form25_exchange_filed_index_cik_not_proof_of_issuer": True,
        "same_cik_2017_10k_filer_index_entries": len(matched),
        "same_cik_2017_10k_filer_distinct_ciks": len({
            row["filer_cik"] for row in matched}),
        "same_cik_prior_or_same_day_10k_index_entries": len(prior),
        "current_ticker_registry_not_used": True,
        "form25_filing_date_not_effective_delisting_date": True,
        "form25_index_does_not_identify_security_class_or_common_stock": True,
        "exchange_25_nse_and_amendments_not_deduplicated_as_exits": True,
        "same_cik_not_proof_of_delisting_or_investability": True,
        "original_form25_documents_not_examined": True,
        "no_delisting_adjusted_total_return_or_investable_alpha": True,
        "broker_requests": 0, "broker_orders": 0,
        "paper_authorized": False, "live_authorized": False,
    }



def capture_annual(output_dir: Path, agent: str, *, form25_documents: bool = False) -> dict:
    """Read four official SEC quarter indexes; preserve raw reproducible bytes."""
    first = capture(output_dir, agent)
    original = {1: (output_dir / "original-sec-2017q1-master.idx").read_bytes()}
    for quarter in (2, 3, 4):
        original[quarter] = _official_get(INDEX_URLS[quarter], agent, MAX_INDEX)
    registry = (output_dir / "original-sec-current-tickers.json").read_bytes()
    report = evaluate_annual(
        original, registry, captured_utc=first["capture_timestamp_utc"])
    manifest = _manifest_bytes(annual_filing_manifest(original))
    if (sha256(manifest).hexdigest() != report["historical_filing_manifest_sha256"]
        or manifest.count(b"\n") != report["historical_filing_manifest_rows"]):
        raise PopulationStop("Original SEC accession manifest reconciliation failed")
    for quarter in (2, 3, 4):
        (output_dir / f"original-sec-2017q{quarter}-master.idx").write_bytes(
            original[quarter])
    first_events, panel = month_end_2017_filing_observability(
        annual_filing_manifest(original))
    first_event_bytes = _manifest_bytes(first_events)
    if (sha256(first_event_bytes).hexdigest() !=
            report["first_observed_2017_10k_events_sha256"]
        or len(first_events) != report["first_observed_2017_10k_event_ciks"]
        or panel != report["month_end_asof_2017_filing_observability"]):
        raise PopulationStop("Dated original filing manifest reconciliation failed")
    (output_dir / report["first_observed_2017_10k_events_file"]).write_bytes(
        first_event_bytes)
    (output_dir / report["historical_filing_manifest_file"]).write_bytes(manifest)
    (output_dir / "historical-2017-annual-filer-census.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    form25 = evaluate_form25_index(original)
    form25_manifest = _manifest_bytes(form25_index_manifest(original))
    if (sha256(form25_manifest).hexdigest() != form25["original_form25_manifest_sha256"]
        or form25_manifest.count(b"\n") != form25["original_form25_index_entries"]):
        raise PopulationStop("Original Form 25 index evidence reconciliation failed")
    (output_dir / form25["original_form25_manifest_file"]).write_bytes(form25_manifest)
    (output_dir / "historical-2017-form25-index-census.json").write_text(
        json.dumps(form25, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if form25_documents:
        # Original-source only: 8 issuer-filed and 8 exchange-filed
        # non-amendment filings. Never an order or an exit classification.
        from fund100_stock_historical_sec_form25_p4y_v1_0 import capture_original_sample
        capture_original_sample(output_dir, agent)
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Official SEC filing census, no broker")
    cli.add_argument("--output-dir", required=True, type=Path)
    cli.add_argument("--annual-2017", action="store_true",
                     help="Capture all four 2017 quarters, preserving Q1 legacy census")
    args = cli.parse_args()
    agent = os.environ.get("SEC_USER_AGENT", "")
    result = (capture_annual(args.output_dir, agent, form25_documents=True) if args.annual_2017
              else capture(args.output_dir, agent))
    print(json.dumps(result, sort_keys=True))

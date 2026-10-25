"""P4U: source-backed 2017 10-K cover-page listing evidence, research only.

A historical SEC filer CIK is not a listed share. This bounded,
predeclared, reproducible source audit samples original 2017 10-K submissions
from BOTH contemporary-registry strata. It is NOT a historical security
master, a population estimate, a delisting census, or a trading backtest.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fund100_stock_historical_sec_population_p4t_v1_0 import parse_current_registry

SCHEMA = "FUND100_P4U_2017_ORIGINAL_10K_COVER_SOURCE_AUDIT_V1"
MAX_FILING_BYTES = 12_000_000
MAX_FILING_INDEX_BYTES = 2_000_000
MAX_SAMPLES_PER_STRATUM = 16
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


class FilingSourceFailure(ListingEvidenceStop):
    """Fixed non-sensitive reason code; never expose HTTP headers or credentials."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise ListingEvidenceStop("Original P4T source artifact missing")
    return path.read_bytes()


def select_sample(source_dir: Path, *, per_stratum: int = 16) -> tuple[list[dict], dict]:
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


def _inspect_cover_text(cover: str) -> dict:
    cover = cover[:250_000]
    cover = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", cover)
    clean = unescape(re.sub(r"(?s)<[^>]+>", " ", cover))
    clean = re.sub(r"\s+", " ", clean)
    # Section 12(g) can contain a common-share class even where 12(b)
    # explicitly says "None" (observed in the original 2017 10-K sample).
    # 12(g) registration alone does NOT establish exchange listing.
    section_g = SECTION_G.search(clean)
    g_block = (clean[section_g.end():section_g.end() + 350]
               if section_g is not None else "")
    g_block = re.split(r"(?i)indicate\s+by\s+check\s+mark", g_block)[0]
    g_common = bool(COMMON.search(g_block))
    heading = SECTION_B.search(clean)
    if heading is None:
        return {"cover_state": "SECTION_12B_NOT_LOCATED_IN_COVER",
                "section_12b_excerpt": "",
                "section12g_common_class_review_required": g_common}
    block = clean[heading.end():heading.end() + 6000]
    end = SECTION_G.search(block)
    if end is not None:
        block = block[:end.start()]
    # A flattened 12(b) table can falsely pair a debt security's NYSE
    # cell with common stock on a DIFFERENT row. Keep original HTML row
    # boundaries while normalising source whitespace; a joint mention must
    # occur within one row, not merely within the same 6,000-character block.
    # For unstructured prose, the result is still only a review flag.
    row_markup = re.sub(r"\s+", " ", cover)
    row_markup = re.sub(r"(?i)</tr\s*>", "\n", row_markup)
    row_text = unescape(re.sub(r"(?s)<[^>]+>", " ", row_markup))
    row_text = re.sub(r"[^\S\n]+", " ", row_text)
    row_heading = SECTION_B.search(row_text)
    row_block = (row_text[row_heading.end():row_heading.end() + 6000]
                 if row_heading is not None else "")
    row_end = SECTION_G.search(row_block)
    if row_end is not None:
        row_block = row_block[:row_end.start()]
    direct = any(COMMON.search(row) and EXCHANGE.search(row)
                 for row in row_block.splitlines())
    cross_row = bool(COMMON.search(block) and EXCHANGE.search(block) and not direct)
    # The 2017 Multi-Color 10-K puts "NASDAQ Global Select Market"
    # immediately BEFORE the 12(b) heading and "Common Stock" after it.
    # Preserve this as a distinct, weaker cover-layout review flag.
    preceding = bool(COMMON.search(block) and not direct and
                     EXCHANGE.search(clean[max(0, heading.start() - 300):heading.start()]))
    if direct:
        state = "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED"
    elif preceding:
        state = "POSSIBLE_12B_COMMON_PRECEDING_EXCHANGE_REVIEW_REQUIRED"
    elif cross_row:
        state = "AMBIGUOUS_12B_CROSS_ROW_COMMON_EXCHANGE_REVIEW_REQUIRED"
    else:
        state = "NO_JOINT_12B_COMMON_EXCHANGE_TEXT_EVIDENCE"
    # Neither flag proves a share-class/exchange mapping or an investable
    # security. Historical listing records and corporate actions are needed.
    return {
        "cover_state": state,
        "section_12b_excerpt": block[:1200],
        "section12g_common_class_review_required": g_common,
    }



def inspect_original_10k(raw: bytes) -> dict:
    """Inspect a 10-K document explicitly identified inside an original submission."""
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
    return _inspect_cover_text(match.group(1).decode("latin-1", errors="replace"))


def inspect_primary_10k(raw: bytes) -> dict:
    """Only call after a canonical SEC filing-detail row identifies this as 10-K."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FILING_BYTES:
        raise ListingEvidenceStop("Primary 10-K missing or oversized")
    if not re.search(rb"(?i)<(?:html|body)\b", raw[:50_000]):
        return {"cover_state": "NO_VERIFIED_10K_TEXT", "section_12b_excerpt": ""}
    return _inspect_cover_text(raw[:250_000].decode("latin-1", errors="replace"))


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
                raise FilingSourceFailure("NONCANONICAL_HTTP_RESPONSE")
            raw = response.read(MAX_FILING_BYTES + 1)
    except HTTPError as exc:
        code = exc.code
        if code in (403, 404, 429):
            reason = f"HTTP_{code}"
        elif 500 <= code <= 599:
            reason = "HTTP_5XX"
        else:
            reason = "HTTP_OTHER"
        raise FilingSourceFailure(reason) from None
    except IncompleteRead:
        raise FilingSourceFailure("INCOMPLETE_SOURCE") from None
    except TimeoutError:
        raise FilingSourceFailure("TIMEOUT") from None
    except URLError:
        raise FilingSourceFailure("NETWORK_UNAVAILABLE") from None
    except OSError:
        raise FilingSourceFailure("TRANSPORT_ERROR") from None
    if not raw:
        raise FilingSourceFailure("EMPTY_SOURCE")
    if len(raw) > MAX_FILING_BYTES:
        raise FilingSourceFailure("OVER_12MB_SOURCE_LIMIT")
    return raw



class _SecFilingDocumentTable(HTMLParser):
    """Extract rows/cell links from the SEC filing-detail document table."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.cells = None
        self.cell_text = None
        self.cell_href = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag in ("td", "th") and self.cells is not None:
            self.cell_text = []
            self.cell_href = None
        elif tag == "a" and self.cell_text is not None:
            self.cell_href = dict(attrs).get("href")

    def handle_data(self, data):
        if self.cell_text is not None:
            self.cell_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell_text is not None:
            self.cells.append((" ".join(self.cell_text).strip(), self.cell_href))
            self.cell_text = None
        elif tag == "tr" and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = None


def _primary_urls(path: str, filename: str = "") -> tuple[str, str]:
    """Derive exact same-accession SEC paths; never follow an arbitrary href."""
    match = ARCHIVE_PATH.fullmatch(path) if type(path) is str else None
    if match is None:
        raise ListingEvidenceStop("Invalid SEC original accession path")
    accession = path.rsplit("/", 1)[1][:-4]
    if re.fullmatch(r"[0-9]+-[0-9]{2}-[0-9]+", accession) is None:
        raise ListingEvidenceStop("Invalid SEC accession identity")
    directory = "edgar/data/" + match.group(1) + "/" + accession.replace("-", "") + "/"
    index_url = SEC_PREFIX + directory + accession + "-index.htm"
    if not filename:
        return index_url, ""
    if (type(filename) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\.(?:htm|html|txt)", filename,
                        re.IGNORECASE) is None):
        raise ListingEvidenceStop("Unsafe SEC primary document filename")
    return index_url, SEC_PREFIX + directory + filename


def _primary_10k_from_index(path: str, index_raw: bytes) -> tuple[str, str, str]:
    """Require one exact 10-K document row from the canonical filing-detail page."""
    if type(index_raw) is not bytes or not 0 < len(index_raw) <= MAX_FILING_INDEX_BYTES:
        raise FilingSourceFailure("PRIMARY_INDEX_INVALID")
    parser = _SecFilingDocumentTable()
    try:
        parser.feed(index_raw.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeError) as exc:
        raise FilingSourceFailure("PRIMARY_INDEX_INVALID") from exc
    found = []
    for row in parser.rows:
        if len(row) < 4 or row[3][0].strip().upper() != "10-K":
            continue
        filename = row[2][0].strip()
        href = row[2][1]
        try:
            index_url, document_url = _primary_urls(path, filename)
        except ListingEvidenceStop:
            raise FilingSourceFailure("PRIMARY_INDEX_UNSAFE_DOCUMENT") from None
        relative = document_url.removeprefix("https://www.sec.gov")
        if href not in (filename, relative, document_url):
            raise FilingSourceFailure("PRIMARY_INDEX_UNSAFE_LINK")
        found.append((filename, index_url, document_url))
    if len(found) != 1:
        raise FilingSourceFailure("PRIMARY_INDEX_10K_NOT_UNIQUE")
    return found[0]


def _official_primary_10k_get(path: str, agent: str) -> tuple[bytes, bytes, str, str, str]:
    """Fallback for oversized submissions: verified 10-K row + bounded primary bytes."""
    if (type(agent) is not str or len(agent) < 10 or "@" not in agent
        or "\r" in agent or "\n" in agent):
        raise ListingEvidenceStop("SEC contact user agent not configured")
    index_url, _ = _primary_urls(path)

    def fetch_exact(url: str, limit: int) -> bytes:
        try:
            with urlopen(Request(url, headers={
                    "User-Agent": agent, "Accept": "text/html"}), timeout=35) as response:
                if response.status != 200 or response.geturl() != url:
                    raise FilingSourceFailure("NONCANONICAL_HTTP_RESPONSE")
                raw = response.read(limit + 1)
        except HTTPError as exc:
            if exc.code in (403, 404, 429):
                reason = f"HTTP_{exc.code}"
            elif 500 <= exc.code <= 599:
                reason = "HTTP_5XX"
            else:
                reason = "HTTP_OTHER"
            raise FilingSourceFailure(reason) from None
        except IncompleteRead:
            raise FilingSourceFailure("INCOMPLETE_SOURCE") from None
        except TimeoutError:
            raise FilingSourceFailure("TIMEOUT") from None
        except URLError:
            raise FilingSourceFailure("NETWORK_UNAVAILABLE") from None
        except OSError:
            raise FilingSourceFailure("TRANSPORT_ERROR") from None
        if not raw:
            raise FilingSourceFailure("EMPTY_SOURCE")
        if len(raw) > limit:
            raise FilingSourceFailure("PRIMARY_INDEX_OVERSIZED" if limit ==
                                      MAX_FILING_INDEX_BYTES else "PRIMARY_10K_OVERSIZED")
        return raw

    index_raw = fetch_exact(index_url, MAX_FILING_INDEX_BYTES)
    filename, verified_index_url, primary_url = _primary_10k_from_index(path, index_raw)
    if verified_index_url != index_url:
        raise FilingSourceFailure("PRIMARY_INDEX_IDENTITY_MISMATCH")
    return (fetch_exact(primary_url, MAX_FILING_BYTES), index_raw, filename,
            primary_url, index_url)


def capture(source_dir: Path, output_dir: Path, agent: str,
            *, per_stratum: int = 16, getter=None, primary_getter=None) -> dict:
    selected, annual = select_sample(source_dir, per_stratum=per_stratum)
    if getter is None:
        getter = _official_filing_get
        if primary_getter is None:
            primary_getter = _official_primary_10k_get
    output_dir.mkdir(parents=True, exist_ok=True)
    observations = []
    for row in selected:
        result = {**row, "original_filing_url": SEC_PREFIX + row["sec_archive_path"]}
        try:
            try:
                raw = getter(row["sec_archive_path"], agent)
                if type(raw) is not bytes or not 0 < len(raw) <= MAX_FILING_BYTES:
                    raise ListingEvidenceStop("Original SEC filing source invalid")
                evidence = inspect_original_10k(raw)
                filename = "original-10k-" + str(row["cik"]) + "-" + (
                    row["sec_archive_path"].split("/")[-1])
                source_kind = "FULL_SUBMISSION"
                captured_url = result["original_filing_url"]
                provenance = {}
            except FilingSourceFailure as exc:
                if exc.reason_code != "OVER_12MB_SOURCE_LIMIT" or primary_getter is None:
                    raise
                result["original_submission_failure_reason"] = exc.reason_code
                (raw, index_raw, primary_name, captured_url,
                 index_url) = primary_getter(row["sec_archive_path"], agent)
                expected_index, expected_primary = _primary_urls(
                    row["sec_archive_path"], primary_name)
                if (captured_url != expected_primary or index_url != expected_index
                    or type(raw) is not bytes or not 0 < len(raw) <= MAX_FILING_BYTES
                    or type(index_raw) is not bytes
                    or not 0 < len(index_raw) <= MAX_FILING_INDEX_BYTES):
                    raise ListingEvidenceStop("Unverified primary SEC source identity")
                if _primary_10k_from_index(row["sec_archive_path"], index_raw) != (
                        primary_name, index_url, captured_url):
                    raise ListingEvidenceStop("SEC primary filing index mismatch")
                evidence = inspect_primary_10k(raw)
                accession = row["sec_archive_path"].rsplit("/", 1)[1][:-4]
                filename = "original-primary-10k-" + str(row["cik"]) + "-" + (
                    accession.replace("-", "") + "-" + primary_name)
                index_filename = "original-primary-index-" + str(row["cik"]) + "-" + (
                    accession.replace("-", "") + ".html")
                (output_dir / index_filename).write_bytes(index_raw)
                source_kind = "INDEX_VERIFIED_PRIMARY_10K"
                provenance = {
                    "primary_index_file": index_filename,
                    "primary_index_sha256": sha256(index_raw).hexdigest(),
                    "primary_index_bytes": len(index_raw),
                    "primary_index_url": index_url,
                    "primary_document_filename": primary_name,
                }
            (output_dir / filename).write_bytes(raw)
            result.update({
                "source_state": ("ORIGINAL_10K_BYTES_CAPTURED" if
                                 source_kind == "FULL_SUBMISSION" else
                                 "ORIGINAL_PRIMARY_10K_BYTES_CAPTURED"),
                "source_kind": source_kind,
                "captured_source_url": captured_url,
                "original_sha256": sha256(raw).hexdigest(),
                "original_bytes": len(raw),
                "local_original_file": filename,
                **provenance,
                **evidence,
            })
        except ListingEvidenceStop as exc:
            result.update({
                "source_state": "SOURCE_UNAVAILABLE_OR_UNVERIFIABLE",
                "source_failure_reason": (exc.reason_code if isinstance(
                    exc, FilingSourceFailure) else "OTHER_UNVERIFIABLE"),
                "cover_state": "NOT_EVALUATED",
            })
        observations.append(result)
    count = sum(r["source_state"] in {
        "ORIGINAL_10K_BYTES_CAPTURED", "ORIGINAL_PRIMARY_10K_BYTES_CAPTURED"}
                for r in observations)
    report = {
        "schema": SCHEMA,
        "capture_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "p4t_manifest_sha256": annual["historical_filing_manifest_sha256"],
        "historical_issuer_population": annual["annual_distinct_10k_ciks"],
        "sample_per_current_registry_stratum": per_stratum,
        "predeclared_filing_samples": len(selected),
        "sample_by_current_registry_stratum": dict(sorted(Counter(
            r["current_registry_stratum"] for r in selected).items())),
        "sample_by_filing_quarter": dict(sorted(Counter(
            r["quarter"] for r in selected).items())),
        "captured_by_current_registry_stratum": dict(sorted(Counter(
            r["current_registry_stratum"] for r in observations
            if r["source_state"] in {
                "ORIGINAL_10K_BYTES_CAPTURED", "ORIGINAL_PRIMARY_10K_BYTES_CAPTURED"}
        ).items())),
        "original_filing_sources_captured": count,
        "index_verified_primary_10k_sources_captured": sum(
            r["source_state"] == "ORIGINAL_PRIMARY_10K_BYTES_CAPTURED"
            for r in observations),
        "full_submission_sources_captured": sum(
            r["source_state"] == "ORIGINAL_10K_BYTES_CAPTURED"
            for r in observations),
        "unavailable_or_unverifiable_sources": len(selected) - count,
        "source_failure_reason_counts": dict(sorted(Counter(
            r["source_failure_reason"] for r in observations
            if r["source_state"] == "SOURCE_UNAVAILABLE_OR_UNVERIFIABLE"
        ).items())),
        "possible_section12b_common_equity_exchange_covers": sum(
            r["cover_state"] in {
                "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED",
                "POSSIBLE_12B_COMMON_PRECEDING_EXCHANGE_REVIEW_REQUIRED"}
            for r in observations),
        "section12g_common_class_covers": sum(
            r.get("section12g_common_class_review_required") is True
            for r in observations),
        "sample_not_universe_or_delisting_estimate": True,
        "cover_text_not_independent_listing_or_security_master": True,
        "index_verified_primary_is_not_complete_submission": True,
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
    cli.add_argument("--per-stratum", type=int, default=16)
    args = cli.parse_args()
    result = capture(args.source_dir, args.output_dir,
                     os.environ.get("SEC_USER_AGENT", ""),
                     per_stratum=args.per_stratum)
    print("P4U original 2017 10-K cover source audit:",
          result["original_filing_sources_captured"], "verified source captures of",
          result["predeclared_filing_samples"], "predeclared samples;",
          result["possible_section12b_common_equity_exchange_covers"],
          "possible Section 12(b) common-share/exchange mentions, REVIEW REQUIRED; ",
          result["section12g_common_class_covers"], "12(g) common-class covers.")
    print("Source failure reason counts (not listing evidence):",
          json.dumps(result["source_failure_reason_counts"], sort_keys=True))
    print("NO historical listed-security eligibility, alpha, broker access or orders.")

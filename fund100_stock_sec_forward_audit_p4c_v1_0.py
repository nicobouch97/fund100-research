"""P4C SEC source-authenticated contemporary stock coverage & append-only ledger.

NO live SEC network, trading API, securities performance backtest, or
licensed analyst estimates. The official source ZIP downloaded from an
explicit P4B capture is validated AGAINST ITS ORIGINAL BYTES. Never treat
a current SEC CompanyFacts download as a vintage available in 2015.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as source

SCHEMA = "FUND100_PHASE4C_STOCK_SEC_FORWARD_SOURCE_AUDIT_V1"
RECORD_SCHEMA = "FUND100_PHASE4C_APPEND_ONLY_CAPTURE_RECORD_V1"
MAX_UNCOMPRESSED_BYTES = 200_000_000


class CohortAuditStop(ValueError):
    pass


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def snapshot_files(path: Path) -> dict[str, bytes]:
    """Read bounded original ZIP or extracted P4B artifact, never extract paths."""
    if path.is_dir():
        root = path.resolve()
        files = {}
        for file in path.rglob("*"):
            if file.is_symlink():
                raise CohortAuditStop("Symlink forbidden in source artifact.")
            if file.is_file():
                relative = file.relative_to(path).as_posix()
                if file.stat().st_size > source.MAX_JSON_BYTES:
                    raise CohortAuditStop("Oversize captured source.")
                files[relative] = file.read_bytes()
    else:
        files = {}
        with zipfile.ZipFile(path) as z:
            entries = z.infolist()
            if sum(e.file_size for e in entries) > MAX_UNCOMPRESSED_BYTES:
                raise CohortAuditStop("Uncompressed archive exceeds limit.")
            for item in entries:
                if item.is_dir():
                    continue
                n = item.filename
                if (n in files or item.file_size > source.MAX_JSON_BYTES or
                    item.flag_bits & 0x1 or
                    PurePosixPath(n).is_absolute() or
                    ".." in PurePosixPath(n).parts or "\\" in n):
                    raise CohortAuditStop("Unsafe, duplicated or oversized SEC file.")
                files[n] = z.read(item)
    if "manifest-and-quality.json" not in files:
        raise CohortAuditStop("No original P4B manifest in source artifact.")
    if any(n != "manifest-and-quality.json" and not re.fullmatch(
        r"raw/CIK\d{10}-[A-Z]{1,5}-(companyfacts|submissions)\.json", n
    ) for n in files):
        raise CohortAuditStop("Unexpected item in official SEC research artifact.")
    return files


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", value
    ):
        raise CohortAuditStop("Missing canonical capture UTC.")
    try:
        t = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CohortAuditStop("Invalid source UTC clock.") from exc
    if value < "2026-10-15T00:00:00Z":
        raise CohortAuditStop("Source predates frozen prospective cohort.")
    return t


def audit(files: dict[str, bytes]) -> dict:
    """Fail closed on every original SEC issuer/hash/asof score comparison."""
    if not isinstance(files, dict) or "manifest-and-quality.json" not in files:
        raise CohortAuditStop("Missing original SEC capture manifest.")
    raw_manifest = files["manifest-and-quality.json"]
    try:
        manifest = json.loads(raw_manifest)
    except (ValueError, TypeError) as exc:
        raise CohortAuditStop("Invalid original SEC manifest.") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != source.SCHEMA:
        raise CohortAuditStop("Unknown original P4B SEC manifest schema.")
    capture = manifest.get("capture_timestamp_utc")
    _timestamp(capture)
    asof = capture[:10]
    cohort = source.read_cohort()
    n = manifest.get("companies_attempted")
    rows = manifest.get("companies")
    if (type(n) is not int or n not in (1, 2, 4, 8) or
        type(rows) is not list or len(rows) != n or
        manifest.get("source_count") != 2*n or
        len(files) != 1 + 2*n):
        raise CohortAuditStop("Partial or inconsistent SEC issuer cohort capture.")
    if (manifest.get("observation_asof_utc_date") != asof or
        manifest.get("status") != "PROSPECTIVE_SEC_SOURCE_CAPTURE_RESEARCH_ONLY" or
        manifest.get("paper_authorized") is not False or
        manifest.get("live_authorized") is not False or
        manifest.get("broker_orders") != 0 or
        manifest.get("analyst_estimates_and_revisions_not_included") is not True or
        manifest.get("raw_current_sec_download_is_not_historical_archived_source_vintage") is not True or
        manifest.get("selection_is_contemporary_survivor_biased_if_backtested_historically") is not True or
        manifest.get("full_universe_survey_not_yet_performed") is not (n < 8)):
        raise CohortAuditStop("P4B capture authorization or source limitations invalid.")
    observed, unavailable = [], []
    used = {"manifest-and-quality.json"}
    for expected, row in zip(cohort[:n], rows):
        if (type(row) is not dict or
            row.get("ticker") != expected["ticker"] or
            row.get("cik") != expected["cik_10_digit"] or
            row.get("paper_authorized") is not False or
            row.get("live_authorized") is not False or
            row.get("analyst_earnings_revision_signal") is not None or
            row.get("survivorship_safe_historical_backtest_eligible") is not False or
            row.get("raw_full_source_captured_at_utc") != capture):
            raise CohortAuditStop("SEC stock provenance, order or cohort identity mismatch.")
        cik = row["cik"]
        prov = row.get("report_data_provenance")
        if not isinstance(prov, dict) or set(prov) != set(source.ENDPOINTS):
            raise CohortAuditStop("SEC expected source names missing.")
        originals = {}
        for kind in source.ENDPOINTS:
            entry = prov[kind]
            name = f"raw/CIK{cik}-{row['ticker']}-{kind}.json"
            if (not isinstance(entry, dict) or
                entry.get("source_file") != name or
                entry.get("official_url") != source.sec_url(cik, kind) or
                name not in files or
                entry.get("byte_count") != len(files[name]) or
                entry.get("raw_sha256") != digest(files[name])):
                raise CohortAuditStop("Original SEC source SHA, URL or filename mismatch.")
            used.add(name)
            originals[kind] = source.decode_source(files[name], expected_cik=cik)
        quality.validate_identity(originals["companyfacts"], originals["submissions"], cik)
        calculated = quality.asof_quality(
            originals["companyfacts"], originals["submissions"], cik, asof
        )
        keys = {
            "quality_state": "state",
            "quality_score": "score",
            "quality_revenue_growth_yoy": "revenue_growth_yoy",
            "quality_operating_margin": "operating_margin",
            "quality_free_cash_flow_margin": "free_cash_flow_margin",
            "last_eligible_fiscal_year": "annual_asof_source_period",
            "last_eligible_filing_accession": "source_accession",
            "last_eligible_filing_available_date": "source_available_date",
        }
        if any(row.get(a) != calculated.get(b) for a, b in keys.items()):
            raise CohortAuditStop("Source-linked annual score not reproducible from original SEC bytes.")
        if row.get("quality_maximum") != (3 if calculated["score"] is not None else None):
            raise CohortAuditStop("Noncanonical annual quality maximum.")
        score = calculated["score"]
        item = {
            "ticker": row["ticker"], "cik": cik,
            "state": calculated["state"], "score": score,
            "annual_period_end": calculated["annual_asof_source_period"],
            "published_eligible_date": calculated["source_available_date"],
            "sec_10k_accession": calculated["source_accession"],
            "revenue_growth_yoy": calculated["revenue_growth_yoy"],
            "operating_margin": calculated["operating_margin"],
            "fcf_margin": calculated["free_cash_flow_margin"],
            "companyfacts_sha256": prov["companyfacts"]["raw_sha256"],
            "submissions_sha256": prov["submissions"]["raw_sha256"],
        }
        observed.append(item)
        if score is None:
            unavailable.append(row["ticker"])
    if used != set(files):
        raise CohortAuditStop("Unreviewed or extra file in source capture.")
    return {
        "schema": SCHEMA,
        "status": "VERIFIED_GENUINE_SEC_SOURCE_COHORT_RESEARCH_ONLY",
        "source_original_manifest_sha256": digest(raw_manifest),
        "capture_timestamp_utc": capture,
        "asof_utc_date": asof,
        "contemporary_cohort_size": len(cohort),
        "source_companies": n,
        "quality_available": n-len(unavailable),
        "quality_unavailable": len(unavailable),
        "missing_quality_tickers": unavailable,
        "uncaptured_cohort_tickers": [r["ticker"] for r in cohort[n:]],
        "coverage_percent_of_captured": round(100*(n-len(unavailable))/n, 2),
        "coverage_percent_of_frozen_cohort": round(100*(n-len(unavailable))/len(cohort), 2),
        "score_values_are_descriptive_not_ranking_alpha": True,
        "source_capture_is_historical_vintage": False,
        "point_in_time_historical_security_master_available": False,
        "analyst_revision_signals_available": False,
        "historical_stock_return_backtest_eligible": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_orders": 0,
        "observations": observed,
    }


def ledger_record(audit_report: dict, previous: list[dict] | None = None) -> dict:
    prior = [] if previous is None else previous
    validate_ledger(prior)
    if audit_report.get("schema") != SCHEMA or audit_report.get("paper_authorized") is not False or audit_report.get("live_authorized") is not False:
        raise CohortAuditStop("Only source-audited nontrading reports enter ledger.")
    capture = audit_report["capture_timestamp_utc"]
    _timestamp(capture)
    manifest_hash = audit_report["source_original_manifest_sha256"]
    if not re.fullmatch(r"[a-f0-9]{64}", str(manifest_hash)):
        raise CohortAuditStop("Source manifest SHA missing.")
    if prior and capture <= prior[-1]["capture_timestamp_utc"]:
        raise CohortAuditStop("Attempt to backdate or duplicate existing SEC observation.")
    prev_hash = prior[-1]["record_sha256"] if prior else None
    payload = {
        "schema": RECORD_SCHEMA,
        "capture_timestamp_utc": capture,
        "source_manifest_sha256": manifest_hash,
        "captured_tickers": [r["ticker"] for r in audit_report["observations"]],
        "quality_available": audit_report["quality_available"],
        "quality_missing": audit_report["quality_unavailable"],
        "previous_record_sha256": prev_hash,
        "stock_trade_orders": 0,
        "historical_alpha_validated": False,
        "paper_authorized": False,
        "live_authorized": False,
    }
    payload["record_sha256"] = digest(json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode())
    return payload


def validate_ledger(records: list[dict]) -> None:
    if not isinstance(records, list):
        raise CohortAuditStop("Prospective SEC ledger must be list.")
    prior = None
    date_before = None
    for record in records:
        if not isinstance(record, dict) or record.get("schema") != RECORD_SCHEMA:
            raise CohortAuditStop("Unknown SEC ledger record.")
        timestamp = record.get("capture_timestamp_utc")
        _timestamp(timestamp)
        if date_before and timestamp <= date_before:
            raise CohortAuditStop("Retroactive, duplicated or unsorted SEC record.")
        if (record.get("previous_record_sha256") != prior or
            record.get("stock_trade_orders") != 0 or
            record.get("historical_alpha_validated") is not False or
            record.get("paper_authorized") is not False or
            record.get("live_authorized") is not False or
            type(record.get("quality_available")) is not int or
            type(record.get("quality_missing")) is not int or
            not isinstance(record.get("captured_tickers"), list) or
            len(set(record["captured_tickers"])) != len(record["captured_tickers"]) or
            record["quality_available"] + record["quality_missing"] != len(record["captured_tickers"])):
            raise CohortAuditStop("SEC score ledger provenance/permissions changed.")
        original = {k: v for k,v in record.items() if k != "record_sha256"}
        computed = digest(json.dumps(original, sort_keys=True, separators=(",", ":")).encode())
        if computed != record.get("record_sha256"):
            raise CohortAuditStop("SEC append-only ledger SHA256 chain broken.")
        date_before, prior = timestamp, computed


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-artifact", required=True, help="P4B ZIP or extracted artifact dir")
    p.add_argument("--report-json", required=True)
    p.add_argument("--record-json", required=True)
    p.add_argument("--prior-ledger-jsonl", default=None)
    args = p.parse_args()
    result = audit(snapshot_files(Path(args.source_artifact)))
    previous = []
    if args.prior_ledger_jsonl:
        prior_path = Path(args.prior_ledger_jsonl)
        if prior_path.exists():
            previous = [json.loads(line) for line in prior_path.read_text().splitlines() if line.strip()]
    record = ledger_record(result, previous)
    Path(args.report_json).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    Path(args.record_json).write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print("SEC authentic raw-company coverage:", result["quality_available"],
          "of", result["source_companies"], "captured issuers.")
    print("SEC prospective cohort coverage:", result["coverage_percent_of_frozen_cohort"], "%.")
    print("No analyst EPS revisions, historical stock alpha or PAPER/LIVE orders.")


if __name__ == "__main__":
    main()

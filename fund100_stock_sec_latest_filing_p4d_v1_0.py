"""P4D strict latest-original-10-K feature coverage diagnostic.

Never retroactively amend a source capture's original P4A score/state.
Instead put a LATER separately versioned 'latest filing completeness'
gate on prospective evidence: an older complete 10-K must never make
a newer incomplete filing look fully qualified. Alternative US-GAAP
concepts are documented for research only, NEVER substituted into
the frozen original model or used for orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import date
import math

import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_forward_audit_p4c_v1_0 as p4c
import fund100_stock_sec_source_p4b_v1_0 as p4b

SCHEMA = "FUND100_PHASE4D_LATEST_SEC_10K_ORIGINAL_TAG_COVERAGE_V1"
ALTERNATE_TAGS_FOR_SOURCE_REVIEW_ONLY = {
    "revenue": ("Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"),
    "capital_expenditure": ("PropertyPlantAndEquipmentAdditions",),
    "operating_income": (),
    "operating_cash_flow": (),
}


class NewestFilingStop(ValueError):
    pass


def _annual_concept_fact(concepts: dict, tag: str, filing: dict, accession: str) -> bool:
    fact = concepts.get(tag)
    if not isinstance(fact, dict):
        return False
    for r in fact.get("units", {}).get("USD", []):
        if not isinstance(r, dict):
            continue
        if (r.get("form") != p4a.FORM or
            r.get("accn") != accession or
            r.get("filed") != filing["filed"] or
            r.get("end") != filing["end"]):
            continue
        try:
            start = p4a.iso_date(r.get("start"), "start")
            end = p4a.iso_date(r.get("end"), "end")
        except p4a.StockSourceStop:
            continue
        if not p4a.MIN_FY_DAYS <= (end-start).days <= p4a.MAX_FY_DAYS:
            continue
        val = r.get("val")
        if type(val) not in (int, float) or not math.isfinite(float(val)):
            continue
        return True
    return False


def diagnose(facts: dict, submissions: dict, cik: str, asof_date: str,
             original_capture_score: int | None,
             original_capture_accession: str | None) -> dict:
    p4a.validate_identity(facts, submissions, cik)
    now = p4a.iso_date(asof_date, "as-of date")
    filings = p4a.submissions_index(submissions)
    released = sorted(
        ((a, record) for a, record in filings.items()
         if record["form"] == p4a.FORM
         and p4a.iso_date(record["end"], "period") <= now
         and p4a.iso_date(p4a.availability_day(record["filed"]), "availability") <= now),
        key=lambda x: (x[1]["end"], x[1]["filed"], x[0]),
    )
    if not released:
        return {
            "status": "NO_ELIGIBLE_RECENT_10K_IN_SEC_SUBMISSIONS",
            "latest_original_accession": None,
            "missing_original_concepts": list(p4a.ANNUAL_TAGS),
            "descriptive_score_after_latest_filing_gate": None,
            "frozen_capture_score_not_rewritten": original_capture_score,
            "original_capture_accession_not_rewritten": original_capture_accession,
        }
    accession, filing = released[-1]
    concepts = facts["facts"]["us-gaap"]
    reasons = {}
    alternatives = {}
    for label, tag in p4a.ANNUAL_TAGS.items():
        if _annual_concept_fact(concepts, tag, filing, accession):
            continue
        if tag not in concepts:
            reasons[label] = "FIXED_GAAP_TAG_ABSENT_FROM_CURRENT_SEC_SOURCE"
        else:
            reasons[label] = "NO_MATCHING_LATEST_ORIGINAL_FULL_YEAR_10K_FACT"
        alternatives[label] = [
            alt for alt in ALTERNATE_TAGS_FOR_SOURCE_REVIEW_ONLY[label]
            if alt in concepts
        ]
    eligible = (
        not reasons and
        original_capture_score is not None and
        original_capture_accession == accession
    )
    return {
        "status": ("LATEST_10K_FIXED_SOURCE_FACTS_COMPLETE" if eligible
                   else "LATEST_10K_NOT_ELIGIBLE_FOR_FROZEN_SCORE"),
        "latest_original_accession": accession,
        "latest_original_fiscal_end": filing["end"],
        "latest_original_filed_date": filing["filed"],
        "latest_original_conservative_available_date":
            p4a.availability_day(filing["filed"]),
        "missing_original_concepts": sorted(reasons),
        "incomplete_fixed_source_details": reasons,
        "alternate_US_GAAP_tags_PRESENT_ONLY_not_substituted": alternatives,
        "descriptive_score_after_latest_filing_gate":
            original_capture_score if eligible else None,
        "frozen_capture_score_not_rewritten": original_capture_score,
        "original_capture_accession_not_rewritten": original_capture_accession,
        "original_source_report_is_current_retrieval_not_verified_historical_vintage": True,
        "analyst_estimate_revisions_available": False,
        "survivorship_safe_historical_backtest_eligible": False,
        "paper_authorized": False, "live_authorized": False,
        "broker_orders": 0,
    }


def review_original_source_archive(path: Path) -> dict:
    files = p4c.snapshot_files(path)
    p4c_report = p4c.audit(files)
    capture = json.loads(files["manifest-and-quality.json"])
    items = []
    for row, old in zip(capture["companies"], p4c_report["observations"]):
        cik, sym = row["cik"], row["ticker"]
        f = p4b.decode_source(
            files[f"raw/CIK{cik}-{sym}-companyfacts.json"], expected_cik=cik
        )
        s = p4b.decode_source(
            files[f"raw/CIK{cik}-{sym}-submissions.json"], expected_cik=cik
        )
        item = diagnose(f, s, cik, p4c_report["asof_utc_date"],
                        old["score"], old["sec_10k_accession"])
        items.append({"ticker": sym, "cik": cik, **item})
    return {
        "schema": SCHEMA,
        "status": "LATEST_10K_SOURCE_COVERAGE_DIAGNOSTIC_RESEARCH_ONLY",
        "source_raw_manifest_sha256": p4c_report["source_original_manifest_sha256"],
        "original_observation_utc": p4c_report["capture_timestamp_utc"],
        "captured_company_count": len(items),
        "latest_year_eligible_quality_count": sum(
            item["descriptive_score_after_latest_filing_gate"] is not None
            for item in items
        ),
        "latest_year_coverage_unavailable_tickers": [
            item["ticker"] for item in items
            if item["descriptive_score_after_latest_filing_gate"] is None
        ],
        "model_thresholds_changed": False,
        "automatic_tag_substitutions_performed": False,
        "older_p4b_p4c_prospective_results_mutated": False,
        "current_company_survivor_cohort_not_historical_universe": True,
        "independent_historical_alpha_validated": False,
        "live_authorized": False,
        "paper_authorized": False,
        "broker_orders": 0,
        "companies": items,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-artifact", required=True)
    p.add_argument("--output-json", required=True)
    args = p.parse_args()
    report = review_original_source_archive(Path(args.source_artifact))
    Path(args.output_json).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("P4D verified latest 10-K tag coverage:",
          report["latest_year_eligible_quality_count"],
          "/", report["captured_company_count"])
    print("No frozen P4A history was modified, no earnings revisions or trades.")


if __name__ == "__main__":
    main()

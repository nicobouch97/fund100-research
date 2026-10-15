"""Phase 4E: separately-versioned, frozen SEC issuer-specific quality source map.

Evaluate ONLY the latest eligible original 10-K accession's two full-year
annual reporting periods, as carried in that 10-K (current and comparative).
Every fact must match ONE accession/filed day/period end and the explicit
per-company US-GAAP tag. Comparative figures in the latest published 10-K
are legitimate CURRENT retrospective financial information, NOT the raw
values known years before. No older complete 10-K fallback permitted.

Issuer-specific Revenue/Capex concepts improve descriptive *today*
coverage but economic FCF comparisons across sectors are NOT validated.
Historical alpha, analyst revision estimates, price/delisting history,
broker PAPER and LIVE all remain unavailable/forbidden.
"""
from __future__ import annotations

import csv
from datetime import date
import json
import math
from pathlib import Path
import re

import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b
import fund100_stock_sec_forward_audit_p4c_v1_0 as p4c

SCHEMA = "FUND100_PHASE4E_ISSUER_GAAP_FILING_QUALITY_V1"
MAP_FILE = Path("research_lab/stocks/p4e_frozen_issuer_gaap_concept_contract_2026_10_15.csv")
OPERATING = "OperatingIncomeLoss"
CFO = "NetCashProvidedByUsedInOperatingActivities"
FROZEN_REVENUE = {
    "AAPL":"RevenueFromContractWithCustomerExcludingAssessedTax",
    "MSFT":"RevenueFromContractWithCustomerExcludingAssessedTax",
    "GOOGL":"Revenues",
    "AMZN":"RevenueFromContractWithCustomerExcludingAssessedTax",
    "XOM":"Revenues",
    "JNJ":"RevenueFromContractWithCustomerExcludingAssessedTax",
    "PG":"Revenues",
    "KO":"Revenues",
}
FROZEN_CAPEX = {
    k:("PaymentsToAcquireProductiveAssets" if k=="AMZN"
       else "PaymentsToAcquirePropertyPlantAndEquipment")
    for k in FROZEN_REVENUE
}
EXPECTED_COLUMNS = (
    "ticker","cik_10_digit","revenue_us_gaap_tag",
    "capital_expenditure_us_gaap_tag","accounting_review_note",
)


class GAAPMappingStop(ValueError):
    pass


def source_mapping(path: Path = MAP_FILE) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fp:
        table = csv.DictReader(fp)
        if tuple(table.fieldnames or []) != EXPECTED_COLUMNS:
            raise GAAPMappingStop("Unrecognised issuer-tag source contract.")
        rows = list(table)
    cohort = p4b.read_cohort()
    if len(rows) != len(cohort) or len(rows) != len(FROZEN_REVENUE):
        raise GAAPMappingStop("Issuer-tag map incomplete.")
    for expected,row in zip(cohort, rows):
        ticker = expected["ticker"]
        if (row["ticker"] != ticker
            or row["cik_10_digit"] != expected["cik_10_digit"]
            or row["revenue_us_gaap_tag"] != FROZEN_REVENUE[ticker]
            or row["capital_expenditure_us_gaap_tag"] != FROZEN_CAPEX[ticker]
            or not row["accounting_review_note"].strip()):
            raise GAAPMappingStop("Unreviewed issuer tag substitution or cohort identity.")
    return rows


def annual_value(concepts: dict, tag: str, accession: str,
                 filed: str, period_end: str) -> float | None:
    """Require unique one-year USD amount FROM LATEST 10-K accession."""
    concept = concepts.get(tag)
    if concept is None:
        return None
    if not isinstance(concept, dict):
        raise GAAPMappingStop("Corrupt SEC financial concept.")
    units = concept.get("units")
    if not isinstance(units, dict) or "USD" not in units or not isinstance(units["USD"],list):
        return None
    matched = []
    for item in units["USD"]:
        if not isinstance(item, dict):
            raise GAAPMappingStop("Corrupt SEC USD fact.")
        if any(item.get(k)!=v for k,v in (
            ("accn",accession),("filed",filed),
            ("form","10-K"),("end",period_end)
        )):
            continue
        try:
            start = p4a.iso_date(item.get("start"), "annual start")
            end = p4a.iso_date(period_end, "annual end")
        except p4a.StockSourceStop:
            continue
        if not p4a.MIN_FY_DAYS <= (end-start).days <= p4a.MAX_FY_DAYS:
            continue
        raw = item.get("val")
        if type(raw) not in (int,float) or not math.isfinite(float(raw)):
            raise GAAPMappingStop("Non-finite/malformed source concept amount.")
        matched.append(float(raw))
    if not matched:
        return None
    if any(v!=matched[0] for v in matched):
        raise GAAPMappingStop("Conflicting annual dollars for same accession and tag.")
    return matched[0]


def newest_annual_quality(facts: dict, submissions: dict,
                          map_row: dict, asof: str) -> dict:
    ticker, cik = map_row["ticker"], map_row["cik_10_digit"]
    frozen = {r["ticker"]:r for r in source_mapping()}
    if ticker not in frozen or map_row != frozen[ticker]:
        raise GAAPMappingStop("An issuer GAAP rule not included in frozen policy.")
    p4a.validate_identity(facts, submissions, cik)
    now = p4a.iso_date(asof,"SEC capture research as-of")
    filings = p4a.submissions_index(submissions)
    ready = sorted(
        [(a,f) for a,f in filings.items()
         if f["form"]=="10-K"
         and p4a.iso_date(f["end"],"FY report date") <= now
         and p4a.iso_date(p4a.availability_day(f["filed"]),"asof gate") <= now],
        key=lambda x:(x[1]["end"],x[1]["filed"],x[0]),
        reverse=True
    )
    out = {
        "ticker": ticker, "cik":cik,
        "asof_research_date":asof,
        "latest_10k_accession":None,
        "latest_10k_fiscal_end":None,
        "latest_10k_filing_date":None,
        "latest_10k_conservative_available_date":None,
        "previous_10k_accession_for_period_provenance":None,
        "latest_10k_comparative_values_from_same_accession":True,
        "revenue_source_tag":map_row["revenue_us_gaap_tag"],
        "capex_source_tag":map_row["capital_expenditure_us_gaap_tag"],
        "operating_income_source_tag":OPERATING,
        "operating_cash_flow_source_tag":CFO,
        "state":"MISSING_ELIGIBLE_10K_OR_QUALITY_FACTS",
        "missing_concepts":[],
        "quality_score":None,
        "revenue_growth_yoy":None,
        "operating_income_margin":None,
        "free_cash_flow_margin":None,
        "not_economically_cross_sector_neutral":True,
        "estimate_revisions_available":False,
        "survivorship_safe_historical_backtest_eligible":False,
        "paper_authorized":False,"live_authorized":False,"broker_orders":0,
    }
    if len(ready)<2:
        out["state"]="INSUFFICIENT_PRIOR_OR_CURRENT_ORIGINAL_10KS"
        return out
    current, prev = ready[0], ready[1]
    ca,cf=current;pa,pf=prev
    out.update({
        "latest_10k_accession":ca,
        "latest_10k_fiscal_end":cf["end"],
        "latest_10k_filing_date":cf["filed"],
        "latest_10k_conservative_available_date":p4a.availability_day(cf["filed"]),
        "previous_10k_accession_for_period_provenance":pa,
    })
    if (now-p4a.iso_date(cf["end"],"FY end")).days > p4a.MAX_STALENESS_DAYS:
        out["state"]="LATEST_10K_STALE";return out
    if (p4a.iso_date(cf["end"],"FY end")-p4a.iso_date(pf["end"],"prior FY end")).days not in range(330,400):
        out["state"]="NONCONSECUTIVE_ANNUAL_PERIOD";return out
    concepts = facts["facts"]["us-gaap"]
    tags={"revenue":map_row["revenue_us_gaap_tag"],
          "operating_income":OPERATING,
          "operating_cash_flow":CFO,
          "capital_expenditure":map_row["capital_expenditure_us_gaap_tag"]}
    current_values={}
    prior_values={}
    # Obtain each metric for BOTH annual periods from the latest issuer
    # filing itself, not the former 10-K. This keeps GAAP taxonomy
    # comparable under the same accounting presentation as of capture.
    for k,tag in tags.items():
        value=annual_value(concepts,tag,ca,cf["filed"],cf["end"])
        earlier=annual_value(concepts,tag,ca,cf["filed"],pf["end"])
        if value is None:
            out["missing_concepts"].append(k+":current")
        if earlier is None:
            out["missing_concepts"].append(k+":comparative")
        current_values[k]=value
        prior_values[k]=earlier
    if out["missing_concepts"]:
        out["state"]="LATEST_10K_MISSING_FROZEN_OR_COMPARATIVE_GAAP_FACT"
        return out
    if (current_values["revenue"]<=0 or prior_values["revenue"]<=0
        or current_values["capital_expenditure"]<0):
        out["state"]="INVALID_NONPOSITIVE_REVENUE_OR_CAPEX"
        return out
    revenue_growth=current_values["revenue"]/prior_values["revenue"]-1
    op_margin=current_values["operating_income"]/current_values["revenue"]
    fcf_margin=(current_values["operating_cash_flow"]-current_values["capital_expenditure"])/current_values["revenue"]
    score=int(revenue_growth>=0)+int(op_margin>=.10)+int(fcf_margin>=.05)
    out.update({
        "state":"DESCRIPTIVE_NEWEST_ORIGINAL_10K_ISSUER_SPECIFIC_QUALITY",
        "quality_score":score,
        "revenue_growth_yoy":round(revenue_growth,8),
        "operating_income_margin":round(op_margin,8),
        "free_cash_flow_margin":round(fcf_margin,8),
    })
    return out


def from_verified_source_artifact(path: Path) -> dict:
    files=p4c.snapshot_files(path)
    review=p4c.audit(files)
    original=json.loads(files["manifest-and-quality.json"])
    mapping=source_mapping()
    observations=[]
    for i,row in enumerate(original["companies"]):
        cik,ticker=row["cik"],row["ticker"]
        facts=p4b.decode_source(files[f"raw/CIK{cik}-{ticker}-companyfacts.json"],expected_cik=cik)
        subs=p4b.decode_source(files[f"raw/CIK{cik}-{ticker}-submissions.json"],expected_cik=cik)
        calculated=newest_annual_quality(facts,subs,mapping[i],review["asof_utc_date"])
        calculated["raw_companyfacts_sha256"]=review["observations"][i]["companyfacts_sha256"]
        calculated["raw_submissions_sha256"]=review["observations"][i]["submissions_sha256"]
        observations.append(calculated)
    eligible=[x for x in observations if x["quality_score"] is not None]
    return {
        "schema":SCHEMA,
        "status":"REVIEWED_ISSUER_TAGS_PROSPECTIVE_RESEARCH_ONLY",
        "source_original_manifest_sha256":review["source_original_manifest_sha256"],
        "original_capture_utc":review["capture_timestamp_utc"],
        "original_p4a_quality_counts_not_rewritten":True,
        "p4e_candidates_count":len(observations),
        "p4e_eligible_count":len(eligible),
        "p4e_missing_tickers":[x["ticker"] for x in observations if x["quality_score"] is None],
        "two_year_data_from_latest_10k_comparatives_not_old_point_in_time_vintages":True,
        "company_specific_accounting_margins_not_sector_neutral":True,
        "historical_stock_alpha_or_returns_validated":False,
        "analyst_estimate_revision_signals_available":False,
        "future_prices_and_delistings_validated":False,
        "trading_authorized":False,
        "paper_authorized":False,"live_authorized":False,"broker_orders":0,
        "observations":observations,
    }


def main() -> None:
    p = __import__("argparse").ArgumentParser()
    p.add_argument("--source-artifact",required=True)
    p.add_argument("--output-json",required=True)
    args=p.parse_args()
    obj=from_verified_source_artifact(Path(args.source_artifact))
    Path(args.output_json).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Phase 4E issuer-accounting source coverage:",obj["p4e_eligible_count"],"/",obj["p4e_candidates_count"])
    print("Descriptive quality / missing data only. Zero stock orders or PAPER/LIVE permissions.")


if __name__=="__main__":
    main()

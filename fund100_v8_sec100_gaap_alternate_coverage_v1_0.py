"""Replay original SEC100 financial archive and test bounded alternative GAAP tags.

Strict 2026-forward, nontrading source-COVERAGE study. The original P4A
2-year score and original 200-SEC-byte archive remain frozen and unchanged.
This alternative analysis allows Revenues only where an accession has no
RevenueFromContractWithCustomerExcludingAssessedTax, and cash PaymentsToAcquire-
ProductiveAssets only where PaymentsToAcquirePropertyPlantAndEquipment is
absent. Their economic comparability is provisional and NOT demonstrated by
matching SEC tag names. Thus do not treat candidate scores as a verified alpha
signal, authoritative peer comparison, backtest or an investment order.

The original SEC100 manifest and all 200 underlying original compressed bytes
are independently replayed before reading any alternative candidate fields.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v8_sec100_original_annual_quality_source_v1_0 as original

SCHEMA = "FUND100_V8_SEC100_SOURCE_NATIVE_GAAP_ALTERNATE_COVERAGE_REPLAY_V1"
PINNED_ORIGINAL_SEC100_RUN_ID = 42620947546
PINNED_ORIGINAL_SEC100_HEAD = "8b0356cfaf406127a1b418bbe29d87c27457c0dd"
TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets"),
}
NO_BROKER_NETWORK = True
NO_PRIVATE_GIT_WRITES = True
TRADING_AUTHORIZED = False
ALPHA_VERIFIED = False
MIN_TEN_K_YEARS = 2

class GAAPCoverageHold(ValueError):
    pass


def _canonical_utc(value):
    try:
        return original._utc(value)
    except Exception:
        raise GAAPCoverageHold("Unverified original per-issuer receipt date") from None


def _fact(gaap, *, name, accession, filed, end):
    """Only original SAME annual SEC accession, filed date and actual FY."""
    tags = TAGS[name]
    for tag in tags:
        src = gaap.get(tag)
        if src is None:
            continue
        if type(src) is not dict:
            raise GAAPCoverageHold("Malformed alternate SEC XBRL concept")
        rows = src.get("units", {}).get("USD")
        if rows is None:
            continue
        if type(rows) is not list:
            raise GAAPCoverageHold("Malformed original USD XBRL fact list")
        matches = []
        for row in rows:
            if type(row) is not dict:
                raise GAAPCoverageHold("Malformed source fact entry")
            if (row.get("accn")!=accession
                or row.get("form")!="10-K"
                or row.get("filed")!=filed
                or row.get("end")!=end):
                continue
            try:
                start=date.fromisoformat(row.get("start"))
                end_date=date.fromisoformat(end)
            except (ValueError,TypeError):
                continue
            if not quality.MIN_FY_DAYS <= (end_date-start).days <= quality.MAX_FY_DAYS:
                continue
            v=row.get("val")
            if type(v) not in (int,float):
                raise GAAPCoverageHold("Non-numeric original annual XBRL fact")
            amount=Decimal(str(v))
            if not amount.is_finite() or abs(amount)>Decimal("1e15"):
                raise GAAPCoverageHold("Nonfinite or unbounded actual annual XBRL fact")
            matches.append(amount)
        if matches:
            if len(set(matches))!=1:
                raise GAAPCoverageHold("Same accession has conflicting annual GAAP values")
            return matches[0],tag
    return None,None


def _alternative_one(facts, submissions, *, cik, acquired_utc):
    seen=_canonical_utc(acquired_utc).date()
    try:
        quality.validate_identity(facts,submissions,cik)
        filings=quality.submissions_index(submissions)
    except quality.StockSourceStop:
        raise GAAPCoverageHold("Original issuer SEC source identity/chronology invalid") from None
    gaap=facts["facts"]["us-gaap"]
    candidates=[]
    years=set()
    for accession,item in filings.items():
        if item["form"]!="10-K":
            continue
        try:
            filed=item["filed"]
            end=item["end"]
            fy=date.fromisoformat(end)
            filing_day=date.fromisoformat(filed)
            availability=date.fromisoformat(quality.availability_day(filed))
        except (TypeError,ValueError,quality.StockSourceStop):
            raise GAAPCoverageHold("Missing canonical 10-K annual filing timing") from None
        if not (fy<=filing_day and availability<=seen and fy<=seen):
            continue
        metrics={}
        mapped={}
        for name in TAGS:
            v,tag=_fact(
                gaap,name=name,accession=accession,filed=filed,end=end)
            if tag is None:
                break
            metrics[name]=v
            mapped[name]=tag
        if len(metrics)!=len(TAGS):
            continue
        if (metrics["revenue"]<=0 or metrics["capital_expenditure"]<0):
            continue
        if end in years:
            # Conflicting versions must be reconciled explicitly, never
            # opportunistically select the best financial metrics.
            raise GAAPCoverageHold("Multiple original 10-K versions for same FY")
        years.add(end)
        candidates.append({
            "period_end":end,"accession":accession,"filed":filed,
            "availability_date":availability.isoformat(),
            "metrics":metrics,"tags":mapped})
    candidates.sort(key=lambda x:x["period_end"])
    if len(candidates)<MIN_TEN_K_YEARS:
        return {"state":"ALTERNATE_NOT_TWO_FULL_YEAR_REPORTS","score":None}
    cur,prev=candidates[-1],candidates[-2]
    span=(date.fromisoformat(cur["period_end"])-
          date.fromisoformat(prev["period_end"])).days
    if not 330<=span<=400:
        return {"state":"ALTERNATE_FISCAL_YEARS_NOT_CONSECUTIVE","score":None}
    if (seen-date.fromisoformat(cur["period_end"])).days>quality.MAX_STALENESS_DAYS:
        return {"state":"ALTERNATE_LAST_FISCAL_YEAR_TOO_STALE","score":None}
    growth=cur["metrics"]["revenue"]/prev["metrics"]["revenue"]-Decimal(1)
    op_margin=cur["metrics"]["operating_income"]/cur["metrics"]["revenue"]
    fcf_margin=(cur["metrics"]["operating_cash_flow"]-
                cur["metrics"]["capital_expenditure"])/cur["metrics"]["revenue"]
    score=(int(growth>=0) + int(op_margin>=Decimal(".10")) +
           int(fcf_margin>=Decimal(".05")))
    return {
        "state":"SOURCE_NATIVE_TWO_YEAR_ALTERNATE_GAAP_COVERED_UNVALIDATED",
        "score":score,
        "score_max":3,
        "most_recent_FY_end":cur["period_end"],
        "source_last_annual_accession":cur["accession"],
        "source_previous_annual_accession":prev["accession"],
        "last_filing_conservative_availability_date":cur["availability_date"],
        "actual_tags_latest":cur["tags"],
        "actual_tags_previous":prev["tags"],
        "tag_substitution_is_unvalidated_economic_comparability":True,
        "revenue_growth_yoy":str(growth.quantize(Decimal(".000001"))),
        "operating_margin":str(op_margin.quantize(Decimal(".000001"))),
        "free_cash_flow_margin":str(fcf_margin.quantize(Decimal(".000001"))),
    }


def replay(*, u3_dir:Path, sec100_dir:Path):
    """Only additional old-P4A gaps may be studied; no original rewrite."""
    try:
        documented=original.verify(u3_dir=u3_dir, report_dir=sec100_dir)
    except Exception:
        raise GAAPCoverageHold("Original official SEC100 source not independently replayable") from None
    if (documented.get("schema")!=original.SCHEMA
        or documented.get("source_issuer_count")!=100
        or documented.get("original_official_SEC_endpoint_get_count")!=200
        or documented.get("live_authorized") is not False
        or documented.get("broker_orders")!=0):
        raise GAAPCoverageHold("Unapproved source baseline or broker authority")
    rows=[]
    for row in documented["source_issuer_rows"]:
        symbol=row["ticker"]
        cik=row["original_sec_cik_10digit"]
        base={
            "ticker":symbol, "cik":cik,
            "original_P4A_comparable":row["quality_score"] is not None,
            "original_P4A_state":row["quality_state"],
            "original_companyfacts_sha256":row[
                "official_SEC_original_raw_sources"]["companyfacts"]["original_raw_sha256"],
            "original_submissions_sha256":row[
                "official_SEC_original_raw_sources"]["submissions"]["original_raw_sha256"],
        }
        if base["original_P4A_comparable"]:
            rows.append({**base, "alternate_state":"ORIGINAL_P4A_ALREADY_AVAILABLE",
                         "alternate_candidate":None})
            continue
        sources={}
        for kind in ("companyfacts","submissions"):
            name=original._name(symbol,cik,kind)
            raw,_=original._unzip_bound(sec100_dir/name)
            if not isinstance(raw,bytes):
                raise GAAPCoverageHold("Missing original source")
            sources[kind]=sec.decode_source(raw,expected_cik=cik)
        try:
            assessment=_alternative_one(
                sources["companyfacts"],sources["submissions"],
                cik=cik, acquired_utc=row["original_official_source_received_utc"])
        except GAAPCoverageHold:
            assessment={"state":"ALTERNATE_SOURCE_FINANCIAL_CONFLICT_QUARANTINED",
                        "score":None}
        rows.append({
            **base,"alternate_state":assessment["state"],
            "alternate_candidate":assessment if assessment["score"] is not None else None,
        })
    comparable=sum(r["original_P4A_comparable"] for r in rows)
    proposed=sum(r["alternate_candidate"] is not None for r in rows)
    return {
        "schema":SCHEMA,
        "status":"SEC100_REPLAY_ALTERNATE_GAAP_COVERAGE_RESEARCH_NOT_ALPHA",
        "pinned_original_sec100_completed_workflow_run_id":PINNED_ORIGINAL_SEC100_RUN_ID,
        "pinned_original_sec100_main_commit_sha":PINNED_ORIGINAL_SEC100_HEAD,
        "original_sec100_count":100,
        "original_P4A_annual_quality_comparable_count":comparable,
        "additional_issuer_source_native_candidate_count":proposed,
        "original_plus_source_native_provisional_count":comparable+proposed,
        "issuer_rows":rows,
        "no_retroactive_change_to_original_P4A_source":True,
        "alternate_GAAP_tag_economic_comparability_not_verified":True,
        "all_original_source_raw_bytes_replayed_and_hashed":True,
        "point_in_time_share_count_price_liquidity_delisting_unverified":True,
        "forecast_alpha_backtest_or_outperformance_established":False,
        "live_trading_authorized":False,
        "broker_orders":0,"broker_gets":0,"broker_posts":0,
        "private_git_writes":0,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--original-u3",type=Path,required=True)
    parser.add_argument("--original-sec100",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if not (NO_BROKER_NETWORK and NO_PRIVATE_GIT_WRITES
            and not TRADING_AUTHORIZED and not ALPHA_VERIFIED):
        raise GAAPCoverageHold("Source-only guard")
    if args.output.exists():
        raise GAAPCoverageHold("Never overwrite registered source-coverage decision")
    result=replay(u3_dir=args.original_u3,sec100_dir=args.original_sec100)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("SEC100 original comparable:",result["original_P4A_annual_quality_comparable_count"])
    print("Additional source-native GAAP covered, unvalidated comparability:",
          result["additional_issuer_source_native_candidate_count"])
    print("No new original SEC fetches; ZERO brokerage, trades or alpha claims.")


if __name__=="__main__":
    main()

"""V6-Q1 original-source issuer cash-generation proxy: SEC, NOT Buffett owner earnings.

Uses the ALREADY archived 15 October 2026 original SEC 10-K source bytes
and the existing strict P4E latest-accession comparative accounting map.
Cash flow minus reported asset purchases is a *descriptive* cash proxy.
Maintenance capex, working-capital normalization, acquisitions, capital
allocation and point-in-time equity valuation are UNVERIFIED. It cannot
calculate intrinsic value or create any brokerage intents.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import argparse
import hashlib
import json
from pathlib import Path

import fund100_stock_sec_source_p4b_v1_0 as p4b
import fund100_stock_sec_forward_audit_p4c_v1_0 as p4c
import fund100_stock_sec_issuer_quality_p4e_v1_0 as p4e
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_V6_Q1_ORIGINAL_SEC_CASH_GENERATION_PROXY_SOURCE_GAP_V1"
TICKERS=("AAPL","MSFT","GOOGL","AMZN","XOM","JNJ","PG","KO")
EXPECTED_SOURCE_DATE="2026-10-15"
MISSING_VALUATION=(
 "timestamped_price_per_share_at_original_asof",
 "shares_outstanding_on_same_timestamp_and_class",
 "net_debt_and_enterprise_value_consistent_with_original_filings",
 "maintenance_capital_expenditure_separate_from_total_spend",
 "working_capital_normalization_and_nonrecurring_items",
 "share_issuance_and_stock_based_compensation_economic_adjustments",
 "acquisitions_and_disposals_cash_flow_treatment",
)
REPORT_ONLY="DESCRIPTIVE_REPORTED_CFO_MINUS_ISSUER_MAPPED_ASSET_SPENDING_NOT_OWNER_EARNINGS"


class Q1SourceStop(ValueError):pass


def money(value:object,name:str)->Decimal:
    if isinstance(value,bool) or type(value) not in (int,float,str,Decimal):
        raise Q1SourceStop("Non-accounting source value in "+name)
    try:v=Decimal(str(value))
    except (InvalidOperation,ValueError) as exc:raise Q1SourceStop("Bad "+name) from exc
    if not v.is_finite():raise Q1SourceStop("Nonfinite "+name)
    return v


def summarize(*,issuer_observations:list,financial_values:dict,source_manifest_sha256:str,
              original_capture_utc:str)->dict:
    """Pure, separately testable economics from prior original 10-K observations.

    Financial values MUST be independently provided by the separate original
    capture and accession check; source manifest verified in caller.
    """
    if (not isinstance(issuer_observations,list) or len(issuer_observations)!=len(TICKERS)
        or not isinstance(financial_values,dict) or set(financial_values)!=set(TICKERS)):
        raise Q1SourceStop("Original P4E issuer coverage not preserved")
    if source_manifest_sha256!=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256:
        raise Q1SourceStop("Must use same original audited October SEC source")
    if original_capture_utc!=p4g.FROZEN_SEC_OBSERVED_AT_UTC:
        raise Q1SourceStop("No reconstructed hindsight filing acquisition time")
    report=[]
    for ticker,obs in zip(TICKERS,issuer_observations):
        if not isinstance(obs,dict) or obs.get("ticker")!=ticker:
            raise Q1SourceStop("Wrong issuer identity or original cohort order")
        if obs.get("asof_research_date")!=EXPECTED_SOURCE_DATE:
            raise Q1SourceStop("Original issuer quality research date changed")
        score=obs.get("quality_score")
        row=financial_values[ticker]
        if not isinstance(row,dict):raise Q1SourceStop("No accession-linked values")
        available=score is not None
        if available and (type(score) is not int or score not in range(4)):
            raise Q1SourceStop("Unexpected audited quality score")
        if available:
            if (obs.get("state")!="DESCRIPTIVE_NEWEST_ORIGINAL_10K_ISSUER_SPECIFIC_QUALITY"
                or not isinstance(obs.get("latest_10k_accession"),str)
                or not obs.get("latest_10k_filing_date")
                or row.get("accession")!=obs["latest_10k_accession"]):
                raise Q1SourceStop("Unreconciled audited 10-K accession")
            cfo=money(row.get("operating_cash_usd"),"original operating cash flow")
            spend=money(row.get("productive_asset_spend_usd"),"original capex")
            revenue=money(row.get("revenue_usd"),"original revenue")
            if spend<0 or revenue<=0:
                raise Q1SourceStop("Malformed original capex or revenue")
            proxy=cfo-spend
            calculated=proxy/revenue
            rounded_margin=money(obs.get("free_cash_flow_margin"),"P4E published margin")
            if abs(calculated-rounded_margin)>Decimal("0.00000002"):
                raise Q1SourceStop("Independent CFO-capex arithmetic disagrees with P4E")
            financials={
                "operating_cash_usd":str(cfo),
                "issuer_mapped_reported_productive_asset_spend_usd":str(spend),
                "reported_operating_cash_after_asset_spending_usd":str(proxy),
                "reported_operating_cash_after_spending_margin":str(calculated.quantize(Decimal(".00000001"))),
            }
            status="ORIGINAL_SEC_CFO_MINUS_ASSET_SPENDING_VERIFIED_NOT_OWNER_EARNINGS"
        else:
            if row!={} or obs.get("state")=="DESCRIPTIVE_NEWEST_ORIGINAL_10K_ISSUER_SPECIFIC_QUALITY":
                raise Q1SourceStop("Cannot impute numbers for missing issuer")
            financials=None
            status="UNKNOWN_MISSING_AUDITABLE_ORIGINAL_10K_FACTS"
        report.append({
          "ticker":ticker,
          "issuer_cik":obs.get("cik"),
          "latest_original_10k_accession":obs.get("latest_10k_accession"),
          "latest_original_10k_filing_date":obs.get("latest_10k_filing_date"),
          "p4e_quality_score":score,
          "accounting_source_status":status,
          "cash_proxy":financials,
          "capital_spending_source_tag":obs.get("capex_source_tag"),
          "cash_flow_is_not_maintenance_capex_adjusted_owner_earnings":True,
          "historic_fair_value_signal_available":False,
          "current_trade_signal_available":False,
        })
    eligible=sum(x["cash_proxy"] is not None for x in report)
    if eligible!=6:
        raise Q1SourceStop("Original six-auditable two-missing P4E state drifted")
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_SEC_ISSUER_CASH_PROXY_RESEARCH_ONLY",
        "economic_hypothesis":"Business quality and valuation, separated from trend or blind sector exposure",
        "accounting_measure":REPORT_ONLY,
        "source_original_sec_manifest_sha256":source_manifest_sha256,
        "source_capture_utc":original_capture_utc,
        "issuer_count":len(report),"issuer_cfo_capex_complete_count":eligible,
        "unknown_issuer_count":len(report)-eligible,
        "source_original_latest_10k_only":True,
        "valuation_and_owner_earnings_inputs_missing":list(MISSING_VALUATION),
        "latest_available_sec_is_not_historical_point_in_time_universe":True,
        "cash_generation_is_not_stock_return_or_intrinsic_value":True,
        "company_specific_asset_spending_definitions_may_differ":True,
        "investable_historical_universe_available":False,
        "price_valuation_signal_available":False,
        "maintenance_capex_verified":False,
        "independently_validated_alpha":False,
        "candidate_research_promotion":False,
        "paper_authorized":False,"live_authorized":False,
        "broker_calls":0,"broker_orders":0,
        "observations":report,
    }


def from_original_sec_archive(path:Path)->dict:
    """Source-authenticate original raw 15 October SEC capture; no fresh SEC GET."""
    original=p4e.from_verified_source_artifact(path)
    if (original.get("source_original_manifest_sha256")!=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256
        or original.get("original_capture_utc")!=p4g.FROZEN_SEC_OBSERVED_AT_UTC
        or original.get("p4e_candidates_count")!=8
        or original.get("p4e_eligible_count")!=6):
        raise Q1SourceStop("Original captured SEC issuer data not reconciled")
    files=p4c.snapshot_files(path)
    review=p4c.audit(files)
    if review["source_original_manifest_sha256"]!=original["source_original_manifest_sha256"]:
        raise Q1SourceStop("P4C source archive hash disagrees with P4E")
    source_rows=p4e.source_mapping()
    amounts={}
    for i,obs in enumerate(original["observations"]):
        ticker=obs["ticker"]
        if ticker!=TICKERS[i] or source_rows[i]["ticker"]!=ticker:
            raise Q1SourceStop("Changed original issuer order")
        if obs["quality_score"] is None:
            amounts[ticker]={}
            continue
        cik=obs["cik"]
        facts=p4b.decode_source(files[f"raw/CIK{cik}-{ticker}-companyfacts.json"],expected_cik=cik)
        subs=p4b.decode_source(files[f"raw/CIK{cik}-{ticker}-submissions.json"],expected_cik=cik)
        # P4E already verified original accession identity, comparative years,
        # filing-day availability and issuer mapping.
        accession=obs["latest_10k_accession"]
        filed=obs["latest_10k_filing_date"]
        year_end=obs["latest_10k_fiscal_end"]
        tags={
            "operating_cash_usd":p4e.CFO,
            "productive_asset_spend_usd":source_rows[i]["capital_expenditure_us_gaap_tag"],
            "revenue_usd":source_rows[i]["revenue_us_gaap_tag"],
        }
        sec_facts=facts["facts"]["us-gaap"]
        vals={k:p4e.annual_value(sec_facts,tag,accession,filed,year_end)
              for k,tag in tags.items()}
        if any(v is None for v in vals.values()):
            raise Q1SourceStop("Actual SEC source no longer agrees with P4E accession evidence")
        amounts[ticker]={"accession":accession,**vals}
    return summarize(issuer_observations=original["observations"],
         financial_values=amounts,
         source_manifest_sha256=original["source_original_manifest_sha256"],
         original_capture_utc=original["original_capture_utc"])


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-sec-artifact",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    report=from_original_sec_archive(a.original_sec_artifact)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("V6-Q1 genuine SEC issuer cash generation sources",report["issuer_cfo_capex_complete_count"],"/8")
    for row in report["observations"]:
        print("V6_Q1",row["ticker"],row["accounting_source_status"])
    print("UNVERIFIED: maintenance capex, original as-of market valuation, comparable owner earnings, investable alpha")
    print("NO BROKER OR LIVE STOCK ORDERS",report["broker_orders"])


if __name__=="__main__":
    main()

"""P4E: synthetic original SEC accession, issuer-tag and time-gate invariants."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

import fund100_stock_sec_issuer_quality_p4e_v1_0 as p4e
from test_fund100_stock_sec_quality_p4a_v1_0 import sample, CIK, ACCESSIONS, FILINGS, DATES
from test_fund100_stock_sec_forward_audit_p4c_v1_0 import prepared, fake_zip


def prepared_current():
    facts,sub=sample()
    for concept in facts["facts"]["us-gaap"].values():
        array=concept["units"]["USD"]
        comp=deepcopy(array[0])
        comp["accn"]=ACCESSIONS[1]
        comp["filed"]=FILINGS[1]
        # same full-year date range but as published again in 2026 original 10-K
        array.append(comp)
    return facts,sub


def apple_row():
    return p4e.source_mapping()[0]


def test_research_mapping_has_eight_frozen_ciks_and_no_unverified_auto_tag_swaps():
    rows=p4e.source_mapping()
    assert len(rows)==8
    assert {r["ticker"] for r in rows}==set(p4e.FROZEN_REVENUE)
    assert p4e.FROZEN_REVENUE["GOOGL"]=="Revenues"
    assert p4e.FROZEN_REVENUE["KO"]=="Revenues"
    assert p4e.FROZEN_REVENUE["PG"]=="Revenues"
    assert p4e.FROZEN_CAPEX["AMZN"]=="PaymentsToAcquireProductiveAssets"
    assert p4e.FROZEN_REVENUE["XOM"]=="Revenues"
    assert p4e.FROZEN_REVENUE["JNJ"]=="RevenueFromContractWithCustomerExcludingAssessedTax"


def test_same_newest_filing_year_and_comparative_are_allowed_after_filing_only():
    f,s=prepared_current()
    result=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert result["state"]=="DESCRIPTIVE_NEWEST_ORIGINAL_10K_ISSUER_SPECIFIC_QUALITY"
    assert result["quality_score"]==3
    assert result["revenue_growth_yoy"]==pytest.approx(.2)
    assert result["operating_income_margin"]==pytest.approx(.15)
    assert result["free_cash_flow_margin"]==pytest.approx(.125)
    assert result["latest_10k_accession"]==ACCESSIONS[1]
    assert result["previous_10k_accession_for_period_provenance"]==ACCESSIONS[0]


def test_future_newest_10k_cannot_be_used_before_conservative_pub_day():
    f,s=prepared_current()
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-11-04")
    assert r["latest_10k_accession"]==ACCESSIONS[0]
    assert r["quality_score"] is None
    assert r["paper_authorized"] is False
    assert r["live_authorized"] is False


def test_previous_10k_full_facts_not_silently_mixed_with_current_accession():
    f,s=sample()
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert r["quality_score"] is None
    assert "revenue:comparative" in r["missing_concepts"]
    assert r["state"]=="LATEST_10K_MISSING_FROZEN_OR_COMPARATIVE_GAAP_FACT"


def test_no_older_complete_filing_fallback_when_newest_concept_missing():
    f,s=prepared_current()
    tag=p4e.FROZEN_REVENUE["AAPL"]
    a=f["facts"]["us-gaap"][tag]["units"]["USD"]
    f["facts"]["us-gaap"][tag]["units"]["USD"]=[r for r in a if r["accn"]!=ACCESSIONS[1]]
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert r["latest_10k_accession"]==ACCESSIONS[1]
    assert r["quality_score"] is None
    assert "revenue:current" in r["missing_concepts"]
    assert "revenue:comparative" in r["missing_concepts"]


def test_same_tag_year_to_year_and_no_ytd_rows():
    f,s=prepared_current()
    cap=p4e.FROZEN_CAPEX["AAPL"]
    a=f["facts"]["us-gaap"][cap]["units"]["USD"]
    for row in a:
        if row["accn"]==ACCESSIONS[1] and row["end"]==DATES[0]:
            row["start"]="2025-08-01"
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert "capital_expenditure:comparative" in r["missing_concepts"]
    assert r["quality_score"] is None


def test_conflicting_original_same_accession_facts_rejected():
    f,s=prepared_current()
    arr=f["facts"]["us-gaap"][p4e.FROZEN_REVENUE["AAPL"]]["units"]["USD"]
    duplicate=deepcopy(arr[-1]);duplicate["val"]+=1
    arr.append(duplicate)
    with pytest.raises(p4e.GAAPMappingStop,match="Conflicting"):
        p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")


def test_unreviewed_tag_swap_cik_or_company_rejected(tmp_path):
    rows=p4e.source_mapping()
    r=deepcopy(rows[0])
    r["revenue_us_gaap_tag"]="Revenues"
    f,s=prepared_current()
    with pytest.raises(p4e.GAAPMappingStop):
        p4e.newest_annual_quality(f,s,r,"2026-12-01")
    r=deepcopy(rows[0]);r["cik_10_digit"]="0000789019"
    with pytest.raises(p4e.GAAPMappingStop):
        p4e.newest_annual_quality(f,s,r,"2026-12-01")


def test_operating_income_cannot_be_replaced_by_pretax_income():
    f,s=prepared_current()
    del f["facts"]["us-gaap"][p4e.OPERATING]
    f["facts"]["us-gaap"]["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"]={
        "units":{"USD":[]}
    }
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert r["quality_score"] is None
    assert "operating_income:current" in r["missing_concepts"]


def test_company_specific_cash_asset_purchases_not_arbitrarily_substituted():
    rows=p4e.source_mapping()
    amazon=next(r for r in rows if r["ticker"]=="AMZN")
    assert amazon["capital_expenditure_us_gaap_tag"]=="PaymentsToAcquireProductiveAssets"
    assert amazon["revenue_us_gaap_tag"]==p4e.FROZEN_REVENUE["AMZN"]
    assert p4e.FROZEN_CAPEX["AAPL"] != p4e.FROZEN_CAPEX["AMZN"]


def test_data_from_future_filings_cannot_override_current_public_accounting():
    f,s=prepared_current()
    for name,c in f["facts"]["us-gaap"].items():
        for row in c.get("units",{}).get("USD",[]):
            if row.get("accn")==ACCESSIONS[1]:
                row["filed"]="2027-01-01"
    r=p4e.newest_annual_quality(f,s,apple_row(),"2026-12-01")
    assert r["quality_score"] is None


def test_audited_raw_sources_only_and_zero_broker_order_count(tmp_path):
    manifest,files=prepared()
    # add SAME 2026 filing accession prior annual comparative into raw
    name=next(n for n in files if n.endswith("-companyfacts.json"))
    f=json.loads(files[name])
    for concept in f["facts"]["us-gaap"].values():
        rows=concept.get("units",{}).get("USD",[])
        if len(rows)<2:continue
        old=deepcopy(rows[0])
        old["accn"]=ACCESSIONS[1]
        old["filed"]=FILINGS[1]
        rows.append(old)
    files[name]=json.dumps(f).encode()
    detail=manifest["companies"][0]["report_data_provenance"]["companyfacts"]
    detail["raw_sha256"]=p4e.p4c.digest(files[name])
    detail["byte_count"]=len(files[name])
    files["manifest-and-quality.json"]=json.dumps(manifest).encode()
    archive=tmp_path/"capture.zip"
    fake_zip(archive,files)
    report=p4e.from_verified_source_artifact(archive)
    assert report["p4e_candidates_count"]==1
    assert report["p4e_eligible_count"]==1
    assert report["observations"][0]["quality_score"]==3
    assert report["original_p4a_quality_counts_not_rewritten"] is True
    assert report["analyst_estimate_revision_signals_available"] is False
    assert report["historical_stock_alpha_or_returns_validated"] is False
    assert report["broker_orders"]==0
    assert report["paper_authorized"] is False
    assert report["live_authorized"] is False

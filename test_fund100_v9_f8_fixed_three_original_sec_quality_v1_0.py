"""Brokerless source regression: 3 exact F6 CIKs, original EPS + P4A cash quality."""
from datetime import datetime,timezone
from hashlib import sha256
import json

import pytest

import fund100_v9_f8_fixed_three_original_sec_quality_v1_0 as f8
import test_fund100_v9_f6_original_10k_diluted_eps_coverage_v1_0 as f6test

ASOF=datetime(2026,11,11,13,55,tzinfo=timezone.utc)
CANDIDATES=list(f6test.GOOD)
PRIOR_ACC="0001193125-25-000001"
PRIOR_FILED="2025-02-20"
PRIOR_START="2024-01-01"
PRIOR_END="2024-12-31"


def annual_sub(cik):
    original=f6test.subs(cik)
    recent=original["filings"]["recent"]
    for k,value in [
        ("accessionNumber",PRIOR_ACC),("form","10-K"),
        ("reportDate",PRIOR_END),("filingDate",PRIOR_FILED),
        ("acceptanceDateTime",PRIOR_FILED+"T16:30:00.000Z"),
    ]:
        recent[k].append(value)
    return original


def annual_facts(cik, *, previous=True, latest=True, eps=True,
                 prior_revenue=100_000_000, revenue=130_000_000,
                 operating_income=20_000_000, cashflow=30_000_000,
                 capex=5_000_000, bad_class=False):
    tag_values={
        "RevenueFromContractWithCustomerExcludingAssessedTax":
            (prior_revenue,revenue),
        "OperatingIncomeLoss":(10_000_000,operating_income),
        "NetCashProvidedByUsedInOperatingActivities":
            (15_000_000,cashflow),
        "PaymentsToAcquirePropertyPlantAndEquipment":(4_000_000,capex),
    }
    tags={}
    for label,(v0,v1) in tag_values.items():
        rows=[]
        if previous:
            rows.append(dict(accn=PRIOR_ACC,filed=PRIOR_FILED,
                             form="10-K",start=PRIOR_START,
                             end=PRIOR_END,val=v0))
        if latest:
            rows.append(dict(accn=f6test.ACC,filed=f6test.FILED,
                             form="10-K",start=f6test.START,
                             end=f6test.END,val=v1))
        tags[label]={"units":{"USD":rows}}
    if eps:
        tags["EarningsPerShareDiluted"]={
            "units":{"USD/shares":[{
                "accn":f6test.ACC,"filed":f6test.FILED,
                "form":"10-K","start":f6test.START,
                "end":f6test.END,"val":3.5,
            }]}}
    if bad_class:
        tags.pop("NetCashProvidedByUsedInOperatingActivities")
    return {"cik":cik,"facts":{"us-gaap":tags}}


def test_same_filing_old_and_new_positive_earnings_and_cashflow_score():
    status=f8.original_same_filing_quality_status(
        facts=annual_facts(CANDIDATES[0]),submissions=annual_sub(CANDIDATES[0]),
        cik=CANDIDATES[0],accession=f6test.ACC,filed=f6test.FILED,
        end=f6test.END,observed=ASOF)
    assert status=="ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_3_OF_3_REVIEW_ONLY"


@pytest.mark.parametrize("case,expected",[
    ({"previous":False},"ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD"),
    ({"latest":False},"ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD"),
    ({"bad_class":True},"ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD"),
    ({"eps":False},"FIRST_F6_ORIGINAL_POSITIVE_EPS_PROVENANCE_CHANGED_HOLD"),
    ({"revenue":80_000_000,"operating_income":0,"cashflow":0},
     "ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_0_OF_3_REVIEW_ONLY"),
    ({"revenue":80_000_000,"operating_income":20_000_000,"cashflow":0},
     "ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_1_OF_3_REVIEW_ONLY"),
    ({"revenue":80_000_000,"operating_income":20_000_000,"cashflow":30_000_000},
     "ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_2_OF_3_REVIEW_ONLY"),
])
def test_fixed_original_quality_rules_never_backfill_missing_or_refit(case,expected):
    assert f8.original_same_filing_quality_status(
        facts=annual_facts(CANDIDATES[0],**case),
        submissions=annual_sub(CANDIDATES[0]),cik=CANDIDATES[0],
        accession=f6test.ACC,filed=f6test.FILED,end=f6test.END,
        observed=ASOF)==expected


def test_original_quality_must_match_exact_same_f6_own_10k_not_older_preferred():
    assert f8.original_same_filing_quality_status(
        facts=annual_facts(CANDIDATES[0],latest=False),
        submissions=annual_sub(CANDIDATES[0]),cik=CANDIDATES[0],
        accession=f6test.ACC,filed=f6test.FILED,end=f6test.END,
        observed=ASOF)=="ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD"


def test_issuer_mismatch_with_positive_eps_never_qualifies_quality():
    assert f8.original_same_filing_quality_status(
        facts=annual_facts(CANDIDATES[1]),submissions=annual_sub(CANDIDATES[0]),
        cik=CANDIDATES[0],accession=f6test.ACC,filed=f6test.FILED,
        end=f6test.END,observed=ASOF)==(
        "FIRST_F6_ORIGINAL_POSITIVE_EPS_PROVENANCE_CHANGED_HOLD")


def source_fixture(monkeypatch, *, facts_map=None):
    # Keep an *entire* original eight-CIK/one-current-own-10K plus
    # one prior own filing. No replacement issuers or retrieval of data
    # for the other four plus one source-missing.
    counts,_,primary_get,_=f6test.sources(monkeypatch)
    digest=sha256(
        b"FUND100_V9_F6_FIRST_CLASS_MATCHED_CIKS_V1\n"+
        b"|".join(f"{c:010d}".encode() for c in sorted(CANDIDATES))
    ).hexdigest()
    monkeypatch.setattr(f8.f7,"F6_THREE_CIK_SHA256",digest)
    calls={"subs":[],"facts":[],"primary":[]}
    def sub(cik):
        calls["subs"].append(cik)
        if cik==f6test.ALL[-1]:
            return json.dumps(f6test.subs(cik,filed="2023-01-20",
                                         end="2022-12-31")).encode()
        return json.dumps(annual_sub(cik)).encode()
    def pri(path):
        calls["primary"].append(path)
        return primary_get(path)
    def facts(cik):
        calls["facts"].append(cik)
        value=(facts_map or {}).get(cik)
        if value=="404":return None
        if value=="no-prior": return json.dumps(
            annual_facts(cik,previous=False)).encode()
        if value=="bad-current":return json.dumps(
            annual_facts(cik,latest=False)).encode()
        return json.dumps(annual_facts(cik)).encode()
    return calls,sub,pri,facts,digest


def test_full_source_exact_eight_and_three_with_strict_score_and_no_leaks(monkeypatch):
    calls,sub,pri,facts,digest=source_fixture(monkeypatch)
    report=f8.assess(directories={},sec_raw=b"{}",observed=ASOF,
                     submissions_get=sub,primary_get=pri,
                     companyfacts_get=facts,min_pool=2)
    assert len(calls["subs"])==8
    assert len(calls["primary"])==7
    assert calls["facts"]==CANDIDATES
    assert report["original_eight_sec_issuer_count"]==8
    assert report["exact_first_three_class_issuer_count"]==3
    assert report["unchanged_first_three_cik_commitment"]==digest
    assert report["source_status_counts"]=={
        "ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_3_OF_3_REVIEW_ONLY":3,
        "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
        "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
    }
    assert report["economic_edge_vs_hold_acwi_or_event_strategy_proven"] is False
    assert report["issuer_quality_to_exact_share_class_or_intrinsic_value_proven"] is False
    assert report["live_authorized"] is False
    assert report["broker_gets"]==report["broker_posts"]==report["broker_orders"]==0
    obj=json.dumps(report)
    for secret in ("320193","1002","AAPL",f6test.ACC,
                   "130000000","2026-02-20","3.5"):
        assert secret not in obj


def test_original_missing_year_or_companyfacts_not_zero_quality(monkeypatch):
    calls,sub,pri,facts,digest=source_fixture(
        monkeypatch,facts_map={CANDIDATES[0]:"no-prior",
                               CANDIDATES[1]:"bad-current",
                               CANDIDATES[2]:"404"})
    report=f8.assess(directories={},sec_raw=b"{}",observed=ASOF,
                     submissions_get=sub,primary_get=pri,
                     companyfacts_get=facts,min_pool=2)
    assert report["source_status_counts"]=={
        "ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD":2,
        "ORIGINAL_SEC_COMPANYFACTS_404_HOLD":1,
        "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
        "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
    }
    assert len(calls["facts"])==3


def test_changed_f6_three_cik_source_is_hold_before_quality_get(monkeypatch):
    calls,sub,pri,facts,digest=source_fixture(monkeypatch)
    monkeypatch.setattr(f8.f7,"F6_THREE_CIK_SHA256","wrong")
    with pytest.raises(f8.f7.PriceCoverageHold,
                       match="three-issuer identity subset changed"):
        f8.assess(directories={},sec_raw=b"{}",observed=ASOF,
                  submissions_get=sub,primary_get=pri,
                  companyfacts_get=facts,min_pool=2)
    assert calls["facts"]==[]


def test_no_copying_any_private_fields_or_untrusted_source_error(monkeypatch):
    calls,sub,pri,facts,digest=source_fixture(monkeypatch)
    def malicious(cik):
        calls["facts"].append(cik)
        return b'{invalid json user/pw://secret}'
    report=f8.assess(directories={},sec_raw=b"{}",observed=ASOF,
                     submissions_get=sub,primary_get=pri,
                     companyfacts_get=malicious,min_pool=2)
    assert report["source_status_counts"][
        "ORIGINAL_SEC_ISSUER_QUALITY_SOURCE_UNQUALIFIED_HOLD"]==3
    assert "secret" not in json.dumps(report)

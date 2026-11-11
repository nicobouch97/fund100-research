"""Fixed-three original SEC own-10K EPS + two-FY quality source coverage.

Existing SEC P4A revenue growth, operating margin and FCF margin rules
are reused verbatim, not retuned to observed company results. Requires
source-specific latest original accession equality, F6 EPS provenance and
the precommitted exact eight-issuer and three-issuer CIK fingerprints.
Only aggregate coverage; no issuer/stock score rows, alpha or broker I/O.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import os
import time
from pathlib import Path

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_f5_original_sec_10k_class_crosscheck_v1_0 as f5
import fund100_v9_f6_original_10k_diluted_eps_coverage_v1_0 as f6
import fund100_v9_f7_current_completed_vendor_price_source_v1_0 as f7

SCHEMA="FUND100_V9_F8_FIXED_THREE_OWN_10K_TWO_FY_QUALITY_SOURCE_V1"
F6_ORIGINAL_OWN_EPS_RUN=43026350533
F7_ORIGINAL_COMPLETED_PRICE_RUN=43030160608
NO_BROKER_GET=NO_BROKER_POST=NO_BROKER_ORDERS=NO_PRIVATE_WRITES=0
LIVE_AUTHORIZED=False
SHARE_CLASS_VALUATION_VALIDATED=False

class QualitySourceHold(ValueError):
    pass


def original_same_filing_quality_status(*,facts:dict,submissions:dict,cik:int,
                                        accession:str,filed:str,end:str,
                                        observed:datetime)->str:
    """Require the original F6 EPS and same annual 10-K P4A quality packet.

    No average, all-company fallback, recent amended 10-K or price selection.
    Two full-fiscal-year quality is a *source* observation only, not alpha.
    """
    if type(observed) is not datetime or observed.tzinfo is None:
        raise QualitySourceHold("Source decision time missing")
    eps=f6.eps_original_own_accession_status(
        facts=facts,submissions=submissions,cik=cik,accession=accession,
        filed=filed,end=end)
    if eps!="ORIGINAL_OWN_10K_DILUTED_EPS_POSITIVE_REVIEW_ONLY":
        return "FIRST_F6_ORIGINAL_POSITIVE_EPS_PROVENANCE_CHANGED_HOLD"
    try:
        packet=quality.asof_quality(
            facts,submissions,f"{cik:010d}",
            observed.astimezone(timezone.utc).date().isoformat())
    except (quality.StockSourceStop,KeyError,TypeError,ValueError):
        return "ORIGINAL_SEC_TWO_FY_QUALITY_SOURCE_INVALID_HOLD"
    if packet.get("state")!="ANNUAL_REPORTED_QUALITY_AVAILABLE_NOT_TRADE_READY":
        return "ORIGINAL_SEC_TWO_FY_QUALITY_UNAVAILABLE_HOLD"
    # P4A may legitimately have a usable older annual pair but it MUST
    # NOT be silently promoted to quality for the 10-K used in F5/F6.
    if (packet.get("source_accession")!=accession or
        packet.get("annual_asof_source_period")!=end or
        packet.get("source_available_date")!=quality.availability_day(filed)):
        return "TWO_FY_QUALITY_NOT_SAME_F6_ORIGINAL_10K_HOLD"
    score=packet.get("score")
    if type(score) is not int or score not in (0,1,2,3):
        return "ORIGINAL_SEC_TWO_FY_QUALITY_SOURCE_INVALID_HOLD"
    return f"ORIGINAL_SAME_10K_TWO_FY_QUALITY_SCORE_{score}_OF_3_REVIEW_ONLY"


def assess(*,directories,sec_raw,observed,submissions_get,primary_get,
           companyfacts_get,min_pool=1000):
    """Same 8, same exact F6 three issuer identities, three companyfacts GETs."""
    if (type(observed) is not datetime or observed.tzinfo is None or
        not all(callable(x) for x in (
            submissions_get,primary_get,companyfacts_get))):
        raise QualitySourceHold("Original issuer source acquisition missing")
    source_cache={}
    hashes=[]
    def original_sub(cik):
        raw=submissions_get(cik)
        if raw is not None:
            if type(raw) is not bytes or not 2<=len(raw)<=sec.MAX_JSON_BYTES:
                raise QualitySourceHold("SEC submissions source invalid")
            source_cache[cik]=raw
            hashes.append(sha256(raw).hexdigest())
        return raw
    candidates,others,eight_sha,three_sha,primary_sha,n=f7.source_issuer_candidates(
        directories=directories,sec_raw=sec_raw,observed=observed,
        submissions_get=original_sub,primary_get=primary_get,min_pool=min_pool)
    states=Counter(others)
    if len(candidates)!=3:
        raise QualitySourceHold("Original first three issuer candidates changed")
    for cik,ticker,venue in candidates:
        try:
            sub=sec.decode_source(source_cache[cik],
                                  expected_cik=f"{cik:010d}")
            filing,reason=f5.candidate_filing(
                submissions=sub,cik=cik,observed=observed)
            if filing is None:
                states["ORIGINAL_ANNUAL_SOURCE_DRIFT_AFTER_CLASS_REVIEW_HOLD"]+=1
                continue
            _,accession,filed,end=filing
            try:
                raw=companyfacts_get(cik)
            except broad.SourceHold:
                states["ORIGINAL_SEC_COMPANYFACTS_SOURCE_UNAVAILABLE_HOLD"]+=1
                continue
            if raw is None:
                states["ORIGINAL_SEC_COMPANYFACTS_404_HOLD"]+=1
                continue
            if type(raw) is not bytes or not 2<=len(raw)<=sec.MAX_JSON_BYTES:
                states["ORIGINAL_SEC_COMPANYFACTS_INVALID_SIZE_HOLD"]+=1
                continue
            hashes.append(sha256(raw).hexdigest())
            facts=sec.decode_source(raw,expected_cik=f"{cik:010d}")
            status=original_same_filing_quality_status(
                facts=facts,submissions=sub,cik=cik,accession=accession,
                filed=filed,end=end,observed=observed)
            states[status]+=1
        except (sec.SecIntakeStop,quality.StockSourceStop,
                f5.CoverHold,KeyError,TypeError):
            states["ORIGINAL_SEC_ISSUER_QUALITY_SOURCE_UNQUALIFIED_HOLD"]+=1
    if sum(states.values())!=n:
        raise QualitySourceHold("Original eight issuer SEC quality counts do not reconcile")
    return {
        "schema":SCHEMA,
        "observed_utc":observed.astimezone(timezone.utc).isoformat(),
        "original_eight_sec_issuer_count":n,
        "exact_first_three_class_issuer_count":len(candidates),
        "first_positive_eps_original_source_run":F6_ORIGINAL_OWN_EPS_RUN,
        "first_completed_vendor_price_original_source_run":F7_ORIGINAL_COMPLETED_PRICE_RUN,
        "unchanged_first_eight_cik_commitment":eight_sha,
        "unchanged_first_three_cik_commitment":three_sha,
        "original_10k_documents_commitment":primary_sha,
        "original_sec_submissions_companyfacts_sha256":sha256(
            ("\n".join(hashes)+"\n").encode()).hexdigest(),
        "source_status_counts":dict(sorted(states.items())),
        "original_own_two_year_us_gaap_cashflow_revenue_margin_review_only":True,
        "same_filing_positive_eps_required_for_quality":True,
        "source_comparison_uses_existing_predeclared_p4a_quality_criteria":True,
        "analyst_expectations_revisions_or_next_growth_authenticated":False,
        "original_sec_cik_to_permanent_share_class_figi_legally_proven":False,
        "issuer_quality_to_exact_share_class_or_intrinsic_value_proven":False,
        "survivor_free_historical_population_proven":False,
        "economic_edge_vs_hold_acwi_or_event_strategy_proven":False,
        "live_authorized":False,
        "broker_gets":0,"broker_posts":0,
        "broker_orders":0,"private_state_writes":0,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise QualitySourceHold("Original quality source report already exists")
    if (os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE")!="DISABLED"):
        raise QualitySourceHold("Only protected no-broker original main source")
    agent=sec.contact_user_agent(os.getenv("SEC_USER_AGENT"))
    official={name:listing._get_official(name) for name in listing.FILES}
    current=link.fetch_sec(agent=agent)
    observed=datetime.now(timezone.utc)
    def sub(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"submissions",agent=agent)
    def primary(path):
        time.sleep(.4)
        return f5.p4u._official_primary_10k_get(path,agent)
    def facts(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"companyfacts",agent=agent)
    result=assess(directories=official,sec_raw=current,observed=observed,
                  submissions_get=sub,primary_get=primary,
                  companyfacts_get=facts)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("Original eight issuer source denominator:",result["original_eight_sec_issuer_count"])
    print("First three issuer fixed quality source statuses:",result["source_status_counts"])
    print("Zero stock names, CIKs, annual values, account or broker network.")


if __name__=="__main__":
    main()

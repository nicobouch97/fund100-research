"""Original annual diluted EPS source coverage for the exact frozen F5 issuer cohort.

Research-only coverage, NOT P/E, a share-class fundamental valuation, or alpha.
Reuse original SEC latest own 10-K Section 12(b) class row, accession/lag,
companyfacts own-10-K per-share fact parser, and exact precommitted eight CIKs.
Only redacted aggregate categories, hashes and run clock leave process memory.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import math
import os
import time
from pathlib import Path

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
import fund100_stock_sec_eps_yield_p4s_v1_0 as p4s
import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_f4_current_openfigi_class_reference_v1_0 as f4
import fund100_v9_f5_original_sec_10k_class_crosscheck_v1_0 as f5

SCHEMA = "FUND100_V9_F6_OWN_10K_ANNUAL_DILUTED_EPS_COVERAGE_NO_VALUATION_V1"
F5_FIRST_OWN_10K_RUN = 43021601200
F5_CLASS_MATCHES = 3
MATCH = "EXACT_OWN_10K_12B_SYMBOL_COMMON_VENUE_REVIEW_ONLY_NOT_FIGI_PROVEN"
NO_BROKER_GET = NO_BROKER_POST = NO_BROKER_ORDERS = NO_PRIVATE_WRITES = 0
LIVE_AUTHORIZED = False

class EpsCoverageHold(ValueError):
    pass


def eps_original_own_accession_status(*, facts: dict, submissions: dict, cik: int,
                                       accession: str, filed: str, end: str) -> str:
    """Require the same original 10-K accession and date, never current EPS."""
    try:
        quality.validate_identity(facts, submissions, f"{cik:010d}")
        filings = quality.submissions_index(submissions)
        original = filings.get(accession)
        if (original is None or original["form"] != "10-K"
            or original["filed"] != filed or original["end"] != end):
            return "ORIGINAL_OWN_10K_EPS_FILING_IDENTITY_HOLD"
        metrics = facts["facts"]["us-gaap"]
        eps = p4s.original_annual_eps(metrics, accession, filed, end)
    except (KeyError, TypeError, quality.StockSourceStop,
            p4s.EarningsYieldStop):
        return "ORIGINAL_EPS_SOURCE_UNQUALIFIED_HOLD"
    if eps is None:
        return "ORIGINAL_OWN_10K_DILUTED_EPS_NOT_AVAILABLE_HOLD"
    if type(eps) not in (int, float) or not math.isfinite(eps):
        return "ORIGINAL_EPS_SOURCE_UNQUALIFIED_HOLD"
    if eps <= 0:
        return "ORIGINAL_OWN_10K_DILUTED_EPS_NONPOSITIVE_REVIEW_ONLY"
    return "ORIGINAL_OWN_10K_DILUTED_EPS_POSITIVE_REVIEW_ONLY"


def assess(*, directories: dict, sec_raw: bytes, observed: datetime,
           submissions_get, primary_get, facts_get, min_pool=1000):
    """Original eight CIKs, zero opportunistic reselection or account I/O."""
    if (type(observed) is not datetime or observed.tzinfo is None
        or not all(callable(x) for x in
                   (submissions_get, primary_get, facts_get))):
        raise EpsCoverageHold("Original source acquisition contract unavailable")
    jobs, digest, n = f4.selected_jobs(
        directories=directories, sec_raw=sec_raw, observed=observed,
        min_pool=min_pool)
    if (digest != f5.FROZEN_F4_CIK_COMMITMENT or n != 8
        or len(jobs) > 8):
        raise EpsCoverageHold("Original eight issuer cohort changed")
    states = Counter()
    documents = []
    class_matches = 0
    matched_ciks = []
    companyfacts_requested = 0
    for cik, ticker, venue in jobs:
        try:
            subs_raw = submissions_get(cik)
            if subs_raw is None:
                states["ORIGINAL_ISSUER_SUBMISSIONS_UNAVAILABLE_HOLD"] += 1
                continue
            if type(subs_raw) is not bytes or not 2 <= len(subs_raw) <= sec.MAX_JSON_BYTES:
                raise EpsCoverageHold("Original SEC submissions missing/oversized")
            submissions = sec.decode_source(subs_raw,expected_cik=f"{cik:010d}")
            documents.append(sha256(subs_raw).hexdigest())
            filing, reason = f5.candidate_filing(
                submissions=submissions,cik=cik,observed=observed)
            if filing is None:
                states[reason] += 1
                continue
            path, accession, filed, end = filing
            try:
                original, index_raw, filename, primary_url, index_url = primary_get(path)
            except p4u.FilingSourceFailure as exc:
                states[f5.sec_original_archive_hold(exc)] += 1
                continue
            if (type(original) is not bytes or not 0 < len(original) <= p4u.MAX_PRIMARY_10K_BYTES
                or type(index_raw) is not bytes or not 0 < len(index_raw) <= p4u.MAX_FILING_INDEX_BYTES
                or p4u._primary_10k_from_index(path, index_raw) !=
                   (filename,index_url,primary_url)):
                raise EpsCoverageHold("Original canonical 10-K index proof invalid")
            parsed = p4u.inspect_primary_10k(original)
            documents.extend([sha256(index_raw).hexdigest(),
                              sha256(original).hexdigest()])
            reason = f5.classify_10k(parsed=parsed,ticker=ticker,venue=venue)
            if reason != MATCH:
                states[reason] += 1
                continue
            class_matches += 1
            matched_ciks.append(cik)
            companyfacts_requested += 1
            try:
                facts_raw = facts_get(cik)
            except broad.SourceHold:
                states["ORIGINAL_SEC_COMPANYFACTS_SOURCE_UNAVAILABLE_HOLD"] += 1
                continue
            if facts_raw is None:
                states["ORIGINAL_SEC_COMPANYFACTS_404_HOLD"] += 1
                continue
            if type(facts_raw) is not bytes or not 2 <= len(facts_raw) <= sec.MAX_JSON_BYTES:
                states["ORIGINAL_SEC_COMPANYFACTS_SIZE_HOLD"] += 1
                continue
            documents.append(sha256(facts_raw).hexdigest())
            facts = sec.decode_source(facts_raw,expected_cik=f"{cik:010d}")
            states[eps_original_own_accession_status(
                facts=facts,submissions=submissions,cik=cik,
                accession=accession,filed=filed,end=end)] += 1
        except (sec.SecIntakeStop, quality.StockSourceStop, f5.CoverHold,
                p4u.ListingEvidenceStop):
            states["ORIGINAL_SEC_ISSUER_SOURCE_UNQUALIFIED_HOLD"] += 1
    if n - len(jobs):
        states["PRECOMMITTED_ISSUER_ALIAS_OR_SOURCE_MISSING_HOLD"] = n-len(jobs)
    if sum(states.values()) != n:
        raise EpsCoverageHold("Eps original source statuses fail to reconcile")
    # Existing verified F5 first reception observed three class candidates;
    # do not choose only the new favored companies if original source drifts.
    if class_matches != F5_CLASS_MATCHES:
        raise EpsCoverageHold("Original F5 three class matches changed; no EPS cohort promoted")
    class_subset_hash = sha256(
        b"FUND100_V9_F6_FIRST_CLASS_MATCHED_CIKS_V1\\n" +
        b"|".join(f"{c:010d}".encode("ascii") for c in sorted(matched_ciks))
    ).hexdigest()
    return {
        "schema":SCHEMA,
        "first_f5_own_10k_run":F5_FIRST_OWN_10K_RUN,
        "frozen_eight_issuer_cik_commitment":digest,
        "source_received_utc":observed.astimezone(timezone.utc).isoformat(),
        "original_source_document_sha256_commitment":sha256(
            ("\n".join(documents)+"\n").encode()).hexdigest(),
        "original_issuer_denominator":n,
        "original_issuer_declared_12b_class_candidates":class_matches,
        "current_12b_class_candidate_issuer_commitment_sha256":class_subset_hash,
        "companyfacts_source_requests_for_only_class_candidates":companyfacts_requested,
        "source_status_counts":dict(sorted(states.items())),
        "eps_is_issuer_us_gaap_not_proven_share_class_valuation":True,
        "eps_original_filing_accession_date_matching_required":True,
        "independent_issuer_cik_to_figi_proven":False,
        "class_specific_shares_and_market_cap_price_verified":False,
        "expected_alpha_or_cheap_stock_inferred":False,
        "historical_delisted_security_universe_proven":False,
        "live_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "private_state_writes":0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    opts = p.parse_args()
    if opts.out.exists():
        raise EpsCoverageHold("Original EPS source receipt output exists")
    if (os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE") != "DISABLED"):
        raise EpsCoverageHold("Only protected main, STOP, no-broker original source")
    agent = sec.contact_user_agent(os.getenv("SEC_USER_AGENT"))
    dirs = {filename:listing._get_official(filename) for filename in listing.FILES}
    sec_raw = link.fetch_sec(agent=agent)
    observed = datetime.now(timezone.utc)
    def subs(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"submissions",agent=agent)
    def primary(path):
        time.sleep(.4)
        return p4u._official_primary_10k_get(path,agent)
    def facts(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"companyfacts",agent=agent)
    output = assess(directories=dirs,sec_raw=sec_raw,observed=observed,
                    submissions_get=subs,primary_get=primary,facts_get=facts)
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(output,sort_keys=True,indent=2)+"\n")
    print("Frozen original SEC issuer cohort",output["original_issuer_denominator"])
    print("Original 10-K class-matched earnings source statuses",output["source_status_counts"])
    print("Research-only original filing coverage; zero stock values, CIKs, FIGIs, broker I/O.")


if __name__ == "__main__":
    main()

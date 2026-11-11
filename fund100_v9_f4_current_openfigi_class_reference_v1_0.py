"""V9-F4: first *current* free OpenFIGI security metadata source, research only.

Original Nasdaq/SEC candidate source is reused, and the precommitted first
eight SHA256-chosen V9 issuers are never replaced when identification fails.
OpenFIGI provides a candidate share-class identifier, NOT a CIK corroboration,
historic listing, as-of identity, actual class shares or trading authority.
The OpenFIGI POST is a publicly documented idempotent DATA QUERY, never a
broker/order POST. All published results are only category counts and hashes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
import argparse
import json
import os
import re

import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
import fund100_stock_sec_source_p4b_v1_0 as sec

SCHEMA = "FUND100_V9_F4_CURRENT_OPENFIGI_CANDIDATE_CLASS_SOURCE_NO_VALUATION_V1"
URL = "https://api.openfigi.com/v3/mapping"
REGISTERED_COHORT_SIZE = 8
MAX_RESPONSE_BYTES = 250_000
MAX_RAW_SOURCE_BYTES = 7_000_000
NO_BROKER_GETS = NO_BROKER_POSTS = NO_BROKER_ORDERS = NO_PRIVATE_WRITES = 0
LIVE_AUTHORIZED = False
RESEARCH_ONLY = True

class FigiHold(ValueError):
    pass


def selected_jobs(*, directories, sec_raw, observed, min_pool=1000):
    if type(observed) is not datetime or observed.tzinfo is None:
        raise FigiHold("Missing source acquisition clock")
    # Precommitted selection is the PREFIX of the V9 32-CIK sample, NOT a
    # finance/price-informed sample or a preferred set of easy mapped shares.
    sample, digest, _ = broad.eligible_issuer_sample(
        directories=directories, sec_associations=sec_raw,
        observed=observed, sample_n=REGISTERED_COHORT_SIZE,
        min_pool=min_pool)
    rows, _ = link.candidate_rows(directories, observed=observed, min_rows=1)
    index, _, _ = link.sec_records(sec_raw, min_rows=1)
    roots = Counter(t for t, _, _ in rows)
    # Include originally unqualified aliases, null venues and unusual
    # ticker formats in the CIK one-to-many ambiguity, not just SEC index.
    original = json.loads(sec_raw.decode("utf-8-sig"))
    associations = defaultdict(set)
    for cik, _, ticker, exchange in original["data"]:
        associations[cik].add((ticker, exchange))
    candidates = defaultdict(set)
    selected = set(sample)
    for ticker, venue, cue in rows:
        if cue != broad.CUE or roots[ticker] != 1:
            continue
        records = index.get(ticker)
        if records is None or len(records) != 1:
            continue
        cik, sec_venue = next(iter(records))
        if cik in selected and sec_venue == venue:
            candidates[cik].add((ticker, venue))
    records = []
    for cik in sample:
        linked = candidates[cik]
        if len(linked) == 1 and len(associations[cik]) == 1:
            ticker, venue = next(iter(linked))
            records.append((cik, ticker, venue))
    # No replacement of source-missing/ambiguous selected issuers.
    if len(records) > REGISTERED_COHORT_SIZE:
        raise FigiHold("Registered source cohort expanded")
    return records, digest, len(sample)


def mapping_payload(jobs):
    if (type(jobs) is not list or not 0 < len(jobs) <= REGISTERED_COHORT_SIZE
        or any(type(j) is not tuple or len(j)!=3 for j in jobs)):
        raise FigiHold("OpenFIGI bounded query jobs missing")
    seen = set()
    payload = []
    for cik, ticker, venue in jobs:
        if (type(cik) is not int or cik<=0
            or type(ticker) is not str
            or re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,18}", ticker) is None
            or venue not in {"Nasdaq", "NYSE", "NYSE American", "NYSE Arca",
                             "Cboe", "IEX"}):
            raise FigiHold("Noncanonical originally matched security query")
        if ticker in seen:
            raise FigiHold("Duplicate ticker query")
        seen.add(ticker)
        # The venue is independently required at the source selection gate.
        # OpenFIGI US alone is not an independently verified venue+CIK join.
        payload.append({"idType":"TICKER", "idValue":ticker,
                        "exchCode":"US", "includeUnlistedEquities":True})
    return payload


def fetch_mapping(*, jobs):
    payload = mapping_payload(jobs)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    req = Request(URL, data=body, method="POST", headers={
        "Content-Type":"application/json", "Accept":"application/json",
        "User-Agent":"Fund100-public-research-source-audit/1.0"})
    try:
        with build_opener(listing._NoRedirect).open(req, timeout=25) as response:
            if (response.status != 200 or response.geturl() != URL
                or "json" not in response.headers.get("Content-Type","").lower()):
                raise FigiHold("OpenFIGI original response invalid")
            raw = response.read(MAX_RESPONSE_BYTES+1)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        raise FigiHold("OpenFIGI source unavailable or non-success") from None
    if not 2 <= len(raw) <= MAX_RESPONSE_BYTES:
        raise FigiHold("OpenFIGI original source absent or oversized")
    return raw


def _valid_id(value):
    return type(value) is str and re.fullmatch(r"[A-Z0-9]{12}", value) is not None


def classify(*, jobs, raw):
    payload=mapping_payload(jobs)
    if type(raw) is not bytes or not 2 <= len(raw) <= MAX_RESPONSE_BYTES:
        raise FigiHold("Missing original response bytes")
    try:
        data=json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise FigiHold("Malformed original OpenFIGI response") from None
    if type(data) is not list or len(data)!=len(payload):
        raise FigiHold("OpenFIGI return job order/count unqualified")
    counts=Counter()
    across={}
    for (_,ticker,_),response in zip(jobs,data):
        if type(response) is not dict or not set(response).issubset(
                {"data","error","warning"}) or not response:
            raise FigiHold("Unrecognised OpenFIGI job schema")
        if "warning" in response:
            # Warnings can indicate incomplete source; never claim a class.
            counts["SOURCE_WARNED_UNQUALIFIED"]+=1
            continue
        if "error" in response:
            if type(response["error"]) is not str:
                raise FigiHold("Malformed source error type")
            counts["SOURCE_NO_MAPPING_OR_ERROR"]+=1
            continue
        entries=response.get("data")
        if type(entries) is not list or len(entries)>15000:
            raise FigiHold("Unbounded original security mapping rows")
        if len(entries)!=1:
            counts["ZERO_OR_MULTIPLE_OPENFIGI_CANDIDATES_HOLD"]+=1
            continue
        obj=entries[0]
        if type(obj) is not dict:
            raise FigiHold("Invalid OpenFIGI security record")
        if (obj.get("ticker")!=ticker or obj.get("exchCode")!="US"
            or not _valid_id(obj.get("figi"))
            or not _valid_id(obj.get("compositeFIGI"))
            or not _valid_id(obj.get("shareClassFIGI"))):
            counts["UNMATCHED_OR_MISSING_INSTRUMENT_ID_HOLD"]+=1
            continue
        if (obj.get("marketSector")!="Equity"
            or obj.get("securityType2")!="Common Stock"):
            counts["NONCOMMON_OR_UNVERIFIED_INSTRUMENT_HOLD"]+=1
            continue
        candidate=obj["shareClassFIGI"]
        if candidate in across:
            # Two different SEC CIKs apparently resolve to same share
            # class: do not present either as an independent candidate.
            counts["DUPLICATE_CLASS_CROSS_ISSUER_HOLD"]+=1
            if across[candidate]:
                counts["CURRENT_SYMBOL_COMMON_CLASS_CANDIDATE_NOT_CIK_PROVEN"]-=1
                counts["DUPLICATE_CLASS_CROSS_ISSUER_HOLD"]+=1
                across[candidate]=False
            continue
        across[candidate]=True
        counts["CURRENT_SYMBOL_COMMON_CLASS_CANDIDATE_NOT_CIK_PROVEN"]+=1
    if sum(counts.values())!=len(jobs):
        raise FigiHold("OpenFIGI source classifications fail original count")
    return dict(sorted(counts.items()))


def report(*,directories,sec_raw,observed,figi_raw,figi_observed,
           min_pool=1000):
    if (type(observed) is not datetime or observed.tzinfo is None
        or type(figi_observed) is not datetime or figi_observed.tzinfo is None
        or figi_observed < observed):
        raise FigiHold("Original source clocks absent or reversed")
    jobs, commitment, total=selected_jobs(
        directories=directories,sec_raw=sec_raw,
        observed=observed,min_pool=min_pool)
    if not jobs:
        # No POST is justified if actual issuer cohort has no credible symbol.
        raise FigiHold("No supported original SEC candidate for OpenFIGI")
    counts=classify(jobs=jobs,raw=figi_raw)
    return {
        "schema":SCHEMA,
        "stage":"CURRENT_FREE_REFERENCE_SOURCE_ONLY_NOT_HISTORICAL_SECURITY_MASTER",
        "original_source_asof_utc":observed.astimezone(timezone.utc).isoformat(),
        "original_openfigi_response_at_utc":figi_observed.astimezone(timezone.utc).isoformat(),
        "original_eight_cik_sha256_commitment":commitment,
        "registered_original_issuer_cohort_not_return_selected":total,
        "first_eight_source_linked_current_symbols_queried":len(jobs),
        "precommitted_issuer_source_missing_or_ambiguous":total-len(jobs),
        "original_openfigi_response_sha256":sha256(figi_raw).hexdigest(),
        "source_status_counts_not_issuer_to_class_corroboration":counts,
        "openfigi_endpoint":URL,
        "openfigi_vendor_identity_not_sec_cik_verified":True,
        "underlying_us_share_class_permanent_id_verified":False,
        "original_historical_asof_membership_or_delisting_verified":False,
        "class_specific_share_count_price_or_market_cap_verified":False,
        "security_selection_expected_alpha_evaluated":False,
        "live_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "private_state_writes":0,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise FigiHold("Original source report already exists")
    if (os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE")!="DISABLED"):
        raise FigiHold("Protected no-broker main research-only environment required")
    agent=os.getenv("SEC_USER_AGENT")
    sec.contact_user_agent(agent)
    directories={name:listing._get_official(name) for name in listing.FILES}
    sec_raw=link.fetch_sec(agent=agent)
    observed=datetime.now(timezone.utc)
    jobs,_,_=selected_jobs(directories=directories,sec_raw=sec_raw,
                           observed=observed)
    raw=fetch_mapping(jobs=jobs)
    seen=datetime.now(timezone.utc)
    outcome=report(directories=directories,sec_raw=sec_raw,observed=observed,
                   figi_raw=raw,figi_observed=seen)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(outcome,sort_keys=True,indent=2)+"\n")
    print("Original source-linked fixed cohort:",outcome[
        "registered_original_issuer_cohort_not_return_selected"])
    print("OpenFIGI no-key original query count:",1)
    print("No issuer names, CIKs, tickers, FIGIs, stock valuation or broker calls.")


if __name__=="__main__":
    main()

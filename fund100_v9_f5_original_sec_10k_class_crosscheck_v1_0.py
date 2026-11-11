"""Original 10-K Section 12(b) symbol/class source for frozen F4 SEC CIKs.

Research ONLY. Independently inspect SEC-issuer original 10-K primary bytes,
with source-index linkage and original filing lag. An OpenFIGI current mapping
by ticker is not yet a proven issuer->FIGI security master; this is a
supplementary issuer-filed, ticker-and-venue class disclosure audit, not a
valuation or broker authorization. Never emit identifiers or source values.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, date, timezone
from hashlib import sha256
import argparse
import json
import os
import re
import time
from pathlib import Path

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
import fund100_v9_f4_current_openfigi_class_reference_v1_0 as f4

SCHEMA="FUND100_V9_F5_ORIGINAL_SEC_10K_CURRENT_TICKER_CLASS_CROSSCHECK_V1"
F4_FIRST_SOURCE_RUN=43008393873
# First independently observed eight SEC CIK roster, *not* eight securities.
FROZEN_F4_CIK_COMMITMENT="caa63b8763c38ae04e911ed05f7baaba086722062b5ba0d134c0b0082c21d972"
FROZEN_F4_OPENFIGI_RESPONSE_SHA256="6ae1334d76b7680a437ce2ef6f8132248027792c87ed31d967bae283b939d529"
MAX_AGE_FY_DAYS=550
MAX_SOURCE_PER_ISSUER=3
NO_BROKER_READS=NO_BROKER_POSTS=NO_BROKER_ORDERS=NO_PRIVATE_WRITES=0
LIVE_AUTHORIZED=False

class CoverHold(ValueError):
    pass


# These are literal, independently defined P4U original SEC filing source
# error codes. Expose at most the bounded *reason family*, never an HTTP
# response body/header, issuer, accession, filename, URL or contact user agent.
# The first F5 source receipt exposed seven unqualified original 10-K archive
# requests; a generic unavailable category cannot distinguish a 403/429 from
# a genuinely non-unique 10-K filing-index table.
SAFE_SEC_ARCHIVE_SOURCE_REASONS = frozenset({
    "HTTP_403", "HTTP_404", "HTTP_429", "HTTP_5XX", "HTTP_OTHER",
    "TIMEOUT", "NETWORK_UNAVAILABLE", "TRANSPORT_ERROR", "INCOMPLETE_SOURCE",
    "EMPTY_SOURCE", "NONCANONICAL_HTTP_RESPONSE", "PRIMARY_INDEX_INVALID",
    "PRIMARY_INDEX_UNSAFE_DOCUMENT", "PRIMARY_INDEX_UNSAFE_LINK",
    "PRIMARY_INDEX_10K_NOT_UNIQUE", "PRIMARY_INDEX_IDENTITY_MISMATCH",
    "PRIMARY_INDEX_OVERSIZED", "PRIMARY_10K_OVERSIZED",
})


def sec_original_archive_hold(exc: p4u.FilingSourceFailure) -> str:
    """Opaque, allowlisted, redacted source failure: no untrusted details."""
    if not isinstance(exc, p4u.FilingSourceFailure):
        raise CoverHold("Original source failure contract unavailable")
    reason = exc.reason_code
    if type(reason) is str and reason in SAFE_SEC_ARCHIVE_SOURCE_REASONS:
        return "ORIGINAL_SEC_ARCHIVE_" + reason + "_HOLD"
    return "ORIGINAL_SEC_ARCHIVE_UNCLASSIFIED_SOURCE_FAILURE_HOLD"


def candidate_filing(*, submissions:dict, cik:int, observed:datetime):
    """Latest own 10-K source accession only; never infer a historic stock."""
    if type(cik) is not int or not 0<cik<10_000_000_000:
        raise CoverHold("Invalid original SEC issuer identity")
    if type(observed) is not datetime or observed.tzinfo is None:
        raise CoverHold("Missing acquisition clock")
    day=observed.astimezone(timezone.utc).date()
    # The authentic SEC submissions API sends the CIK as a digit string,
    # while its companyfacts endpoint often sends an integer. Reuse the
    # existing bounded issuer identity contract; never coerce arbitrary text
    # or a mismatched/bool/floating identity into a successful match.
    if (type(submissions) is not dict
        or not quality.cik_matches_expected(submissions.get("cik"),
                                            f"{cik:010d}")):
        raise CoverHold("SEC submissions response CIK inconsistent")
    try:
        ledger=quality.submissions_index(submissions)
    except (KeyError, TypeError, ValueError, quality.StockSourceStop):
        raise CoverHold("Original SEC submissions accession ledger invalid") from None
    eligible={}
    for accession, meta in ledger.items():
        if meta["form"]!="10-K":
            continue
        end=quality.iso_date(meta["end"],"10-K original period")
        filed=quality.iso_date(meta["filed"],"10-K original filed")
        available=quality.iso_date(quality.availability_day(meta["filed"]),
                                   "10-K conservative availability")
        if not (end<=filed<=day and available<=day
                and 0<=(day-end).days<=MAX_AGE_FY_DAYS):
            continue
        eligible.setdefault(end,[]).append((accession,meta))
    if not eligible:
        return None,"NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD"
    latest=max(eligible)
    if len(eligible[latest])!=1:
        return None,"AMBIGUOUS_MULTIPLE_ORIGINAL_10K_FOR_FY_HOLD"
    accession,meta=eligible[latest][0]
    # SEC archive data/Cik/{accession}.txt is a canonical provenance
    # *construction*, not trusted metadata or a redirect-following fetch.
    path=f"edgar/data/{cik}/{accession}.txt"
    if p4u.ARCHIVE_PATH.fullmatch(path) is None:
        raise CoverHold("Original 10-K accession path cannot be constructed")
    return (path, accession,meta["filed"],meta["end"]),"SOURCE_ELIGIBLE"


def venue_matches(value:str,expected:str)->bool:
    """Conservatively match distinct issuer-declared original exchanges."""
    if type(value) is not str or type(expected) is not str:
        return False
    phrase=" ".join(value.upper().split())
    if len(phrase)>180:
        return False
    if expected=="Nasdaq":
        return "NASDAQ" in phrase and "NYSE" not in phrase
    if expected=="NYSE":
        return (("NEW YORK STOCK EXCHANGE" in phrase or "NYSE" in phrase)
                and not any(x in phrase for x in ("AMERICAN","ARCA")))
    if expected=="NYSE American":
        return "NYSE AMERICAN" in phrase
    if expected=="NYSE Arca":
        return "NYSE ARCA" in phrase
    # Existing conservative P4U structured cover extractor does not verify
    # Cboe/IEX; never guess or promote those current associations.
    return False


def classify_10k(*, parsed:dict, ticker:str,venue:str)->str:
    """One own filing, one explicit plain-common 12b row, same original symbol."""
    if (type(parsed) is not dict or type(ticker) is not str
        or re.fullmatch(r"[A-Z][A-Z0-9.-]{0,18}",ticker) is None
        or venue not in {"Nasdaq","NYSE","NYSE American","NYSE Arca","Cboe","IEX"}):
        raise CoverHold("Original SEC cover input contract invalid")
    rows=parsed.get("possible_12b_security_class_rows")
    if type(rows) is not list or len(rows)>100:
        raise CoverHold("Original 10-K 12b row source malformed")
    if not rows:
        return "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD"
    if len(rows)!=1:
        return "MULTIPLE_PLAIN_COMMON_12B_CLASSES_AMBIGUOUS_HOLD"
    row=rows[0]
    if (type(row) is not dict or set(row)!={
        "security_class_text","exchange_text","trading_symbol_in_original_10k","evidence_level"}
        or row["evidence_level"]!="ORIGINAL_10K_12B_ROW_REVIEW_ONLY"):
        raise CoverHold("Untrusted original 12b row identity")
    symbol=row["trading_symbol_in_original_10k"]
    if symbol is None:
        return "NO_INDEPENDENT_10K_TICKER_SYMBOL_HOLD"
    if symbol!=ticker:
        return "ORIGINAL_10K_TICKER_NOT_EQUAL_CURRENT_MATCH_HOLD"
    if not venue_matches(row["exchange_text"],venue):
        return "ORIGINAL_10K_VENUE_NOT_EQUAL_CURRENT_MATCH_HOLD"
    return "EXACT_OWN_10K_12B_SYMBOL_COMMON_VENUE_REVIEW_ONLY_NOT_FIGI_PROVEN"


def assess(*,directories:dict,sec_raw:bytes,observed:datetime,
           submissions_get,primary_get, min_pool=1000):
    """Original eight issuer source exercise; only aggregate report leaves RAM."""
    if (type(observed) is not datetime or observed.tzinfo is None
        or not callable(submissions_get) or not callable(primary_get)):
        raise CoverHold("Original research sources not fully configured")
    jobs,roster_sha,n=f4.selected_jobs(directories=directories,sec_raw=sec_raw,
                                      observed=observed,min_pool=min_pool)
    if roster_sha!=FROZEN_F4_CIK_COMMITMENT or n!=8:
        raise CoverHold("F4 source original CIK cohort changed; no retrospective repicking")
    states=Counter()
    provenance=[]
    for cik,ticker,venue in jobs:
        try:
            raw=submissions_get(cik)
            if raw is None:
                states["ORIGINAL_SEC_SUBMISSIONS_404_HOLD"]+=1
                continue
            if type(raw) is not bytes or not 2<=len(raw)<=sec.MAX_JSON_BYTES:
                raise CoverHold("Original SEC submissions body missing/oversized")
            payload=sec.decode_source(raw,expected_cik=f"{cik:010d}")
            filing,state=candidate_filing(submissions=payload,cik=cik,observed=observed)
            provenance.append(sha256(raw).hexdigest())
            if filing is None:
                states[state]+=1
                continue
            path, accession, filed, end=filing
            try:
                primary,index_raw,filename,primary_url,index_url=primary_get(path)
            except p4u.FilingSourceFailure as source_exc:
                states[sec_original_archive_hold(source_exc)]+=1
                continue
            if (type(primary) is not bytes
                or type(index_raw) is not bytes or not index_raw
                or not primary or
                p4u._primary_urls(path,filename)!=(index_url,primary_url)):
                raise CoverHold("Original SEC primary and index identity mismatch")
            parsed=p4u.inspect_primary_10k(primary)
            states[classify_10k(parsed=parsed,ticker=ticker,venue=venue)]+=1
            provenance.extend((sha256(index_raw).hexdigest(),
                               sha256(primary).hexdigest()))
        except (sec.SecIntakeStop,quality.StockSourceStop,p4u.ListingEvidenceStop):
            states["SEC_ORIGINAL_SOURCE_UNQUALIFIED_HOLD"]+=1
        # No source errors become a counted success; no replacement names.
    remaining=n-len(jobs)
    if remaining:
        states["PRECOMMITTED_ISSUER_MULTI_SYMBOL_OR_UNMATCHED_HOLD"]=remaining
    if sum(states.values())!=n:
        raise CoverHold("Source statuses do not reconcile to frozen eight")
    fingerprint=sha256(("\n".join(provenance)+"\n").encode()).hexdigest()
    return {
        "schema":SCHEMA,
        "source_kind":"CURRENT_2026_ORIGINAL_OWN_10K_CLASS_DISCLOSURE_NOT_SECURITY_MASTER",
        "source_received_utc":observed.astimezone(timezone.utc).isoformat(),
        "first_f4_run_id":F4_FIRST_SOURCE_RUN,
        "frozen_f4_openfigi_response_sha256":FROZEN_F4_OPENFIGI_RESPONSE_SHA256,
        "frozen_f4_eight_issuer_cik_commitment":roster_sha,
        "original_source_hashed_document_commitment":fingerprint,
        "original_issuer_count":n,
        "frozen_issuer_source_status_counts":dict(sorted(states.items())),
        "sec_10k_cover_is_issuer_declared_not_independent_share_class_id":True,
        "original_vendor_figi_to_sec_cik_identity_proven":False,
        "class_specific_market_cap_share_count_price_and_alpha_verified":False,
        "historical_survivorship_free_universe_proven":False,
        "live_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,"private_state_writes":0,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise CoverHold("Original immutable one-run source already exists")
    if (os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE")!="DISABLED"):
        raise CoverHold("Not a protected brokerless main-only source acquisition")
    agent=os.getenv("SEC_USER_AGENT")
    sec.contact_user_agent(agent)
    directories={filename:listing._get_official(filename) for filename in listing.FILES}
    sec_raw=link.fetch_sec(agent=agent)
    observed=datetime.now(timezone.utc)
    def submissions_get(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"submissions",agent=agent)
    def primary_get(path):
        time.sleep(.4)
        return p4u._official_primary_10k_get(path,agent)
    output=assess(directories=directories,sec_raw=sec_raw,observed=observed,
                  submissions_get=submissions_get,primary_get=primary_get)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,sort_keys=True,indent=2)+"\n")
    print("Frozen first original SEC issuer cohort:",output["original_issuer_count"])
    print("Original SEC 10-K own-class 12b source states:",
          output["frozen_issuer_source_status_counts"])
    print("No issuer names, CIKs, tickers, original filings, figures, valuation or broker I/O.")


if __name__=="__main__":
    main()

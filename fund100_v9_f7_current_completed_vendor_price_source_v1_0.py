"""First previous-completed NYSE-session price-source coverage for F6's fixed 3 CIKs.

Original SEC own 10-K class/symbol/venue REVIEW + original eight-source
commitment prove a *candidate for current vendor price coverage*, not the
security master, issuer-class price entitlement, relative return or alpha.
Yahoo/yfinance is a revisable research vendor. Only SHA256 and counts leave RAM.
NO broker request, private account access, trading release or real order.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import argparse
import io
import json
import logging
import os
import time
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_v9_sec_current_listing_association_v1_0 as link
import fund100_v9_f4_current_openfigi_class_reference_v1_0 as f4
import fund100_v9_f5_original_sec_10k_class_crosscheck_v1_0 as f5
import fund100_v8_sec100_completed_vendor_price_coverage_v1_0 as vendor

SCHEMA = "FUND100_V9_F7_FIXED_THREE_ISSUER_COMPLETED_VENDOR_PRICE_SOURCE_V1"
F6_FIRST_POSITIVE_EPS_SOURCE_RUN = 43026350533
F6_THREE_CIK_SHA256 = "a2fe180b71fc46d818c015f76bc608f9bc59c72ab7c92caab7cfe17581b75a59"
FIRST_F6_EPS_ORIGINAL_MATCHES = 3
COMPLETED_XNYS_SESSIONS = 21
NO_BROKER_GET = NO_BROKER_POST = NO_BROKER_ORDERS = NO_PRIVATE_WRITES = 0
LIVE_AUTHORIZED = False
NO_FIGI_CIK_IDENTITY_PROOF = True

class PriceCoverageHold(ValueError):
    pass


def source_issuer_candidates(*,directories,sec_raw,observed,submissions_get,
                             primary_get,min_pool=1000):
    """Full eight-CIK unranked replay; fail on changed exact F6 3-CIK subset."""
    jobs,digest,n=f4.selected_jobs(directories=directories,sec_raw=sec_raw,
                                   observed=observed,min_pool=min_pool)
    if (digest!=f5.FROZEN_F4_CIK_COMMITMENT or n!=8 or len(jobs)>8):
        raise PriceCoverageHold("Original fixed eight SEC issuers changed")
    states=Counter()
    original_hashes=[]
    class_rows=[]
    for cik,ticker,venue in jobs:
        try:
            raw=submissions_get(cik)
            if raw is None:
                states["ORIGINAL_SEC_SUBMISSIONS_404_HOLD"]+=1
                continue
            if type(raw) is not bytes or not 2<=len(raw)<=sec.MAX_JSON_BYTES:
                raise PriceCoverageHold("Original SEC submissions source invalid")
            filings=sec.decode_source(raw,expected_cik=f"{cik:010d}")
            original_hashes.append(sha256(raw).hexdigest())
            source,reason=f5.candidate_filing(
                submissions=filings,cik=cik,observed=observed)
            if source is None:
                states[reason]+=1
                continue
            path,_,_,_=source
            try:
                raw_10k,index_raw,name,doc_url,index_url=primary_get(path)
            except p4u.FilingSourceFailure as error:
                states[f5.sec_original_archive_hold(error)]+=1
                continue
            if (type(raw_10k) is not bytes or
                type(index_raw) is not bytes or
                not 0<len(raw_10k)<=p4u.MAX_PRIMARY_10K_BYTES or
                not 0<len(index_raw)<=p4u.MAX_FILING_INDEX_BYTES or
                p4u._primary_10k_from_index(path,index_raw)!=(
                    name,index_url,doc_url)):
                raise PriceCoverageHold("Original 10-K document index proof failed")
            original_hashes.extend((sha256(index_raw).hexdigest(),
                                    sha256(raw_10k).hexdigest()))
            category=f5.classify_10k(parsed=p4u.inspect_primary_10k(raw_10k),
                                     ticker=ticker,venue=venue)
            if category==(
                "EXACT_OWN_10K_12B_SYMBOL_COMMON_VENUE_REVIEW_ONLY_NOT_FIGI_PROVEN"):
                class_rows.append((cik,ticker,venue))
            else:
                states[category]+=1
        except (f5.CoverHold,sec.SecIntakeStop,p4u.ListingEvidenceStop):
            states["ORIGINAL_SEC_CLASS_SOURCE_UNQUALIFIED_HOLD"]+=1
    if len(class_rows)!=FIRST_F6_EPS_ORIGINAL_MATCHES:
        raise PriceCoverageHold("F6 exact three current class candidates changed")
    class_digest=sha256(
        b"FUND100_V9_F6_FIRST_CLASS_MATCHED_CIKS_V1\n" +
        b"|".join(f"{cik:010d}".encode("ascii")
                  for cik in sorted(x[0] for x in class_rows))
    ).hexdigest()
    if class_digest!=F6_THREE_CIK_SHA256:
        raise PriceCoverageHold("F6 three-issuer identity subset changed")
    if n-len(jobs):
        states["ORIGINAL_CIK_ALIAS_OR_SOURCE_UNMATCHED_HOLD"]=n-len(jobs)
    if sum(states.values())+len(class_rows)!=n:
        raise PriceCoverageHold("Original eight-issuer source statuses do not reconcile")
    return (class_rows,states,digest,class_digest,sha256(
        ("\n".join(original_hashes)+"\n").encode()).hexdigest(),n)


def completed_session_price_status(*,rows,now:datetime)->str:
    """Validate 21 strictly previous completed US sessions; no same-day marks."""
    if type(now) is not datetime or now.tzinfo is None:
        raise PriceCoverageHold("Missing original vendor receipt clock")
    if type(rows) is not list or len(rows)>vendor.MAX_ROWS_PER_SYMBOL:
        return "VENDOR_SOURCE_ROWS_MISSING_OR_UNBOUNDED_HOLD"
    cal=xcals.get_calendar("XNYS")
    prior=cal.sessions_in_range(
        pd.Timestamp(now.date()-timedelta(days=45)),
        pd.Timestamp(now.date()-timedelta(days=1)))
    expected=[x.date().isoformat() for x in prior[-COMPLETED_XNYS_SESSIONS:]]
    if len(expected)!=COMPLETED_XNYS_SESSIONS:
        raise PriceCoverageHold("Expected completed XNYS sessions unavailable")
    observed={}
    last=""
    for row in rows:
        if type(row) is not dict or set(row)!={
            "session","close_usd","adjusted_close_usd","volume_shares"}:
            return "INVALID_VENDOR_PRICE_ROW_SHAPE_HOLD"
        day=row["session"]
        if type(day) is not str or len(day)!=10 or day<=last or day>=now.date().isoformat():
            return "INVALID_OR_SAME_DAY_VENDOR_MARKET_DATE_HOLD"
        try:
            calendar_day=datetime.strptime(day,"%Y-%m-%d").date()
            if not cal.is_session(pd.Timestamp(calendar_day)):
                return "UNVERIFIED_VENDOR_EXCHANGE_SESSION_HOLD"
            close=vendor.number(row["close_usd"],positive=True)
            adjusted=vendor.number(row["adjusted_close_usd"],positive=True)
            volume=vendor.number(row["volume_shares"],integer=True)
        except (ValueError, vendor.PriceSourceHold):
            return "INVALID_VENDOR_PRICE_OR_VOLUME_HOLD"
        if close>Decimal("1000000") or adjusted>Decimal("1000000"):
            return "UNBOUNDED_VENDOR_PRICE_HOLD"
        last=day
        observed[day]=(close,adjusted,volume)
    if any(day not in observed for day in expected):
        return "INCOMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_SESSIONS_HOLD"
    # A real closing price and enough share turnover are necessary but
    # NOT proof of broker quote, bid/ask liquidity or future execution.
    if observed[expected[-1]][2]<=0:
        return "LAST_COMPLETED_VENDOR_SESSION_NO_VOLUME_HOLD"
    avg_volume=sum((observed[day][0]*observed[day][2]
                    for day in expected[-20:]),Decimal(0))/20
    if avg_volume<=0:
        return "NO_20_SESSION_DOLLAR_TURNOVER_HOLD"
    return "COMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_VOLUME_REVIEW_ONLY"


def assess(*,directories,sec_raw,observed,submissions_get,primary_get,
           vendor_get,min_pool=1000):
    """Only fixed cohort price coverage categories; never emit a price or ID."""
    if (type(observed) is not datetime or observed.tzinfo is None or
        not all(callable(a) for a in (submissions_get,primary_get,vendor_get))):
        raise PriceCoverageHold("Original source contract missing")
    candidates,other_states,eight_digest,three_digest,sec_sha,n=source_issuer_candidates(
        directories=directories,sec_raw=sec_raw,observed=observed,
        submissions_get=submissions_get,primary_get=primary_get,
        min_pool=min_pool)
    # Names are from source-qualified current original SEC CIK + 10-K issuer
    # ticker rows only; do not source other CIKs, fit on returns, or leak names.
    names=[ticker for _,ticker,_ in candidates]
    if len(set(names))!=3:
        raise PriceCoverageHold("Three original candidate tickers not distinct")
    acquired=observed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prices=vendor_get(names,acquired)
    if (type(prices) is not dict or set(prices)!={"source","captured_utc","quotes_by_ticker"}
        or prices["source"]!=vendor.SOURCE
        or prices["captured_utc"]!=acquired
        or type(prices["quotes_by_ticker"]) is not dict
        or set(prices["quotes_by_ticker"])!=set(names)):
        raise PriceCoverageHold("Original public vendor source shape/identity invalid")
    states=Counter(other_states)
    for _,ticker,_ in candidates:
        states[completed_session_price_status(
            rows=prices["quotes_by_ticker"][ticker],now=observed)]+=1
    if sum(states.values())!=n:
        raise PriceCoverageHold("Original eight issuer price statuses do not reconcile")
    vendor_sha=sha256(json.dumps(
        prices,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    return {
        "schema":SCHEMA,
        "source_received_utc":observed.astimezone(timezone.utc).isoformat(),
        "first_original_positive_eps_source_run":F6_FIRST_POSITIVE_EPS_SOURCE_RUN,
        "original_eight_sec_issuer_denominator":n,
        "three_first_source_class_candidate_denominator":len(candidates),
        "frozen_eight_cik_commitment_sha256":eight_digest,
        "frozen_three_class_candidate_cik_commitment_sha256":three_digest,
        "original_sec_source_document_commitment_sha256":sec_sha,
        "public_vendor_source_receipt_sha256":vendor_sha,
        "vendor_source":vendor.SOURCE,
        "prior_xnys_completed_sessions_required":COMPLETED_XNYS_SESSIONS,
        "source_status_counts":dict(sorted(states.items())),
        "vendor_not_broker_exchange_or_executable_quote":True,
        "price_source_symbol_to_issuer_security_master_independently_proven":False,
        "eps_is_issuer_reported_and_class_specific_eps_not_proven":True,
        "shares_market_cap_full_intrinsic_value_alpha_or_buy_proven":False,
        "not_point_in_time_delisted_universe_or_independently_adjusted":True,
        "live_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,"private_state_writes":0,
    }


def main():
    opts=argparse.ArgumentParser()
    opts.add_argument("--out",type=Path,required=True)
    args=opts.parse_args()
    if args.out.exists():
        raise PriceCoverageHold("Original vendor coverage output already exists")
    if (os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE")!="DISABLED"):
        raise PriceCoverageHold("Not a protected, public-research only main source")
    agent=sec.contact_user_agent(os.getenv("SEC_USER_AGENT"))
    dirs={name:listing._get_official(name) for name in listing.FILES}
    sec_raw=link.fetch_sec(agent=agent)
    acquired=datetime.now(timezone.utc)
    def sub(cik):
        time.sleep(.4)
        return broad._get_sec(cik,"submissions",agent=agent)
    def primary(path):
        time.sleep(.4)
        return p4u._official_primary_10k_get(path,agent)
    def public_vendor(names,clock):
        # yfinance can emit ticker-bearing errors to stderr or logging.
        # Keep all provider log/exception details confined to this process.
        previous=logging.root.manager.disable
        try:
            logging.disable(logging.CRITICAL)
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                return vendor._download(names=names,acquired_utc=clock)
        except Exception:
            raise PriceCoverageHold("Public completed-price provider unavailable") from None
        finally:
            logging.disable(previous)
    report=assess(directories=dirs,sec_raw=sec_raw,observed=acquired,
                  submissions_get=sub,primary_get=primary,
                  vendor_get=public_vendor)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("Frozen current SEC issuer denominator:",report["original_eight_sec_issuer_denominator"])
    print("Prior-completed vendor price source states:",report["source_status_counts"])
    print("NO issuer names, price values, CIK, FIGI, broker or valuation published.")


if __name__=="__main__":
    main()

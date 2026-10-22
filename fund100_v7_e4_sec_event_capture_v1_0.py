"""V7-E4: daily prospective SEC 8-K Item 2.02 evidence. NO BROKER.

Only the eight frozen CIKs, official public submissions endpoints,
requester-identified access, raw responses and SHA256 source receipts.
One captured snapshot is NOT proof of first discovery or analyst surprise.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable

import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1

SCHEMA = "FUND100_V7_E4_PROSPECTIVE_SEC_SUBMISSIONS_SOURCE_V1"
REGISTERED = "2026-10-15"
MAX_EVENTS = 200

class FeedStop(ValueError):
    pass

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _timestamp(value: object) -> datetime:
    try:
        return e1.capture_time(value,"prospective SEC observation")
    except (e1.SourceStop, ValueError, TypeError) as exc:
        raise FeedStop("missing canonical UTC acquisition timestamp") from exc

def collect(*, user_agent: str, loader: Callable | None = None,
            clock: Callable[[], str] = utcnow) -> tuple[dict,dict[str,bytes]]:
    """In-memory, all-eight snapshot. Only production's default loader goes online."""
    agent=sec.contact_user_agent(user_agent)
    roster=sec.read_cohort()
    if len(roster)!=8:
        raise FeedStop("original frozen eight CIKs are mandatory")
    get=loader or sec.fetch_one
    files={}
    company_rows=[]
    observed=[]
    for row in roster:
        ticker,cik=row["ticker"],row["cik_10_digit"]
        url=sec.sec_url(cik,"submissions")
        raw=get(url,agent)
        source=sec.decode_source(raw,expected_cik=cik)
        acquired=clock()  # AFTER the response was received, never backdated
        captured=_timestamp(acquired)
        candidates=e1.filing_candidates(source,ticker,captured)
        path=f"raw/CIK{cik}-{ticker}-submissions.json"
        if path in files:
            raise FeedStop("duplicate official source identity")
        files[path]=raw
        filtered=[]
        for item in candidates:
            if item["filed_date"]>=REGISTERED:
                filtered.append({
                    "ticker":ticker,"issuer_cik":cik,
                    "original_sec_accession":item["accession"],
                    "filing_date":item["filed_date"],
                    "sec_submissions_observed_at_utc":acquired,
                    "issuer_event_type":"8-K ITEM 2.02",
                    "earnings_surprise_known":False,
                    "price_signal_calculated":False,
                    "orders_authorized":False,
                })
        if len(filtered)>MAX_EVENTS:
            raise FeedStop("unbounded source event history")
        company_rows.append({
            "ticker":ticker,"cik":cik,
            "official_submissions_url":url,
            "source_file":path,
            "raw_sha256":sha256(raw).hexdigest(),
            "byte_count":len(raw),
            "source_observed_at_utc":acquired,
            "qualifying_type_events_in_current_retrieval":len(filtered)
        })
        observed.extend(filtered)
    acquired_end=clock()
    end_dt=_timestamp(acquired_end)
    for row in company_rows:
        if end_dt<_timestamp(row["source_observed_at_utc"]):
            raise FeedStop("capture end is before a constituent's actual acquisition")
    if len({(r["issuer_cik"],r["original_sec_accession"]) for r in observed})!=len(observed):
        raise FeedStop("duplicate issuer SEC accession")
    return ({
        "schema":SCHEMA,
        "status":"CURRENT_OFFICIAL_SEC_FILING_EVIDENCE_NOT_A_STRATEGY_SIGNAL",
        "registered_source_cohort_date":REGISTERED,
        "capture_complete_utc":acquired_end,
        "all_frozen_issuers_acquired":True,
        "source_class":"REVISABLE_CURRENT_SEC_SUBMISSIONS_WITH_CAPTURED_RAW_BYTES",
        "source_count":len(company_rows),
        "issuer_sources":company_rows,
        "item_2_02_filings_since_registration_in_current_source":len(observed),
        "observed_filings_not_necessarily_new_today":observed,
        "first_public_dissemination_time_proven":False,
        "analyst_eps_surprise_available":False,
        "prior_archived_vintage_replaced":False,
        "historical_survivorship_safe":False,
        "live_portfolio_changed":False,
        "broker_orders":0,
        "paper_authorized":False,"live_authorized":False,
        "trading_authorized":False
    },files)

def verify(root: Path) -> dict:
    """Re-check every original captured byte before using any event in research."""
    manifest=json.loads((root/"manifest.json").read_bytes())
    roster=sec.read_cohort()
    if (manifest.get("schema")!=SCHEMA
        or manifest.get("source_count")!=8
        or manifest.get("all_frozen_issuers_acquired") is not True
        or manifest.get("status")!="CURRENT_OFFICIAL_SEC_FILING_EVIDENCE_NOT_A_STRATEGY_SIGNAL"
        or manifest.get("broker_orders")!=0
        or manifest.get("paper_authorized") is not False
        or manifest.get("live_authorized") is not False
        or manifest.get("trading_authorized") is not False):
        raise FeedStop("invalid archived source provenance/control manifest")
    end=_timestamp(manifest.get("capture_complete_utc"))
    rows=manifest.get("issuer_sources")
    if (not isinstance(rows,list) or len(rows)!=8
        or [r.get("ticker") for r in rows]!=[r["ticker"] for r in roster]):
        raise FeedStop("original issuer roster changed")
    original=[]
    for row,expected in zip(rows,roster):
        cik,ticker=expected["cik_10_digit"],expected["ticker"]
        path=f"raw/CIK{cik}-{ticker}-submissions.json"
        if (row.get("cik")!=cik or row.get("source_file")!=path
            or row.get("official_submissions_url")!=sec.sec_url(cik,"submissions")):
            raise FeedStop("original SEC source identity/path changed")
        raw=(root/path).read_bytes()
        if len(raw)!=row.get("byte_count") or sha256(raw).hexdigest()!=row.get("raw_sha256"):
            raise FeedStop("original raw SEC bytes have been modified")
        observed=_timestamp(row.get("source_observed_at_utc"))
        if observed>end:
            raise FeedStop("source acquisition later than snapshot completion")
        source=sec.decode_source(raw,expected_cik=cik)
        candidates=e1.filing_candidates(source,ticker,observed)
        original.extend({
            "ticker":ticker,"issuer_cik":cik,"original_sec_accession":c["accession"],
            "filing_date":c["filed_date"],"sec_submissions_observed_at_utc":row["source_observed_at_utc"],
            "issuer_event_type":"8-K ITEM 2.02",
            "earnings_surprise_known":False,"price_signal_calculated":False,
            "orders_authorized":False
        } for c in candidates if c["filed_date"]>=REGISTERED)
    if (original!=manifest.get("observed_filings_not_necessarily_new_today")
        or len(original)!=manifest.get("item_2_02_filings_since_registration_in_current_source")
        or any(r.get("orders_authorized") is not False for r in original)):
        raise FeedStop("stored event rows do not reproduce from original SEC bytes")
    return manifest

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    target=a.output_dir
    if target.exists() and any(target.iterdir()):
        raise FeedStop("refuse to overwrite an existing capture")
    agent=sec.contact_user_agent(os.getenv("SEC_USER_AGENT",""))
    report,files=collect(user_agent=agent)
    target.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        loc=target/name
        loc.parent.mkdir(parents=True,exist_ok=True)
        loc.write_bytes(raw)
    (target/"manifest.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    verify(target)
    print("V7-E4 verified original official SEC issuer count",report["source_count"])
    print("Original observed SEC Item 2.02 filings since registration:",
          report["item_2_02_filings_since_registration_in_current_source"])
    print("Research filing observations are NOT necessarily new; no orders or alpha claims.")

if __name__=="__main__":
    main()

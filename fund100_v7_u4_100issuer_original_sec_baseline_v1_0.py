"""V7 U4 — one exact first-original-SEC Item 2.02 baseline for U3's 100 CIKs.

The U3 archive is explicitly issuer-ATTRIBUTED, NOT original iShares raw.
No event already present in this inaugural snapshot is newly discovered.
Only a LATER original SEC acquisition can find a new accession absent
from this source baseline. Even then it does not prove SEC dissemination
at the acquisition timestamp, positive analyst surprise, alpha, or fills.

Zero brokerage connectivity. One immutable source cohort, never rerank.
"""
from __future__ import annotations
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from typing import Callable

import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_v7_u3_dated_issuer_mirror_sec100_v1_0 as u3

SCHEMA="FUND100_V7_U4_FIRST_ORIGINAL_SEC_100_ISSUER_BASELINE_V1"
ORIGINAL_U3_RUN_ID=40545345749
ORIGINAL_U3_ARTIFACT_ID=12752028069
ORIGINAL_U3_ARTIFACT_NAME="fund100-v7-u3-first-dated-mirror-sec100-40545345749"
COUNT=100
MAX_TOTAL_RAW=125_000_000
MAX_OBSERVATIONS_PER_ISSUER=15
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_ENABLED=False

class BaselineStop(ValueError):pass

def stamp(value:str):
    try:
        return e1.capture_time(value,"original SEC first receipt")
    except (e1.SourceStop, ValueError, TypeError) as exc:
        raise BaselineStop("Invalid UTC original source timestamp") from exc

def original_issuer_roster(u3_dir:Path):
    try:
        record=json.loads((u3_dir/"U3-first-100-issuer-research-roster.json").read_bytes())
        mirror=(u3_dir/"first-vintage-third-party-IVV-snapshot.json").read_bytes()
        official=(u3_dir/"first-vintage-official-SEC-ticker-map.json").read_bytes()
        replay=u3.freeze(mirror_bytes=mirror,official_sec_ticker_bytes=official,
                         acquired_utc=record["actual_original_mirror_and_sec_acquisition_utc"])
    except (ValueError, OSError, KeyError, u3.MirrorStop, sec.SecIntakeStop) as exc:
        raise BaselineStop("Original U3 source archive not independently replayable") from exc
    if (replay!=record or record.get("schema")!=u3.SCHEMA
        or record.get("status")!="PROSPECTIVELY_FROZEN_THIRD_PARTY_IVV_100_ISSUERS_NOT_AN_ALPHA_SIGNAL"
        or record.get("source_is_direct_official_ishares_file") is not False
        or record.get("observed_new_future_returns")!=0
        or record.get("trading_authorized") is not False
        or record.get("broker_gets")!=0 or record.get("broker_posts")!=0
        or record.get("broker_orders")!=0):
        raise BaselineStop("Untrusted third-party source identity/trade restriction")
    roster=record.get("first_100_distinct_SEC_CIK_mapped_issuer_roster")
    if (not isinstance(roster,list) or len(roster)!=COUNT
        or len({r["sec_cik_10_digit"] for r in roster})!=COUNT):
        raise BaselineStop("Incomplete original SEC identity population")
    return record,roster

def eligible_filing_events(original:dict,ticker:str,observed:str)->list[dict]:
    now=stamp(observed)
    try:
        # Reuse E6 alignment and source-window validator and E1's strict
        # amended-filing / 8-K ITEM 2.02 original accession classification.
        source=e6._bounded_recent_window(original)
        events=e1.filing_candidates(source,ticker,now)
    except (e6.ExpandedFeedStop,e1.SourceStop) as exc:
        raise BaselineStop("Source-native SEC 8-K Item 2.02 arrays invalid") from exc
    filtered=[{
        "original_sec_accession":r["accession"],
        "filing_date":r["filed_date"],
        "issuer_event_type":"8-K ITEM 2.02",
        "source_preexisting_or_new_is_observer_only":True,
        "analyst_surprise_verified":False,
        "public_disclosure_timestamp_proven":False,
        "trading_authorized":False,
    } for r in events if r["filed_date"]>="2026-10-15"]
    if len(filtered)>MAX_OBSERVATIONS_PER_ISSUER:
        raise BaselineStop("Unexpected unbounded issuer filing-census scope")
    return sorted(filtered,key=lambda x:(x["filing_date"],x["original_sec_accession"]))

def collect(*,u3_dir:Path,agent:str,loader:Callable|None=None,
            clock:Callable[[],str]|None=None):
    try:
        requester=sec.contact_user_agent(agent)
    except sec.SecIntakeStop as exc:
        raise BaselineStop("Valid SEC requester identity required") from exc
    roster_doc,roster=original_issuer_roster(u3_dir)
    reference_time=stamp(roster_doc["actual_original_mirror_and_sec_acquisition_utc"])
    get=loader if loader is not None else sec.fetch_one
    now=clock or (lambda:datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    captured={}
    rows=[]
    source_total=0
    for identity in roster:
        ticker,cik=identity["ticker"],identity["sec_cik_10_digit"]
        url=sec.sec_url(cik,"submissions")
        raw=get(url,requester)
        decoded=sec.decode_source(raw,expected_cik=cik)
        acquired=now()  # Actual source receipt AFTER API download.
        if stamp(acquired)<reference_time:
            raise BaselineStop("SEC snapshot precedes original U3 issuer freeze")
        source_total+=len(raw)
        if source_total>MAX_TOTAL_RAW:
            raise BaselineStop("Unbounded 100-company original SEC source")
        path=f"raw/CIK{cik}-submissions.json.gz"
        if path in captured:
            raise BaselineStop("Duplicate original SEC request/CIK")
        captured[path]=gzip.compress(raw,mtime=0)
        observations=eligible_filing_events(decoded,ticker,acquired)
        rows.append({
            "ticker":ticker,
            "sec_cik_10_digit":cik,
            "original_sec_url":url,
            "original_raw_file":path,
            "original_raw_json_sha256":sha256(raw).hexdigest(),
            "original_raw_json_bytes":len(raw),
            "original_source_acquired_utc":acquired,
            "first_baseline_all_prior_filings_are_not_new_signals":True,
            "source_observed_item2_02_accessions":observations,
        })
        if loader is None:
            time.sleep(.15)  # SEC API fair-use well under 10 requests/s.
    end=now()
    if any(stamp(x["original_source_acquired_utc"])>stamp(end) for x in rows):
        raise BaselineStop("SEC observation later than survey completion")
    total=sum(len(r["source_observed_item2_02_accessions"]) for r in rows)
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_FIRST_100_ISSUER_SEC_BASELINE_NOT_A_NEW_EVENT",
        "original_u3_run_id":ORIGINAL_U3_RUN_ID,
        "original_u3_artifact_id":ORIGINAL_U3_ARTIFACT_ID,
        "original_u3_original_mirror_sha256":
            roster_doc["exact_mirror_original_json_sha256"],
        "original_u3_official_SEC_ticker_sha256":
            roster_doc["exact_SEC_original_ticker_bytes_sha256"],
        "original_u3_source_observed_utc":
            roster_doc["actual_original_mirror_and_sec_acquisition_utc"],
        "original_100_issuer_identity_roster_not_reranked":True,
        "original_brokerless_sec_captured_end_utc":end,
        "source_count":COUNT,
        "first_source_issuer_rows":rows,
        "baseline_historical_earnings_filing_accession_count":total,
        "baseline_filing_accessions_all_preexisting":True,
        "independent_first_public_release_proven":False,
        "first_new_postbaseline_sec_event_count":0,
        "observed_future_aftercost_returns":0,
        "earnings_surprise_or_quality_alpha_proven":False,
        "issuer_source_is_third_party_attributed_not_direct_ishares":True,
        "original_live_trial_ceiling_usd":"130.30",
        "original_operator_stop_and_kill_untouched":True,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,"live_authorized":False,
    },captured

def verify(*,u3_dir:Path,report_dir:Path):
    source,roster=original_issuer_roster(u3_dir)
    report=json.loads((report_dir/"manifest.json").read_bytes())
    if (report.get("schema")!=SCHEMA
        or report.get("status")!="ORIGINAL_FIRST_100_ISSUER_SEC_BASELINE_NOT_A_NEW_EVENT"
        or report.get("source_count")!=COUNT
        or report.get("original_u3_run_id")!=ORIGINAL_U3_RUN_ID
        or report.get("original_u3_artifact_id")!=ORIGINAL_U3_ARTIFACT_ID
        or report.get("original_u3_original_mirror_sha256")!=
             source["exact_mirror_original_json_sha256"]
        or report.get("original_u3_official_SEC_ticker_sha256")!=
             source["exact_SEC_original_ticker_bytes_sha256"]
        or report.get("original_u3_source_observed_utc")!=
             source["actual_original_mirror_and_sec_acquisition_utc"]
        or report.get("baseline_filing_accessions_all_preexisting") is not True
        or report.get("first_new_postbaseline_sec_event_count")!=0
        or report.get("observed_future_aftercost_returns")!=0
        or report.get("broker_gets")!=0 or report.get("broker_posts")!=0
        or report.get("broker_orders")!=0
        or report.get("trading_authorized") is not False
        or report.get("live_authorized") is not False):
        raise BaselineStop("Original 100-issuer first baseline manifest changed")
    rows=report.get("first_source_issuer_rows")
    if not isinstance(rows,list) or len(rows)!=COUNT:
        raise BaselineStop("Incomplete baseline original SEC source set")
    end=stamp(report["original_brokerless_sec_captured_end_utc"])
    total=0
    for a,b in zip(rows,roster):
        cik,ticker=b["sec_cik_10_digit"],b["ticker"]
        path=f"raw/CIK{cik}-submissions.json.gz"
        if (a.get("sec_cik_10_digit")!=cik
            or a.get("ticker")!=ticker
            or a.get("original_raw_file")!=path
            or a.get("original_sec_url")!=sec.sec_url(cik,"submissions")
            or stamp(a["original_source_acquired_utc"])>end):
            raise BaselineStop("SEC archive CIK/URL/date no longer frozen")
        raw=gzip.decompress((report_dir/path).read_bytes())
        if (len(raw)!=a.get("original_raw_json_bytes")
            or sha256(raw).hexdigest()!=a.get("original_raw_json_sha256")):
            raise BaselineStop("Original SEC source SHA changed")
        decoded=sec.decode_source(raw,expected_cik=cik)
        calculated=eligible_filing_events(decoded,ticker,a["original_source_acquired_utc"])
        if calculated!=a.get("source_observed_item2_02_accessions"):
            raise BaselineStop("Original SEC 8-K accession set was rewritten")
        total+=len(calculated)
    if total!=report.get("baseline_historical_earnings_filing_accession_count"):
        raise BaselineStop("Baseline event count not corroborated by original SEC")
    return report

def compare(*,baseline:dict,later:dict):
    """Only absent-to-present ORIGINAL accession deltas, NEVER alpha."""
    if (baseline.get("schema")!=SCHEMA or later.get("schema")!=SCHEMA
        or baseline.get("source_count")!=COUNT or later.get("source_count")!=COUNT
        or baseline.get("original_u3_original_mirror_sha256")!=
            later.get("original_u3_original_mirror_sha256")
        or baseline.get("original_u3_official_SEC_ticker_sha256")!=
            later.get("original_u3_official_SEC_ticker_sha256")
        or stamp(later["original_brokerless_sec_captured_end_utc"])<=
            stamp(baseline["original_brokerless_sec_captured_end_utc"])):
        raise BaselineStop("Changed original first SEC baseline/source chronology")
    first=baseline["first_source_issuer_rows"]
    newer=later["first_source_issuer_rows"]
    if not isinstance(first,list) or not isinstance(newer,list) or len(first)!=COUNT or len(newer)!=COUNT:
        raise BaselineStop("Missing complete 100 source responses")
    possible=[]
    first_date=baseline["original_brokerless_sec_captured_end_utc"][:10]
    for a,b in zip(first,newer):
        if (a["ticker"]!=b["ticker"] or a["sec_cik_10_digit"]!=b["sec_cik_10_digit"]):
            raise BaselineStop("Original issuer membership changed between observations")
        previous={x["original_sec_accession"] for x in a["source_observed_item2_02_accessions"]}
        current={x["original_sec_accession"] for x in b["source_observed_item2_02_accessions"]}
        if not previous<=current:
            raise BaselineStop("Previously observed original SEC 8-Ks disappeared on rerun")
        for x in b["source_observed_item2_02_accessions"]:
            if x["original_sec_accession"] not in previous and x["filing_date"]>=first_date:
                possible.append({
                    "ticker":b["ticker"],"cik":b["sec_cik_10_digit"],
                    "accession":x["original_sec_accession"],
                    "original_SEC_filing_date":x["filing_date"],
                    "first_source_observed_after_baseline_utc":
                        b["original_source_acquired_utc"],
                    "first_original_disclosure_timestamp_confirmed":False,
                    "earnings_surprise_known":False,
                    "order_authorized":False,
                })
    return {"status":"NEW_ABSENT_FROM_BASELINE_SEC_ACCESSIONS_RESEARCH_NOT_ALPHA",
            "candidate_first_delta_count":len(possible),
            "candidate_first_delta_filings_not_trade_signals":possible,
            "original_SEC_disclosure_time_not_proven":True,
            "forward_aftercost_outcomes_observed":0,
            "live_authorized":False,"broker_orders":0}

def main():
    import argparse,os
    p=argparse.ArgumentParser()
    p.add_argument("--u3-source-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise BaselineStop("Original original-first SEC output already exists")
    report,raw=collect(u3_dir=a.u3_source_dir,
                       agent=os.environ.get("SEC_USER_AGENT",""))
    a.output_dir.mkdir(parents=True,exist_ok=True)
    for name,content in raw.items():
        path=a.output_dir/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
    (a.output_dir/"manifest.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    verify(u3_dir=a.u3_source_dir,report_dir=a.output_dir)
    print("OFFICIAL SEC 100 issuer sources captured:",report["source_count"])
    print("Historical 8-K Item 2.02 accessions for FIRST baseline:",
          report["baseline_historical_earnings_filing_accession_count"])
    print("NEW prospective earnings events:",report["first_new_postbaseline_sec_event_count"])
    print("NO earning surprise, NO return, NO BROKER ORDERS.")

if __name__=="__main__":main()

"""V7-E6: original SEC Item 2.02 publication census across 24 FROZEN issuers.

Expands source-only earnings observer from original eight 15-Oct issuers to
the 16 extra P4L issuers frozen 24-Oct. The latter original SEC CIKs are
anchored to authentic original P4N capture, main run #40345993054.
META and NEE 21 Oct historical filings MUST NOT turn into postfreeze alerts.
This is source coverage research, not original first SEC discovery, forward
entry, analyst surprise, an order or an investable historical universe.
All original E4 eight-company observers remain independently unchanged.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Callable

import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
import fund100_v7_e4_sec_event_capture_v1_0 as e4

SCHEMA="FUND100_V7_E6_PINNED_24_ISSUER_ORIGINAL_SEC_EARNINGS_SOURCE_V1"
ORIGINAL_P4N_RUN_ID=40345993054
ORIGINAL_P4N_MANIFEST_SHA256="39a1cf8ab1bc5f6cfa2f915da409231be3b23c84b2adbc210f94fafade5b530e"
ORIGINAL_EIGHT_REGISTRATION="2026-10-15"
EXTRA_SIXTEEN_REGISTRATION="2026-10-24"
REFERENCE_LOOKBACK_START="2026-10-15"
EXTRA_SIXTEEN={
    "AVGO":"0001730168","CAT":"0000018230","COST":"0000909832",
    "CVX":"0000093410","DIS":"0001744489","HD":"0000354950",
    "JPM":"0000019617","LLY":"0000059478","MA":"0001141391",
    "MCD":"0000063908","META":"0001326801","NEE":"0000753308",
    "NVDA":"0001045810","PEP":"0000077476","V":"0001403161",
    "WMT":"0000104169",
}
MAX_OBSERVATIONS_PER_ISSUER=20
MAX_OFFICIAL_RECENT_ROWS=50000
MAX_SELECTED_COHORT_ROWS=5000
BROKER_ORDERS=0

class ExpandedFeedStop(ValueError):
    pass

def identities()->list[dict]:
    try:
        old=sec.read_cohort()
    except sec.SecIntakeStop as exc:
        raise ExpandedFeedStop("Original eight SEC identity roster unavailable") from exc
    if (len(old)!=8 or len(EXTRA_SIXTEEN)!=16
        or set(EXTRA_SIXTEEN)&{r["ticker"] for r in old}
        or set(EXTRA_SIXTEEN)|{r["ticker"] for r in old}!=set(p4l.SECTORS)
        or len({*EXTRA_SIXTEEN.values(),*[r["cik_10_digit"] for r in old]})!=24):
        raise ExpandedFeedStop("Pinned 24-company original SEC identities changed")
    return sorted(
        [{"ticker":r["ticker"],"cik":r["cik_10_digit"],
          "frozen_registration":ORIGINAL_EIGHT_REGISTRATION,
          "identity_source":"FROZEN_P4B_2026_10_15"} for r in old] +
        [{"ticker":ticker,"cik":cik,
          "frozen_registration":EXTRA_SIXTEEN_REGISTRATION,
          "identity_source":"ORIGINAL_P4N_2026_10_26_PINNED_CIK"} for ticker,cik
         in EXTRA_SIXTEEN.items()],
        key=lambda row:row["ticker"])

def _utc(stamp:str)->datetime:
    try:
        return e4._timestamp(stamp)
    except (e4.FeedStop,ValueError,TypeError) as exc:
        raise ExpandedFeedStop("Noncanonical original SEC capture time") from exc

def _events(source:dict,ticker:str,cik:str,registered:str,
            observed_utc:str)->tuple[list[dict],list[dict]]:
    captured=_utc(observed_utc)
    if captured.date().isoformat()<registered:
        raise ExpandedFeedStop("SEC cohort captured before its original registration")
    # SEC "recent" can be far larger than E1's original eight-issuer
    # 5,000-row ceiling (JPM had 26,430 REAL aligned rows on 26 Oct).
    # Validate original FULL cardinality before creating a bounded copy of
    # just dates in this frozen registered observation window. All source
    # bytes remain independently SHA-pinned and archived unchanged.
    recent=source.get("filings",{}).get("recent")
    required=("form","accessionNumber","filingDate","items")
    if not isinstance(recent,dict) or any(
        not isinstance(recent.get(k),list) for k in required
    ):
        raise ExpandedFeedStop("Original full SEC submissions arrays incomplete")
    total=len(recent["form"])
    if total>MAX_OFFICIAL_RECENT_ROWS or any(
        len(recent[k])!=total for k in required
    ):
        raise ExpandedFeedStop("Original SEC submissions rows inconsistent or unbounded")
    selected_indices=[
        i for i,date in enumerate(recent["filingDate"])
        if isinstance(date,str) and date>=REFERENCE_LOOKBACK_START
    ]
    if len(selected_indices)>MAX_SELECTED_COHORT_ROWS:
        raise ExpandedFeedStop("Recent registered SEC event window unexpectedly oversized")
    trimmed={"filings":{"recent":{
        k:[recent[k][i] for i in selected_indices] for k in required
    }}}
    candidates=e1.filing_candidates(trimmed,ticker,captured)
    event_rows=[]
    older=[]
    for entry in candidates:
        filed=entry["filed_date"]
        if filed<REFERENCE_LOOKBACK_START:
            continue
        row={
            "ticker":ticker,"cik":cik,
            "original_sec_accession":entry["accession"],
            "filing_date":filed,
            "original_sec_observed_at_utc":observed_utc,
            "type":"8-K ITEM 2.02",
            "first_public_dissemination_timestamp_verified":False,
            "earnings_surprise_available":False,
            "broker_order_authorized":False,
        }
        if filed>=registered:
            row["cohort_status"]="AFTER_REGISTERED_DATE_SOURCE_OBSERVATION_NOT_FORWARD_SIGNAL"
            event_rows.append(row)
        else:
            row["cohort_status"]="EARLIER_THAN_EXPANDED_COHORT_FREEZE_NOT_A_FORWARD_SIGNAL"
            older.append(row)
    if len(event_rows)+len(older)>MAX_OBSERVATIONS_PER_ISSUER:
        raise ExpandedFeedStop("Unexpected unbounded original issuer 8-K event coverage")
    return event_rows,older

def collect(*,agent:str,loader:Callable|None=None,
            clock:Callable[[],str]=e4.utcnow)->tuple[dict,dict[str,bytes]]:
    contact=sec.contact_user_agent(agent)
    roster=identities()
    get=loader or sec.fetch_one
    files={}
    rows=[]
    eligible=[]
    historical=[]
    for ident in roster:
        ticker,cik=ident["ticker"],ident["cik"]
        url=sec.sec_url(cik,"submissions")
        raw=get(url,contact)
        decoded=sec.decode_source(raw,expected_cik=cik)
        stamp=clock()  # after actual network receipt, never inferred from filed day
        now=_utc(stamp)
        if now.date().isoformat()<ident["frozen_registration"]:
            raise ExpandedFeedStop("Future cohort not yet registered")
        latest,earlier=_events(decoded,ticker,cik,ident["frozen_registration"],stamp)
        path=f"raw/CIK{cik}-{ticker}-submissions.json"
        if path in files:raise ExpandedFeedStop("Repeated SEC CIK research endpoint")
        files[path]=raw
        rows.append({**ident,"original_source_url":url,"source_file":path,
                     "raw_sha256":sha256(raw).hexdigest(),
                     "byte_count":len(raw),"observed_at_utc":stamp,
                     "after_registration_events":len(latest),
                     "pre_registration_reference_events":len(earlier)})
        eligible.extend(latest)
        historical.extend(earlier)
    end=clock()
    if any(_utc(r["observed_at_utc"])>_utc(end) for r in rows):
        raise ExpandedFeedStop("SEC capture completion precedes constituent observation")
    if len({(x["cik"],x["original_sec_accession"])
            for x in (*eligible,*historical)})!=len(eligible)+len(historical):
        raise ExpandedFeedStop("Repeated original SEC event accession")
    return ({
        "schema":SCHEMA,"status":"FROZEN_24_ORIGINAL_SEC_EVENT_COVERAGE_NOT_TRADE",
        "capture_complete_utc":end,
        "original_8_issuer_freeze":ORIGINAL_EIGHT_REGISTRATION,
        "additional_16_issuer_freeze":EXTRA_SIXTEEN_REGISTRATION,
        "original_P4N_main_run_id":ORIGINAL_P4N_RUN_ID,
        "original_P4N_source_manifest_sha256":ORIGINAL_P4N_MANIFEST_SHA256,
        "original_eight_E4_observer_unmodified":True,
        "source_count":24,
        "original_SEC_submissions_all_24_verified":True,
        "original_source_issuer_rows":rows,
        "after_registration_earnings_8k_events_not_trade_signals":eligible,
        "precohort_reference_earnings_8k_events_not_trade_signals":historical,
        "after_registration_event_count":len(eligible),
        "precohort_reference_event_count":len(historical),
        "filing_date_is_not_first_independent_public_release_timestamp":True,
        "new_event_first_discovered_in_this_capture_proven":False,
        "source_current_submissions_revisable":True,
        "contemporary_2026_issuer_roster_not_2017_investable_universe":True,
        "forward_return_observations":0,
        "independent_analyst_surprises_available":False,
        "no_trade_signal_and_no_account_binding":True,
        "broker_orders":BROKER_ORDERS,"broker_http_requests":0,
        "live_authorized":False,"paper_authorized":False,
        "trading_authorized":False,
    },files)

def verify(root:Path)->dict:
    try:
        manifest=json.loads((root/"manifest.json").read_text())
        roster=identities()
        if (manifest.get("schema")!=SCHEMA
            or manifest.get("source_count")!=24
            or manifest.get("original_P4N_source_manifest_sha256")!=ORIGINAL_P4N_MANIFEST_SHA256
            or manifest.get("original_SEC_submissions_all_24_verified") is not True
            or manifest.get("live_authorized") is not False
            or manifest.get("paper_authorized") is not False
            or manifest.get("trading_authorized") is not False
            or manifest.get("broker_orders")!=0
            or manifest.get("broker_http_requests")!=0
            or manifest.get("forward_return_observations")!=0
            or manifest.get("new_event_first_discovered_in_this_capture_proven") is not False):
            raise ExpandedFeedStop("Untrusted source-only 24-issuer research manifest")
        rows=manifest.get("original_source_issuer_rows")
        if not isinstance(rows,list) or len(rows)!=24:
            raise ExpandedFeedStop("Incomplete research original SEC issuer sources")
        end=_utc(manifest["capture_complete_utc"])
        eligible=[];earlier=[]
        for row,ident in zip(rows,roster):
            if any(row.get(k)!=ident[k] for k in ident):
                raise ExpandedFeedStop("Pinned SEC issuer CIK or original freeze changed")
            ticker,cik=ident["ticker"],ident["cik"]
            path=f"raw/CIK{cik}-{ticker}-submissions.json"
            if (row.get("source_file")!=path or
                row.get("original_source_url")!=sec.sec_url(cik,"submissions")):
                raise ExpandedFeedStop("Original SEC source locator changed")
            raw=(root/path).read_bytes()
            if (len(raw)!=row.get("byte_count")
                or sha256(raw).hexdigest()!=row.get("raw_sha256")):
                raise ExpandedFeedStop("Original source bytes and SHA no longer match")
            if _utc(row["observed_at_utc"])>end:
                raise ExpandedFeedStop("Observation newer than source capture completed")
            decoded=sec.decode_source(raw,expected_cik=cik)
            a,b=_events(decoded,ticker,cik,ident["frozen_registration"],
                        row["observed_at_utc"])
            if (row.get("after_registration_events")!=len(a)
                or row.get("pre_registration_reference_events")!=len(b)):
                raise ExpandedFeedStop("Original issuer event rows cannot be replayed")
            eligible.extend(a);earlier.extend(b)
        if (eligible!=manifest.get("after_registration_earnings_8k_events_not_trade_signals")
            or earlier!=manifest.get("precohort_reference_earnings_8k_events_not_trade_signals")
            or len(eligible)!=manifest.get("after_registration_event_count")
            or len(earlier)!=manifest.get("precohort_reference_event_count")):
            raise ExpandedFeedStop("Source events mismatched with pinned independent bytes")
        return manifest
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        if isinstance(exc,ExpandedFeedStop):raise
        raise ExpandedFeedStop("Source archive missing, malformed or not independently replayable") from exc

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ExpandedFeedStop("Never replace independently archived source")
    agent=sec.contact_user_agent(os.getenv("SEC_USER_AGENT",""))
    report,files=collect(agent=agent)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for path,data in files.items():
        dest=args.output_dir/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    (args.output_dir/"manifest.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    verify(args.output_dir)
    print("Verified original SEC submissions for",report["source_count"],"fixed issuers")
    print("After-cohort 8-K earnings filing observations (NOT trading signals):",
          report["after_registration_event_count"])
    print("Historically observed before 24-Oct expansion, NOT eligible:",
          report["precohort_reference_event_count"],
          [(r["ticker"],r["filing_date"])
           for r in report["precohort_reference_earnings_8k_events_not_trade_signals"]])
    print("No independent surprise / forward return / broker order.")

if __name__=="__main__":main()

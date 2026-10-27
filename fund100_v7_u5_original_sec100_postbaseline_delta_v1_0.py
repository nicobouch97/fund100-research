"""V7 U5: TRUE original SEC 100-issuer postbaseline DELTA, NEVER an order.

Replay independently the exact real first official-SEC 100-company baseline
and later raw original SEC responses, each with uncompressed SHA256. A
new accession is only "absent from original first baseline and visible
in this later source." No claim of original SEC public dissemination time
or first observation in this particular run (later rescans can repeat).
"""
from __future__ import annotations
import argparse
import json
import zlib
from pathlib import Path
from hashlib import sha256

import fund100_v7_u4_100issuer_original_sec_baseline_v1_0 as u4

SCHEMA="FUND100_V7_U5_ORIGINAL_SEC100_CUMULATIVE_POSTBASELINE_CENSUS_V1"
PINNED_U3_MAIN_RUN_ID=40545345749
PINNED_U4_MAIN_RUN_ID=40550119246
PINNED_U4_FIRST_BASELINE_ARTIFACT_ID=12755320802
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
TRADING_AUTHORIZED=False

class NewSourceStop(ValueError):pass

def original_source_delta(*,original_u3_dir:Path,
                          pinned_first_sec_dir:Path,
                          later_actual_sec_dir:Path,
                          previous_successful_sec_dir:Path|None=None,
                          previous_successful_main_run_id:int|None=None)->dict:
    try:
        original=u4.verify(
            u3_dir=original_u3_dir,report_dir=pinned_first_sec_dir)
        later=u4.verify(
            u3_dir=original_u3_dir,report_dir=later_actual_sec_dir)
        assessment=u4.compare(baseline=original,later=later)
    except (u4.BaselineStop,KeyError,ValueError,TypeError,OSError,EOFError,zlib.error) as exc:
        raise NewSourceStop("Original 100-issuer sources failed replay or chronology") from exc
    if (original.get("source_count")!=100 or later.get("source_count")!=100
        or original.get("original_u3_artifact_id")!=u4.ORIGINAL_U3_ARTIFACT_ID
        or original.get("first_new_postbaseline_sec_event_count")!=0
        or original.get("broker_orders")!=0
        or later.get("broker_orders")!=0
        or assessment.get("broker_orders")!=0
        or original["original_brokerless_sec_captured_end_utc"]>=
           later["original_brokerless_sec_captured_end_utc"]):
        raise NewSourceStop("Later SEC source is not a subsequent read-only observation")
    possible=assessment["candidate_first_delta_filings_not_trade_signals"]
    outcome=[]
    for row in possible:
        if row.get("order_authorized") is not False:
            raise NewSourceStop("Original SEC source tried to authorize order")
        copy={
            "ticker":row["ticker"],
            "sec_cik_10_digit":row["cik"],
            "original_sec_filing_accession":row["accession"],
            "sec_original_filing_date":row["original_SEC_filing_date"],
            # U4 names this field "first", but in repeated acquisitions
            # it is NOT a first-receipt proof. Rename without guessing.
            "visible_in_THIS_later_original_source_utc":
                row["first_source_observed_after_baseline_utc"],
            "first_seen_in_current_run_proven":False,
            "SEC_actual_disclosure_timestamp_verified":False,
            "earnings_surprise_available":False,
            "independent_postevent_stock_and_benchmark_marks":False,
            "broker_order_authorized":False,
        }
        outcome.append(copy)
    if len({(r["sec_cik_10_digit"],r["original_sec_filing_accession"])
            for r in outcome})!=len(outcome):
        raise NewSourceStop("Duplicated original SEC accessions in delta")
    if len(outcome)!=assessment["candidate_first_delta_count"]:
        raise NewSourceStop("Source delta count mismatch")
    # Distinguish cumulative additions from accessions absent in the immediately
    # preceding successful, archived main observer. Never infer public release
    # time or a first-ever source observation from this pair of captures.
    if (previous_successful_sec_dir is None)!=(previous_successful_main_run_id is None):
        raise NewSourceStop("Previous SEC archive and its verified main run ID must be paired")
    new_since_previous=None
    previous_manifest_sha=None
    if previous_successful_sec_dir is not None:
        if (type(previous_successful_main_run_id) is not int
            or previous_successful_main_run_id<=0
            or previous_successful_main_run_id in (PINNED_U3_MAIN_RUN_ID,
                                                    PINNED_U4_MAIN_RUN_ID)):
            raise NewSourceStop("Previous successful observer main run ID invalid")
        try:
            previous=u4.verify(u3_dir=original_u3_dir,
                               report_dir=previous_successful_sec_dir)
            prior_delta=u4.compare(baseline=original,later=previous)
            u4.compare(baseline=previous,later=later)
            if not (original["original_brokerless_sec_captured_end_utc"] <
                    previous["original_brokerless_sec_captured_end_utc"] <
                    later["original_brokerless_sec_captured_end_utc"]):
                raise NewSourceStop("Previous observer not strictly between baseline and current")
            # Check that the previous successful workflow actually archived
            # the same original baseline-derived cumulative report.
            archived=json.loads((previous_successful_sec_dir/
                "cumulative-original-accession-delta.json").read_bytes())
            recomputed=original_source_delta(
                original_u3_dir=original_u3_dir,
                pinned_first_sec_dir=pinned_first_sec_dir,
                later_actual_sec_dir=previous_successful_sec_dir)
            # U5's original successful archive predates these new fields.
            # Verify EVERY original report field exactly while accepting the
            # new, independently non-trading observer-comparison metadata.
            comparison_fields={
                "previous_successful_daily_observer_artifact_compared",
                "previous_successful_main_observer_run_id",
                "previous_successful_observer_manifest_sha256",
                "new_accessions_since_previous_successful_observer_count",
                "accessions_absent_from_previous_successful_observer_NOT_trade_signals",
                "previous_successful_observer_is_not_SEC_public_release_timestamp",
            }
            original_fields=set(recomputed)-comparison_fields
            if (not isinstance(archived,dict)
                or not original_fields<=set(archived)
                or not set(archived)<=set(recomputed)
                or any(archived[k]!=recomputed[k] for k in original_fields)):
                raise NewSourceStop("Previous successful observer report does not replay")
            if archived.get("previous_successful_daily_observer_artifact_compared",False):
                prior_count=archived.get("new_accessions_since_previous_successful_observer_count")
                prior_rows=archived.get("accessions_absent_from_previous_successful_observer_NOT_trade_signals")
                if (type(prior_count) is not int or prior_count<0
                    or not isinstance(prior_rows,list) or len(prior_rows)!=prior_count):
                    raise NewSourceStop("Previous observer comparison metadata inconsistent")
            prior_keys={(r["cik"],r["accession"])
                        for r in prior_delta["candidate_first_delta_filings_not_trade_signals"]}
            now_keys={(r["sec_cik_10_digit"],r["original_sec_filing_accession"])
                      for r in outcome}
            if not prior_keys<=now_keys:
                raise NewSourceStop("Previously observed candidate accession disappeared")
            new_since_previous=[
                {**r,"first_seen_since_previous_successful_source_only":True}
                for r in outcome
                if (r["sec_cik_10_digit"],r["original_sec_filing_accession"])
                   not in prior_keys
            ]
            previous_manifest_sha=sha256(
                (previous_successful_sec_dir/"manifest.json").read_bytes()).hexdigest()
        except NewSourceStop:
            raise
        except (u4.BaselineStop,KeyError,ValueError,TypeError,OSError,EOFError,
                zlib.error,json.JSONDecodeError) as exc:
            raise NewSourceStop("Previous successful SEC archive failed original replay") from exc
    latest_raw=(later_actual_sec_dir/"manifest.json").read_bytes()
    first_raw=(pinned_first_sec_dir/"manifest.json").read_bytes()
    return {
        "schema":SCHEMA,
        "status":"REVISABLE_SEC_FILING_CUMULATIVE_DELTA_SINCE_FIRST_BASELINE_NOT_ALPHA",
        "original_issuer_identity_run_id":PINNED_U3_MAIN_RUN_ID,
        "original_first_sec_baseline_run_id":PINNED_U4_MAIN_RUN_ID,
        "original_first_sec_baseline_artifact_id":PINNED_U4_FIRST_BASELINE_ARTIFACT_ID,
        "original_sec_first_baseline_manifest_sha256":sha256(first_raw).hexdigest(),
        "current_source_manifest_sha256":sha256(latest_raw).hexdigest(),
        "original_first_baseline_observed_utc":
            original["original_brokerless_sec_captured_end_utc"],
        "current_original_sec_source_completed_utc":
            later["original_brokerless_sec_captured_end_utc"],
        "exact_preselected_100_SEC_CIK_sources_verified":True,
        "known_filings_present_in_baseline":
            original["baseline_historical_earnings_filing_accession_count"],
        "cumulative_absent_from_FIRST_baseline_accessions_now_visible":
            len(outcome),
        "candidate_accessions_absent_from_first_baseline_NOT_trade_signals":
            outcome,
        "newly_observed_TODAY_or_first_seen_in_this_run_proven":False,
        "previous_successful_daily_observer_artifact_compared":
            previous_successful_sec_dir is not None,
        "previous_successful_main_observer_run_id":previous_successful_main_run_id,
        "previous_successful_observer_manifest_sha256":previous_manifest_sha,
        "new_accessions_since_previous_successful_observer_count":
            None if new_since_previous is None else len(new_since_previous),
        "accessions_absent_from_previous_successful_observer_NOT_trade_signals":
            new_since_previous,
        "previous_successful_observer_is_not_SEC_public_release_timestamp":True,
        "actual_original_SEC_public_dissemination_time_proven":False,
        "SEC_filing_date_is_not_economic_intraday_timestamp":True,
        "this_is_a_watch_population_not_an_investment_strategy":True,
        "candidates_with_independent_analyst_surprise":0,
        "independent_future_stock_return_marks":0,
        "measured_portfolio_alpha":False,
        "first_source_issuer_attribution_was_third_party_mirror":True,
        "historical_backtest_point_in_time_source":False,
        "original_live_pilot_ceiling_usd":"130.30",
        "live_stop_and_kill_unmodified":True,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,"live_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-u3",type=Path,required=True)
    p.add_argument("--original-first-sec",type=Path,required=True)
    p.add_argument("--later-sec",type=Path,required=True)
    p.add_argument("--previous-successful-sec",type=Path)
    p.add_argument("--previous-successful-main-run-id",type=int)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        raise NewSourceStop("Do not overwrite existing original SEC delta artifact")
    doc=original_source_delta(
        original_u3_dir=args.original_u3,
        pinned_first_sec_dir=args.original_first_sec,
        later_actual_sec_dir=args.later_sec,
        previous_successful_sec_dir=args.previous_successful_sec,
        previous_successful_main_run_id=args.previous_successful_main_run_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    print("Original verified 100 CIKs:",doc["exact_preselected_100_SEC_CIK_sources_verified"])
    print("PREEXISTING baseline 8-K filings:",doc["known_filings_present_in_baseline"])
    print("CUMULATIVE after-baseline absent original accessions:",
          doc["cumulative_absent_from_FIRST_baseline_accessions_now_visible"])
    print("New since previous successful source (null if unverified):",
          doc["new_accessions_since_previous_successful_observer_count"])
    print("Not a same-day first dissemination time. NOT proven alpha. NO BROKER.")

if __name__=="__main__":main()

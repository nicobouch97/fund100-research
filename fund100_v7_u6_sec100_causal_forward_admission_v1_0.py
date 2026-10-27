"""V7 U6: independently replayed SEC100 source -> frozen prospective model closes.

A verified U5 consecutive archived SEC receipt, NOT the SEC filing date or a
third-party news clock, determines first hypothetical entry. Every accession
new relative to the immediately prior successful observer is frozen before
independent future price acquisition. A same-day close is never assumed.
This module DOES NOT fetch prices, publish returns, place orders, release
risk limits, or claim an edge. Zero events means zero model exposures.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

import exchange_calendars as xcals
import pandas as pd

import fund100_v7_u5_original_sec100_postbaseline_delta_v1_0 as u5

SCHEMA = "FUND100_V7_U6_SEC100_CONSECUTIVE_SOURCE_FROZEN_FORWARD_CLOSES_V1"
COST_BPS_EACH_SIDE = (5, 15, 35)
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
TRADING_AUTHORIZED = False

class ForwardAdmissionStop(ValueError):
    pass

def stamp(value):
    if type(value) is not str or not re.fullmatch(
            r"20[0-9]{2}-(?:0[1-9]|1[0-2])-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z",value):
        raise ForwardAdmissionStop("SEC source timestamp not canonical UTC")
    try:
        dt=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ForwardAdmissionStop("SEC source timestamp invalid") from exc
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ")!=value:
        raise ForwardAdmissionStop("SEC source timestamp not canonical UTC")
    return dt

def future_closes(captured:datetime):
    """First TWO actual XNYS sessions strictly AFTER source UTC date.

    This conservative research model does not assume a source obtained
    earlier on a trading date was executable at that same day's close.
    """
    if not isinstance(captured,datetime) or captured.tzinfo!=timezone.utc:
        raise ForwardAdmissionStop("First source receipt must be UTC")
    day=captured.date()
    try:
        cal=xcals.get_calendar("XNYS")
        idx=cal.sessions_in_range(
            pd.Timestamp(day+timedelta(days=1)),
            pd.Timestamp(day+timedelta(days=16)))
    except Exception as exc:
        raise ForwardAdmissionStop("Independent NYSE exchange calendar unavailable") from exc
    if len(idx)<2:
        raise ForwardAdmissionStop("Missing two subsequent NYSE closes")
    entry=idx[0].date()
    exit_=idx[1].date()
    if not (day<entry<exit_):
        raise ForwardAdmissionStop("Forward closes would use lookahead")
    return entry.isoformat(),exit_.isoformat()

def freeze_verified_delta(report:dict)->dict:
    """Consume U5's independently replayed report; never a broker signal.

    Production callers MUST obtain report from u5.original_source_delta,
    not trust an unauthenticated JSON file. This function separately checks
    data shape/relationships to avoid silent duplicate investments.
    """
    if not isinstance(report,dict) or (
        report.get("schema")!=u5.SCHEMA
        or report.get("status")!="REVISABLE_SEC_FILING_CUMULATIVE_DELTA_SINCE_FIRST_BASELINE_NOT_ALPHA"
        or report.get("exact_preselected_100_SEC_CIK_sources_verified") is not True
        or report.get("newly_observed_TODAY_or_first_seen_in_this_run_proven") is not False
        or report.get("actual_original_SEC_public_dissemination_time_proven") is not False
        or report.get("measured_portfolio_alpha") is not False
        or report.get("broker_gets")!=0 or report.get("broker_posts")!=0
        or report.get("broker_orders")!=0
        or report.get("trading_authorized") is not False
        or report.get("live_authorized") is not False):
        raise ForwardAdmissionStop("SEC census evidence is not a brokerless replay")
    current=stamp(report.get("current_original_sec_source_completed_utc"))
    baseline=stamp(report.get("original_first_baseline_observed_utc"))
    if not baseline<current:
        raise ForwardAdmissionStop("SEC source chronology inverted")
    for key in ("original_sec_first_baseline_manifest_sha256",
                "current_source_manifest_sha256"):
        h=report.get(key)
        if type(h) is not str or re.fullmatch(r"[0-9a-f]{64}",h) is None:
            raise ForwardAdmissionStop("Untrusted SEC manifest SHA")
    cumulative=report.get("candidate_accessions_absent_from_first_baseline_NOT_trade_signals")
    n=report.get("cumulative_absent_from_FIRST_baseline_accessions_now_visible")
    if (type(n) is not int or n<0 or not isinstance(cumulative,list)
        or len(cumulative)!=n):
        raise ForwardAdmissionStop("Cumulative census inconsistent")
    cumulative_keys=set()
    for r in cumulative:
        if not isinstance(r,dict):
            raise ForwardAdmissionStop("Cumulative accession malformed")
        key=(r.get("sec_cik_10_digit"),r.get("original_sec_filing_accession"))
        if key in cumulative_keys:
            raise ForwardAdmissionStop("Duplicate historical accession")
        cumulative_keys.add(key)

    has_previous=report.get("previous_successful_daily_observer_artifact_compared")
    previous_id=report.get("previous_successful_main_observer_run_id")
    n_new=report.get("new_accessions_since_previous_successful_observer_count")
    new_rows=report.get("accessions_absent_from_previous_successful_observer_NOT_trade_signals")
    if has_previous is False:
        if previous_id is not None or n_new is not None or new_rows is not None:
            raise ForwardAdmissionStop("Missing prior source cannot imply first observation")
        status="NO_PREVIOUS_SOURCE_CANNOT_ADMIT_NEW_EVENTS"
        new_rows=[]
    elif has_previous is True:
        h=report.get("previous_successful_observer_manifest_sha256")
        if (type(previous_id) is not int or previous_id<=0
            or type(h) is not str or re.fullmatch(r"[0-9a-f]{64}",h) is None
            or type(n_new) is not int or n_new<0
            or n_new>n or not isinstance(new_rows,list) or len(new_rows)!=n_new):
            raise ForwardAdmissionStop("Prior observer source proof malformed")
        status=("FROZEN_NEW_SOURCE_OBSERVATIONS_WAIT_FUTURE_PRICES" if n_new
                else "VERIFIED_NO_NEW_ACCESSIONS")
    else:
        raise ForwardAdmissionStop("Unverified previous-source status")

    entries={}
    new_keys=set()
    accession_rows=[]
    for r in new_rows:
        if (not isinstance(r,dict)
            or r.get("first_seen_since_previous_successful_source_only") is not True
            or r.get("first_seen_in_current_run_proven") is not False
            or r.get("SEC_actual_disclosure_timestamp_verified") is not False
            or r.get("broker_order_authorized") is not False):
            raise ForwardAdmissionStop("Original filing was promoted as tradeable")
        ticker=r.get("ticker")
        cik=r.get("sec_cik_10_digit")
        accession=r.get("original_sec_filing_accession")
        if (type(ticker) is not str or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}",ticker)
            or type(cik) is not str or not re.fullmatch(r"[0-9]{10}",cik)
            or type(accession) is not str or not re.fullmatch(
                r"[0-9]{10}-[0-9]{2}-[0-9]{6}",accession)):
            raise ForwardAdmissionStop("Untrusted accession or ticker")
        key=(cik,accession)
        if key in new_keys or key not in cumulative_keys:
            raise ForwardAdmissionStop("Duplicate or not-cumulative accession")
        new_keys.add(key)
        original=next(q for q in cumulative
                      if (q["sec_cik_10_digit"],q["original_sec_filing_accession"])==key)
        if any(r.get(k)!=original.get(k) for k in original):
            raise ForwardAdmissionStop("New accession differs from original SEC census")
        observed=stamp(r.get("visible_in_THIS_later_original_source_utc"))
        filing=r.get("sec_original_filing_date")
        try:
            filed=date.fromisoformat(filing)
        except (ValueError,TypeError):
            raise ForwardAdmissionStop("Untrusted SEC filing calendar date") from None
        if (observed>current or observed<=baseline
            or filed>observed.date()):
            raise ForwardAdmissionStop("Original filing observed out of source chronology")
        entry_date,exit_date=future_closes(current)
        admission={
            "ticker":ticker,"sec_cik_10_digit":cik,
            "original_sec_filing_accession":accession,
            "sec_filing_date_not_first_public_release":filing,
            "current_original_SEC_observed_utc":observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "first_research_eligible_entry_close":entry_date,
            "second_research_eligible_exit_close":exit_date,
            "first_observed_by_Fund100_before_model_entry":True,
            "independent_future_price_source_received":False,
            "post_cost_relative_return":None,
            "broker_order":None}
        accession_rows.append(admission)
        exposure=(ticker,entry_date)
        if exposure not in entries:
            entries[exposure]={"ticker":ticker,"entry_close":entry_date,
                "exit_close":exit_date,"accessions":[],"post_cost_return":None,
                "stock_and_SPY_future_closes_authenticated":False}
        entries[exposure]["accessions"].append(accession)
    exposure_rows=sorted(entries.values(),key=lambda a:(a["entry_close"],a["ticker"]))
    for x in exposure_rows:
        x["accessions"].sort()
    return {
        "schema":SCHEMA,"status":status,
        "source":"INDEPENDENTLY_REPLAYED_U5_CONSECUTIVE_OFFICIAL_SEC100",
        "previous_main_observer_run":previous_id,
        "current_source_finished_utc":current.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "current_source_manifest_sha256":report["current_source_manifest_sha256"],
        "u5_census_report_sha256":sha256(
            json.dumps(report,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "new_accessions_relative_to_preceding_successful_observer":
            n_new if has_previous else None,
        "distinct_model_exposures":len(exposure_rows),
        "source_qualified_accessions":sorted(accession_rows,
                  key=lambda a:(a["ticker"],a["original_sec_filing_accession"])),
        "deduplicated_stock_entry_exposures":exposure_rows,
        "entry_first_NYSE_session_strictly_after_capture_date":True,
        "exit_next_NYSE_session":True,
        "historical_first_SEC_dissemination_time_known":False,
        "forward_price_mark_count":0,"future_return_measurement":None,
        "research_costs_bps_each_side":list(COST_BPS_EACH_SIDE),
        "alpha_established":False,"broker_gets":0,"broker_posts":0,
        "broker_orders":0,"trading_authorized":False,"live_authorized":False}

def freeze_from_sources(*,original_u3:Path,original_first_sec:Path,
                        later_sec:Path,previous_sec:Path|None=None,
                        previous_main_id:int|None=None)->dict:
    # U5 validates 100 original raw compressed SEC responses, all SHA256s,
    # both baselines, prior report, accession set monotonicity and timestamps.
    original=u5.original_source_delta(
        original_u3_dir=original_u3,
        pinned_first_sec_dir=original_first_sec,
        later_actual_sec_dir=later_sec,
        previous_successful_sec_dir=previous_sec,
        previous_successful_main_run_id=previous_main_id)
    return freeze_verified_delta(original)

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
        raise ForwardAdmissionStop("Never overwrite a source-frozen research roster")
    result=freeze_from_sources(
        original_u3=args.original_u3,original_first_sec=args.original_first_sec,
        later_sec=args.later_sec,previous_sec=args.previous_successful_sec,
        previous_main_id=args.previous_successful_main_run_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("Frozen source-relative new SEC100 accessions:",
          result["new_accessions_relative_to_preceding_successful_observer"])
    print("Distinct future modeled exposures:",result["distinct_model_exposures"])
    print("No price returns, no fills, no broker.")

if __name__=="__main__":
    main()

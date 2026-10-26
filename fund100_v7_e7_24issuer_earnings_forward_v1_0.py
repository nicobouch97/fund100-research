"""Fund-100 V7-E7: 24-issuer original SEC first-observation forward marks.

NO BROKER. Source selection is pinned to successful original E6 main run
40365882558, independently verified 24-issuer raw SEC manifest and original
public P4L 24-company + SPY + SHY adjusted daily price vintage.

Never backdate the SEC observation to the filed date. First hypothetical
entry is the first completed NYSE CLOSE strictly AFTER the original SEC
capture DATE, exit is the immediately following NYSE CLOSE. Original price
vintage must be acquired after both closes; until then all returns are NULL.
No same-day closing fills inferred from filings observed intraday, analyst
consensus or public news timestamps, no broker order and no alpha promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_stock_broad_momentum_p4l_v1_0 as p4l

SCHEMA="FUND100_V7_E7_24_ISSUER_SOURCE_DATED_FORWARD_MARKS_NO_BROKER_V1"
PINNED_E6_MAIN_RUN=40365882558
PINNED_E6_ARTIFACT=12671170962
PINNED_E6_MANIFEST_SHA256="878ce40b44c7b574e5161f98b72979514ccf2ee3eceb88dd58664b644c9deb0a"
COSTS=(5,15,35)
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0

class EventForwardStop(ValueError):pass

def utc(text:str)->datetime:
    try:
        return e6._utc(text)
    except (ValueError,TypeError,e6.ExpandedFeedStop) as exc:
        raise EventForwardStop("Original source UTC invalid") from exc

def next_completed_sessions(after:datetime)->tuple[pd.Timestamp,pd.Timestamp]:
    """Prospectively fixed first TWO full XNYS sessions after observation date."""
    try:
        days=xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp((after+timedelta(days=1)).date()),
            pd.Timestamp((after+timedelta(days=15)).date()))
    except (ValueError,IndexError,TypeError) as exc:
        raise EventForwardStop("Cannot independently establish next two NYSE sessions") from exc
    if len(days)<2:
        raise EventForwardStop("No two independent subsequent exchange closes")
    return days[0].tz_localize(None),days[1].tz_localize(None)

def evaluate(manifest:dict, price_report:dict, prices:pd.DataFrame)->dict:
    if (not isinstance(manifest,dict) or manifest.get("schema")!=e6.SCHEMA
        or manifest.get("source_count")!=24
        or manifest.get("original_P4N_source_manifest_sha256")!=e6.ORIGINAL_P4N_MANIFEST_SHA256
        or manifest.get("broker_orders")!=0 or manifest.get("broker_http_requests")!=0
        or manifest.get("live_authorized") is not False
        or manifest.get("trading_authorized") is not False
        or manifest.get("forward_return_observations")!=0
        or manifest.get("new_event_first_discovered_in_this_capture_proven") is not False):
        raise EventForwardStop("Original 24-company SEC original not verified")
    data=p4l.validate_prices(prices)
    try:
        import fund100_stock_quality_momentum_p4g_v1_0 as p4g
        p4g.verify_original_nyse_source_sessions(data.index)
    except (p4g.P4GStop,ValueError,TypeError,IndexError) as exc:
        raise EventForwardStop("Original 24-issuer price sessions are not all NYSE closes") from exc
    if (not isinstance(price_report,dict)
        or price_report.get("schema")!=p4l.SCHEMA
        or price_report.get("cohort_size")!=24
        or price_report.get("canonical_price_csv_sha256")!=sha256(
            p4l.canonical_csv(data).encode("utf-8")).hexdigest()
        or price_report.get("asof_completed_session")!=data.index[-1].date().isoformat()
        or price_report.get("trading_authorized") is not False
        or price_report.get("broker_orders")!=0
        or price_report.get("paper_authorized") is not False
        or price_report.get("live_authorized") is not False):
        raise EventForwardStop("Original independently dated 24-company price source mismatch")
    sec_end=utc(manifest["capture_complete_utc"])
    price_at=utc(price_report["source_acquired_at_utc"])
    if (price_at<=sec_end or price_at.date()<=data.index[-1].date()
        or (price_at.date()-data.index[-1].date()).days>5):
        raise EventForwardStop("Price snapshot not genuinely later than original SEC capture")
    eligible=manifest.get("after_registration_earnings_8k_events_not_trade_signals")
    historical=manifest.get("precohort_reference_earnings_8k_events_not_trade_signals")
    if (not isinstance(eligible,list) or not isinstance(historical,list)
        or len(eligible)!=manifest.get("after_registration_event_count")
        or len(historical)!=manifest.get("precohort_reference_event_count")):
        raise EventForwardStop("Original SEC event counts were changed")
    accepted=[]
    excluded=[]
    observed_keys=set()
    for event,pre in [(x,False) for x in eligible]+[(x,True) for x in historical]:
        if not isinstance(event,dict):
            raise EventForwardStop("Unknown source filing")
        sym=event.get("ticker")
        original=e6.identities()
        ids={row["ticker"]:row for row in original}
        if (sym not in ids or event.get("cik")!=ids[sym]["cik"]
            or event.get("type")!="8-K ITEM 2.02"
            or event.get("broker_order_authorized") is not False):
            raise EventForwardStop("SEC observation source identity invalid")
        accession=event.get("original_sec_accession")
        key=(sym,accession)
        if not isinstance(accession,str) or key in observed_keys:
            raise EventForwardStop("Duplicate or missing original SEC accession")
        observed_keys.add(key)
        filed=event.get("filing_date")
        registered=ids[sym]["frozen_registration"]
        if ((pre and (event.get("cohort_status")!="EARLIER_THAN_EXPANDED_COHORT_FREEZE_NOT_A_FORWARD_SIGNAL"
                      or filed>=registered))
            or (not pre and (event.get("cohort_status")!="AFTER_REGISTERED_DATE_SOURCE_OBSERVATION_NOT_FORWARD_SIGNAL"
                             or filed<registered))):
            raise EventForwardStop("Historical pre-cohort filing converted into a forward event")
        seen=utc(event["original_sec_observed_at_utc"])
        if seen>sec_end or filed>seen.date().isoformat():
            raise EventForwardStop("Filing future of independent original source receipt")
        if pre:
            excluded.append({"ticker":sym,"filing_date":filed,
                             "reason":"FILING_PREDATES_REGISTERED_2026_COHORT_NO_FORWARD_REACTION"})
            continue
        entry,exit_=next_completed_sessions(seen)
        row={"ticker":sym,"original_sec_accession":accession,
             "filing_date":filed,"source_first_observed_utc":event["original_sec_observed_at_utc"],
             "first_model_entry_close":entry.date().isoformat(),
             "second_model_exit_close":exit_.date().isoformat(),
             "status":"WAITING_FOR_TWO_POST_OBSERVATION_COMPLETED_SESSIONS",
             "gross_stock_return":None,"gross_spy_return":None,
             "net_stock_minus_net_spy_percentage_points":None,
             "net_stock_minus_gross_spy_percentage_points":None,
             "actual_order_placed":False}
        # A timestamp later than the SECOND close is necessary. Daily
        # vendor closes cannot establish exact inside-session timestamps,
        # so require acquisition on a strictly later UTC date.
        if (exit_ in data.index and entry in data.index
            and data.index[-1]>=exit_
            and price_at.date()>exit_.date()):
            stock=float(data.loc[exit_,sym]/data.loc[entry,sym]-1)
            spy=float(data.loc[exit_,"SPY"]/data.loc[entry,"SPY"]-1)
            if stock<=-1 or spy<=-1:
                raise EventForwardStop("Invalid independently acquired equity returns")
            row.update({
                "status":"HISTORICAL_TWO_COMPLETED_CLOSES_DESCRIPTIVE_NOT_ALPHA",
                "gross_stock_return":round(stock,10),
                "gross_spy_return":round(spy,10),
                "net_stock_minus_net_spy_percentage_points":{
                    str(b):round(100*((1+stock)*(1-b/10000)**2
                                      -(1+spy)*(1-b/10000)**2),9)
                    for b in COSTS},
                "net_stock_minus_gross_spy_percentage_points":{
                    str(b):round(100*((1+stock)*(1-b/10000)**2
                                      -(1+spy)),9)
                    for b in COSTS}
            })
        accepted.append(row)
    n_complete=sum(row["gross_stock_return"] is not None for row in accepted)
    return {
        "schema":SCHEMA,
        "status":("ORIGINAL_SEC_EVENTS_WITH_POST_OBSERVATION_PRICE_MARKS_NOT_ALPHA"
                  if n_complete else "WAITING_FOR_INDEPENDENT_POST_OBSERVATION_MARKS"),
        "original_SEC_main_run":PINNED_E6_MAIN_RUN,
        "original_SEC_artifact_id":PINNED_E6_ARTIFACT,
        "pinned_original_SEC_manifest_sha256":PINNED_E6_MANIFEST_SHA256,
        "SEC_capture_utc":manifest["capture_complete_utc"],
        "price_capture_utc":price_report["source_acquired_at_utc"],
        "price_last_completed_session":price_report["asof_completed_session"],
        "price_source_csv_sha256":price_report["canonical_price_csv_sha256"],
        "source_issuer_count":24,"registered_source_events":len(accepted),
        "precohort_historical_exclusions":excluded,
        "post_observation_two_close_marks":n_complete,
        "cost_bps_each_side":list(COSTS),
        "prices_same_later_vendor_vintage_stock_and_spy":True,
        "same_cost_applied_to_spy_and_stock_in_matched_comparison":True,
        "original_filing_date_is_not_source_observation_date":True,
        "entry_strictly_after_original_SEC_observation_date":True,
        "archive_later_vendor_prices_may_revise_original_history":True,
        "survivorship_safe_24_company_history":False,
        "trading_strategy_signal_qualified":False,
        "observations":accepted,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,
        "live_authorized":False,"paper_authorized":False,"trading_authorized":False,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sec-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    verified=e6.verify(args.sec_dir)
    original=(args.sec_dir/"manifest.json").read_bytes()
    if sha256(original).hexdigest()!=PINNED_E6_MANIFEST_SHA256:
        raise EventForwardStop("Not the exact original successful E6 SEC manifest")
    # Original adjusted stock and market close prices independently obtained,
    # then saved unchanged before any analysis.
    prices=p4l.public_prices()
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot=p4l.evaluate(
        prices,acquired_at_utc=stamp,
        provider_reference="yfinance original 24-issuer completed-close snapshot "+stamp)
    output=args.output_dir
    output.mkdir(parents=True,exist_ok=True)
    (output/"original-24issuer-prices.csv").write_text(p4l.canonical_csv(prices))
    (output/"original-price-manifest.json").write_text(
        json.dumps(snapshot,sort_keys=True,indent=2)+"\n")
    result=evaluate(verified,snapshot,prices)
    (output/"source-pinned-24issuer-event-forward.json").write_text(
        json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("SEC original registered postcohort filing observations:",len(result["observations"]))
    print("PRECOHORT historic observations excluded:",len(result["precohort_historical_exclusions"]))
    print("AFTER original observation genuine two-close marks:",result["post_observation_two_close_marks"])
    print("Research status:",result["status"],"No broker order or alpha promotion.")

if __name__=="__main__":main()

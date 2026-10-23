"""V7-E5: independently sourced post-signal event price marks (research only).

The source E4 SEC/raw source AND T+1 price snapshot is frozen before
the modelled entry. A separate, later genuine P4G artifact can mark a
FIXED one-completed-session horizon, using ONLY its own later-vintage
post-signal entry+exit rows. Vendor history revisions are always labelled.
This is not a fill, executable next-close order, alpha or trade permit.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

import fund100_v7_e4_sec_event_capture_v1_0 as sec
import fund100_v7_e4_event_signal_observer_v1_0 as signal
import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_V7_E5_ONE_INTERVAL_PINNED_EVENT_FORWARD_MARKS_V1"
COSTS_BPS=(5,15,35)
SIGNAL_STATUS="OBSERVED_REACTION_OVER_THRESHOLD_NOT_FORWARD_ALPHA"

class ForwardStop(ValueError):
    pass

def evaluate(*, sec_source:dict, baseline:dict, baseline_prices:pd.DataFrame,
             follow:dict, follow_prices:pd.DataFrame) -> dict:
    """Pure evaluation; production *must* read and authenticate every artifact."""
    # Reconstruct signal from *baseline* time and original prices, never later source.
    original=signal.evaluate(sec_source,baseline,baseline_prices)
    first=p4g.validate_prices(baseline_prices)
    later=p4g.validate_prices(follow_prices)
    try:
        first_stamp=sec._timestamp(baseline["source_acquired_at_utc"])
        later_stamp=sec._timestamp(follow["source_acquired_at_utc"])
    except (ValueError,KeyError,TypeError) as exc:
        raise ForwardStop("original/followup source capture time invalid") from exc
    if (baseline.get("paper_authorized") is not False
        or baseline.get("live_authorized") is not False
        or baseline.get("future_performance_observations")!=0
        or follow.get("schema")!=p4g.SCHEMA
        or follow.get("broker_orders")!=0
        or follow.get("trading_authorized") is not False
        or follow.get("paper_authorized") is not False
        or follow.get("live_authorized") is not False
        or follow.get("future_performance_observations")!=0
        or follow.get("asof_completed_session")!=later.index[-1].date().isoformat()
        or later_stamp<=first_stamp
        or later_stamp.date()<=later.index[-1].date()
        or (later_stamp.date()-later.index[-1].date()).days>5
        or len(first)==0
        or not first.index.isin(later.index).all()):
        raise ForwardStop("later price source not independently dated, complete or research-only")
    prefix=later.loc[first.index]
    prefix_identical=bool(prefix.equals(first))
    base_prefix_sha=sha256(p4g.canonical_price_csv(first).encode("utf-8")).hexdigest()
    late_prefix_sha=sha256(p4g.canonical_price_csv(prefix).encode("utf-8")).hexdigest()
    next_dates=later.index[later.index>first.index[-1]]
    # Always choose the FIRST two later completed sessions; later runs cannot
    # choose an attractive exit date from multiple opportunities.
    entry=next_dates[0] if len(next_dates)>=1 else None
    exit_=next_dates[1] if len(next_dates)>=2 else None
    candidates=[e for e in original["events"] if e["status"]==SIGNAL_STATUS]
    results=[]
    for item in candidates:
        ticker=item["ticker"]
        obs={"ticker":ticker,"original_sec_accession":item["original_sec_accession"],
             "filed_date":item["original_filing_date"],
             "pre_entry_reaction_original_source":item["pre_entry_reaction_vs_spy"],
             "status":"NO_POST_SIGNAL_ENTRY_OR_EXIT_YET",
             "hypothetical_entry_close":None,"hypothetical_exit_close":None,
             "one_completed_session_net_stock_minus_gross_SPY":None,
             "broker_fills_verified":False,"orders_authorized":False}
        if exit_ is not None:
            if not (entry.date()>first.index[-1].date()
                    and exit_.date()>entry.date()
                    and first_stamp.date()<=entry.date()
                    and later_stamp.date()>exit_.date()):
                raise ForwardStop("forward entry/exit or source capture chronology invalid")
            gross_stock=float(later.loc[exit_,ticker]/later.loc[entry,ticker]-1)
            gross_spy=float(later.loc[exit_,"SPY"]/later.loc[entry,"SPY"]-1)
            # Match P4K's exact multiplicative entry/exit cost model.
            # SPY is an UNTRADED gross benchmark, not a second net position.
            obs.update({
                "status":"REVISED_OR_MATCHED_VENDOR_VINTAGE_HYPOTHETICAL_ONE_INTERVAL_MARK",
                "hypothetical_entry_close":entry.date().isoformat(),
                "hypothetical_exit_close":exit_.date().isoformat(),
                "one_completed_session_net_stock_minus_gross_SPY":{
                    str(b):round((1+gross_stock)*(1-b/10000)**2-1-gross_spy,10)
                    for b in COSTS_BPS},
                "stock_gross":round(gross_stock,10),
                "SPY_gross":round(gross_spy,10),
            })
        results.append(obs)
    if not candidates:
        status="NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS"
    elif exit_ is None:
        status="WAITING_FOR_TWO_COMPLETED_POST_SIGNAL_SESSIONS"
    else:
        status="ONE_INTERVAL_ALTERNATE_OR_MATCHED_VENDOR_RESEARCH_MARKS_NO_FILLS"
    return {
        "schema":SCHEMA,"status":status,
        "source_original_SEC_capture":sec_source["capture_complete_utc"],
        "original_price_capture":baseline["source_acquired_at_utc"],
        "original_price_asof":baseline["asof_completed_session"],
        "later_price_capture":follow["source_acquired_at_utc"],
        "later_price_asof":follow["asof_completed_session"],
        "original_prefix_sha256":base_prefix_sha,
        "later_same_dates_prefix_sha256":late_prefix_sha,
        "original_vendor_historical_rows_unchanged":prefix_identical,
        "vendor_revision_if_any_reported_not_repaired":True,
        "model_entry_first_later_session":entry.date().isoformat() if entry is not None else None,
        "model_exit_second_later_session":exit_.date().isoformat() if exit_ is not None else None,
        "pre_entry_qualified_original_events":len(candidates),
        "observed_events":len(original["events"]),
        "costs_bps_each_side":list(COSTS_BPS),
        "stock_entry_and_exit_costs_compounded_exactly":True,
        "SPY_is_untraded_gross_benchmark":True,
        "hypothetical_marks":results,
        "original_signal_is_never_reranked_from_later_snapshot":True,
        "returns_same_later_vendor_vintage_only":True,
        "spread_and_trade_fills_verified":False,
        "independent_market_session_calendar_verified":False,
        "statistically_significant_alpha_proven":False,
        "actual_live_account_pnl_measured":False,
        "private_state_mutations":0,"broker_http_requests":0,
        "broker_orders":0,"paper_authorized":False,"live_authorized":False,
        "trading_authorized":False
    }


def aggregate_reports(reports:list[dict])->dict:
    """Aggregate ALL source-qualified E4 captures, not just the newest eligible one.

    One later archived price vintage is shared across the cohort. Repeated
    observations of the same public filing/entry are counted ONCE. The
    aggregate is descriptive and never a model-selection or trading signal.
    """
    from statistics import mean, median
    if type(reports) is not list or len(reports)>40:
        raise ForwardStop("Expected at most forty independently archived E4 captures")
    source_ids=set()
    later_source=None
    unique={}
    revised=0
    for r in reports:
        if type(r) is not dict or r.get("schema")!=SCHEMA:
            raise ForwardStop("Unverified event-forward report")
        for name in ("SEC_manifest_file_SHA256","original_price_report_SHA256",
                     "later_price_report_SHA256","original_price_csv_SHA256",
                     "later_price_csv_SHA256"):
            v=r.get(name)
            if type(v) is not str or len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
                raise ForwardStop("Source artifact hash missing or malformed")
        if (r.get("broker_orders")!=0 or r.get("broker_http_requests")!=0
            or r.get("private_state_mutations")!=0
            or r.get("paper_authorized") is not False
            or r.get("live_authorized") is not False
            or r.get("trading_authorized") is not False
            or r.get("original_signal_is_never_reranked_from_later_snapshot") is not True
            or r.get("returns_same_later_vendor_vintage_only") is not True
            or r.get("stock_entry_and_exit_costs_compounded_exactly") is not True
            or r.get("costs_bps_each_side")!=list(COSTS_BPS)):
            raise ForwardStop("Event source or research-only contract changed")
        later=(r["later_price_report_SHA256"],r.get("later_price_asof"),
               r.get("later_price_capture"))
        if later_source is None:
            later_source=later
        elif later_source!=later:
            raise ForwardStop("Mixed later price vintages cannot be pooled")
        source=(r["SEC_manifest_file_SHA256"],r["original_price_report_SHA256"])
        if source in source_ids:
            raise ForwardStop("Same original capture supplied twice")
        source_ids.add(source)
        rows=r.get("hypothetical_marks")
        if (type(rows) is not list
            or len(rows)!=r.get("pre_entry_qualified_original_events")
            or r.get("status") not in (
                "NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS",
                "ONE_INTERVAL_ALTERNATE_OR_MATCHED_VENDOR_RESEARCH_MARKS_NO_FILLS")):
            raise ForwardStop("Inconsistent original event cohort")
        if r.get("original_vendor_historical_rows_unchanged") is False:
            revised+=1
        for row in rows:
            if (type(row) is not dict
                or row.get("status")!="REVISED_OR_MATCHED_VENDOR_VINTAGE_HYPOTHETICAL_ONE_INTERVAL_MARK"
                or row.get("broker_fills_verified") is not False
                or row.get("orders_authorized") is not False
                or row.get("hypothetical_entry_close")!=r.get("model_entry_first_later_session")
                or row.get("hypothetical_exit_close")!=r.get("model_exit_second_later_session")):
                raise ForwardStop("Non-forward or unqualified event return")
            costs=row.get("one_completed_session_net_stock_minus_gross_SPY")
            if (type(costs) is not dict
                or set(costs)!={str(b) for b in COSTS_BPS}
                or any(type(v) not in (float,int) or not -2<v<2
                       for v in costs.values())):
                raise ForwardStop("Incomplete or invalid costed event returns")
            key=(row.get("ticker"),row.get("original_sec_accession"),
                 row.get("hypothetical_entry_close"))
            if any(type(x) is not str or not x for x in key):
                raise ForwardStop("Original event identity missing")
            if key in unique:
                prior=unique[key]
                if (prior["hypothetical_exit_close"]!=row["hypothetical_exit_close"]
                    or prior["one_completed_session_net_stock_minus_gross_SPY"]!=costs):
                    raise ForwardStop("Conflicting duplicate original event marks")
            else:
                unique[key]=row
    rows=list(unique.values())
    costed={}
    for b in COSTS_BPS:
        values=[float(r["one_completed_session_net_stock_minus_gross_SPY"][str(b)])
                for r in rows]
        costed[str(b)]={
            "observations":len(values),
            "descriptive_mean_excess_pct":round(100*mean(values),5) if values else None,
            "descriptive_median_excess_pct":round(100*median(values),5) if values else None,
            "descriptive_positive_fraction":round(sum(x>0 for x in values)/len(values),5)
                if values else None,
        }
    return {
        "schema":"FUND100_V7_E5_ALL_ELIGIBLE_E4_CAPTURES_DEDUPLICATED_COHORT_V1",
        "status":"DESCRIPTIVE_SOURCE_PINNED_EVENTS_NOT_ALPHA"
            if rows else "NO_SOURCE_QUALIFIED_FORWARD_EVENTS",
        "original_captures_evaluated":len(reports),
        "unique_original_filing_entry_events":len(rows),
        "duplicate_event_rows_removed":sum(len(r["hypothetical_marks"]) for r in reports)-len(rows),
        "captures_with_vendor_prefix_revisions":revised,
        "one_common_later_price_vintage":later_source is not None,
        "modelled_one_session_stock_minus_untraded_SPY_by_one_way_cost_bps":costed,
        "no_cross_event_independence_or_multiple_testing_claim":True,
        "not_a_survivorship_safe_universe":True,
        "statistically_significant_alpha_proven":False,
        "strategy_promoted_for_live":False,
        "broker_orders":0,"broker_http_requests":0,"private_state_mutations":0,
        "paper_authorized":False,"live_authorized":False,"trading_authorized":False,
    }

def real_sources(sec_dir:Path,baseline_json:Path,baseline_csv:Path,
                 later_json:Path,later_csv:Path)->dict:
    # Exactly original raw SEC bytes and original price captures are
    # independently validated before the model sees their content.
    source=sec.verify(sec_dir)
    base,base_prices,base_sha=p4h.read_snapshot(baseline_json,baseline_csv)
    follow,follow_prices,follow_sha=p4h.read_snapshot(later_json,later_csv)
    out=evaluate(sec_source=source,baseline=base,baseline_prices=base_prices,
                 follow=follow,follow_prices=follow_prices)
    out["SEC_manifest_file_SHA256"]=sha256((sec_dir/"manifest.json").read_bytes()).hexdigest()
    out["original_price_report_SHA256"]=base_sha
    out["later_price_report_SHA256"]=follow_sha
    out["original_price_csv_SHA256"]=base["canonical_price_csv_sha256"]
    out["later_price_csv_SHA256"]=follow["canonical_price_csv_sha256"]
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sec-dir",type=Path,required=True)
    p.add_argument("--original-json",type=Path,required=True)
    p.add_argument("--original-csv",type=Path,required=True)
    p.add_argument("--later-json",type=Path,required=True)
    p.add_argument("--later-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    r=real_sources(args.sec_dir,args.original_json,args.original_csv,
                   args.later_json,args.later_csv)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print("V7-E5",r["status"],"SIGNALS",r["pre_entry_qualified_original_events"],
          "ORIGINAL_VENDOR_PREFIX_REVISED",not r["original_vendor_historical_rows_unchanged"])
    print("NO BROKER, NO FILLS, NO LIVE ALPHA; RESEARCH MARKS ONLY.")

if __name__=="__main__":
    main()

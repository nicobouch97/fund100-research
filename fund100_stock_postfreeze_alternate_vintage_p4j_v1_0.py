"""P4J: post-freeze-only MARKS from one later price vendor snapshot.

Original P4I strict same-vintage fail-closed rules are left UNMODIFIED.
If vendor original history changes, this is a separately labelled alternate
vintage mark, never the original independently attested forward result.
No HTTP, broker, credentials, automatic orders or privileged state.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_P4J_ALTERNATE_VENDOR_VINTAGE_POST_FREEZE_ONLY_MARKS_V1"
MODE="SEPARATE_REVISED_VINTAGE_RESEARCH_NOT_P4I_PROOF"
ENTRY_EARLIEST="2026-10-19"
UNRELEASED_LIVE_TRADING=True
NO_HTTP_OR_GITHUB_MUTATIONS=True


class P4JStop(ValueError):
    pass


def compare_only_future(anchor:dict,follow:dict,prices:pd.DataFrame)->dict:
    """Use ONLY future sessions' closes for optional hypothetical marks.

    Production must call evaluate(), which source-validates anchor/JSON/CSV.
    Pure synthetic tests may call this directly with fake price frames.
    """
    original_cutoff=pd.Timestamp(p4i.FIRST_CUTOFF)
    if (anchor.get("frozen_asof_completed_market_session")!=p4i.FIRST_CUTOFF
        or anchor.get("original_p4g_json_sha256")!=p4i.ORIGINAL_JSON_SHA
        or anchor.get("original_p4g_canonical_price_csv_sha256")!=p4i.ORIGINAL_CSV_SHA
        or anchor.get("original_preselected_watchlist")!=p4i.FROZEN_WATCHLIST
        or anchor.get("reference_six_quality_cohort")!=p4i.REFERENCE_COHORT
        or anchor.get("entry_and_exit_cost_bps_each_side")!=[5,15,35]
        or anchor.get("original_history_used_as_future_strategy_returns") is not False
        or anchor.get("broker_orders")!=0
        or anchor.get("derivatives_margin_live_stocks_authorized") is not False):
        raise P4JStop("Wrong or modified original frozen P4I selection")
    if (type(follow) is not dict
        or type(follow.get("asof_completed_session")) is not str
        or type(follow.get("source_acquired_at_utc")) is not str
        or follow["source_acquired_at_utc"][:10]<=p4i.OBS_DATE):
        raise P4JStop("Later source not independently after original watchlist freeze")
    try:
        prices=p4g.validate_prices(prices)
    except (p4g.P4GStop, ValueError):
        raise P4JStop("Invalid later adjusted-close market source") from None
    if (not len(prices)
        or original_cutoff not in prices.index
        or prices.index[-1].date().isoformat()!=follow["asof_completed_session"]):
        raise P4JStop("Later source missing original cutoff or claimed final completed session")
    hist=prices.loc[:original_cutoff]
    actual_prefix_sha=sha256(p4g.canonical_price_csv(hist).encode("utf-8")).hexdigest()
    prefix_matches=actual_prefix_sha==p4i.ORIGINAL_CSV_SHA
    next_=prices.index[prices.index>original_cutoff]
    if len(next_) and next_[0].date().isoformat()<ENTRY_EARLIEST:
        raise P4JStop("Forward period was backdated before original freeze")
    selected=list(p4i.FROZEN_WATCHLIST)
    reference=list(p4i.REFERENCE_COHORT)
    if not set(selected).issubset(reference):
        raise P4JStop("Original frozen selection not in frozen reference")
    prefix_status=("ORIGINAL_HISTORICAL_PREFIX_MATCHES"
                   if prefix_matches else "ORIGINAL_HISTORICAL_PREFIX_REVISED")
    status=("NO_POST_FREEZE_ENTRY_SESSION" if len(next_)==0 else
            "ENTRY_SESSION_ONLY_NO_FORWARD_RETURN" if len(next_)==1 else
            "ALTERNATE_VENDOR_VINTAGE_POST_FREEZE_ONLY_HYPOTHETICAL_MARK")
    result={
        "schema":SCHEMA, "mode":MODE, "status":status,
        "original_source_vintage_status":prefix_status,
        "original_baseline_reference_sha256":p4i.ORIGINAL_CSV_SHA,
        "later_historical_prefix_sha256":actual_prefix_sha,
        "original_historical_vendor_price_rows_consistent":prefix_matches,
        "original_P4I_identical_vintage_claimed":False,
        "original_frozen_selected_stocks":selected,
        "frozen_original_selection_preserved":True,
        "original_selection_asof_session":p4i.FIRST_CUTOFF,
        "hypothetical_entry_session":(
            next_[0].date().isoformat() if len(next_) else None),
        "hypothetical_last_mark_session":(
            next_[-1].date().isoformat() if len(next_)>1 else None),
        "completed_sessions_after_original_freeze":len(next_),
        "postfreeze_return_intervals_observed":max(0,len(next_)-1),
        "data_used_as_illustrative_returns_start_at_or_after_oct19":True,
        "historic_pre_freeze_price_rows_used_for_returns":False,
        "same_vintage_entry_and_exit_mark_only":True,
        "vendor_dividend_adjustments_independently_verified":False,
        "exchange_session_completeness_independently_verified":False,
        "broker_fill_or_trade_verified":False,
        "statistical_alpha_or_CAGR_claimed":False,
        "research_portfolio_authorized":False,
        "paper_orders_authorized":False,
        "live_orders_authorized":False,
        "actual_broker_orders":0,
        "broker_http_calls":0,
        "private_state_mutations":0,
        "costed_scenarios":None,
    }
    if len(next_)<2:
        return result
    # Entirely WITHIN a single later snapshot and only after original freeze.
    entry=prices.index.get_loc(next_[0])
    end=prices.index.get_loc(next_[-1])
    gross={
        "fixed_selected":p4h._gross_return(prices,entry,end,selected),
        "frozen_six":p4h._gross_return(prices,entry,end,reference),
        "spy":p4h._gross_return(prices,entry,end,["SPY"]),
    }
    costs={}
    for bps in (5,15,35):
        side=bps/10000
        net={key:(1+v)*(1-side)**2-1 for key,v in gross.items()}
        costs[str(bps)]={
            "cost_bps_per_side":bps,
            "selected_net_pct":round(net["fixed_selected"]*100,6),
            "six_net_pct":round(net["frozen_six"]*100,6),
            "spy_net_pct":round(net["spy"]*100,6),
            "selected_minus_spy_pp":round(
                (net["fixed_selected"]-net["spy"])*100,6),
            "forward_prices_from_one_later_vendor_vintage":True,
            "true_entry_fills_or_spreads_observed":False,
        }
    result["costed_scenarios"]=costs
    return result


def evaluate(anchor_path:Path,followup_json:Path,followup_csv:Path)->dict:
    try:
        anchor,anchor_digest=p4i.read_anchor(anchor_path)
        follow,prices,follow_digest=p4h.read_snapshot(
            followup_json,followup_csv)
        result=compare_only_future(anchor,follow,prices)
    except (p4i.AnchorStop,p4h.ForwardStop,P4JStop,OSError,ValueError,TypeError):
        raise P4JStop("Frozen selection or self-consistent later source is invalid") from None
    result["exact_original_anchor_file_sha256"]=anchor_digest
    result["validated_later_p4g_json_sha256"]=follow_digest
    result["validated_later_p4g_price_csv_sha256"]=follow[
        "canonical_price_csv_sha256"]
    result["later_p4g_source_acquired_utc"]=follow["source_acquired_at_utc"]
    result["separate_source_status"]="SELF_CONSISTENT_LATER_SOURCE_NOT_PROVEN_SAME_VINTAGE"
    return result


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--anchor",type=Path,default=p4i.ANCHOR_FILE)
    parser.add_argument("--followup-json",type=Path,required=True)
    parser.add_argument("--followup-csv",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=evaluate(args.anchor,args.followup_json,args.followup_csv)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("P4J POSTFREEZE-ONLY ALT VINTAGE",report["status"],
          "PRIOR_VENDOR_SOURCE",report["original_source_vintage_status"],
          "FORWARD_SESSIONS",report["completed_sessions_after_original_freeze"])
    print("NO ORIGINAL P4I SAME-VINTAGE RESULT; NO ALPHA OR BROKER ORDERS")


if __name__=="__main__":
    main()

"""P4X: short-horizon, *observed* after-cost stock-challenger verdict.

Consumes the already source-vetted P4W/P4I fixed 17-Oct selection output,
not new market information. The purpose is to REPORT and compare genuine
future sessions against SPY and a frozen six-stock reference; it never
fits a new strategy, optimizes its cohort, approves a trade or infers alpha.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_forward_corporate_action_bridge_p4v_v1_0 as p4v
import fund100_stock_forward_source_selector_p4w_v1_0 as p4w

SCHEMA="FUND100_P4X_ORIGINAL_FROZEN_STOCK_CHALLENGER_AFTER_COST_VERDICT_V1"
SIDE_COST_BPS=(5,15,35)
# This is not a LIVE launch gate. The threshold only changes the *description*
# of a very small sample, never makes the strategy statistically proven.
MIN_SESSIONS_FOR_DESCRIPTIVE_TREND=21
FORWARD_ALPHA_PROVEN=False
BROKER_POST_REQUESTS=0
LIVE_ORDERS=0


class ScorecardStop(ValueError):
    pass


def _real(x:object)->float:
    if type(x) not in (float,int) or isinstance(x,bool):
        raise ScorecardStop("Non-numeric or boolean research return")
    v=float(x)
    if not isfinite(v) or abs(v)>1000:
        raise ScorecardStop("Invalid researched return or implausible bound")
    return v


def _pct(x:object)->float:
    v=_real(x)
    if not -100<v<100:
        raise ScorecardStop("Research percentage outside supported interval")
    return v


def _net(gross_pct:float,side_bps:int)->float:
    fee=side_bps/10000
    return 100*((1+gross_pct/100)*(1-fee)**2-1)


def _eq(a:float,b:float,*,tol:float=0.000003)->bool:
    return abs(a-b)<=tol


def analyze(report:dict)->dict:
    if type(report) is not dict:
        raise ScorecardStop("Source-qualified forward result absent")
    try:
        p4w._require_research_only(report)
    except p4w.SourceSelectionStop as exc:
        raise ScorecardStop("P4W source provenance or funded-order boundary rejected") from exc
    src=report.get("scheduled_research_source_selection")
    if (type(src) is not dict
        or src.get("broker_orders")!=0 or src.get("live_authorized") is not False
        or src.get("later_vendor_revisions_permitted_unconditionally") is not False):
        raise ScorecardStop("Missing source selection evidence")
    method=src.get("selection_method")
    if method=="STRICT_P4I_ORIGINAL_VINTAGE":
        if (report.get("schema")!=p4i.SCHEMA
            or src.get("strict_p4i_original_vintage_accepted") is not True
            or src.get("strict_p4i_revision_rejection") is not None
            or report.get("original_17_oct_archive_verified_before_forward_calculation") is not True
            or report.get("overlapping_original_adjusted_prices_sha_verified") is not True
            or report.get("revised_overlap_prices_used_for_pnl") is not False):
            raise ScorecardStop("Strict original-source proof absent")
    elif method=="KNOWN_PG_OCT23_DIVIDEND_BRIDGE_P4V":
        p=report.get("corporate_action_crosscheck")
        if (report.get("schema")!=p4v.SCHEMA
            or src.get("strict_p4i_original_vintage_accepted") is not False
            or type(src.get("strict_p4i_revision_rejection")) is not str
            or "material historical vendor restatement" not in src["strict_p4i_revision_rejection"]
            or type(p) is not dict or p.get("event")!=p4v.PG_EVENT
            or p.get("frozen_original_price_rows_retained") is not True
            or p.get("revised_pre_freeze_rows_used_for_returns") is not False
            or p.get("independent_total_return_benchmark_verified") is not False
            or p.get("cash_dividend_actually_settled_verified") is not False):
            raise ScorecardStop("Unqualified corporate-action source evidence")
    else:
        raise ScorecardStop("Unknown original source qualification method")
    if (report.get("original_baseline_price_csv_sha256")!=p4i.ORIGINAL_CSV_SHA
        or report.get("post_freeze_entry_session")!="2026-10-19"
        or type(report.get("future_return_observations")) is not int
        or type(report.get("observed_new_completed_sessions")) is not int
        or report["future_return_observations"]<1
        or report["observed_new_completed_sessions"]!=report["future_return_observations"]+1
        or type(report.get("post_freeze_exit_observation_session")) is not str
        or report["post_freeze_exit_observation_session"]<=report["post_freeze_entry_session"]):
        raise ScorecardStop("Invalid fixed forward-return chronology")
    try:
        dates=xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp(report["post_freeze_entry_session"]),
            pd.Timestamp(report["post_freeze_exit_observation_session"]))
    except Exception as exc:
        raise ScorecardStop("Market-session chronology cannot be verified") from exc
    if len(dates)!=report["observed_new_completed_sessions"]:
        raise ScorecardStop("Missing or fabricated completed NYSE forward sessions")
    source_key=("followup_source_sha256" if method=="KNOWN_PG_OCT23_DIVIDEND_BRIDGE_P4V"
                else "later_original_p4g_json_sha256")
    digest=report.get(source_key)
    if (type(digest) is not str or len(digest)!=64
        or any(c not in "0123456789abcdef" for c in digest)):
        raise ScorecardStop("Missing genuine later price-vintage identifier")
    scenarios=report.get("costed_return_scenarios")
    if type(scenarios) is not dict or set(scenarios)!={str(x) for x in SIDE_COST_BPS}:
        raise ScorecardStop("Missing complete predeclared 5/15/35bps cost comparisons")
    comparison={}
    gross_reference=None
    last_nets={name:None for name in ("selected","spy","equal_six")}
    for cost in SIDE_COST_BPS:
        row=scenarios[str(cost)]
        if type(row) is not dict or row.get("cost_bps_each_side")!=cost:
            raise ScorecardStop("Modified cost experiment")
        gross=_pct(row.get("selected_gross_return_pct"))
        selected=_pct(row.get("selected_net_return_pct"))
        spy=_pct(row.get("spy_net_return_pct"))
        six=_pct(row.get("equal_six_net_return_pct"))
        delta_spy=_real(row.get("selected_minus_spy_net_percentage_points"))
        delta_six=_real(row.get("selected_minus_equal_six_net_percentage_points"))
        if (not _eq(selected,_net(gross,cost))
            or not _eq(delta_spy,selected-spy)
            or not _eq(delta_six,selected-six)
            or (gross_reference is not None and not _eq(gross,gross_reference, tol=1e-8))
            or row.get("hypothetical_open_and_close_both_modelled") is not True):
            raise ScorecardStop("After-cost return arithmetic or source model inconsistent")
        if any(last_nets[n] is not None and net>=last_nets[n]
               for n,net in (("selected",selected),("spy",spy),("equal_six",six))):
            raise ScorecardStop("Larger identical-side trade costs increased net return")
        gross_reference=gross
        last_nets.update(selected=selected,spy=spy,equal_six=six)
        comparison[str(cost)]={
            "modeled_entry_and_exit_bps_each_side":cost,
            "selected_net_return_pct":round(selected,6),
            "spy_net_return_pct":round(spy,6),
            "frozen_six_net_return_pct":round(six,6),
            "selected_minus_spy_net_pp":round(delta_spy,6),
            "selected_minus_frozen_six_net_pp":round(delta_six,6),
            "beat_spy":delta_spy>0,
            "beat_frozen_six":delta_six>0,
        }
    successes=sum(row["beat_spy"] for row in comparison.values())
    status=("OUTPERFORMED_SPY_IN_ALL_MODELED_COST_SCENARIOS" if successes==3 else
            "UNDERPERFORMED_OR_TIED_SPY_IN_ALL_MODELED_COST_SCENARIOS" if successes==0 else
            "MIXED_SPY_RELATIVE_RESULTS_ACROSS_COST_SCENARIOS")
    n=report["future_return_observations"]
    return {
        "schema":SCHEMA,
        "status":"OBSERVED_RESEARCH_ONLY_NOT_A_TRADING_STRATEGY_RELEASE",
        "frozen_selection_date":"2026-10-17",
        "frozen_selection":["MSFT","KO","PG"],
        "first_hypothetical_entry_close":"2026-10-19",
        "last_observed_exit_close":report["post_freeze_exit_observation_session"],
        "completed_forward_return_intervals":n,
        "research_sample_status":(
            "VERY_SHORT_OBSERVATION_WINDOW" if n<MIN_SESSIONS_FOR_DESCRIPTIVE_TREND
            else "LONGER_DESCRIPTIVE_OBSERVATION_NOT_INDEPENDENT_ALPHA"),
        "source_validation_method":method,
        "original_fixed_source_sha256":p4i.ORIGINAL_JSON_SHA,
        "later_source_sha256":digest,
        "after_both_side_costs":comparison,
        "observed_spy_relative_verdict":status,
        "one_fixed_lookback_and_single_revisable_vendor_vintage":True,
        "hypothetical_closing_prices_not_verified_broker_fills":True,
        "dividends_beyond_specific_qualified_PG_event_not_verified":True,
        "no_estimated_CAGR_or_independent_statistical_alpha":True,
        "historical_returns_not_a_funded_profit_forecast":True,
        "cannot_promote_strategies_or_change_existing_holdings":True,
        "strategy_approved_for_live":False,
        "current_broker_account_reconciled":False,
        "broker_post_requests":0,
        "broker_orders":0,
        "live_authorized":False,
    }


def main()->None:
    args=argparse.ArgumentParser()
    args.add_argument("--qualified-report",required=True,type=Path)
    args.add_argument("--output",required=True,type=Path)
    opt=args.parse_args()
    source=opt.qualified_report.read_bytes()
    if not 100<len(source)<100000:
        raise ScorecardStop("Missing or oversized source report")
    result=analyze(json.loads(source))
    result["qualified_source_report_sha256"]=sha256(source).hexdigest()
    opt.output.parent.mkdir(parents=True,exist_ok=True)
    opt.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("P4X FORWARD COMPARISON",result["observed_spy_relative_verdict"],
          "INTERVALS",result["completed_forward_return_intervals"],
          "FUNDING ORDERS",result["broker_orders"])


if __name__=="__main__":
    main()

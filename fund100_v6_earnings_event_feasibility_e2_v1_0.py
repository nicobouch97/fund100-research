"""V6-E2 retrospective economics of real SEC earnings events; never trade.

The 2026 handpicked US megacap survivor cohort and October 2026 archive
make historical results biased/exploratory, NOT investable alpha.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import datetime as dt
import json
from pathlib import Path
from statistics import mean, median

import pandas as pd
import exchange_calendars as xcals

import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_V6_E2_RETROSPECTIVE_EARNINGS_REACTION_FEASIBILITY_V1"
EARLIEST=dt.date(2025,11,1)
LATEST=dt.date(2026,8,31)
N_FOLLOWING_TO_SIGNAL=2
ENTER_FOLLOWING_IDX=2
TEN_SESSION_HOLD=10
EXIT_FOLLOWING_IDX=ENTER_FOLLOWING_IDX+TEN_SESSION_HOLD
SIGNAL_THRESHOLD=.02
COSTS=(5,15,35)
MIN_EVENTS=24
MIN_ISSUERS=6


def _complete_xnys_event_window(filing:dt.date, preceding:dt.date,
                                following:list[dt.date])->bool:
    """Only actual consecutive exchange sessions count toward the event horizon.

    The filing DATE is excluded even if it was a market session, because
    the original SEC capture does not prove when on that date news arrived.
    """
    if not following:
        return False
    cal=xcals.get_calendar("XNYS")
    prior=[x.date() for x in cal.sessions_in_range(
        pd.Timestamp(filing-dt.timedelta(days=10)),pd.Timestamp(filing))
        if x.date()<filing]
    subsequent=[x.date() for x in cal.sessions_in_range(
        pd.Timestamp(filing),pd.Timestamp(following[-1]))
        if x.date()>filing]
    return bool(prior and preceding==prior[-1] and following==subsequent)



# A realized event is NOT the return on an investable fund: overlapping
# signals compete for the same cash. This descriptive simulation preserves
# the precommitted third-close entry and ten-session exit. It does not use
# future prices to choose which events qualify; fills at the exact close are
# optimistic, cash earns zero, and spread/impact beyond fixed fees are absent.
PORTFOLIO_MAX_NAMES=4
PORTFOLIO_MAX_NAME_FRACTION=.25


def _portfolio_path(events:list[dict], data:pd.DataFrame, cost_bps:int)->dict:
    """Retrospective, long-only, shared-cash event portfolio; no broker path.

    First-come (entry date, ticker, accession) allocation, 25% of NAV per
    issuer, four simultaneous positions, and exact entry/exit cost debits.
    SPY buy/hold uses the SAME entry/exit dates and both-sided fees.
    """
    if cost_bps not in COSTS:
        raise e1.SourceStop("Unregistered event portfolio transaction cost")
    if not events:
        return {
            "selected_events":0,"accepted_entries":0,"closed_exits":0,
            "capacity_skipped":0,"duplicate_issuer_skipped":0,
            "max_concurrent_names":0,"max_gross_fraction":0.0,
            "min_cash_fraction":None,"net_portfolio_return_pct":None,
            "net_spy_buy_hold_return_pct":None,
            "portfolio_minus_spy_net_percentage_points":None,
            "max_portfolio_drawdown_pct":None,
            "all_positions_flat_at_final_close":True,
        }
    by_date={}
    seen=set()
    dates={x.date() for x in data.index}
    for event in events:
        ticker=event["ticker"]
        accession=event["original_sec_accession"]
        entry=dt.date.fromisoformat(event["hypothetical_entry_third_close"])
        exit_day=dt.date.fromisoformat(event["hypothetical_exit_after_ten_sessions"])
        if (ticker not in data.columns or ticker=="SPY"
            or (ticker,accession) in seen or entry not in dates
            or exit_day not in dates or entry>=exit_day):
            raise e1.SourceStop("Invalid selected event portfolio schedule")
        seen.add((ticker,accession))
        by_date.setdefault(entry,[]).append((ticker,accession,exit_day))
    first=min(by_date)
    last=max(dt.date.fromisoformat(
        e["hypothetical_exit_after_ten_sessions"]) for e in events)
    market=data.loc[pd.Timestamp(first):pd.Timestamp(last)]
    if len(market)<2:
        raise e1.SourceStop("No complete event portfolio return horizon")
    fee=cost_bps/10_000
    cash=1.0
    holdings={}  # ticker -> (fractional shares, exit date)
    accepted=closed=capacity_skipped=duplicate_skipped=0
    max_names=0
    max_gross=0.0
    min_cash=1.0
    peak=1.0
    max_drawdown=0.0
    for stamp,row in market.iterrows():
        day=stamp.date()
        # EXIT first: released cash may fund a new signal at this close.
        for ticker,(qty,exit_day) in list(holdings.items()):
            if exit_day==day:
                cash+=qty*float(row[ticker])*(1-fee)
                del holdings[ticker]
                closed+=1
        nav_before=cash+sum(q*float(row[t]) for t,(q,_) in holdings.items())
        if nav_before<=0:
            raise e1.SourceStop("Event portfolio has nonpositive NAV")
        for ticker,accession,exit_day in sorted(by_date.get(day,[])):
            if ticker in holdings:
                duplicate_skipped+=1
                continue
            if len(holdings)>=PORTFOLIO_MAX_NAMES:
                capacity_skipped+=1
                continue
            budget=min(PORTFOLIO_MAX_NAME_FRACTION*nav_before,cash/(1+fee))
            if budget<=1e-10:
                capacity_skipped+=1
                continue
            qty=budget/float(row[ticker])
            cash-=budget*(1+fee)
            holdings[ticker]=(qty,exit_day)
            accepted+=1
        nav=cash+sum(q*float(row[t]) for t,(q,_) in holdings.items())
        if nav<=0 or cash < -1e-9:
            raise e1.SourceStop("Event portfolio violated no-margin budget")
        gross=sum(q*float(row[t]) for t,(q,_) in holdings.items())/nav
        max_gross=max(max_gross,gross)
        max_names=max(max_names,len(holdings))
        min_cash=min(min_cash,max(0.0,cash)/nav)
        peak=max(peak,nav)
        max_drawdown=max(max_drawdown,1-nav/peak)
    if holdings or accepted!=closed:
        raise e1.SourceStop("Unreconciled historical event positions")
    spy_start=float(data.loc[pd.Timestamp(first),"SPY"])
    spy_end=float(data.loc[pd.Timestamp(last),"SPY"])
    spy_final=(spy_end/spy_start)*(1-fee)/(1+fee)
    return {
        "selected_events":len(events),
        "accepted_entries":accepted,"closed_exits":closed,
        "capacity_skipped":capacity_skipped,
        "duplicate_issuer_skipped":duplicate_skipped,
        "max_concurrent_names":max_names,
        "max_gross_fraction":round(max_gross,6),
        "min_cash_fraction":round(min_cash,6),
        "first_hypothetical_entry":first.isoformat(),
        "last_hypothetical_exit":last.isoformat(),
        "net_portfolio_return_pct":round(100*(nav-1),5),
        "net_spy_buy_hold_return_pct":round(100*(spy_final-1),5),
        "portfolio_minus_spy_net_percentage_points":round(100*(nav-spy_final),5),
        "max_portfolio_drawdown_pct":round(-100*max_drawdown,5),
        "all_positions_flat_at_final_close":True,
    }


def event_study(sec_manifest:dict, submissions:dict, p4g_snapshot:dict, prices:pd.DataFrame)->dict:
    """Actual original SEC filing dates; strictly historical exploratory event horizons."""
    report=e1.evaluate(sec_manifest=sec_manifest,submissions=submissions,
                       p4g_snapshot=p4g_snapshot,prices=prices)
    data=p4g.validate_prices(prices)
    source_captured=e1.capture_time(sec_manifest["capture_timestamp_utc"],"original SEC")
    sessions=[i.date() for i in data.index]
    events=[]
    exclusions=defaultdict(int)
    for ticker in sorted(submissions):
        original=e1.filing_candidates(submissions[ticker],ticker,source_captured)
        for filing in original:
            date=e1.iso_date(filing["filed_date"],"filing")
            if not EARLIEST<=date<=LATEST:
                continue
            prior=[i for i,day in enumerate(sessions) if day<date]
            future=[i for i,day in enumerate(sessions) if day>date]
            if not prior:
                exclusions["NO_PRE_FILING_COMPLETE_PRICE"]+=1
                continue
            if len(future)<=EXIT_FOLLOWING_IDX:
                exclusions["INCOMPLETE_FUTURE_TEN_SESSION_HOLD"]+=1
                continue
            base=prior[-1]
            # A missing price row, extra holiday row or nonconsecutive NYSE
            # session cannot silently alter the two-day signal or ten-day hold.
            if not _complete_xnys_event_window(
                date,sessions[base],
                [sessions[i] for i in future[:EXIT_FOLLOWING_IDX+1]]):
                exclusions["NONCONSECUTIVE_XNYS_EVENT_WINDOW"]+=1
                continue
            second=future[N_FOLLOWING_TO_SIGNAL-1]
            entry=future[ENTER_FOLLOWING_IDX]
            exit_idx=future[EXIT_FOLLOWING_IDX]
            sec_t=data[ticker]
            spy=data[p4g.BENCHMARK]
            pre_move=float(sec_t.iloc[second]/sec_t.iloc[base]-1)
            spy_pre=float(spy.iloc[second]/spy.iloc[base]-1)
            reaction=pre_move-spy_pre
            stock_gross=float(sec_t.iloc[exit_idx]/sec_t.iloc[entry]-1)
            spy_gross=float(spy.iloc[exit_idx]/spy.iloc[entry]-1)
            qualified=reaction>=SIGNAL_THRESHOLD
            events.append({
                "ticker":ticker,
                "original_sec_accession":filing["accession"],
                "filing_date":date.isoformat(),
                "pre_filing_completed_close":sessions[base].isoformat(),
                "second_post_filing_close":sessions[second].isoformat(),
                "hypothetical_entry_third_close":sessions[entry].isoformat(),
                "hypothetical_exit_after_ten_sessions":sessions[exit_idx].isoformat(),
                "prior_two_session_reaction_stock_minus_spy_pct":round(100*reaction,5),
                "qualifies_positive_catalyst_signal":qualified,
                "ten_session_stock_gross_pct":round(100*stock_gross,5),
                "ten_session_spy_gross_pct":round(100*spy_gross,5),
                "net_spy_relative_percentage_points_by_one_way_cost_bps":{
                    str(bps):round(100*((1+stock_gross)*(1-bps/10000)**2-(1+spy_gross)),5)
                    for bps in COSTS
                },
                "event_was_confirmed_available_to_original_2025_buyer":False,
                "broker_order_notional_usd":0,
            })
    # Distinct original event acc numbers within each issuer only.
    if len(events)!=len({(r["ticker"],r["original_sec_accession"]) for r in events}):
        raise e1.SourceStop("Duplicate historical SEC 8-K accession counted.")
    selected=sorted((r for r in events if r["qualifies_positive_catalyst_signal"]),
                    key=lambda x:(x["hypothetical_entry_third_close"],x["ticker"],x["original_sec_accession"]))
    def summarize(cohort):
        result={}
        for bps in COSTS:
            key=str(bps)
            values=[x["net_spy_relative_percentage_points_by_one_way_cost_bps"][key]
                    for x in cohort]
            result[key]={
                "event_count":len(values),
                "mean_net_excess_percentage_points":None if not values else round(mean(values),5),
                "median_net_excess_percentage_points":None if not values else round(median(values),5),
                "min_net_excess_percentage_points":None if not values else round(min(values),5),
                "positive_net_excess_event_fraction":None if not values else round(sum(v>0 for v in values)/len(values),5),
            }
        return result

    # Post-hoc descriptive controls, NOT an untouched holdout or a
    # causal estimate. All groups use identical entry/exit dates and fees.
    summary=summarize(selected)
    unselected=[r for r in events if not r["qualifies_positive_catalyst_signal"]]
    below=summarize(unselected)
    unconditional=summarize(events)
    controls={}
    for bps in COSTS:
        key=str(bps)
        signal_mean=summary[key]["mean_net_excess_percentage_points"]
        below_mean=below[key]["mean_net_excess_percentage_points"]
        all_mean=unconditional[key]["mean_net_excess_percentage_points"]
        controls[key]={
            "below_threshold_filing_control":below[key],
            "all_filing_unconditional_control":unconditional[key],
            "selected_minus_below_threshold_mean_pp":None if
                signal_mean is None or below_mean is None else
                round(signal_mean-below_mean,5),
            "selected_minus_all_filing_mean_pp":None if
                signal_mean is None or all_mean is None else
                round(signal_mean-all_mean,5),
        }
    v35=[r["net_spy_relative_percentage_points_by_one_way_cost_bps"]["35"] for r in selected]
    k=len(v35)//2
    stable_halves=(len(v35)>=2 and k>0 and mean(v35[:k])>0 and mean(v35[k:])>0)
    issuer_count=len({r["ticker"] for r in selected})
    minimal_coverage=(
        len(selected)>=MIN_EVENTS and issuer_count>=MIN_ISSUERS
        and summary["35"]["median_net_excess_percentage_points"] is not None
        and summary["35"]["median_net_excess_percentage_points"]>0
        and summary["35"]["positive_net_excess_event_fraction"]>.5
        and stable_halves
    )
    return {
        "schema":SCHEMA,
        "status":"RETROSPECTIVE_SURVIVOR_BIASED_FEASIBILITY_NOT_PROVEN_ALPHA",
        "source_frozen_sec_acquisition":sec_manifest["capture_timestamp_utc"],
        "source_frozen_prices_acquisition":p4g_snapshot["source_acquired_at_utc"],
        "source_price_sha256":report["source_price_sha256"],
        "date_window":{"earliest":EARLIEST.isoformat(),"latest":LATEST.isoformat()},
        "cohort_eight_known_2026_survivors":True,
        "original_archived_2025_price_and_sec_vintages_absent":True,
        "no_historical_point_in_time_quality_scores":True,
        "event_reaction_minimum_spy_relative_pct":100*SIGNAL_THRESHOLD,
        "simulated_entry_session_after_filing":ENTER_FOLLOWING_IDX+1,
        "simulated_ten_session_holding_period":TEN_SESSION_HOLD,
        "intraday_executable_entry_price_verified":False,
        "independent_analyst_earnings_surprise_present":False,
        "individual_original_sec_earnings_events_checked":len(events),
        "events_excluded_lack_coverage":dict(sorted(exclusions.items())),
        "positive_reaction_events":len(selected),
        "positive_reaction_issuers":issuer_count,
        "results_by_one_way_transaction_cost_bps":summary,
        "matched_event_controls_by_cost_bps":controls,
        "shared_cash_portfolio_by_cost_bps":{
            str(bps):_portfolio_path(selected,data,bps) for bps in COSTS
        },
        "portfolio_uses_first_come_25pct_max_four_names":True,
        "portfolio_is_retrospective_close_fill_optimistic_not_alpha":True,
        "controls_added_post_hoc_not_independent_holdout":True,
        "real_xnys_event_horizons_verified":True,
        "minimum_research_coverage":MIN_EVENTS,
        "minimal_candidate_evidence_check_passed":minimal_coverage,
        "economic_status":"INCONCLUSIVE_NEEDS_INDEPENDENT_EVIDENCE" if minimal_coverage else "REJECT_FOR_LIVE_TOO_WEAK_OR_INSUFFICIENT",
        "measured_real_money_live_returns":False,
        "event_study_is_not_portfolio_cagr_or_sharpe":True,
        "all_qualified_event_observations":selected,
        "broker_orders":0,
        "old_live_positions_sold":False,
        "operator_authorized_liquidation":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sec-original-directory",type=Path,required=True)
    p.add_argument("--p4g-original-report",type=Path,required=True)
    p.add_argument("--p4g-original-prices",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    m,s=e1.original_sec_sources(args.sec_original_directory)
    r,data=e1.original_price_source(args.p4g_original_report,args.p4g_original_prices)
    result=event_study(m,s,r,data)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("V6-E2 reviewed original Item 2.02 filings:",result["individual_original_sec_earnings_events_checked"])
    print("Qualifying positive reaction events:",result["positive_reaction_events"])
    print("Covered selected issuers:",result["positive_reaction_issuers"])
    print("Full-horizon filing controls:",result["matched_event_controls_by_cost_bps"]["15"]["all_filing_unconditional_control"]["event_count"])
    print("Non-signal filing controls:",result["matched_event_controls_by_cost_bps"]["15"]["below_threshold_filing_control"]["event_count"])
    for bps,m in result["results_by_one_way_transaction_cost_bps"].items():
        print(bps,"bps/side event excess pct-points: median",m["median_net_excess_percentage_points"],
              "mean",m["mean_net_excess_percentage_points"],"hit share",m["positive_net_excess_event_fraction"])
    for bps,portfolio in result["shared_cash_portfolio_by_cost_bps"].items():
        print("Shared-cash portfolio",bps,"bps/side accepted",portfolio["accepted_entries"],
              "net return pct",portfolio["net_portfolio_return_pct"],
              "net SPY pct",portfolio["net_spy_buy_hold_return_pct"],
              "capacity skipped",portfolio["capacity_skipped"])
    print("Decision:",result["economic_status"])
    print("Retrospective survivor-biased event statistics; NO REAL TRADES.")


if __name__=="__main__":
    main()

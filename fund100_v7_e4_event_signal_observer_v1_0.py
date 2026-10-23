"""V7-E4: same-vintage SEC event + T+1 price observation only, never orders.

This models an original stock-vs-SPY *past* two-session reaction. It does
not backdate the 2026-10-22 capture, claim analyst surprises, or produce fills.
"""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

import fund100_stock_quality_momentum_p4g_v1_0 as p4g
import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_v7_e4_sec_event_capture_v1_0 as feed

SCHEMA="FUND100_V7_E4_CONCURRENT_SEC_EARNINGS_REACTION_OBSERVER_V1"
FREEZE=date(2026,10,15)
REACTION_MIN=.02
MAX_SCORE_AGE_DAYS=90

class SignalStop(ValueError):
    pass


def verify_post_filing_sessions(filed: date, last: date, observed: list[date]) -> None:
    """Verify the SEC reaction horizon against actual XNYS sessions.

    A missing vendor row must not turn three real sessions into an apparent
    two-session post-earnings reaction. Exchange holidays and half-days are
    handled by the exchange calendar rather than weekday arithmetic.
    """
    try:
        expected = [
            session.date()
            for session in xcals.get_calendar("XNYS").sessions_in_range(
                pd.Timestamp(filed), pd.Timestamp(last)
            )
            if session.date() > filed
        ]
    except (ValueError, TypeError, IndexError) as exc:
        raise SignalStop("Cannot verify XNYS post-filing market sessions") from exc
    if observed != expected:
        raise SignalStop("Missing, extra or unordered XNYS post-filing sessions")


def evaluate(source:dict, price_report:dict, prices) -> dict:
    if (source.get("schema")!=feed.SCHEMA
        or source.get("all_frozen_issuers_acquired") is not True
        or source.get("broker_orders")!=0
        or source.get("trading_authorized") is not False):
        raise SignalStop("SEC source bundle not a verified original capture")
    data=p4g.validate_prices(prices)
    if (price_report.get("schema")!=p4g.SCHEMA
        or price_report.get("asof_completed_session")!=data.index[-1].date().isoformat()
        or price_report.get("trading_authorized") is not False
        or price_report.get("broker_orders")!=0):
        raise SignalStop("invalid completed stock price observation")
    sec_finished=feed._timestamp(source["capture_complete_utc"])
    price_finished=feed._timestamp(price_report["source_acquired_at_utc"])
    joined=max(sec_finished,price_finished)
    last=data.index[-1].date()
    if joined.date()<=last or joined.date()>last+timedelta(days=5):
        raise SignalStop("price observations not acquired after latest completed session")
    sessions=[d.date() for d in data.index]
    score_age=(joined.date()-FREEZE).days
    results=[]
    counts=Counter()
    observed=source.get("observed_filings_not_necessarily_new_today")
    if not isinstance(observed,list):
        raise SignalStop("missing original SEC observations")
    for event in observed:
        ticker=event.get("ticker")
        if ticker not in p4g.FROZEN_P4E_SCORES:
            raise SignalStop("unregistered issuer")
        acc=event.get("original_sec_accession")
        filed=date.fromisoformat(event["filing_date"])
        event_seen=feed._timestamp(event["sec_submissions_observed_at_utc"])
        if (event_seen>sec_finished or filed>event_seen.date()
            or event.get("orders_authorized") is not False
            or event.get("issuer_event_type")!="8-K ITEM 2.02"):
            raise SignalStop("SEC event source identity/time invalid")
        subsequent=[d for d in sessions if d>filed]
        prior=[d for d in sessions if d<filed]
        # The original pre-entry reaction also needs real session continuity.
        # E5 independently verifies the later entry/exit sessions.
        if (FREEZE<=filed<=last and score_age<=MAX_SCORE_AGE_DAYS
            and p4g.FROZEN_P4E_SCORES[ticker] is not None):
            verify_post_filing_sessions(filed,last,subsequent)
        relative=None
        if score_age>MAX_SCORE_AGE_DAYS:
            state="STALE_ORIGINAL_FROZEN_QUALITY_REQUIRES_REFRESH"
        elif p4g.FROZEN_P4E_SCORES[ticker] is None:
            state="NO_FROZEN_QUALITY_SCORE"
        elif filed<FREEZE:
            state="EARLIER_THAN_QUALITY_FREEZE"
        elif not prior or len(subsequent)<2:
            state="NOT_YET_TWO_COMPLETED_POST_EVENT_SESSIONS"
        elif len(subsequent)>2:
            state="SOURCE_ACQUIRED_AFTER_SIGNAL_SESSION_NO_BACKDATING"
        elif joined.date()!=price_finished.date() or joined.hour>=12 or (joined.date()-last).days>4:
            state="RESEARCH_CAPTURE_TOO_LATE_FOR_NEXT_SESSION_MODEL"
        else:
            # Source price last session is the second post-event close.
            base=prior[-1]
            relative=float(data.loc[last.isoformat(),ticker]/data.loc[base.isoformat(),ticker]-1
                           -(data.loc[last.isoformat(),"SPY"]/data.loc[base.isoformat(),"SPY"]-1))
            state=("OBSERVED_REACTION_OVER_THRESHOLD_NOT_FORWARD_ALPHA"
                   if relative>=REACTION_MIN else "OBSERVED_REACTION_BELOW_THRESHOLD")
        counts[state]+=1
        results.append({
            "ticker":ticker, "original_sec_accession":acc,
            "original_filing_date":filed.isoformat(),
            "second_post_filing_completed_session":subsequent[1].isoformat()
                if len(subsequent)>=2 else None,
            "signal_source_recorded_utc":joined.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status":state,
            "pre_entry_reaction_vs_spy":None if relative is None else round(relative,9),
            "broker_order_notional_usd":0,"orders_authorized":False
        })
    return {
        "schema":SCHEMA,
        "status":"DATED_T_PLUS_ONE_RESEARCH_SIGNAL_OBSERVER_NO_TRADE",
        "source_SEC_capture_completed_utc":source["capture_complete_utc"],
        "price_capture_utc":price_report["source_acquired_at_utc"],
        "price_asof_completed_session":last.isoformat(),
        "price_vintage_canonical_csv_sha256":price_report.get("canonical_price_csv_sha256"),
        "issuer_source_count":source["source_count"],
        "events_reviewed_not_necessarily_new":len(results),
        "observation_status_counts":dict(sorted(counts.items())),
        "events":results,
        "next_market_session_and_fill_NOT_guaranteed":True,
        "price_vendor_adjustments_independently_verified":False,
        "forward_post_entry_returns_measured":False,
        "independent_analyst_earnings_surprises_available":False,
        "statistical_alpha_proven":False,"paper_authorized":False,
        "live_authorized":False,"trading_authorized":False,"broker_orders":0
    }

def main() -> None:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--sec-dir",type=Path,required=True)
    p.add_argument("--price-json",type=Path,required=True)
    p.add_argument("--price-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    source=feed.verify(args.sec_dir)
    snap,prices,_=p4h.read_snapshot(args.price_json,args.price_csv)
    doc=evaluate(source,snap,prices)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    print("V7-E4 same-day source/price research event states",doc["observation_status_counts"])
    print("Zero evidence of investment alpha or real fills; no orders.")

if __name__=="__main__":
    main()

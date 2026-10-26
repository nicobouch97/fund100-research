"""V7-M1: independently dated, frozen 24-stock momentum forward comparator.

Selection is original source-run 40368883430, captured BEFORE proposed
27 October 2026 first eligible NYSE entry close. Price histories prior
to that selected source CANNOT be used to change or optimise the picks.

Twenty-one completed NYSE close-to-close intervals, equal-weight six
selected stocks vs passive SPY, both 95%-gross with equal-side execution
friction. This is a one-shot prospective *cohort test* on survivor-selected
24 stocks, not independent 2017 investability, statistical alpha proof,
live execution, a licensed market feed or brokerage permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l

SCHEMA="FUND100_V7_M1_ORIGINAL_24_ISSUER_MOMENTUM_FORWARD_21_SESSIONS_V1"
ORIGINAL_RUN_ID=40368883430
ORIGINAL_ARTIFACT_ID=12670273944
ORIGINAL_LAST_SESSION="2026-10-23"
SOURCE_ACQUISITION_DATE="2026-10-26"
ENTRY_SESSION="2026-10-27"
HOLD_SESSIONS=21
COST_BPS=(5,15,35)
INITIAL_CASH=5.
INITIAL_NAV=100.
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class ForwardStop(ValueError):pass

def _timestamp(value):
    if type(value) is not str:
        raise ForwardStop("Unverifiable original vendor source receipt")
    try:
        instant=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise ForwardStop("Noncanonical source receipt") from exc
    if instant.strftime("%Y-%m-%dT%H:%M:%SZ")!=value:
        raise ForwardStop("Noncanonical source receipt")
    return instant

def _calendar(first,last):
    try:
        return xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp(first),pd.Timestamp(last)
        ).tz_localize(None).normalize()
    except Exception as exc:
        raise ForwardStop("NYSE session calendar unavailable") from exc

def _original(original:dict, original_prices:pd.DataFrame)->list[str]:
    if (not isinstance(original,dict)
        or original.get("schema")!=p4l.SCHEMA
        or original.get("status")!="BROAD_CONTEMPORARY_MOMENTUM_RESEARCH_NOT_ALPHA"
        or original.get("asof_completed_session")!=ORIGINAL_LAST_SESSION
        or original.get("contemporary_cohort_start")!="2026-10-24"
        or original.get("cohort_size")!=24
        or original.get("broker_orders")!=0
        or original.get("trading_authorized") is not False
        or original.get("paper_authorized") is not False
        or original.get("live_authorized") is not False
        or original.get("post_selection_forward_return_observations")!=0
        or original.get("universe_historically_survivorship_safe") is not False):
        raise ForwardStop("Pinned prospectively frozen 24-stock source invalid")
    acquired=_timestamp(original.get("source_acquired_at_utc"))
    if acquired.date().isoformat()!=SOURCE_ACQUISITION_DATE:
        raise ForwardStop("Wrong historical source vintage")
    if not acquired.date()<pd.Timestamp(ENTRY_SESSION).date():
        raise ForwardStop("Selections observed after proposed entry")
    try:
        panel=p4l.validate_prices(original_prices)
    except p4l.BroadStockStop as exc:
        raise ForwardStop("Original source 24-issuer closes invalid") from exc
    if (panel.index[-1].date().isoformat()!=ORIGINAL_LAST_SESSION
        or sha256(p4l.canonical_csv(panel).encode("utf-8")).hexdigest()
        !=original.get("canonical_price_csv_sha256")):
        raise ForwardStop("Original source bytes/date mismatch")
    # Rerun the ORIGINAL source algorithm, not a recomputed selection on
    # future market closes. 2026 market-vintage biases remain documented.
    from_source=p4l.evaluate(panel,
        acquired_at_utc=original["source_acquired_at_utc"],
        provider_reference=original["source_reference"])
    if from_source["momentum_only_watchlist"]!=original.get("momentum_only_watchlist"):
        raise ForwardStop("Original ranked selection changed or revised")
    names=original["momentum_only_watchlist"]
    if (type(names) is not list or len(names)<1 or len(names)>p4l.MAX_NAMES
        or len(set(names))!=len(names)
        or any(x not in p4l.SECTORS for x in names)):
        raise ForwardStop("Original frozen momentum selection unavailable")
    return names

def evaluate(*,original_manifest:dict,original_prices:pd.DataFrame,
             later_prices:pd.DataFrame,captured_utc:str):
    selected=_original(original_manifest,original_prices)
    capture=_timestamp(captured_utc)
    try:
        data=p4l.validate_prices(later_prices)
    except p4l.BroadStockStop as exc:
        raise ForwardStop("Later original public stock close history invalid") from exc
    last=data.index[-1].date().isoformat()
    if (capture.date()<=data.index[-1].date()
        or (capture.date()-data.index[-1].date()).days>5):
        raise ForwardStop("Future-dated, same-date or stale later vendor close")
    if capture<=_timestamp(original_manifest["source_acquired_at_utc"]):
        raise ForwardStop("Later market source is not independent in time")
    if data.index[0]>original_prices.index[0] or data.index[0]>pd.Timestamp(ORIGINAL_LAST_SESSION):
        raise ForwardStop("Later source loses essential original lookback")
    # Do not fabricate missing NYSE sessions even on an incomplete horizon.
    after=data.index[data.index>pd.Timestamp(ORIGINAL_LAST_SESSION)]
    if len(after) and not after.equals(_calendar("2026-10-26",last)):
        raise ForwardStop("Gap, extra source price date or missing XNYS closes")
    target=_calendar(ENTRY_SESSION,"2026-12-15")
    if len(target)<=HOLD_SESSIONS or target[0]!=pd.Timestamp(ENTRY_SESSION):
        raise ForwardStop("Exchange calendar cannot establish frozen horizon")
    final=target[HOLD_SESSIONS]
    finished=last>=final.date().isoformat()
    if last<ENTRY_SESSION:
        stage="WAITING_FOR_FROZEN_ENTRY_CLOSE"
        periods=0
        provisional=None
        by_cost={}
    else:
        if pd.Timestamp(ENTRY_SESSION) not in data.index:
            raise ForwardStop("Actual predeclared entry close missing")
        entry=data.loc[ENTRY_SESSION]
        exit_date=final if finished else data.index[-1]
        end=data.loc[exit_date]
        interval=data.loc[ENTRY_SESSION:exit_date]
        periods=len(interval)-1
        if periods>HOLD_SESSIONS:
            # Explicitly truncate to the 21-session exit date.
            interval=data.loc[ENTRY_SESSION:final]
            periods=HOLD_SESSIONS
        stock_growth=np.mean([float(end[s]/entry[s]) for s in selected])
        spy_growth=float(end[p4l.BENCHMARK]/entry[p4l.BENCHMARK])
        by_cost={}
        for bps in COST_BPS:
            fee=bps/10000.
            risky=95./(1+fee)
            stock_final=INITIAL_CASH+risky*stock_growth*(1-fee)
            passive_final=INITIAL_CASH+risky*spy_growth*(1-fee)
            by_cost[str(bps)]={
                "equal_95pct_initial_cash_and_round_trip_costs":True,
                "theoretical_stock_terminal_after_exit_fee_usd":round(stock_final,8),
                "theoretical_spy_terminal_after_exit_fee_usd":round(passive_final,8),
                "stock_minus_spy_net_percentage_points":round(stock_final-passive_final,8),
                "entry_purchase_cost_usd":round(95.-risky,8),
                "final_risky_exit_is_modeled_only":True,
            }
        stage=("COMPLETED_FROZEN_21_SESSION_FORWARD_MARK_NOT_ALPHA"
               if finished else "INTERIM_FOR_INFORMATION_NOT_QUALIFICATION")
        provisional=by_cost["15"]["stock_minus_spy_net_percentage_points"]
    return {
        "schema":SCHEMA,
        "status":stage,
        "original_fixed_run_id":ORIGINAL_RUN_ID,
        "original_fixed_artifact_id":ORIGINAL_ARTIFACT_ID,
        "original_24issuer_selection_price_sha256":
            original_manifest["canonical_price_csv_sha256"],
        "original_source_observed_utc":original_manifest["source_acquired_at_utc"],
        "original_pretrade_selection":selected,
        "original_selection_size":len(selected),
        "frozen_entry_close_session":ENTRY_SESSION,
        "fixed_exit_close_session":final.date().isoformat(),
        "completed_price_session":last,
        "later_price_observed_utc":captured_utc,
        "observed_holding_intervals":periods,
        "required_holding_intervals":HOLD_SESSIONS,
        "final_result_completed":finished if last>=ENTRY_SESSION else False,
        "interim_excess_at_15bps_pp_not_alpha":provisional if not finished else None,
        "costed_95pct_stocks_versus_95pct_spy":by_cost,
        "not_a_survivorship_safe_universe":True,
        "only_one_contemporary_frozen_selection":True,
        "initial_equal_weight_sector_pilot_single_symbol_leq_50pct":
            bool(len(selected)>=2),
        "stock_total_returns_or_tradable_fills_verified":False,
        "historical_prices_revisable_and_current_marks_not_original_entry_fills":True,
        "signal_predictive_alpha_proven":False,
        "eligible_to_rank_real_live_orders":False,
        "current_live_principal_ceiling_usd":"130.30",
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,"trading_authorized":LIVE_AUTHORIZED,
    }

def main():
    import argparse
    args=argparse.ArgumentParser()
    args.add_argument("--original-dir",type=Path,required=True)
    args.add_argument("--output-dir",type=Path,required=True)
    a=args.parse_args()
    original=json.loads((a.original_dir/"original-price-manifest.json").read_text())
    original_prices=p4l.validate_prices(pd.read_csv(
        a.original_dir/"original-24issuer-prices.csv",parse_dates=["Date"]
    ).set_index("Date"))
    new_prices=p4l.public_prices()
    acquired=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=evaluate(original_manifest=original,original_prices=original_prices,
                    later_prices=new_prices,captured_utc=acquired)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/"frozen-forward-stocks-versus-SPY.json").write_text(
        json.dumps(result,sort_keys=True,indent=2)+"\n")
    (a.output_dir/"new-price-manifest.csv").write_text(
        p4l.canonical_csv(new_prices),encoding="utf-8")
    print("Original 24-stock selection pinned to",ORIGINAL_RUN_ID)
    print("Market-source through",result["completed_price_session"])
    print("Causal 21-session forward stage:",result["status"])
    print("No broker, no alpha proof, no permission to trade.")
if __name__=="__main__":main()

"""V7 M3: frozen initial 27 Oct stock entry receipt never silently rewritten.

A 2026 Yahoo adjusted-history vendor may restate an earlier forward entry
price after dividends, splits or revisions. Comparing every later exit bar
to a silently revised "27 October" close misrepresents a prospective
experiment. This verifier locks the first source record to a distinct
immutable successful GitHub Actions artifact *before any later exit
sessions are admitted*. If the original 27 October adjusted series
changes at later acquisition, HOLD; do not synthesize stock returns.

Pure public-data diagnostics; no API, broker, credentials, order authority.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as m1

SCHEMA="FUND100_V7_M3_IMMUTABLE_FIRST_ENTRY_VENDOR_VINTAGE_V1"
FIRST_ENTRY_ARTIFACT_NAME="fund100-v7-m3-first-entry-20261027"
ORIGINAL_ENTRY_SESSION=m1.ENTRY_SESSION
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class EntryAnchorStop(ValueError):pass

def _canonical_prices(raw:pd.DataFrame)->pd.DataFrame:
    try:
        return p4l.validate_prices(raw)
    except p4l.BroadStockStop as e:
        raise EntryAnchorStop("Unverifiable original price schema") from e

def entry_revision_diagnostic(*,initial_prices:pd.DataFrame,
                              subsequent_prices:pd.DataFrame)->dict:
    """Describe blocked adjusted-close drift; never qualify revised returns.

    Vendor auto-adjusted prices can change after corporate actions or data
    corrections. This does not infer the cause or reconstruct total returns.
    """
    original=_canonical_prices(initial_prices)
    later=_canonical_prices(subsequent_prices)
    date=pd.Timestamp(ORIGINAL_ENTRY_SESSION)
    if (original.index[-1]!=date or date not in later.index
        or set(original.columns)!=set(later.columns)):
        raise EntryAnchorStop("Cannot diagnose nonmatching entry price panels")
    changes=[]
    for ticker in sorted(original.columns):
        anchor=float(original.loc[date,ticker])
        current=float(later.loc[date,ticker])
        if format(anchor,".10f")!=format(current,".10f"):
            changes.append({
                "symbol":ticker,
                "entry_anchor_adjusted_close":round(anchor,10),
                "later_vintage_entry_adjusted_close":round(current,10),
                "relative_change_bps":round(10000*(current/anchor-1),8),
            })
    return {
        "schema":"FUND100_V7_M3_BLOCKED_ENTRY_VENDOR_REVISION_DIAGNOSTIC_V1",
        "status":"BLOCKED_REVISED_ENTRY_VENDOR_VINTAGE_RESEARCH_ONLY",
        "entry_session":ORIGINAL_ENTRY_SESSION,
        "changed_entry_symbols":len(changes),
        "total_compared_symbols":len(original.columns),
        "changes":changes,
        "cannot_distinguish_corporate_actions_from_vendor_corrections":True,
        "not_a_return_or_alpha_estimate":True,
        "do_not_replace_original_entry_anchor":True,
        "no_trading_authority":True,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
    }

def _proof(r:dict,required_stage:str):
    if (type(r) is not dict or r.get("schema")!=m1.SCHEMA
        or r.get("status")!=required_stage
        or r.get("original_fixed_run_id")!=m1.ORIGINAL_RUN_ID
        or r.get("original_fixed_artifact_id")!=m1.ORIGINAL_ARTIFACT_ID
        or r.get("frozen_entry_close_session")!=ORIGINAL_ENTRY_SESSION
        or r.get("required_holding_intervals")!=m1.HOLD_SESSIONS
        or r.get("signal_predictive_alpha_proven") is not False
        or r.get("trading_authorized") is not False
        or r.get("eligible_to_rank_real_live_orders") is not False
        or r.get("broker_gets")!=0 or r.get("broker_posts")!=0
        or r.get("broker_orders")!=0):
        raise EntryAnchorStop("Unauthenticated M1 source provenance or trading boundary")
    source=r.get("original_later_source_completed_nyse_close_evidence")
    if (type(source) is not dict
        or source.get("captured_after_exchange_close_plus_buffer") is not True
        or source.get("post_close_source_buffer_minutes")!=90):
        raise EntryAnchorStop("Missing independent post-close source proof")
    # A Boolean in a saved report is not evidence of a completed session.
    # Independently replay the original NYSE clock from its source receipt.
    try:
        expected=m1._source_close_qualified(
            last_session=r["completed_price_session"],
            capture=m1._timestamp(r["later_price_observed_utc"]))
    except (KeyError,TypeError,ValueError) as exc:
        raise EntryAnchorStop("Unverifiable original exchange-close receipt") from exc
    if source!=expected:
        raise EntryAnchorStop("Saved exchange-close proof disagrees with its timestamp")
    return source

def verify(*,initial_report:dict,initial_prices:pd.DataFrame,
           subsequent_report:dict,subsequent_prices:pd.DataFrame):
    initial=_proof(initial_report,"ENTRY_CLOSE_OBSERVED_AWAITING_FIRST_FUTURE_MARK")
    if (initial_report.get("observed_holding_intervals")!=0
        or initial_report.get("completed_price_session")!=ORIGINAL_ENTRY_SESSION
        or initial.get("last_vendor_session")!=ORIGINAL_ENTRY_SESSION
        or initial_report.get("costed_95pct_stocks_versus_95pct_spy")!={}
        or initial_report.get("final_result_completed") is not False):
        raise EntryAnchorStop("Anchor is not first entry-only completed NYSE close")
    stage=subsequent_report.get("status")
    if stage not in (
        "INTERIM_FOR_INFORMATION_NOT_QUALIFICATION",
        "COMPLETED_FROZEN_21_SESSION_FORWARD_MARK_NOT_ALPHA"):
        raise EntryAnchorStop("Later return horizon is not actually observed")
    subsequent=_proof(subsequent_report,stage)
    if (not 1<=subsequent_report.get("observed_holding_intervals",0)<=m1.HOLD_SESSIONS
        or subsequent_report.get("completed_price_session")<=ORIGINAL_ENTRY_SESSION
        or subsequent.get("last_vendor_session")!=
           subsequent_report.get("completed_price_session")
        or initial_report.get("original_24issuer_selection_price_sha256")!=
           subsequent_report.get("original_24issuer_selection_price_sha256")
        or initial_report.get("original_pretrade_selection")!=
           subsequent_report.get("original_pretrade_selection")):
        raise EntryAnchorStop("Later source changes original selection or duration")
    original=_canonical_prices(initial_prices)
    later=_canonical_prices(subsequent_prices)
    date=pd.Timestamp(ORIGINAL_ENTRY_SESSION)
    if (original.index[-1]!=date or date not in later.index
        or original.index[0]!=later.index[0]
        or subsequent_report["completed_price_session"]!=
           later.index[-1].date().isoformat()):
        raise EntryAnchorStop("Anchor price cutoff or later market session missing")
    # The zero lookahead decision demands the very SAME originally
    # published 26 share/benchmark prices on model entry day.
    # P4L validates full input histories; compare the selected day's
    # strictly numeric values at the original 10-decimal CSV precision.
    first=original.loc[date]
    current=later.loc[date]
    modified=[ticker for ticker in first.index if
              format(float(first[ticker]),".10f")!=
              format(float(current[ticker]),".10f")]
    if modified:
        # Do not disclose ticker identities or financially sensitive source
        # relationships in a rejected audit without authenticated account
        # context. Caller keeps original pinned source and must HOLD.
        raise EntryAnchorStop("Previously observed entry close was vendor-revised")
    # The archived report and CSV are a single economic observation.
    # Recalculate its original 21-session chronology and all primary/sector
    # after-cost returns from the actual supplied prices. A report from a
    # different price vintage must never inherit a valid entry-price pin.
    try:
        sessions=m1._calendar("2026-10-26",later.index[-1].date().isoformat())
        if not later.index[later.index>pd.Timestamp(m1.ORIGINAL_LAST_SESSION)].equals(sessions):
            raise EntryAnchorStop("Missing or extra later NYSE price session")
        horizon=m1._calendar(ORIGINAL_ENTRY_SESSION,"2026-12-15")
        final=horizon[m1.HOLD_SESSIONS]
        finished=later.index[-1]>=final
        exit_day=final if finished else later.index[-1]
        periods=len(m1._calendar(ORIGINAL_ENTRY_SESSION,exit_day))-1
        expected_stage=("COMPLETED_FROZEN_21_SESSION_FORWARD_MARK_NOT_ALPHA"
                        if finished else "INTERIM_FOR_INFORMATION_NOT_QUALIFICATION")
        if (periods!=subsequent_report["observed_holding_intervals"]
            or subsequent_report["status"]!=expected_stage
            or subsequent_report.get("fixed_exit_close_session")!=final.date().isoformat()
            or subsequent_report.get("final_result_completed") is not finished):
            raise EntryAnchorStop("Reported return horizon does not match NYSE sessions")
        selected=subsequent_report["original_pretrade_selection"]
        if (type(selected) is not list or not selected
            or len(set(selected))!=len(selected)
            or any(t not in p4l.SECTORS for t in selected)):
            raise EntryAnchorStop("Unverifiable selected issuer weights")
        entry=later.loc[date]
        exit_prices=later.loc[exit_day]
        stock_growth=sum(float(exit_prices[t]/entry[t]) for t in selected)/len(selected)
        spy_growth=float(exit_prices[p4l.BENCHMARK]/entry[p4l.BENCHMARK])
        control=m1._frozen_sector_control(selected)
        sector_growth=sum(w*float(exit_prices[t]/entry[t]) for t,w in control.items())
        if subsequent_report.get("secondary_frozen_sector_control_weights")!={
                t:round(w,12) for t,w in control.items()}:
            raise EntryAnchorStop("Original sector weights changed after entry")
        results=subsequent_report.get("costed_95pct_stocks_versus_95pct_spy")
        if type(results) is not dict or set(results)!={str(b) for b in m1.COST_BPS}:
            raise EntryAnchorStop("Missing predeclared transaction-cost scenarios")
        for bps in m1.COST_BPS:
            fee=bps/10000.
            risky=(m1.INITIAL_NAV-m1.INITIAL_CASH)/(1+fee)
            stock=round(m1.INITIAL_CASH+risky*stock_growth*(1-fee),8)
            spy=round(m1.INITIAL_CASH+risky*spy_growth*(1-fee),8)
            sector=round(m1.INITIAL_CASH+risky*sector_growth*(1-fee),8)
            row=results[str(bps)]
            control_row=row.get("secondary_same_sector_original_cohort",{})
            if (row.get("theoretical_stock_terminal_after_exit_fee_usd")!=stock
                or row.get("theoretical_spy_terminal_after_exit_fee_usd")!=spy
                or row.get("stock_minus_spy_net_percentage_points")!=round(
                    (m1.INITIAL_NAV-m1.INITIAL_CASH)/(1+fee)
                    *(stock_growth-spy_growth)*(1-fee),8)
                or control_row.get("sector_control_terminal_after_exit_fee_usd")!=sector
                or control_row.get("selected_minus_same_sector_net_percentage_points")!=round(
                    risky*(stock_growth-sector_growth)*(1-fee),8)):
                raise EntryAnchorStop("Reported after-cost return disagrees with source prices")
    except (KeyError,TypeError,IndexError,ValueError) as exc:
        if isinstance(exc,EntryAnchorStop):
            raise
        raise EntryAnchorStop("Cannot independently reconcile source to returns") from exc
    first_sha=sha256(("".join(
        f"{k},{float(first[k]):.10f}\n" for k in sorted(first.index)
        )).encode("ascii")).hexdigest()
    return {
        "schema":SCHEMA,
        "status":"PINNED_2026_10_27_FIRST_ENTRY_SOURCE_STABLE_RESEARCH_ONLY",
        "actual_anchor_price_vintage_sha256":first_sha,
        "anchor_captured_utc":initial_report["later_price_observed_utc"],
        "future_capture_utc":subsequent_report["later_price_observed_utc"],
        "confirmed_frozen_preentry_stock_selection":True,
        "entry_date_price_symbols_compared":len(first.index),
        "anchor_source_stage_before_any_exit":"ENTRY_CLOSE_OBSERVED_AWAITING_FIRST_FUTURE_MARK",
        "checked_later_complete_intervals":subsequent_report["observed_holding_intervals"],
        "independently_recomputed_primary_and_sector_costed_returns":True,
        "verified_original_exchange_close_receipts":True,
        "source_prices_are_vendor_adjusted_not_executable_fills":True,
        "no_alpha_established":True,
        "no_automatic_cashflow_or_corporate_action_repairs":True,
        "original_live_ceiling_usd":"130.30",
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,
    }

def _csv(path:Path):
    return _canonical_prices(pd.read_csv(path,parse_dates=["Date"]).set_index("Date"))

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--first-entry-dir",type=Path,required=True)
    p.add_argument("--latest-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    initial_prices=_csv(a.first_entry_dir/"new-price-manifest.csv")
    subsequent_prices=_csv(a.latest_dir/"new-price-manifest.csv")
    try:
        result=verify(
            initial_report=json.loads((a.first_entry_dir/
                "frozen-forward-stocks-versus-SPY.json").read_text()),
            initial_prices=initial_prices,
            subsequent_report=json.loads((a.latest_dir/
                "frozen-forward-stocks-versus-SPY.json").read_text()),
            subsequent_prices=subsequent_prices)
    except EntryAnchorStop as exc:
        if str(exc)=="Previously observed entry close was vendor-revised":
            # Persist forensic evidence before failing closed. Never replace
            # the original immutable entry vintage or claim interim alpha.
            diagnostic=entry_revision_diagnostic(
                initial_prices=initial_prices,subsequent_prices=subsequent_prices)
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(json.dumps(
                diagnostic,sort_keys=True,indent=2)+"\n")
            print("Blocked revised entry price vintage; forensic artifact written.")
        raise
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(result["status"],"source price symbols:",result["entry_date_price_symbols_compared"])
    print("Original model entry locked; NO BROKER and NO proven alpha.")

if __name__=="__main__":main()

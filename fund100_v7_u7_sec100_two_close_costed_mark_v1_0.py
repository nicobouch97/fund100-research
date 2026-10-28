"""U7: costed TWO-CLOSE SEC100 source cohort marks, NO BROKER.

A newly observed accession is admitted ONLY by independent U5 original SEC
replay and previously archived successful source, as frozen by U6. Neither
the SEC filing date nor a later price-series revision can select an entry.
No broker connectivity, trading signals, order rights or proven alpha.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

import fund100_v7_u6_sec100_causal_forward_admission_v1_0 as u6

SCHEMA="FUND100_V7_U7_COSTED_100_SEC_SOURCE_FORWARD_TWO_CLOSE_MARKS_V1"
COSTS=(5,15,35)
BENCHMARK="SPY"
MAX_EXPOSURES=100
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0

class MarkStop(ValueError):
    pass


def _now_utc()->datetime:
    """Actual observation clock; replaceable only in deterministic tests."""
    return datetime.now(timezone.utc)

def _panel(frame:pd.DataFrame,symbols:set[str])->pd.DataFrame:
    if (not isinstance(frame,pd.DataFrame) or not len(frame)
        or set(frame.columns)!=symbols
        or not isinstance(frame.index,pd.DatetimeIndex)
        or frame.index.tz is not None
        or not frame.index.is_monotonic_increasing
        or frame.index.has_duplicates
        or not all(dt==dt.normalize() for dt in frame.index)):
        raise MarkStop("Unverifiable fixed-symbol daily adjusted-price panel")
    panel=frame.loc[:,sorted(symbols)].copy()
    if any(not pd.api.types.is_numeric_dtype(panel[x]) for x in panel.columns):
        raise MarkStop("Non-numeric daily adjusted close")
    for symbol in panel.columns:
        values=panel[symbol].to_numpy(dtype=float)
        if any(not isfinite(float(x)) or float(x)<=0 or float(x)>=1_000_000 for x in values):
            raise MarkStop("Invalid or missing adjusted-price observation")
        if any(abs(float(values[i])/float(values[i-1])-1)>.45 for i in range(1,len(values))):
            raise MarkStop("Unexplained daily adjusted-price discontinuity")
    try:
        exchange=xcals.get_calendar("XNYS")
        actual=exchange.sessions_in_range(panel.index[0],panel.index[-1])
    except Exception as exc:
        raise MarkStop("Authentic NYSE calendar unavailable") from exc
    actual=actual.tz_localize(None).normalize()
    if not panel.index.equals(actual):
        raise MarkStop("Gap/extra session in market-price evidence")
    return panel

def canonical_csv(panel:pd.DataFrame)->str:
    return panel.to_csv(index=True,index_label="Date",date_format="%Y-%m-%d",
                        float_format="%.10f")

def evaluate(frozen:dict,*,prices:pd.DataFrame|None,
             later_price_acquired_utc:str|None=None,
             provider_reference:str|None=None)->dict:
    """Pure independent two-close comparator, never an order or signal.

    Caller must obtain `frozen` by rerunning u6.freeze_from_sources over
    original immutable U3/U4/U5 and previous main archived SEC responses.
    The price source is ONE later independently acquired, archived vintage.
    """
    if (not isinstance(frozen,dict)
        or frozen.get("schema")!=u6.SCHEMA
        or frozen.get("alpha_established") is not False
        or frozen.get("broker_gets")!=0 or frozen.get("broker_posts")!=0
        or frozen.get("broker_orders")!=0
        or frozen.get("trading_authorized") is not False
        or frozen.get("live_authorized") is not False
        or frozen.get("forward_price_mark_count")!=0
        or frozen.get("future_return_measurement") is not None
        or frozen.get("entry_first_NYSE_session_strictly_after_capture_date") is not True
        or frozen.get("exit_next_NYSE_session") is not True
        or frozen.get("historical_first_SEC_dissemination_time_known") is not False
        or frozen.get("source")!="INDEPENDENTLY_REPLAYED_U5_CONSECUTIVE_OFFICIAL_SEC100"):
        raise MarkStop("Unqualified frozen original SEC100 cohort")
    captured=u6.stamp(frozen.get("current_source_finished_utc"))
    # Source timestamps are claims, not proof that a future session occurred.
    # This check applies even when no market prices were supplied.
    observed_now=_now_utc()
    if captured>observed_now:
        raise MarkStop("Original SEC cohort capture lies in the future")
    rows=frozen.get("deduplicated_stock_entry_exposures")
    accessions=frozen.get("source_qualified_accessions")
    if (not isinstance(rows,list) or len(rows)>MAX_EXPOSURES
        or type(frozen.get("distinct_model_exposures")) is not int
        or frozen["distinct_model_exposures"]!=len(rows)
        or not isinstance(accessions,list)
        or len(accessions)>MAX_EXPOSURES):
        raise MarkStop("Frozen accession and position counts inconsistent")
    n=frozen.get("new_accessions_relative_to_preceding_successful_observer")
    if n is None:
        if rows or accessions:
            raise MarkStop("Absent prior observer cannot create model positions")
    elif type(n) is not int or n!=len(accessions):
        raise MarkStop("New accession census disagrees with original source")
    seen=set()
    expected_symbols={BENCHMARK}
    for entry in rows:
        if not isinstance(entry,dict):
            raise MarkStop("Malformed frozen entry")
        ticker=entry.get("ticker")
        if (type(ticker) is not str or len(ticker)>10
            or ticker not in {r.get("ticker") for r in frozen["source_qualified_accessions"]}
            or entry.get("post_cost_return") is not None
            or entry.get("stock_and_SPY_future_closes_authenticated") is not False):
            raise MarkStop("Original event exposure claimed future price")
        future=u6.future_closes(captured)
        if (entry.get("entry_close"),entry.get("exit_close"))!=future:
            raise MarkStop("Future entry dates changed from original source")
        key=(ticker,entry.get("entry_close"))
        if key in seen:
            raise MarkStop("Duplicate ticker/date portfolio exposure")
        seen.add(key)
        refs=entry.get("accessions")
        if (type(refs) is not list or not refs or refs!=sorted(set(refs))
            or any(not any(r["ticker"]==ticker and r["original_sec_filing_accession"]==acc
                           for r in frozen["source_qualified_accessions"]) for acc in refs)):
            raise MarkStop("Corrupt original accession association")
        expected_symbols.add(ticker)
    if sum(len(entry["accessions"]) for entry in rows)!=len(frozen["source_qualified_accessions"]):
        raise MarkStop("One SEC accession counted as multiple model positions")

    panel=None
    acquired=None
    price_sha=None
    if prices is not None:
        if not rows:
            raise MarkStop("Do not fetch or attach price data for zero new events")
        if type(later_price_acquired_utc) is not str:
            raise MarkStop("Later price source must have original UTC acquisition")
        panel=_panel(prices,expected_symbols)
        try:
            acquired=u6.stamp(later_price_acquired_utc)
        except u6.ForwardAdmissionStop as exc:
            raise MarkStop("Later price source timestamp invalid") from exc
        if acquired>observed_now:
            raise MarkStop("Later market-price receipt lies in the future")
        last=panel.index[-1].date()
        if (type(provider_reference) is not str or
            not 10<=len(provider_reference)<=240
            or acquired<=captured or acquired.date()<=last
            or (acquired.date()-last).days>5):
            raise MarkStop("Price vintage not independent or completed")
        price_sha=sha256(canonical_csv(panel).encode()).hexdigest()
    elif later_price_acquired_utc is not None or provider_reference is not None:
        raise MarkStop("Price metadata without independent panel")

    result_rows=[]
    observed=0
    pending=0
    for entry in rows:
        copy={
            "ticker":entry["ticker"],
            "frozen_entry_close":entry["entry_close"],
            "frozen_exit_close":entry["exit_close"],
            "original_earnings_accessions":entry["accessions"],
            "stock_two_close_gross_return":None,
            "spy_two_close_gross_return":None,
            "stock_net_minus_spy_net_percentage_points":None,
            "stock_net_minus_gross_spy_percentage_points":None,
            "status":"WAITING_FOR_INDEPENDENT_FUTURE_COMPLETED_PRICE_SOURCE",
            "broker_order":None}
        first,last=map(pd.Timestamp,(entry["entry_close"],entry["exit_close"]))
        if (panel is not None and first in panel.index and last in panel.index
            and acquired.date()>last.date()):
            sym=entry["ticker"]
            gross=float(panel.loc[last,sym]/panel.loc[first,sym])
            benchmark=float(panel.loc[last,BENCHMARK]/panel.loc[first,BENCHMARK])
            if not (isfinite(gross) and isfinite(benchmark) and gross>0 and benchmark>0):
                raise MarkStop("Nonfinite source-relative independent returns")
            copy.update({
                "status":"TWO_COMPLETED_CLOSES_COSTED_DESCRIPTIVE_NOT_ALPHA",
                "stock_two_close_gross_return":round(gross-1,10),
                "spy_two_close_gross_return":round(benchmark-1,10),
                "stock_net_minus_spy_net_percentage_points":{
                    str(b):round(100*(gross-benchmark)*(1-b/10000)**2,9) for b in COSTS},
                "stock_net_minus_gross_spy_percentage_points":{
                    str(b):round(100*(gross*(1-b/10000)**2-benchmark),9) for b in COSTS}
            })
            observed+=1
        else:
            pending+=1
        result_rows.append(copy)
    return {
        "schema":SCHEMA,
        "status":("NO_SOURCE_QUALIFIED_NEW_EVENTS" if not rows
            else "SOURCE_DATED_DESCRIPTIVE_FORWARD_MARKS_NOT_ALPHA" if observed
            else "AWAITING_FUTURE_COMPLETED_MARKET_SOURCE"),
        "frozen_original_sec_capture_utc":frozen["current_source_finished_utc"],
        "frozen_original_sec100_manifest_sha256":frozen["current_source_manifest_sha256"],
        "frozen_u6_report_sha256":sha256(
            json.dumps(frozen,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "later_original_price_acquired_utc":later_price_acquired_utc,
        "later_price_source_reference":provider_reference,
        "later_price_source_csv_sha256":price_sha,
        "unique_model_exposures":len(rows),
        "priced_two_close_exposures":observed,
        "pending_two_close_exposures":pending,
        "costs_bps_per_side_stock_and_spy":list(COSTS),
        "matched_SPY_roundtrip_costed":True,
        "separately_stock_vs_gross_untraded_SPY_reported":True,
        "same_later_revisable_vendor_vintage_for_stock_and_SPY":panel is not None,
        "close_prices_are_not_exchange_auction_fills":True,
        "contemporary_source_universe_is_not_survivorship_safe_historical_universe":True,
        "original_SEC_filing_date_not_used_as_entry_date":True,
        "original_source_replay_must_precede_model":True,
        "new_events_are_not_earnings_surprise_or_trade_signals":True,
        "source_relative_first_observation_not_true_public_dissemination":True,
        "source_dated_return_observations":result_rows,
        "statistically_proven_alpha":False,"trading_authorized":False,
        "live_authorized":False,"broker_gets":0,"broker_posts":0,"broker_orders":0}

def public_original_prices(symbols:set[str])->pd.DataFrame:
    """Source is a revision-prone vendor; preserve exact downloaded CSV."""
    if not symbols or BENCHMARK not in symbols or len(symbols)>MAX_EXPOSURES+1:
        raise MarkStop("Unbounded or unqualified research price roster")
    import yfinance as yf
    now=datetime.now(timezone.utc)
    raw=yf.download(tickers=sorted(symbols),start="2026-10-20",
                    end=now.date().isoformat(),interval="1d",
                    auto_adjust=True,actions=False,progress=False,threads=False)
    if not isinstance(raw,pd.DataFrame) or raw.empty:
        raise MarkStop("Later independent public prices unavailable")
    if not isinstance(raw.columns,pd.MultiIndex):
        raise MarkStop("Later price source did not return symbol identities")
    values={}
    for symbol in sorted(symbols):
        for key in (("Close",symbol),(symbol,"Close")):
            if key in raw.columns:
                values[symbol]=raw[key]
                break
        if symbol not in values:
            raise MarkStop("Source missing frozen symbol")
    frame=pd.DataFrame(values)
    if frame.index.tz is not None:
        frame.index=frame.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        frame.index=frame.index.normalize()
    return _panel(frame,symbols)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-u3",type=Path,required=True)
    p.add_argument("--original-first-sec",type=Path,required=True)
    p.add_argument("--later-sec",type=Path,required=True)
    p.add_argument("--previous-successful-sec",type=Path)
    p.add_argument("--previous-successful-main-run-id",type=int)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    out=args.output_dir
    if out.exists():
        raise MarkStop("Original source/returns output must be new, never overwritten")
    frozen=u6.freeze_from_sources(
        original_u3=args.original_u3,original_first_sec=args.original_first_sec,
        later_sec=args.later_sec,previous_sec=args.previous_successful_sec,
        previous_main_id=args.previous_successful_main_run_id)
    refs=frozen["deduplicated_stock_entry_exposures"]
    acquired=None
    price=None
    provider=None
    if refs:
        price=public_original_prices({BENCHMARK}|{r["ticker"] for r in refs})
        acquired=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        provider="independent revisable public yfinance adjusted closes received "+acquired
    result=evaluate(frozen,prices=price,
                    later_price_acquired_utc=acquired,provider_reference=provider)
    out.mkdir(parents=True)
    (out/"original-u6-frozen-source-cohort.json").write_text(
        json.dumps(frozen,indent=2,sort_keys=True)+"\n")
    if price is not None:
        (out/"original-later-revisable-market-vintage.csv").write_text(canonical_csv(price))
    (out/"costed-source-dated-two-close-marks.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("Source-qualified SEC100 exposures:",result["unique_model_exposures"])
    print("Genuine post-observation completed market marks:",result["priced_two_close_exposures"])
    print("WAITING marks:",result["pending_two_close_exposures"])
    print("NO broker orders or proven investment alpha.")

if __name__=="__main__":main()

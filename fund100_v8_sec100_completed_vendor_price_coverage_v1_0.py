"""Capture prospective vendor-completed prices for the original frozen SEC100 CIKs.

External provider is Yahoo/yfinance: a public research vendor, NOT an exchange,
broker entitlement, executable quote, issuer-share-class attestation, PIT
historical price archive or proven total-return factor. Each original frozen
issuer gets a visible PRICE_SOURCE_MISSING state rather than being dropped.
Do not use live unless a separately authenticated eligible order source
passes full funded account risk, order ledger and trade execution review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

import exchange_calendars as xcals
import pandas as pd

import fund100_v8_sec100_original_annual_quality_source_v1_0 as financial

SCHEMA = "FUND100_V8_FROZEN_SEC100_COMPLETED_PUBLIC_VENDOR_PRICE_COVERAGE_NO_ORDERS_V1"
SOURCE = "YFINANCE_NORMALIZED_PUBLIC_VENDOR_UNAUTHENTICATED_V1"
ORIGINAL_FINANCIAL_RUN = 42620947546
ORIGINAL_FINANCIAL_SHA = "8b0356cfaf406127a1b418bbe29d87c27457c0dd"
FIRST_REGISTERED_UTC = "2026-11-09T13:20:00Z"
TARGET = 100
LOOKBACK = 252
SKIP = 42
LIQUIDITY = 20
MAX_ROWS_PER_SYMBOL = 800
NO_BROKER_NETWORK = True
NO_PRIVATE_MUTATIONS = True
LIVE_RELEASED = False

class PriceSourceHold(ValueError):
    pass


def utc(v):
    if type(v) is not str or re.fullmatch(
            r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",v) is None:
        raise PriceSourceHold("Original price acquisition clock not canonical UTC")
    try:
        dt=datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise PriceSourceHold("Invalid original acquisition timestamp") from None
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ")!=v:
        raise PriceSourceHold("Noncanonical original UTC timestamp")
    return dt


def number(v, *, positive=False, integer=False):
    if type(v) is not str or re.fullmatch(
            r"(?:0|[1-9][0-9]{0,13})(?:\.[0-9]{1,8})?",v) is None:
        raise PriceSourceHold("Missing or noncanonical original price/volume")
    try:
        n=Decimal(v)
    except InvalidOperation:
        raise PriceSourceHold("Invalid numeric vendor observation") from None
    if not n.is_finite() or n>Decimal("1e13") or (positive and n<=0):
        raise PriceSourceHold("Unbounded or invalid public vendor observation")
    if integer and n!=n.to_integral_value():
        raise PriceSourceHold("Volume must represent complete shares")
    return n


def _source_rows(*, observed:dict, roster:list[dict], acquisition:str, finance:dict):
    now=utc(acquisition)
    if now<=utc(FIRST_REGISTERED_UTC):
        raise PriceSourceHold("Unregistered source observation")
    if now<utc(finance["original_sec100_source_completed_utc"]):
        raise PriceSourceHold("Future SEC fundamentals reused before original reception")
    if type(observed) is not dict or type(roster) is not list or len(roster)!=TARGET:
        raise PriceSourceHold("Original 100-issuer source frame invalid")
    symbols=[r["ticker"] for r in roster]
    if (len(set(symbols))!=TARGET
        or set(observed)!=set(symbols)
        or any(type(s) is not str or re.fullmatch(r"[A-Z][A-Z0-9-]{0,12}",s) is None
               for s in symbols)):
        raise PriceSourceHold("Public vendor names do not match original frozen issuer IDs")
    try:
        cal=xcals.get_calendar("XNYS")
        completed=cal.sessions_in_range(
            pd.Timestamp(now.date()-timedelta(days=14)),
            pd.Timestamp(now.date()-timedelta(days=1)))
        last=completed[-1].date()
        window=cal.sessions_in_range(
            pd.Timestamp(last-timedelta(days=550)),pd.Timestamp(last))
        sessions=[x.date().isoformat() for x in window[-(LOOKBACK+1):]]
    except Exception as exc:
        raise PriceSourceHold("Independent NYSE calendar unavailable") from exc
    if len(sessions)!=LOOKBACK+1:
        raise PriceSourceHold("Insufficient independent XNYS lookback")
    oldest=sessions[0]
    accepted=0
    per_symbol=[]
    for row in roster:
        s=row["ticker"]
        items=observed[s]
        if type(items) is not list or len(items)>MAX_ROWS_PER_SYMBOL:
            raise PriceSourceHold("Missing or unbounded price rows for one issuer")
        prices={}
        last_day=""
        for obj in items:
            if type(obj) is not dict or set(obj)!={
                    "session","close_usd","adjusted_close_usd","volume_shares"}:
                raise PriceSourceHold("Unreviewed vendor session row fields")
            day=obj["session"]
            if type(day) is not str or re.fullmatch(r"20\d\d-\d\d-\d\d",day) is None:
                raise PriceSourceHold("Noncanonical vendor market date")
            try:
                parsed=datetime.strptime(day,"%Y-%m-%d").date()
            except ValueError:
                raise PriceSourceHold("Invalid vendor market date") from None
            if (parsed>=now.date() or day<=last_day
                or not cal.is_session(pd.Timestamp(parsed))):
                raise PriceSourceHold("Intraday/future/reordered/non-NYSE vendor price")
            last_day=day
            price=number(obj["close_usd"],positive=True)
            adj=number(obj["adjusted_close_usd"],positive=True)
            volume=number(obj["volume_shares"],integer=True)
            if price>Decimal("1000000") or adj>Decimal("1000000"):
                raise PriceSourceHold("Unbounded vendor price")
            prices[day]=(price,adj,volume)
        status="MISSING_LAST_COMPLETED_NYSE_PRICE"
        coverage=sum(s0 in prices for s0 in sessions)
        marks={}
        if last.isoformat() in prices:
            status="INSUFFICIENT_252_SESSION_ADJUSTED_PRICE_HISTORY"
            if coverage==len(sessions):
                values=[prices[day] for day in sessions]
                status="INVALID_NONPOSITIVE_20D_DOLLAR_TURNOVER"
                vol20=sum((p*v for p,_,v in values[-LIQUIDITY:]),Decimal(0))/LIQUIDITY
                if vol20>0:
                    status="PRICE_SESSION_OBSERVED_RESEARCH_ONLY"
                    accepted+=1
                    marks={
                        "last_completed_market_close_usd":
                            format(values[-1][0],".8f"),
                        "last_adjusted_close_usd":format(values[-1][1],".8f"),
                        "adjusted_252_sessions_ago":format(values[0][1],".8f"),
                        "adjusted_42_sessions_ago":
                            format(values[-1-SKIP][1],".8f"),
                        "average_20_day_unadjusted_dollar_volume_usd":
                            format(vol20.quantize(Decimal(".01")),"f"),
                    }
        per_symbol.append({
            "ticker":s,"original_issuer_CIK":row["original_sec_cik_10digit"],
            "last_completed_NYSE_session":last.isoformat(),
            "source_market_session_count":len(prices),
            "required_253_session_coverage_count":coverage,
            "status":status,
            "source_price_mark":marks,
            "original_frozen_2026_issuer_not_broker_eligible":True,
            "shares_market_cap_quotes_spreads_and_alpha_not_authenticated":True,
            "trading_authorized":False,
        })
    return last.isoformat(),per_symbol,accepted


def analyze(*, normalized_source:dict, finance:dict)->dict:
    if (type(finance) is not dict or finance.get("schema")!=financial.SCHEMA
        or finance.get("source_issuer_count")!=TARGET
        or finance.get("original_official_SEC_endpoint_get_count")!=200
        or finance.get("live_authorized") is not False
        or finance.get("broker_orders")!=0
        or type(normalized_source) is not dict
        or set(normalized_source)!={"source","captured_utc","quotes_by_ticker"}
        or normalized_source["source"]!=SOURCE):
        raise PriceSourceHold("Not the pinned brokerless 100-issuer original financial source")
    roster=finance["source_issuer_rows"]
    last,rows,complete=_source_rows(
        observed=normalized_source["quotes_by_ticker"],roster=roster,
        acquisition=normalized_source["captured_utc"],finance=finance)
    raw=json.dumps(normalized_source,sort_keys=True,
                   separators=(",",":"),ensure_ascii=True).encode("ascii")
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_SEC100_COMPLETED_PUBLIC_VENDOR_MARKS_RESEARCH_ONLY",
        "original_financial_source_main_run_id":ORIGINAL_FINANCIAL_RUN,
        "original_financial_source_commit_sha":ORIGINAL_FINANCIAL_SHA,
        "original_financial_source_completed_utc":
            finance["original_sec100_source_completed_utc"],
        "price_source":SOURCE,
        "normalized_vendor_snapshot_sha256":sha256(raw).hexdigest(),
        "price_capture_utc":normalized_source["captured_utc"],
        "last_prior_completed_NYSE_market_session":last,
        "original_issuer_count":TARGET,
        "complete_253_prior_NYSE_session_price_count":complete,
        "incomplete_or_missing_last_253_session_count":TARGET-complete,
        "issuer_coverage_rows":rows,
        "historical_yahoo_prices_not_original_point_in_time_market_tape":True,
        "vendor_adjusted_history_can_be_revised":True,
        "market_price_share_class_split_and_quote_independently_verified":False,
        "provider_is_not_broker_or_exchange":True,
        "stock_valuation_earnings_alpha_and_executable_liquidity_unverified":True,
        "live_order_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "private_git_writes":0,
    }


def _download(*, names:list[str], acquired_utc:str):
    """Whole-cohort vendor source: normalize, NEVER fill missing history."""
    import yfinance as yf
    after=(utc(acquired_utc).date()+timedelta(days=1)).isoformat()
    data=yf.download(tickers=names,start="2025-07-01",end=after,
                     interval="1d",auto_adjust=False,actions=False,
                     progress=False,threads=False,group_by="column")
    if not isinstance(data,pd.DataFrame) or data.empty:
        raise PriceSourceHold("Public research price vendor unavailable")
    if not isinstance(data.columns,pd.MultiIndex):
        raise PriceSourceHold("Unrecognised multi-symbol public vendor structure")
    if data.index.has_duplicates:
        raise PriceSourceHold("Duplicated vendor session date")
    if data.index.tz is not None:
        ix=data.index.tz_convert("UTC").tz_localize(None)
    else:
        ix=data.index
    data.index=ix.normalize()
    output={}
    for s in names:
        cols={}
        for name in ("Close","Adj Close","Volume"):
            found=next((col for col in ((name,s),(s,name)) if col in data.columns),None)
            if found is None:
                cols={}
                break
            cols[name]=data[found]
        items=[]
        if cols:
            for day in data.index:
                if day.date()>=utc(acquired_utc).date():
                    # Never call a partial same-day NYSE bar a completed close.
                    continue
                price=cols["Close"].loc[day]
                adjusted=cols["Adj Close"].loc[day]
                volume=cols["Volume"].loc[day]
                if any(pd.isna(x) for x in (price,adjusted,volume)):
                    continue
                try:
                    def fmt(v):
                        return format(Decimal(str(float(v))),".8f")
                    raw={
                        "session":day.date().isoformat(),
                        "close_usd":fmt(price),
                        "adjusted_close_usd":fmt(adjusted),
                        "volume_shares":str(int(volume)),
                    }
                except (ValueError,TypeError,InvalidOperation,OverflowError):
                    continue
                items.append(raw)
        output[s]=items
    return {"source":SOURCE,"captured_utc":acquired_utc,"quotes_by_ticker":output}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-u3",type=Path,required=True)
    p.add_argument("--original-sec100",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not (NO_BROKER_NETWORK and NO_PRIVATE_MUTATIONS and not LIVE_RELEASED):
        raise PriceSourceHold("Nonbroker source release changed")
    if a.output.exists() and any(a.output.iterdir()):
        raise PriceSourceHold("Never overwrite original current vendor source")
    try:
        original_finance=financial.verify(
            u3_dir=a.original_u3,report_dir=a.original_sec100)
    except Exception:
        raise PriceSourceHold("Original SEC100 frozen original sources not replayable") from None
    captured=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    names=[x["ticker"] for x in original_finance["source_issuer_rows"]]
    normalized=_download(names=names,acquired_utc=captured)
    report=analyze(normalized_source=normalized,finance=original_finance)
    a.output.mkdir(parents=True,exist_ok=False)
    raw=json.dumps(normalized,sort_keys=True,separators=(",",":")).encode("ascii")
    (a.output/"normalized-public-price-source.json").write_bytes(raw)
    (a.output/"coverage-manifest.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n")
    # Locally recompute from the immutable normalized file, not from a new HTTP GET.
    source=json.loads((a.output/"normalized-public-price-source.json").read_bytes())
    if analyze(normalized_source=source,finance=original_finance)!=report:
        raise PriceSourceHold("Original source coverage report did not replay")
    print("Frozen issuer count:",report["original_issuer_count"])
    print("Complete 253 prior NYSE close covered:",
          report["complete_253_prior_NYSE_session_price_count"])
    print("Vendor coverage gaps/quarantine:",
          report["incomplete_or_missing_last_253_session_count"])
    print("No share valuation, executable quotes, broker or alpha.")


if __name__=="__main__":
    main()

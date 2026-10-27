"""V7-U1: ONE prospective 100-issuer universe from original IVV holdings/SEC.

This is a new signal-coverage cohort, NOT a source of alpha, an old-
historical point-in-time listed security master, or brokerage permission.
Freeze the top 100 DISTINCT operating-company CIKs among original IVV
equity holdings, ranked by provider-supplied fund weight; match original
SEC ticker CIK map obtained at the SAME research source-capture time.

The original source was selected before future post-capture earnings
events. Never re-rank with later returns, or silently roll the roster.
"""
from __future__ import annotations

from csv import reader
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

SCHEMA="FUND100_V7_U1_ORIGINAL_IVV_WEIGHT_100_ISSUER_PROSPECTIVE_COHORT_V1"
ORIGINAL_IVV_HOLDINGS_URL=(
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund")
ORIGINAL_SEC_TICKERS_URL="https://www.sec.gov/files/company_tickers.json"
FIRST_REGISTRATION_NOT_EARLIER_THAN="2026-10-27"
TARGET_DISTINCT_CIKS=100
MIN_IVV_EQUITY_TICKERS=400
MAX_RAW_HOLDINGS_BYTES=4_000_000
MAX_SEC_MAP_BYTES=5_000_000
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class UniverseStop(ValueError): pass

def _text(raw:bytes,max_len:int,name:str)->str:
    if type(raw) is not bytes or not 600<=len(raw)<=max_len:
        raise UniverseStop("Missing/oversized original "+name)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise UniverseStop("Original "+name+" is not UTF-8 text") from e

def _stamp(value:str)->datetime:
    if (type(value) is not str or
        re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                     value) is None):
        raise UniverseStop("Expected exact UTC original source receipt")
    try:
        result=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise UniverseStop("Impossible original UTC receipt") from None
    return result

def _source_day(raw):
    if type(raw) is not str:
        raise UniverseStop("Missing official source provider holdings date")
    # The original iShares report usually presents e.g. "Oct 23, 2026".
    try:
        return datetime.strptime(raw.strip(),"%b %d, %Y").date()
    except ValueError:
        raise UniverseStop("Unexpected original IVV holdings date") from None

def original_layout_diagnostic(raw:bytes):
    """Return ONLY PUBLIC, bounded original provider CSV structure.

    Observe the actual issuer file on a credentialless PR without
    redistributing the source vendor's security position data.
    Date metadata is represented by format only (never guessed),
    columns are displayed only when they resemble known header tokens.
    """
    original=_text(raw,MAX_RAW_HOLDINGS_BYTES,"holdings layout")
    try:
        lines=list(reader(StringIO(original)))
    except Exception as e:
        raise UniverseStop("Cannot inspect holdings CSV rows") from e
    tags=("ticker","issuer ticker","name","sector","asset class",
          "weight (%)","fund holdings as of","holdings as of","as of",
          "fund name","fund","ticker symbol")
    observations=[]
    for i,row in enumerate(lines[:90]):
        clean=[str(x).strip().lstrip("\ufeff") for x in row]
        tokens=[x for x in clean if x.lower() in tags]
        has_asof=any("holdings" in x.lower() and ("as of" in x.lower()
                        or "date" in x.lower()) for x in clean)
        # No issuer names, prices, weights, portfolio holdings or
        # raw bytes emitted. For troublesome date layouts show only
        # field count and first cell's length, not full source strings.
        if tokens or has_asof or i<5:
            observations.append({
                "zero_based_csv_row":i,
                "field_count":len(clean),
                "matching_public_column_labels":tokens[:18],
                "row_has_holdings_asof_label":has_asof,
                "first_field_character_count":len(clean[0]) if clean else 0,
                "second_field_character_count":len(clean[1]) if len(clean)>1 else 0,
            })
    return {"schema":"FUND100_U2_PUBLIC_ORIGINAL_IVV_COLUMN_LAYOUT_ONLY",
            "original_content_sha256":sha256(raw).hexdigest(),
            "original_csv_row_count":len(lines),
            "original_byte_count":len(raw),
            "candidate_metadata_and_header_rows":observations,
            "source_constituent_data_redistributed":False,
            "broker_gets":0,"broker_posts":0,"broker_orders":0}

def _holdings(raw:bytes):
    original=_text(raw,MAX_RAW_HOLDINGS_BYTES,"fund holdings")
    try:
        lines=list(reader(StringIO(original)))
    except Exception as e:
        raise UniverseStop("Malformed provider holdings CSV") from e
    if not 405<=len(lines)<=3000:
        raise UniverseStop("Unexpected IVV S&P500 file size or membership")
    held_date=None
    header=None
    for i,row in enumerate(lines[:65]):
        clean=[str(x).strip() for x in row]
        if (len(clean)>=2 and clean[0] in
                ("Fund Holdings as of","Holdings as of")):
            if held_date is not None:
                raise UniverseStop("Ambiguous provider holdings date")
            held_date=_source_day(clean[1])
        # BlackRock's current IVV export labels the equity identifier
        # "Issuer Ticker"; some earlier downloads use "Ticker". Accept
        # exactly one documented spelling, never guess a column by position.
        needed={"Name","Sector","Asset Class","Weight (%)"}
        ticker_headers=[x for x in ("Ticker","Issuer Ticker") if x in clean]
        if needed<=set(clean) and ticker_headers:
            if header is not None:
                raise UniverseStop("Repeated holdings column header")
            if len(ticker_headers)!=1 or any(clean.count(x)!=1 for x in
                    (*needed,*ticker_headers)):
                raise UniverseStop("Ambiguous original holdings columns")
            cols={col:clean.index(col) for col in needed}
            cols["Ticker"]=clean.index(ticker_headers[0])
            header=(i,cols)
    if held_date is None or header is None:
        raise UniverseStop("No identifiable official IVV date/weight/asset class")
    start,cols=header
    rows=[]
    seen=set()
    equity_total=Decimal(0)
    for idx,row in enumerate(lines[start+1:],start+2):
        if len(row)<=max(cols.values()):
            continue  # official provider disclaimer / following blank rows
        def field(key):
            return row[cols[key]].strip()
        if field("Asset Class")!="Equity":
            continue
        ticker=field("Ticker").upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,10}",ticker):
            raise UniverseStop("Unrecognized reported IVV common-share ticker")
        if ticker in seen:
            raise UniverseStop("Duplicate equity ticker within original holdings")
        seen.add(ticker)
        try:
            w=Decimal(field("Weight (%)").replace(",",""))
        except InvalidOperation:
            raise UniverseStop("Invalid original IVV provider fund weight") from None
        if not w.is_finite() or w<0 or w>Decimal("20"):
            raise UniverseStop("Unbounded provider source equity weight")
        equity_total+=w
        if field("Name") and field("Sector") and w>0:
            rows.append({"ticker":ticker,"name":field("Name"),
                         "sector":field("Sector"),"weight_percent":w,
                         "original_provider_line":idx})
    if len(rows)<MIN_IVV_EQUITY_TICKERS or not Decimal("95")<=equity_total<=Decimal("102"):
        raise UniverseStop("IVV holdings weight coverage or stock breadth invalid")
    return held_date,rows

def _sec_map(raw:bytes):
    data=_text(raw,MAX_SEC_MAP_BYTES,"SEC CIK mapping")
    try:
        payload=json.loads(data)
    except ValueError:
        raise UniverseStop("Invalid SEC original ticker map") from None
    if not isinstance(payload,dict) or len(payload)<1000:
        raise UniverseStop("SEC original ticker map improbably incomplete")
    lookup={}
    for value in payload.values():
        if type(value) is not dict or not {"ticker","cik_str","title"}<=set(value):
            raise UniverseStop("SEC original CIK record missing source fields")
        ticker=value["ticker"]
        cik=value["cik_str"]
        if (type(ticker) is not str or type(cik) is not int
            or cik<=0 or cik>=10_000_000_000 or
            re.fullmatch(r"[A-Z][A-Z0-9.-]{0,12}",ticker) is None):
            raise UniverseStop("SEC original ticker or CIK invalid")
        normalized=ticker.replace(".","-")
        cik=f"{cik:010d}"
        if normalized in lookup and lookup[normalized]!=cik:
            raise UniverseStop("Ambiguous conflicting SEC ticker CIK")
        lookup[normalized]=cik
    return lookup

def freeze(*,holdings_csv:bytes,sec_ticker_json:bytes,
           captured_at_utc:str):
    now=_stamp(captured_at_utc)
    if now.date().isoformat()<FIRST_REGISTRATION_NOT_EARLIER_THAN:
        raise UniverseStop("Forward cohort source predates preregistration")
    asof,rows=_holdings(holdings_csv)
    if not 0<=(now.date()-asof).days<=7:
        raise UniverseStop("Official holdings too stale/future for prospective freeze")
    ciks=_sec_map(sec_ticker_json)
    # Sort by original fund provider weight only, not by future
    # returns, earnings news, ticker performance or future company status.
    rows.sort(key=lambda x:(-x["weight_percent"],x["ticker"]))
    enrolled=[]
    unique_cik=set()
    missing=[]
    for item in rows:
        ticker=item["ticker"].replace(".","-")
        cik=ciks.get(ticker)
        if cik is None:
            missing.append(ticker)
            continue
        if cik in unique_cik:
            continue
        unique_cik.add(cik)
        if len(enrolled)<TARGET_DISTINCT_CIKS:
            enrolled.append({
                "ticker":ticker,
                "sec_cik_10_digit":cik,
                "original_provider_weight_percent":
                    format(item["weight_percent"],"f"),
                "original_ishares_sector":item["sector"],
                "original_line_number":item["original_provider_line"],
                "identity_only_not_instrument_authorization":True,
            })
        if len(enrolled)==TARGET_DISTINCT_CIKS:
            break
    if len(enrolled)!=TARGET_DISTINCT_CIKS:
        raise UniverseStop("Insufficient uniquely SEC-resolved issuer identities")
    if len(set(x["ticker"] for x in enrolled))!=TARGET_DISTINCT_CIKS:
        raise UniverseStop("Duplicate equity share identifier in prospective roster")
    return {
        "schema":SCHEMA,
        "status":"FIRST_PROSPECTIVE_100_ISSUER_WATCH_UNIVERSE_NOT_SIGNAL",
        "original_ivv_source_url":ORIGINAL_IVV_HOLDINGS_URL,
        "original_sec_ticker_url":ORIGINAL_SEC_TICKERS_URL,
        "original_provider_csv_sha256":sha256(holdings_csv).hexdigest(),
        "original_sec_ticker_map_sha256":sha256(sec_ticker_json).hexdigest(),
        "original_source_collected_at_utc":captured_at_utc,
        "original_holdings_reported_asof":asof.isoformat(),
        "fixed_registration_after_source_receipt_utc":captured_at_utc,
        "original_equity_symbols_count":len(rows),
        "original_official_provider_weight_sum_with_cash_excluded":
            format(sum((x["weight_percent"] for x in rows),Decimal(0)),"f"),
        "source_missing_tickers_count_before_top100_resolved":
            len(missing),
        "prospectively_frozen_100_unique_cik_roster":enrolled,
        "selected_by_provider_index_weight_NOT_future_stock_returns":True,
        "top100_index_weight_is_not_quality_alpha_or_independent_analysis":True,
        "2026_roster_not_historical_point_in_time_membership":True,
        "sec_cik_identity_not_verified_common_share_tradability":True,
        "original_public_feeds_revisable_after_capture":True,
        "future_sec_events_or_returns_observed":0,
        "eligible_to_rank_or_execute_live_orders":False,
        "original_live_cap_usd":"130.30",
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "live_authorized":False,"trading_authorized":False,
    }

def _fetch(url,agent,max_bytes):
    req=Request(url,headers={
        "User-Agent":agent,"Accept":"text/csv,application/json,*/*"})
    try:
        with urlopen(req,timeout=35) as response:
            if response.status!=200:
                raise UniverseStop("Unexpected official source status")
            if not response.url.startswith(url.split("?")[0]):
                raise UniverseStop("Unexpected official source redirect")
            data=response.read(max_bytes+1)
    except Exception as e:
        raise UniverseStop("Official provider or SEC source unavailable") from e
    if len(data)>max_bytes:
        raise UniverseStop("Oversized official source")
    return data

def acquire_original(*,contact_agent:str)->tuple[dict,bytes,bytes]:
    if type(contact_agent) is not str or not 10<=len(contact_agent)<=200:
        raise UniverseStop("Original SEC contact identity unavailable")
    original=_fetch(ORIGINAL_IVV_HOLDINGS_URL,contact_agent,MAX_RAW_HOLDINGS_BYTES)
    sec=_fetch(ORIGINAL_SEC_TICKERS_URL,contact_agent,MAX_SEC_MAP_BYTES)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return freeze(holdings_csv=original,sec_ticker_json=sec,
                  captured_at_utc=now),original,sec

def main():
    import argparse,os
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--inspect-provider-layout",action="store_true")
    args=parser.parse_args()
    if args.inspect_provider_layout:
        raw=_fetch(ORIGINAL_IVV_HOLDINGS_URL,
                   "Fund100 institutional prospective ETF source schema audit",MAX_RAW_HOLDINGS_BYTES)
        print(json.dumps(original_layout_diagnostic(raw),
                         indent=2,sort_keys=True))
        return
    if args.output_dir is None:
        raise UniverseStop("Original roster directory must be explicit")
    if args.output_dir.exists() and list(args.output_dir.iterdir()):
        raise UniverseStop("Never overwrite original prospective roster artifact")
    report,raw_ivv,raw_sec=acquire_original(
        contact_agent=os.environ.get("SEC_USER_AGENT",""))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"original-IVV-public-fund-holdings.csv").write_bytes(raw_ivv)
    (args.output_dir/"original-SEC-public-ticker-map.json").write_bytes(raw_sec)
    (args.output_dir/"prospective-100-issuer-manifest.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    # Verify that the saved raw source can still recreate the same
    # original source identity and deterministic 100-issuer ranking.
    checked=freeze(
        holdings_csv=(args.output_dir/"original-IVV-public-fund-holdings.csv").read_bytes(),
        sec_ticker_json=(args.output_dir/"original-SEC-public-ticker-map.json").read_bytes(),
        captured_at_utc=report["original_source_collected_at_utc"])
    if checked!=report:
        raise UniverseStop("Saved original source fails independent exact replay")
    print("Original holdings as of",report["original_holdings_reported_asof"])
    print("First prospective 100-issuer source roster frozen from public original bytes")
    print("No SEC event prediction, no alpha, NO BROKER.")

if __name__=="__main__":main()

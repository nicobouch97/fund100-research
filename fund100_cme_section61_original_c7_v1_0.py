"""C7 CME *original* PDF first-page futures delivery-month settlements.

Research-only original public exchange bulletin intake with FINAL/source
timestamp, CL identity, settlement and open-interest reconciliation.
NO continuous futures returns, no expiry dates, no order execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen

SCHEMA="FUND100_C7_CME_OFFICIAL_SECTION61_FINAL_CURVE_SOURCE_V1"
SOURCE="https://www.cmegroup.com/daily_bulletin/current/Section61_Energy_Futures_Products.pdf"
MAX_PDF=12_000_000
MIN_PDF=5_000
MAX_DAYS_OLD=14
MONTHS=("JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC")
MONTH_INDEX={m:i for i,m in enumerate(MONTHS)}
CODE=re.compile(r"^("+ "|".join(MONTHS)+r")(\d{2})$")
DOC_DATE=re.compile(r"\bBULLETIN\s*#\s*(\d{1,4})@?[^\n]{0,160}?(Mon|Tue|Wed|Thu|Fri),?\s+"
                    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s*(20\d{2})",
                    re.I)
# Settlement is the value *immediately followed by its signed
# POINT CHANGE*; unlike a different column's high/low or opening price.
PRICE_CHANGE=re.compile(r"(?<![\d.])(\d{1,3}\.\d{2})\s+([+-])\s+(\d{1,3}\.\d{2})"
                        r"\s+([\d,]+|----)\s+([\d,]+|----)\s+([\d,]+|----)(?!\d)")
ROW=re.compile(r"^\s*((?:"+"|".join(MONTHS)+r")\d{2})\s+(.+)$",re.M)
TOTAL=re.compile(r"\bTOTAL\s+CL\s+FUT\s+([\d,]+)\s+([\d,]+|----)\s+([\d,]+)",re.I)


class CMEStop(ValueError):
    pass


def _utc(value:str)->datetime:
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",value):
        raise CMEStop("Source observation requires canonical UTC acquisition timestamp.")
    try:
        return datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CMEStop("Impossible original CME source observation datetime.") from exc


def _number(value:str,name:str)->int:
    if value=="----":
        return 0
    if not re.fullmatch(r"\d{1,12}(?:,\d{3})*",value):
        raise CMEStop("Invalid CME integer "+name)
    return int(value.replace(",",""))


def month_number(token:str)->int:
    m=CODE.fullmatch(token)
    if not m:
        raise CMEStop("Invalid exact CME delivery month.")
    year=2000+int(m.group(2))
    return year*12+MONTH_INDEX[m.group(1)]


def parse_first_page(first_page_text:str,*,acquired_utc:str)->dict:
    """Parse actual pdftotext -layout first page; never read text from another source."""
    acquired=_utc(acquired_utc)
    if not isinstance(first_page_text,str) or len(first_page_text)<300 or len(first_page_text)>400000:
        raise CMEStop("Missing PDF-extracted original first page.")
    head=first_page_text[:1800]
    if "ENERGY FUTURES PRODUCTS" not in head.upper() or "CME GROUP" not in head.upper():
        raise CMEStop("Not actual CME original energy daily bulletin.")
    # CME prints its PRELIMINARY or FINAL label *before* the
    # multi-column PG61 Bulletin/date heading. Reject draft first.
    if re.search(r"\bPRELIMINARY\b",head,re.I):
        raise CMEStop("PRELIMINARY original CME bulletin cannot become FINAL settlement source.")
    found=DOC_DATE.search(head)
    if not found:
        raise CMEStop("Undated original bulletin, no reliable trade date.")
    bulletin=int(found.group(1))
    dow,mon,d,year=found.group(2),found.group(3),int(found.group(4)),int(found.group(5))
    try:
        trade=datetime.strptime(f"{mon} {d} {year}","%b %d %Y").date()
    except ValueError as exc:
        raise CMEStop("Malformed original CME bulletin trade date.") from exc
    if trade.strftime("%a").lower()!=dow.lower()[:3] or not 100<=bulletin<=500:
        raise CMEStop("CME trade date or bulletin sequence header inconsistent.")
    if trade>acquired.date() or (acquired.date()-trade).days>MAX_DAYS_OLD:
        raise CMEStop("Original dated CME bulletin is future or stale beyond 14 days.")
    # Read only status near the header before any product-specific text.
    if re.search(r"\bPRELIMINARY\b",head,re.I):
        raise CMEStop("PRELIMINARY original CME bulletin cannot become FINAL settlement source.")
    if not re.search(r"(?m)^\s*FINAL\s*$",head):
        raise CMEStop("CME bulletin must declare literal FINAL.")
    block_start=re.search(r"(?im)^\s*CL\s+FUT\s+NYMEX\s+CRUDE\s+OIL\s+\(PHYSICAL\)\s*$",first_page_text)
    block_end=re.search(r"(?im)^\s*TOTAL\s+CL\s+FUT\b",first_page_text)
    if not block_start or not block_end or block_end.start()<=block_start.end():
        raise CMEStop("Original CME CL NYMEX CRUDE OIL (PHYSICAL) complete block absent.")
    section=first_page_text[block_start.end():block_end.start()]
    rows=[]
    for mt in ROW.finditer(section):
        label,payload=mt.group(1),mt.group(2)
        parsed=PRICE_CHANGE.search(payload)
        if not parsed or len(PRICE_CHANGE.findall(payload))!=1:
            raise CMEStop("Unparseable/ambiguous settlement and OI for "+label)
        price=float(parsed.group(1))
        change=round(float(parsed.group(3))*(1 if parsed.group(2)=="+" else -1),2)
        volume=_number(parsed.group(4),"globex volume")
        pnt=_number(parsed.group(5),"PNT/PIT volume")
        oi=_number(parsed.group(6),"open interest")
        if not 0<price<500 or not 0<=oi<50_000_000 or volume>100_000_000:
            raise CMEStop("Implausible CL contract price or interest.")
        delivery=month_number(label)
        if delivery<trade.year*12+trade.month-2 or delivery>trade.year*12+trade.month+160:
            raise CMEStop("Nonsensical CL contract expiry month.")
        rows.append({
            "contract_month":label,"delivery_month":f"{delivery//12:04d}-{(delivery%12)+1:02d}",
            "settlement_usd_per_barrel":round(price,2),
            "point_change_usd":change,
            "globex_volume_contracts":volume,
            "pnt_pit_volume_contracts":pnt,
            "open_interest_contracts":oi,
        })
    if len(rows)<12 or len(rows)>125:
        raise CMEStop("Not enough unambiguous individual CL futures contract rows.")
    labels=[r["contract_month"] for r in rows]
    serials=[month_number(x) for x in labels]
    if len(set(labels))!=len(rows) or serials!=sorted(serials):
        raise CMEStop("Duplicate or out-of-order CL delivery months.")
    if serials[1]-serials[0]!=1 or serials[2]-serials[1]!=1:
        raise CMEStop("CME missing immediate front/next futures delivery months.")
    published=TOTAL.search(first_page_text[block_end.start():block_end.start()+200])
    if not published:
        raise CMEStop("CME original CL contract sum row missing.")
    reported_oi=_number(published.group(3),"TOTAL CL FUT original OI")
    computed_oi=sum(r["open_interest_contracts"] for r in rows)
    if reported_oi!=computed_oi:
        raise CMEStop(f"CME CL OI total inconsistent: computed {computed_oi}, published {reported_oi}.")
    f,n=rows[0],rows[1]
    spread=round(f["settlement_usd_per_barrel"]-n["settlement_usd_per_barrel"],2)
    return {
        "schema":SCHEMA,"status":"OFFICIAL_FINAL_CME_CONTRACT_CURVE_SOURCE_ONLY",
        "source_url":SOURCE,
        "source_exchange":"CME_GROUP_NYMEX",
        "source_product_code":"CL",
        "source_product":"NYMEX_CRUDE_OIL_PHYSICAL",
        "original_bulletin_id":bulletin,
        "original_trade_date":trade.isoformat(),
        "source_original_status":"FINAL",
        "observed_acquired_at_utc":acquired_utc,
        "days_old_on_acquisition":(acquired.date()-trade).days,
        "stale_for_current_market_read":(acquired.date()-trade).days>3,
        "contract_month_count":len(rows),
        "published_total_open_interest":reported_oi,
        "sum_verified":True,
        "front_next_month_spread_usd_per_barrel":spread,
        "front_next_curve_shape":"BACKWARDATION" if spread>0 else
            ("CONTANGO" if spread<0 else "FLAT"),
        "has_contract_last_trade_dates":False,
        "exact_original_cme_publication_utc_verified":False,
        "historical_strips_present":False,
        "realized_roll_yield_measured":False,
        "futures_pnl_after_roll_costs_measured":False,
        "fully_executable_trading_quote_verified":False,
        "live_authorized":False,"paper_authorized":False,
        "broker_orders":0,
        "trading_authorized":False,
        "operator_authorized_liquidation":False,
        "source_contract_months":rows,
    }


def extract_first_page_pdf(pdf_bytes:bytes)->str:
    if not isinstance(pdf_bytes,bytes) or not MIN_PDF<=len(pdf_bytes)<=MAX_PDF or not pdf_bytes.startswith(b"%PDF-"):
        raise CMEStop("Missing, oversized or wrong-content original CME PDF bytes.")
    with TemporaryDirectory() as td:
        src=Path(td)/"source.pdf"
        src.write_bytes(pdf_bytes)
        try:
            p=subprocess.run(
                ["pdftotext","-f","1","-l","1","-layout",str(src),"-"],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=18,check=False,
            )
        except (FileNotFoundError,subprocess.TimeoutExpired) as exc:
            raise CMEStop("Original CME source extraction dependency unavailable.") from exc
        if p.returncode!=0 or not p.stdout:
            raise CMEStop("Original CME PDF first page cannot be read safely.")
        try:
            return p.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CMEStop("Corrupted CME source text encoding.") from exc


def inspect(pdf_bytes:bytes,*,acquired_utc:str)->dict:
    text=extract_first_page_pdf(pdf_bytes)
    result=parse_first_page(text,acquired_utc=acquired_utc)
    result["original_pdf_sha256"]=sha256(pdf_bytes).hexdigest()
    result["original_pdf_byte_count"]=len(pdf_bytes)
    result["original_first_page_extracted_sha256"]=sha256(text.encode()).hexdigest()
    return result


def original_one_get()->bytes:
    req=Request(SOURCE,headers={
        "User-Agent":"Fund100-Official-Public-CME-Source-Research/1.0",
        "Accept":"application/pdf",
    },method="GET")
    try:
        with urlopen(req,timeout=35) as resp:
            if resp.status!=200 or resp.geturl()!=SOURCE:
                raise CMEStop("CME source response redirect or not 200; no proxy.")
            data=resp.read(MAX_PDF+1)
    except (HTTPError,URLError,TimeoutError) as exc:
        raise CMEStop("Original official CME PDF unavailable: "+type(exc).__name__) from exc
    if len(data)>MAX_PDF:
        raise CMEStop("CME original PDF source oversized.")
    return data


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-json",type=Path,required=True)
    p.add_argument("--output-pdf",type=Path,required=True)
    a=p.parse_args()
    raw=original_one_get()
    acquisition=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=inspect(raw,acquired_utc=acquisition)
    for path in (a.output_json,a.output_pdf):
        path.parent.mkdir(parents=True,exist_ok=True)
    a.output_pdf.write_bytes(raw)
    a.output_json.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    f,n=result["source_contract_months"][:2]
    print("OFFICIAL CME FINAL",result["original_trade_date"],
          "BULLETIN",result["original_bulletin_id"],
          "SOURCE_SHA",result["original_pdf_sha256"])
    print("CL_NEAR",f["contract_month"],f["settlement_usd_per_barrel"],
          "CL_NEXT",n["contract_month"],n["settlement_usd_per_barrel"],
          "FRONT_MINUS_NEXT",result["front_next_month_spread_usd_per_barrel"],
          "CURVE",result["front_next_curve_shape"],
          "CONTRACTS",result["contract_month_count"],
          "OI_RECONCILED",result["sum_verified"],
          "STALE",result["stale_for_current_market_read"])
    print("SINGLE DATED CURVE ONLY. NO CARRY PNL. NO SOURCE PUBLICATION CLOCK. NO BROKER ORDERS.")


if __name__=="__main__":
    main()

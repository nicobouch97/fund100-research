"""C8 CME Daily Bulletin ORIGINAL SOURCE status and rejection fingerprint.

CME's rotating /current/ PDF can contain PRELIMINARY or stale FINAL.
Preserve evidence of the raw bytes seen WITHOUT admitting PRELIMINARY
prices, archiving its proprietary raw PDF, or inventing missing curves.
No Alpaca, broker, paid subscription, historical return or order code.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_cme_section61_original_c7_v1_0 as c7

SCHEMA="FUND100_C8_CME_SOURCE_ADMISSION_STATUS_V1"
SOURCE=c7.SOURCE
READ_LIMIT=c7.MAX_PDF
STATUS_RE=re.compile(r"(?m)^\s*(PRELIMINARY|FINAL)\s*$",re.I)


def _base(acquired_utc:str)->dict:
    c7._utc(acquired_utc)
    return {
        "schema":SCHEMA,
        "official_rotating_source_url":SOURCE,
        "source_class":"CME_OFFICIAL_PUBLIC_REFERENCE_BULLETIN",
        "acquired_at_utc":acquired_utc,
        "source_url_immutable":False,
        "http_cache_bypass_requested":True,
        "source_authentic_publication_timestamp_independently_verified":False,
        "vendor_license_or_data_redistribution_rights_verified":False,
        "one_date_is_not_historical_earned_carry":True,
        "independent_historical_settlement_return_series":False,
        "broker_orders":0,
        "operator_authorized_etf_liquidation":False,
        "operator_authorized_new_futures":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def _header(first_page:str)->tuple[str|None,str|None,int|None]:
    """Read identity/status before any settlement parsing, including draft PDFs."""
    if not isinstance(first_page,str) or len(first_page)<200:
        return None,None,None
    header=first_page[:1800]
    if "CME GROUP" not in header.upper() or "ENERGY FUTURES PRODUCTS" not in header.upper():
        return None,None,None
    m=c7.DOC_DATE.search(header)
    status=STATUS_RE.search(header)
    date=None
    bulletin=None
    if m:
        try:
            d=datetime.strptime(f"{m.group(3)} {m.group(4)} {m.group(5)}","%b %d %Y").date()
        except ValueError:
            d=None
        if d and d.strftime("%a").lower()==m.group(2).lower()[:3]:
            date=d.isoformat()
            bulletin=int(m.group(1))
    return status.group(1).upper() if status else None,date,bulletin


def evaluate_raw(raw:bytes,*,acquired_utc:str)->dict:
    """Returns a JSON-serializable status even when PDF must be refused."""
    report=_base(acquired_utc)
    report["original_body_received"]=isinstance(raw,bytes)
    report["original_pdf_sha256"]=sha256(raw).hexdigest() if isinstance(raw,bytes) else None
    report["original_pdf_byte_count"]=len(raw) if isinstance(raw,bytes) else 0
    report["original_pdf_archived"]=False
    report["admitted_contract_curve"]=False
    report["source_admission_status"]="REJECT_INVALID_SOURCE"
    report["source_admission_reason"]="Original content failed identity or PDF integrity."
    report["printed_original_trade_date"]=None
    report["printed_original_status"]=None
    report["printed_bulletin_id"]=None
    report["futures_settlement_values_present_in_report"]=False
    if not isinstance(raw,bytes) or not c7.MIN_PDF<=len(raw)<=READ_LIMIT or not raw.startswith(b"%PDF-"):
        return report
    try:
        extracted=c7.extract_first_page_pdf(raw)
        report["original_first_page_text_sha256"]=sha256(extracted.encode()).hexdigest()
    except c7.CMEStop as exc:
        report["source_admission_reason"]="PDF extraction rejected: "+str(exc)
        return report
    status,date,bulletin=_header(extracted)
    report["printed_original_trade_date"]=date
    report["printed_original_status"]=status
    report["printed_bulletin_id"]=bulletin
    if not date or not status or not bulletin:
        report["source_admission_reason"]="CME original dated product/header/status could not be reconciled."
        return report
    if status!="FINAL":
        report["source_admission_status"]="REJECT_PRELIMINARY"
        report["source_admission_reason"]="Original CME document is PRELIMINARY, not a final settlement."
        return report
    try:
        admitted=c7.inspect(raw,acquired_utc=acquired_utc)
    except c7.CMEStop as exc:
        report["source_admission_status"]="REJECT_FINAL_SOURCE_INVALID"
        report["source_admission_reason"]="FINAL PDF failed contract, staleness or open-interest validation: "+str(exc)
        return report
    # One source document never means a measured futures carry/roll return.
    if admitted["original_pdf_sha256"]!=report["original_pdf_sha256"]:
        report["source_admission_reason"]="SHA mismatch between provenance and original PDF."
        return report
    report["source_admission_status"]="ACCEPT_FINAL_SOURCE_ONLY"
    report["source_admission_reason"]="Dated FINAL CME futures curve passed C7 validations."
    report["admitted_contract_curve"]=True
    report["original_pdf_archived"]=True
    report["futures_settlement_values_present_in_report"]=True
    report["admitted_final_curve"]=admitted
    return report


def no_source(*,acquired_utc:str,reason:str)->dict:
    report=_base(acquired_utc)
    report.update({
        "source_admission_status":"REJECT_SOURCE_UNAVAILABLE",
        "source_admission_reason":reason,
        "original_body_received":False,
        "original_pdf_sha256":None,
        "original_pdf_byte_count":0,
        "original_pdf_archived":False,
        "admitted_contract_curve":False,
        "printed_original_trade_date":None,
        "printed_original_status":None,
        "printed_bulletin_id":None,
        "futures_settlement_values_present_in_report":False,
    })
    return report


def one_public_request()->bytes:
    """One bounded official GET; cache control is requested, not guaranteed."""
    req=Request(SOURCE,method="GET",headers={
        "User-Agent":"Fund100-Exchange-Source-Provenance/1.0",
        "Accept":"application/pdf",
        "Cache-Control":"no-cache, no-store, max-age=0",
        "Pragma":"no-cache",
    })
    with urlopen(req,timeout=30) as response:
        if response.status!=200 or response.geturl()!=SOURCE:
            raise c7.CMEStop("Unexpected CME HTTP status or redirected response URL.")
        data=response.read(READ_LIMIT+1)
    if len(data)>READ_LIMIT:
        raise c7.CMEStop("Official PDF exceeds bounded source size.")
    return data


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--output-status-json",type=Path,required=True)
    p.add_argument("--output-final-pdf",type=Path,required=True)
    args=p.parse_args()
    acquired=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    original=None
    try:
        original=one_public_request()
        result=evaluate_raw(original,acquired_utc=acquired)
    except (HTTPError,URLError,TimeoutError,c7.CMEStop) as exc:
        result=no_source(acquired_utc=acquired,reason=f"Original public CME GET failed ({type(exc).__name__}).")
    args.output_status_json.parent.mkdir(parents=True,exist_ok=True)
    args.output_status_json.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    # Never write raw rejected or preliminary bytes to artifact / filesystem.
    if result["source_admission_status"]=="ACCEPT_FINAL_SOURCE_ONLY":
        args.output_final_pdf.parent.mkdir(parents=True,exist_ok=True)
        args.output_final_pdf.write_bytes(original)
    print("ORIGINAL_CME_SOURCE_STATUS",result["source_admission_status"])
    print("DOCUMENT_DATE",result["printed_original_trade_date"],
          "PRINTED_STATUS",result["printed_original_status"],
          "BULLETIN",result["printed_bulletin_id"],
          "SHA256",result["original_pdf_sha256"])
    print("ADMITTED_TO_RESEARCH",result["admitted_contract_curve"],
          "NO_CARRY_ESTIMATE",result["one_date_is_not_historical_earned_carry"],
          "BROKER_ORDERS",result["broker_orders"])


if __name__=="__main__":
    main()

"""P4AA original Twitter 2022 official SEC merger entitlement reconciliation.

A 2022 delisted security is neither worth ZERO nor last-trade sale
proceeds. This audit associates the official completed cash merger
right with an independently source-hashed real sample of TWTR trading
bars, without assuming when a custodian made cash available.

ONLY ex-post descriptive provenance. This Oct-2022 SEC filing was
obtained for research in 2026; it cannot retroactively make a strategy's
October 2022 decision causal, prove actual shareholder cash settlement,
create a point-in-time listed universe, or authorize broker orders.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

import fund100_stock_delisted_sample_p4z_v1_0 as p4z

SCHEMA="FUND100_P4AA_OFFICIAL_SEC_TWTR_2022_CASH_MERGER_RIGHT_V1"
ORIGINAL_8K_URL=(
    "https://www.sec.gov/Archives/edgar/data/1418091/"
    "000119312522272772/d411753d8k.htm")
ORIGINAL_SEC_CIK=1418091
ORIGINAL_SEC_ACCESSION="0001193125-22-272772"
ORIGINAL_REPORT_EVENT_DATE="2022-10-27"
CASH_RIGHT_USD="54.20"
ORIGINAL_THIRD_PARTY_SAMPLE_SHA256=(
    "3640e34b8de32d86a3e1fd83e68e99013e5c130f72ed3a93287a2b651b24f843")
MAX_SEC_BYTES=2_000_000
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class MergerEvidenceStop(ValueError):pass

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.words=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):
            self.skip+=1
    def handle_endtag(self,tag):
        if tag in ("script","style"):
            self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if self.skip==0:self.words.append(data)

def _original_document(raw:bytes):
    if type(raw) is not bytes or not 650<=len(raw)<=MAX_SEC_BYTES:
        raise MergerEvidenceStop("Missing or unbounded fixed original SEC merger filing")
    try:
        decoded=raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MergerEvidenceStop("Unexpected original SEC source encoding") from exc
    parser=_Text()
    try:
        parser.feed(decoded)
        parser.close()
    except Exception as exc:
        raise MergerEvidenceStop("Unparseable original SEC 8-K HTML") from exc
    content=re.sub(r"\s+"," ",unescape(" ".join(parser.words))).strip()
    header=content[:2500]
    if (not re.search(r"\bFORM\s+8-K\b",header,re.I)
        or not re.search(r"\bTwitter,\s*Inc\.",header,re.I)
        or "001-36164" not in header
        or not re.search(r"\bTWTR\b",content[:6500])
        or not re.search(r"Date of Report.{0,90}October\s+27,\s*2022",header,re.I)):
        raise MergerEvidenceStop("Original issuer, 8-K report, class or event date mismatched")
    intro=re.search(
        r"Introductory Note\s+(.*?)\s+Item\s+1\.01",content,re.I|re.S)
    if intro is None:
        raise MergerEvidenceStop("Original source merger introductory disclosure missing")
    event=intro.group(1)
    if (not re.search(
        r"On October\s+27,\s*2022.{0,300}merged with and into Twitter",
        event,re.I)
        or not re.search(r"each issued and outstanding share of Twitter",
                         event,re.I)
        or not re.search(
            r"common stock.{0,250}(?:canceled|cancelled) and converted "
            r"into the right to receive \$(54\.20) in cash, without interest",
            event,re.I|re.S)):
        raise MergerEvidenceStop("Unverified completed merger per-share legal entitlement")
    item2=re.search(
        r"Item\s+2\.01.{0,130}Completion of Acquisition or Disposition "
        r"of Assets.{0,350}October\s+27,\s*2022.{0,150}"
        r"Merger was consummated",content,re.I|re.S)
    if item2 is None:
        raise MergerEvidenceStop("SEC Item 2.01 does not confirm consummated merger")
    item3=re.search(
        r"Item\s+3\.01.{0,160}Notice of Delisting.{0,550}"
        r"trading of Twitter.{0,130}was suspended prior to the opening "
        r"of the NYSE on October\s+28,\s*2022",content,re.I|re.S)
    if item3 is None:
        raise MergerEvidenceStop("Cannot independently confirm last trading-session boundary")
    amounts=set(re.findall(r"(?:right to receive|Merger Consideration).*?\$(\d+\.\d{2}) "
                           r"in cash",event,re.I|re.S))
    if amounts!={CASH_RIGHT_USD}:
        raise MergerEvidenceStop("Merger consideration ambiguous or changed")
    return {
        "official_sec_original_filing_sha256":sha256(raw).hexdigest(),
        "issuer_name":"Twitter, Inc.",
        "official_sec_cik":ORIGINAL_SEC_CIK,
        "original_sec_accession":ORIGINAL_SEC_ACCESSION,
        "legal_event_date":ORIGINAL_REPORT_EVENT_DATE,
        "ordinary_share_symbol":"TWTR",
        "eligible_common_share_merger_right_usd":CASH_RIGHT_USD,
        "different_equity_award_and_excluded_share_treatment":True,
        "delisting_trading_suspension_from":"2022-10-28",
        "original_sec_item_2_01_verified":True,
        "original_sec_item_3_01_verified":True,
    }

def reconcile(official_8k:bytes,p4z_report:dict)->dict:
    claim=_original_document(official_8k)
    if (type(p4z_report) is not dict
        or p4z_report.get("schema")!=p4z.SCHEMA
        or p4z_report.get("original_zip_sha256")!=ORIGINAL_THIRD_PARTY_SAMPLE_SHA256
        or p4z_report.get("twtr_last_trading_bar")!=ORIGINAL_REPORT_EVENT_DATE
        or p4z_report.get("twtr_source_delisting_label")!="2022-10-31"
        or p4z_report.get("twtr_terminal_shareholder_proceeds_usd") is not None
        or p4z_report.get("twtr_post_delisting_total_return") is not None
        or p4z_report.get("four_chosen_names_not_historical_point_in_time_universe") is not True
        or p4z_report.get("broker_gets")!=0
        or p4z_report.get("broker_posts")!=0
        or p4z_report.get("broker_orders")!=0
        or p4z_report.get("trading_authorized") is not False):
        raise MergerEvidenceStop("Original delisted-stock sample not source pinned")
    listings=p4z_report.get("listings")
    if not isinstance(listings,list) or len(listings)!=4:
        raise MergerEvidenceStop("Original sample identities unavailable")
    twtr=[x for x in listings if type(x) is dict and x.get("symbol")=="TWTR"]
    if (len(twtr)!=1 or twtr[0].get("last_price_date")!=ORIGINAL_REPORT_EVENT_DATE
        or twtr[0].get("archive_delisting_label")!="2022-10-31"
        or not isinstance(twtr[0].get("daily_source_sha256"),str)
        or not re.fullmatch(r"[0-9a-f]{64}",twtr[0]["daily_source_sha256"])):
        raise MergerEvidenceStop("Official merger does not match delisted source security")
    return {
        "schema":SCHEMA,
        "status":"OFFICIAL_LEGAL_CASH_RIGHT_MATCHED_NO_SETTLED_CASH_ASSUMPTION",
        "official_sec_original_url":ORIGINAL_8K_URL,
        "source_sha256":claim["official_sec_original_filing_sha256"],
        "original_sample_sha256":p4z_report["original_zip_sha256"],
        "original_sample_twtr_daily_sha256":twtr[0]["daily_source_sha256"],
        "official_claim":claim,
        "per_eligible_common_share_merger_entitlement_usd":CASH_RIGHT_USD,
        "share_cancelled_at_completed_merger_not_sold_at_last_bar":True,
        "last_vendor_price_bar_session":"2022-10-27",
        "confirmed_no_trading_from":"2022-10-28",
        "source_vendor_file_delisting_label":"2022-10-31",
        "cash_right_known_ex_post_only":True,
        "actual_shareholder_eligibility_or_exclusions_verified":False,
        "shareholder_broker_receipt_date_utc":None,
        "shareholder_settled_cash_available_date_utc":None,
        "cash_settlement_or_reinvestment_in_2022_authorized":False,
        "entry_price_or_actual_share_quantities_available":False,
        "historical_security_master_or_delisting_completeness_established":False,
        "historical_strategy_alpha_test_eligible":False,
        "original_v5_live_ceiling_usd":"130.30",
        "original_operator_and_environment_stop_not_changed":True,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,"trading_authorized":LIVE_AUTHORIZED,
    }

def official_sec_get(agent:str)->bytes:
    if type(agent) is not str or not 10<=len(agent)<=240:
        raise MergerEvidenceStop("Configured SEC requester identity unavailable")
    req=Request(ORIGINAL_8K_URL,headers={
        "User-Agent":agent,"Accept":"text/html"})
    try:
        with urlopen(req,timeout=30) as response:
            if (response.status!=200 or response.url!=ORIGINAL_8K_URL
                or response.headers.get("Content-Type","").split(";")[0]
                   not in ("text/html","application/xhtml+xml")):
                raise MergerEvidenceStop("Original SEC response unexpected")
            raw=response.read(MAX_SEC_BYTES+1)
    except (OSError,TimeoutError) as exc:
        raise MergerEvidenceStop("Official SEC source unavailable, no fallback") from exc
    _original_document(raw)
    return raw

def main():
    import os
    args=argparse.ArgumentParser()
    args.add_argument("--original-vendor-zip",type=Path,required=True)
    args.add_argument("--output",type=Path,required=True)
    a=args.parse_args()
    report=p4z.audit_zip(a.original_vendor_zip)
    raw=official_sec_get(os.environ.get("SEC_USER_AGENT",""))
    doc=reconcile(raw,report)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    print(doc["status"],"legal right",doc["per_eligible_common_share_merger_entitlement_usd"])
    print("SEC source hash",doc["source_sha256"])
    print("Cash available date unknown. NO reallocation, live orders or alpha.")
if __name__=="__main__":main()

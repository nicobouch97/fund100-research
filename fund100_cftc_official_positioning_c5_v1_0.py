"""C5 original official 2026 CFTC disaggregated Futures Only source review.

This measures GOLD/WTI managed-money crowding, NOT futures prices, roll
yield, historical original publication timing, alpha or permissions.
Absolutely NO broker/network writes. No LIVE/PAPER order interface.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from zipfile import ZipFile,BadZipFile
import pandas as pd

SCHEMA="FUND100_C5_ORIGINAL_CFTC_MANAGED_MONEY_FUTURES_ONLY_V1"
SOURCE="https://www.cftc.gov/files/dea/history/fut_disagg_txt_2026.zip"
SOURCE_HTML="https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm"
MAX_ZIP=25_000_000
MAX_UNPACKED=80_000_000
FIELDS={
    "date":"As_of_Date_Form_YYYY-MM-DD",
    "code":"CFTC_Contract_Market_Code",
    "name":"Market_and_Exchange_Names",
    "open_interest":"Open_Interest_All",
    "long":"M_Money_Positions_Long_All",
    "short":"M_Money_Positions_Short_All",
}
MARKETS={"088691":"COMEX_GOLD","067651":"NYMEX_LIGHT_SWEET_WTI"}
MARKET_NAME={"088691":"GOLD","067651":"CRUDE"}
MIN_WEEKS=2


class CFTCStop(ValueError):
    pass


def utc_capture(s:str)->datetime:
    if not isinstance(s,str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",s):
        raise CFTCStop("Canonical acquisition UTC required.")
    try:
        return datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CFTCStop("Invalid source acquisition datetime.") from exc


def original_annual_zip(raw:bytes)->pd.DataFrame:
    if not isinstance(raw,bytes) or not 100<=len(raw)<=MAX_ZIP:
        raise CFTCStop("Official original CFTC 2026 compressed archive missing/too large.")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            entries=[i for i in archive.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
            if len(entries)!=1 or not re.fullmatch(r"[^/\\]+[.](?:txt|csv)",entries[0].filename,re.I):
                raise CFTCStop("CFTC archive does not contain exactly one plain official report text file.")
            member=entries[0]
            if member.file_size<=0 or member.file_size>MAX_UNPACKED:
                raise CFTCStop("CFTC source decompression exceeds bound.")
            original=archive.read(member)
            if len(original)!=member.file_size:
                raise CFTCStop("CFTC ZIP source truncated.")
    except (BadZipFile,OSError,RuntimeError) as exc:
        raise CFTCStop("Invalid source ZIP; never substitute synthetic CFTC figures.") from exc
    try:
        data=pd.read_csv(BytesIO(original),dtype=str,encoding="utf-8-sig",low_memory=False)
    except (UnicodeError,ValueError,pd.errors.ParserError) as exc:
        raise CFTCStop("CFTC original source CSV parse failed.") from exc
    data.columns=[s.strip().replace("\ufeff","") for s in data.columns]
    if not set(FIELDS.values()).issubset(data.columns):
        raise CFTCStop("Official CFTC disaggregated source columns missing.")
    if len(data)<100 or len(data)>500_000:
        raise CFTCStop("Expected nonempty entire-market official 2026 report.")
    if "FutOnly_or_Combined" in data.columns:
        all_modes={str(v).strip().upper() for v in data["FutOnly_or_Combined"].dropna().unique()}
        if any("COMB" in s for s in all_modes):
            raise CFTCStop("Combined options observations must not enter Futures Only.")
    selected=data[data[FIELDS["code"]].str.strip().isin(MARKETS)].copy()
    if selected.empty:
        raise CFTCStop("No original market identities match CFTC gold/WTI.")
    return selected


def _whole_contract(value:object,name:str)->int:
    if not isinstance(value,str) or not re.fullmatch(r"\s*\d{1,12}\s*",value):
        raise CFTCStop(f"Invalid CFTC futures contract count ({name}).")
    return int(value.strip())


def position_records(data:pd.DataFrame,observed_utc:str)->dict:
    observed=utc_capture(observed_utc)
    if not isinstance(data,pd.DataFrame) or not set(FIELDS.values()).issubset(data.columns):
        raise CFTCStop("Missing CFTC source columns.")
    market_rows={code:[] for code in MARKETS}
    for row in data.to_dict(orient="records"):
        code=str(row[FIELDS["code"]]).strip()
        if code not in MARKETS:
            raise CFTCStop("Unapproved CFTC contract market identity.")
        if MARKET_NAME[code] not in str(row[FIELDS["name"]]).upper():
            raise CFTCStop("Market CFTC code/name mismatch (possibly substituted product).")
        rawdate=str(row[FIELDS["date"]]).strip()
        dt=None
        for fmt in ("%Y-%m-%d","%m/%d/%Y"):
            try:
                dt=datetime.strptime(rawdate,fmt)
                break
            except ValueError:
                pass
        if dt is None or dt.year!=2026 or dt.weekday()!=1:
            raise CFTCStop("Invalid as-of Tuesday in 2026 official futures report.")
        if dt.date()>=observed.date():
            raise CFTCStop("CFTC position date not earlier than source acquisition.")
        oi=_whole_contract(row[FIELDS["open_interest"]],"open_interest")
        l=_whole_contract(row[FIELDS["long"]],"managed_money_long")
        s=_whole_contract(row[FIELDS["short"]],"managed_money_short")
        if oi<=0 or l>oi or s>oi:
            raise CFTCStop("Invalid futures OI or managed-money position share.")
        market_rows[code].append({
            "position_asof_tuesday":dt.date().isoformat(),
            "managed_money_long_contracts":l,
            "managed_money_short_contracts":s,
            "managed_money_net_contracts":l-s,
            "all_market_open_interest_contracts":oi,
            "managed_money_net_share_of_oi":round((l-s)/oi,7),
        })
    out={}
    for code,rows in market_rows.items():
        rows.sort(key=lambda r:r["position_asof_tuesday"])
        if len(rows)<MIN_WEEKS or len({r["position_asof_tuesday"] for r in rows})!=len(rows):
            raise CFTCStop("Missing two independent weeks or duplicate report dates.")
        a,b=rows[-2:]
        if (datetime.fromisoformat(b["position_asof_tuesday"])
            -datetime.fromisoformat(a["position_asof_tuesday"])).days not in (7,14,21):
            raise CFTCStop("Unexpected missing intervening CFTC reporting weeks.")
        out[MARKETS[code]]={
            "contract_market_code":code,
            "weeks_observed":len(rows),
            "first_position_date":rows[0]["position_asof_tuesday"],
            "last_position_date":b["position_asof_tuesday"],
            "last_week":b,
            "week_before":a,
            "net_contract_change_last_week":b["managed_money_net_contracts"]-a["managed_money_net_contracts"],
            "net_oi_share_change_last_week":round(b["managed_money_net_share_of_oi"]-a["managed_money_net_share_of_oi"],7),
            "contract_expiry_dates_known":False,
            "futures_price_and_realized_roll_return_known":False,
        }
    return out


def audit(raw:bytes,*,acquired_utc:str)->dict:
    originals=original_annual_zip(raw)
    features=position_records(originals,acquired_utc)
    return {
        "schema":SCHEMA,
        "status":"OFFICIAL_2026_CFTC_FUTURES_ONLY_POSITIONING_NOT_CARRY_RESEARCH",
        "cftc_official_source_url":SOURCE,
        "cftc_catalogue_url":SOURCE_HTML,
        "original_archive_sha256":sha256(raw).hexdigest(),
        "original_archive_size_bytes":len(raw),
        "acquired_at_utc":acquired_utc,
        "current_annual_compilation_is_not_original_weekly_publication_vintage":True,
        "actual_historical_report_publication_times_verified":False,
        "historical_2025_cftc_funding_shutdown_release_delays_accounted_for":False,
        "actual_futures_expiry_settlements_captured":False,
        "independently_measured_futures_roll_yield":False,
        "dbc_etf_positions_mapped_to_cftc_contracts":False,
        "stock_or_etf_alpha_measured":False,
        "contract_markets":features,
        "broker_orders":0,
        "operator_authorized_etf_liquidation":False,
        "trading_authorized":False,
        "paper_authorized":False,
        "live_authorized":False,
    }


def download()->bytes:
    request=Request(SOURCE,headers={
        "User-Agent":"Fund100-Original-CFTC-Public-Research/1.0",
        "Accept":"application/zip,application/octet-stream",
    },method="GET")
    try:
        with urlopen(request,timeout=30) as response:
            if response.status!=200 or response.geturl()!=SOURCE:
                raise CFTCStop("Official CFTC URL changed or response not 200.")
            raw=response.read(MAX_ZIP+1)
    except (HTTPError,URLError,TimeoutError) as exc:
        raise CFTCStop(f"Official CFTC ZIP unreachable: {type(exc).__name__}; NO substitute data.") from exc
    if len(raw)>MAX_ZIP:
        raise CFTCStop("Original CFTC ZIP too large.")
    return raw


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--output-json",required=True,type=Path)
    p.add_argument("--output-zip",required=True,type=Path)
    args=p.parse_args()
    raw=download()
    captured=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report=audit(raw,acquired_utc=captured)
    for path in (args.output_json,args.output_zip):
        path.parent.mkdir(parents=True,exist_ok=True)
    args.output_zip.write_bytes(raw)
    args.output_json.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    for name,record in report["contract_markets"].items():
        print(name,"latest Tuesday",record["last_position_date"],
              "MM_NET_CONTRACTS",record["last_week"]["managed_money_net_contracts"],
              "MM_NET_SHARE_OI",record["last_week"]["managed_money_net_share_of_oi"],
              "WEEK_CHANGE",record["net_contract_change_last_week"])
    print("OFFICIAL FUTURES POSITIONING ONLY. NO CONTRACT EXPIRIES, NO CARRY, NO BROKER ORDERS.")


if __name__=="__main__":
    main()

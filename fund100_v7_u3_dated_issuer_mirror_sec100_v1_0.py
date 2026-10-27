"""V7 U3: issuer-ATTRIBUTED third-party IVV holdings mirror + official SEC CIK.

The original direct iShares CSV endpoint returned a 2.3 MB HTML page on
2026-10-27. Never pretend that was independently replayed issuer data.
An explicitly weaker, issuer-ATTRIBUTED CC BY 4.0 third-party mirror can
still preregister a genuine prospective event-surveillance population.
No retrospective alpha or order routing results. All securities 2026-sourced.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal,InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

import fund100_v7_u1_original_ivv_100_issuer_freeze_v1_0 as original

SCHEMA="FUND100_V7_U3_THIRD_PARTY_ISSUER_ATTRIBUTED_IVV_SEC_100_WATCH_V1"
MIRROR_URL="https://tickerinside.com/api/v1/fund/ivv.json"
OFFICIAL_SEC_URL=original.ORIGINAL_SEC_TICKERS_URL
FIRST_REGISTRATION_UTC="2026-10-27T16:30:00Z"
MIN_HOLDINGS=450
MAX_HOLDINGS=550
MAX_SOURCE_BYTES=600_000
MAX_SOURCE_AGE_DAYS=8
TARGET_ISSUERS=100
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_ENABLED=False

class MirrorStop(ValueError): pass

def _stamp(value:str):
    try:
        return original._stamp(value)
    except original.UniverseStop as e:
        raise MirrorStop("Invalid real source acquisition UTC") from e

def _source_day(raw:str):
    if type(raw) is not str or re.fullmatch(r"20\d\d-\d\d-\d\d",raw) is None:
        raise MirrorStop("No original dated holdings at mirror")
    try:
        return datetime.strptime(raw,"%Y-%m-%d").date()
    except ValueError:
        raise MirrorStop("Impossible provider holdings date") from None

def _weight(v):
    if type(v) not in (int,float) or isinstance(v,bool):
        raise MirrorStop("Mirror source missing numeric provider fund weight")
    try:
        n=Decimal(str(v))
    except (ValueError,InvalidOperation):
        raise MirrorStop("Invalid mirror weight") from None
    if not n.is_finite() or n<0 or n>Decimal("20"):
        raise MirrorStop("Unbounded provider-attributed weight")
    return n

def freeze(*,mirror_bytes:bytes,official_sec_ticker_bytes:bytes,
           acquired_utc:str):
    captured=_stamp(acquired_utc)
    if captured<_stamp(FIRST_REGISTRATION_UTC):
        raise MirrorStop("Prospective registration preceded original mirror receipt")
    if type(mirror_bytes) is not bytes or not 5000<=len(mirror_bytes)<=MAX_SOURCE_BYTES:
        raise MirrorStop("Mirror original JSON source missing/oversized")
    try:
        content=json.loads(mirror_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError,ValueError):
        raise MirrorStop("Mirror bytes are not original JSON") from None
    if (type(content) is not dict or content.get("ticker")!="IVV"
        or content.get("source_layer")!="issuer"
        or content.get("license")!="CC BY 4.0"
        or content.get("positions") not in range(MIN_HOLDINGS,MAX_HOLDINGS+1)
        or type(content.get("cite_as")) is not str
        or "iShares" not in content["cite_as"]
        or "2026-" not in content["cite_as"]
        or "https://tickerinside.com/etf/ivv/" not in content["cite_as"]
        or content.get("page_url")!="https://tickerinside.com/etf/ivv/"):
        raise MirrorStop("Unverified IVV and third-party issuer-attribution identity")
    held_date=_source_day(content.get("holdings_as_of"))
    if not 0<=(captured.date()-held_date).days<=MAX_SOURCE_AGE_DAYS:
        raise MirrorStop("Mirror is future-dated or stale at actual acquisition")
    if (type(content.get("category")) is not dict
        or content["category"].get("asset_class")!="equity"
        or content["category"].get("as_of")!=held_date.isoformat()
        or type(content.get("holdings")) is not dict
        or len(content["holdings"])!=content["positions"]
        or len(content["holdings"])<MIN_HOLDINGS):
        raise MirrorStop("Mirrored issuer-holdings not a complete equity index book")
    ciks=original._sec_map(official_sec_ticker_bytes)
    entries=[]
    seen=set()
    total=Decimal(0)
    for ticker,value in content["holdings"].items():
        if (type(ticker) is not str
            or re.fullmatch(r"[A-Z][A-Z0-9.]{0,12}",ticker) is None
            or ticker in seen):
            raise MirrorStop("Invalid or duplicate mirrored listed security")
        seen.add(ticker)
        w=_weight(value)
        total+=w
        if w>0:
            entries.append((ticker.replace(".","-"),w,ticker))
    if not Decimal("94")<=total<=Decimal("102"):
        raise MirrorStop("Mirrored IVV constituent weights fail source completeness")
    entries.sort(key=lambda x:(-x[1],x[0]))
    selected=[]
    seen_cik=set()
    skipped=0
    for symbol,weight,mirror_symbol in entries:
        cik=ciks.get(symbol)
        if not cik:
            skipped+=1
            continue
        if cik in seen_cik:
            continue
        seen_cik.add(cik)
        selected.append({
            "ticker":symbol,
            "sec_cik_10_digit":cik,
            "original_issuer_attributed_weight_percent":format(weight,"f"),
            "mirror_security_identifier":mirror_symbol,
            "top_weight_rank":len(selected)+1,
            "issuer_attributed_mirror_not_raw_issuer_verified":True,
            "no_broker_instrument_permission":True,
        })
        if len(selected)==TARGET_ISSUERS:
            break
    if len(selected)!=TARGET_ISSUERS:
        raise MirrorStop("No verified distinct 100 CIK mapping from dated mirror")
    return {
        "schema":SCHEMA,
        "status":"PROSPECTIVELY_FROZEN_THIRD_PARTY_IVV_100_ISSUERS_NOT_AN_ALPHA_SIGNAL",
        "mirror_original_snapshot_url":MIRROR_URL,
        "mirror_attribution_page_url":content["page_url"],
        "mirror_attribution_license":"CC BY 4.0",
        "source_is_direct_official_ishares_file":False,
        "third_party_provider_claims_issuer_source_layer":True,
        "mirror_dated_issuer_attributed_holdings_asof":held_date.isoformat(),
        "prospective_registration_utc":FIRST_REGISTRATION_UTC,
        "actual_original_mirror_and_sec_acquisition_utc":acquired_utc,
        "exact_mirror_original_json_sha256":sha256(mirror_bytes).hexdigest(),
        "exact_SEC_original_ticker_bytes_sha256":
            sha256(official_sec_ticker_bytes).hexdigest(),
        "SEC_original_ticker_map_url":OFFICIAL_SEC_URL,
        "source_reported_positions":content["positions"],
        "source_reported_weight_total_percent":format(total,"f"),
        "first_100_distinct_SEC_CIK_mapped_issuer_roster":selected,
        "unmapped_mirror_symbols_skipped_before_100":skipped,
        "top100_chosen_by_dated_existing_fund_weight_not_future_returns":True,
        "direct_issuer_source_unavailable_at_first_attempt":True,
        "only_forward_post_registration_events_eligible_for_future_research":True,
        "issuer_identity_not_share_class_or_broker_eligibility":True,
        "independently_validated_first_public_reception_earnings_signals":0,
        "observed_new_future_returns":0,
        "historical_investable_universe":False,
        "no_predictive_alpha_evidence":True,
        "original_live_trial_cap_usd":"130.30",
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,"live_authorized":False,
    }

def acquire_original(*,contact_agent:str):
    if type(contact_agent) is not str or len(contact_agent)<10:
        raise MirrorStop("SEC official identity required")
    # The source is explicitly a third-party MIRROR, not iShares bytes.
    mirror=original._fetch(MIRROR_URL,contact_agent,MAX_SOURCE_BYTES)
    sec=original._fetch(OFFICIAL_SEC_URL,contact_agent,original.MAX_SEC_MAP_BYTES)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return freeze(mirror_bytes=mirror,official_sec_ticker_bytes=sec,
                  acquired_utc=now),mirror,sec

def main():
    import argparse,os
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise MirrorStop("Never replace first frozen original mirror source")
    d,mirror,sec=acquire_original(contact_agent=os.getenv("SEC_USER_AGENT",""))
    a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/"first-vintage-third-party-IVV-snapshot.json").write_bytes(mirror)
    (a.output_dir/"first-vintage-official-SEC-ticker-map.json").write_bytes(sec)
    (a.output_dir/"U3-first-100-issuer-research-roster.json").write_text(
        json.dumps(d,sort_keys=True,indent=2)+"\n")
    reread=freeze(
        mirror_bytes=(a.output_dir/"first-vintage-third-party-IVV-snapshot.json").read_bytes(),
        official_sec_ticker_bytes=(a.output_dir/"first-vintage-official-SEC-ticker-map.json").read_bytes(),
        acquired_utc=d["actual_original_mirror_and_sec_acquisition_utc"])
    if d!=reread:
        raise MirrorStop("Original dated source can no longer reproduce first 100 issuers")
    print("Mirrored IVV source date",d["mirror_dated_issuer_attributed_holdings_asof"])
    print("SEC identified distinct issuer sources",len(d["first_100_distinct_SEC_CIK_mapped_issuer_roster"]))
    print("This is issuer-ATTRIBUTED MIRROR, not directly verified original iShares.")
    print("NO trading, no proven strategy alpha, original LIVE STOP stays engaged.")

if __name__=="__main__":main()

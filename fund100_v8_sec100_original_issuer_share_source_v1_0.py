"""Research-only share-count provenance from the ORIGINAL SEC100 financial archive.

Replay the frozen original U3 issuer identity and all 200 official SEC JSON
documents before inspecting DEI and GAAP *instant* share facts. Each positive
observation must match an original 10-K/10-Q accession, filing day and period,
satisfy a conservative 2-weekday filing delay and be <=150 days old at the
actual first original per-issuer source receipt. No invented shares, split
adjustment, class mapping, current market capitalization, valuation or alpha.

SEC companyfacts can aggregate share classes and filing-period dimensions;
issuer-level share observations are NEVER proof of the listed share class.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v8_sec100_original_annual_quality_source_v1_0 as original

SCHEMA = "FUND100_V8_SEC100_ORIGINAL_ISSUER_SHARE_SOURCE_COVERAGE_NO_VALUATION_V1"
SOURCE_RUN_ID = 42620947546
SOURCE_MAIN_SHA = "8b0356cfaf406127a1b418bbe29d87c27457c0dd"
TAGS = (("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"))
MAX_SHARE_AGE_DAYS = 150
MAX_OBSERVATION_SHARES = 100_000_000_000_000
NO_BROKER_HTTP = True
NO_PRIVATE_GIT_WRITE = True
NO_LIVE_STRATEGY = True

class ShareSourceHold(ValueError):
    pass


def _date(value):
    try:
        return quality.iso_date(value, "original SEC filed/share fact day")
    except quality.StockSourceStop:
        raise ShareSourceHold("Malformed original SEC share/filing date") from None


def _observed(*, facts, submissions, cik, acquisition):
    try:
        seen = original._utc(acquisition).date()
        quality.validate_identity(facts, submissions, cik)
        filings = quality.submissions_index(submissions)
    except Exception:
        raise ShareSourceHold("Original SEC identity or filing chronology invalid") from None
    found = {}
    for space, tag in TAGS:
        concept = facts.get("facts", {}).get(space, {}).get(tag)
        if concept is None:
            continue
        if type(concept) is not dict:
            raise ShareSourceHold("Malformed issuer-share concept")
        units = concept.get("units", {})
        if type(units) is not dict:
            raise ShareSourceHold("Malformed original SEC share units")
        facts_list = units.get("shares")
        if facts_list is None:
            continue
        if type(facts_list) is not list or len(facts_list) > 5000:
            raise ShareSourceHold("Unbounded issuer-share concept facts")
        candidates = {}
        for row in facts_list:
            if type(row) is not dict:
                raise ShareSourceHold("Malformed original SEC share fact")
            accn = row.get("accn")
            filing = filings.get(accn)
            if filing is None or filing.get("form") not in ("10-K", "10-Q"):
                continue
            if (row.get("form") != filing["form"]
                or row.get("filed") != filing["filed"]
                or row.get("start") is not None):
                # Annual/YTD weighted-average shares are not an instant
                # issuer share count; later filing comparative facts are not
                # eligible under a different annual source accession.
                continue
            end = _date(row.get("end"))
            filed = _date(row.get("filed"))
            if end > filed:
                continue
            try:
                available = _date(quality.availability_day(row["filed"]))
            except (KeyError, quality.StockSourceStop):
                raise ShareSourceHold("Invalid conservative filing availability") from None
            if available > seen or end > seen or (seen-end).days > MAX_SHARE_AGE_DAYS:
                continue
            count = row.get("val")
            if (type(count) is not int or
                not 0 < count <= MAX_OBSERVATION_SHARES):
                raise ShareSourceHold("Untrusted or nonpositive original issuer shares")
            key = (end.isoformat(), filed.isoformat(), accn)
            if key in candidates and candidates[key] != count:
                raise ShareSourceHold("Conflicting original same-accession issuer shares")
            candidates[key] = count
        if not candidates:
            continue
        # Ambiguous same-period competing issuer filing accessions are not
        # resolved by picking a convenient larger/smaller float.
        latest = max(k[0] for k in candidates)
        latest_values = [(key,val) for key,val in candidates.items() if key[0]==latest]
        if len({val for _,val in latest_values}) > 1:
            raise ShareSourceHold("Multiple inconsistent latest same-period share facts")
        selected = max(latest_values, key=lambda pair:pair[0])[0]
        found[space] = {
            "actual_SEC_namespace":space,
            "actual_SEC_tag":tag,
            "original_SEC_filing_accession":selected[2],
            "original_SEC_form":filings[selected[2]]["form"],
            "original_SEC_filed_date":selected[1],
            "conservative_available_date":quality.availability_day(selected[1]),
            "source_share_asof_date":selected[0],
            "days_since_source_share_observation":(seen-_date(selected[0])).days,
            "source_issuer_level_share_count":str(candidates[selected]),
            "common_share_class_or_broker_instrument_verified":False,
        }
    return found


def replay(*, u3_dir:Path, original_sec100_dir:Path):
    """No new source fetch: original SEC100 collector replay proves all bytes."""
    try:
        report=original.verify(u3_dir=u3_dir, report_dir=original_sec100_dir)
    except Exception:
        raise ShareSourceHold("Original SEC100 200-source archive did not replay") from None
    if (report.get("schema")!=original.SCHEMA
        or report.get("source_issuer_count")!=100
        or report.get("original_official_SEC_endpoint_get_count")!=200
        or report.get("live_authorized") is not False
        or report.get("broker_orders")!=0):
        raise ShareSourceHold("Wrong original SEC100 read-only source")
    rows=[]
    for source in report["source_issuer_rows"]:
        symbol=source["ticker"]
        cik=source["original_sec_cik_10digit"]
        blobs={}
        for kind in ("companyfacts","submissions"):
            filename=original._name(symbol,cik,kind)
            raw,_=original._unzip_bound(original_sec100_dir/filename)
            if sha256(raw).hexdigest()!=source[
                    "official_SEC_original_raw_sources"][kind]["original_raw_sha256"]:
                raise ShareSourceHold("Source SEC issuer hash changed after replay")
            blobs[kind]=sec.decode_source(raw,expected_cik=cik)
        try:
            facts=_observed(
                facts=blobs["companyfacts"],
                submissions=blobs["submissions"],cik=cik,
                acquisition=source["original_official_source_received_utc"])
        except ShareSourceHold:
            facts={}
            state="SHARE_REPORTING_CONFLICT_QUARANTINED"
        else:
            if len(facts)==2:
                state="TWO_ISSUER_SHARE_TAGS_OBSERVED_CLASS_UNVERIFIED"
            elif facts:
                state="ONE_ISSUER_SHARE_TAG_OBSERVED_CLASS_UNVERIFIED"
            else:
                state="NO_RECENT_SOURCE_MATCHED_ISSUER_SHARE_FACT_HOLD"
        rows.append({
            "ticker":symbol,
            "frozen_2026_original_sec_cik":cik,
            "original_source_received_utc":source[
                "original_official_source_received_utc"],
            "original_official_companyfacts_sha256":source[
                "official_SEC_original_raw_sources"]["companyfacts"]["original_raw_sha256"],
            "original_official_submissions_sha256":source[
                "official_SEC_original_raw_sources"]["submissions"]["original_raw_sha256"],
            "status":state,
            "original_sec_issuer_share_observations":facts,
            "company_share_class_from_ticker_authenticated":False,
            "shares_times_public_vendor_ticker_price_is_market_cap_authorized":False,
            "ticker_mapped_share_count_for_valuation":None,
            "live_trading_authorized":False,
        })
    sources=sum(bool(r["original_sec_issuer_share_observations"]) for r in rows)
    conflicts=sum(r["status"]=="SHARE_REPORTING_CONFLICT_QUARANTINED"
                  for r in rows)
    both=sum(len(r["original_sec_issuer_share_observations"])==2 for r in rows)
    return {
        "schema":SCHEMA,
        "status":"SEC100_ORIGINAL_ISSUER_SHARES_EVIDENCE_NOT_A_SHARE_CLASS_VALUATION",
        "source_completed_main_run_id":SOURCE_RUN_ID,
        "source_main_sha":SOURCE_MAIN_SHA,
        "original_sec100_manifest_sha256":sha256(
            (original_sec100_dir/"manifest.json").read_bytes()).hexdigest(),
        "frozen_2026_issuer_count":100,
        "original_200_sec_json_replayed":True,
        "recent_issuer_share_source_coverage_count":sources,
        "two_source_tag_observations":both,
        "quarantined_original_issuer_share_conflict_count":conflicts,
        "unqualified_or_missing_issuer_share_source_count":100-sources,
        "issuer_rows":rows,
        "current_listed_share_class_verified_count":0,
        "market_cap_valuation_ready_count":0,
        "historical_survivorship_free_cohort":False,
        "source_is_original_2026_first_capture_not_pit_historical_archive":True,
        "independent_share_class_split_adjusted_ticker_join":False,
        "alpha_or_undervaluation_established":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "private_git_writes":0,"live_authorized":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-u3",type=Path,required=True)
    p.add_argument("--original-sec100",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if not (NO_BROKER_HTTP and NO_PRIVATE_GIT_WRITE and NO_LIVE_STRATEGY):
        raise ShareSourceHold("Original share-source no-live release changed")
    if args.output.exists():
        raise ShareSourceHold("Never overwrite archived source examination")
    result=replay(u3_dir=args.original_u3,original_sec100_dir=args.original_sec100)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("Original SEC100 frozen issuer rows:",result["frozen_2026_issuer_count"])
    print("Recent issuer-level filing-matched share source:",
          result["recent_issuer_share_source_coverage_count"])
    print("Dual original DEI/GAAP issuer observations:",
          result["two_source_tag_observations"])
    print("No verified listed share-class valuation, broker or alpha.")


if __name__=="__main__":
    main()

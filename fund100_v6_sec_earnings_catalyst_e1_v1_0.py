"""V6-E1: authentic SEC earnings 8-K catalyst + post-freeze price reaction.

Research-only screening of original archived public sources. NOT earnings
surprise, licensed analyst revision data, historical alpha, a broker-order
manifest, a trading permission or an executable investment instruction.
"""
from __future__ import annotations

import argparse
import datetime as dt
from hashlib import sha256
import json
from pathlib import Path
import re

import pandas as pd

import fund100_stock_quality_momentum_p4g_v1_0 as p4g
import fund100_stock_sec_source_p4b_v1_0 as sec

SCHEMA = "FUND100_V6_E1_EARNINGS_CATALYST_SOURCE_REVIEW_V1"
FROZEN_START = dt.date(2026, 10, 15)
MIN_FOLLOWING_SESSIONS = 2
MAX_EVENT_AGE_SESSIONS = 10
RELATIVE_REACTION_MIN = 0.02
MAX_STOCK_WEIGHT_RESEARCH = 0.25
MAX_ACTIVE_STOCKS_RESEARCH = 4
ONE_WAY_COSTS_BPS = (5, 15, 35)
P4B_SOURCE_MANIFEST_SHA256 = p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256


class SourceStop(ValueError):
    pass


def iso_date(value: object, label: str) -> dt.date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise SourceStop(f"Invalid {label} date.")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as e:
        raise SourceStop(f"Invalid {label} date.") from e


def capture_time(value: object, label: str) -> dt.datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise SourceStop(f"Canonical {label} UTC timestamp required.")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as e:
        raise SourceStop(f"Invalid {label} timestamp.") from e


def original_sec_sources(root: Path) -> tuple[dict,dict[str,dict]]:
    """Validate ALL original SEC raw bytes against manifest, not just event issuers."""
    manifest_file = root/"manifest-and-quality.json"
    if not manifest_file.is_file():
        raise SourceStop("Original complete SEC manifest missing.")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (manifest.get("schema") != sec.SCHEMA
        or manifest.get("status") != "PROSPECTIVE_SEC_SOURCE_CAPTURE_RESEARCH_ONLY"
        or manifest.get("companies_attempted") != 8
        or manifest.get("source_count") != 16
        or manifest.get("broker_orders") != 0
        or manifest.get("paper_authorized") is not False
        or manifest.get("live_authorized") is not False):
        raise SourceStop("Original eight-company SEC evidence or safety status invalid.")
    acquired = capture_time(manifest.get("capture_timestamp_utc"), "SEC acquisition")
    if acquired.strftime("%Y-%m-%dT%H:%M:%SZ") != p4g.FROZEN_SEC_OBSERVED_AT_UTC:
        raise SourceStop("Original SEC capture not the approved 2026-10-15 vintage.")
    cohort = p4g.read_cohort()
    rows = manifest["companies"]
    if len(rows) != 8 or {x.get("ticker") for x in rows} != set(cohort):
        raise SourceStop("SEC current-universe roster mismatch.")
    sources = {}
    observed_paths = set()
    for row in rows:
        t = row["ticker"]
        cik = cohort[t]["cik_10_digit"]
        if row.get("cik") != cik:
            raise SourceStop("SEC original issuer identity mismatch.")
        prov = row.get("report_data_provenance")
        if not isinstance(prov,dict) or set(prov) != {"companyfacts","submissions"}:
            raise SourceStop("Incomplete independently archived SEC bytes.")
        for kind in ("companyfacts","submissions"):
            obj = prov[kind]
            expected = f"raw/CIK{cik}-{t}-{kind}.json"
            if (obj.get("source_file") != expected
                or obj.get("official_url") != sec.sec_url(cik,kind)):
                raise SourceStop("SEC source path or origin changed.")
            raw_path = root/expected
            if not raw_path.is_file() or expected in observed_paths:
                raise SourceStop("SEC original source missing or duplicate.")
            raw = raw_path.read_bytes()
            observed_paths.add(expected)
            if (len(raw) != obj.get("byte_count")
                or sha256(raw).hexdigest() != obj.get("raw_sha256")):
                raise SourceStop("SEC raw-byte original SHA256 mismatch.")
            decoded = sec.decode_source(raw,expected_cik=cik)
            if kind == "submissions":
                sources[t] = decoded
    return manifest,sources


def original_price_source(json_path: Path, csv_path: Path) -> tuple[dict,pd.DataFrame]:
    if not json_path.is_file() or not csv_path.is_file():
        raise SourceStop("Archived 17 October original source snapshot incomplete.")
    snapshot=json.loads(json_path.read_text(encoding="utf-8"))
    if (snapshot.get("schema") != p4g.SCHEMA
        or snapshot.get("source_class") != "REVISABLE_PUBLIC_YFINANCE_ADJUSTED_CLOSE"
        or snapshot.get("future_performance_observations") != 0
        or snapshot.get("original_sec_quality_source_manifest_sha256") != P4B_SOURCE_MANIFEST_SHA256
        or snapshot.get("broker_orders") != 0
        or snapshot.get("trading_authorized") is not False
        or snapshot.get("live_authorized") is not False):
        raise SourceStop("Original P4G price snapshot or controls invalid.")
    acquired = capture_time(snapshot.get("source_acquired_at_utc"),"price acquisition")
    if acquired.date() < dt.date(2026,10,16):
        raise SourceStop("Price evidence predates strategy freeze.")
    raw = csv_path.read_bytes()
    try:
        data = pd.read_csv(csv_path,parse_dates=["Date"]).set_index("Date")
    except Exception as e:
        raise SourceStop("Original canonical price CSV format invalid.") from e
    data=p4g.validate_prices(data)
    canonical=p4g.canonical_price_csv(data).encode("utf-8")
    if (raw != canonical
        or sha256(raw).hexdigest() != snapshot.get("canonical_price_csv_sha256")
        or data.index[-1].date().isoformat() != snapshot.get("asof_completed_session")
        or acquired.date() <= data.index[-1].date()):
        raise SourceStop("Original price evidence byte hash/availability mismatch.")
    return snapshot,data


def filing_candidates(submissions: dict, ticker: str, acquired: dt.datetime) -> list[dict]:
    """Item 2.02 identifies an 8-K earnings *filing*, NOT a positive surprise."""
    recent = submissions.get("filings",{}).get("recent")
    required=("form","accessionNumber","filingDate","items")
    if not isinstance(recent,dict) or any(not isinstance(recent.get(k),list) for k in required):
        raise SourceStop("SEC submissions recent event arrays invalid.")
    total = len(recent["form"])
    if any(len(recent[k]) != total for k in required) or total > 5000:
        raise SourceStop("SEC submissions event arrays inconsistent/truncated.")
    results=[]
    seen=set()
    for i in range(total):
        form,accession,date,items = (recent[k][i] for k in required)
        # Reject amended filings; never treat Item 9.01 alone as earnings.
        if form != "8-K":
            continue
        if not isinstance(items,str) or "2.02" not in {
            part.strip() for part in re.split(r"[,;]",items)
        }:
            continue
        filed = iso_date(date,"SEC filing")
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}",str(accession)):
            raise SourceStop("Invalid SEC earnings accession identity.")
        if accession in seen:
            raise SourceStop("Duplicate original earnings accession.")
        seen.add(accession)
        if filed > acquired.date():
            raise SourceStop("Future-dated SEC filing appeared in original source.")
        results.append({"ticker":ticker,"accession":accession,
                        "filed_date":filed.isoformat(),
                        "issuer_event_type":"8-K ITEM 2.02",
                        "earnings_surprise_known":False})
    return results


def evaluate(*, sec_manifest: dict, submissions: dict[str,dict],
             p4g_snapshot: dict, prices: pd.DataFrame) -> dict:
    captured_sec=capture_time(sec_manifest.get("capture_timestamp_utc"),"SEC original")
    price_capture=capture_time(p4g_snapshot.get("source_acquired_at_utc"),"price original")
    data=p4g.validate_prices(prices)
    if (captured_sec.strftime("%Y-%m-%dT%H:%M:%SZ") != p4g.FROZEN_SEC_OBSERVED_AT_UTC
        or price_capture <= captured_sec
        or data.index[-1].date().isoformat() != p4g_snapshot.get("asof_completed_session")
        or set(submissions) != set(p4g.FROZEN_P4E_SCORES)):
        raise SourceStop("SEC and price original source chronology/coverage not bound.")
    market_dates=[d.date() for d in data.index]
    last=market_dates[-1]
    events=[]
    eligible=[]
    for ticker in sorted(submissions):
        row=sec.decode_source(json.dumps(submissions[ticker]).encode("utf-8"),
                              expected_cik=p4g.read_cohort()[ticker]["cik_10_digit"])
        for event in filing_candidates(row,ticker,captured_sec):
            filed=iso_date(event["filed_date"],"filing")
            is_new_event = filed >= FROZEN_START
            # Never turn a pre-freeze filing into a purported real-time signal.
            if not is_new_event:
                continue
            # Only complete trading sessions strictly after the filing date
            # are eligible; never assume an EDGAR accepted time is the moment
            # all brokers actually saw news.
            later=[i for i,d in enumerate(market_dates) if d > filed]
            enough=len(later)>=MIN_FOLLOWING_SESSIONS
            observation={
                **event,
                "original_sec_available_at_utc":captured_sec.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fully_completed_following_sessions":len(later),
                "mature":enough,
                "post_event_reaction_relative_to_spy":None,
                "entry_order_authorized":False,
            }
            if enough:
                end=later[MIN_FOLLOWING_SESSIONS-1]
                before=[i for i,d in enumerate(market_dates) if d < filed]
                if before:
                    prev=before[-1]
                    stock_return=float(data[ticker].iloc[end]/data[ticker].iloc[prev]-1)
                    benchmark_return=float(data[p4g.BENCHMARK].iloc[end]/data[p4g.BENCHMARK].iloc[prev]-1)
                    observed=stock_return-benchmark_return
                    observation["post_event_reaction_relative_to_spy"]=round(observed,8)
                    observation["reaction_is_observed_past_not_future_alpha"]=True
                    # A dated source retrieved after the event; this stage ONLY
                    # checks whether a prospective screen warrants investigation.
                    if (len(later) <= MAX_EVENT_AGE_SESSIONS
                        and price_capture.date()>market_dates[end]
                        and p4g.FROZEN_P4E_SCORES[ticker] is not None
                        and p4g.FROZEN_P4E_SCORES[ticker]>=2
                        and observed>=RELATIVE_REACTION_MIN):
                        eligible.append((ticker,observed,event["accession"]))
            events.append(observation)
    eligible.sort(key=lambda row:(-row[1],row[0],row[2]))
    watchlist=[]
    used=set()
    for ticker,relative,acc in eligible:
        if ticker in used:continue
        used.add(ticker)
        watchlist.append({"ticker":ticker,"last_8k_accession":acc,
                          "observed_prior_reaction_vs_spy":round(relative,8),
                          "potential_name_cap_only_if_separately_released":MAX_STOCK_WEIGHT_RESEARCH,
                          "broker_order_notional_usd":0})
        if len(watchlist)>=MAX_ACTIVE_STOCKS_RESEARCH:break
    return {
        "schema":SCHEMA,
        "status":"EXPLORATORY_SEC_EARNINGS_CATALYST_SCREEN_RESEARCH_ONLY",
        "source_frozen_sec_acquired_at_utc":sec_manifest["capture_timestamp_utc"],
        "source_frozen_price_acquired_at_utc":p4g_snapshot["source_acquired_at_utc"],
        "source_price_sha256":p4g_snapshot["canonical_price_csv_sha256"],
        "completed_price_session":last.isoformat(),
        "original_sec_source_retrospective_replay_for_earlier_periods_disallowed":True,
        "earnings_surprise_consensus_present":False,
        "requires_independent_volume_and_spread_source_before_order_eligibility":True,
        "historical_survivorship_safe_stock_alpha_measured":False,
        "actual_forward_holding_period_profit_measured":False,
        "signal_definition":"Item2.02 8-K + 2 subsequent completed trading sessions + 2% SPY-relative price reaction + contemporary quality >=2",
        "cost_sensitivity_one_way_bps":list(ONE_WAY_COSTS_BPS),
        "trading_costs_not_deducted_from_past_information_screen":True,
        "maximum_research_per_stock_weight":MAX_STOCK_WEIGHT_RESEARCH,
        "max_concurrent_research_stocks":MAX_ACTIVE_STOCKS_RESEARCH,
        "source_contemporary_eight_company_only":True,
        "earnings_filing_events_since_quality_freeze":len(events),
        "reviewed_earnings_events":events,
        "descriptive_watchlist_not_order_recommendations":watchlist,
        "broker_orders":0,
        "operator_authorized_old_position_sales":False,
        "operator_authorized_stock_buys":False,
        "risk_contract_released":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sec-original-directory",type=Path,required=True)
    parser.add_argument("--p4g-original-report",type=Path,required=True)
    parser.add_argument("--p4g-original-prices",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    sec_report,subs=original_sec_sources(args.sec_original_directory)
    price_report,prices=original_price_source(
        args.p4g_original_report,args.p4g_original_prices)
    result=evaluate(sec_manifest=sec_report,submissions=subs,
                    p4g_snapshot=price_report,prices=prices)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("V6-E1 verified SEC item 2.02 events after quality freeze:",
          result["earnings_filing_events_since_quality_freeze"])
    print("Independent analyst earnings surprises: UNAVAILABLE")
    print("Historic strategy returns: NOT CLAIMED")
    print("Potential event watchlist (research only):",
          [s["ticker"] for s in result["descriptive_watchlist_not_order_recommendations"]])
    print("LIVE/PAPER orders: ZERO. Existing V5 holdings: UNTOUCHED.")


if __name__=="__main__":
    main()

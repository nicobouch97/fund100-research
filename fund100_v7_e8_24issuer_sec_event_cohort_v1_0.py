"""V7-E8: cohort-forward results across *all* original E6 source captures.

Actual SEC source artifacts are verified in full by E6.verify before
analysis. E7 runs per separately received original source against ONE later
original P4L 24-company vendor vintage; deterministic first original receipt
of every accession is preserved, even if it later appears in many SEC runs.
Distinct filings sharing the same ticker and modeled entry close represent
ONE modeled investment exposure, not independent returns.

Research-only. A filing's SEC filed date is NOT when Fund-100 first saw it;
a 2+ day late capture is not actionable near-filing earnings alpha. The
original issuer roster is contemporary and survivor-selected. No broker.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import mean,median

import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_v7_e7_24issuer_earnings_forward_v1_0 as e7

SCHEMA="FUND100_V7_E8_ARCHIVED_FIRST_OBSERVATION_24_ISSUER_EARNINGS_COHORT_V1"
MAX_ORIGINAL_RUNS=41
COSTS=e7.COSTS
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0

class CohortStop(ValueError):pass

def complete_successful_main_run_ids(rows:list[dict])->list[int]:
    """Fail closed rather than silently discard older original SEC captures.

    The workflow requests MAX_ORIGINAL_RUNS+1 successful main-branch E6
    runs. If the provider returns one more than our bounded source capacity,
    stop the study: a rolling newest-N sample would rewrite first-observed
    event dates and contaminate prospective performance.
    """
    if not isinstance(rows,list) or not rows or len(rows)>MAX_ORIGINAL_RUNS:
        raise CohortStop("Original SEC successful run history absent or exceeds bounded capacity")
    ids=[]
    for row in rows:
        if (not isinstance(row,dict)
            or type(row.get("databaseId")) is not int
            or row["databaseId"]<=0
            or row.get("status")!="completed"
            or row.get("conclusion")!="success"):
            raise CohortStop("Unverified original SEC successful main run")
        ids.append(row["databaseId"])
    if len(set(ids))!=len(ids):
        raise CohortStop("Duplicate original SEC run ID")
    if e7.PINNED_E6_MAIN_RUN not in ids:
        raise CohortStop("Foundational original SEC capture missing from complete run roster")
    return sorted(ids)

def verified_source_dirs(root:Path)->list[dict]:
    """Only real original SEC directories named by original main run ID.

    Strict original source hashes; no rebuilding the source from current API.
    Caller must separately restrict GitHub run discovery to main/success.
    """
    if not isinstance(root,Path) or not root.is_dir():
        raise CohortStop("Original SEC archive directory missing")
    dirs=sorted(x for x in root.iterdir() if x.is_dir())
    if not dirs or len(dirs)>MAX_ORIGINAL_RUNS:
        raise CohortStop("No or too many original SEC source captures")
    sources=[]
    for folder in dirs:
        if not re.fullmatch(r"[1-9][0-9]{7,14}",folder.name):
            raise CohortStop("Original SEC folder is not a numeric GitHub run")
        raw_path=folder/"manifest.json"
        try:
            raw=raw_path.read_bytes()
            doc=e6.verify(folder)
        except (OSError,ValueError,TypeError) as exc:
            raise CohortStop("SEC source could not be independently replayed") from exc
        sources.append({"run_id":int(folder.name),
                        "manifest_sha256":sha256(raw).hexdigest(),
                        "manifest":doc})
    # Enforce the historical first authentic main source anchor.
    pinned=[s for s in sources if s["run_id"]==e7.PINNED_E6_MAIN_RUN]
    if len(pinned)!=1 or pinned[0]["manifest_sha256"]!=e7.PINNED_E6_MANIFEST_SHA256:
        raise CohortStop("Missing or revised foundational original SEC observation")
    return sources

def _stats(exposures:list[dict],cost:int,field:str)->dict:
    observed=[float(r[field][str(cost)]) for r in exposures
              if r[field] is not None]
    if not observed:
        return {"observations":0,"mean_excess_percentage_points":None,
                "median_excess_percentage_points":None,
                "positive_fraction":None}
    return {"observations":len(observed),
            "mean_excess_percentage_points":round(mean(observed),8),
            "median_excess_percentage_points":round(median(observed),8),
            "positive_fraction":round(
                sum(v>0 for v in observed)/len(observed),8)}

def aggregate(sources:list[dict],price_report:dict,prices:pd.DataFrame)->dict:
    """Only prior-original-E6 captures, never retrospectively re-ranked filings."""
    if not isinstance(sources,list) or not 1<=len(sources)<=MAX_ORIGINAL_RUNS:
        raise CohortStop("Unbounded or missing SEC source captures")
    sorted_captures=[]
    runs=set()
    for s in sources:
        if not isinstance(s,dict):
            raise CohortStop("Invalid original SEC capture reference")
        run=s.get("run_id")
        raw_sha=s.get("manifest_sha256")
        doc=s.get("manifest")
        if (type(run) is not int or run<1 or run in runs
            or not isinstance(raw_sha,str) or not re.fullmatch(r"[0-9a-f]{64}",raw_sha)
            or not isinstance(doc,dict)):
            raise CohortStop("Untrusted source run identity or manifest hash")
        runs.add(run)
        sorted_captures.append((e7.utc(doc["capture_complete_utc"]),run,raw_sha,doc))
    sorted_captures.sort(key=lambda x:(x[0],x[1]))
    if (e7.PINNED_E6_MAIN_RUN not in runs
        or next(x[2] for x in sorted_captures if x[1]==e7.PINNED_E6_MAIN_RUN)
           !=e7.PINNED_E6_MANIFEST_SHA256):
        raise CohortStop("Foundational original live-source event is absent")
    first_by_accession={}
    exposures_by_entry={}
    historical=set()
    source_roster=[]
    for completed,run,raw_sha,doc in sorted_captures:
        # E7 performs the exact same market calendar, price manifest and
        # SEC/source chronology checks as the previously passing live E7.
        try:
            report=e7.evaluate(doc,price_report,prices)
        except (e7.EventForwardStop,ValueError,KeyError,TypeError) as exc:
            raise CohortStop("Later independent price vintage or SEC run chronology invalid") from exc
        source_roster.append({"run_id":run,"SEC_original_manifest_sha256":raw_sha,
                              "source_completed_utc":doc["capture_complete_utc"],
                              "registered_event_rows_seen":report["registered_source_events"]})
        for h in report["precohort_historical_exclusions"]:
            historical.add((h["ticker"],h["filing_date"]))
        original_rows=doc["after_registration_earnings_8k_events_not_trade_signals"]
        events={(ev["ticker"],ev["original_sec_accession"]):ev for ev in original_rows}
        if len(events)!=len(original_rows):
            raise CohortStop("Duplicate first-party original filing accession")
        for row in report["observations"]:
            key=(row["ticker"],row["original_sec_accession"])
            original=events.get(key)
            if original is None or row["source_first_observed_utc"]!=original["original_sec_observed_at_utc"]:
                raise CohortStop("Original SEC receipt missing from independently replayed source")
            if key in first_by_accession:
                prior=first_by_accession[key]
                if (row["filing_date"]!=prior["filing_date"] or
                    e7.utc(row["source_first_observed_utc"])<
                       e7.utc(prior["first_seen_in_FUND100_SEC_utc"])):
                    raise CohortStop("Historical filing changed date or earlier source discovered out of order")
                continue
            lag=(date.fromisoformat(row["source_first_observed_utc"][:10])-
                 date.fromisoformat(row["filing_date"])).days
            if lag<0:
                raise CohortStop("Negative original SEC observation delay")
            selected={**row,
                      "source_run_id":run,
                      "source_manifest_SHA256":raw_sha,
                      "first_seen_in_FUND100_SEC_utc":row["source_first_observed_utc"],
                      "filing_to_FUND100_first_seen_calendar_days":lag,
                      "original_filing_publication_time_is_not_known":True}
            first_by_accession[key]=selected
            entry=(row["ticker"],row["first_model_entry_close"])
            if entry not in exposures_by_entry:
                exposures_by_entry[entry]=selected
            else:
                previous=exposures_by_entry[entry]
                for k in ("second_model_exit_close","gross_stock_return",
                          "gross_spy_return","net_stock_minus_net_spy_percentage_points",
                          "net_stock_minus_gross_spy_percentage_points"):
                    if selected[k]!=previous[k]:
                        raise CohortStop("Conflicting duplicate stock/date exposure across original filings")
    all_filings=sorted(first_by_accession.values(),key=lambda v:(
        v["first_seen_in_FUND100_SEC_utc"],v["ticker"],v["original_sec_accession"]))
    positions=sorted(exposures_by_entry.values(),key=lambda v:(
        v["first_model_entry_close"],v["ticker"]))
    marked=[x for x in positions if x["gross_stock_return"] is not None]
    lags={"same_date":0,"one_day":0,"two_days":0,"three_or_more_days":0}
    for x in all_filings:
        n=x["filing_to_FUND100_first_seen_calendar_days"]
        lags[("same_date" if n==0 else "one_day" if n==1 else
              "two_days" if n==2 else "three_or_more_days")]+=1
    stats={
        str(b):{"both_stock_and_SPY_entry_exit_costs":
                _stats(positions,b,"net_stock_minus_net_spy_percentage_points"),
                "stock_costed_vs_gross_SPY":
                _stats(positions,b,"net_stock_minus_gross_spy_percentage_points")}
        for b in COSTS}
    status=("FORWARD_PRICE_MARKS_DESCRIPTIVE_NOT_ALPHA" if marked else
            "NO_COMPLETED_INDEPENDENT_TWO_CLOSE_RETURNS")
    return {
        "schema":SCHEMA,"status":status,
        "original_SEC_archives_verified":len(sorted_captures),
        "original_SEC_capture_manifest_hashes":source_roster,
        "source_scope":"CURRENT_SUCCESSFUL_MAIN_E6_SOURCE_ARTIFACTS_WITHIN_GITHUB_RETENTION",
        "earliest_historical_SEC_original_PG_run":e7.PINNED_E6_MAIN_RUN,
        "foundational_original_SEC_manifest_sha256":e7.PINNED_E6_MANIFEST_SHA256,
        "later_single_price_vendor_source_sha256":price_report["canonical_price_csv_sha256"],
        "later_price_snapshot_utc":price_report["source_acquired_at_utc"],
        "later_price_completed_through":price_report["asof_completed_session"],
        "unique_eligible_filing_accessions":len(all_filings),
        "distinct_ticker_entry_exposures":len(positions),
        "source_eligible_exposures_with_completed_returns":len(marked),
        "pre_registration_historical_ticker_date_references":len(historical),
        "filing_to_first_SEC_source_capture_lag_days":lags,
        "cost_per_side_bps":list(COSTS),
        "costed_SPY_benchmark_equal_full_roundtrip":True,
        "descriptive_exposure_statistics":stats,
        "unique_filing_observations":all_filings,
        "one_observation_per_ticker_entry_for_performance":True,
        "first_genuine_archive_observation_never_replaced_by_later_repeat":True,
        "source_issuer_universe_is_2026_survivor_selected":True,
        "filing_date_not_equivalent_to_first_investor_news_publication":True,
        "report_is_bounded_by_90_day_GitHub_original_artifact_retention":True,
        "alpha_not_established":True,"signal_promotable":False,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,
        "paper_authorized":False,"live_authorized":False,"trading_authorized":False,
    }

def main():
    p=__import__("argparse").ArgumentParser()
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    sources=verified_source_dirs(args.source_root)
    price=p4l.public_prices()
    stamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    price_report=p4l.evaluate(price,acquired_at_utc=stamp,
            provider_reference="yfinance 24 issuer independent completed closes captured "+stamp)
    report=aggregate(sources,price_report,price)
    dest=args.output_dir
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"original-24issuer-prices.csv").write_text(p4l.canonical_csv(price))
    (dest/"original-price-source-manifest.json").write_text(
        json.dumps(price_report,sort_keys=True,indent=2)+"\n")
    (dest/"source-dedup-24issuer-cohort.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("Real source captures",report["original_SEC_archives_verified"])
    print("Unique original earnings accessions",report["unique_eligible_filing_accessions"])
    print("Distinct candidate stock entry exposures",report["distinct_ticker_entry_exposures"])
    print("Real new forward two-close return marks",report["source_eligible_exposures_with_completed_returns"])
    print("15bp-side descriptive result",
          report["descriptive_exposure_statistics"]["15"]["both_stock_and_SPY_entry_exit_costs"])
    print("Research-only: no broker trade or alpha promotion.")

if __name__=="__main__":main()

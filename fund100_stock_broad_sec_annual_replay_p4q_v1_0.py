"""P4Q: reconstruct SEC annual quality at each ORIGINAL 10-K availability date.

Reuse the existing P4N official SEC capture and issuer-specific tag contract.
An observation uses only facts with the selected historical 10-K's own
accession, filing date and fiscal periods. Today's SEC companyfacts download
is NOT an independently archived historical point-in-time vendor feed.
No prices, backtest, ranking, broker access or trading authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b

SCHEMA = "FUND100_P4Q_ACCESSION_LINKED_ANNUAL_QUALITY_CHRONOLOGY_V1"


class AnnualReplayStop(ValueError):
    pass


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise AnnualReplayStop("Original SEC archive is incomplete")
    return path.read_bytes()


def _clock(value: object) -> str:
    if not isinstance(value, str):
        raise AnnualReplayStop("Original SEC acquisition timestamp missing")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise AnnualReplayStop("Noncanonical SEC acquisition timestamp") from exc
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise AnnualReplayStop("Noncanonical SEC acquisition timestamp")
    return dt.date().isoformat()


def evaluate(source_dir: Path) -> dict:
    """Audit 16 archived issuer identities; replay 12 industrial annual series.

    No missing accession, concept or historical filing is imputed. Four
    sector-specific issuer diagnostics remain deliberately non-comparable.
    """
    try:
        manifest_raw = _read(source_dir / "manifest.json")
        report = json.loads(manifest_raw)
        capture_day = _clock(report["capture_timestamp_utc"])
        registry = _read(source_dir / "official-sec-ticker-registry.json")
        if (report["schema"] != p4n.SCHEMA
            or report["source_count"] != 2 * p4n.MAX_NEW
            or report["new_issuers_captured"] != p4n.MAX_NEW
            or report["p4l_roster_size"] != len(p4l.SECTORS)
            or len(report["observations"]) != p4n.MAX_NEW
            or hashlib.sha256(registry).hexdigest() != report["official_registry_sha256"]
            or report["trading_authorized"] is not False
            or report["paper_authorized"] is not False
            or report["live_authorized"] is not False
            or report["broker_orders"] != 0):
            raise AnnualReplayStop("Incomplete or executable original P4N archive")
        identities = p4n.resolve_registry(registry, allow_frozen_drift=True)
        frozen = {row["ticker"] for row in p4b.read_cohort()}
        new = set(p4l.SECTORS) - frozen
        if ({row["ticker"] for row in report["observations"]} != new
            or len({row["ticker"] for row in report["observations"]}) != p4n.MAX_NEW):
            raise AnnualReplayStop("Original 16-issuer cohort changed")
        observations = []
        for row in sorted(report["observations"], key=lambda r: r["ticker"]):
            ticker = row["ticker"]
            cik = row["cik_10_digit"]
            if (cik != identities[ticker] or
                row["contemporary_sector"] != p4l.SECTORS[ticker] or
                row["fundamental_quality_for_trading_approved"] is not False):
                raise AnnualReplayStop("Issuer identity or source permissions changed")
            raw = {}
            for kind in ("companyfacts", "submissions"):
                provenance = row["source_provenance"][kind]
                expected = f"raw/CIK{cik}-{ticker}-{kind}.json"
                if (provenance["source_file"] != expected or
                    provenance["official_url"] != p4b.sec_url(cik, kind)):
                    raise AnnualReplayStop("Unexpected original SEC provenance path")
                data = _read(source_dir / expected)
                if (hashlib.sha256(data).hexdigest() != provenance["raw_sha256"]
                    or len(data) != provenance["byte_count"]):
                    raise AnnualReplayStop("Original SEC source hash/size mismatch")
                raw[kind] = p4b.decode_source(data, expected_cik=cik)
            facts, submissions = raw["companyfacts"], raw["submissions"]
            p4a.validate_identity(facts, submissions, cik)
            if (p4n.source_matched_annual_quality(
                    facts, submissions, cik, ticker, capture_day)
                != row["source_matched_latest_10k_quality"]):
                raise AnnualReplayStop("Original issuer quality report not reproducible")
            if ticker not in p4n.SOURCE_MATCHED_TAGS:
                observations.append({
                    "ticker": ticker, "cik_10_digit": cik,
                    "state": "SECTOR_SPECIFIC_ACCOUNTING_NOT_CROSS_SECTOR_REPLAYED",
                    "annual_filing_dates_reviewed": 0,
                    "available_score_count": 0,
                    "annual_events": [],
                })
                continue
            filings = p4a.submissions_index(submissions)
            dates = sorted({
                p4a.availability_day(f["filed"])
                for f in filings.values()
                if f["form"] == "10-K"
                and p4a.availability_day(f["filed"]) <= capture_day
                and f["end"] <= capture_day
            })
            events = []
            for day in dates:
                quality = p4n.source_matched_annual_quality(
                    facts, submissions, cik, ticker, day)
                accession = quality["latest_10k_accession"]
                available = quality["latest_10k_available_date"]
                if quality["score"] is not None:
                    if (quality["state"] != "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY"
                        or accession not in filings
                        or available != p4a.availability_day(filings[accession]["filed"])
                        or available > day
                        or quality["score"] not in (0, 1, 2, 3)):
                        raise AnnualReplayStop("Historical accession chronology inconsistent")
                events.append({
                    "asof_conservative_available_date": day,
                    "source_10k_accession": accession,
                    "source_10k_available_date": available,
                    "state": quality["state"],
                    "score": quality["score"],
                    "revenue_growth_yoy": quality["revenue_growth_yoy"],
                    "operating_margin": quality["operating_margin"],
                    "free_cash_flow_margin": quality["free_cash_flow_margin"],
                    "same_accession_comparative": quality[
                        "comparative_from_same_latest_accession"],
                })
            observations.append({
                "ticker": ticker, "cik_10_digit": cik,
                "state": "RECONSTRUCTED_FROM_ORIGINAL_ACCESSION_TAGS",
                "annual_filing_dates_reviewed": len(events),
                "available_score_count": sum(e["score"] is not None for e in events),
                "annual_events": events,
            })
        return {
            "schema": SCHEMA,
            "status": "HISTORICAL_10K_ACCESSION_REPLAY_SOURCE_LIMITED_NOT_ALPHA",
            "original_p4n_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "original_sec_registry_sha256": hashlib.sha256(registry).hexdigest(),
            "source_acquisition_utc": report["capture_timestamp_utc"],
            "new_issuers_verified": len(observations),
            "industrial_issuer_chronologies": len(p4n.SOURCE_MATCHED_TAGS),
            "sector_specific_issuers_not_replayed": sorted(
                set(new) - set(p4n.SOURCE_MATCHED_TAGS)),
            "industrial_annual_filing_dates_reviewed": sum(
                row["annual_filing_dates_reviewed"] for row in observations),
            "industrial_annual_scores_available": sum(
                row["available_score_count"] for row in observations),
            "original_accession_and_filed_day_used": True,
            "conservative_two_weekday_lag_not_holiday_or_intraday_proof": True,
            "today_retrieved_companyfacts_not_original_historical_capture": True,
            "issuer_roster_selected_with_2026_knowledge": True,
            "historical_prices_dividends_delistings_not_reconstructed": True,
            "sector_neutral_quality_or_valuation_not_validated": True,
            "historical_investable_backtest_eligible": False,
            "independent_alpha_validated": False,
            "research_only": True,
            "trading_authorized": False,
            "paper_authorized": False,
            "live_authorized": False,
            "broker_requests": 0,
            "broker_orders": 0,
            "observations": observations,
        }
    except (KeyError, TypeError, IndexError, json.JSONDecodeError,
            p4n.BroadSecStop, p4a.StockSourceStop,
            p4b.SecIntakeStop, ValueError) as exc:
        if isinstance(exc, AnnualReplayStop):
            raise
        raise AnnualReplayStop("Original SEC accession replay validation failed") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("P4Q original SEC annual replay:",
          report["industrial_issuer_chronologies"], "industrial issuers;",
          report["industrial_annual_scores_available"], "dated annual scores")
    print("TODAY-RETRIEVED accession facts, NOT independently archived point-in-time data.")
    print("NO historical alpha, valuation, broker requests or orders.")


if __name__ == "__main__":
    main()

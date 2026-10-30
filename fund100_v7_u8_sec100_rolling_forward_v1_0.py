"""Read-only rolling forward marks for consecutively archived SEC100 cohorts.

Reuses the real U5->U6 original-source replay and U7 two-close after-cost
evaluator. Unlike the pinned first two-event demonstration, this processes
successive source-receipt cohorts, including zero-event days. A rolling window
is not the entire research history and never constitutes alpha or order rights.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

import fund100_v7_u6_sec100_causal_forward_admission_v1_0 as u6
import fund100_v7_u7_sec100_two_close_costed_mark_v1_0 as u7

SCHEMA = "FUND100_V7_U8_ROLLING_SEC100_SOURCE_COHORT_MARKS_V1"
MAX_ARCHIVES = 20
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
TRADING_AUTHORIZED = False


class RollingStop(ValueError):
    pass


def freeze_chain(*, original_u3: Path, original_first_sec: Path,
                 observations: list[tuple[int, Path]]) -> list[tuple[int, int, dict]]:
    """Every adjacent source pair is replayed from original SEC bytes.

    No price is consulted until ALL source-relative positions are frozen.
    Run IDs must be increasing; the caller separately verifies each is a
    successful main-branch U5 run with its original archived artifact.
    """
    if not isinstance(observations, list) or not 2 <= len(observations) <= MAX_ARCHIVES:
        raise RollingStop("Need 2-20 consecutive archived main U5 observations")
    ids = []
    for entry in observations:
        if (not isinstance(entry, tuple) or len(entry) != 2
            or type(entry[0]) is not int or entry[0] <= 0
            or not isinstance(entry[1], Path)):
            raise RollingStop("Invalid original SEC observer identity")
        ids.append(entry[0])
    if ids != sorted(set(ids)):
        raise RollingStop("Source run order or identity is not strictly increasing")
    frozen = []
    for previous, current in zip(observations, observations[1:]):
        try:
            selection = u6.freeze_from_sources(
                original_u3=original_u3, original_first_sec=original_first_sec,
                previous_sec=previous[1], previous_main_id=previous[0],
                later_sec=current[1])
        except Exception as exc:
            raise RollingStop("Consecutive original SEC100 archive replay failed") from exc
        if (selection.get("broker_orders") != 0
            or selection.get("trading_authorized") is not False
            or selection.get("live_authorized") is not False
            or selection.get("previous_main_observer_run") != previous[0]):
            raise RollingStop("Original SEC100 source tried to bypass research lock")
        frozen.append((previous[0], current[0], selection))
    return frozen


def required_symbols(cohorts: list[tuple[int, int, dict]]) -> set[str]:
    symbols = set()
    for _, _, frozen in cohorts:
        for entry in frozen["deduplicated_stock_entry_exposures"]:
            symbols.add(entry["ticker"])
    return symbols | {u7.BENCHMARK, u7.EQUAL_WEIGHT_BENCHMARK} if symbols else set()


def mark_chain(cohorts: list[tuple[int, int, dict]], *,
               prices: pd.DataFrame | None,
               acquired_utc: str | None = None,
               provider_reference: str | None = None) -> dict:
    """No successful-subset selection when any symbol or cohort is missing."""
    if not cohorts:
        raise RollingStop("No frozen original source-relative cohorts")
    symbols = required_symbols(cohorts)
    if symbols:
        if prices is not None and (
            not isinstance(prices, pd.DataFrame)
            or set(prices.columns) != symbols):
            raise RollingStop("Incomplete rolling source panel; never select surviving tickers")
    elif prices is not None:
        raise RollingStop("No new events: market prices must not be acquired")
    if prices is None and (acquired_utc is not None or provider_reference is not None):
        raise RollingStop("Price metadata without original price evidence")
    if prices is not None and (acquired_utc is None or provider_reference is None):
        raise RollingStop("Original price receipt and provider required")
    results = []
    total_exposures = priced = pending = 0
    for previous_id, current_id, frozen in cohorts:
        rows = frozen["deduplicated_stock_entry_exposures"]
        sub = None
        if rows and prices is not None:
            names = {r["ticker"] for r in rows} | {
                u7.BENCHMARK, u7.EQUAL_WEIGHT_BENCHMARK}
            sub = prices.loc[:, sorted(names)]
        try:
            mark = u7.evaluate(
                frozen, prices=sub,
                later_price_acquired_utc=acquired_utc if sub is not None else None,
                provider_reference=provider_reference if sub is not None else None)
        except Exception as exc:
            raise RollingStop("At least one original cohort cannot be priced safely") from exc
        total_exposures += mark["unique_model_exposures"]
        priced += mark["priced_two_close_exposures"]
        pending += mark["pending_two_close_exposures"]
        results.append({
            "previous_main_source_run_id": previous_id,
            "current_main_source_run_id": current_id,
            "original_frozen_source": frozen,
            "source_relative_two_close_marks": mark,
        })
    if priced + pending != total_exposures:
        raise RollingStop("Incomplete cohort coverage or fabricated marks")
    return {
        "schema": SCHEMA,
        "status": "ROLLING_SOURCE_RELATIVE_DESCRIPTIVE_RESEARCH_ONLY",
        "archived_observer_pairs": len(cohorts),
        "rolling_window_not_entire_historical_population": True,
        "all_source_pairs_in_window_evaluated_without_success_filter": True,
        "source_relative_distinct_exposures": total_exposures,
        "priced_two_close_exposures": priced,
        "pending_two_close_exposures": pending,
        "all_nonempty_cohorts_fully_priced": bool(total_exposures and not pending),
        "cohort_results": results,
        "independent_revisable_price_acquired_utc": acquired_utc,
        "no_portfolio_alpha_from_overlapping_or_partial_cohorts": True,
        "statistically_proven_alpha": False,
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
        "trading_authorized": False, "live_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-u3", type=Path, required=True)
    parser.add_argument("--original-first-sec", type=Path, required=True)
    parser.add_argument("--observations-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise RollingStop("Never overwrite a previously archived rolling vintage")
    raw = json.loads(args.observations_json.read_text())
    if not isinstance(raw, list):
        raise RollingStop("Original source observation list malformed")
    observations = []
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"run_id", "path"}:
            raise RollingStop("Unrecognized source observer metadata")
        observations.append((entry["run_id"], Path(entry["path"])))
    frozen = freeze_chain(
        original_u3=args.original_u3,
        original_first_sec=args.original_first_sec,
        observations=observations)
    symbols = required_symbols(frozen)
    price = None
    receipt = provider = None
    if symbols:
        price = u7.public_original_prices(symbols)
        receipt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        provider = "independent revisable public yfinance adjusted closes received " + receipt
    result = mark_chain(frozen, prices=price, acquired_utc=receipt,
                        provider_reference=provider)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "rolling-original-sec100-cohort-marks.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n")
    if price is not None:
        (args.output_dir / "original-later-revisable-market-vintage.csv").write_text(
            u7.canonical_csv(price))
    print("Original consecutive SEC100 cohort pairs:", len(frozen))
    print("Frozen exposures:", result["source_relative_distinct_exposures"])
    print("Completed two-close marks:", result["priced_two_close_exposures"])
    print("Still pending:", result["pending_two_close_exposures"])
    print("ROLLING WINDOW ONLY. NO proven alpha, broker orders or release.")


if __name__ == "__main__":
    main()

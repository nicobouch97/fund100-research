"""P4R: observed post-10-K stock returns by original SEC quality score.

This is an EVENT-LEVEL HISTORICAL DIAGNOSTIC, not a tradable strategy:
the 2026 survivor-selected 12-issuer roster, today-retrieved SEC facts,
revisable adjusted price history and missing delistings invalidate alpha
claims. Each score is known only after its own 10-K availability date.
Entry is the NEXT completed exchange close, exit 126 sessions later.
There is no rebalancing, selection optimization, brokerage or order path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_annual_replay_p4q_v1_0 as p4q
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA = "FUND100_P4R_ORIGINAL_SEC_QUALITY_126_SESSION_EVENT_STUDY_V1"
HORIZON = 126
SIDE_COSTS_BPS = (5, 15, 35)
HISTORICAL_PRICE_START = "2017-01-01"


class EventStudyStop(ValueError):
    pass


def _date(value: object) -> pd.Timestamp:
    if not isinstance(value, str):
        raise EventStudyStop("Missing dated SEC event")
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise EventStudyStop("Invalid SEC event date") from exc
    if d.strftime("%Y-%m-%d") != value:
        raise EventStudyStop("Noncanonical SEC event date")
    return pd.Timestamp(d)


def _summarize(rows: list[dict], bps: int) -> dict:
    values = [r["cost_scenarios"][str(bps)]["stock_minus_spy_pp"] for r in rows]
    if not values:
        return {"events": 0, "distinct_issuers": 0,
                "mean_stock_minus_spy_pp": None, "median_stock_minus_spy_pp": None,
                "positive_relative_event_fraction": None}
    return {
        "events": len(rows),
        "distinct_issuers": len({r["ticker"] for r in rows}),
        "mean_stock_minus_spy_pp": round(float(np.mean(values)), 6),
        "median_stock_minus_spy_pp": round(float(np.median(values)), 6),
        "positive_relative_event_fraction": round(
            sum(x > 0 for x in values) / len(values), 6),
    }


def _issuer_balanced_sensitivity(rows: list[dict], bps: int) -> dict:
    """Descriptive issuer weighting and deletion sensitivity, NOT inference.

    Repeated annual outcomes from the same issuer and overlapping 126-session
    windows are dependent. Delete an issuer from BOTH score groups if it
    changes score; do not treat events as independent experimental units.
    """
    def issuer_means(group: list[dict]) -> dict[str, float]:
        by_ticker: dict[str, list[float]] = {}
        for row in group:
            by_ticker.setdefault(row["ticker"], []).append(
                row["cost_scenarios"][str(bps)]["stock_minus_spy_pp"])
        return {ticker: float(np.mean(values))
                for ticker, values in sorted(by_ticker.items())}

    low = issuer_means([r for r in rows if r["quality_score"] < 2])
    high = issuer_means([r for r in rows if r["quality_score"] >= 2])

    def group_report(means: dict[str, float]) -> dict:
        return {
            "distinct_issuers": len(means),
            "issuer_equal_weight_mean_stock_minus_spy_pp": (
                round(float(np.mean(list(means.values()))), 6) if means else None),
            "per_issuer_mean_stock_minus_spy_pp": {
                ticker: round(value, 6) for ticker, value in means.items()},
        }

    gap = (float(np.mean(list(high.values()))) -
           float(np.mean(list(low.values())))) if high and low else None
    leave_one_out = {}
    for ticker in sorted(set(high) | set(low)):
        remaining_high = [value for name, value in high.items() if name != ticker]
        remaining_low = [value for name, value in low.items() if name != ticker]
        if remaining_high and remaining_low:
            leave_one_out[ticker] = round(
                float(np.mean(remaining_high) - np.mean(remaining_low)), 6)
    return {
        "method": "ISSUER_EQUAL_WEIGHT_WITH_WHOLE_ISSUER_DELETION",
        "score_0_or_1": group_report(low),
        "score_2_or_3": group_report(high),
        "issuers_appearing_in_both_groups": sorted(set(high) & set(low)),
        "high_minus_low_issuer_balanced_pp": round(gap, 6) if gap is not None else None,
        "leave_one_issuer_out_gap_pp": leave_one_out,
        "leave_one_issuer_out_evaluable_exclusions": len(leave_one_out),
        "leave_one_issuer_out_gap_range_pp": (
            [min(leave_one_out.values()), max(leave_one_out.values())]
            if leave_one_out else None),
        "deletion_range_is_not_a_confidence_interval": True,
        "survivorship_and_overlapping_outcomes_preclude_alpha_inference": True,
    }


def analyze(annual: dict, prices: pd.DataFrame, *,
            acquired_at_utc: str, source_sha256: str) -> dict:
    """Pure deterministic event-return study; caller authenticates SEC archive."""
    try:
        data = p4l.validate_prices(prices)
    except p4l.BroadStockStop as exc:
        raise EventStudyStop("Incomplete original market price history") from exc
    if hashlib.sha256(p4l.canonical_csv(data).encode()).hexdigest() != source_sha256:
        raise EventStudyStop("Original market source fingerprint mismatch")
    try:
        capture = datetime.strptime(acquired_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        sec_capture = datetime.strptime(
            annual["source_acquisition_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as exc:
        raise EventStudyStop("Noncanonical acquisition clocks") from exc
    if (capture.strftime("%Y-%m-%dT%H:%M:%SZ") != acquired_at_utc
        or sec_capture.strftime("%Y-%m-%dT%H:%M:%SZ") != annual["source_acquisition_utc"]
        or data.index[-1].date() >= capture.date()
        or data.index[-1].date() > sec_capture.date()
        or len(data) < 2 * HORIZON
        or data.index[0].date().isoformat() > "2018-01-01"):
        raise EventStudyStop("Incomplete historical window or future price source")
    if (annual.get("schema") != p4q.SCHEMA
        or annual.get("new_issuers_verified") != 16
        or annual.get("industrial_issuer_chronologies") != 12
        or annual.get("original_accession_and_filed_day_used") is not True
        or annual.get("today_retrieved_companyfacts_not_original_historical_capture") is not True
        or annual.get("issuer_roster_selected_with_2026_knowledge") is not True
        or annual.get("historical_investable_backtest_eligible") is not False
        or annual.get("independent_alpha_validated") is not False
        or annual.get("trading_authorized") is not False
        or annual.get("paper_authorized") is not False
        or annual.get("live_authorized") is not False
        or annual.get("broker_orders") != 0):
        raise EventStudyStop("Unverified or executable SEC replay")
    observations = annual.get("observations")
    if (not isinstance(observations, list) or len(observations) != 16
        or {r["ticker"] for r in observations} !=
           (set(p4l.SECTORS) - set(p4g.FROZEN_P4E_SCORES))):
        raise EventStudyStop("SEC issuer roster mismatch")
    if (sum(r["available_score_count"] for r in observations) != annual["industrial_annual_scores_available"]
        or sum(r["annual_filing_dates_reviewed"] for r in observations) != annual["industrial_annual_filing_dates_reviewed"]):
        raise EventStudyStop("SEC event-to-outcome accounting failed")
    rows = []
    missing = 0
    right_censored = 0
    no_entry = 0
    left_censored = 0
    not_new_accession_events = 0
    for issuer in sorted(observations, key=lambda r: r["ticker"]):
        ticker = issuer["ticker"]
        if ticker not in p4n.SOURCE_MATCHED_TAGS:
            if issuer["annual_events"] or issuer["available_score_count"] != 0:
                raise EventStudyStop("Sector-specific scores cannot be pooled")
            continue
        events = issuer["annual_events"]
        if (len(events) != issuer["annual_filing_dates_reviewed"]
            or sum(e["score"] is not None for e in events) != issuer["available_score_count"]):
            raise EventStudyStop("SEC event counts inconsistent")
        last_day = None
        for event in events:
            day = _date(event["asof_conservative_available_date"])
            if ((last_day is not None and day <= last_day)
                or day.date() > sec_capture.date()):
                raise EventStudyStop("SEC filing chronology or availability mismatch")
            last_day = day
            # P4Q enumerates all original 10-K filing dates. Its as-of
            # quality evaluator can still reference a PREVIOUS accession
            # when the newly filed 10-K has an older fiscal end or lacks
            # the issuer-specific facts. That is NOT a new score signal.
            # Only a score whose OWN source accession becomes available
            # on this event day is eligible for a forward outcome.
            available = event["source_10k_available_date"]
            if available is None:
                not_new_accession_events += 1
                continue
            source_day = _date(available)
            if source_day > day:
                raise EventStudyStop("Future SEC accession leaked into event")
            if source_day < day:
                not_new_accession_events += 1
                continue
            score = event["score"]
            if score is None:
                missing += 1
                continue
            if (type(score) is not int or score not in (0, 1, 2, 3)
                or event["state"] != "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY"
                or not event["same_accession_comparative"]
                or not event["source_10k_accession"]):
                raise EventStudyStop("Invalid original SEC quality evidence")
            if day < data.index[0]:
                left_censored += 1
                continue
            # Use the first close strictly AFTER the conservative filing day.
            # This cannot buy on the filing-day close or a prior close.
            entry_i = int(data.index.searchsorted(day, side="right"))
            if entry_i >= len(data):
                no_entry += 1
                continue
            exit_i = entry_i + HORIZON
            if exit_i >= len(data):
                right_censored += 1
                continue
            stock_gross = float(data[ticker].iloc[exit_i] / data[ticker].iloc[entry_i])
            spy_gross = float(data["SPY"].iloc[exit_i] / data["SPY"].iloc[entry_i])
            costs = {}
            for bps in SIDE_COSTS_BPS:
                factor = (1 - bps / 10000) ** 2
                costs[str(bps)] = {
                    "stock_net_return_pct": round(100 * (stock_gross * factor - 1), 6),
                    "spy_net_return_pct": round(100 * (spy_gross * factor - 1), 6),
                    "stock_minus_spy_pp": round(
                        100 * (stock_gross - spy_gross) * factor, 6),
                }
            rows.append({
                "ticker": ticker, "original_10k_accession": event["source_10k_accession"],
                "quality_score": score,
                "conservative_available_date": day.date().isoformat(),
                "entry_next_session_close": data.index[entry_i].date().isoformat(),
                "exit_126_sessions_later": data.index[exit_i].date().isoformat(),
                "stock_gross_return_pct": round(100 * (stock_gross - 1), 6),
                "spy_matched_gross_return_pct": round(100 * (spy_gross - 1), 6),
                "cost_scenarios": costs,
            })
    if len(rows) + missing + right_censored + no_entry + left_censored + not_new_accession_events != annual["industrial_annual_scores_available"] + (
        annual["industrial_annual_filing_dates_reviewed"] -
        annual["industrial_annual_scores_available"]):
        raise EventStudyStop("SEC event-to-outcome accounting failed")
    groups = {}
    for bps in SIDE_COSTS_BPS:
        groups[str(bps)] = {
            "all_scored": _summarize(rows, bps),
            "score_0_or_1": _summarize([r for r in rows if r["quality_score"] < 2], bps),
            "score_2_or_3": _summarize([r for r in rows if r["quality_score"] >= 2], bps),
        }
    return {
        "schema": SCHEMA,
        "status": "HINDSIGHT_SURVIVOR_EVENT_STUDY_NOT_VALIDATED_ALPHA",
        "source_sec_capture_utc": annual["source_acquisition_utc"],
        "source_sec_manifest_sha256": annual["original_p4n_manifest_sha256"],
        "source_prices_capture_utc": acquired_at_utc,
        "source_prices_canonical_csv_sha256": source_sha256,
        "source_first_price_session": data.index[0].date().isoformat(),
        "source_last_price_session": data.index[-1].date().isoformat(),
        "predeclared_forward_sessions": HORIZON,
        "cost_per_side_bps": list(SIDE_COSTS_BPS),
        "original_annual_scores": annual["industrial_annual_scores_available"],
        "missing_original_annual_scores": missing,
        "right_censored_eligible_scores": right_censored,
        "scores_without_future_entry_close": no_entry,
        "left_censored_eligible_scores": left_censored,
        "nonnew_or_unavailable_source_accession_events": not_new_accession_events,
        "completed_event_returns": len(rows),
        "summary": groups,
        "issuer_balanced_sensitivity": {
            str(bps): _issuer_balanced_sensitivity(rows, bps)
            for bps in SIDE_COSTS_BPS
        },
        "event_returns": rows,
        "event_returns_are_overlapping_and_not_independent": True,
        "retrospectively_selected_2026_survivors": True,
        "SEC_facts_retrieved_today_not_historical_vintages": True,
        "vendor_adjusted_prices_revisable_and_corporate_actions_not_independently_verified": True,
        "delistings_and_historical_membership_missing": True,
        "no_point_in_time_investable_backtest": True,
        "not_a_self_financing_portfolio_or_validated_alpha": True,
        "no_valuation_or_cross_sector_quality_model": True,
        "research_only": True, "trading_authorized": False,
        "paper_authorized": False, "live_authorized": False,
        "broker_requests": 0, "broker_orders": 0,
    }


def evaluate(source_dir: Path, prices: pd.DataFrame, *,
             acquired_at_utc: str) -> dict:
    """Require P4Q's original SEC file/hash verification before joining prices."""
    annual = p4q.evaluate(source_dir)
    digest = hashlib.sha256(p4l.canonical_csv(prices).encode()).hexdigest()
    return analyze(annual, prices, acquired_at_utc=acquired_at_utc,
                   source_sha256=digest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-prices-csv", type=Path, required=True)
    args = parser.parse_args()
    prices = p4l.public_prices(start=HISTORICAL_PRICE_START)
    p4g.verify_original_nyse_source_sessions(prices.index)
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = evaluate(args.source_dir, prices, acquired_at_utc=captured)
    args.output_prices_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_prices_csv.write_text(p4l.canonical_csv(prices), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("P4R ORIGINAL 10-K 126-SESSION MATCHED SPY EVENT STUDY")
    print("Completed events:", report["completed_event_returns"],
          "right-censored:", report["right_censored_eligible_scores"])
    print("15bp score >=2:", report["summary"]["15"]["score_2_or_3"])
    print("15bp score <2:", report["summary"]["15"]["score_0_or_1"])
    print("2026 SURVIVORS / REVISABLE PRICES / NO VALIDATED ALPHA OR ORDERS")


if __name__ == "__main__":
    main()

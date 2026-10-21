"""P4K: frozen-selection stock forward MARKS within ONE later source vintage.

Observed adjusted-close MARKS are revisable, NOT verified fills/alpha/total returns.
No broker or network code. The old P4I source-vintage fail-closed policy remains.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd

import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_original_price_vintage_diff_p4j_v1_0 as p4j
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA = "FUND100_P4K_SINGLE_VINTAGE_POST_SELECTION_PRICE_MARK_V1"
FIRST_ENTRY = pd.Timestamp("2026-10-19")
SIDE_COST_BPS = (5, 15, 35)
RELEASED_TO_TRADE = False


class SingleVintageStop(ValueError):
    pass


def _observation_clock(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise SingleVintageStop("Missing timestamp on captured source")
    try:
        v = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise SingleVintageStop("Not a canonical UTC source timestamp") from exc
    if v.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise SingleVintageStop("Noncanonical capture timestamp")
    return v


def window_mark(*, anchor: dict, later_doc: dict, later_prices: pd.DataFrame,
                revision: dict) -> dict:
    """Pure source-consistent window; caller must separately authenticate bytes."""
    if (not isinstance(anchor, dict)
        or anchor.get("frozen_asof_completed_market_session") != p4i.FIRST_CUTOFF
        or anchor.get("original_preselected_watchlist") != p4i.FROZEN_WATCHLIST
        or anchor.get("reference_six_quality_cohort") != p4i.REFERENCE_COHORT
        or anchor.get("original_p4g_json_sha256") != p4i.ORIGINAL_JSON_SHA):
        raise SingleVintageStop("Original historic selection identity not pinned")
    if (not isinstance(later_doc, dict)
        or later_doc.get("schema") != p4g.SCHEMA
        or later_doc.get("status") !=
            "FORWARD_RESEARCH_SIGNAL_NOT_INVESTMENT_ALPHA"
        or later_doc.get("future_performance_observations") != 0
        or later_doc.get("paper_authorized") is not False
        or later_doc.get("live_authorized") is not False
        or later_doc.get("trading_authorized") is not False
        or later_doc.get("broker_orders") != 0):
        raise SingleVintageStop("Unacceptable later source research flags")
    data = p4g.validate_prices(later_prices)
    cutoff = pd.Timestamp(p4i.FIRST_CUTOFF)
    if (cutoff not in data.index
        or data.index[-1].date().isoformat() !=
            later_doc.get("asof_completed_session")):
        raise SingleVintageStop("Later session cutoff not comparable")
    clock = _observation_clock(later_doc.get("source_acquired_at_utc"))
    if (clock.date() <= data.index[-1].date()
        or clock.date() <= datetime.strptime(
            p4i.OBS_DATE, "%Y-%m-%d").date()
        or (clock.date() - data.index[-1].date()).days > 5):
        raise SingleVintageStop("Late, stale, impossible or backdated source capture")
    if (not isinstance(revision, dict)
        or revision.get("comparison_status") not in (
            "EXACT_PREFIX_PRESERVED", "DIFFERING_ORIGINAL_PRICE_CELLS")
        or revision.get("missing_original_sessions") != 0
        or revision.get("extra_baseline_sessions") != 0
        or revision.get("no_forward_return_calculated") is not True):
        raise SingleVintageStop("Unreconciled original historical sessions")
    future = data.index[data.index > cutoff]
    if len(future) and future[0] != FIRST_ENTRY:
        raise SingleVintageStop("Original first post-freeze entry session was lost")
    entry = future[0].date().isoformat() if len(future) else None
    end = future[-1].date().isoformat() if len(future) > 1 else None
    report = {
        "schema": SCHEMA,
        "status": "NO_ELIGIBLE_ENTRY_SESSION" if not len(future) else
                  "ENTRY_OBSERVED_NO_EXIT_MARK" if len(future) == 1 else
                  "OBSERVED_SAME_VINTAGE_ADJUSTED_CLOSE_WINDOW",
        "source_metric": "AS_CAPTURED_ADJUSTED_CLOSE_RETURN_MARK",
        "source_price_vintage_revisable": True,
        "source_vintage_confirmed_identical_within_entry_exit": True,
        "historical_source_prefix_status": revision["comparison_status"],
        "historical_prefix_can_differ_without_fabricating_returns": True,
        "original_signal_asof_completed_session": p4i.FIRST_CUTOFF,
        "original_watchlist": list(p4i.FROZEN_WATCHLIST),
        "original_six_stock_reference": list(p4i.REFERENCE_COHORT),
        "later_source_asof_session": later_doc["asof_completed_session"],
        "later_source_capture_utc": later_doc["source_acquired_at_utc"],
        "actual_new_sessions_in_later_source": len(future),
        "forward_observations": max(len(future) - 1, 0),
        "post_selection_entry_close_session": entry,
        "post_selection_exit_mark_session": end,
        "price_only_or_total_return_independently_verified": False,
        "corporate_actions_independently_verified": False,
        "independent_alpha_or_expected_profit_proven": False,
        "cagr_or_significance_inferred": False,
        "broker_fills_verified": False,
        "new_asset_class_released": False,
        "trading_authorized": False,
        "paper_orders": 0, "live_orders": 0, "broker_requests": 0,
        "costed_mark_percent": None,
    }
    if len(future) < 2:
        return report
    first = data.index.get_loc(future[0])
    final = data.index.get_loc(future[-1])
    gross = {
        "frozen_three": p4h._gross_return(
            data, first, final, p4i.FROZEN_WATCHLIST),
        "frozen_equal_six": p4h._gross_return(
            data, first, final, p4i.REFERENCE_COHORT),
        "spy": p4h._gross_return(data, first, final, ["SPY"]),
    }
    costed = {}
    for bps in SIDE_COST_BPS:
        c = bps / 10_000
        m = {k: 100 * ((1 + v) * (1 - c) ** 2 - 1)
             for k, v in gross.items()}
        costed[str(bps)] = {
            "one_way_cost_bps": bps,
            "frozen_three_gross_mark_pct": round(100 * gross["frozen_three"], 6),
            "frozen_three_net_mark_pct": round(m["frozen_three"], 6),
            "spy_net_mark_pct": round(m["spy"], 6),
            "frozen_equal_six_net_mark_pct": round(m["frozen_equal_six"], 6),
            "frozen_three_minus_spy_net_pp":
                round(m["frozen_three"] - m["spy"], 6),
            "frozen_three_minus_six_net_pp":
                round(m["frozen_three"] - m["frozen_equal_six"], 6),
            "modelled_entry_and_exit_costs_no_fills": True,
        }
    report["costed_mark_percent"] = costed
    return report


def evaluate(original_json: Path, original_csv: Path,
             followup_json: Path, followup_csv: Path,
             anchor_path: Path = p4i.ANCHOR_FILE) -> dict:
    anchor, anchor_sha = p4i.read_anchor(anchor_path)
    # Authentic archive hash and signal checks never weakened from P4I.
    verified = p4i.verify_first_archive(anchor, original_json, original_csv)
    old, original_prices, original_json_sha = p4h.read_snapshot(
        original_json, original_csv)
    later, new_prices, later_json_sha = p4h.read_snapshot(
        followup_json, followup_csv)
    if (old["asof_completed_session"] != p4i.FIRST_CUTOFF
        or original_json_sha != p4i.ORIGINAL_JSON_SHA
        or later["asof_completed_session"] <= p4i.FIRST_CUTOFF
        or later["source_acquired_at_utc"] <= old["source_acquired_at_utc"]):
        raise SingleVintageStop("Original or later source provenance not chronological")
    revision = p4j.classify(
        original_prices, new_prices,
        original_anchor_digest=anchor["original_p4g_canonical_price_csv_sha256"],
        source_original_digest=old["canonical_price_csv_sha256"],
    )
    report = window_mark(
        anchor=anchor, later_doc=later, later_prices=new_prices,
        revision=revision)
    report.update({
        "original_p4g_run_id": p4j.ORIGINAL_RUN,
        "original_p4g_artifact_id": p4j.ORIGINAL_ARTIFACT,
        "original_anchor_sha256": anchor_sha,
        "original_archive_sha_verified": verified[
            "original_artifact_fingerprint_verified"],
        "original_json_sha256": original_json_sha,
        "original_csv_sha256": old["canonical_price_csv_sha256"],
        "later_p4g_run_id": p4j.FOLLOWUP_RUN,
        "later_p4g_artifact_id": p4j.FOLLOWUP_ARTIFACT,
        "later_json_sha256": later_json_sha,
        "later_canonical_csv_sha256": later["canonical_price_csv_sha256"],
        "old_vendor_adjustments_source_identical": (
            revision["comparison_status"] == "EXACT_PREFIX_PRESERVED"),
        "first_observed_close_bid_ask_source_verified": False,
        "original_live_holdings_touched": False,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    for item in ("original-json", "original-csv", "later-json", "later-csv", "output"):
        parser.add_argument("--" + item, type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(
        args.original_json, args.original_csv, args.later_json, args.later_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("P4K_WINDOW", report["status"])
    print("FROZEN_SECTOR_STOCKS", "/".join(report["original_watchlist"]))
    print("POST_FREEZE_ENTRY", report["post_selection_entry_close_session"])
    print("EXIT_OBSERVATION", report["post_selection_exit_mark_session"])
    print("AVAILABLE_SESSIONS", report["actual_new_sessions_in_later_source"])
    print("OLD_PREFIX", report["historical_source_prefix_status"])
    print("AS_CAPTURED_MARK_ONLY, NO TRADING")


if __name__ == "__main__":
    main()

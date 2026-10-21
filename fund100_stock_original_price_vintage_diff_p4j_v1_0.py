"""P4J: original P4G price-vintage mismatch diagnostic, NO performance claims.

Input artifacts already captured by genuine GitHub Actions P4G executions.
Only compare their pinned historical prefix; never write or place orders.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA = "FUND100_P4J_GENUINE_PRICE_VINTAGE_DIFF_V1"
ORIGINAL_RUN = 39015519726
FOLLOWUP_RUN = 39571738927
ORIGINAL_ARTIFACT = 12094995126
FOLLOWUP_ARTIFACT = 12332028291


class SourceDiffStop(ValueError):
    pass


def classify(original: pd.DataFrame, followup: pd.DataFrame, *,
             original_anchor_digest: str, source_original_digest: str) -> dict:
    """Pure frame comparison; public prices are not returned in diagnostic."""
    if (type(original_anchor_digest) is not str or
        type(source_original_digest) is not str or
        original_anchor_digest != source_original_digest):
        raise SourceDiffStop("Original source digest is not the frozen baseline")
    old = p4g.validate_prices(original)
    new = p4g.validate_prices(followup)
    cutoff = pd.Timestamp(p4i.FIRST_CUTOFF)
    if old.index[-1] != cutoff:
        raise SourceDiffStop("Original source cutoff is not the frozen 16 October session")
    if new.index[-1] <= cutoff:
        raise SourceDiffStop("Later source lacks any genuinely newer market session")
    hist = new.loc[:cutoff]
    missing = old.index.difference(hist.index)
    extra = hist.index.difference(old.index)
    # Date arithmetic is only about source identity, not simulated returns.
    if len(missing) or len(extra) or not hist.index.equals(old.index):
        return {
            "comparison_status": "MISSING_OR_REORDERED_BASELINE_SESSIONS",
            "original_historical_sessions": len(old),
            "later_historical_sessions": len(hist),
            "missing_original_sessions": len(missing),
            "extra_baseline_sessions": len(extra),
            "symbols_with_changed_history": None,
            "first_differing_session": None,
            "no_forward_return_calculated": True,
        }
    changed = {}
    earliest = None
    for ticker in sorted(old.columns):
        # Both P4G canonical validated series contain exact same symbol universe.
        unequal = old[ticker].ne(hist[ticker])
        count = int(unequal.sum())
        if not count:
            continue
        first = old.index[unequal][0].date().isoformat()
        if earliest is None or first < earliest:
            earliest = first
        ratios = ((hist.loc[unequal, ticker] / old.loc[unequal, ticker]) - 1).abs()
        changed[ticker] = {
            "original_sessions_with_changed_price": count,
            "first_change_session": first,
            "max_absolute_fractional_price_difference": round(float(ratios.max()), 10),
        }
    return {
        "comparison_status":
            "DIFFERING_ORIGINAL_PRICE_CELLS" if changed else "EXACT_PREFIX_PRESERVED",
        "original_historical_sessions": len(old),
        "later_historical_sessions": len(hist),
        "missing_original_sessions": 0,
        "extra_baseline_sessions": 0,
        "symbols_with_changed_history": changed,
        "first_differing_session": earliest,
        "no_forward_return_calculated": True,
    }


def inspect(original_json: Path, original_csv: Path,
            later_json: Path, later_csv: Path,
            anchor_path: Path = p4i.ANCHOR_FILE) -> dict:
    anchor, anchored_file_sha = p4i.read_anchor(anchor_path)
    first, original, digest = p4h.read_snapshot(original_json, original_csv)
    second, later, later_digest = p4h.read_snapshot(later_json, later_csv)
    if (first["asof_completed_session"] != p4i.FIRST_CUTOFF or
        first["source_acquired_at_utc"][:10] != p4i.OBS_DATE or
        first["research_watchlist"] != p4i.FROZEN_WATCHLIST or
        first["comparison_cohort_equal_weight"] != p4i.REFERENCE_COHORT or
        digest != p4i.ORIGINAL_JSON_SHA or
        digest != anchor["original_p4g_json_sha256"] or
        first["canonical_price_csv_sha256"] != p4i.ORIGINAL_CSV_SHA or
        first["canonical_price_csv_sha256"] !=
            anchor["original_p4g_canonical_price_csv_sha256"] or
        second["asof_completed_session"] <= first["asof_completed_session"] or
        second["source_acquired_at_utc"] <= first["source_acquired_at_utc"] or
        second["research_watchlist"] is None):
        raise SourceDiffStop("Original or later authenticated source identity changed")
    src = classify(
        original, later,
        original_anchor_digest=anchor["original_p4g_canonical_price_csv_sha256"],
        source_original_digest=first["canonical_price_csv_sha256"],
    )
    return {
        "schema": SCHEMA,
        "original_artifact_run_id": ORIGINAL_RUN,
        "original_artifact_id": ORIGINAL_ARTIFACT,
        "followup_artifact_run_id": FOLLOWUP_RUN,
        "followup_artifact_id": FOLLOWUP_ARTIFACT,
        "original_anchor_file_sha256": anchored_file_sha,
        "original_p4g_json_sha256": digest,
        "original_price_csv_sha256": first["canonical_price_csv_sha256"],
        "later_p4g_json_sha256": later_digest,
        "later_price_csv_sha256": second["canonical_price_csv_sha256"],
        "original_frozen_selection": p4i.FROZEN_WATCHLIST,
        "comparison_asof_session": second["asof_completed_session"],
        **src,
        "cause_of_difference_independently_proven": False,
        "original_artifact_not_modified": True,
        "research_signal_not_reselected": True,
        "no_raw_vendor_prices_republished": True,
        "not_proof_of_alpha": True,
        "portfolio_cash_policy_changed": False,
        "trading_authorized": False,
        "paper_orders": 0,
        "live_orders": 0,
        "broker_requests": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for opt in ("original-json", "original-csv", "later-json", "later-csv", "output"):
        parser.add_argument("--" + opt, required=True, type=Path)
    args = parser.parse_args()
    out = inspect(args.original_json, args.original_csv, args.later_json,
                  args.later_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    print("P4J_OLD_VINTAGE_STATUS", out["comparison_status"])
    print("P4J_DIFFERENT_TICKERS", len(out["symbols_with_changed_history"] or {}))
    print("P4J_FIRST_DIFFERENT_SESSION", out["first_differing_session"])
    print("ORIGINAL_SIGNAL_UNCHANGED, NO_FORWARD_PROFIT, NO_ORDERS")


if __name__ == "__main__":
    main()

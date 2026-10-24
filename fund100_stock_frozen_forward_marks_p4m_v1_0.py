"""P4M: source-consistent forward marks for the ORIGINAL P4L 24-stock selection.

Never backfill a strategy return before the first post-selection NYSE close.
Original GitHub Actions run/artifact identity is pinned by the read-only
research workflow. Vendor adjusted closes remain revisable and unverified as
independent total returns. No broker credentials, network, orders or LIVE policy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_single_vintage_forward_marks_p4k_v1_0 as p4k

SCHEMA = "FUND100_P4M_FROZEN_24_STOCK_FORWARD_MARKS_V1"
ORIGINAL_RUN_ID = 40057272409
ORIGINAL_ARTIFACT_ID = 12545733087
ORIGINAL_HEAD_SHA = "e519515f224caaad6a6450bac6e2af875ec8eed6"
ORIGINAL_ARTIFACT_ZIP_SHA256 = "ea8b0a9f8143e51d1b26c66657bbec24e8b887ed7d93a19bb57e44f68f5ac4db"
ORIGINAL_SELECTION = ["MSFT", "CVX", "XOM", "DIS", "MA", "V"]
ORIGINAL_SESSION = "2026-10-23"
FIRST_ENTRY = pd.Timestamp("2026-10-26")
COSTS_BPS = (5, 15, 35)


class P4MStop(ValueError):
    pass


def _clock(value: object) -> datetime:
    if type(value) is not str:
        raise P4MStop("Missing source acquisition timestamp")
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise P4MStop("Noncanonical UTC acquisition timestamp") from exc
    if result.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise P4MStop("Noncanonical UTC acquisition timestamp")
    return result


def _verified(doc: dict, prices: pd.DataFrame) -> pd.DataFrame:
    if type(doc) is not dict:
        raise P4MStop("Missing original research snapshot")
    try:
        data = p4l.validate_prices(prices)
        regenerated = p4l.evaluate(
            data,
            acquired_at_utc=doc.get("source_acquired_at_utc"),
            provider_reference=doc.get("source_reference"),
        )
    except (p4l.BroadStockStop, TypeError, ValueError) as exc:
        raise P4MStop("Invalid P4L source snapshot") from exc
    # Full re-evaluation protects the actual selected names, not merely a
    # self-declared source hash or mutable selection list.
    if doc != regenerated:
        raise P4MStop("P4L report does not match original source prices")
    if (doc["broker_orders"] != 0 or doc["paper_authorized"] is not False
        or doc["live_authorized"] is not False or doc["trading_authorized"] is not False):
        raise P4MStop("Research source claimed execution authority")
    return data


def _read_snapshot(report: Path, csv_path: Path) -> tuple[dict, pd.DataFrame, str]:
    raw = csv_path.read_bytes()
    try:
        doc = json.loads(report.read_text(encoding="utf-8"))
        frame = pd.read_csv(csv_path, index_col="Date", parse_dates=["Date"])
        data = _verified(doc, frame)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise P4MStop("Missing or malformed archived P4L source") from exc
    if raw != p4l.canonical_csv(data).encode("utf-8"):
        raise P4MStop("Noncanonical or altered source CSV")
    digest = hashlib.sha256(raw).hexdigest()
    if doc["canonical_price_csv_sha256"] != digest:
        raise P4MStop("Source CSV SHA256 mismatch")
    return doc, data, digest


def _wealth(prices: pd.DataFrame, entry: int, exit: int,
            symbols: list[str]) -> list[float]:
    return p4k._gross_buy_hold_wealth_path(prices, entry, exit, symbols)


def window_mark(original_doc: dict, original_prices: pd.DataFrame,
                later_doc: dict, later_prices: pd.DataFrame) -> dict:
    original = _verified(original_doc, original_prices)
    later = _verified(later_doc, later_prices)
    if (original_doc["asof_completed_session"] != ORIGINAL_SESSION
        or original.index[-1] != pd.Timestamp(ORIGINAL_SESSION)
        or original_doc["momentum_only_watchlist"] != ORIGINAL_SELECTION):
        raise P4MStop("Original 23 October P4L watchlist was not preserved")
    if (_clock(original_doc["source_acquired_at_utc"]).date()
            != pd.Timestamp("2026-10-24").date()):
        raise P4MStop("Original source acquisition not on frozen cohort date")
    if (_clock(later_doc["source_acquired_at_utc"])
            < _clock(original_doc["source_acquired_at_utc"])
        or later.index[-1] < original.index[-1]):
        raise P4MStop("Later source predates frozen selection")
    if not original.index.equals(later.index[:len(original.index)]):
        raise P4MStop("Original historical sessions missing or reordered")
    # Historical adjusted prices may legitimately revise. NEVER splice an
    # original-vintage entry with a later-vintage exit.
    changed = (original.to_numpy() !=
               later.iloc[:len(original)].loc[:, original.columns].to_numpy())
    revised_cells = int(changed.sum())
    future = later.index[later.index > pd.Timestamp(ORIGINAL_SESSION)]
    try:
        p4k._verified_future_sessions(pd.Timestamp(ORIGINAL_SESSION), later.index)
    except p4k.SingleVintageStop as exc:
        raise P4MStop("Missing or extra post-selection XNYS sessions") from exc
    if len(future) and future[0] != FIRST_ENTRY:
        raise P4MStop("First post-selection NYSE close missing")
    status = ("WAITING_FOR_FIRST_POST_SELECTION_CLOSE" if len(future) == 0
              else "ENTRY_CLOSE_ONLY_NO_RETURN" if len(future) == 1
              else "SOURCE_CONSISTENT_POST_SELECTION_MARKS")
    result = {
        "schema": SCHEMA,
        "status": status,
        "frozen_source_run_id": ORIGINAL_RUN_ID,
        "frozen_source_artifact_id": ORIGINAL_ARTIFACT_ID,
        "frozen_source_head_sha": ORIGINAL_HEAD_SHA,
        "frozen_selection_session": ORIGINAL_SESSION,
        "frozen_selection": list(ORIGINAL_SELECTION),
        "original_source_csv_sha256": original_doc["canonical_price_csv_sha256"],
        "later_source_csv_sha256": later_doc["canonical_price_csv_sha256"],
        "later_capture_utc": later_doc["source_acquired_at_utc"],
        "later_asof_completed_session": later_doc["asof_completed_session"],
        "historical_adjusted_price_cells_revised": revised_cells,
        "historical_prefix_not_spliced_into_forward_marks": True,
        "first_post_selection_entry_session": future[0].date().isoformat() if len(future) else None,
        "last_post_selection_mark_session": future[-1].date().isoformat() if len(future) > 1 else None,
        "observed_post_selection_sessions": len(future),
        "observed_forward_return_intervals": max(0, len(future) - 1),
        "same_later_source_vintage_for_entry_and_exit": True,
        "all_post_selection_nyse_sessions_verified": True,
        "price_vintage_independently_authenticated": False,
        "dividends_and_corporate_actions_independently_verified": False,
        "historical_survivorship_safe": False,
        "statistically_valid_alpha_or_future_profit_proven": False,
        "costed_marks_percent": None,
        "gross_path_downside": None,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "paper_authorized": False, "live_authorized": False,
        "trading_authorized": False,
    }
    if len(future) < 2:
        return result
    first = later.index.get_loc(future[0])
    final = later.index.get_loc(future[-1])
    groups = {
        "frozen_six": ORIGINAL_SELECTION,
        "equal_weight_24": sorted(p4l.SECTORS),
        "spy": [p4l.BENCHMARK],
    }
    wealth = {key: _wealth(later, first, final, names)
              for key, names in groups.items()}
    result["gross_path_downside"] = {
        **{key: p4k._path_downside(path) for key, path in wealth.items()},
        "frozen_six_relative_to_spy": p4k._path_downside(
            [a / b for a, b in zip(wealth["frozen_six"], wealth["spy"])]),
        "same_vintage_daily_closes_no_intraday_fill_claim": True,
    }
    gross = {key: path[-1] - 1 for key, path in wealth.items()}
    costed = {}
    for bps in COSTS_BPS:
        cost = bps / 10000
        net = {key: 100 * ((1 + value) * (1 - cost) ** 2 - 1)
               for key, value in gross.items()}
        costed[str(bps)] = {
            "one_way_cost_bps": bps,
            "frozen_six_gross_mark_pct": round(gross["frozen_six"] * 100, 6),
            "frozen_six_net_mark_pct": round(net["frozen_six"], 6),
            "equal_weight_24_net_mark_pct": round(net["equal_weight_24"], 6),
            "spy_net_mark_pct": round(net["spy"], 6),
            "frozen_six_minus_spy_net_pp": round(net["frozen_six"] - net["spy"], 6),
            "frozen_six_minus_equal_24_net_pp": round(
                net["frozen_six"] - net["equal_weight_24"], 6),
            "hypothetical_round_trip_costs_no_broker_fills": True,
        }
    result["costed_marks_percent"] = costed
    return result


def evaluate(original_json: Path, original_csv: Path,
             later_json: Path, later_csv: Path) -> dict:
    original, old, _ = _read_snapshot(original_json, original_csv)
    later, new, _ = _read_snapshot(later_json, later_csv)
    return window_mark(original, old, later, new)


def main() -> None:
    parser = argparse.ArgumentParser()
    for arg in ("original-json", "original-csv", "later-json", "later-csv", "output"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(args.original_json, args.original_csv,
                      args.later_json, args.later_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("P4M frozen 24-stock forward marks:", report["status"],
          "intervals", report["observed_forward_return_intervals"])
    print("Revisable vendor marks only; no historical backtest, fills or orders.")


if __name__ == "__main__":
    main()

"""Phase 3 C3: observed WTI two-contract term structure, RESEARCH ONLY.

RCLC1/RCLC2 are EIA *continuous ranked* NYMEX WTI contract settlements,
NOT identified contracts or a daily record of the DBIQ optimum-yield DBC
basket. Positive-quote backwardation/contango classification is a feature,
NOT earned roll yield, annualized carry, trade price or a trade signal.

EIA NYMEX futures data DISCONTINUED after 2024-04-05. Reject later dates.
One-off provider history may be revised; require date/source metadata and
a separately fixed release delay. No LIVE/PAPER/broker capability.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

EIA_CUTOFF = pd.Timestamp("2024-04-05")
SOURCES = ("RCLC1", "RCLC2")
RELEASE_POLICY = "OBSERVATION_PLUS_TWO_US_WEEKDAYS_ASSUMED_NOT_VERIFIED"
MIN_OBSERVATIONS = 60
MIN_VALID_PAIRS = 30
MONTHLY_MIN_VALID_OBS = 5
TRADING_ALLOWED = False


class CurveResearchStop(ValueError):
    pass


def validate_source(frame: pd.DataFrame) -> pd.DataFrame:
    expected = {"observation_date", "available_date", "RCLC1", "RCLC2"}
    if not isinstance(frame, pd.DataFrame) or set(frame.columns) != expected:
        raise CurveResearchStop("Expected dated RCLC1/RCLC2 observed settlement pairs.")
    if len(frame) < MIN_OBSERVATIONS:
        raise CurveResearchStop("Insufficient EIA WTI paired observations.")
    data = frame.copy()
    for col in ("observation_date", "available_date"):
        series = data[col]
        if not pd.api.types.is_datetime64_any_dtype(series):
            raise CurveResearchStop("Observation/availability dates must be parsed.")
        if series.dt.tz is not None or (series != series.dt.normalize()).any():
            raise CurveResearchStop("Macro dates must be naive calendar days.")
    if (
        not data["observation_date"].is_monotonic_increasing
        or data["observation_date"].duplicated().any()
        or not data["available_date"].is_monotonic_increasing
        or (data["available_date"] < data["observation_date"]).any()
        or (data["observation_date"] > EIA_CUTOFF).any()
    ):
        raise CurveResearchStop("Nonchronological, future-available or post-EIA-end prices.")
    for sym in SOURCES:
        if not pd.api.types.is_numeric_dtype(data[sym]):
            raise CurveResearchStop("Non-numeric continuous futures settlement.")
        quotes = data[sym].to_numpy(dtype=float)
        if not np.isfinite(quotes).all() or (np.abs(quotes) > 1000).any():
            raise CurveResearchStop("Missing/nonfinite/implausible EIA settlements.")
    # Important: do NOT treat negative WTI April 2020 settlement as
    # nonexistent. Permit negative quotes and quarantine percentage metrics.
    return data


def input_sha256(data: pd.DataFrame) -> str:
    data = validate_source(data)
    raw = data.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.8f")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify(front: float, second: float) -> tuple[str, float | None]:
    a, b = float(front), float(second)
    if not isfinite(a) or not isfinite(b):
        raise CurveResearchStop("Unreliable EIA input quote.")
    if a <= 0 or b <= 0:
        return "NONPOSITIVE_SETTLEMENT_NO_PCT_CARRY", None
    normalized = (a / b) - 1.0
    if normalized > 0:
        state = "WTI_BACKWARDATION"
    elif normalized < 0:
        state = "WTI_CONTANGO"
    else:
        state = "WTI_FLAT"
    return state, normalized


def features(data: pd.DataFrame) -> pd.DataFrame:
    history = validate_source(data)
    records = []
    for row in history.itertuples(index=False):
        state, spread_pct = classify(row.RCLC1, row.RCLC2)
        records.append({
            "observation_date": row.observation_date,
            "available_date": row.available_date,
            "wti_state": state,
            "front_minus_second_dollars_per_bbl": round(float(row.RCLC1 - row.RCLC2), 6),
            "front_over_second_minus_one": spread_pct,
            "usable_for_positive_pct_proxy": spread_pct is not None,
        })
    return pd.DataFrame.from_records(records)


def monthly_features(data: pd.DataFrame) -> pd.DataFrame:
    """A historical classification of WTI only, never a DBC return."""
    feat = features(data)
    rows = []
    feat["month"] = feat["observation_date"].dt.to_period("M")
    for month, group in feat.groupby("month", sort=True):
        valid = group.loc[group["usable_for_positive_pct_proxy"]]
        if len(valid) < MONTHLY_MIN_VALID_OBS:
            continue
        proxy = float(valid["front_over_second_minus_one"].median())
        rows.append({
            "month": str(month),
            "median_wti_front_over_second_minus_one": round(proxy, 8),
            "positive_quote_pair_days": int(len(valid)),
            "excluded_nonpositive_quote_days": int(len(group) - len(valid)),
            "last_observation_date": group["observation_date"].max().date().isoformat(),
            "last_assumed_available_date": group["available_date"].max().date().isoformat(),
            "wti_only_not_dbc_roll_return": True,
        })
    return pd.DataFrame(rows)


def report(data: pd.DataFrame) -> dict[str, Any]:
    validated = validate_source(data)
    signals = features(validated)
    months = monthly_features(validated)
    valid = signals.loc[signals["usable_for_positive_pct_proxy"]]
    if len(valid) < MIN_VALID_PAIRS:
        raise CurveResearchStop("Too few positive quote pairs for descriptive study.")
    states = valid["wti_state"].value_counts().to_dict()
    return {
        "schema": "FUND100_PHASE3_C3_WTI_CURVE_EXPLORATORY_V1",
        "status": "RESEARCH_ONLY_NO_PROMOTION",
        "dataset_sha256": input_sha256(validated),
        "source": "US EIA NYMEX Futures Prices, daily RCLC1 and RCLC2",
        "source_series": list(SOURCES),
        "source_observation_cutoff": EIA_CUTOFF.date().isoformat(),
        "available_lag_claim": RELEASE_POLICY,
        "actual_release_vintages_verified": False,
        "continuous_contract_rank_not_identified_contract_ids": True,
        "term_structure_is_wti_only_not_dbc_basket": True,
        "dbc_index_methodology_changed_2025_11_10": True,
        "wti_spread_is_not_futures_roll_pnl_or_realized_carry": True,
        "c3_strategy_backtest_performed": False,
        "broker_order_count": 0,
        "live_authorized": False,
        "paper_authorized": False,
        "record_count": len(validated),
        "first_observation_date": validated["observation_date"].iloc[0].date().isoformat(),
        "last_observation_date": validated["observation_date"].iloc[-1].date().isoformat(),
        "nonpositive_quote_rows": int((~signals["usable_for_positive_pct_proxy"]).sum()),
        "positive_quote_pairs": len(valid),
        "backwardation_days": int(states.get("WTI_BACKWARDATION", 0)),
        "contango_days": int(states.get("WTI_CONTANGO", 0)),
        "flat_days": int(states.get("WTI_FLAT", 0)),
        "historical_months_with_at_least_five_valid_pairs": int(len(months)),
        "last_monthly_wti_observation": (months.iloc[-1]["month"] if len(months) else None),
        "forward_carry_signal_current_as_of_2026": False,
        "next_required_dataset": "Identified expiries, documented DBC index constituent/roll weights, "
                                 "verified settlement release timestamps after 2024-04-05",
    }


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--curve-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    data = pd.read_csv(
        args.curve_csv, parse_dates=["observation_date", "available_date"],
    )
    result = report(data)
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("C3 EIA historical WTI term structure research; NOT 2026 current signal.")
    print("EIA dataset SHA256:", result["dataset_sha256"])
    print("Observed dates:", result["first_observation_date"], "to", result["last_observation_date"])
    print("Historical quoted pairs:", result["positive_quote_pairs"])
    print("Backwardation days:", result["backwardation_days"],
          "; contango days:", result["contango_days"])
    print("Nonpositive quote days quarantined:", result["nonpositive_quote_rows"])
    print("DBC index carry calculated: NO; actual futures roll PnL calculated: NO.")
    print("Brokerage routes, LIVE/PAPER orders, permissions: ZERO.")


if __name__ == "__main__":
    main()

"""Cost-vs-selection attribution for the actual immutable Fund-100 Forward Lab.

This is an exact algebraic *same-realized-weight* gross-return reconstruction,
NOT a genuinely executable no-cost strategy or a valid test of alpha.
Reads the existing forward ledger and manifest; no prices, broker,
private state or model parameter search, and no trading authority.
"""
from __future__ import annotations

from hashlib import sha256
import argparse
import json
from math import isfinite, log1p, sqrt
from numbers import Real
from pathlib import Path

import pandas as pd

import fund100_forward as base
import fund100_forward_evidence_scorecard_v1_0 as verified

SCHEMA = "FUND100_FORWARD_GROSS_SELECTION_VERSUS_COSTS_RESEARCH_V1"
LIVE_AUTHORIZED = MODEL_PROMOTION_AUTHORIZED = False
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
METRIC_TOLERANCE = 1e-8


class AttributionStop(ValueError):
    pass


def _num(value):
    if type(value) is bool or not isinstance(value, Real) or not isfinite(float(value)):
        raise AttributionStop("Non-finite original forward daily component")
    return float(value)


def _corr(a, b):
    n = len(a)
    if n != len(b) or n < 5:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va < 1e-22 or vb < 1e-22:
        return None
    return round(
        max(-1.0, min(1.0, sum((x-ma)*(y-mb) for x,y in zip(a,b))
                  / sqrt(va * vb))), 8)


def analyze(ledger: pd.DataFrame, manifest: dict) -> dict:
    # Fully validate source hash chain, frozen strategy manifest, exact
    # complete XNYS dates and recovered-vs-FORWARD classifications FIRST.
    validated = verified.analyze(ledger, manifest)
    models = {}
    strict_market = {}
    for name in base.MODELS:
        rows = ledger.loc[ledger["strategy"] == name].sort_values("date")
        if len(rows) <= 1:
            raise AttributionStop("No prospective source for gross comparison")
        gross_nav = float(base.PAPER_START_NAV)
        strict_market[name] = []
        gross_log_strict = 0.0
        gross_log_recovered = 0.0
        drag_log_strict = 0.0
        drag_log_recovered = 0.0
        all_cost_drag = 0.0
        for ix, (_, row) in enumerate(rows.iterrows()):
            try:
                payload = json.loads(row["payload_json"])
            except (ValueError, TypeError):
                raise AttributionStop("Unparseable active-return payload") from None
            if ix == 0:
                continue
            net_daily = _num(payload.get("daily_return"))
            bm_daily = _num(payload.get("benchmark_return"))
            gross_active = _num(payload.get("gross_overlay_return"))
            net_active = _num(payload.get("active_return"))
            cost_drag = _num(payload.get("cost_drag_return"))
            actual_net_daily = _num(row["nav"]) / _num(
                rows.iloc[ix - 1]["nav"]) - 1
            actual_bm_daily = _num(row["benchmark_nav"]) / _num(
                rows.iloc[ix - 1]["benchmark_nav"]) - 1
            gross_daily = bm_daily + gross_active
            if (min(1 + net_daily, 1 + bm_daily, 1 + gross_daily) <= 0
                or abs(net_daily - actual_net_daily) > METRIC_TOLERANCE
                or abs(bm_daily - actual_bm_daily) > METRIC_TOLERANCE
                or abs(net_daily - bm_daily - net_active) > METRIC_TOLERANCE
                or abs(net_daily - gross_daily - cost_drag) > METRIC_TOLERANCE
                or cost_drag > METRIC_TOLERANCE):
                raise AttributionStop("Original signed daily gross/cost components disagree")
            gross_nav *= 1 + gross_daily
            all_cost_drag += cost_drag
            gross_log = 100 * (log1p(gross_daily) - log1p(bm_daily))
            drag_log = 100 * (log1p(net_daily) - log1p(gross_daily))
            if row["row_type"] == "FORWARD":
                strict_market[name].append(gross_active)
                gross_log_strict += gross_log
                drag_log_strict += drag_log
            elif row["row_type"] == "RECOVERED_AFTER_OUTAGE":
                gross_log_recovered += gross_log
                drag_log_recovered += drag_log
            else:
                raise AttributionStop("Nonbaseline observation lacks source provenance")
        summary = validated["models"][name]
        bm_nav = _num(summary["final_acwi_nav_units"])
        net_nav = _num(summary["final_paper_nav_units"])
        if gross_nav < net_nav - 1e-7:
            raise AttributionStop("Gross same-weight path smaller than net path")
        models[name] = {
            "strict_forward_intervals": summary["strict_forward_intervals"],
            "recovered_after_outage_intervals": summary["recovered_after_outage_intervals"],
            "same_weight_path_gross_before_cost_nav": round(gross_nav, 9),
            "actual_original_paper_after_cost_nav": round(net_nav, 9),
            "acwi_benchmark_nav": round(bm_nav, 9),
            "same_weight_path_cost_effect_nav_units": round(gross_nav - net_nav, 9),
            "gross_selection_minus_acwi_total_return_pp": round(gross_nav - bm_nav, 8),
            "net_strategy_minus_acwi_total_return_pp":
                summary["strategy_minus_acwi_total_return_percentage_points"],
            "strict_forward_gross_selection_log_relative_wealth_pp":
                round(gross_log_strict, 8),
            "strict_forward_cost_drag_log_relative_wealth_pp":
                round(drag_log_strict, 8),
            "recovered_gross_selection_log_relative_wealth_pp":
                round(gross_log_recovered, 8),
            "recovered_cost_drag_log_relative_wealth_pp":
                round(drag_log_recovered, 8),
            "strict_forward_market_gross_intervals": len(strict_market[name]),
            "gross_selection_was_negative_after_modeled_cost_removal":
                gross_nav < bm_nav,
            "source_history_hash_last": summary["last_chain_hash"],
        }
        if (abs((gross_log_strict+gross_log_recovered+
                 drag_log_strict+drag_log_recovered) -
                summary["total_active_log_relative_wealth_contribution_pp"])
            > 0.000001):
            raise AttributionStop("Attribution does not reconcile with original scorecard")
    correlations = {}
    for i, left in enumerate(base.MODELS):
        for right in base.MODELS[i+1:]:
            correlations[left+"__"+right] = _corr(
                strict_market[left], strict_market[right])
    highly_similar = bool(correlations) and all(
        v is not None and v >= 0.95 for v in correlations.values())
    gross_lags = all(
        row["gross_selection_was_negative_after_modeled_cost_removal"]
        for row in models.values())
    if gross_lags and highly_similar:
        research = "GROSS_SELECTION_LAG_WITH_NEAR_DUPLICATE_OVERLAYS_RESEARCH_ONLY"
    elif gross_lags:
        research = "GROSS_SELECTION_LAG_ALL_MODELS_RESEARCH_ONLY"
    else:
        research = "MIXED_GROSS_SELECTION_AND_COST_DIAGNOSTIC_RESEARCH_ONLY"
    return {
        "schema": SCHEMA, "status": research,
        "models": models,
        "strict_forward_gross_active_return_correlations": correlations,
        "all_original_models_highly_similar_on_strict_forward_observations":
            highly_similar,
        "all_original_models_gross_selection_lags_acwi": gross_lags,
        "gross_path_is_same_realized_weights_not_recomputed_no_fee_strategy": True,
        "recovered_source_rows_never_qualified_as_pristine_forward": True,
        "model_selection_or_strategy_promotion_authorized": False,
        "research_alone_cannot_require_waiting_for_new_forward_months": True,
        "paper_returns_are_not_broker_fills": True,
        "broker_GETs": 0, "broker_POSTs": 0, "broker_orders": 0,
        "live_order_authorized": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, default=base.LEDGER_PATH)
    p.add_argument("--manifest", type=Path, default=base.MANIFEST_PATH)
    p.add_argument("--output", type=Path,
                   default=base.OUTPUT_DIR / "latest_forward_active_attribution.json")
    a = p.parse_args()
    raw = a.ledger.read_bytes()
    result = analyze(pd.read_csv(a.ledger), json.loads(a.manifest.read_text()))
    result["source_ledger_file_sha256"] = sha256(raw).hexdigest()
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["status"], "research only, zero broker calls/orders")
    for name, entry in result["models"].items():
        print(name, "gross selection vs ACWI pp:",
              entry["gross_selection_minus_acwi_total_return_pp"],
              "modeled cost NAV units:",
              entry["same_weight_path_cost_effect_nav_units"])


if __name__ == "__main__":
    main()

"""S1 cash-entry exposure comparison using ORIGINAL frozen research history.

Hypotheses fixed before new 98% result: same XLK/XLE/IWM 50/30/20;
95% / 98% / 100% gross-at-rebalance targets, 5/15/35 bps costs.
Historical sensitivity, NOT independent alpha or execution permission.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_l1_fixed_mix_attribution_v1_0 as original
import fund100_v6_s1_exact95_costed_cash_floor_v1_0 as s1

SCHEMA = "FUND100_V6_ENTRY_CASH_HISTORICAL_SENSITIVITY_V1"
TARGETS = {
    "BASELINE_95": {"XLK": .475, "XLE": .285, "IWM": .190},
    "LOW_BUFFER_98": {"XLK": .490, "XLE": .294, "IWM": .196},
    "FULLY_ALLOCATED_100": {"XLK": .500, "XLE": .300, "IWM": .200},
}
EXPECTED_COSTS = (5, 15, 35)
PERIODS = {"2014_onward": "2014-01-01", "2020_onward": "2020-01-01"}


class CashComparisonStop(ValueError):
    pass


def _locked() -> None:
    s1.verify_contract()
    if (TARGETS["BASELINE_95"] != s1.TARGET
        or TARGETS["FULLY_ALLOCATED_100"] != l1.FULL
        or tuple(l1.COST_BPS) != EXPECTED_COSTS
        or l1.BAND != .10
        or set(TARGETS) != {"BASELINE_95","LOW_BUFFER_98","FULLY_ALLOCATED_100"}):
        raise CashComparisonStop("Research target or cost preregistration changed")
    for policy, weights in TARGETS.items():
        gross = {"BASELINE_95": .95, "LOW_BUFFER_98": .98,
                 "FULLY_ALLOCATED_100": 1.00}[policy]
        if set(weights) != set(l1.NAMES):
            raise CashComparisonStop("Unregistered market universe")
        if any(abs(weights[s] - l1.FULL[s]*gross) > 1e-12 for s in l1.NAMES):
            raise CashComparisonStop("Sector mix changed in response to results")


def evaluate(prices: pd.DataFrame, *, original_source_sha256: str) -> dict:
    _locked()
    if original_source_sha256 != l1.ORIGINAL_SHA:
        raise CashComparisonStop("Not original frozen historical price source")
    validated = l1.validate(prices)
    results = {}
    for cost in EXPECTED_COSTS:
        series = {k: s1.simulate(validated, cost_bps=cost, targets=w)
                  for k, w in TARGETS.items()}
        old95 = s1.simulate(validated, cost_bps=cost)
        old100 = original.fixed_mix(validated, cost_bps=cost)
        # Prove exact NAV/turnover parity with original previously studied models.
        for key, comparator in (("BASELINE_95", old95),
                                ("FULLY_ALLOCATED_100", old100)):
            fresh = series[key]
            if (not fresh.index.equals(comparator.index)
                or abs(float(fresh["nav"].iloc[-1]/comparator["nav"].iloc[-1]-1)) > 1e-10
                or abs(float(fresh["turnover"].sum()-comparator["turnover"].sum())) > 1e-9
                or int(fresh["trade"].sum()) != int(comparator["trade"].sum())):
                raise CashComparisonStop("Prior-original comparator regression mismatch")
        sections = {}
        for label, date in PERIODS.items():
            metrics = {key: l1.metrics(frame, date) for key, frame in series.items()}
            sections[label] = {
                "by_cash_entry_policy": metrics,
                "entry_98_minus_95_cagr_percentage_points": round(
                    metrics["LOW_BUFFER_98"]["nav"]["annual_return_pct"]
                    - metrics["BASELINE_95"]["nav"]["annual_return_pct"], 5),
                "entry_100_minus_95_cagr_percentage_points": round(
                    metrics["FULLY_ALLOCATED_100"]["nav"]["annual_return_pct"]
                    - metrics["BASELINE_95"]["nav"]["annual_return_pct"], 5),
                "reference_ACWI_annual_return_pct":
                    metrics["BASELINE_95"]["acwi_nav"]["annual_return_pct"],
                "backtest_winner_cannot_auto_select_cash_policy": True,
            }
        results[str(cost)] = sections
    return {
        "schema": SCHEMA,
        "original_frozen_source_sha256": original_source_sha256,
        "original_sector_50_30_20_mixture_preserved": True,
        "cash_policy_weights_at_rebalance": TARGETS,
        "original_costs_one_way_bps": list(EXPECTED_COSTS),
        "research_previously_examined_not_out_of_sample": True,
        "cash_level_between_rebalances_is_uncontrolled": True,
        "not_a_new_alpha_strategy": True,
        "new_live_policy_promoted": False,
        "live_positions_changed": False,
        "broker_requests": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-history", type=Path,
                        default=Path("research_lab/frozen_history_v2.csv"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prices, digest = l1.load_frozen(args.frozen_history)
    result = evaluate(prices, original_source_sha256=digest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    for cost, section in result["results"].items():
        for label, part in section.items():
            for k, v in part["by_cash_entry_policy"].items():
                m = v["nav"]
                print("CASH_SENSITIVITY", cost, label, k,
                      "CAGR_PCT", m["annual_return_pct"],
                      "MAX_DD_PCT", m["max_drawdown_pct"],
                      "REALIZED_VOL_PCT", m["annual_realised_volatility_pct"])
    print("HISTORICAL_ONLY NO_TRADING", result["live_orders"])


if __name__ == "__main__":
    main()

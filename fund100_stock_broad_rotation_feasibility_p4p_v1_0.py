"""P4P: costed MONTHLY turnover feasibility for the contemporary P4L stock roster.

A diagnostic on a roster chosen in October 2026, NOT a historical
survivorship-safe or point-in-time stock backtest. No inference of alpha.
Signals use only the completed prior month-end close, and hypothetical
execution is deferred to the NEXT completed close; returns start thereafter.
No brokerage access, credentials, trades, or LIVE risk policy changes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_frozen_forward_marks_p4m_v1_0 as p4m
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA = "FUND100_P4P_CONTEMPORARY_ROSTER_HISTORICAL_FEASIBILITY_V1"
SIDE_COSTS = (5, 15, 35)
ANNUALIZATION_NOT_JUSTIFIED = True


class FeasibilityStop(ValueError):
    pass


def _month_end(index: pd.DatetimeIndex, t: int) -> bool:
    return t + 1 < len(index) and index[t].month != index[t + 1].month


def _select(prices: pd.DataFrame, t: int) -> list[str]:
    """Exact original 126/63 signal and six-name/two-per-sector rules.

    Decision observes close t only; caller executes at close t+1.
    """
    if t < p4l.LOOKBACK:
        raise FeasibilityStop("Insufficient historical momentum lookback")
    spy63 = prices[p4l.BENCHMARK].iloc[t] / prices[p4l.BENCHMARK].iloc[t - p4l.RELATIVE_LOOKBACK] - 1
    eligible = []
    for symbol, sector in p4l.SECTORS.items():
        absolute = prices[symbol].iloc[t] / prices[symbol].iloc[t - p4l.LOOKBACK] - 1
        relative = prices[symbol].iloc[t] / prices[symbol].iloc[t - p4l.RELATIVE_LOOKBACK] - 1 - spy63
        if absolute > 0 and relative > 0:
            eligible.append((-round(float(relative), 8), symbol, sector))
    eligible.sort()
    chosen: list[str] = []
    sectors: dict[str, int] = {}
    for _, symbol, sector in eligible:
        if len(chosen) >= p4l.MAX_NAMES:
            break
        if sectors.get(sector, 0) < p4l.MAX_PER_SECTOR:
            chosen.append(symbol)
            sectors[sector] = sectors.get(sector, 0) + 1
    return chosen


def _drawdown(path: list[float]) -> float:
    arr = np.asarray(path, dtype=float)
    return float((arr / np.maximum.accumulate(arr) - 1).min())


def _simulate(prices: pd.DataFrame, signal_i: int, cost_bps: int) -> dict:
    if cost_bps not in SIDE_COSTS:
        raise FeasibilityStop("Only predeclared 5/15/35 bps per-side costs")
    start = signal_i + 1
    c = cost_bps / 10000
    nav = 1.0
    # Multiplicative fee factor isolates selection/market P&L from trading
    # friction WITHOUT changing any historical signal, holding or rebalance.
    cost_factor = 1.0
    weights: dict[str, float] = {}
    cash = 1.0
    pending = (start, signal_i, _select(prices, signal_i))
    path: list[float] = []
    decisions: list[dict] = []
    one_way_turnover = 0.0
    cash_history: list[float] = []
    for t in range(start, len(prices)):
        if t > start:
            gross = cash + sum(
                weight * float(prices[s].iloc[t] / prices[s].iloc[t - 1])
                for s, weight in weights.items()
            )
            if not np.isfinite(gross) or gross <= 0:
                raise FeasibilityStop("Impossible price-relative portfolio return")
            nav *= gross
            weights = {
                s: weight * float(prices[s].iloc[t] / prices[s].iloc[t - 1]) / gross
                for s, weight in weights.items()
            }
            cash /= gross
        if pending is not None and pending[0] == t:
            _, decision_t, chosen = pending
            target = {s: 1.0 / p4l.MAX_NAMES for s in chosen}
            turnover = sum(
                abs(target.get(s, 0.0) - weights.get(s, 0.0))
                for s in set(target) | set(weights)
            )
            fee_factor = 1 - c * turnover
            if fee_factor <= 0:
                raise FeasibilityStop("Invalid transaction-cost factor")
            nav *= fee_factor
            cost_factor *= fee_factor
            one_way_turnover += turnover
            weights = target
            cash = 1.0 - sum(target.values())
            decisions.append({
                "signal_session": prices.index[decision_t].date().isoformat(),
                "execution_close_session": prices.index[t].date().isoformat(),
                "selected": list(chosen),
                "one_way_turnover_fraction": round(turnover, 8),
            })
            pending = None
        cash_history.append(cash)
        path.append(nav)
        if _month_end(prices.index, t) and t >= p4l.LOOKBACK:
            pending = (t + 1, t, _select(prices, t))
    # Hypothetical exit cost on final close; no actual sale or broker fill.
    exit_turnover = sum(weights.values())
    exit_fee_factor = 1 - c * exit_turnover
    if exit_fee_factor <= 0:
        raise FeasibilityStop("Invalid terminal transaction-cost factor")
    nav *= exit_fee_factor
    cost_factor *= exit_fee_factor
    one_way_turnover += exit_turnover
    path[-1] = nav
    if (not np.isfinite(nav) or nav <= 0 or not np.isfinite(cost_factor)
        or cost_factor <= 0):
        raise FeasibilityStop("Invalid terminal hypothetical portfolio wealth")
    # Portfolio weights are not affected by proportional fees: removing
    # their product recovers EXACTLY the same holdings path before costs.
    gross_nav = nav / cost_factor

    start_prices = prices.iloc[start]
    end_prices = prices.iloc[-1]
    spy_gross = float(end_prices[p4l.BENCHMARK] / start_prices[p4l.BENCHMARK])
    equal24_gross = float(np.mean(
        (end_prices[list(p4l.SECTORS)] / start_prices[list(p4l.SECTORS)]).to_numpy()
    ))
    # Two-sided entry/exit for passive buy-and-hold comparators, and
    # actual gross notional turnover at every rotation for the strategy.
    spy_net = spy_gross * (1 - c) ** 2
    equal24_net = equal24_gross * (1 - c) ** 2
    return {
        "entry_execution_close": prices.index[start].date().isoformat(),
        "last_exit_mark_close": prices.index[-1].date().isoformat(),
        "observed_return_intervals": len(prices) - start - 1,
        "month_end_signal_count": len(decisions),
        "signals_and_next_close_execution": decisions,
        "total_one_way_turnover_including_entry_exit": round(one_way_turnover, 6),
        "average_cash_weight_pct": round(100 * float(np.mean(cash_history)), 4),
        "max_drawdown_hypothetical_pct": round(100 * _drawdown(path), 4),
        "strategy_net_return_pct": round(100 * (nav - 1), 6),
        "strategy_pre_cost_return_pct": round(100 * (gross_nav - 1), 6),
        "spy_passive_pre_cost_return_pct": round(100 * (spy_gross - 1), 6),
        "equal24_passive_pre_cost_return_pct": round(100 * (equal24_gross - 1), 6),
        "strategy_pre_cost_minus_spy_pp": round(100 * (gross_nav - spy_gross), 6),
        "strategy_pre_cost_minus_equal24_pp": round(100 * (gross_nav - equal24_gross), 6),
        "strategy_modelled_cost_drag_pp": round(100 * (gross_nav - nav), 6),
        "spy_passive_modelled_cost_drag_pp": round(100 * (spy_gross - spy_net), 6),
        "strategy_vs_spy_incremental_cost_drag_pp": round(
            100 * ((gross_nav - spy_gross) - (nav - spy_net)), 6),
        "pre_cost_result_not_evidence_of_point_in_time_alpha": True,
        "spy_passive_net_return_pct": round(100 * (spy_net - 1), 6),
        "equal24_passive_net_return_pct": round(100 * (equal24_net - 1), 6),
        "strategy_minus_spy_net_pp": round(100 * (nav - spy_net), 6),
        "strategy_minus_equal24_net_pp": round(100 * (nav - equal24_net), 6),
    }


def analyze(prices: pd.DataFrame, *, source_sha256: str) -> dict:
    try:
        data = p4l.validate_prices(prices)
        p4g.verify_original_nyse_source_sessions(data.index)
    except (p4l.BroadStockStop, p4g.P4GStop) as exc:
        raise FeasibilityStop("Incomplete or invalid original NYSE market source") from exc
    canonical_sha = sha256(p4l.canonical_csv(data).encode("utf-8")).hexdigest()
    if source_sha256 != canonical_sha:
        raise FeasibilityStop("Original source fingerprint mismatch")
    eligible = [
        i for i in range(p4l.LOOKBACK, len(data) - 2)
        if _month_end(data.index, i)
    ]
    if not eligible:
        raise FeasibilityStop("Insufficient completed post-lookback month-end sessions")
    first = eligible[0]
    scenarios = {str(bps): _simulate(data, first, bps) for bps in SIDE_COSTS}
    return {
        "schema": SCHEMA,
        "status": "HINDSIGHT_SELECTED_ROSTER_FEASIBILITY_ONLY_NOT_ALPHA",
        "source_canonical_csv_sha256": canonical_sha,
        "source_first_session": data.index[0].date().isoformat(),
        "source_last_session": data.index[-1].date().isoformat(),
        "historical_roster_selected_only_on_2026_10_24": True,
        "survivorship_and_sector_history_not_point_in_time": True,
        "corporate_actions_and_total_returns_not_independently_verified": True,
        "adjusted_price_vendor_vintage_revisable": True,
        "not_a_historical_investable_strategy_backtest": True,
        "cannot_infer_alpha_or_expected_return": True,
        "no_annualized_CAGR_or_statistical_significance": ANNUALIZATION_NOT_JUSTIFIED,
        "predeclared_month_end_signal_next_session_close_execution": True,
        "cash_assumed_zero_yield": True,
        "transaction_costs_exclude_market_impact_and_tax": True,
        "pre_cost_selection_vs_friction_attribution_same_decisions": True,
        "pre_cost_is_not_a_tradeable_zero_friction_strategy": True,
        "initial_month_end_signal": data.index[first].date().isoformat(),
        "per_side_cost_scenarios_bps": list(SIDE_COSTS),
        "scenarios": scenarios,
        "research_only": True,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "trading_authorized": False, "paper_authorized": False,
        "live_authorized": False,
    }


def evaluate(source_json: Path, source_csv: Path) -> dict:
    # Same strict P4M original-source verification; never trust a self-declared
    # hash or silently mix revised historical vendor snapshots.
    doc, prices, digest = p4m._read_snapshot(source_json, source_csv)
    result = analyze(prices, source_sha256=digest)
    if doc["canonical_price_csv_sha256"] != result["source_canonical_csv_sha256"]:
        raise FeasibilityStop("Original dated P4L report and prices disagree")
    result["source_acquired_at_utc"] = doc["source_acquired_at_utc"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.source_json, args.source_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    base = report["scenarios"]["15"]
    print("P4P CONTEMPORARY ROSTER COSTED FEASIBILITY ONLY",
          "15bps strategy", base["strategy_net_return_pct"],
          "SPY", base["spy_passive_net_return_pct"],
          "gross_strategy_minus_spy_pp", base["strategy_pre_cost_minus_spy_pp"],
          "incremental_cost_drag_pp", base["strategy_vs_spy_incremental_cost_drag_pp"],
          "turnover", base["total_one_way_turnover_including_entry_exit"])
    print("HINDSIGHT ROSTER, NO ALPHA, NO ORDERS, NO LIVE AUTHORIZATION")


if __name__ == "__main__":
    main()

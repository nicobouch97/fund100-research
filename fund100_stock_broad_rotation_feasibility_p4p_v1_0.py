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
from math import sqrt
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


def _risk_path(path: list[float], sessions: int) -> dict:
    """Entry and exit fees belong to actual observed market sessions.

    Include the initial 1.0 wealth anchor so a first-close purchase cost
    cannot disappear from drawdown. Never append a fictitious liquidation day.
    """
    arr = np.asarray(path, dtype=float)
    if (len(arr) != sessions + 1 or sessions < 2
        or not np.isfinite(arr).all() or (arr <= 0).any()):
        raise FeasibilityStop("Invalid cost-inclusive market-session wealth path")
    returns = arr[1:] / arr[:-1] - 1
    return {
        "max_drawdown": float((arr / np.maximum.accumulate(arr) - 1).min()),
        "annualized_volatility": float(np.std(returns, ddof=1) * sqrt(252)),
        "worst_session_return": float(returns.min()),
    }



def _spy_at_strategy_decision_exposure(
    prices: pd.DataFrame, start: int, decisions: list[dict], cost: float,
) -> dict:
    """Costed SPY/cash control with the strategy's *decision-time* equity budget.

    A selected stock consumes 1/MAX_NAMES of notional. At each strategy
    execution close, the comparator sets SPY to that total target; between
    decisions it drifts with SPY and earns zero on cash. This is NOT a
    point-in-time historical investable strategy or an independently chosen
    signal, nor is its daily cash weight exactly the strategy's daily weight.
    """
    if not 0 <= cost < 1 or start < 0 or start >= len(prices) - 1:
        raise FeasibilityStop("Invalid exposure-matched comparator configuration")
    targets = {}
    for decision in decisions:
        day = decision["execution_close_session"]
        chosen = decision["selected"]
        if (day in targets or len(chosen) > p4l.MAX_NAMES
            or len(chosen) != len(set(chosen))
            or any(s not in p4l.SECTORS for s in chosen)):
            raise FeasibilityStop("Invalid comparator decision exposure")
        targets[day] = len(chosen) / p4l.MAX_NAMES
    sessions = [d.date().isoformat() for d in prices.index[start:]]
    if set(targets) - set(sessions) or sessions[0] not in targets:
        raise FeasibilityStop("Comparator decision outside observed sessions")
    nav = 1.0
    equity = 0.0
    cash = 1.0
    turnover = 0.0
    path = [nav]
    for t in range(start, len(prices)):
        if t > start:
            relative = float(prices[p4l.BENCHMARK].iloc[t] /
                             prices[p4l.BENCHMARK].iloc[t - 1])
            gross = cash + equity * relative
            if not np.isfinite(gross) or gross <= 0:
                raise FeasibilityStop("Invalid comparator SPY market return")
            nav *= gross
            equity = equity * relative / gross
            cash /= gross
        target = targets.get(sessions[t - start])
        if target is not None:
            traded = abs(target - equity)
            nav *= 1 - cost * traded
            turnover += traded
            equity = target
            cash = 1 - target
        path.append(nav)
    # Hypothetical terminal liquidation on the last REAL session.
    nav *= 1 - cost * equity
    turnover += equity
    path[-1] = nav
    if not np.isfinite(nav) or nav <= 0:
        raise FeasibilityStop("Invalid costed comparator wealth")
    return {"terminal_wealth": nav, "path": path, "one_way_turnover": turnover}


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
    # Preserve the pre-entry wealth anchor; the first close charges entry fees.
    path: list[float] = [1.0]
    decisions: list[dict] = []
    one_way_turnover = 0.0
    cash_history: list[float] = []
    # Chain-linked arithmetic contribution to terminal GROSS wealth. This
    # is path attribution, not a causal counterfactual or an alpha estimate.
    gross_symbol_contributions = {s: 0.0 for s in p4l.SECTORS}
    for t in range(start, len(prices)):
        if t > start:
            relatives = {
                s: float(prices[s].iloc[t] / prices[s].iloc[t - 1])
                for s in weights
            }
            gross = cash + sum(
                weight * relatives[s] for s, weight in weights.items()
            )
            if not np.isfinite(gross) or gross <= 0:
                raise FeasibilityStop("Impossible price-relative portfolio return")
            # If C_{t-1} sums to gross_wealth_{t-1}-1, then
            # C_t = gross_t*C_{t-1} + sum(w_s*(relative_s-1)).
            # Consequently the final ticker contributions add EXACTLY to
            # terminal gross wealth minus one, including after rotations.
            for symbol in gross_symbol_contributions:
                gross_symbol_contributions[symbol] *= gross
            for symbol, weight in weights.items():
                gross_symbol_contributions[symbol] += weight * (relatives[symbol] - 1)
            nav *= gross
            weights = {
                s: weight * relatives[s] / gross
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
    # Decompose the equal-24 buy-and-hold gross benchmark using its fixed
    # inception weights. Subtracting ticker by ticker yields an exact
    # descriptive active gross attribution against the SAME 24-name roster.
    equal24_symbol_contributions = {
        s: float(end_prices[s] / start_prices[s] - 1) / len(p4l.SECTORS)
        for s in p4l.SECTORS
    }
    active_symbol_contributions = {
        s: gross_symbol_contributions[s] - equal24_symbol_contributions[s]
        for s in p4l.SECTORS
    }
    sectors = sorted(set(p4l.SECTORS.values()))
    gross_sector_contributions = {
        sector: sum(gross_symbol_contributions[s]
                    for s, group in p4l.SECTORS.items() if group == sector)
        for sector in sectors
    }
    active_sector_contributions = {
        sector: sum(active_symbol_contributions[s]
                    for s, group in p4l.SECTORS.items() if group == sector)
        for sector in sectors
    }
    gross_error = gross_nav - 1 - sum(gross_symbol_contributions.values())
    active_error = (gross_nav - equal24_gross
                    - sum(active_symbol_contributions.values()))
    if abs(gross_error) > 1e-9 or abs(active_error) > 1e-9:
        raise FeasibilityStop("Gross stock attribution failed wealth reconciliation")
    # Two-sided entry/exit for passive buy-and-hold comparators, and
    # actual gross notional turnover at every rotation for the strategy.
    spy_net = spy_gross * (1 - c) ** 2
    equal24_net = equal24_gross * (1 - c) ** 2

    # Passive controls use their actual buy-and-hold wealth paths rather than
    # only a terminal return. This is the SAME execution-close window as the
    # rotating strategy, including entry cost on the first close and final
    # liquidation cost on the last close, with no invented extra session.
    spy_relatives = (prices[p4l.BENCHMARK].iloc[start:] /
                     start_prices[p4l.BENCHMARK]).to_numpy(dtype=float)
    equal24_relatives = (prices[list(p4l.SECTORS)].iloc[start:] /
                         start_prices[list(p4l.SECTORS)]).mean(axis=1).to_numpy(dtype=float)
    spy_path = [1.0] + list((1 - c) * spy_relatives)
    equal24_path = [1.0] + list((1 - c) * equal24_relatives)
    spy_path[-1] *= 1 - c
    equal24_path[-1] *= 1 - c
    if (abs(spy_path[-1] - spy_net) > 1e-10
        or abs(equal24_path[-1] - equal24_net) > 1e-10):
        raise FeasibilityStop("Passive costed risk and terminal return disagree")
    sessions = len(prices) - start
    strategy_risk = _risk_path(path, sessions)
    spy_risk = _risk_path(spy_path, sessions)
    equal24_risk = _risk_path(equal24_path, sessions)
    # Control for the strategy's varying equity budget without falsely
    # treating a 100%-equity SPY benchmark as the same risk exposure.
    exposure_spy = _spy_at_strategy_decision_exposure(prices, start, decisions, c)
    exposure_spy_gross = _spy_at_strategy_decision_exposure(
        prices, start, decisions, 0.0)
    exposure_spy_risk = _risk_path(exposure_spy["path"], sessions)
    if exposure_spy["terminal_wealth"] > exposure_spy_gross["terminal_wealth"] + 1e-10:
        raise FeasibilityStop("Costed comparator exceeds its gross wealth")
    return {
        "entry_execution_close": prices.index[start].date().isoformat(),
        "last_exit_mark_close": prices.index[-1].date().isoformat(),
        "observed_return_intervals": len(prices) - start - 1,
        "month_end_signal_count": len(decisions),
        "signals_and_next_close_execution": decisions,
        "total_one_way_turnover_including_entry_exit": round(one_way_turnover, 6),
        "average_cash_weight_pct": round(100 * float(np.mean(cash_history)), 4),
        "max_drawdown_hypothetical_pct": round(
            100 * strategy_risk["max_drawdown"], 4),
        "spy_passive_max_drawdown_hypothetical_pct": round(
            100 * spy_risk["max_drawdown"], 4),
        "equal24_passive_max_drawdown_hypothetical_pct": round(
            100 * equal24_risk["max_drawdown"], 4),
        "strategy_annualized_volatility_fraction": round(
            strategy_risk["annualized_volatility"], 8),
        "spy_passive_annualized_volatility_fraction": round(
            spy_risk["annualized_volatility"], 8),
        "equal24_passive_annualized_volatility_fraction": round(
            equal24_risk["annualized_volatility"], 8),
        "strategy_worst_session_return_pct": round(
            100 * strategy_risk["worst_session_return"], 6),
        "spy_passive_worst_session_return_pct": round(
            100 * spy_risk["worst_session_return"], 6),
        "equal24_passive_worst_session_return_pct": round(
            100 * equal24_risk["worst_session_return"], 6),
        "risk_path_observed_sessions": sessions,
        "risk_paths_include_entry_and_exit_costs_on_actual_sessions": True,
        "passive_benchmarks_100pct_equity_not_cash_matched": True,
        "spy_decision_exposure_control_not_daily_cash_matched": True,
        "spy_decision_exposure_control_uses_same_strategy_signals": True,
        "spy_decision_exposure_control_cash_zero_yield": True,
        "spy_decision_exposure_net_return_pct": round(
            100 * (exposure_spy["terminal_wealth"] - 1), 6),
        "spy_decision_exposure_pre_cost_return_pct": round(
            100 * (exposure_spy_gross["terminal_wealth"] - 1), 6),
        "spy_decision_exposure_modelled_cost_drag_pp": round(
            100 * (exposure_spy_gross["terminal_wealth"] -
                   exposure_spy["terminal_wealth"]), 6),
        "spy_decision_exposure_one_way_turnover": round(
            exposure_spy["one_way_turnover"], 6),
        "strategy_minus_spy_decision_exposure_net_pp": round(
            100 * (nav - exposure_spy["terminal_wealth"]), 6),
        "spy_decision_exposure_max_drawdown_hypothetical_pct": round(
            100 * exposure_spy_risk["max_drawdown"], 4),
        "spy_decision_exposure_annualized_volatility_fraction": round(
            exposure_spy_risk["annualized_volatility"], 8),
        "spy_decision_exposure_worst_session_return_pct": round(
            100 * exposure_spy_risk["worst_session_return"], 6),
        "strategy_net_return_pct": round(100 * (nav - 1), 6),
        "strategy_pre_cost_return_pct": round(100 * (gross_nav - 1), 6),
        "spy_passive_pre_cost_return_pct": round(100 * (spy_gross - 1), 6),
        "equal24_passive_pre_cost_return_pct": round(100 * (equal24_gross - 1), 6),
        "strategy_pre_cost_minus_spy_pp": round(100 * (gross_nav - spy_gross), 6),
        "strategy_pre_cost_minus_equal24_pp": round(100 * (gross_nav - equal24_gross), 6),
        "gross_attribution_method": "CHAIN_LINKED_DAILY_RETURN_TO_TERMINAL_WEALTH",
        "gross_symbol_contribution_pct": {
            s: round(100 * gross_symbol_contributions[s], 6)
            for s in sorted(p4l.SECTORS)
        },
        "gross_sector_contribution_pct": {
            sector: round(100 * gross_sector_contributions[sector], 6)
            for sector in sectors
        },
        "gross_active_vs_equal24_symbol_pp": {
            s: round(100 * active_symbol_contributions[s], 6)
            for s in sorted(p4l.SECTORS)
        },
        "gross_active_vs_equal24_sector_pp": {
            sector: round(100 * active_sector_contributions[sector], 6)
            for sector in sectors
        },
        "gross_attribution_reconciliation_error_pp": round(100 * gross_error, 9),
        "gross_active_attribution_reconciliation_error_pp": round(100 * active_error, 9),
        "gross_attribution_is_path_dependent_not_causal_alpha": True,
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
        "costed_drawdown_volatility_and_worst_day_for_all_three_arms": True,
        "strategy_decision_exposure_spy_cash_control_is_descriptive": True,
        "gross_stock_sector_attribution_uses_same_decisions_and_prices": True,
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

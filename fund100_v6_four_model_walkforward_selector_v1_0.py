"""Causal historical switching among FOUR existing V6 model NAV paths.

This is an exploratory meta-allocation stress test on ALREADY-INSPECTED
historical prices. It is NOT a new independent holdout, executable model
replication, LIVE strategy, broker plan, or evidence of expected alpha.
The original four model signals and their costed NAVs are unchanged.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from fund100_v6_four_model_selection_uncertainty_v1_0 import MODELS

SCHEMA = "FUND100_V6_FOUR_MODEL_CAUSAL_QUARTERLY_SELECTOR_V1"
TRAINING_RETURNS = 252
START_WINDOWS = {"since_2014": "2014-01-01",
                 "since_2020": "2020-01-01",
                 "since_2023": "2023-01-01"}
SIDE_COST_BPS = (5, 15, 35)
HISTORICAL_DRAWDOWN_SCREEN = .20
HISTORICAL_VOL_SCREEN = .35
CASH = "CASH"
ANNUAL_SESSIONS = 252
# Single fixed, unoptimised downside-control research challenger.
VOL_TARGET_ANNUAL = 0.10
VOL_LOOKBACK_SESSIONS = 63


class WalkforwardStop(ValueError):
    pass


def _verified_paths(paths: dict) -> tuple[pd.DatetimeIndex, np.ndarray, dict]:
    if not isinstance(paths, dict) or set(paths) != set(MODELS):
        raise WalkforwardStop("Exactly four original model paths required")
    dates = None
    benchmark = None
    navs = {}
    for model in MODELS:
        frame = paths[model]
        if (not isinstance(frame, pd.DataFrame)
            or not {"nav", "benchmark"} <= set(frame.columns)
            or not isinstance(frame.index, pd.DatetimeIndex)
            or frame.index.tz is not None or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing):
            raise WalkforwardStop("Unverified model path or dated index")
        if dates is None:
            dates = frame.index
        elif not dates.equals(frame.index):
            raise WalkforwardStop("Model paths have different market sessions")
        values = frame[["nav", "benchmark"]].to_numpy(dtype=float)
        if (not np.isfinite(values).all() or (values <= 0).any()):
            raise WalkforwardStop("Missing or nonpositive original model NAV")
        if benchmark is None:
            benchmark = values[:, 1]
        elif not np.allclose(values[:, 1], benchmark, rtol=1e-12, atol=1e-9):
            raise WalkforwardStop("Model benchmarks disagree")
        navs[model] = values[:, 0]
    if len(dates) < TRAINING_RETURNS + 260:
        raise WalkforwardStop("Insufficient original model history")
    return dates, benchmark, navs


def _lagged_choice(benchmark: np.ndarray, navs: dict, t: int) -> str:
    """At session t close, rank ONLY through session t-1.

    A switch selected at t close can first earn the NEW model's return
    from t close to t+1 close. No same-session selected-model return.
    """
    if t < TRAINING_RETURNS + 1:
        return CASH
    b = benchmark[t - TRAINING_RETURNS - 1:t]
    b_growth = math.log(float(b[-1] / b[0]))
    eligible = []
    for model in MODELS:
        n = navs[model][t - TRAINING_RETURNS - 1:t]
        daily = n[1:] / n[:-1] - 1
        vol = float(np.std(daily, ddof=1) * math.sqrt(ANNUAL_SESSIONS))
        drawdown = float(np.min(n / np.maximum.accumulate(n) - 1))
        active = math.log(float(n[-1] / n[0])) - b_growth
        if (active > 0 and drawdown >= -HISTORICAL_DRAWDOWN_SCREEN
            and vol <= HISTORICAL_VOL_SCREEN):
            eligible.append((-active, model))
    return min(eligible)[1] if eligible else CASH


def _fixed_equal_model_blend(dates: pd.DatetimeIndex, navs: dict,
                             cost_bps: int) -> np.ndarray:
    """A precommitted, no-rebalance, four-sleeve comparator.

    Invest 25% in each original *costed* model at the same first eligible
    quarterly close as the selector. Hold sleeve units thereafter; original
    model turnover remains embedded in its NAV. Pay one synthetic entry
    side on total capital. No hindsight weights or intra-sleeve replication.
    """
    first = next((
        t for t in range(TRAINING_RETURNS + 1, len(dates))
        if dates[t].to_period("Q") != dates[t - 1].to_period("Q")
    ), None)
    if first is None:
        raise WalkforwardStop("No eligible quarterly comparator entry")
    out = np.full(len(dates), 100.0)
    entry_capital = 100.0 * (1 - cost_bps / 10000)
    for t in range(first, len(dates)):
        out[t] = entry_capital * sum(
            float(navs[model][t] / navs[model][first])
            for model in MODELS
        ) / len(MODELS)
    if not np.isfinite(out).all() or (out <= 0).any():
        raise WalkforwardStop("Invalid fixed four-model comparator NAV")
    return out



def _vol_target_fixed_blend(dates: pd.DatetimeIndex, navs: dict,
                            cost_bps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cash-only volatility scaling of the same fixed four costed model sleeves.

    At close t use the 63 returns THROUGH t to set next-session exposure.
    Apply t-1 exposure to the return ending at t, then pay the one-way
    cost for the exposure change at close t. No borrowing or shorts.
    A single predeclared 10% volatility target is NOT fitted to history.
    This is a synthetic NAV challenger, not replicable broker orders.
    """
    first = next((
        t for t in range(TRAINING_RETURNS + 1, len(dates))
        if dates[t].to_period("Q") != dates[t - 1].to_period("Q")
    ), None)
    if first is None or first < VOL_LOOKBACK_SESSIONS:
        raise WalkforwardStop("Insufficient causal blend-volatility history")
    raw = np.mean(np.vstack([
        navs[model] / navs[model][first] for model in MODELS
    ]), axis=0)
    if not np.isfinite(raw).all() or (raw <= 0).any():
        raise WalkforwardStop("Invalid original blend NAV")
    daily = raw[1:] / raw[:-1] - 1
    if not np.isfinite(daily).all() or (daily <= -1).any():
        raise WalkforwardStop("Invalid original blend returns")
    wealth = np.full(len(dates), 100.0)
    exposure = np.zeros(len(dates))
    turnover = np.zeros(len(dates))
    held = 0.0
    capital = 100.0
    for t in range(first, len(dates)):
        if t > first:
            # Exposure fixed at the preceding close: no same-close foresight.
            capital *= 1 + held * float(daily[t - 1])
        trailing = daily[t - VOL_LOOKBACK_SESSIONS:t]
        if len(trailing) != VOL_LOOKBACK_SESSIONS:
            raise WalkforwardStop("Incomplete trailing volatility history")
        annual_vol = float(np.std(trailing, ddof=1) * math.sqrt(ANNUAL_SESSIONS))
        if not math.isfinite(annual_vol):
            raise WalkforwardStop("Invalid trailing volatility")
        new = min(1.0, VOL_TARGET_ANNUAL / annual_vol) if annual_vol > 1e-12 else 1.0
        changed = abs(new - held)
        # Synthetic one-way trade cost, on current capital at each close.
        capital *= 1 - changed * cost_bps / 10000
        if not math.isfinite(capital) or capital <= 0 or not 0 <= new <= 1:
            raise WalkforwardStop("Invalid unlevered risk-controlled NAV")
        wealth[t] = capital
        exposure[t] = new
        turnover[t] = changed
        held = new
    return wealth, exposure, turnover

def _window_metrics(frame: pd.DataFrame, start: str) -> dict:
    view = frame.loc[start:]
    if len(view) < 260:
        raise WalkforwardStop("Insufficient historical comparison window")
    years = (view.index[-1] - view.index[0]).days / 365.25
    if years <= 0:
        raise WalkforwardStop("Invalid historical duration")
    wealth = view["selector_nav"]
    bench = view["acwi_nav"]
    blend = view["equal_model_blend_nav"]
    risk = view["vol_target_blend_nav"]
    risk_daily = risk.pct_change(fill_method=None).dropna()
    risk_annual = (risk.iloc[-1] / risk.iloc[0]) ** (1 / years) - 1
    risk_drawdown = risk / risk.cummax() - 1
    daily = wealth.pct_change(fill_method=None).dropna()
    annual = (wealth.iloc[-1] / wealth.iloc[0]) ** (1 / years) - 1
    baseline = (bench.iloc[-1] / bench.iloc[0]) ** (1 / years) - 1
    blend_annual = (blend.iloc[-1] / blend.iloc[0]) ** (1 / years) - 1
    return {
        "first_session": view.index[0].date().isoformat(),
        "last_session": view.index[-1].date().isoformat(),
        "sessions": len(view),
        "historical_selector_cagr_pct": round(float(100 * annual), 4),
        "historical_acwi_cagr_pct": round(float(100 * baseline), 4),
        "historical_excess_cagr_pp": round(float(100 * (annual - baseline)), 4),
        "historical_equal_model_blend_cagr_pct": round(float(100 * blend_annual), 4),
        "historical_vol_target_blend_cagr_pct": round(float(100 * risk_annual), 4),
        "historical_vol_target_minus_fixed_blend_cagr_pp": round(
            float(100 * (risk_annual - blend_annual)), 4),
        "historical_vol_target_blend_max_drawdown_pct": round(
            float(100 * risk_drawdown.min()), 4),
        "historical_vol_target_blend_realized_vol_pct": round(
            float(100 * risk_daily.std(ddof=1) * math.sqrt(ANNUAL_SESSIONS)), 4),
        "historical_vol_target_blend_average_exposure_pct": round(
            float(100 * view["vol_target_exposure_after_close"].mean()), 4),
        "historical_vol_target_blend_one_way_turnover_NAV": round(
            float(view["vol_target_turnover"].sum()), 4),
        "historical_vol_target_blend_20pct_drawdown_screen_breached": bool(
            risk_drawdown.min() < -HISTORICAL_DRAWDOWN_SCREEN),
        "historical_selector_minus_equal_blend_cagr_pp": round(
            float(100 * (annual - blend_annual)), 4),
        "historical_equal_blend_max_drawdown_pct": round(
            float(100 * (blend / blend.cummax() - 1).min()), 4),
        "historical_selector_max_drawdown_pct": round(
            float(100 * (wealth / wealth.cummax() - 1).min()), 4),
        "historical_selector_annual_volatility_pct": round(
            float(100 * daily.std(ddof=1) * math.sqrt(ANNUAL_SESSIONS)), 4),
        "historical_selector_worst_session_pct": round(
            float(100 * daily.min()), 4),
        "switches": int((view["switch_turnover"] > 0).sum()),
        "model_switch_one_way_notional_NAV": round(
            float(view["switch_turnover"].sum()), 4),
        "cash_held_sessions": int((view["held_during_session"] == CASH).sum()),
        "historical_20pct_drawdown_screen_breached": bool(
            (wealth / wealth.cummax() - 1).min() < -HISTORICAL_DRAWDOWN_SCREEN),
    }


def evaluate(paths: dict, *, switch_side_cost_bps: int) -> dict:
    """One fixed quarterly 252-session lagged rule; no fitted parameters.

    Original NAV paths already include original strategy turnover costs.
    Additional switch-side costs approximate *model-sleeve replacement*,
    not independently replicated underlying ETF holdings or actual fills.
    """
    if type(switch_side_cost_bps) is not int or switch_side_cost_bps not in SIDE_COST_BPS:
        raise WalkforwardStop("Only original 5/15/35bps cost scenarios allowed")
    dates, benchmark, navs = _verified_paths(paths)
    blend = _fixed_equal_model_blend(dates, navs, switch_side_cost_bps)
    risk_nav, risk_exposure, risk_turnover = _vol_target_fixed_blend(
        dates, navs, switch_side_cost_bps)
    chosen = CASH
    capital = 100.0
    rows = []
    for t, date in enumerate(dates):
        held = chosen
        if t and held != CASH:
            daily = float(navs[held][t] / navs[held][t - 1] - 1)
            if daily <= -1 or not math.isfinite(daily):
                raise WalkforwardStop("Impossible model return")
            capital *= 1 + daily
        new_choice = None
        turnover = 0
        # First session of each quarter, not a hindsight-detected last bar.
        # All 252 ranking returns end at the PREVIOUS completed close.
        if (t >= TRAINING_RETURNS + 1 and t
            and date.to_period("Q") != dates[t - 1].to_period("Q")):
            new_choice = _lagged_choice(benchmark, navs, t)
            if new_choice != chosen:
                turnover = (int(chosen != CASH) + int(new_choice != CASH))
                capital *= 1 - turnover * switch_side_cost_bps / 10000
                chosen = new_choice
        if not math.isfinite(capital) or capital <= 0:
            raise WalkforwardStop("Nonpositive hypothetical capital")
        rows.append({
            "date": date, "selector_nav": capital,
            "acwi_nav": 100.0 * float(benchmark[t] / benchmark[0]),
            "equal_model_blend_nav": float(blend[t]),
            "vol_target_blend_nav": float(risk_nav[t]),
            "vol_target_exposure_after_close": float(risk_exposure[t]),
            "vol_target_turnover": float(risk_turnover[t]),
            "held_during_session": held,
            "chosen_after_close": chosen,
            "quarterly_decision_after_close": new_choice,
            "switch_turnover": turnover,
        })
    frame = pd.DataFrame(rows).set_index("date")
    return {
        "schema": SCHEMA,
        "status": "EXPLORATORY_LAGGED_FOUR_MODEL_SWITCHING_ALREADY_STUDIED_HISTORY",
        "training_returns": TRAINING_RETURNS,
        "decision_at_first_quarter_session_close": True,
        "training_ends_at_previous_session_close": True,
        "new_model_first_earns_next_session_return": True,
        "model_paths_already_net_of_original_costs": True,
        "extra_switch_cost_bps_each_side": switch_side_cost_bps,
        "cash_yield_assumed_zero": True,
        "equal_model_blend_is_fixed_25pct_per_model_at_first_eligible_quarter": True,
        "equal_model_blend_rebalances_after_entry": False,
        "equal_model_blend_one_synthetic_entry_side_charged": True,
        "equal_model_blend_uses_only_original_costed_model_paths": True,
        "vol_target_blend_is_exploratory_cash_only_synthetic": True,
        "vol_target_blend_annual_volatility_target_pct": 10,
        "vol_target_blend_lookback_completed_sessions": VOL_LOOKBACK_SESSIONS,
        "vol_target_blend_decision_after_close_applies_next_session": True,
        "vol_target_blend_no_leverage_or_shorting": True,
        "vol_target_blend_extra_one_way_costs_included": True,
        "vol_target_blend_target_not_parameter_optimized": True,
        "historical_model_risk_screens_not_live_controls": True,
        "synthetic_model_sleeve_replication_not_verified": True,
        "historical_universe_and_models_already_inspected": True,
        "independent_out_of_sample_alpha_proven": False,
        "strategy_promoted_for_funded_trading": None,
        "paper_or_live_orders": 0,
        "terminal_hypothetical_selector_nav": round(capital, 6),
        "total_switches": int((frame["switch_turnover"] > 0).sum()),
        "comparison_windows": {
            name: _window_metrics(frame, start)
            for name, start in START_WINDOWS.items()
        },
    }

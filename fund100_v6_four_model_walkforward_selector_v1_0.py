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


def _window_metrics(frame: pd.DataFrame, start: str) -> dict:
    view = frame.loc[start:]
    if len(view) < 260:
        raise WalkforwardStop("Insufficient historical comparison window")
    years = (view.index[-1] - view.index[0]).days / 365.25
    if years <= 0:
        raise WalkforwardStop("Invalid historical duration")
    wealth = view["selector_nav"]
    bench = view["acwi_nav"]
    daily = wealth.pct_change(fill_method=None).dropna()
    annual = (wealth.iloc[-1] / wealth.iloc[0]) ** (1 / years) - 1
    baseline = (bench.iloc[-1] / bench.iloc[0]) ** (1 / years) - 1
    return {
        "first_session": view.index[0].date().isoformat(),
        "last_session": view.index[-1].date().isoformat(),
        "sessions": len(view),
        "historical_selector_cagr_pct": round(float(100 * annual), 4),
        "historical_acwi_cagr_pct": round(float(100 * baseline), 4),
        "historical_excess_cagr_pp": round(float(100 * (annual - baseline)), 4),
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
        "historical_model_risk_screens_not_live_controls": True,
        "synthetic_model_sleeve_replication_not_verified": True,
        "historical_universe_and_models_already_inspected": True,
        "independent_out_of_sample_alpha_proven": False,
        "strategy_promoted_for_funded_trading": None,
        "paper_or_live_orders": 0,
        "comparison_windows": {
            name: _window_metrics(frame, start)
            for name, start in START_WINDOWS.items()
        },
    }

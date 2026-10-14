"""Fund-100 Phase 2: isolated BOND ETF historical research, NEVER trading.

Price-only defensive trend hypothesis (NOT a yield-curve / carry model):
Compare TLT, IEF, TIP and LQD on lagged 63/126-session absolute AND
SHY-relative momentum. Hold at most two, with a separate TLT long-duration
concentration ceiling; remainder stays SHY. Evaluate against SHY after
costs. Training selection and untouched chronological holdout are separate.

Research cannot generate broker candidates, LIVE permissions, permits,
orders, or portfolio-level risk budgets. Vendor-adjusted historical
prices can be revised; prospective paper evidence is still required.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np
import pandas as pd

UNIVERSE = ("TLT", "IEF", "SHY", "TIP", "LQD")
SATELLITES = ("TLT", "IEF", "TIP", "LQD")
COST_SCENARIOS_BPS = (5, 15, 35)
CANDIDATES = ((63, 0.15), (63, 0.25), (126, 0.15), (126, 0.25))
MAX_TLT_WEIGHT = 0.15
MAX_NON_SHY_WEIGHT = 0.50
MIN_SESSIONS = 650
OUT_SAMPLE_FRACTION = 0.30


class BondResearchStop(ValueError):
    pass


def validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame) or not all(
        symbol in prices.columns for symbol in UNIVERSE
    ):
        raise BondResearchStop("Five required bond ETF adjusted-close series missing.")
    data = prices.loc[:, list(UNIVERSE)].copy()
    if len(data) < MIN_SESSIONS:
        raise BondResearchStop("Insufficient sessions for separate train and holdout.")
    if (
        not isinstance(data.index, pd.DatetimeIndex)
        or data.index.tz is not None
        or data.index.has_duplicates
        or not data.index.is_monotonic_increasing
        or any(x.time() != pd.Timestamp(x.date()).time() for x in data.index)
    ):
        raise BondResearchStop("Expected ascending, unique date-only sessions.")
    if not all(pd.api.types.is_numeric_dtype(data[c]) for c in UNIVERSE):
        raise BondResearchStop("Non-numeric ETF price series.")
    values = data.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise BondResearchStop("Missing, zero or non-finite adjusted ETF prices.")
    # Suspicious vendor discontinuities must be reviewed, not treated as alpha.
    raw_moves = data.pct_change().iloc[1:].to_numpy(dtype=float)
    if (np.abs(raw_moves) > 0.35).any():
        raise BondResearchStop("Abnormally large bond ETF session move.")
    return data


def source_hash(prices: pd.DataFrame) -> str:
    clean = validate_prices(prices)
    canonical = clean.to_csv(index=True, float_format="%.10f", date_format="%Y-%m-%d")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reference_weights(prices: pd.DataFrame, session: int,
                      lookback: int, per_satellite_cap: float) -> dict[str, float]:
    """At session t's close, decide solely from prices through t-1."""
    if lookback not in {63, 126} or per_satellite_cap not in {0.15, 0.25}:
        raise BondResearchStop("Unapproved candidate parameter.")
    if type(session) is not int or not (0 <= session < len(prices)):
        raise BondResearchStop("Invalid reference session.")
    weights = dict.fromkeys(UNIVERSE, 0.0)
    weights["SHY"] = 1.0
    if session <= lookback:
        return weights
    observation = session - 1
    history = observation - lookback
    trailing = prices.iloc[observation] / prices.iloc[history] - 1.0
    shy_return = float(trailing["SHY"])
    eligible = sorted(
        (
            (symbol, float(trailing[symbol]) - shy_return)
            for symbol in SATELLITES
            if float(trailing[symbol]) > 0 and
               float(trailing[symbol]) > shy_return
        ),
        key=lambda item: (-item[1], item[0]),
    )
    remaining = MAX_NON_SHY_WEIGHT
    for symbol, _ in eligible[:2]:
        cap = min(per_satellite_cap, MAX_TLT_WEIGHT) if symbol == "TLT" else per_satellite_cap
        allocation = min(cap, remaining)
        weights[symbol] = allocation
        remaining -= allocation
    weights["SHY"] = 1.0 - sum(weights[s] for s in SATELLITES)
    assert abs(sum(weights.values()) - 1.0) < 1e-10
    return weights


@dataclass
class Backtest:
    nav: pd.Series
    control_nav: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame


def backtest(prices: pd.DataFrame, *, lookback: int,
             cap: float, cost_bps: int) -> Backtest:
    """Signal at prior close; rebalance at session t CLOSE; affect t+1 return.

    Charges costs at t on absolute weight traded, including SHY legs.
    Holdings drift with close-to-close adjusted returns before rebalancing.
    """
    data = validate_prices(prices)
    if cost_bps not in COST_SCENARIOS_BPS:
        raise BondResearchStop("Unsupported one-way trading cost.")
    returns = data.pct_change().fillna(0.0)
    weights = {s: 0.0 for s in UNIVERSE}
    weights["SHY"] = 1.0
    nav, control = 100.0, 100.0
    navs, controls, turns, rows = [], [], [], []
    previous_month = None
    for i, (day, r) in enumerate(returns.iterrows()):
        gross = sum(weights[s] * float(r[s]) for s in UNIVERSE)
        if 1.0 + gross <= 0:
            raise BondResearchStop("Invalid portfolio return.")
        nav *= 1.0 + gross
        control *= 1.0 + float(r["SHY"])
        # Drift holdings BEFORE any t-close trade.
        weights = {
            s: weights[s] * (1.0 + float(r[s])) / (1.0 + gross)
            for s in UNIVERSE
        }
        turnover = 0.0
        month = (day.year, day.month)
        if i > 0 and month != previous_month:
            new = reference_weights(data, i, lookback, cap)
            turnover = sum(abs(new[s] - weights[s]) for s in UNIVERSE)
            nav *= 1.0 - turnover * cost_bps / 10000.0
            weights = new
        previous_month = month
        if nav <= 0 or control <= 0:
            raise BondResearchStop("Portfolio depleted in research simulation.")
        navs.append(nav)
        controls.append(control)
        turns.append(turnover)
        rows.append(weights.copy())
    return Backtest(
        nav=pd.Series(navs, index=data.index, dtype=float),
        control_nav=pd.Series(controls, index=data.index, dtype=float),
        turnover=pd.Series(turns, index=data.index, dtype=float),
        weights=pd.DataFrame(rows, index=data.index, columns=UNIVERSE),
    )


def metrics(result: Backtest, start: int, end: int) -> dict[str, float]:
    if not 0 <= start < end < len(result.nav):
        raise BondResearchStop("Invalid measurement window.")
    nav = result.nav.iloc[start:end + 1]
    control = result.control_nav.iloc[start:end + 1]
    sessions = end - start
    ratio = float(nav.iloc[-1] / nav.iloc[0])
    control_ratio = float(control.iloc[-1] / control.iloc[0])
    returns = nav.pct_change().dropna()
    std = float(returns.std(ddof=1))
    peak = nav.cummax()
    return {
        "sessions": sessions,
        "net_total_return": round(ratio - 1.0, 8),
        "shy_total_return": round(control_ratio - 1.0, 8),
        "net_excess_vs_shy": round(ratio - control_ratio, 8),
        "net_cagr": round(ratio ** (252.0 / sessions) - 1.0, 8),
        "shy_cagr": round(control_ratio ** (252.0 / sessions) - 1.0, 8),
        "annualized_volatility": round(std * sqrt(252), 8),
        "max_drawdown": round(float((1.0 - nav / peak).max()), 8),
        "one_way_turnover_sum": round(float(result.turnover.iloc[start+1:end+1].sum()), 8),
    }


def analyze(prices: pd.DataFrame) -> dict[str, Any]:
    data = validate_prices(prices)
    split = int(len(data) * (1.0 - OUT_SAMPLE_FRACTION))
    if split < 365 or len(data) - split < 126:
        raise BondResearchStop("Cannot form adequately separated evaluation windows.")
    trained = []
    for lookback, cap in CANDIDATES:
        path = backtest(data, lookback=lookback, cap=cap, cost_bps=15)
        outcome = metrics(path, 0, split-1)
        trained.append((outcome["net_excess_vs_shy"], -outcome["max_drawdown"],
                        -outcome["one_way_turnover_sum"], lookback, cap))
    # Precommit one parameter pair using TRAIN observations only.
    winner = max(trained)
    chosen_lookback, chosen_cap = winner[-2:]
    evaluations = {}
    for cost in COST_SCENARIOS_BPS:
        path = backtest(data, lookback=chosen_lookback, cap=chosen_cap, cost_bps=cost)
        evaluations[str(cost)] = {
            "train": metrics(path, 0, split - 1),
            "untouched_holdout": metrics(path, split - 1, len(data) - 1),
        }
    return {
        "schema": "FUND100_BOND_ETF_RESEARCH_V1",
        "phase": "PHASE_2_RESEARCH_ONLY",
        "asset_universe": list(UNIVERSE),
        "control": "SHY adjusted-close buy-and-hold",
        "hypothesis": "Lagged absolute and SHY-relative price trend, "
                      "long-duration concentration cap, defensive SHY remainder.",
        "no_yield_curve_or_credit_spread_input": True,
        "data_source_note": "External adjusted-close prices may have revisions and "
                            "are not fully point-in-time macro/fundamental data.",
        "data_sha256": source_hash(data),
        "first_session": data.index[0].date().isoformat(),
        "last_session": data.index[-1].date().isoformat(),
        "train_last_session": data.index[split - 1].date().isoformat(),
        "holdout_first_session": data.index[split].date().isoformat(),
        "session_count": len(data),
        "chosen_on_training_only": {
            "momentum_lookback_sessions": chosen_lookback,
            "max_selected_satellite_weight": chosen_cap,
        },
        "cost_scenarios_bps_per_side": list(COST_SCENARIOS_BPS),
        "evaluation": evaluations,
        "strategy_promoted_to_live": False,
        "strategy_promoted_to_paper": False,
        "live_orders_authorized": False,
        "requires_independent_forward_paper": True,
        "research_decision": "UNPROMOTED_RESEARCH_ONLY",
        "limitations": [
            "Adjusted historical close can be revised by vendor",
            "No true duration/yield-curve or inflation surprise data yet",
            "SHY may lose value; it is not equivalent to cash",
            "No live spreads, borrow, liquidity or bid/ask execution evidence",
            "Backtest and holdout alone do not demonstrate forward edge",
        ],
    }


def main() -> None:
    """Research entrypoint for a distinct local bond-price CSV, not LIVE state."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.prices_csv, index_col="Date", parse_dates=["Date"])
    report = analyze(prices)
    Path(args.output_json).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Fund-100 Phase 2 BOND ETF research: completed, no orders.")
    print("Source SHA256:", report["data_sha256"])
    print("Training selected:", report["chosen_on_training_only"])
    for cost, result in report["evaluation"].items():
        holdout = result["untouched_holdout"]
        print("Holdout at", cost, "bps/side, excess vs SHY:",
              holdout["net_excess_vs_shy"])
    print("Broker or LIVE trading permissions: NONE")


if __name__ == "__main__":
    main()

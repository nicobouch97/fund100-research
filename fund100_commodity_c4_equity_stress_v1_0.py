"""C4: a PREDECLARED equity-stress-diversification commodity ETF overlay.

RESEARCH ONLY. C4 is neither a futures-curve/carry model nor a DBC index
replica. It responds to observed 63-session co-movement of GLD/DBC with
SPY when SPY realized volatility is elevated, rather than using the
failed C1 trend and C2 unverified macro-lag decisions.

Portfolio remains long-only GLD<=20%, DBC<=15%, SHY>=65% at monthly
rebalance targets. SPY is diagnostic signal input only, NEVER traded.
No broker, orders, fund risk/kill-switch modifications, PAPER/LIVE
permissions, or self-promotion based on retrospective evidence.

Existing post-2020 histories are ALREADY examined: treat all resulting
historical comparisons as exploratory, never a new holdout. A future
independent forward scorecard needs an append-only start.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_commodity_etp_research_v1_0 as base

SCHEMA = "FUND100_PHASE3_C4_COMMODITY_EQUITY_STRESS_OVERLAY_V1"
WINDOW = 63
SPY_STRESS_ANNUAL_VOL = 0.25
DBC_EQUITY_CORRELATION_TRIGGER = 0.40
GLD_EQUITY_CORRELATION_TRIGGER = 0.30
DBC_STRESS_TARGET = 0.05
GLD_STRESS_TARGET = 0.10
COSTS_BPS = (5, 15, 35)
MODEL_MAX_GLD = base.GLD_CAP
MODEL_MAX_DBC = base.DBC_CAP


class CommodityC4Stop(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    weights: dict[str, float]
    spy_annualized_vol: float | None
    dbc_spy_corr: float | None
    gold_spy_corr: float | None
    dbc_stress_reduced: bool
    gold_stress_reduced: bool


def decision(prices: pd.DataFrame, t: int) -> Decision:
    """Target at close t, computed using bars through close t-1 ONLY."""
    data = base.validate_prices(prices)
    if type(t) is not int or not 0 <= t < len(data):
        raise CommodityC4Stop("Invalid C4 date boundary.")
    target = {"GLD": MODEL_MAX_GLD, "DBC": MODEL_MAX_DBC,
              "SHY": 1.-MODEL_MAX_GLD-MODEL_MAX_DBC}
    if t < WINDOW + 2:
        return Decision(target, None, None, None, False, False)
    # 63 consecutive close-to-close returns, ending at t-1.
    daily = data.loc[:, ["SPY", "DBC", "GLD"]].iloc[t-WINDOW-1:t].pct_change().iloc[1:]
    if len(daily) != WINDOW or not np.isfinite(daily.to_numpy(dtype=float)).all():
        raise CommodityC4Stop("Insufficient clean pre-decision return window.")
    annual = float(daily["SPY"].std(ddof=1) * sqrt(252))
    # Constant series has no defined correlation; treat as NO credible
    # evidence of correlated equity stress, do not force an exposure cut.
    def corr(s: str) -> float | None:
        if float(daily[s].std(ddof=1)) <= 1e-12 or float(daily["SPY"].std(ddof=1)) <= 1e-12:
            return None
        val = float(daily[s].corr(daily["SPY"]))
        return val if np.isfinite(val) else None
    dbc = corr("DBC")
    gld = corr("GLD")
    stress = annual >= SPY_STRESS_ANNUAL_VOL
    cut_dbc = stress and dbc is not None and dbc >= DBC_EQUITY_CORRELATION_TRIGGER
    cut_gld = stress and gld is not None and gld >= GLD_EQUITY_CORRELATION_TRIGGER
    if cut_dbc:
        target["DBC"] = DBC_STRESS_TARGET
    if cut_gld:
        target["GLD"] = GLD_STRESS_TARGET
    target["SHY"] = round(1.-target["GLD"]-target["DBC"], 12)
    if (target["GLD"] < 0 or target["GLD"] > MODEL_MAX_GLD or
        target["DBC"] < 0 or target["DBC"] > MODEL_MAX_DBC or
        target["SHY"] < 1.-MODEL_MAX_GLD-MODEL_MAX_DBC-1e-12):
        raise CommodityC4Stop("C4 target allocation constraint violation.")
    return Decision(target, annual, dbc, gld, cut_dbc, cut_gld)


def backtest(prices: pd.DataFrame, *, cost_bps: int) -> tuple[base.PathResult, dict]:
    data = base.validate_prices(prices)
    if cost_bps not in COSTS_BPS:
        raise CommodityC4Stop("Unsupported trading cost.")
    # Identical convention to static and C1: starts in SHY, rebalance
    # at first close of each new month, pay both legs at cost per side.
    held = {"GLD": 0., "DBC": 0., "SHY": 1.}
    nav = shy = spy = 100.
    returns = data.pct_change().fillna(0.)
    paths, shys, spys, turn, weights = [], [], [], [], []
    months = None
    reductions = {"dbc": 0, "gold": 0, "both": 0, "rebalance_count": 0}
    for t, (day, daily) in enumerate(returns.iterrows()):
        gain = sum(held[s]*float(daily[s]) for s in base.TRADED)
        if gain <= -1:
            raise CommodityC4Stop("Research wealth depleted.")
        nav *= 1+gain
        shy *= 1+float(daily["SHY"])
        spy *= 1+float(daily["SPY"])
        held = {s: held[s]*(1+float(daily[s]))/(1+gain) for s in base.TRADED}
        turnover = 0.
        current_month = (day.year, day.month)
        if t > 0 and current_month != months:
            signal = decision(data, t)
            nextw = signal.weights
            turnover = sum(abs(nextw[s]-held[s]) for s in base.TRADED)
            nav *= 1-turnover*cost_bps/10000.
            held = nextw
            reductions["rebalance_count"] += 1
            reductions["dbc"] += int(signal.dbc_stress_reduced)
            reductions["gold"] += int(signal.gold_stress_reduced)
            reductions["both"] += int(signal.dbc_stress_reduced and signal.gold_stress_reduced)
        months = current_month
        if min(nav, shy, spy) <= 0:
            raise CommodityC4Stop("Nonpositive hypothetical wealth.")
        paths.append(nav); shys.append(shy); spys.append(spy)
        turn.append(turnover); weights.append(held.copy())
    return base.PathResult(
        nav=pd.Series(paths, index=data.index, dtype=float),
        shy_nav=pd.Series(shys, index=data.index, dtype=float),
        static_gld_dbc_nav=None,
        spy_nav=pd.Series(spys, index=data.index, dtype=float),
        turnover=pd.Series(turn, index=data.index, dtype=float),
        close_weights=pd.DataFrame(weights, index=data.index, columns=base.TRADED),
    ), reductions


def analyze(prices: pd.DataFrame) -> dict:
    data = base.validate_prices(prices)
    split = int(len(data)*base.SPLIT_FRACTION)
    if split < 365 or len(data)-split < 126:
        raise CommodityC4Stop("Insufficient sample for explanatory analysis.")
    result = {
        "schema": SCHEMA,
        "status": "EXPLORATORY_HISTORY_ALREADY_EXAMINED_NO_PROMOTION",
        "hypothesis": "63-session lagged ETF equity correlation and SPY volatility interaction",
        "spy_stress_annualized_vol_threshold": SPY_STRESS_ANNUAL_VOL,
        "dbc_spy_correlation_threshold": DBC_EQUITY_CORRELATION_TRIGGER,
        "gold_spy_correlation_threshold": GLD_EQUITY_CORRELATION_TRIGGER,
        "stress_target_gl_dbc_shy": {
            "DBC_only": {"GLD": .20, "DBC": .05, "SHY": .75},
            "GLD_only": {"GLD": .10, "DBC": .15, "SHY": .75},
            "both": {"GLD": .10, "DBC": .05, "SHY": .85},
        },
        "long_only_no_leverage": True,
        "max_gl_dbc_target": .35,
        "fund_dbc_roll_already_embedded_in_adjusted_etf_close": True,
        "no_real_futures_carry_signal_computed": True,
        "all_later_historical_periods_already_explored_in_C1_C2": True,
        "retrospective_holdout_is_not_independent_validation": True,
        "prospective_evidence_required": True,
        "vendor_adjustments_are_not_point_in_time_proven": True,
        "source_sha256": base.data_hash(data),
        "n_sessions": len(data),
        "first_session": data.index[0].date().isoformat(),
        "last_session": data.index[-1].date().isoformat(),
        "descriptive_late_period_starts": data.index[split-1].date().isoformat(),
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_order_count": 0,
        "cost_results": {},
    }
    for c in COSTS_BPS:
        candidate, counts = backtest(data, cost_bps=c)
        reference = base.backtest(data, cost_bps=c, mode="static")
        cm = base.metrics(candidate, split-1, len(data)-1)
        sm = base.metrics(reference, split-1, len(data)-1)
        result["cost_results"][str(c)] = {
            "c4_exploratory_late_period": cm,
            "static_exploratory_late_period": sm,
            "c4_less_static_net_cumulative_return_percentage_points": round(
                cm["net_total_return_pct"]-sm["net_total_return_pct"], 5
            ),
            "c4_less_static_max_drawdown_percentage_points": round(
                cm["max_drawdown_pct"]-sm["max_drawdown_pct"], 5
            ),
            "entire_history_monthly_target_stress_count": counts,
        }
    return result


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--prices-csv", required=True)
    p.add_argument("--output-json", required=True)
    args = p.parse_args()
    prices = pd.read_csv(args.prices_csv, index_col="Date", parse_dates=["Date"])
    result = analyze(prices)
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print("C4 exploratory equity-stress commodity study, NO BROKER")
    print("Research only, retrospective segment has been previously inspected.")
    print("Price SHA256:", result["source_sha256"])
    for cost, d in result["cost_results"].items():
        print("Cost", cost, "bps each traded side:",
              "C4 minus capped static NET cumulative return (pp)",
              d["c4_less_static_net_cumulative_return_percentage_points"])
    print("Cannot self-promote to PAPER or LIVE. Broker order count: 0.")


if __name__ == "__main__":
    main()

"""Phase 3 commodities: GLD physical-gold vs DBC futures-linked ETP research.

Completely isolated from broker execution, candidate issuance, PAPER and LIVE.
Fixed lagged absolute/SHY-relative trend and realized-volatility caps; no
parameter fit to a later holdout. SHY is a risky short-Treasury ETF proxy,
not cash; SPY is a non-tradable diagnostic for equity stress/correlation.

DBC adjusted ETP prices ALREADY include historical roll/tracking/fee impacts
at the fund level: do NOT add a fabricated second roll-cost deduction.
Trading cost scenarios represent additional buy/sell slippage/commissions,
not expense ratio, fund roll yield, tax or market impact.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

PRICES = ("GLD", "DBC", "SHY", "SPY")
TRADED = ("GLD", "DBC", "SHY")
COSTS_BPS = (5, 15, 35)
LOOKBACK = 126
VOL_WINDOW = 63
GLD_CAP = 0.20
DBC_CAP = 0.15
MAX_COMMODITY_EXPOSURE = GLD_CAP + DBC_CAP
GLD_VOL_HALVE_ABOVE = 0.30
DBC_VOL_HALVE_ABOVE = 0.35
MIN_SESSIONS = 840
SPLIT_FRACTION = 0.70


class CommodityResearchStop(ValueError):
    pass


def validate_prices(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(PRICES):
        raise CommodityResearchStop("Expected exactly GLD, DBC, SHY and SPY closes.")
    if (
        not isinstance(raw.index, pd.DatetimeIndex)
        or raw.index.tz is not None
        or not raw.index.is_monotonic_increasing
        or raw.index.has_duplicates
        or any(ts != ts.normalize() for ts in raw.index)
        or len(raw) < MIN_SESSIONS
    ):
        raise CommodityResearchStop("Missing, unordered or invalid dated price history.")
    if any(not pd.api.types.is_numeric_dtype(raw[c]) for c in PRICES):
        raise CommodityResearchStop("Commodity reference price is not numeric.")
    values = raw.loc[:, list(PRICES)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise CommodityResearchStop("Missing, nonfinite or nonpositive adjusted prices.")
    if (np.abs(raw.pct_change().iloc[1:].to_numpy(dtype=float)) > 0.45).any():
        raise CommodityResearchStop("Suspicious daily ETP price discontinuity.")
    return raw.loc[:, list(PRICES)].copy()


def data_hash(prices: pd.DataFrame) -> str:
    canonical = validate_prices(prices).to_csv(
        index=True, date_format="%Y-%m-%d", float_format="%.10f",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reference_weights(prices: pd.DataFrame, t: int,
                      mode: str = "trend") -> dict[str, float]:
    """Close-t order reference based ONLY on market bars through t-1.

    A research reference allocation is not a trading signal or broker intent.
    """
    if mode not in {"trend", "static"} or type(t) is not int or not 0 <= t < len(prices):
        raise CommodityResearchStop("Invalid reference mode or session.")
    if mode == "static":
        return {"GLD": GLD_CAP, "DBC": DBC_CAP,
                "SHY": 1.0 - MAX_COMMODITY_EXPOSURE}
    weights = {"GLD": 0.0, "DBC": 0.0, "SHY": 1.0}
    if t <= max(LOOKBACK, VOL_WINDOW + 1):
        return weights
    # Strictly previous close (t-1), with lookback as of (t-1-126).
    trailing = prices.iloc[t - 1] / prices.iloc[t - 1 - LOOKBACK] - 1.0
    historical_returns = prices.iloc[t - VOL_WINDOW - 1:t].pct_change().dropna()
    realized_vol = historical_returns.std(ddof=1)*sqrt(252)
    shy_trend = float(trailing["SHY"])
    for symbol, cap, vol_limit in (
        ("GLD", GLD_CAP, GLD_VOL_HALVE_ABOVE),
        ("DBC", DBC_CAP, DBC_VOL_HALVE_ABOVE),
    ):
        if float(trailing[symbol]) > max(0.0, shy_trend):
            weights[symbol] = cap * (0.5 if float(realized_vol[symbol]) > vol_limit else 1.0)
    weights["SHY"] = 1.0 - weights["GLD"] - weights["DBC"]
    assert weights["SHY"] >= 1.0 - MAX_COMMODITY_EXPOSURE
    return weights


@dataclass
class PathResult:
    nav: pd.Series
    shy_nav: pd.Series
    static_gld_dbc_nav: pd.Series | None
    spy_nav: pd.Series
    turnover: pd.Series
    close_weights: pd.DataFrame


def backtest(prices: pd.DataFrame, *, cost_bps: int,
             mode: str = "trend") -> PathResult:
    data = validate_prices(prices)
    if cost_bps not in COSTS_BPS or mode not in {"trend", "static"}:
        raise CommodityResearchStop("Invalid cost or backtest variant.")
    position = {"GLD": 0.0, "DBC": 0.0, "SHY": 1.0}
    nav = shy = spy = 100.0
    path, shy_path, spy_path, turnovers, targets = [], [], [], [], []
    returns = data.pct_change().fillna(0.0)
    prev_month = None
    for t, (day, r) in enumerate(returns.iterrows()):
        # Exposure held entering t receives t close-to-close total return.
        gross = sum(position[s]*float(r[s]) for s in TRADED)
        if gross <= -1:
            raise CommodityResearchStop("Invalid daily return / depleted reference NAV.")
        nav *= 1 + gross
        shy *= 1 + float(r["SHY"])
        spy *= 1 + float(r["SPY"])
        position = {
            s: position[s]*(1 + float(r[s]))/(1 + gross) for s in TRADED
        }
        turnover = 0.0
        month = (day.year, day.month)
        if t > 0 and month != prev_month:
            target = reference_weights(data, t, mode=mode)
            turnover = sum(abs(target[s] - position[s]) for s in TRADED)
            nav *= 1.0 - turnover*cost_bps/10000.0
            position = target
        prev_month = month
        if min(nav, shy, spy) <= 0:
            raise CommodityResearchStop("Nonpositive research NAV.")
        path.append(nav)
        shy_path.append(shy)
        spy_path.append(spy)
        turnovers.append(turnover)
        targets.append(position.copy())
    idx = data.index
    return PathResult(
        nav=pd.Series(path, index=idx, dtype=float),
        shy_nav=pd.Series(shy_path, index=idx, dtype=float),
        static_gld_dbc_nav=None,
        spy_nav=pd.Series(spy_path, index=idx, dtype=float),
        turnover=pd.Series(turnovers, index=idx, dtype=float),
        close_weights=pd.DataFrame(targets, index=idx, columns=TRADED),
    )


def metrics(result: PathResult, start: int, end: int) -> dict:
    if type(start) is not int or type(end) is not int or not 0 <= start < end < len(result.nav):
        raise CommodityResearchStop("Invalid research evaluation window.")
    nav = result.nav.iloc[start:end+1]
    shy = result.shy_nav.iloc[start:end+1]
    spy = result.spy_nav.iloc[start:end+1]
    sessions = end - start
    daily = nav.pct_change().dropna()
    equity = spy.pct_change().dropna()
    downside = equity <= -0.02
    # Observed daily return on equity-down days, descriptive not prediction.
    stress_avg = float(daily.loc[downside].mean()) if downside.any() else None
    corr = float(daily.corr(equity)) if daily.std() > 0 and equity.std() > 0 else None
    dd = float((1 - nav/nav.cummax()).max())
    ratio = float(nav.iloc[-1]/nav.iloc[0])
    shy_ratio = float(shy.iloc[-1]/shy.iloc[0])
    return {
        "sessions": sessions,
        "net_total_return_pct": round(100*(ratio-1), 5),
        "shy_total_return_pct": round(100*(shy_ratio-1), 5),
        "net_excess_vs_shy_percentage_points": round(100*(ratio-shy_ratio), 5),
        "annualized_volatility": round(float(daily.std(ddof=1)*sqrt(252)), 6),
        "max_drawdown_pct": round(100*dd, 5),
        "total_one_way_turnover": round(float(result.turnover.iloc[start+1:end+1].sum()), 5),
        "equity_daily_correlation": None if corr is None else round(corr, 5),
        "spy_equity_down_2pct_day_count": int(downside.sum()),
        "strategy_avg_return_on_spy_down_2pct_days_pct":
            None if stress_avg is None else round(100*stress_avg, 5),
    }


def analyze(prices: pd.DataFrame) -> dict:
    """ONE fixed challenger vs defensible references, no parameter tuning."""
    data = validate_prices(prices)
    split = int(len(data)*SPLIT_FRACTION)
    if not 365 < split < len(data) - 126:
        raise CommodityResearchStop("Insufficient train and chronological evaluation.")
    report = {
        "schema": "FUND100_PHASE3_COMMODITY_RESEARCH_V1",
        "scope": "RESEARCH_ONLY_NO_BROKER",
        "universe": {"physical_gold_trust": "GLD",
                     "futures_commodity_ETP": "DBC",
                     "defensive_non_cash_ETF": "SHY",
                     "equity_stress_diagnostic_only": "SPY"},
        "fixed_hypothesis": "Lagged six-month absolute and SHY-relative trends, "
                            "conservative instrument-specific volatility caps.",
        "lookback_sessions": LOOKBACK,
        "volatility_window_sessions": VOL_WINDOW,
        "commodity_target_max": MAX_COMMODITY_EXPOSURE,
        "GLD_target_max": GLD_CAP,
        "DBC_target_max": DBC_CAP,
        "one_way_cost_scenarios_bps": list(COSTS_BPS),
        "fund_expenses_and_DBC_roll_already_reflected_in_price_history": True,
        "no_added_futures_roll_penalty_to_avoid_double_counting": True,
        "does_not_prove_point_in_time_vendor_prices": True,
        "fixed_before_holdout_no_parameter_selection": True,
        "strategy_promoted_to_live": False,
        "strategy_promoted_to_paper": False,
        "broker_order_count": 0,
        "universe_extended_for_live": False,
        "data_sha256": data_hash(data),
        "first_session": data.index[0].date().isoformat(),
        "last_session": data.index[-1].date().isoformat(),
        "train_end": data.index[split-1].date().isoformat(),
        "holdout_start": data.index[split].date().isoformat(),
        "sessions": len(data),
        "results": {},
    }
    for cost in COSTS_BPS:
        trend = backtest(data, cost_bps=cost, mode="trend")
        fixed = backtest(data, cost_bps=cost, mode="static")
        report["results"][str(cost)] = {
            "fixed_trend_training": metrics(trend, 0, split-1),
            "fixed_trend_holdout": metrics(trend, split-1, len(data)-1),
            "capped_static_GLD_DBC_holdout": metrics(fixed, split-1, len(data)-1),
        }
    return report


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.prices_csv, index_col="Date", parse_dates=["Date"])
    report = analyze(prices)
    Path(args.output_json).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print("Phase 3 commodity study: fixed model, no broker.")
    print("Dataset SHA256:", report["data_sha256"])
    print("Holdout begins:", report["holdout_start"])
    for cost, values in report["results"].items():
        trend = values["fixed_trend_holdout"]
        fixed = values["capped_static_GLD_DBC_holdout"]
        print("Cost", cost, "bps / side, trend excess vs SHY (pp):",
              trend["net_excess_vs_shy_percentage_points"],
              "capped static mix excess (pp):",
              fixed["net_excess_vs_shy_percentage_points"],
              "equity daily correlation:", trend["equity_daily_correlation"])
    print("Research-only; no PAPER/LIVE orders or approvals.")


if __name__ == "__main__":
    main()

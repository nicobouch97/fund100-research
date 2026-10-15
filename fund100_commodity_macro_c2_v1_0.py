"""Fund-100 Phase 3: hypothesis C2, inflation/real-yield commodity regimes.

RESEARCH ONLY. No Alpaca, permits, orders, API credentials or LIVE whitelists.

Unlike initial GLD/DBC trend-only challenger, keep a modest permanent physical
gold reference weight, increase gold in falling-real-yield or rising-credit-
stress regimes, and condition DBC futures-fund exposure on rising breakevens
and positive price trend. This is NOT an observed futures carry/term-structure
signal. No parameters are optimised or selected using historical results.

Assumed FRED availability = observation plus 2 weekdays, NOT proof of public
release or vintage; retrospectively downloaded historical values may revise.
Only prior trading-session information informs monthly-close allocations.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

import fund100_commodity_etp_research_v1_0 as base

MACRO_COLUMNS = ("DFII10", "T10YIE", "BAA10Y")
GLD_PERMANENT = 0.10
GLD_REGIME_TARGET = 0.20
DBC_REGIME_TARGET = 0.15
MAX_COMMODITIES = 0.35
REAL_YIELD_FALL_TRIGGER_PP = -0.15
CREDIT_STRESS_RISE_TRIGGER_PP = 0.25
CREDIT_DBC_PAUSE_TRIGGER_PP = 0.30
BREAKEVEN_RISE_TRIGGER_PP = 0.10
MACRO_WINDOW_SESSIONS = 21
DBC_TREND_LOOKBACK = 63
MAX_MACRO_STALENESS_CALENDAR_DAYS = 10
COSTS_BPS = (5, 15, 35)
AVAILABILITY_CLAIM = "ASSUMED_TWO_WEEKDAYS_NOT_VERIFIED_POINT_IN_TIME"


class CommodityRegimeStop(ValueError):
    pass


def validate_macro(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != {
        "observation_date", "available_date", *MACRO_COLUMNS
    } or len(raw) < 200:
        raise CommodityRegimeStop("Expected date-stamped real-yield, inflation and credit macro data.")
    table = raw.copy()
    for name in ("observation_date", "available_date"):
        col = table[name]
        if not pd.api.types.is_datetime64_any_dtype(col):
            raise CommodityRegimeStop("Macro dates must be datetime values.")
        if col.dt.tz is not None or (col != col.dt.normalize()).any():
            raise CommodityRegimeStop("Macro dates must be timezone-free calendar days.")
    if table["observation_date"].duplicated().any():
        raise CommodityRegimeStop("Conflicting macro observations.")
    if not table["observation_date"].is_monotonic_increasing or not table["available_date"].is_monotonic_increasing:
        raise CommodityRegimeStop("Macro series not chronologically sorted.")
    if (table["available_date"] < table["observation_date"]).any():
        raise CommodityRegimeStop("Macro observations allegedly released before collected.")
    for s in MACRO_COLUMNS:
        if not pd.api.types.is_numeric_dtype(table[s]):
            raise CommodityRegimeStop("Non-numeric macro values.")
    vals = table[list(MACRO_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(vals).all():
        raise CommodityRegimeStop("Macro gaps not permitted.")
    if (np.abs(vals[:, 0]) > 25).any() or (np.abs(vals[:, 1]) > 25).any():
        raise CommodityRegimeStop("Implausible real yields or breakeven.")
    if (vals[:, 2] < 0).any() or (vals[:, 2] > 25).any():
        raise CommodityRegimeStop("Invalid Baa corporate credit spread.")
    return table


def asof_available(prices: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    prices = base.validate_prices(prices)
    macro = validate_macro(macro)
    left = pd.DataFrame({
        "session": prices.index[1:],
        "known_by": prices.index[:-1],
    })
    right = macro.rename(columns={"available_date": "known_by"}).sort_values(
        ["known_by", "observation_date"]
    )
    # Keep original claimed available_date separately to audit lag.
    right = right.assign(available_date=right["known_by"])
    joined = pd.merge_asof(
        left, right, on="known_by", direction="backward",
        allow_exact_matches=True,
    ).set_index("session").reindex(prices.index)
    return joined


def reference_weights(prices: pd.DataFrame, known: pd.DataFrame, t: int) -> dict[str, float]:
    """Fixed, no-permission reference target for trading session t close."""
    if type(t) is not int or not 0 <= t < len(prices) or len(prices) != len(known):
        raise CommodityRegimeStop("Invalid strategy observation boundary.")
    weights = {"GLD": GLD_PERMANENT, "DBC": 0.0, "SHY": 1.0 - GLD_PERMANENT}
    if t <= max(MACRO_WINDOW_SESSIONS, DBC_TREND_LOOKBACK):
        return weights
    now = known.iloc[t]
    old = known.iloc[t - MACRO_WINDOW_SESSIONS]
    for row, session in (
        (now, known.index[t]),
        (old, known.index[t - MACRO_WINDOW_SESSIONS]),
    ):
        if pd.isna(row["observation_date"]) or pd.isna(row["available_date"]):
            return weights
        if row["available_date"] > session:
            raise CommodityRegimeStop("Macro observation not yet public at signal.")
        age = (session - row["observation_date"]).days
        if age < 0:
            raise CommodityRegimeStop("Unobserved future macro observation.")
        if age > MAX_MACRO_STALENESS_CALENDAR_DAYS:
            return weights
    real_yield_change = float(now["DFII10"] - old["DFII10"])
    credit_change = float(now["BAA10Y"] - old["BAA10Y"])
    breakeven_change = float(now["T10YIE"] - old["T10YIE"])
    credit_stress = credit_change >= CREDIT_STRESS_RISE_TRIGGER_PP
    if real_yield_change <= REAL_YIELD_FALL_TRIGGER_PP or credit_stress:
        weights["GLD"] = GLD_REGIME_TARGET
    # DBC is futures-linked. Breakeven trend is NOT futures roll yield/carry.
    t0 = t-1-DBC_TREND_LOOKBACK
    dbc_return = float(prices["DBC"].iloc[t-1] / prices["DBC"].iloc[t0] - 1)
    shy_return = float(prices["SHY"].iloc[t-1] / prices["SHY"].iloc[t0] - 1)
    if (
        breakeven_change >= BREAKEVEN_RISE_TRIGGER_PP
        and credit_change < CREDIT_DBC_PAUSE_TRIGGER_PP
        and dbc_return > max(0.0, shy_return)
    ):
        weights["DBC"] = DBC_REGIME_TARGET
    weights["SHY"] = 1 - weights["GLD"] - weights["DBC"]
    if weights["GLD"] > GLD_REGIME_TARGET or weights["DBC"] > DBC_REGIME_TARGET or weights["SHY"] < 1-MAX_COMMODITIES-1e-12:
        raise CommodityRegimeStop("Internal fixed allocation cap violation.")
    return weights


@dataclass(frozen=True)
class BacktestResult:
    nav: pd.Series
    shy: pd.Series
    spy: pd.Series
    turnover: pd.Series
    close_weights: pd.DataFrame


def backtest(prices: pd.DataFrame, macro: pd.DataFrame, cost_bps: int) -> BacktestResult:
    data = base.validate_prices(prices)
    if cost_bps not in COSTS_BPS:
        raise CommodityRegimeStop("Unsupported model cost.")
    joined = asof_available(data, macro)
    # Before first reference rebalance hold SHY, same initial convention as C1.
    holdings = {"GLD": 0., "DBC": 0., "SHY": 1.}
    nav = shy = spy = 100.
    paths, shys, spys, turnovers, weights = [], [], [], [], []
    months = None
    for i, (date, r) in enumerate(data.pct_change().fillna(0).iterrows()):
        gross = sum(holdings[s]*float(r[s]) for s in base.TRADED)
        if gross <= -1:
            raise CommodityRegimeStop("Non-positive hypothetical portfolio return.")
        nav *= 1 + gross
        shy *= 1 + float(r["SHY"])
        spy *= 1 + float(r["SPY"])
        holdings = {s: holdings[s]*(1+float(r[s]))/(1+gross) for s in base.TRADED}
        current_month = (date.year, date.month)
        turnover = 0.
        if i > 0 and current_month != months:
            new = reference_weights(data, joined, i)
            turnover = sum(abs(new[s] - holdings[s]) for s in base.TRADED)
            nav *= 1.0 - turnover*cost_bps/10000.
            holdings = new
        months = current_month
        if min(nav, shy, spy) <= 0:
            raise CommodityRegimeStop("Hypothetical NAV cannot be nonpositive.")
        paths.append(nav)
        shys.append(shy)
        spys.append(spy)
        turnovers.append(turnover)
        weights.append(holdings.copy())
    idx = data.index
    return BacktestResult(
        nav=pd.Series(paths, index=idx),
        shy=pd.Series(shys, index=idx),
        spy=pd.Series(spys, index=idx),
        turnover=pd.Series(turnovers, index=idx),
        close_weights=pd.DataFrame(weights, index=idx, columns=base.TRADED),
    )


def _metrics(nav: pd.Series, shy: pd.Series, spy: pd.Series,
             turnover: pd.Series, split: int) -> dict:
    part = nav.iloc[split-1:]
    control = shy.iloc[split-1:]
    benchmark = spy.iloc[split-1:]
    returns = part.pct_change().dropna()
    equities = benchmark.pct_change().dropna()
    down = equities <= -0.02
    corr = float(returns.corr(equities)) if returns.std() > 0 and equities.std() > 0 else None
    result = {
        "cumulative_excess_vs_shy_percentage_points":
            round(100*(part.iloc[-1]/part.iloc[0]-control.iloc[-1]/control.iloc[0]), 5),
        "cumulative_net_return_pct":
            round(100*(part.iloc[-1]/part.iloc[0]-1), 5),
        "max_drawdown_pct": round(float((1-part/part.cummax()).max())*100, 5),
        "annualized_vol": round(float(returns.std(ddof=1)*sqrt(252)), 6),
        "turnover_one_way_sum": round(float(turnover.iloc[split:].sum()), 5),
        "correlation_daily_spy": round(corr, 5) if corr is not None else None,
        "spy_down_2pct_days": int(down.sum()),
        "mean_strategy_return_on_spy_down_2pct_days_pct":
            round(100*float(returns.loc[down].mean()), 5) if down.any() else None,
    }
    return result


def macro_hash(raw: pd.DataFrame) -> str:
    data = validate_macro(raw)
    canonical = data.to_csv(index=False, float_format="%.10f", date_format="%Y-%m-%d")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def analyze(prices: pd.DataFrame, macro: pd.DataFrame) -> dict:
    data = base.validate_prices(prices)
    series = validate_macro(macro)
    split = int(len(data)*.70)
    report = {
        "schema": "FUND100_PHASE3_COMMODITY_C2_MACRO_V1",
        "hypothesis": "Permanent physical gold with real-yield/credit stress gold overlay; "
                      "breakeven-plus-price regime for futures-linked DBC",
        "status": "EXPLORATORY_HISTORICAL_ONLY_NO_PROMOTION",
        "already_inspected_historical_late_segment": True,
        "holdout_is_independent": False,
        "benchmark_selection_from_inspected_data": False,
        "future_prospective_validation_required": True,
        "macro_availability_policy": AVAILABILITY_CLAIM,
        "historical_vintage_authentication_established": False,
        "futures_term_structure_or_carry_observed": False,
        "live_authorized": False,
        "paper_authorized": False,
        "broker_orders": 0,
        "prices_sha256": base.data_hash(data),
        "macro_sha256": macro_hash(series),
        "days": len(data),
        "last_date": data.index[-1].date().isoformat(),
        "late_segment_start": data.index[split].date().isoformat(),
        "rules": {
            "gold_base": GLD_PERMANENT,
            "gold_regime_target": GLD_REGIME_TARGET,
            "dbc_regime_target": DBC_REGIME_TARGET,
            "real_yield_falling_pp": REAL_YIELD_FALL_TRIGGER_PP,
            "credit_stress_pp": CREDIT_STRESS_RISE_TRIGGER_PP,
            "credit_pause_dbc_pp": CREDIT_DBC_PAUSE_TRIGGER_PP,
            "breakeven_rising_pp": BREAKEVEN_RISE_TRIGGER_PP,
            "macro_change_sessions": MACRO_WINDOW_SESSIONS,
            "dbc_trend_sessions": DBC_TREND_LOOKBACK,
        },
        "costs_bps_per_side": list(COSTS_BPS),
        "results": {},
    }
    for cost in COSTS_BPS:
        c2 = backtest(data, series, cost_bps=cost)
        c1 = base.backtest(data, cost_bps=cost, mode="trend")
        static = base.backtest(data, cost_bps=cost, mode="static")
        report["results"][str(cost)] = {
            "C2_regime": _metrics(c2.nav, c2.shy, c2.spy, c2.turnover, split),
            "C1_prior_trend": base.metrics(c1, split-1, len(data)-1),
            "static_GLD_DBC_reference": base.metrics(static, split-1, len(data)-1),
        }
    return report


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--macro-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.price_csv, parse_dates=["Date"], index_col="Date")
    macro = pd.read_csv(args.macro_csv, parse_dates=["observation_date", "available_date"])
    result = analyze(prices, macro)
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print("Fund-100 C2 commodity real-yield / inflation regimes: retrospective ONLY.")
    print("Source price hash:", result["prices_sha256"])
    print("Source macro hash:", result["macro_sha256"])
    print("Known late-segment independent: NO. Historical vintage verified: NO.")
    for cost, row in result["results"].items():
        print(
            "Cost", cost, "bps per side | C2 vs SHY (pp):",
            row["C2_regime"]["cumulative_excess_vs_shy_percentage_points"],
            "| C1 vs SHY (pp):",
            row["C1_prior_trend"]["net_excess_vs_shy_percentage_points"],
            "| static vs SHY (pp):",
            row["static_GLD_DBC_reference"]["net_excess_vs_shy_percentage_points"],
        )
    print("Trading permissions: NONE; PAPER or LIVE orders: ZERO.")


if __name__ == "__main__":
    main()

"""Phase 2 bond macro-regime RESEARCH only. No broker, no order interface.

Uses separately availability-dated macro observations to decide ETF reference
weights at each month's first session close from information available BEFORE
that session. Publication/vintage claims are ONLY as strong as the input
availability provenance; today's FRED history is retrospectively revised.

Predeclared illustrative (not optimized) rules compare three yield/spread
regimes against SHY and the existing price-only challenger. No historical
holdout is claimed independent after prior inspection. Paper/Live: DENIED.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

import fund100_bond_etf_research_v1_0 as bond

SERIES = ("DGS2", "DGS10", "T10YIE", "BAA10Y")
MAX_STALENESS_CALENDAR_DAYS = 10
REFERENCE_LOOKBACK = 21
COSTS = (5, 15, 35)
EXPECTED_AVAILABILITY_POLICY = "TWO_BUSINESS_DAYS_ASSUMED_NOT_VERIFIED"
RULES = {
    "duration_falling_10y_min_pctpoints": -0.15,
    "credit_no_shock_max_pctpoints": 0.30,
    "spread_tightening_min_pctpoints": -0.20,
    "spread_level_max_pctpoints": 3.50,
    "breakeven_rising_min_pctpoints": 0.10,
    "yield_rising_min_pctpoints": 0.10,
}


class MacroResearchStop(ValueError):
    pass


def validate_macro(macro: pd.DataFrame) -> pd.DataFrame:
    """One record per macro observation date; availability dates are explicit.

    Even a compliant dataset is NOT proven point-in-time until real historical
    vintages and genuine release timestamps are independently verified.
    """
    expected = {"observation_date", "available_date", *SERIES}
    if not isinstance(macro, pd.DataFrame) or set(macro.columns) != expected:
        raise MacroResearchStop("Macro input columns/series mismatch.")
    rows = macro.copy()
    if len(rows) < 200:
        raise MacroResearchStop("Insufficient separate macro observations.")
    for name in ("observation_date", "available_date"):
        if not pd.api.types.is_datetime64_any_dtype(rows[name]):
            raise MacroResearchStop("Macro dates must be parsed calendar dates.")
        if getattr(rows[name].dt, "tz", None) is not None:
            raise MacroResearchStop("Time-zoned macro dates not supported.")
        if (rows[name] != rows[name].dt.normalize()).any():
            raise MacroResearchStop("Macro dates must be date-only.")
    if rows["observation_date"].duplicated().any():
        raise MacroResearchStop("Duplicated observation/vintage not resolved.")
    if not rows["observation_date"].is_monotonic_increasing:
        raise MacroResearchStop("Macro observation dates are not ordered.")
    if (rows["available_date"] < rows["observation_date"]).any():
        raise MacroResearchStop("Macro value available before observation date.")
    if not rows["available_date"].is_monotonic_increasing:
        raise MacroResearchStop("Non-monotone availability chronology.")
    # Values are FRED percentages (e.g., 4.25) NOT decimal fractions.
    for series in SERIES:
        if not pd.api.types.is_numeric_dtype(rows[series]):
            raise MacroResearchStop("Non-numeric macro series.")
    matrix = rows.loc[:, list(SERIES)].to_numpy(dtype=float)
    if not np.isfinite(matrix).all():
        raise MacroResearchStop("Missing macro observation values.")
    if (matrix[:, :3] < -2.0).any() or (matrix[:, :3] > 30.0).any():
        raise MacroResearchStop("Implausible yield or breakeven values.")
    if (matrix[:, 3] < 0).any() or (matrix[:, 3] > 25).any():
        raise MacroResearchStop("Invalid Baa minus Treasury credit spread.")
    return rows


def align_available_macro(price_index: pd.DatetimeIndex,
                          macro: pd.DataFrame) -> pd.DataFrame:
    """As-of join by FIRST permissible availability date, no lookahead.

    Rows strictly after the trading session's *previous* close are never used
    for its current signal. Macro age checked on each signal separately.
    """
    rows = validate_macro(macro)
    if not isinstance(price_index, pd.DatetimeIndex) or price_index.tz is not None:
        raise MacroResearchStop("Bond ETF trading dates are invalid.")
    if len(price_index) < 2 or not price_index.is_monotonic_increasing:
        raise MacroResearchStop("Need ordered bond trading session dates.")
    left = pd.DataFrame({
        "session": price_index[1:],
        "known_by": price_index[:-1],
    })
    right = rows.assign(source_available_date=rows["available_date"])
    right = right.rename(columns={"available_date": "known_by"}).sort_values(
        ["known_by", "observation_date"]
    )
    available = pd.merge_asof(
        left, right, on="known_by", direction="backward",
        allow_exact_matches=True,
    ).set_index("session").reindex(price_index)
    return available.rename(columns={"source_available_date": "available_date"})


def decision(macro_history: pd.DataFrame, index: int) -> dict[str, float]:
    """Deterministic reference allocation; not execution-authorized."""
    weights = dict.fromkeys(bond.UNIVERSE, 0.0)
    weights["SHY"] = 1.0
    if type(index) is not int or index < 0 or index >= len(macro_history):
        raise MacroResearchStop("Out-of-range macro decision.")
    if index < REFERENCE_LOOKBACK:
        return weights
    current = macro_history.iloc[index]
    earlier = macro_history.iloc[index - REFERENCE_LOOKBACK]
    for observation, session in ((current, macro_history.index[index]),
                                 (earlier, macro_history.index[index - REFERENCE_LOOKBACK])):
        day = observation["observation_date"]
        if pd.isna(day):
            return weights
        age = (session - day).days
        if age < 0:
            raise MacroResearchStop("Future macro observation would leak.")
        if age > MAX_STALENESS_CALENDAR_DAYS:
            # No future data, but unreliable source. Refuse to ascribe regime.
            return weights
    y10 = float(current["DGS10"])
    y10_change = y10 - float(earlier["DGS10"])
    credit_change = float(current["BAA10Y"]) - float(earlier["BAA10Y"])
    inflation_change = float(current["T10YIE"]) - float(earlier["T10YIE"])

    if (
        y10_change <= RULES["duration_falling_10y_min_pctpoints"]
        and credit_change <= RULES["credit_no_shock_max_pctpoints"]
    ):
        weights.update({"TLT": 0.15, "IEF": 0.20, "SHY": 0.65})
    elif (
        credit_change <= RULES["spread_tightening_min_pctpoints"]
        and float(current["BAA10Y"]) <= RULES["spread_level_max_pctpoints"]
    ):
        weights.update({"LQD": 0.20, "IEF": 0.15, "SHY": 0.65})
    elif (
        inflation_change >= RULES["breakeven_rising_min_pctpoints"]
        and y10_change >= RULES["yield_rising_min_pctpoints"]
    ):
        weights.update({"TIP": 0.20, "IEF": 0.15, "SHY": 0.65})
    assert all(v >= 0 for v in weights.values())
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    return weights


@dataclass
class MacroBacktest:
    nav: pd.Series
    benchmark: pd.Series
    turnover: pd.Series
    weights: pd.DataFrame


def run(prices: pd.DataFrame, macro: pd.DataFrame, cost_bps: int) -> MacroBacktest:
    prices = bond.validate_prices(prices)
    if cost_bps not in COSTS:
        raise MacroResearchStop("Unsupported cost scenario.")
    aligned = align_available_macro(prices.index, macro)
    returns = prices.pct_change().fillna(0.0)
    position = dict.fromkeys(bond.UNIVERSE, 0.0)
    position["SHY"] = 1.0
    nav, shy = 100.0, 100.0
    paths, benchmarks, turnovers, holdings = [], [], [], []
    prior_month = None
    for i, (day, r) in enumerate(returns.iterrows()):
        daily = sum(position[s]*float(r[s]) for s in bond.UNIVERSE)
        if daily <= -1.0:
            raise MacroResearchStop("Negative or zero NAV.")
        nav *= 1.0 + daily
        shy *= 1.0 + float(r["SHY"])
        position = {
            s: position[s]*(1.0+float(r[s]))/(1.0+daily)
            for s in bond.UNIVERSE
        }
        month = (day.year, day.month)
        turnover = 0.0
        if i > 0 and month != prior_month:
            target = decision(aligned, i)
            turnover = sum(abs(target[s] - position[s]) for s in bond.UNIVERSE)
            nav *= 1.0 - turnover*cost_bps/10000.0
            position = target
        prior_month = month
        paths.append(nav)
        benchmarks.append(shy)
        turnovers.append(turnover)
        holdings.append(position.copy())
    return MacroBacktest(
        nav=pd.Series(paths, index=prices.index),
        benchmark=pd.Series(benchmarks, index=prices.index),
        turnover=pd.Series(turnovers, index=prices.index),
        weights=pd.DataFrame(holdings, index=prices.index, columns=bond.UNIVERSE),
    )


def _hash_macro(macro: pd.DataFrame) -> str:
    clean = validate_macro(macro)
    raw = clean.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.10f")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _metrics(nav: pd.Series, shy: pd.Series, turnover: pd.Series) -> dict:
    n = len(nav)
    if n < 2:
        raise MacroResearchStop("Not enough comparable sessions.")
    relative = float(nav.iloc[-1]/nav.iloc[0] - shy.iloc[-1]/shy.iloc[0])
    wealth = nav/nav.iloc[0]
    dd = float((1 - wealth/wealth.cummax()).max())
    return {
        "cumulative_excess_vs_shy_pctpoints": round(relative*100, 4),
        "cumulative_net_return_pct": round(float((wealth.iloc[-1]-1)*100), 4),
        "max_drawdown_pct": round(dd*100, 4),
        "total_one_way_turnover": round(float(turnover.sum()), 4),
    }


def compare(prices: pd.DataFrame, macro: pd.DataFrame) -> dict:
    prices = bond.validate_prices(prices)
    macro = validate_macro(macro)
    result = {
        "schema": "FUND100_PHASE2_MACRO_BOND_EXPLORATORY_V1",
        "portfolio_status": "RESEARCH_ONLY_NO_PROMOTION",
        "macro_source": "External dated data with conservative assumed availability; "
                        "NOT genuine archived real-time vintages",
        "availability_policy": EXPECTED_AVAILABILITY_POLICY,
        "historical_holdout_not_independent": True,
        "model_selection_on_prior_holdout": False,
        "no_broker_orders": True,
        "live_authorized": False,
        "paper_authorized": False,
        "bond_assets_are_live_whitelisted": False,
        "macro_source_sha256": _hash_macro(macro),
        "bond_price_source_sha256": bond.source_hash(prices),
        "market_dates": {
            "first": prices.index[0].date().isoformat(),
            "last": prices.index[-1].date().isoformat(),
            "total": len(prices),
        },
        "macro_series": list(SERIES),
        "fixed_rules_pctpoints": RULES,
        "costs_bps_per_side": list(COSTS),
        "results": {},
    }
    first = int(len(prices)*0.70) - 1
    for cost in COSTS:
        model = run(prices, macro, cost)
        prior = bond.backtest(prices, lookback=126, cap=0.25, cost_bps=cost)
        result["results"][str(cost)] = {
            "macro_exploratory_late_segment":
                _metrics(model.nav.iloc[first:], model.benchmark.iloc[first:],
                         model.turnover.iloc[first+1:]),
            "prior_price_only_challenger_same_segment":
                _metrics(prior.nav.iloc[first:], prior.control_nav.iloc[first:],
                         prior.turnover.iloc[first+1:]),
        }
    return result


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices-csv", required=True)
    parser.add_argument("--macro-csv", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.prices_csv, index_col="Date", parse_dates=["Date"])
    macro = pd.read_csv(
        args.macro_csv, parse_dates=["observation_date", "available_date"]
    )
    result = compare(prices, macro)
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Bond macro regime exploratory study (no trading).")
    print("Availability policy: two-business-day assumption, NOT vintage evidence.")
    print("Historic holdout independent: NO; prior research already inspected it.")
    for cost, obj in result["results"].items():
        print(
            "Cost", cost, "bps: macro late-segment excess vs SHY (pp):",
            obj["macro_exploratory_late_segment"]["cumulative_excess_vs_shy_pctpoints"],
            "; price-only same segment (pp):",
            obj["prior_price_only_challenger_same_segment"]["cumulative_excess_vs_shy_pctpoints"],
        )
    print("Broker orders, LIVE/PAPER permissions and promotion: NONE")


if __name__ == "__main__":
    main()

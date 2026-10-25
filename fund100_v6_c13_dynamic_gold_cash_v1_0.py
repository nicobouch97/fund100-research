"""C13 portfolio-level GLD-versus-interest-bearing-cash trend challenger.

RESEARCH ONLY. Same 75% fixed equity mix as C13 cash and static-gold
comparators. One lagged 126-session GLD-vs-cash rule, no parameter search.
This previously inspected 2014+ history is NOT an independent holdout.
No broker/private-state access, order intent, or LIVE promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_crossasset_stress_diagnostic_v1_0 as c13

SCHEMA = "FUND100_V6_C13_GOLD_CASH_TREND_CHALLENGER_V1"
LOOKBACK = 126  # fixed before execution; consistent with prior C1 trend horizon
CONTROL = c13.CASH_CONTROL
GOLD = c13.GOLD_ONLY
COSTS_BPS = c13.COSTS_BPS
CASH_SCENARIOS = c13.CASH_SCENARIOS
NO_BROKER_OR_PRIVATE_STATE_ACCESS = True
NO_LIVE_OR_PAPER_AUTHORITY = True


class TrendStudyStop(ValueError):
    pass


def _cash_yields(prices: pd.DataFrame, rates: pd.DataFrame) -> dict[str, pd.Series]:
    source = rates.loc["2013-12-01":prices.index[-1]].copy()
    discount = c13.validate_cash_rates(source, prices.index)
    bill = (discount * 365 / (360 - discount * 91 / 100)).clip(lower=0)
    return {
        "ZERO": pd.Series(0., index=prices.index),
        "IRX_MINUS_50BP": (bill - .5).clip(lower=0),
        "IRX_GROSS": bill,
    }


def verify_original_source(prices: pd.DataFrame, rates: pd.DataFrame,
                           prior: dict) -> str:
    """Require exact same-invocation C13 original price/rate source bytes."""
    data = c13.validate_prices(prices)
    source = rates.loc["2013-12-01":data.index[-1]].copy()
    c13.validate_cash_rates(source, data.index)
    if (not isinstance(prior, dict)
        or prior.get("schema") != c13.SCHEMA
        or prior.get("last_completed_session") != data.index[-1].date().isoformat()
        or prior.get("price_sha256") != sha256(c13.canonical_prices(data).encode()).hexdigest()
        or prior.get("cash_rate_sha256") != sha256(c13.canonical_cash_rates(source).encode()).hexdigest()):
        raise TrendStudyStop("C13 original-source price/rate SHA or session mismatch")
    stamp = prior.get("acquired_at_utc")
    try:
        parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        raise TrendStudyStop("Missing original-source acquisition timestamp") from exc
    if parsed.date() <= data.index[-1].date():
        raise TrendStudyStop("Incomplete or future price session")
    return stamp


def simulate_trend(prices: pd.DataFrame, rate: pd.Series, cost_bps: int) -> dict:
    """Rebalance at month-end close using ONLY the preceding close's signal.

    The target applies after the month-end close; ETF-only traded notional
    is charged once per buy/sell leg. No cash leg is charged. Cash earns
    prior-session lagged bill proxy over actual calendar days.
    """
    data = c13.validate_prices(prices)
    if type(cost_bps) is not int or cost_bps not in COSTS_BPS:
        raise TrendStudyStop("Unregistered transaction-cost scenario")
    if (not isinstance(rate, pd.Series) or not rate.index.equals(data.index)
        or not pd.api.types.is_numeric_dtype(rate)):
        raise TrendStudyStop("Cash yield must align to every market session")
    annual = rate.to_numpy(dtype=float)
    if not np.isfinite(annual).all() or (annual < 0).any() or (annual > 25).any():
        raise TrendStudyStop("Invalid cash yield")
    initial = np.asarray(c13.WEIGHTS[CONTROL], dtype=float)
    gold = np.asarray(c13.WEIGHTS[GOLD], dtype=float)
    if (not np.array_equal(initial[:3], gold[:3])
        or not np.isclose(initial[:3].sum(), .75)
        or not np.isclose(gold[3] - initial[3], .10)
        or not np.isclose(initial[5] - gold[5], .10)):
        raise TrendStudyStop("Fixed 75%-equity GLD/cash contract changed")
    held = initial.copy()
    value = 1.0 - cost_bps / 10000 * float(held[:-1].sum())
    nav = [value]
    turnover = [float(held[:-1].sum())]
    decisions = []
    switches = 0
    previous_gold = False
    risky = data.loc[:, list(c13.ASSETS[:-1])].to_numpy(dtype=float)
    elapsed = np.asarray((data.index[1:] - data.index[:-1]).days, dtype=float)
    for t in range(1, len(data)):
        cash_growth = float(np.exp(annual[t-1] / 100 * elapsed[t-1] / 365.25))
        moves = np.r_[risky[t] / risky[t-1], cash_growth]
        drifted = held * moves
        growth = float(drifted.sum())
        if not np.isfinite(growth) or growth <= 0:
            raise TrendStudyStop("Invalid NAV growth")
        value *= growth
        held = drifted / growth
        traded = 0.0
        if t < len(data)-1 and data.index[t].month != data.index[t+1].month:
            on = False
            signal_relative_pct = None
            if t >= LOOKBACK + 1:
                # Yesterday's GLD return, ending at t-1, versus cash earned
                # over exactly the same preceding 126 close-to-close periods.
                gld_gross = float(risky[t-1, 3] / risky[t-1-LOOKBACK, 3])
                cash_log = float(np.sum(
                    annual[t-LOOKBACK-1:t-1] / 100
                    * elapsed[t-LOOKBACK-1:t-1] / 365.25))
                signal_relative_pct = 100 * (gld_gross / np.exp(cash_log) - 1)
                on = signal_relative_pct > 0
            target = gold if on else initial
            traded = float(np.abs(held[:-1] - target[:-1]).sum())
            value *= 1.0 - cost_bps / 10000 * traded
            held = target.copy()
            if on != previous_gold:
                switches += 1
            previous_gold = on
            decisions.append({
                "rebalance_close": data.index[t].date().isoformat(),
                "signal_latest_close": data.index[t-1].date().isoformat(),
                "gold_target_pct": 10 if on else 0,
                "trailing_gld_minus_cash_pct": (
                    round(signal_relative_pct, 6)
                    if signal_relative_pct is not None else None),
            })
        nav.append(value)
        turnover.append(traded)
    return {
        "nav": pd.Series(nav, index=data.index, dtype=float),
        "turnover": pd.Series(turnover, index=data.index, dtype=float),
        "decisions": decisions,
        "switches": switches,
        "gold_target_months": sum(d["gold_target_pct"] == 10 for d in decisions),
    }


def _period_return(nav: pd.Series, start: str, end: str) -> dict:
    window = nav.loc[start:end]
    if len(window) < 252:
        raise TrendStudyStop("Historical period too short")
    days = (window.index[-1] - window.index[0]).days
    if days <= 0:
        raise TrendStudyStop("Invalid evaluation period")
    return {
        "start": window.index[0].date().isoformat(),
        "end": window.index[-1].date().isoformat(),
        "cagr_pct": round(100 * ((float(window.iloc[-1] / window.iloc[0]))
                                  ** (365.25 / days) - 1), 4),
        "max_drawdown_pct": round(
            100 * float((window / window.cummax() - 1).min()), 4),
    }


def evaluate(prices: pd.DataFrame, rates: pd.DataFrame, prior: dict) -> dict:
    stamp = verify_original_source(prices, rates, prior)
    data = c13.validate_prices(prices)
    yields = _cash_yields(data, rates)
    spy = data["SPY"] / float(data["SPY"].iloc[0])
    stress = spy.pct_change(fill_method=None).iloc[1:] <= c13.STRESS_SPY_DAILY_THRESHOLD
    results = {}
    for bps in COSTS_BPS:
        scenarios = {}
        for name in CASH_SCENARIOS:
            annual = yields[name]
            dynamic = simulate_trend(data, annual, bps)
            cash = c13.simulate(data, c13.WEIGHTS[CONTROL], bps,
                                cash_annual_rate=annual)
            gold = c13.simulate(data, c13.WEIGHTS[GOLD], bps,
                                cash_annual_rate=annual)
            paths = {"DYNAMIC_GOLD_OR_CASH": dynamic["nav"],
                     "STATIC_10_GOLD": gold["nav"],
                     "CASH_CONTROL": cash["nav"]}
            metrics = {k: c13._risk_report(v, spy, stress) for k, v in paths.items()}
            periods = {
                period: {k: _period_return(v, start, end)
                         for k, v in paths.items()}
                for period, start, end in (
                    ("2014_TO_2019", "2014-01-02", "2019-12-31"),
                    ("2020_ONWARD", "2020-01-01", "2099-12-31"),
                )
            }
            scenarios[name] = {
                "metrics": metrics,
                "dynamic_minus_cash_cagr_pp": round(
                    metrics["DYNAMIC_GOLD_OR_CASH"]["net_cagr_pct"]
                    - metrics["CASH_CONTROL"]["net_cagr_pct"], 4),
                "dynamic_minus_static_gold_cagr_pp": round(
                    metrics["DYNAMIC_GOLD_OR_CASH"]["net_cagr_pct"]
                    - metrics["STATIC_10_GOLD"]["net_cagr_pct"], 4),
                "dynamic_turnover_per_initial_nav":
                    round(float(dynamic["turnover"].sum()), 6),
                "gold_target_months": dynamic["gold_target_months"],
                "monthly_decisions": len(dynamic["decisions"]),
                "gold_cash_switches": dynamic["switches"],
                "chronological_periods_already_inspected_not_holdout": periods,
                "decision_log": dynamic["decisions"],
            }
        results[str(bps)] = scenarios
    return {
        "schema": SCHEMA,
        "source_schema": c13.SCHEMA,
        "original_source_acquired_at_utc": stamp,
        "price_sha256": prior["price_sha256"],
        "cash_rate_sha256": prior["cash_rate_sha256"],
        "status": "POST_RESULT_CAUSAL_HISTORICAL_CHALLENGER_NOT_INDEPENDENT_ALPHA",
        "hypothesis": "126_SESSION_GLD_TOTAL_RETURN_GT_LAGGED_CASH_PROXY",
        "signal_observed_through": "PREVIOUS_SESSION_CLOSE",
        "signal_implemented": "MONTH_END_CLOSE_FOR_NEXT_SESSION",
        "fixed_equity_weight": .75,
        "fixed_gold_weight_when_on": .10,
        "preexisting_C13_static_gold_and_cash_comparators_unchanged": True,
        "historical_data_previously_inspected_no_clean_holdout": True,
        "vendor_prices_revisable_and_cash_proxy_not_executable": True,
        "no_new_live_instruments_or_strategy_promotion": True,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "private_state_writes": 0,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--rates", type=Path, required=True)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prices = pd.read_csv(args.prices, index_col="Date", parse_dates=["Date"])
    rates = pd.read_csv(args.rates, index_col="Date", parse_dates=["Date"])
    report = evaluate(prices, rates, json.loads(args.source_report.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    for cost in COSTS_BPS:
        row = report["results"][str(cost)]["IRX_GROSS"]
        print("GOLD_CASH_TREND", cost, "DYNAMIC_MINUS_CASH_CAGR_PP",
              row["dynamic_minus_cash_cagr_pp"],
              "DYNAMIC_MINUS_STATIC_GOLD_CAGR_PP",
              row["dynamic_minus_static_gold_cagr_pp"],
              "SWITCHES", row["gold_cash_switches"])
    print("RESEARCH_ONLY", "BROKER_ORDERS", report["live_orders"])


if __name__ == "__main__":
    main()

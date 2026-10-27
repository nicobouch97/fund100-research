"""V7 R1: predeclared listed real-asset satellite momentum vs matched passive.

VNQ/IGF are traded ETF vehicles, not direct property/infrastructure returns.
The source is one 2026 vendor-adjusted historical vintage (NOT point-in-time
original quotes or an untouched holdout). This is a research-only, causal
signal-timing simulation, not demonstrated alpha or executable broker intent.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

SCHEMA = "FUND100_V7_R1_LISTED_REAL_ASSET_SATELLITE_RESEARCH_V1"
TICKERS = ("VNQ", "IGF", "SPY", "ACWI")
SATELLITES = ("VNQ", "IGF")
FIRST = "2012-01-03"
ASOF = "2026-10-23"
START = "2013-03-01"
ERAS = (("2013_2016", "2013-03-01", "2016-12-30"),
        ("2017_2020", "2017-01-03", "2020-12-31"),
        ("2021_2025", "2021-01-04", "2025-12-31"))
YTD = ("2026_YTD_DIAGNOSTIC", "2026-01-02", ASOF)
COSTS = (5, 15, 35)
BACK_YEAR = 252
SKIP_RECENT = 21
CASH_RESERVE = .05
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
TRADING_AUTHORIZED = False

class RealAssetStop(ValueError):
    pass

def sessions(start, end):
    try:
        return xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp(start), pd.Timestamp(end)).tz_localize(None).normalize()
    except Exception as exc:
        raise RealAssetStop("Unverifiable NYSE calendar") from exc

def validate_prices(prices):
    if (not isinstance(prices, pd.DataFrame)
        or set(prices.columns) != set(TICKERS)
        or not isinstance(prices.index, pd.DatetimeIndex)
        or prices.index.tz is not None
        or prices.index.has_duplicates
        or not prices.index.is_monotonic_increasing):
        raise RealAssetStop("Invalid four-ETF source panel")
    if not prices.index.equals(sessions(FIRST, ASOF)):
        raise RealAssetStop("Missing or additional historical exchange sessions")
    if any(not pd.api.types.is_numeric_dtype(prices[x]) for x in TICKERS):
        raise RealAssetStop("Non-numeric ETF adjusted close")
    values = prices.loc[:, TICKERS].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values <= 0).any()
        or (values > 1e6).any()
        or (prices.loc[:, TICKERS].pct_change(fill_method=None).iloc[1:].abs()
            > .60).to_numpy().any()):
        raise RealAssetStop("Invalid or discontinuous ETF price")
    return prices.loc[:, TICKERS].copy()

def canonical_csv(prices):
    return prices.to_csv(index=True, index_label="Date", date_format="%Y-%m-%d",
                         float_format="%.12g").encode("utf-8")

def signal(prices, t):
    if type(t) is not int or t < BACK_YEAR + 1 or t >= len(prices):
        raise RealAssetStop("Insufficient pre-entry history")
    # Both bars are strictly earlier than the execution close t.
    # 12-minus-1 month momentum excludes the most recent 21 sessions.
    old, recent = t - BACK_YEAR - 1, t - SKIP_RECENT - 1
    return sorted(SATELLITES, key=lambda s:(
        -float(prices[s].iloc[recent] / prices[s].iloc[old] - 1), s))[0]

def rebalance(holdings, cash, target, bps):
    if (set(holdings) != set(TICKERS) or set(target) != set(TICKERS)
        or bps not in COSTS or any(not np.isfinite(x) or x < 0
                                  for x in (*holdings.values(), cash, *target.values()))
        or abs(sum(target.values()) - (1 - CASH_RESERVE)) > 1e-10):
        raise RealAssetStop("Invalid nonlevered target")
    nav = cash + sum(holdings.values())
    if nav <= 0:
        raise RealAssetStop("Nonpositive simulated NAV")
    fee = 0.
    for _ in range(100):
        net = nav - fee
        desired = {s: net * target[s] for s in TICKERS}
        next_fee = bps / 10000 * sum(abs(desired[s] - holdings[s]) for s in TICKERS)
        if abs(next_fee - fee) < 1e-12:
            fee = next_fee
            break
        fee = next_fee
    else:
        raise RealAssetStop("Fee/cash model did not converge")
    net = nav - fee
    desired = {s: net * target[s] for s in TICKERS}
    cash_after = nav - fee - sum(desired.values())
    if cash_after < -1e-9 or abs(cash_after - net * CASH_RESERVE) > nav * 1e-8:
        raise RealAssetStop("Unreconciled cash reserve")
    return desired, cash_after, fee

def simulate(prices, bps):
    prices = validate_prices(prices)
    if type(bps) is not int or bps not in COSTS:
        raise RealAssetStop("Unregistered per-side costs")
    first_i = int(prices.index.get_loc(pd.Timestamp(START)))
    if first_i < BACK_YEAR + 1:
        raise RealAssetStop("Signal would require future data")
    targets = {
        "rotation": {"SPY": .475, "VNQ": 0., "IGF": 0., "ACWI": 0.},
        "static_real_assets": {"SPY": .475, "VNQ": .2375, "IGF": .2375, "ACWI": 0.},
        "passive_spy": {"SPY": .95, "VNQ": 0., "IGF": 0., "ACWI": 0.},
        "passive_acwi": {"SPY": 0., "VNQ": 0., "IGF": 0., "ACWI": .95},
    }
    holdings = {k: {s: 0. for s in TICKERS} for k in targets}
    cash = {k: 100. for k in targets}
    total_fees = {k: 0. for k in targets}
    decisions = []
    marks = []
    last_month = None
    cap_drift_days = 0
    for i in range(first_i, len(prices)):
        date = prices.index[i]
        if i > first_i:
            for name in targets:
                for s in TICKERS:
                    holdings[name][s] *= float(prices[s].iloc[i] / prices[s].iloc[i-1])
        if (date.year, date.month) != last_month:
            choice = signal(prices, i)
            targets["rotation"] = {s: (.475 if s in ("SPY", choice) else 0.)
                                   for s in TICKERS}
            holdings["rotation"], cash["rotation"], fee = rebalance(
                holdings["rotation"], cash["rotation"], targets["rotation"], bps)
            total_fees["rotation"] += fee
            decisions.append({
                "execution_close": date.date().isoformat(),
                "signal_last_used_close": prices.index[i-SKIP_RECENT-1].date().isoformat(),
                "signal_first_used_close": prices.index[i-BACK_YEAR-1].date().isoformat(),
                "selected_real_asset": choice,
                "fee_per_100_initial_nav": round(fee, 8),
            })
            if i == first_i:
                for name in ("static_real_assets", "passive_spy", "passive_acwi"):
                    holdings[name], cash[name], fee = rebalance(
                        holdings[name], cash[name], targets[name], bps)
                    total_fees[name] += fee
            last_month = (date.year, date.month)
        navs = {k: cash[k] + sum(holdings[k].values()) for k in targets}
        if any(not np.isfinite(v) or v <= 0 for v in navs.values()):
            raise RealAssetStop("Invalid marked portfolio NAV")
        if any(holdings["rotation"][s] / navs["rotation"] > .5 + 1e-9
               for s in TICKERS):
            cap_drift_days += 1
        marks.append({"Date": date, **navs})
    return pd.DataFrame(marks).set_index("Date"), {
        "decisions": decisions,
        "costs_per_100_initial_units": {k: round(v, 6) for k, v in total_fees.items()},
        "rotation_daily_observations_over_50pct_single_asset": cap_drift_days,
        "signal_excludes_execution_and_latest_21_closes": True,
        "passive_comparators_bought_once": True,
        "same_5pct_initial_cash_for_all": True,
        "real_fills_verified": False,
    }

def window(marks, start, end):
    frame = marks.loc[start:end]
    if not frame.index.equals(sessions(start, end)) or len(frame) < 45:
        raise RealAssetStop("Incomplete predetermined study window")
    years = (frame.index[-1] - frame.index[0]).days / 365.25
    stats = {}
    for name in ("rotation", "static_real_assets", "passive_spy", "passive_acwi"):
        wealth = frame[name].to_numpy(dtype=float)
        daily = np.diff(wealth) / wealth[:-1]
        stats[name] = {
            "net_model_cagr_pct": round(100 * ((wealth[-1]/wealth[0])**(1/years)-1), 6),
            "maximum_drawdown_pct": round(100 * float(np.min(
                wealth / np.maximum.accumulate(wealth) - 1)), 6),
            "annualized_volatility_pct": round(100 * float(np.std(daily, ddof=1)
                                                       * np.sqrt(252)), 6),
        }
    return {
        "from": start, "through": end, "observations": len(frame),
        "strategies": stats,
        "rotation_minus_static_real_assets_net_cagr_pp": round(
            stats["rotation"]["net_model_cagr_pct"]
            - stats["static_real_assets"]["net_model_cagr_pct"], 6),
        "rotation_minus_spy_net_cagr_pp": round(
            stats["rotation"]["net_model_cagr_pct"]
            - stats["passive_spy"]["net_model_cagr_pct"], 6),
    }

def evaluate(prices, *, captured_utc, source_id):
    try:
        stamp = datetime.strptime(captured_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        if (stamp.strftime("%Y-%m-%dT%H:%M:%SZ") != captured_utc
            or not pd.Timestamp(ASOF).date() < stamp.date()
            or (stamp.date() - pd.Timestamp(ASOF).date()).days > 10):
            raise ValueError()
    except (TypeError, ValueError) as exc:
        raise RealAssetStop("Unverifiable source acquisition date") from exc
    if source_id != "YFINANCE_ADJUSTED_ETF_CLOSE_RETRIEVAL_VINTAGE":
        raise RealAssetStop("Unqualified source")
    frame = validate_prices(prices)
    results = {}
    for bps in COSTS:
        marks, ledger = simulate(frame, bps)
        results[str(bps)] = {
            "eras": {label: window(marks, start, end)
                     for label, start, end in (*ERAS, YTD)},
            "full_path": window(marks, START, ASOF),
            "execution": ledger,
        }
    observed = [results["15"]["eras"][label][
        "rotation_minus_static_real_assets_net_cagr_pp"] for label, _, _ in ERAS]
    verdict = ("POSITIVE_IN_ALL_FIXED_ERAS_DESCRIPTIVE_NOT_ALPHA"
               if all(x > 0 for x in observed) else
               "MIXED_FIXED_ERAS_NO_ROBUST_EDGE"
               if any(x > 0 for x in observed) else
               "NO_POSITIVE_FIXED_ERA_RELATIVE_RETURN")
    return {
        "schema": SCHEMA,
        "status": "RETROSPECTIVE_REAL_LISTED_ASSET_MOMENTUM_RESEARCH_ONLY",
        "source_acquired_at_utc": captured_utc,
        "source_id": source_id,
        "source_csv_sha256": sha256(canonical_csv(frame)).hexdigest(),
        "source_tickers": list(TICKERS),
        "first_close": FIRST, "last_close": ASOF, "first_decision": START,
        "fixed_eras": [label for label, _, _ in ERAS],
        "2026_ytd_excluded_from_verdict": True,
        "costs_bps_each_side": list(COSTS),
        "signal": "PRIOR_252_TO_21_COMPLETED_XNYS_CLOSES_BEST_VNQ_OR_IGF",
        "allocation": "47.5pct_SPY_47.5pct_selected_real_asset_5pct_cash",
        "passive_real_asset_control": "47.5pct_SPY_23.75pct_VNQ_23.75pct_IGF_5pct_cash",
        "source_is_single_revised_2026_vintage_not_independent_holdout": True,
        "historical_symbols_and_eras_retrospectively_known": True,
        "vendor_adjusted_dividends_not_authenticated_total_return": True,
        "ETF_infrastructure_equity_beta_and_rate_sensitivity_not_separate_alpha": True,
        "intramonth_risk_cap_drift_is_reported_not_silently_repaired": True,
        "spreads_taxes_impact_fractional_eligibility_unverified": True,
        "cash_earns_zero_interest": True,
        "results": results, "fixed_15bps_era_verdict": verdict,
        "current_live_cap_usd": "130.30",
        "broker_gets": BROKER_GETS, "broker_posts": BROKER_POSTS,
        "broker_orders": BROKER_ORDERS, "trading_authorized": False,
        "live_authorized": False,
    }

def fetch_vendor():
    import yfinance as yf
    data = yf.download(tickers=list(TICKERS), start=FIRST, end="2026-10-24",
                       auto_adjust=False, actions=False, threads=False,
                       progress=False)
    if not isinstance(data, pd.DataFrame) or not isinstance(data.columns, pd.MultiIndex):
        raise RealAssetStop("Missing vendor multicolumn ETF adjusted closes")
    series = {}
    for ticker in TICKERS:
        key = next((k for k in (("Adj Close", ticker), (ticker, "Adj Close"))
                    if k in data.columns), None)
        if key is None:
            raise RealAssetStop("Missing vendor adjusted ETF price " + ticker)
        series[ticker] = data[key]
    frame = pd.DataFrame(series)
    frame.index = (frame.index.tz_convert("UTC").tz_localize(None).normalize()
                   if frame.index.tz is not None else frame.index.normalize())
    return validate_prices(frame)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    prices = fetch_vendor()
    report = evaluate(prices,
        captured_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_id="YFINANCE_ADJUSTED_ETF_CLOSE_RETRIEVAL_VINTAGE")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "original-adjusted-real-assets.csv").write_bytes(canonical_csv(prices))
    (args.output_dir / "real-assets-costed-research.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("V7 R1 fixed 15bps historical verdict:", report["fixed_15bps_era_verdict"])
    for label, _, _ in ERAS:
        print(label, "rotation minus static matched real assets net CAGR pp:",
              report["results"]["15"]["eras"][label][
                  "rotation_minus_static_real_assets_net_cagr_pp"])
    print("Research only; zero broker access or order authority.")

if __name__ == "__main__":
    main()

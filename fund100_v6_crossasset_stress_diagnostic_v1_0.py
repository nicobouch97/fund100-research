"""Fixed-basket cross-asset downside diagnostics, RESEARCH ONLY.

Compares the proposed S1 sector mix with a proportionally de-risked cash
control and an equal-equity-risk GLD/SHY replacement. All three are static
monthly-rebalanced *counterfactuals*, not original S1's live controller.
The 2026-selected weights are applied retrospectively; vendor-adjusted
prices are revisable and this is not an independent alpha holdout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA = "FUND100_V6_CROSSASSET_FIXED_BASKET_STRESS_DIAGNOSTIC_V2"
SYMBOLS = ("XLK", "XLE", "IWM", "GLD", "SHY", "SPY")
ASSETS = ("XLK", "XLE", "IWM", "GLD", "SHY", "CASH")
STUDY_START = "2014-01-02"
COSTS_BPS = (5, 15, 35)
# The existing 95%-invested S1 thesis, and two fixed controls. No fitting.
WEIGHTS = {
    "S1_95_EQUITY_5_CASH": (.475, .285, .19, 0., 0., .05),
    "MATCHED_75_EQUITY_25_CASH": (.375, .225, .15, 0., 0., .25),
    "MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH":
        (.375, .225, .15, .10, .10, .05),
}
# Well-known historical stress intervals, NOT optimized evaluation windows.
STRESS_WINDOWS = {
    "COVID_2020": ("2020-02-19", "2020-03-23"),
    "EQUITY_BEAR_2022": ("2022-01-03", "2022-10-14"),
}
STRESS_SPY_DAILY_THRESHOLD = -.02
NO_BROKER_OR_PRIVATE_STATE_ACCESS = True
NO_LIVE_OR_PAPER_AUTHORITY = True


class CrossAssetStop(ValueError):
    pass


def validate_prices(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(SYMBOLS):
        raise CrossAssetStop("Six exact, independently priced ETFs required")
    ix = raw.index
    if (not isinstance(ix, pd.DatetimeIndex) or ix.tz is not None
        or ix.has_duplicates or not ix.is_monotonic_increasing
        or len(ix) < 1000 or any(x != x.normalize() for x in ix)
        or ix[0] > pd.Timestamp(STUDY_START)
        or ix[-1] < pd.Timestamp("2023-01-01")):
        raise CrossAssetStop("Insufficient, unordered or undated common ETF history")
    if any(not pd.api.types.is_numeric_dtype(raw[x]) for x in SYMBOLS):
        raise CrossAssetStop("Non-numeric market prices")
    data = raw.loc[:, list(SYMBOLS)].copy()
    v = data.to_numpy(dtype=float)
    if (not np.isfinite(v).all() or (v <= 0).any()
        or (data.pct_change(fill_method=None).iloc[1:].abs().to_numpy() > .45).any()):
        raise CrossAssetStop("Missing, invalid or discontinuous adjusted ETF prices")
    return data.loc[STUDY_START:]


def canonical_prices(data: pd.DataFrame) -> str:
    return validate_prices(data).to_csv(index_label="Date", date_format="%Y-%m-%d",
                                        float_format="%.10f")


def simulate(prices: pd.DataFrame, weights: tuple[float, ...], cost_bps: int) -> dict:
    """Monthly close rebalance after today's move, effective NEXT session.

    Buy-side costs charged at inception; all later buys AND sells are
    charged on ETF traded notional only. CASH is not a traded security,
    has zero nominal return; SHY is a risky traded ETF.
    """
    if cost_bps not in COSTS_BPS or type(cost_bps) is not int:
        raise CrossAssetStop("Only fixed 5/15/35bp per-side costs supported")
    if (len(weights) != len(ASSETS) or any(not np.isfinite(x) or x < 0 for x in weights)
        or not np.isclose(sum(weights), 1, atol=1e-12)):
        raise CrossAssetStop("Unreviewed, leveraged or unbalanced basket")
    target = np.asarray(weights, dtype=float)
    data = validate_prices(prices)
    # Fail closed on undocumented symbols, including any futures/leverage.
    risky = data.loc[:, list(ASSETS[:-1])].to_numpy(dtype=float)
    value = 1.0 - cost_bps / 10000 * float(target[:-1].sum())
    held = target.copy()
    nav = [value]
    turnover = [float(target[:-1].sum())]
    for i in range(1, len(data)):
        moves = np.r_[risky[i] / risky[i-1], 1.0]
        drifted = held * moves
        growth = float(drifted.sum())
        if not np.isfinite(growth) or growth <= 0:
            raise CrossAssetStop("Nonpositive hypothetical basket value")
        value *= growth
        held = drifted / growth
        traded = 0.0
        # The last session of each month is a trade at THAT close, and
        # the rebalance only affects exposure from the following close.
        if i < len(data)-1 and data.index[i].month != data.index[i+1].month:
            # Count ETF buys and sells once each, but never the offsetting
            # change in CASH as another traded leg. The old full-vector
            # L1 distance incorrectly charged the cash transfer twice.
            traded = float(np.abs(held[:-1] - target[:-1]).sum())
            value *= 1.0 - cost_bps / 10000 * traded
            held = target.copy()
        nav.append(value)
        turnover.append(traded)
    path = pd.Series(nav, index=data.index, name="net_nav", dtype=float)
    return {"nav": path, "turnover": pd.Series(turnover, index=data.index)}


def _risk_report(nav: pd.Series, spy: pd.Series, stress: pd.Series) -> dict:
    ret = nav.pct_change(fill_method=None).iloc[1:]
    ref = spy.pct_change(fill_method=None).iloc[1:]
    if not ret.index.equals(ref.index) or not stress.index.equals(ref.index):
        raise CrossAssetStop("Risk/benchmark stress dates do not align")
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    if years <= 0 or ret.std(ddof=1) <= 0 or ref.var(ddof=1) <= 1e-12:
        raise CrossAssetStop("Risk attribution not identifiable")
    return {
        "net_cagr_pct": round(100 * (float(nav.iloc[-1]) ** (1 / years) - 1), 4),
        "max_drawdown_pct": round(100 * float((nav / nav.cummax() - 1).min()), 4),
        "annualized_volatility_pct": round(100 * float(ret.std(ddof=1) * np.sqrt(252)), 4),
        "same_session_spy_beta": round(float(ret.cov(ref) / ref.var(ddof=1)), 4),
        "same_session_spy_correlation": round(float(ret.corr(ref)), 4),
        "spy_down_2pct_sessions": int(stress.sum()),
        "mean_return_on_spy_down_2pct_sessions_pct":
            round(100 * float(ret.loc[stress].mean()), 4) if stress.any() else None,
        "stress_windows": {
            label: {
                "window_start": start, "window_end": end,
                "net_portfolio_return_pct": round(100 * float(
                    nav.loc[end] / nav.loc[start] - 1), 4),
                "window_max_drawdown_pct": round(100 * float((
                    nav.loc[start:end] / nav.loc[start:end].cummax() - 1).min()), 4),
            } for label, (start, end) in STRESS_WINDOWS.items()
        },
    }


def evaluate(prices: pd.DataFrame, *, acquired_at_utc: str) -> dict:
    data = validate_prices(prices)
    try:
        stamp = datetime.strptime(acquired_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        if stamp.strftime("%Y-%m-%dT%H:%M:%SZ") != acquired_at_utc:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise CrossAssetStop("Original-source acquisition UTC timestamp required") from exc
    if data.index[-1].date() >= stamp.date():
        raise CrossAssetStop("Do not use today's incomplete price bar")
    for start, end in STRESS_WINDOWS.values():
        if start not in data.index or end not in data.index:
            raise CrossAssetStop("Original stress dates not in common trading sessions")
    reference = data["SPY"] / float(data["SPY"].iloc[0])
    ref_returns = reference.pct_change(fill_method=None).iloc[1:]
    stress = ref_returns <= STRESS_SPY_DAILY_THRESHOLD
    results = {}
    for bps in COSTS_BPS:
        rows = {}
        for name, weights in WEIGHTS.items():
            result = simulate(data, weights, bps)
            nav = result["nav"]
            rows[name] = {
                **_risk_report(nav, reference, stress),
                "net_cumulative_return_pct": round(100 * (float(nav.iloc[-1]) - 1), 4),
                "total_traded_notional_per_initial_nav":
                    round(float(result["turnover"].sum()), 6),
            }
        div = rows["MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH"]
        cash = rows["MATCHED_75_EQUITY_25_CASH"]
        rows["equal_equity_exposure_diversification_vs_cash_control"] = {
            "cagr_difference_pp": round(div["net_cagr_pct"] - cash["net_cagr_pct"], 4),
            "max_drawdown_difference_pp": round(div["max_drawdown_pct"] - cash["max_drawdown_pct"], 4),
            "spy_down_2pct_mean_daily_difference_pp": round(
                div["mean_return_on_spy_down_2pct_sessions_pct"]
                - cash["mean_return_on_spy_down_2pct_sessions_pct"], 4)
                if stress.any() else None,
        }
        results[str(bps)] = rows
    return {
        "schema": SCHEMA, "status": "DESCRIPTIVE_HISTORICAL_CROSSASSET_NOT_ALPHA",
        "source": "YAHOO_YFINANCE_AUTO_ADJUSTED_REVISABLE_CLOSES",
        "acquired_at_utc": acquired_at_utc,
        "price_sha256": sha256(canonical_prices(data).encode()).hexdigest(),
        "first_session": data.index[0].date().isoformat(),
        "last_completed_session": data.index[-1].date().isoformat(),
        "common_sessions": len(data), "fixed_baskets": dict(zip(WEIGHTS, [
            dict(zip(ASSETS, v)) for v in WEIGHTS.values()])),
        "rebalance": "MONTH_END_CLOSE_EFFECTIVE_NEXT_SESSION",
        "per_side_costs_bps": list(COSTS_BPS),
        "inception_buys_charged": True,
        "rebalance_turnover_definition": "SUM_ABS_ETF_WEIGHT_CHANGES_EXCLUDING_CASH",
        "prior_c13_v1_cash_leg_cost_overstatement_corrected": True,
        "cash_nominal_return_assumed_zero": True,
        "shy_is_risky_bond_etf_not_cash": True,
        "no_current_broker_asset_eligibility_inferred": True,
        "original_s1_controller_not_modified_or_replayed": True,
        "survivor_chosen_2026_weights_backapplied_not_point_in_time_alpha": True,
        "stress_windows_selected_after_history_not_holdout": True,
        "funded_trading_or_rebalance_authorized": False,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "private_state_writes": 0,
        "costed_historical_diagnostics": results,
    }


def main() -> None:
    import yfinance as yf
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prices-output", type=Path, required=True)
    args = parser.parse_args()
    end = datetime.now(timezone.utc).date().isoformat()
    raw = yf.download(tickers=list(SYMBOLS), start="2013-12-01", end=end,
                      auto_adjust=True, interval="1d", actions=False,
                      progress=False, threads=False)
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise CrossAssetStop("Public research market source unavailable")
    prices = {}
    for symbol in SYMBOLS:
        key = ("Close", symbol)
        if key not in raw.columns:
            raise CrossAssetStop("Missing source-adjusted close: " + symbol)
        prices[symbol] = raw[key]
    data = pd.DataFrame(prices).sort_index()
    if data.index.tz is not None:
        data.index = data.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        data.index = data.index.normalize()
    if data.isna().any().any():
        raise CrossAssetStop("Unexplained interior or inception source gaps")
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = evaluate(data, acquired_at_utc=captured)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.prices_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.prices_output.write_text(canonical_prices(data))
    print("Historical cross-asset stress diagnostic; source hash:", result["price_sha256"])
    print("Sessions:", result["common_sessions"], "last:", result["last_completed_session"])
    print("15bp equal-equity comparison:", result["costed_historical_diagnostics"]["15"]
          ["equal_equity_exposure_diversification_vs_cash_control"])
    print("No alpha or trading authority")


if __name__ == "__main__":
    main()

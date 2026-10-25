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

SCHEMA = "FUND100_V6_CROSSASSET_FIXED_BASKET_STRESS_DIAGNOSTIC_V5"
CASH_SCENARIOS = ("ZERO", "IRX_MINUS_50BP", "IRX_GROSS")
CASH_RATE_LAG_WEEKDAYS = 3  # conservative proxy, NOT verified historical release vintages
SYMBOLS = ("XLK", "XLE", "IWM", "GLD", "SHY", "SPY")
ASSETS = ("XLK", "XLE", "IWM", "GLD", "SHY", "CASH")
STUDY_START = "2014-01-02"
COSTS_BPS = (5, 15, 35)
# The existing 95%-invested S1 thesis, and two fixed controls. No fitting.
WEIGHTS = {
    "S1_95_EQUITY_5_CASH": (.475, .285, .19, 0., 0., .05),
    "MATCHED_75_EQUITY_25_CASH": (.375, .225, .15, 0., 0., .25),
    "MATCHED_75_EQUITY_10_GOLD_15_CASH": (.375, .225, .15, .10, 0., .15),
    "MATCHED_75_EQUITY_10_SHY_15_CASH": (.375, .225, .15, 0., .10, .15),
    "MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH":
        (.375, .225, .15, .10, .10, .05),
}
# Well-known historical stress intervals, NOT optimized evaluation windows.
STRESS_WINDOWS = {
    "COVID_2020": ("2020-02-19", "2020-03-23"),
    "EQUITY_BEAR_2022": ("2022-01-03", "2022-10-14"),
}
STRESS_SPY_DAILY_THRESHOLD = -.02
# Post-result diagnostic controls, not new pre-registered strategies or a holdout.
CASH_CONTROL = "MATCHED_75_EQUITY_25_CASH"
GOLD_ONLY = "MATCHED_75_EQUITY_10_GOLD_15_CASH"
SHY_ONLY = "MATCHED_75_EQUITY_10_SHY_15_CASH"
GOLD_SHY = "MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH"
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


def verify_original_exchange_sessions(index: pd.DatetimeIndex) -> int:
    """Verify EVERY actual XNYS session before accepting original ETF prices.

    A common-vendor gap affecting all six ETFs would survive dropna(how="all")
    and the ordinary numeric validator. Check the independent exchange
    calendar at the original acquisition boundary, not synthetic test data.
    This proves date coverage, NOT independently authenticated prices,
    corporate actions, cash-yield vintages or executable market returns.
    """
    if (not isinstance(index, pd.DatetimeIndex) or len(index) < 2
        or index.tz is not None or index.has_duplicates
        or not index.is_monotonic_increasing
        or any(day != day.normalize() for day in index)):
        raise CrossAssetStop("Invalid original XNYS source date index")
    try:
        import exchange_calendars as xcals
        expected = xcals.get_calendar("XNYS").sessions_in_range(
            index[0], index[-1]).tz_localize(None).normalize()
    except Exception as exc:
        raise CrossAssetStop("Independent XNYS calendar unavailable") from exc
    if not index.equals(expected):
        raise CrossAssetStop(
            "Original ETF source has missing or extra XNYS sessions")
    return len(expected)


def canonical_prices(data: pd.DataFrame) -> str:
    return validate_prices(data).to_csv(index_label="Date", date_format="%Y-%m-%d",
                                        float_format="%.10f")


def validate_cash_rates(raw: pd.DataFrame, price_dates: pd.DatetimeIndex) -> pd.Series:
    """Yahoo ^IRX 13-week T-bill discount quotes, lagged three weekdays.

    IRX is a bill discount yield, NOT a cash deposit or directly earned return.
    The weekday lag is not a verified historical data-release vintage.
    """
    if (not isinstance(raw, pd.DataFrame) or list(raw.columns) != ["IRX"]
        or not isinstance(raw.index, pd.DatetimeIndex)):
        raise CrossAssetStop("Exact dated YAHOO IRX rate series required")
    ix = raw.index
    if (ix.tz is not None or ix.has_duplicates or not ix.is_monotonic_increasing
        or any(x != x.normalize() for x in ix) or len(ix) < 1000
        or ix[0] > pd.Timestamp("2013-12-20")
        or ix[-1] < pd.Timestamp(price_dates[-1]) - pd.Timedelta(days=10)):
        raise CrossAssetStop("Incomplete, stale or unordered cash-rate source")
    if not pd.api.types.is_numeric_dtype(raw["IRX"]):
        raise CrossAssetStop("Non-numeric cash-rate source")
    vals = raw["IRX"].to_numpy(dtype=float)
    if not np.isfinite(vals).all() or (vals < -2).any() or (vals > 25).any():
        raise CrossAssetStop("Invalid YAHOO IRX percentage rate")
    asof = price_dates - pd.offsets.BDay(CASH_RATE_LAG_WEEKDAYS)
    observed = pd.Series(ix, index=ix).reindex(asof, method="ffill")
    lagged = raw["IRX"].reindex(asof, method="ffill")
    ages = (asof - pd.DatetimeIndex(observed)).days
    if lagged.isna().any() or (ages > 10).any() or (ages < 0).any():
        raise CrossAssetStop("Missing or stale pre-decision cash-rate observations")
    return pd.Series(lagged.to_numpy(dtype=float), index=price_dates,
                     name="lagged_IRX_percent")


def canonical_cash_rates(raw: pd.DataFrame) -> str:
    return raw.to_csv(index_label="Date", date_format="%Y-%m-%d",
                      float_format="%.8f")


def simulate(prices: pd.DataFrame, weights: tuple[float, ...], cost_bps: int,
             *, cash_annual_rate: pd.Series | None = None) -> dict:
    """Monthly close rebalance after today's move, effective NEXT session.

    Buy-side costs charged at inception; all later buys AND sells are
    charged on ETF traded notional only. CASH is not a traded security;
    optional lagged annual cash rates accrue over actual calendar days.
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
    if cash_annual_rate is None:
        cash_rates = np.zeros(len(data), dtype=float)
    else:
        if (not isinstance(cash_annual_rate, pd.Series)
            or not cash_annual_rate.index.equals(data.index)
            or not pd.api.types.is_numeric_dtype(cash_annual_rate)):
            raise CrossAssetStop("Cash rates must align exactly with ETF sessions")
        cash_rates = cash_annual_rate.to_numpy(dtype=float)
        if (not np.isfinite(cash_rates).all() or (cash_rates < 0).any()
            or (cash_rates > 25).any()):
            raise CrossAssetStop("Invalid annual cash rates")
    value = 1.0 - cost_bps / 10000 * float(target[:-1].sum())
    held = target.copy()
    nav = [value]
    turnover = [float(target[:-1].sum())]
    for i in range(1, len(data)):
        elapsed_days = (data.index[i] - data.index[i-1]).days
        # The prior session's already-lagged rate is used for this interval.
        cash_growth = float(np.exp(cash_rates[i-1] / 100 * elapsed_days / 365.25))
        moves = np.r_[risky[i] / risky[i-1], cash_growth]
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


def sleeve_attribution(by_basket: dict) -> dict:
    """Descriptive 10% sleeve ablations at identical 75% equity exposure.

    Compare replacing 10% cash with GLD, with SHY, and with both. The
    interaction residual is arithmetic nonadditivity of CAGR/drawdown, NOT
    a causal factor return, statistical interaction, or investable alpha.
    """
    if set(by_basket) != set(WEIGHTS):
        raise CrossAssetStop("Missing or unreviewed sleeve counterfactual")
    for name in (CASH_CONTROL, GOLD_ONLY, SHY_ONLY, GOLD_SHY):
        if not np.isclose(sum(WEIGHTS[name][:3]), .75, atol=1e-12):
            raise CrossAssetStop("Sleeve attribution equity exposure changed")
        if WEIGHTS[name][:3] != WEIGHTS[CASH_CONTROL][:3]:
            raise CrossAssetStop("Sleeve attribution equity mix changed")
    output = {}
    for metric, label in (("net_cagr_pct", "cagr"),
                          ("max_drawdown_pct", "max_drawdown")):
        base = by_basket[CASH_CONTROL][metric]
        gold = by_basket[GOLD_ONLY][metric] - base
        shy = by_basket[SHY_ONLY][metric] - base
        combined = by_basket[GOLD_SHY][metric] - base
        output[label + "_pp"] = {
            "gold_10pct_minus_cash": round(gold, 4),
            "shy_10pct_minus_cash": round(shy, 4),
            "both_10pct_each_minus_cash": round(combined, 4),
            "nonadditive_residual": round(combined - gold - shy, 4),
        }
    return output


def calendar_year_relative_log_wealth(navs: dict[str, pd.Series]) -> dict:
    """Attribute fixed-basket net relative log wealth by calendar year.

    Includes inception trading-cost differences in the first year. Omitting
    the strongest year is descriptive arithmetic, NOT an executable strategy.
    """
    names = (CASH_CONTROL, GOLD_ONLY, SHY_ONLY, GOLD_SHY)
    if set(navs) != set(names):
        raise CrossAssetStop("Missing or unexpected net NAV for year attribution")
    baseline = navs[CASH_CONTROL]
    if (not isinstance(baseline, pd.Series)
        or not isinstance(baseline.index, pd.DatetimeIndex)
        or baseline.index.has_duplicates or not baseline.index.is_monotonic_increasing
        or baseline.index.tz is not None or len(baseline) < 2):
        raise CrossAssetStop("Invalid baseline NAV dates")
    for name in names:
        path = navs[name]
        if (not isinstance(path, pd.Series)
            or not path.index.equals(baseline.index)
            or not pd.api.types.is_numeric_dtype(path)):
            raise CrossAssetStop("NAVs must have identical dates and numeric values")
        values = path.to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise CrossAssetStop("Nonpositive or nonfinite NAV")
    out = {}
    for name in (GOLD_ONLY, SHY_ONLY, GOLD_SHY):
        relative_log = np.log(navs[name].to_numpy(dtype=float) /
                              baseline.to_numpy(dtype=float))
        # Each period's log relative return, plus the one-off inception
        # ETF purchase-cost difference in the first calendar year.
        increments = np.diff(relative_log, prepend=0.0)
        contributions = pd.Series(increments, index=baseline.index)
        yearly = contributions.groupby(contributions.index.year).sum()
        total = float(relative_log[-1])
        if not np.isclose(float(yearly.sum()), total, rtol=0, atol=1e-10):
            raise CrossAssetStop("Annual log attribution does not reconcile")
        positive = yearly[yearly > 0]
        strongest = int(positive.idxmax()) if len(positive) else None
        excluded = total - float(positive.loc[strongest]) if strongest else total
        out[name] = {
            "terminal_relative_log_wealth_pct": round(100 * total, 6),
            "inception_cost_relative_log_wealth_pct": round(
                100 * float(relative_log[0]), 6),
            "calendar_year_log_relative_wealth_pct": {
                str(int(year)): round(100 * float(value), 6)
                for year, value in yearly.items()
            },
            "positive_years": int((yearly > 0).sum()),
            "negative_years": int((yearly < 0).sum()),
            "largest_positive_year": strongest,
            "largest_positive_year_log_relative_wealth_pct": (
                round(100 * float(positive.loc[strongest]), 6)
                if strongest is not None else None),
            "total_ex_largest_positive_year_log_relative_wealth_pct":
                round(100 * excluded, 6),
        }
    return out


def evaluate(prices: pd.DataFrame, *, acquired_at_utc: str,
             cash_rates: pd.DataFrame) -> dict:
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
    # Freeze exactly the rates available through the last completed price day.
    rates_source = cash_rates.loc["2013-12-01":data.index[-1]].copy()
    lagged_irx_discount = validate_cash_rates(rates_source, data.index)
    # Convert a 91-day bank discount quote into an annual investment-yield
    # proxy, not an executable bill roll or an actual broker cash yield.
    bill_yield = (lagged_irx_discount * 365 /
                  (360 - lagged_irx_discount * 91 / 100)).clip(lower=0)
    cash_yields = {
        "ZERO": pd.Series(0., index=data.index),
        "IRX_MINUS_50BP": (bill_yield - .5).clip(lower=0),
        "IRX_GROSS": bill_yield,
    }
    reference = data["SPY"] / float(data["SPY"].iloc[0])
    ref_returns = reference.pct_change(fill_method=None).iloc[1:]
    stress = ref_returns <= STRESS_SPY_DAILY_THRESHOLD
    results = {}
    carry_results = {}
    year_concentration = None
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
        scenario_rows = {}
        for label in CASH_SCENARIOS:
            concentration_navs = {}
            by_basket = {}
            for name, weights in WEIGHTS.items():
                trial = simulate(data, weights, bps,
                                 cash_annual_rate=cash_yields[label])
                by_basket[name] = _risk_report(trial["nav"], reference, stress)
                if bps == 15 and label == "IRX_GROSS" and name in (
                    CASH_CONTROL, GOLD_ONLY, SHY_ONLY, GOLD_SHY):
                    concentration_navs[name] = trial["nav"]
            if bps == 15 and label == "IRX_GROSS":
                year_concentration = calendar_year_relative_log_wealth(
                    concentration_navs)
            baseline = by_basket["MATCHED_75_EQUITY_25_CASH"]
            diverse = by_basket["MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH"]
            scenario_rows[label] = {
                "by_basket": by_basket,
                "equal_equity_sleeve_attribution": sleeve_attribution(by_basket),
                "diversified_minus_cash_control_cagr_pp": round(
                    diverse["net_cagr_pct"] - baseline["net_cagr_pct"], 4),
                "diversified_minus_cash_control_max_drawdown_pp": round(
                    diverse["max_drawdown_pct"] - baseline["max_drawdown_pct"], 4),
            }
        # Strict parity: the new zero-rate model must reproduce the
        # previously reported zero-carry model, not silently reprice it.
        for name in WEIGHTS:
            if scenario_rows["ZERO"]["by_basket"][name] != {
                k: rows[name][k] for k in scenario_rows["ZERO"]["by_basket"][name]
            }:
                raise CrossAssetStop("Original zero-carry result changed")
        carry_results[str(bps)] = scenario_rows
    if year_concentration is None:
        raise CrossAssetStop("Required historical concentration missing")
    return {
        "schema": SCHEMA, "status": "DESCRIPTIVE_HISTORICAL_CROSSASSET_NOT_ALPHA",
        "source": "YAHOO_YFINANCE_AUTO_ADJUSTED_REVISABLE_CLOSES",
        "acquired_at_utc": acquired_at_utc,
        "price_sha256": sha256(canonical_prices(data).encode()).hexdigest(),
        "cash_rate_source": "YAHOO_IRX_13W_BILL_DISCOUNT_YIELD_PROXY",
        "cash_rate_sha256": sha256(canonical_cash_rates(rates_source).encode()).hexdigest(),
        "cash_rate_lag_weekdays": CASH_RATE_LAG_WEEKDAYS,
        "cash_rate_scenarios": list(CASH_SCENARIOS),
        "cash_rate_50bp_haircut_is_assumption_not_observed_deposit_spread": True,
        "cash_rate_not_achievable_account_yield_or_original_release_vintage": True,
        "irx_discount_to_investment_yield_91day_conversion": True,
        "first_session": data.index[0].date().isoformat(),
        "last_completed_session": data.index[-1].date().isoformat(),
        "common_sessions": len(data), "fixed_baskets": dict(zip(WEIGHTS, [
            dict(zip(ASSETS, v)) for v in WEIGHTS.values()])),
        "rebalance": "MONTH_END_CLOSE_EFFECTIVE_NEXT_SESSION",
        "per_side_costs_bps": list(COSTS_BPS),
        "inception_buys_charged": True,
        "rebalance_turnover_definition": "SUM_ABS_ETF_WEIGHT_CHANGES_EXCLUDING_CASH",
        "prior_c13_v1_cash_leg_cost_overstatement_corrected": True,
        "original_zero_cash_baseline_preserved": True,
        "post_result_sleeve_ablation_not_independent_holdout": True,
        "sleeve_attribution_is_nonadditive_metric_diagnostic_not_alpha": True,
        "calendar_year_concentration_is_post_result_not_holdout": True,
        "calendar_year_log_wealth_not_cagr_or_executable_leave_year_out": True,
        "calendar_year_first_and_last_may_be_partial": True,
        "year_concentration_15bp_irx_gross": year_concentration,
        "shy_is_risky_bond_etf_not_cash": True,
        "no_current_broker_asset_eligibility_inferred": True,
        "original_s1_controller_not_modified_or_replayed": True,
        "survivor_chosen_2026_weights_backapplied_not_point_in_time_alpha": True,
        "stress_windows_selected_after_history_not_holdout": True,
        "funded_trading_or_rebalance_authorized": False,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "private_state_writes": 0,
        "costed_historical_diagnostics": results,
        "interest_bearing_cash_sensitivity": carry_results,
    }


def main() -> None:
    import yfinance as yf
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prices-output", type=Path, required=True)
    parser.add_argument("--rates-output", type=Path, required=True)
    args = parser.parse_args()
    end = datetime.now(timezone.utc).date().isoformat()
    raw = yf.download(tickers=list(SYMBOLS) + ["^IRX"], start="2013-12-01", end=end,
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
    # ^IRX may quote on a date when no ETF traded. Remove only all-ETF-
    # missing rows; any partial ETF gaps still fail closed below.
    data = pd.DataFrame(prices).sort_index().dropna(how="all")
    if data.index.tz is not None:
        data.index = data.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        data.index = data.index.normalize()
    if data.isna().any().any():
        raise CrossAssetStop("Unexplained interior or inception source gaps")
    # An all-six-ETF missing date was removed above and cannot be detected
    # by a per-row NaN check. Independently require EVERY exchange session.
    verified_sessions = verify_original_exchange_sessions(data.index)
    # Same public vendor download; ^IRX is a quoted discount-yield index,
    # not a total-return security or an achievable cash account rate.
    if ("Close", "^IRX") not in raw.columns:
        raise CrossAssetStop("Missing historical 13-week T-bill quote ^IRX")
    irx = raw[("Close", "^IRX")].dropna()
    if irx.empty:
        raise CrossAssetStop("No observed historical bill discount yields")
    rate_data = pd.DataFrame({"IRX": irx.to_numpy(dtype=float)}, index=irx.index)
    if rate_data.index.tz is not None:
        rate_data.index = rate_data.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        rate_data.index = rate_data.index.normalize()
    rate_data = rate_data.loc["2013-12-01":data.index[-1]]
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = evaluate(data, acquired_at_utc=captured, cash_rates=rate_data)
    # Set these only after the real original-vendor calendar check. Pure
    # offline evaluate() deliberately makes no original-source claim.
    result["original_price_calendar"] = "XNYS"
    result["original_price_calendar_sessions_verified"] = verified_sessions
    result["original_price_calendar_full_coverage"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.prices_output.parent.mkdir(parents=True, exist_ok=True)
    args.rates_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.prices_output.write_text(canonical_prices(data))
    args.rates_output.write_text(canonical_cash_rates(rate_data))
    print("Historical cross-asset stress diagnostic; source hash:", result["price_sha256"])
    print("Sessions:", result["common_sessions"], "last:", result["last_completed_session"])
    print("15bp equal-equity comparison:", result["costed_historical_diagnostics"]["15"]
          ["equal_equity_exposure_diversification_vs_cash_control"])
    print("15bp IRX gross sleeve attribution:",
          result["interest_bearing_cash_sensitivity"]["15"]["IRX_GROSS"]
          ["equal_equity_sleeve_attribution"])
    print("15bp cash-carry sensitivity:", {
        name: row["diversified_minus_cash_control_cagr_pp"]
        for name, row in result["interest_bearing_cash_sensitivity"]["15"].items()
    })
    print("15bp IRX gross relative log-wealth year concentration:",
          result["year_concentration_15bp_irx_gross"])
    print("No alpha or trading authority")


if __name__ == "__main__":
    main()

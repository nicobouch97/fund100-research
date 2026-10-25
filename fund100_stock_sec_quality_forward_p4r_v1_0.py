"""P4R: observed post-10-K stock returns by original SEC quality score.

This is an EVENT-LEVEL HISTORICAL DIAGNOSTIC, not a tradable strategy:
the 2026 survivor-selected 12-issuer roster, today-retrieved SEC facts,
revisable adjusted price history and missing delistings invalidate alpha
claims. Each score is known only after its own 10-K availability date.
Entry is the NEXT completed exchange close, exit 126 sessions later.
There is no rebalancing, selection optimization, brokerage or order path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_annual_replay_p4q_v1_0 as p4q
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_quality_momentum_p4g_v1_0 as p4g
import fund100_v6_crossasset_stress_diagnostic_v1_0 as c13

SCHEMA = "FUND100_P4R_ORIGINAL_SEC_QUALITY_126_SESSION_EVENT_STUDY_V5"
HORIZON = 126
# Fixed, predeclared relative-momentum window; no grid search or fitted threshold.
MOMENTUM_LOOKBACK = 126
SIDE_COSTS_BPS = (5, 15, 35)
HISTORICAL_PRICE_START = "2017-01-01"


class EventStudyStop(ValueError):
    pass


def _date(value: object) -> pd.Timestamp:
    if not isinstance(value, str):
        raise EventStudyStop("Missing dated SEC event")
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise EventStudyStop("Invalid SEC event date") from exc
    if d.strftime("%Y-%m-%d") != value:
        raise EventStudyStop("Noncanonical SEC event date")
    return pd.Timestamp(d)



def _prefiling_market_beta(data: pd.DataFrame, ticker: str,
                           first_i: int, pre_i: int) -> tuple[float | None, str]:
    """Ex-ante descriptive beta from the SAME 126 strictly pre-filing returns.

    Beta is NOT a hedge instruction: shorting, leverage, financing and
    executable prices are absent. Never estimate it using forward outcomes.
    """
    if first_i < 0:
        return None, "INSUFFICIENT_PREFILING_SESSIONS"
    stock = data[ticker].iloc[first_i:pre_i + 1].to_numpy(dtype=float)
    market = data["SPY"].iloc[first_i:pre_i + 1].to_numpy(dtype=float)
    if len(stock) != MOMENTUM_LOOKBACK + 1 or len(market) != len(stock):
        raise EventStudyStop("Incomplete pre-filing beta lookback")
    sr = stock[1:] / stock[:-1] - 1
    mr = market[1:] / market[:-1] - 1
    if not np.isfinite(sr).all() or not np.isfinite(mr).all():
        raise EventStudyStop("Nonfinite pre-filing beta returns")
    variance = float(np.var(mr, ddof=1))
    if variance <= 1e-12:
        return None, "PREFILING_MARKET_VARIANCE_UNIDENTIFIABLE"
    beta = float(np.cov(sr, mr, ddof=1)[0, 1] / variance)
    if not np.isfinite(beta):
        raise EventStudyStop("Invalid pre-filing market beta")
    return beta, "IDENTIFIABLE_PREFILING_126_SESSION_BETA"


def _beta_exposure_diagnostic(rows: list[dict]) -> dict:
    """Issuer-balanced beta and 15bp risk-adjusted P&L PROXY, not alpha.

    The beta-scaled benchmark subtraction is linear in cumulative returns,
    assumes zero cash carry, and is not an executable hedged portfolio.
    """
    cells = {}
    for momentum, name in ((True, "positive_momentum"),
                           (False, "nonpositive_momentum"),
                           (None, "unavailable_momentum")):
        for high, group in ((True, "quality_2_or_3"),
                            (False, "quality_0_or_1")):
            cohort = [r for r in rows
                      if r["pre_filing_relative_momentum_positive"] is momentum
                      and (r["quality_score"] >= 2) is high]
            usable = [r for r in cohort if r["prefiling_126_session_spy_beta"] is not None]
            by_issuer = {}
            for row in usable:
                by_issuer.setdefault(row["ticker"], []).append(row)
            issuer_betas = [
                float(np.mean([r["prefiling_126_session_spy_beta"] for r in items]))
                for items in by_issuer.values()
            ]
            issuer_proxies = [
                float(np.mean([r["beta_adjusted_15bps_proxy_pp"] for r in items]))
                for items in by_issuer.values()
            ]
            cells[f"{name}_{group}"] = {
                "events": len(cohort),
                "beta_identifiable_events": len(usable),
                "distinct_beta_identifiable_issuers": len(by_issuer),
                "event_mean_prefiling_beta": (
                    round(float(np.mean([r["prefiling_126_session_spy_beta"]
                                         for r in usable])), 6) if usable else None),
                "issuer_equal_mean_prefiling_beta": (
                    round(float(np.mean(issuer_betas)), 6) if issuer_betas else None),
                "issuer_equal_mean_beta_adjusted_15bps_proxy_pp": (
                    round(float(np.mean(issuer_proxies)), 6) if issuer_proxies else None),
                "fewer_than_five_issuers_not_stable": len(by_issuer) < 5,
            }
    return {
        "method": "STRICTLY_PREFILING_126_SESSION_SPY_BETA_AND_LINEAR_FORWARD_PNL_PROXY",
        "pre_filing_beta_uses_no_filing_day_or_forward_prices": True,
        "zero_cash_carry_and_unhedged_proxy_not_self_financing": True,
        "no_shorting_or_leverage_or_executable_hedge_implied": True,
        "no_significance_or_investable_alpha_inference": True,
        "by_quality_and_prior_momentum": cells,
    }


def _summarize(rows: list[dict], bps: int) -> dict:
    values = [r["cost_scenarios"][str(bps)]["stock_minus_spy_pp"] for r in rows]
    if not values:
        return {"events": 0, "distinct_issuers": 0,
                "mean_stock_minus_spy_pp": None, "median_stock_minus_spy_pp": None,
                "positive_relative_event_fraction": None}
    return {
        "events": len(rows),
        "distinct_issuers": len({r["ticker"] for r in rows}),
        "mean_stock_minus_spy_pp": round(float(np.mean(values)), 6),
        "median_stock_minus_spy_pp": round(float(np.median(values)), 6),
        "positive_relative_event_fraction": round(
            sum(x > 0 for x in values) / len(values), 6),
    }


def _issuer_balanced_sensitivity(rows: list[dict], bps: int) -> dict:
    """Descriptive issuer weighting and deletion sensitivity, NOT inference.

    Repeated annual outcomes from the same issuer and overlapping 126-session
    windows are dependent. Delete an issuer from BOTH score groups if it
    changes score; do not treat events as independent experimental units.
    """
    def issuer_means(group: list[dict]) -> dict[str, float]:
        by_ticker: dict[str, list[float]] = {}
        for row in group:
            by_ticker.setdefault(row["ticker"], []).append(
                row["cost_scenarios"][str(bps)]["stock_minus_spy_pp"])
        return {ticker: float(np.mean(values))
                for ticker, values in sorted(by_ticker.items())}

    low = issuer_means([r for r in rows if r["quality_score"] < 2])
    high = issuer_means([r for r in rows if r["quality_score"] >= 2])

    def group_report(means: dict[str, float]) -> dict:
        return {
            "distinct_issuers": len(means),
            "issuer_equal_weight_mean_stock_minus_spy_pp": (
                round(float(np.mean(list(means.values()))), 6) if means else None),
            "per_issuer_mean_stock_minus_spy_pp": {
                ticker: round(value, 6) for ticker, value in means.items()},
        }

    gap = (float(np.mean(list(high.values()))) -
           float(np.mean(list(low.values())))) if high and low else None
    leave_one_out = {}
    for ticker in sorted(set(high) | set(low)):
        remaining_high = [value for name, value in high.items() if name != ticker]
        remaining_low = [value for name, value in low.items() if name != ticker]
        if remaining_high and remaining_low:
            leave_one_out[ticker] = round(
                float(np.mean(remaining_high) - np.mean(remaining_low)), 6)
    return {
        "method": "ISSUER_EQUAL_WEIGHT_WITH_WHOLE_ISSUER_DELETION",
        "score_0_or_1": group_report(low),
        "score_2_or_3": group_report(high),
        "issuers_appearing_in_both_groups": sorted(set(high) & set(low)),
        "high_minus_low_issuer_balanced_pp": round(gap, 6) if gap is not None else None,
        "leave_one_issuer_out_gap_pp": leave_one_out,
        "leave_one_issuer_out_evaluable_exclusions": len(leave_one_out),
        "leave_one_issuer_out_gap_range_pp": (
            [min(leave_one_out.values()), max(leave_one_out.values())]
            if leave_one_out else None),
        "deletion_range_is_not_a_confidence_interval": True,
        "survivorship_and_overlapping_outcomes_preclude_alpha_inference": True,
    }


def _quality_momentum_interaction(rows: list[dict], bps: int) -> dict:
    """Fixed quality x prior relative momentum cells, descriptive only.

    The quality score and relative-momentum sign are measured before entry.
    Sparse cells, repeated issuers and retrospectively selected survivors
    preclude a predictive claim or a self-financing strategy simulation.
    """
    positive = [r for r in rows if r["pre_filing_relative_momentum_positive"] is True]
    nonpositive = [r for r in rows if r["pre_filing_relative_momentum_positive"] is False]
    unavailable = [r for r in rows if r["pre_filing_relative_momentum_positive"] is None]

    def describe(group: list[dict]) -> dict:
        return {
            "events": len(group),
            "distinct_issuers": len({r["ticker"] for r in group}),
            "score_0_or_1": _summarize(
                [r for r in group if r["quality_score"] < 2], bps),
            "score_2_or_3": _summarize(
                [r for r in group if r["quality_score"] >= 2], bps),
            "issuer_balanced_sensitivity": _issuer_balanced_sensitivity(group, bps),
        }

    return {
        "method": "FIXED_126_SESSION_PRE_FILING_STOCK_MINUS_SPY_SIGN_X_SEC_QUALITY",
        "positive_relative_momentum": describe(positive),
        "nonpositive_relative_momentum": describe(nonpositive),
        "unavailable_lookback_events": len(unavailable),
        "all_completed_events_accounted": (
            len(positive) + len(nonpositive) + len(unavailable) == len(rows)),
        "momentum_uses_only_closes_strictly_before_filing_day": True,
        "zero_relative_momentum_classified_nonpositive": True,
        "no_threshold_search_or_fitted_allocation": True,
        "no_independent_alpha_or_statistical_significance_claim": True,
    }



def _capacity_constrained_replay(rows: list[dict], data: pd.DataFrame,
                                 cost_bps: int, *,
                                 cash_annual_rate: pd.Series | None = None) -> dict:
    """Cash-funded, paired-SPY overlapping SEC-event stress test; NOT alpha.

    Use only completed original events and stop 126 sessions before the
    source end so right-censored signals cannot influence admissions.
    At the first close AFTER filing, buy one of six unlevered slots.
    Mark only subsequent returns, exit after 126 sessions, charge each
    traded side and liquidate remaining positions at the evaluation cutoff.
    The matched SPY control buys the same dollars on the same dates.
    Optional cash earns the PREVIOUS session's lagged annual-rate proxy over
    actual elapsed calendar days; neither proxy nor stock universe is alpha.
    """
    if type(cost_bps) is not int or cost_bps not in SIDE_COSTS_BPS:
        raise EventStudyStop("Unregistered replay cost scenario")
    if len(data) < 2 * HORIZON + 2 or p4l.MAX_NAMES != 6:
        raise EventStudyStop("Insufficient maturity buffer or changed slot cap")
    cutoff = len(data) - HORIZON - 1
    if cash_annual_rate is None:
        annual_rates = np.zeros(len(data), dtype=float)
    else:
        if (not isinstance(cash_annual_rate, pd.Series)
            or not cash_annual_rate.index.equals(data.index)
            or not pd.api.types.is_numeric_dtype(cash_annual_rate)):
            raise EventStudyStop("Cash-rate proxy must align to every price session")
        annual_rates = cash_annual_rate.to_numpy(dtype=float)
        if (not np.isfinite(annual_rates).all() or (annual_rates < 0).any()
            or (annual_rates > 25).any()):
            raise EventStudyStop("Invalid annual cash-rate proxy")
    candidates = []
    for row in rows:
        try:
            ticker = row["ticker"]
            entry = _date(row["entry_next_session_close"])
            exit_day = _date(row["exit_126_sessions_later"])
            entry_i = int(data.index.get_loc(entry))
            exit_i = int(data.index.get_loc(exit_day))
            score = row["quality_score"]
            momentum = row["pre_filing_relative_momentum_positive"]
            accession = row["original_10k_accession"]
        except (KeyError, TypeError, ValueError) as exc:
            raise EventStudyStop("Malformed dated SEC replay event") from exc
        if (ticker not in p4n.SOURCE_MATCHED_TAGS or type(score) is not int
            or score not in range(4) or momentum not in (True, False, None)
            or type(accession) is not str or not accession
            or exit_i - entry_i != HORIZON):
            raise EventStudyStop("Invalid causal replay event contract")
        if score >= 2 and momentum is True and entry_i < cutoff:
            prior = row["pre_filing_126_session_stock_minus_spy_pp"]
            if type(prior) not in (float, int) or not np.isfinite(prior) or prior <= 0:
                raise EventStudyStop("Missing positive pre-filing momentum")
            candidates.append((entry_i, -float(prior), ticker, accession, exit_i))
    candidates.sort()
    if len(set((a, c, d) for a, _, c, d, _ in candidates)) != len(candidates):
        raise EventStudyStop("Duplicate accession event at replay entry")

    fee = cost_bps / 10000
    cash_stock = cash_spy = 1.0
    # ticker -> (scheduled exit index, stock shares, SPY shares)
    positions: dict[str, tuple[int, float, float]] = {}
    admitted = blocked_capacity = blocked_same_issuer = terminal_exits = 0
    admission_schedule = []
    traded_stock = traded_spy = 0.0
    peak_concurrent = active_sessions = 0
    gross_exposure_sum = 0.0
    nav_stock, nav_spy = [], []
    event_cursor = 0
    spy = data["SPY"].to_numpy(dtype=float)
    stock = {ticker: data[ticker].to_numpy(dtype=float)
             for ticker in {r[2] for r in candidates}}

    for t in range(cutoff + 1):
        if t:
            days = (data.index[t] - data.index[t - 1]).days
            if days <= 0:
                raise EventStudyStop("Nonpositive cash accrual interval")
            # Both paired portfolios earn identical ex-ante cash carry,
            # on cash only, before this close's exits and new entries.
            factor = float(np.exp(annual_rates[t - 1] / 100 * days / 365.25))
            cash_stock *= factor
            cash_spy *= factor
        for ticker, (exit_i, stock_units, spy_units) in sorted(list(positions.items())):
            if exit_i <= t or t == cutoff:
                stock_proceeds = stock_units * stock[ticker][t]
                spy_proceeds = spy_units * spy[t]
                cash_stock += stock_proceeds * (1 - fee)
                cash_spy += spy_proceeds * (1 - fee)
                traded_stock += stock_proceeds
                traded_spy += spy_proceeds
                terminal_exits += int(t == cutoff and exit_i > t)
                del positions[ticker]

        while event_cursor < len(candidates) and candidates[event_cursor][0] == t:
            _, _, ticker, _, exit_i = candidates[event_cursor]
            event_cursor += 1
            if ticker in positions:
                blocked_same_issuer += 1
                continue
            if len(positions) >= 6:
                blocked_capacity += 1
                continue
            equity_stock = cash_stock + sum(
                units * stock[name][t] for name, (_, units, _) in positions.items())
            equity_spy = cash_spy + sum(
                units * spy[t] for _, (_, _, units) in positions.items())
            notional = min(equity_stock / 6, equity_spy / 6,
                           cash_stock / (1 + fee), cash_spy / (1 + fee))
            if not np.isfinite(notional) or notional <= 1e-12:
                blocked_capacity += 1
                continue
            cash_stock -= notional * (1 + fee)
            cash_spy -= notional * (1 + fee)
            traded_stock += notional
            traded_spy += notional
            positions[ticker] = (exit_i, notional / stock[ticker][t],
                                 notional / spy[t])
            admission_schedule.append({
                "ticker": ticker,
                "entry_close": data.index[t].date().isoformat(),
                "exit_close": data.index[exit_i].date().isoformat(),
            })
            admitted += 1

        held_stock = sum(
            units * stock[name][t] for name, (_, units, _) in positions.items())
        held_spy = sum(units * spy[t] for _, (_, _, units) in positions.items())
        equity_stock, equity_spy = cash_stock + held_stock, cash_spy + held_spy
        if (not np.isfinite([equity_stock, equity_spy, cash_stock, cash_spy]).all()
            or min(equity_stock, equity_spy) <= 0
            or min(cash_stock, cash_spy) < -1e-10
            or held_stock > equity_stock * (1 + 1e-10)
            or held_spy > equity_spy * (1 + 1e-10)):
            raise EventStudyStop("Non-self-financing research replay")
        peak_concurrent = max(peak_concurrent, len(positions))
        active_sessions += bool(positions)
        gross_exposure_sum += held_stock / equity_stock
        nav_stock.append(equity_stock)
        nav_spy.append(equity_spy)
    if admitted + blocked_capacity + blocked_same_issuer != len(candidates):
        raise EventStudyStop("Unreconciled original replay admissions")

    def metrics(path: list[float]) -> dict:
        values = np.asarray(path, dtype=float)
        years = (data.index[cutoff] - data.index[0]).days / 365.25
        return {
            "terminal_nav": round(float(values[-1]), 6),
            "net_cagr_pct": round(100 * (float(values[-1]) ** (1 / years) - 1), 6),
            "max_drawdown_pct": round(
                100 * float(np.min(values / np.maximum.accumulate(values) - 1)), 6),
        }
    stock_metrics, spy_metrics = metrics(nav_stock), metrics(nav_spy)
    return {
        "method": "SIX_SLOT_CASH_FUNDED_ORIGINAL_EVENT_CLOSE_REPLAY_WITH_PAIRED_SPY",
        "cost_per_traded_side_bps": cost_bps,
        "first_session": data.index[0].date().isoformat(),
        "last_session_maturity_cutoff": data.index[cutoff].date().isoformat(),
        "maturity_buffer_sessions": HORIZON,
        "eligible_high_quality_positive_prior_momentum_events": len(candidates),
        "admitted_events": admitted,
        "admission_schedule": admission_schedule,
        "blocked_by_six_slot_capacity": blocked_capacity,
        "blocked_by_same_issuer_overlap": blocked_same_issuer,
        "forced_terminal_liquidations": terminal_exits,
        "peak_concurrent_positions": peak_concurrent,
        "sessions_with_positions": active_sessions,
        "average_gross_stock_exposure_fraction": round(
            gross_exposure_sum / (cutoff + 1), 6),
        "stock": stock_metrics,
        "same_entry_dollar_matched_spy": spy_metrics,
        "stock_minus_paired_spy_terminal_wealth_pp": round(
            100 * (nav_stock[-1] - nav_spy[-1]), 6),
        "stock_minus_paired_spy_cagr_pp": round(
            stock_metrics["net_cagr_pct"] - spy_metrics["net_cagr_pct"], 6),
        "stock_total_traded_notional_per_initial_nav": round(traded_stock, 6),
        "spy_total_traded_notional_per_initial_nav": round(traded_spy, 6),
        "paired_control_uses_identical_admissions_and_dollar_entries": True,
        "entry_after_original_filing_and_next_session_return_only": True,
        "terminal_liquidation_charged_both_sides": True,
        "cash_yield_assumed_zero_not_a_historical_bill_benchmark":
            cash_annual_rate is None,
        "cash_accrual_uses_prior_session_rate_and_actual_calendar_days": True,
        "cash_yield_proxy_is_not_achievable_broker_cash_rate": True,
        "2026_survivor_universe_and_revisable_prices_not_investable_alpha": True,
        "no_broker_or_trading_authority": True,
    }



def _spy_idle_capital_overlay(admissions: list[dict], data: pd.DataFrame,
                              cost_bps: int) -> dict:
    """Research-only self-financing stock replacement of a passive SPY core.

    Reuse EXACT admissions from the existing six-slot SEC replay. When a
    signal arrives, sell enough SPY at the signal's next-close entry to buy
    up to one-sixth of NAV in the stock. Reinvest exits in SPY. Charge both
    sides of every actual ETF/stock trade. Passive comparator buys SPY once
    and sells at the same 126-session maturity cutoff. No cash carry,
    borrowing, shorts, intraday price claims or live order capability.
    """
    if type(cost_bps) is not int or cost_bps not in SIDE_COSTS_BPS:
        raise EventStudyStop("Unregistered SPY-overlay transaction cost")
    cutoff = len(data) - HORIZON - 1
    if cutoff <= 0 or "SPY" not in data:
        raise EventStudyStop("Incomplete SPY-overlay price history")
    fee = cost_bps / 10000
    spy = data["SPY"].to_numpy(dtype=float)
    if not np.isfinite(spy).all() or (spy <= 0).any():
        raise EventStudyStop("Invalid SPY-overlay benchmark prices")
    entries: dict[int, list[tuple[str, int]]] = {}
    seen = set()
    for event in admissions:
        try:
            ticker = event["ticker"]
            entry_i = int(data.index.get_loc(_date(event["entry_close"])))
            exit_i = int(data.index.get_loc(_date(event["exit_close"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise EventStudyStop("Malformed SPY-overlay admission") from exc
        if (ticker not in p4n.SOURCE_MATCHED_TAGS or ticker not in data
            or entry_i >= cutoff or exit_i - entry_i != HORIZON
            or (ticker, entry_i) in seen):
            raise EventStudyStop("Invalid SPY-overlay admission chronology")
        seen.add((ticker, entry_i))
        entries.setdefault(entry_i, []).append((ticker, exit_i))
    for day in entries:
        entries[day].sort()

    # The passive and stock-replacement portfolios pay identical initial
    # SPY entry and terminal exit costs. Only replacement incurs churn.
    passive_units = 1.0 / (spy[0] * (1 + fee))
    spy_units = passive_units
    cash = 0.0
    stocks: dict[str, tuple[int, float]] = {}
    nav_overlay, nav_passive = [], []
    traded_spy = 1.0 / (1 + fee)
    traded_stocks = 0.0
    peak_slots = filled = forced_exits = 0
    stock_fraction_sum = 0.0

    for t in range(cutoff + 1):
        for ticker, (exit_i, units) in sorted(list(stocks.items())):
            if exit_i <= t or t == cutoff:
                proceeds = units * float(data[ticker].iloc[t])
                traded_stocks += proceeds
                cash += proceeds * (1 - fee)
                forced_exits += int(t == cutoff and exit_i > t)
                del stocks[ticker]

        if t < cutoff:
            for ticker, exit_i in entries.get(t, []):
                if ticker in stocks or len(stocks) >= 6:
                    raise EventStudyStop("SPY-overlay admission diverged from paired replay")
                held = sum(units * float(data[name].iloc[t])
                           for name, (_, units) in stocks.items())
                nav = cash + spy_units * spy[t] + held
                # Fund the purchase by SPY sales, never leverage. For six
                # simultaneous entries, the last allocation absorbs fees.
                spendable = cash + spy_units * spy[t] * (1 - fee)
                notional = min(nav / 6, spendable / (1 + fee))
                if not np.isfinite(notional) or notional <= 1e-12:
                    raise EventStudyStop("Unfunded SPY-overlay admission")
                need = max(0.0, notional * (1 + fee) - cash)
                if need:
                    gross_sale = need / (1 - fee)
                    if gross_sale > spy_units * spy[t] + 1e-10:
                        raise EventStudyStop("SPY-overlay sale exceeds holdings")
                    spy_units -= gross_sale / spy[t]
                    traded_spy += gross_sale
                    cash += gross_sale * (1 - fee)
                cash -= notional * (1 + fee)
                if cash < -1e-10:
                    raise EventStudyStop("Negative cash in SPY-overlay entry")
                cash = max(0.0, cash)
                stocks[ticker] = (exit_i, notional / float(data[ticker].iloc[t]))
                traded_stocks += notional
                filled += 1
            # Reinvest released capital in SPY, not an unmodelled free cash
            # balance. A closing trade earns its first return next session.
            if cash > 1e-12:
                buy = cash / (1 + fee)
                spy_units += buy / spy[t]
                traded_spy += buy
                cash = 0.0
        else:
            # Identical terminal horizon and two-sided friction on passive
            # SPY and on every remaining overlay asset.
            cash += spy_units * spy[t] * (1 - fee)
            traded_spy += spy_units * spy[t]
            spy_units = 0.0

        held_stock = sum(units * float(data[name].iloc[t])
                         for name, (_, units) in stocks.items())
        nav = cash + spy_units * spy[t] + held_stock
        passive = passive_units * spy[t] * (1 - fee if t == cutoff else 1)
        if (not np.isfinite([nav, passive, cash, spy_units]).all()
            or min(nav, passive) <= 0 or cash < -1e-10
            or spy_units < -1e-10 or held_stock > nav * (1 + 1e-10)):
            raise EventStudyStop("Non-self-financing SPY-overlay research")
        stock_fraction_sum += held_stock / nav
        peak_slots = max(peak_slots, len(stocks))
        nav_overlay.append(nav)
        nav_passive.append(passive)
    if filled != len(admissions) or stocks or spy_units != 0:
        raise EventStudyStop("Unreconciled SPY-overlay admissions or terminal assets")

    def metrics(path: list[float]) -> dict:
        values = np.asarray(path, dtype=float)
        years = (data.index[cutoff] - data.index[0]).days / 365.25
        return {
            "terminal_nav": round(float(values[-1]), 6),
            "net_cagr_pct": round(100 * (float(values[-1]) ** (1 / years) - 1), 6),
            "max_drawdown_pct": round(
                100 * float(np.min(values / np.maximum.accumulate(values) - 1)), 6),
        }

    selected, passive = metrics(nav_overlay), metrics(nav_passive)
    return {
        "method": "EXACT_SIX_SLOT_ADMISSIONS_SPY_FUNDED_STOCK_REPLACEMENT",
        "cost_per_traded_side_bps": cost_bps,
        "first_session": data.index[0].date().isoformat(),
        "last_session_maturity_cutoff": data.index[cutoff].date().isoformat(),
        "admitted_events": filled,
        "peak_concurrent_positions": peak_slots,
        "forced_terminal_stock_exits": forced_exits,
        "average_stock_exposure_fraction": round(
            stock_fraction_sum / (cutoff + 1), 6),
        "stock_replacement_plus_spy_core": selected,
        "passive_buy_and_hold_spy": passive,
        "replacement_minus_passive_cagr_pp": round(
            selected["net_cagr_pct"] - passive["net_cagr_pct"], 6),
        "replacement_minus_passive_terminal_wealth_pp": round(
            100 * (nav_overlay[-1] - nav_passive[-1]), 6),
        "overlay_spy_traded_notional_per_initial_nav": round(traded_spy, 6),
        "overlay_stock_traded_notional_per_initial_nav": round(traded_stocks, 6),
        "no_signals_equals_identical_passive_spy": filled == 0,
        "passive_and_overlay_pay_same_initial_and_final_spy_fees": True,
        "all_spy_to_stock_and_stock_to_spy_switches_costed": True,
        "original_admissions_reused_without_refitting_thresholds": True,
        "not_a_validated_point_in_time_survivorship_free_strategy": True,
        "not_risk_matched_to_low_equity_cash_portfolio": True,
        "research_only_no_broker_or_live_authority": True,
    }



def _overlay_fixed_admission_issuer_deletion(
        admissions: list[dict], data: pd.DataFrame,
        cost_bps: int, baseline: dict) -> dict:
    """Stress-test the 15bp SPY-funded result against whole-issuer deletion.

    Remove each issuer's ALREADY ADMITTED events, leave its allocation in
    SPY, and replay the same historical prices and transaction costs.
    Crucially, do NOT re-run signal selection or admit a replacement for
    a removed issuer: this is a retrospective concentration diagnostic,
    not a portfolio a trader could have chosen with historical foresight.
    """
    if (cost_bps != 15 or baseline.get("cost_per_traded_side_bps") != cost_bps
        or baseline.get("admitted_events") != len(admissions)
        or baseline.get("method") !=
            "EXACT_SIX_SLOT_ADMISSIONS_SPY_FUNDED_STOCK_REPLACEMENT"):
        raise EventStudyStop("Mismatched issuer-deletion overlay baseline")
    issuers = sorted({row["ticker"] for row in admissions})
    deletions = {}
    for ticker in issuers:
        retained = [row for row in admissions if row["ticker"] != ticker]
        omitted = len(admissions) - len(retained)
        if omitted <= 0:
            raise EventStudyStop("Issuer deletion removed no admissions")
        result = _spy_idle_capital_overlay(retained, data, cost_bps)
        if (result["admitted_events"] != len(retained)
            or result["passive_buy_and_hold_spy"] !=
               baseline["passive_buy_and_hold_spy"]):
            raise EventStudyStop("Issuer deletion changed passive benchmark")
        deletions[ticker] = {
            "removed_admitted_events": omitted,
            "remaining_admitted_events": len(retained),
            "replacement_minus_passive_cagr_pp":
                result["replacement_minus_passive_cagr_pp"],
            "replacement_minus_passive_terminal_wealth_pp":
                result["replacement_minus_passive_terminal_wealth_pp"],
            "overlay_max_drawdown_pct":
                result["stock_replacement_plus_spy_core"]["max_drawdown_pct"],
            "change_from_all_issuers_cagr_pp": round(
                result["replacement_minus_passive_cagr_pp"] -
                baseline["replacement_minus_passive_cagr_pp"], 6),
        }
    excess = [row["replacement_minus_passive_cagr_pp"]
              for row in deletions.values()]
    return {
        "method": "FIXED_ADMISSIONS_WHOLE_ISSUER_DELETION_SPY_FUNDED_15BPS",
        "cost_per_traded_side_bps": cost_bps,
        "all_issuers_admitted_events": len(admissions),
        "all_issuers_baseline_cagr_advantage_pp":
            baseline["replacement_minus_passive_cagr_pp"],
        "distinct_admitted_issuers": len(issuers),
        "per_excluded_issuer": deletions,
        "exclusion_advantage_range_pp":
            [min(excess), max(excess)] if excess else None,
        "exclusions_with_positive_cagr_advantage":
            sum(x > 0 for x in excess),
        "exclusions_with_nonpositive_cagr_advantage":
            sum(x <= 0 for x in excess),
        "removed_positions_remain_in_spy_no_replacement_signals": True,
        "identical_passive_spy_benchmark_and_transaction_costs": True,
        "retrospective_deletion_not_investable_issuer_selection": True,
        "survivor_universe_and_revisable_prices_preclude_alpha": True,
        "not_a_confidence_interval_or_independent_holdout": True,
        "research_only_no_broker_or_live_authority": True,
    }


def analyze(annual: dict, prices: pd.DataFrame, *,
            acquired_at_utc: str, source_sha256: str,
            cash_rates: pd.DataFrame | None = None) -> dict:
    """Pure deterministic event-return study; caller authenticates SEC archive."""
    try:
        data = p4l.validate_prices(prices)
    except p4l.BroadStockStop as exc:
        raise EventStudyStop("Incomplete original market price history") from exc
    if hashlib.sha256(p4l.canonical_csv(data).encode()).hexdigest() != source_sha256:
        raise EventStudyStop("Original market source fingerprint mismatch")
    try:
        capture = datetime.strptime(acquired_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        sec_capture = datetime.strptime(
            annual["source_acquisition_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as exc:
        raise EventStudyStop("Noncanonical acquisition clocks") from exc
    if (capture.strftime("%Y-%m-%dT%H:%M:%SZ") != acquired_at_utc
        or sec_capture.strftime("%Y-%m-%dT%H:%M:%SZ") != annual["source_acquisition_utc"]
        or data.index[-1].date() >= capture.date()
        or data.index[-1].date() > sec_capture.date()
        or len(data) < 2 * HORIZON
        or data.index[0].date().isoformat() > "2018-01-01"):
        raise EventStudyStop("Incomplete historical window or future price source")
    if (annual.get("schema") != p4q.SCHEMA
        or annual.get("new_issuers_verified") != 16
        or annual.get("industrial_issuer_chronologies") != 12
        or annual.get("original_accession_and_filed_day_used") is not True
        or annual.get("today_retrieved_companyfacts_not_original_historical_capture") is not True
        or annual.get("issuer_roster_selected_with_2026_knowledge") is not True
        or annual.get("historical_investable_backtest_eligible") is not False
        or annual.get("independent_alpha_validated") is not False
        or annual.get("trading_authorized") is not False
        or annual.get("paper_authorized") is not False
        or annual.get("live_authorized") is not False
        or annual.get("broker_orders") != 0):
        raise EventStudyStop("Unverified or executable SEC replay")
    observations = annual.get("observations")
    if (not isinstance(observations, list) or len(observations) != 16
        or {r["ticker"] for r in observations} !=
           (set(p4l.SECTORS) - set(p4g.FROZEN_P4E_SCORES))):
        raise EventStudyStop("SEC issuer roster mismatch")
    if (sum(r["available_score_count"] for r in observations) != annual["industrial_annual_scores_available"]
        or sum(r["annual_filing_dates_reviewed"] for r in observations) != annual["industrial_annual_filing_dates_reviewed"]):
        raise EventStudyStop("SEC event-to-outcome accounting failed")
    rows = []
    missing = 0
    right_censored = 0
    no_entry = 0
    left_censored = 0
    not_new_accession_events = 0
    for issuer in sorted(observations, key=lambda r: r["ticker"]):
        ticker = issuer["ticker"]
        if ticker not in p4n.SOURCE_MATCHED_TAGS:
            if issuer["annual_events"] or issuer["available_score_count"] != 0:
                raise EventStudyStop("Sector-specific scores cannot be pooled")
            continue
        events = issuer["annual_events"]
        if (len(events) != issuer["annual_filing_dates_reviewed"]
            or sum(e["score"] is not None for e in events) != issuer["available_score_count"]):
            raise EventStudyStop("SEC event counts inconsistent")
        last_day = None
        for event in events:
            day = _date(event["asof_conservative_available_date"])
            if ((last_day is not None and day <= last_day)
                or day.date() > sec_capture.date()):
                raise EventStudyStop("SEC filing chronology or availability mismatch")
            last_day = day
            # P4Q enumerates all original 10-K filing dates. Its as-of
            # quality evaluator can still reference a PREVIOUS accession
            # when the newly filed 10-K has an older fiscal end or lacks
            # the issuer-specific facts. That is NOT a new score signal.
            # Only a score whose OWN source accession becomes available
            # on this event day is eligible for a forward outcome.
            available = event["source_10k_available_date"]
            if available is None:
                not_new_accession_events += 1
                continue
            source_day = _date(available)
            if source_day > day:
                raise EventStudyStop("Future SEC accession leaked into event")
            if source_day < day:
                not_new_accession_events += 1
                continue
            score = event["score"]
            if score is None:
                missing += 1
                continue
            if (type(score) is not int or score not in (0, 1, 2, 3)
                or event["state"] != "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY"
                or not event["same_accession_comparative"]
                or not event["source_10k_accession"]):
                raise EventStudyStop("Invalid original SEC quality evidence")
            if day < data.index[0]:
                left_censored += 1
                continue
            # Use the first close strictly AFTER the conservative filing day.
            # This cannot buy on the filing-day close or a prior close.
            entry_i = int(data.index.searchsorted(day, side="right"))
            if entry_i >= len(data):
                no_entry += 1
                continue
            exit_i = entry_i + HORIZON
            if exit_i >= len(data):
                right_censored += 1
                continue
            # Use the last COMPLETED close strictly before the filing day,
            # never the filing-day close, post-filing price, or forward outcome.
            pre_i = int(data.index.searchsorted(day, side="left")) - 1
            first_i = pre_i - MOMENTUM_LOOKBACK
            if first_i < 0:
                prior_momentum_pp = None
                prior_momentum_positive = None
                momentum_first_close = None
                momentum_last_close = None
            else:
                prior_momentum_pp_raw = 100 * (
                    float(data[ticker].iloc[pre_i] / data[ticker].iloc[first_i])
                    - float(data["SPY"].iloc[pre_i] / data["SPY"].iloc[first_i]))
                prior_momentum_pp = round(prior_momentum_pp_raw, 6)
                prior_momentum_positive = bool(prior_momentum_pp_raw > 0)
                momentum_first_close = data.index[first_i].date().isoformat()
                momentum_last_close = data.index[pre_i].date().isoformat()
            beta, beta_status = _prefiling_market_beta(data, ticker, first_i, pre_i)
            stock_gross = float(data[ticker].iloc[exit_i] / data[ticker].iloc[entry_i])
            spy_gross = float(data["SPY"].iloc[exit_i] / data["SPY"].iloc[entry_i])
            costs = {}
            for bps in SIDE_COSTS_BPS:
                factor = (1 - bps / 10000) ** 2
                costs[str(bps)] = {
                    "stock_net_return_pct": round(100 * (stock_gross * factor - 1), 6),
                    "spy_net_return_pct": round(100 * (spy_gross * factor - 1), 6),
                    "stock_minus_spy_pp": round(
                        100 * (stock_gross - spy_gross) * factor, 6),
                }
            rows.append({
                "ticker": ticker, "original_10k_accession": event["source_10k_accession"],
                "quality_score": score,
                "pre_filing_126_session_stock_minus_spy_pp": prior_momentum_pp,
                "pre_filing_relative_momentum_positive": prior_momentum_positive,
                "pre_filing_momentum_first_close": momentum_first_close,
                "pre_filing_momentum_last_close": momentum_last_close,
                "prefiling_126_session_spy_beta": (
                    round(beta, 6) if beta is not None else None),
                "prefiling_market_beta_status": beta_status,
                "beta_adjusted_15bps_proxy_pp": (
                    round(100 * (stock_gross * (1 - 15 / 10000) ** 2 - 1
                                 - beta * (spy_gross - 1)), 6)
                    if beta is not None else None),
                "conservative_available_date": day.date().isoformat(),
                "entry_next_session_close": data.index[entry_i].date().isoformat(),
                "exit_126_sessions_later": data.index[exit_i].date().isoformat(),
                "stock_gross_return_pct": round(100 * (stock_gross - 1), 6),
                "spy_matched_gross_return_pct": round(100 * (spy_gross - 1), 6),
                "cost_scenarios": costs,
            })
    if len(rows) + missing + right_censored + no_entry + left_censored + not_new_accession_events != annual["industrial_annual_scores_available"] + (
        annual["industrial_annual_filing_dates_reviewed"] -
        annual["industrial_annual_scores_available"]):
        raise EventStudyStop("SEC event-to-outcome accounting failed")
    groups = {}
    for bps in SIDE_COSTS_BPS:
        groups[str(bps)] = {
            "all_scored": _summarize(rows, bps),
            "score_0_or_1": _summarize([r for r in rows if r["quality_score"] < 2], bps),
            "score_2_or_3": _summarize([r for r in rows if r["quality_score"] >= 2], bps),
        }
    # Preserve the exact zero-carry P4R baseline; add the same interest
    # proxy to BOTH stock and SPY control, not just the selected stocks.
    zero_replays = {
        str(bps): _capacity_constrained_replay(rows, data, bps)
        for bps in SIDE_COSTS_BPS
    }
    spy_overlay = {
        str(bps): _spy_idle_capital_overlay(
            zero_replays[str(bps)]["admission_schedule"], data, bps)
        for bps in SIDE_COSTS_BPS
    }
    cash_sensitivity: dict[str, dict] = {}
    cash_source_sha = None
    if cash_rates is not None:
        if not isinstance(cash_rates, pd.DataFrame):
            raise EventStudyStop("Cash-rate source must be a dated frame")
        rates_source = cash_rates.loc["2013-12-01":data.index[-1]].copy()
        try:
            lagged_discount = c13.validate_cash_rates(rates_source, data.index)
        except (c13.CrossAssetStop, KeyError, TypeError, ValueError) as exc:
            raise EventStudyStop("Incomplete original cash-rate proxy") from exc
        cash_source_sha = hashlib.sha256(
            c13.canonical_cash_rates(rates_source).encode()).hexdigest()
        # ^IRX is a 13-week discount quote, NOT an executable bill return.
        # Conversion and three-weekday observation lag reuse the reviewed
        # C13 original-source convention, without fitting parameters.
        gross = (lagged_discount * 365 /
                 (360 - lagged_discount * 91 / 100)).clip(lower=0)
        scenarios = {
            "IRX_MINUS_50BP": (gross - .5).clip(lower=0),
            "IRX_GROSS": gross,
        }
        for bps in SIDE_COSTS_BPS:
            cash_sensitivity[str(bps)] = {}
            for label, annual_rate in scenarios.items():
                replay = _capacity_constrained_replay(
                    rows, data, bps, cash_annual_rate=annual_rate)
                baseline = zero_replays[str(bps)]
                cash_sensitivity[str(bps)][label] = {
                    **replay,
                    "stock_cagr_minus_zero_cash_pp": round(
                        replay["stock"]["net_cagr_pct"] -
                        baseline["stock"]["net_cagr_pct"], 6),
                    "matched_spy_cagr_minus_zero_cash_pp": round(
                        replay["same_entry_dollar_matched_spy"]["net_cagr_pct"] -
                        baseline["same_entry_dollar_matched_spy"]["net_cagr_pct"], 6),
                    "stock_minus_spy_cagr_change_from_zero_cash_pp": round(
                        replay["stock_minus_paired_spy_cagr_pp"] -
                        baseline["stock_minus_paired_spy_cagr_pp"], 6),
                }
    return {
        "schema": SCHEMA,
        "status": "HINDSIGHT_SURVIVOR_EVENT_STUDY_NOT_VALIDATED_ALPHA",
        "source_sec_capture_utc": annual["source_acquisition_utc"],
        "source_sec_manifest_sha256": annual["original_p4n_manifest_sha256"],
        "source_prices_capture_utc": acquired_at_utc,
        "source_prices_canonical_csv_sha256": source_sha256,
        "source_first_price_session": data.index[0].date().isoformat(),
        "source_last_price_session": data.index[-1].date().isoformat(),
        "predeclared_forward_sessions": HORIZON,
        "predeclared_pre_filing_momentum_sessions": MOMENTUM_LOOKBACK,
        "pre_filing_momentum_threshold_pp": 0,
        "cost_per_side_bps": list(SIDE_COSTS_BPS),
        "original_annual_scores": annual["industrial_annual_scores_available"],
        "missing_original_annual_scores": missing,
        "right_censored_eligible_scores": right_censored,
        "scores_without_future_entry_close": no_entry,
        "left_censored_eligible_scores": left_censored,
        "nonnew_or_unavailable_source_accession_events": not_new_accession_events,
        "completed_event_returns": len(rows),
        "summary": groups,
        "prefiling_market_beta_risk_diagnostic": _beta_exposure_diagnostic(rows),
        "issuer_balanced_sensitivity": {
            str(bps): _issuer_balanced_sensitivity(rows, bps)
            for bps in SIDE_COSTS_BPS
        },
        "quality_by_pre_filing_relative_momentum": {
            str(bps): _quality_momentum_interaction(rows, bps)
            for bps in SIDE_COSTS_BPS
        },
        "missing_pre_filing_momentum_lookback_events": sum(
            r["pre_filing_relative_momentum_positive"] is None for r in rows),
        "event_returns": rows,
        "costed_six_slot_overlap_replay": zero_replays,
        "costed_six_slot_spy_idle_capital_overlay": spy_overlay,
        "spy_overlay_fixed_admission_issuer_deletion_15bps":
            _overlay_fixed_admission_issuer_deletion(
                zero_replays["15"]["admission_schedule"], data, 15,
                spy_overlay["15"]),
        "costed_six_slot_cash_carry_sensitivity": cash_sensitivity,
        "cash_rate_source": ("YAHOO_IRX_13W_BILL_DISCOUNT_PROXY"
                             if cash_source_sha is not None else None),
        "cash_rate_source_canonical_sha256": cash_source_sha,
        "cash_rate_lag_weekdays": (c13.CASH_RATE_LAG_WEEKDAYS
                                   if cash_source_sha is not None else None),
        "cash_rate_is_revisable_vendor_quote_not_archived_historical_vintage": True,
        "cash_rate_not_actual_broker_interest_or_executable_rolled_bill": True,
        "zero_cash_baseline_preserved": True,
        "capacity_replay_is_hindsight_survivor_stress_not_alpha": True,
        "event_returns_are_overlapping_and_not_independent": True,
        "beta_adjusted_proxy_is_not_a_hedged_trade_or_alpha": True,
        "retrospectively_selected_2026_survivors": True,
        "SEC_facts_retrieved_today_not_historical_vintages": True,
        "vendor_adjusted_prices_revisable_and_corporate_actions_not_independently_verified": True,
        "delistings_and_historical_membership_missing": True,
        "no_point_in_time_investable_backtest": True,
        "not_a_self_financing_portfolio_or_validated_alpha": True,
        "no_valuation_or_cross_sector_quality_model": True,
        "research_only": True, "trading_authorized": False,
        "paper_authorized": False, "live_authorized": False,
        "broker_requests": 0, "broker_orders": 0,
    }


def evaluate(source_dir: Path, prices: pd.DataFrame, *,
             acquired_at_utc: str, cash_rates: pd.DataFrame | None = None) -> dict:
    """Require P4Q's original SEC file/hash verification before joining prices."""
    annual = p4q.evaluate(source_dir)
    digest = hashlib.sha256(p4l.canonical_csv(prices).encode()).hexdigest()
    return analyze(annual, prices, acquired_at_utc=acquired_at_utc,
                   source_sha256=digest, cash_rates=cash_rates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-prices-csv", type=Path, required=True)
    parser.add_argument("--output-rates-csv", type=Path, required=True)
    args = parser.parse_args()
    prices = p4l.public_prices(start=HISTORICAL_PRICE_START)
    p4g.verify_original_nyse_source_sessions(prices.index)
    # Fetch historical USD short-bill quotes separately from stock prices.
    # This is research-only; a quote is not an achievable deposit yield.
    import yfinance as yf
    raw = yf.download(tickers=["^IRX"], start="2013-12-01",
                      end=datetime.now(timezone.utc).date().isoformat(),
                      auto_adjust=True, interval="1d", actions=False,
                      progress=False, threads=False)
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise EventStudyStop("Missing original vendor bill-rate source")
    if ("Close", "^IRX") in raw.columns:
        irx = raw[("Close", "^IRX")]
    elif "Close" in raw.columns and not isinstance(raw.columns, pd.MultiIndex):
        irx = raw["Close"]
    else:
        raise EventStudyStop("Missing original ^IRX discount-yield column")
    irx = irx.dropna()
    if irx.empty:
        raise EventStudyStop("Empty original ^IRX source")
    if irx.index.tz is not None:
        irx.index = irx.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        irx.index = irx.index.normalize()
    cash_rates = pd.DataFrame({"IRX": irx.astype(float)})
    cash_rates = cash_rates.loc["2013-12-01":prices.index[-1]].copy()
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = evaluate(args.source_dir, prices, acquired_at_utc=captured,
                      cash_rates=cash_rates)
    args.output_prices_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_prices_csv.write_text(p4l.canonical_csv(prices), encoding="utf-8")
    args.output_rates_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_rates_csv.write_text(
        c13.canonical_cash_rates(cash_rates), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("P4R ORIGINAL 10-K 126-SESSION MATCHED SPY EVENT STUDY")
    print("Completed events:", report["completed_event_returns"],
          "right-censored:", report["right_censored_eligible_scores"])
    print("15bp score >=2:", report["summary"]["15"]["score_2_or_3"])
    print("15bp score <2:", report["summary"]["15"]["score_0_or_1"])
    print("15bp pre-filing quality x relative momentum:",
          report["quality_by_pre_filing_relative_momentum"]["15"])
    print("15bp fully invested SPY-funded stock replacement:",
          report["costed_six_slot_spy_idle_capital_overlay"]["15"])
    print("15bp interest-bearing cash comparison:", {
        label: {"stock_cagr": round(row["stock"]["net_cagr_pct"], 4),
                "paired_spy_cagr": round(
                    row["same_entry_dollar_matched_spy"]["net_cagr_pct"], 4),
                "stock_minus_spy_cagr": round(
                    row["stock_minus_paired_spy_cagr_pp"], 4)}
        for label, row in report["costed_six_slot_cash_carry_sensitivity"]["15"].items()
    })
    print("2026 SURVIVORS / REVISABLE PRICES AND RATES / NO VALIDATED ALPHA OR ORDERS")


if __name__ == "__main__":
    main()

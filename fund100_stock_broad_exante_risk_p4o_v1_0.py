"""P4O: risk attribution at the ORIGINAL P4L six-stock selection freeze.

Use only the 23-Oct-2026 original, source-hashed P4L price vintage.
The six stocks were selected WITH knowledge of these lookback returns:
the result is a hindsight-conditioned risk diagnostic, NOT an investable
backtest, return forecast, LIVE guard, or independently validated alpha.
No market-data acquisition, broker interface, or order capability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_frozen_forward_marks_p4m_v1_0 as p4m

SCHEMA = "FUND100_P4O_ORIGINAL_SIX_STOCK_EXANTE_RISK_V1"
SOURCE_SESSION = "2026-10-23"
LOOKBACK_RETURNS = 126
SESSIONS_PER_YEAR = 252
TAIL_FRACTION = 0.05
# Descriptive risk flags fixed before the original risk numbers were inspected.
BETA_FLAG = 0.90
PAIR_CORRELATION_FLAG = 0.85
EFFECTIVE_DIMENSIONS_FLAG = 3.0
SECTOR_WEIGHT_FLAG = 0.30
VOLATILITY_FLAG = 0.30


class P4OStop(ValueError):
    pass


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        raise P4OStop("Nonfinite risk diagnostic")
    return round(float(value), 6)


def _metrics(returns: pd.DataFrame, selected: list[str]) -> dict:
    """Contemporaneous equal-weight DAILY return proxies, not a traded P&L.

    Daily reweighting here isolates covariance; it does not imply costless
    executable rebalancing, and no historical return is reported as alpha.
    """
    expected = set(p4l.SECTORS) | {p4l.BENCHMARK, p4l.CASH_REFERENCE}
    if (not isinstance(returns, pd.DataFrame) or set(returns.columns) != expected
        or len(returns) != LOOKBACK_RETURNS or returns.isna().any().any()
        or not returns.index.is_monotonic_increasing
        or returns.index.has_duplicates
        or len(selected) != p4l.MAX_NAMES or len(set(selected)) != len(selected)
        or not set(selected) <= set(p4l.SECTORS)):
        raise P4OStop("Invalid original trailing risk window or selection")
    raw = returns.to_numpy(dtype=float)
    if not np.isfinite(raw).all() or (raw <= -1).any():
        raise P4OStop("Invalid trailing market returns")
    chosen = returns[selected].mean(axis=1).to_numpy(dtype=float)
    broad = returns[list(p4l.SECTORS)].mean(axis=1).to_numpy(dtype=float)
    market = returns[p4l.BENCHMARK].to_numpy(dtype=float)
    chosen_std = float(np.std(chosen, ddof=1))
    market_std = float(np.std(market, ddof=1))
    broad_std = float(np.std(broad, ddof=1))
    beta = corr = r_squared = None
    if market_std > 1e-10 and chosen_std > 1e-10:
        cov = float(np.cov(chosen, market, ddof=1)[0, 1])
        beta = cov / market_std**2
        corr = cov / (chosen_std * market_std)
        r_squared = min(1.0, max(0.0, corr**2))
    chosen_stds = returns[selected].std(ddof=1).to_numpy(dtype=float)
    effective = average_pair = max_pair = None
    if (chosen_stds > 1e-10).all():
        matrix = returns[selected].corr().to_numpy(dtype=float)
        if not np.isfinite(matrix).all():
            raise P4OStop("Nonfinite issuer correlation matrix")
        eigen = np.clip(np.linalg.eigvalsh(matrix), 0, None)
        effective = float(eigen.sum()**2 / np.square(eigen).sum())
        upper = matrix[np.triu_indices(len(selected), k=1)]
        average_pair = float(upper.mean())
        max_pair = float(upper.max())
    sector_counts = {}
    for symbol in selected:
        sector = p4l.SECTORS[symbol]
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    sector_weights = {sector: count / len(selected)
                      for sector, count in sorted(sector_counts.items())}
    sector_hhi = sum(weight**2 for weight in sector_weights.values())
    n_worst = max(1, math.ceil(len(market) * TAIL_FRACTION))
    worst_idx = np.argsort(market, kind="stable")[:n_worst]
    market_tail_mean = float(market[worst_idx].mean())
    selected_tail_mean = float(chosen[worst_idx].mean())
    downside_capture = (selected_tail_mean / market_tail_mean
                        if market_tail_mean < -1e-10 else None)
    vol = chosen_std * math.sqrt(SESSIONS_PER_YEAR)
    result = {
        "observed_trailing_return_intervals": len(returns),
        "selection_count": len(selected),
        "equal_weight_daily_rebalanced_covariance_proxy_not_executable": True,
        "selected_annualized_volatility": _rounded(vol),
        "equal_24_annualized_volatility": _rounded(broad_std * math.sqrt(SESSIONS_PER_YEAR)),
        "spy_annualized_volatility": _rounded(market_std * math.sqrt(SESSIONS_PER_YEAR)),
        "selected_spy_beta": _rounded(beta),
        "selected_spy_daily_correlation": _rounded(corr),
        "selected_spy_daily_r_squared": _rounded(r_squared),
        "selected_pairwise_mean_correlation": _rounded(average_pair),
        "selected_pairwise_max_correlation": _rounded(max_pair),
        "selected_effective_correlation_dimensions": _rounded(effective),
        "contemporary_sector_equal_weight_shares": {
            key: _rounded(value) for key, value in sector_weights.items()},
        "effective_contemporary_sector_count": _rounded(1 / sector_hhi),
        "spy_worst_5pct_session_count": n_worst,
        "spy_worst_5pct_mean_daily_return": _rounded(market_tail_mean),
        "selected_same_sessions_mean_daily_return": _rounded(selected_tail_mean),
        "spy_worst_5pct_selected_loss_capture_ratio": _rounded(downside_capture),
        "risk_flags_descriptive_not_live_guards": {
            "selected_spy_beta_at_least_0_90": beta is not None and beta >= BETA_FLAG,
            "max_issuer_pair_correlation_at_least_0_85":
                max_pair is not None and max_pair >= PAIR_CORRELATION_FLAG,
            "effective_issuer_dimensions_below_3":
                effective is not None and effective < EFFECTIVE_DIMENSIONS_FLAG,
            "contemporary_sector_weight_over_30pct":
                max(sector_weights.values()) > SECTOR_WEIGHT_FLAG,
            "selected_volatility_at_least_30pct": vol >= VOLATILITY_FLAG,
        },
    }
    return result


def analyze(original_report: dict, original_prices: pd.DataFrame) -> dict:
    if type(original_report) is not dict:
        raise P4OStop("Original source report missing")
    try:
        prices = p4l.validate_prices(original_prices)
        regenerated = p4l.evaluate(
            prices,
            acquired_at_utc=original_report.get("source_acquired_at_utc"),
            provider_reference=original_report.get("source_reference"),
        )
    except (p4l.BroadStockStop, ValueError, TypeError) as exc:
        raise P4OStop("Original P4L source not independently reproducible") from exc
    if original_report != regenerated:
        raise P4OStop("Original source report and price evidence disagree")
    if (original_report["asof_completed_session"] != SOURCE_SESSION
        or prices.index[-1] != pd.Timestamp(SOURCE_SESSION)
        or original_report["momentum_only_watchlist"] != p4m.ORIGINAL_SELECTION):
        raise P4OStop("Frozen 23-Oct original selection not preserved")
    if (original_report["trading_authorized"] is not False
        or original_report["paper_authorized"] is not False
        or original_report["live_authorized"] is not False
        or original_report["broker_orders"] != 0):
        raise P4OStop("Original evidence contains execution authority")
    digest = hashlib.sha256(p4l.canonical_csv(prices).encode("utf-8")).hexdigest()
    if digest != original_report["canonical_price_csv_sha256"]:
        raise P4OStop("Original source price digest changed")
    returns = prices.iloc[-(LOOKBACK_RETURNS + 1):].pct_change(
        fill_method=None).iloc[1:]
    metrics = _metrics(returns, p4m.ORIGINAL_SELECTION)
    return {
        "schema": SCHEMA,
        "status": "ORIGINAL_FROZEN_SELECTION_TRAILING_RISK_ONLY",
        "original_source_run_id": p4m.ORIGINAL_RUN_ID,
        "original_source_artifact_id": p4m.ORIGINAL_ARTIFACT_ID,
        "original_source_session": SOURCE_SESSION,
        "original_source_price_sha256": digest,
        "selection": list(p4m.ORIGINAL_SELECTION),
        "risk_window_start": returns.index[0].date().isoformat(),
        "risk_window_end": returns.index[-1].date().isoformat(),
        "risk_metrics": metrics,
        "cohort_survivor_selected_and_selected_using_same_lookback": True,
        "historical_selection_conditioning_bias": True,
        "not_a_historical_strategy_backtest": True,
        "not_point_in_time_delisting_safe": True,
        "adjusted_price_vendor_vintage_revisable": True,
        "no_costed_trading_return_or_alpha_claim": True,
        "no_live_risk_policy_change": True,
        "independent_alpha_validated": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_requests": 0,
        "broker_orders": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-json", required=True, type=Path)
    parser.add_argument("--original-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads(args.original_json.read_text(encoding="utf-8"))
    raw = args.original_csv.read_bytes()
    prices = pd.read_csv(args.original_csv, index_col="Date", parse_dates=["Date"])
    if raw != p4l.canonical_csv(prices).encode("utf-8"):
        raise P4OStop("Original source CSV bytes are not canonical")
    result = analyze(report, prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Original six-stock pre-selection trailing risk diagnostics:",
          result["risk_metrics"]["selected_spy_beta"],
          result["risk_metrics"]["selected_effective_correlation_dimensions"])
    print("HINDSIGHT-CONDITIONED risk only. NO historical alpha or broker orders.")


if __name__ == "__main__":
    main()

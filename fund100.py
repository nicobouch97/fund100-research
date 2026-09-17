from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
import yfinance as yf


TRADING_DAYS = 252


# ================================================================
# CONFIGURATION
# ================================================================

def load_config(
    path: str = "strategy_v1.0.yaml"
) -> Tuple[dict, str]:

    path_obj = Path(path)

    raw = path_obj.read_bytes()

    cfg = yaml.safe_load(raw)

    config_hash = hashlib.sha256(
        raw
    ).hexdigest()

    return cfg, config_hash


# ================================================================
# MARKET DATA
# ================================================================

def download_prices(
    cfg: dict
) -> Tuple[pd.DataFrame, pd.Series]:

    dcfg = cfg["data"]

    universe = dcfg["universe"]

    benchmark_ticker = (
        dcfg["benchmark_ticker"]
    )

    fx_ticker = dcfg["fx_ticker"]

    tickers = list(
        dict.fromkeys(
            universe
            + [benchmark_ticker, fx_ticker]
        )
    )

    raw = yf.download(
        tickers=tickers,
        start=dcfg["data_start"],
        end=dcfg.get("end"),
        interval="1d",
        auto_adjust=True,
        repair=True,
        progress=False,
        threads=True,
        group_by="column",
        multi_level_index=True,
    )

    if raw.empty:
        raise RuntimeError(
            "Market-data download "
            "returned no rows."
        )

    if not isinstance(
        raw.columns,
        pd.MultiIndex,
    ):
        raise RuntimeError(
            "Expected yfinance MultiIndex "
            "output for multiple tickers."
        )

    if "Close" not in (
        raw.columns.get_level_values(0)
    ):
        raise RuntimeError(
            "Downloaded data contain "
            "no Close field."
        )

    close = raw["Close"].copy()

    close.index = (
        pd.to_datetime(close.index)
        .tz_localize(None)
    )

    close = close.sort_index()

    required = set(
        universe
        + [
            benchmark_ticker,
            fx_ticker,
        ]
    )

    missing = required.difference(
        close.columns
    )

    if missing:
        raise RuntimeError(
            "Missing required symbols: "
            f"{sorted(missing)}"
        )

    # Only use days on which ACWI traded.
    benchmark_mask = (
        close[benchmark_ticker]
        .notna()
    )

    close = close.loc[
        benchmark_mask
    ].copy()

    fx = (
        close[fx_ticker]
        .ffill(limit=3)
    )

    if fx.isna().any():
        raise RuntimeError(
            "GBP/USD data contain "
            "unresolved missing values."
        )

    # Research assets are USD-listed.
    usd_prices = (
        close[
            universe
            + [benchmark_ticker]
        ]
        .ffill(limit=3)
    )

    # GBP value =
    # USD value / USD per GBP.
    gbp_prices = usd_prices.div(
        fx,
        axis=0,
    )

    bad_assets = [
        col
        for col in (
            universe
            + [benchmark_ticker]
        )
        if (
            gbp_prices[col]
            .isna()
            .mean()
            > 0.02
        )
    ]

    if bad_assets:
        raise RuntimeError(
            "Excessive missing history for: "
            f"{bad_assets}"
        )

    benchmark = gbp_prices.pop(
        benchmark_ticker
    )

    return gbp_prices, benchmark


# ================================================================
# SIGNAL HELPERS
# ================================================================

def cross_sectional_zscore(
    frame: pd.DataFrame
) -> pd.DataFrame:

    means = frame.mean(axis=1)

    stds = (
        frame
        .std(axis=1, ddof=0)
        .replace(0.0, np.nan)
    )

    return (
        frame
        .sub(means, axis=0)
        .div(stds, axis=0)
    )


# ================================================================
# SIGNAL ENGINE
# ================================================================

def compute_signals(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    cfg: dict,
) -> Dict[
    str,
    pd.DataFrame | pd.Series
]:

    scfg = cfg["signals"]
    pcfg = cfg["panic_regime"]

    returns = prices.pct_change(
        fill_method=None
    )

    market_returns = (
        benchmark.pct_change(
            fill_method=None
        )
    )

    # ------------------------------------------------------------
    # 1. MULTI-HORIZON TREND
    # ------------------------------------------------------------

    vol_window = (
        scfg["volatility_lookback"]
    )

    annual_vol = (
        returns
        .rolling(vol_window)
        .std()
        * math.sqrt(TRADING_DAYS)
    )

    trend_components = []

    for horizon in (
        scfg["trend_horizons"]
    ):

        risk_adjusted_return = (
            prices
            .pct_change(horizon)
            .div(
                annual_vol.replace(
                    0.0,
                    np.nan,
                )
            )
        )

        trend_components.append(
            cross_sectional_zscore(
                risk_adjusted_return
            )
        )

    trend = (
        sum(trend_components)
        / len(trend_components)
    )

    # ------------------------------------------------------------
    # 2. RESIDUAL MOMENTUM
    # ------------------------------------------------------------

    regression_window = (
        scfg[
            "residual_regression_lookback"
        ]
    )

    residual_window = (
        scfg[
            "residual_momentum_window"
        ]
    )

    market_mean = (
        market_returns
        .rolling(regression_window)
        .mean()
    )

    market_var = (
        market_returns
        .rolling(regression_window)
        .var()
    )

    residual_raw = pd.DataFrame(
        index=prices.index,
        columns=prices.columns,
        dtype=float,
    )

    for asset in prices.columns:

        asset_ret = returns[asset]

        beta = (
            asset_ret
            .rolling(regression_window)
            .cov(market_returns)
            .div(market_var)
        )

        alpha = (
            asset_ret
            .rolling(
                regression_window
            )
            .mean()
            - beta * market_mean
        )

        residual = (
            asset_ret
            - alpha
            - beta * market_returns
        )

        residual_vol = (
            residual
            .rolling(residual_window)
            .std()
            .replace(
                0.0,
                np.nan,
            )
        )

        residual_raw[asset] = (
            residual
            .rolling(residual_window)
            .sum()
            .div(
                residual_vol
                * math.sqrt(
                    residual_window
                )
            )
        )

    residual_momentum = (
        cross_sectional_zscore(
            residual_raw
        )
    )

    # ------------------------------------------------------------
    # 3. BREAKOUT CONFIRMATION
    # ------------------------------------------------------------

    sma_window = (
        scfg[
            "moving_average_window"
        ]
    )

    high_window = (
        scfg["high_window"]
    )

    moving_average = (
        prices
        .rolling(sma_window)
        .mean()
    )

    rolling_high = (
        prices
        .rolling(high_window)
        .max()
    )

    distance_from_sma = (
        prices.div(
            moving_average
        )
        - 1.0
    )

    distance_from_high = (
        prices.div(
            rolling_high
        )
        - 1.0
    )

    breakout = (
        0.5
        * cross_sectional_zscore(
            distance_from_sma
        )
        + 0.5
        * cross_sectional_zscore(
            distance_from_high
        )
    )

    # ------------------------------------------------------------
    # COMPOSITE SIGNAL
    # ------------------------------------------------------------

    composite = (
        scfg["trend_weight"]
        * trend
        + scfg["residual_weight"]
        * residual_momentum
        + scfg["breakout_weight"]
        * breakout
    )

    # ------------------------------------------------------------
    # PANIC REGIME
    # ------------------------------------------------------------

    benchmark_sma = (
        benchmark
        .rolling(
            pcfg[
                "market_sma_window"
            ]
        )
        .mean()
    )

    realised_market_vol = (
        market_returns
        .rolling(
            pcfg[
                "realised_volatility_window"
            ]
        )
        .std()
        * math.sqrt(TRADING_DAYS)
    )

    volatility_threshold = (
        realised_market_vol
        .rolling(
            pcfg[
                "volatility_percentile_window"
            ]
        )
        .quantile(
            pcfg[
                "volatility_percentile"
            ]
        )
    )

    panic = (
        (
            benchmark
            < benchmark_sma
        )
        &
        (
            realised_market_vol
            > volatility_threshold
        )
    )

    return {
        "returns": returns,
        "annual_vol": annual_vol,
        "trend": trend,
        "residual":
            residual_momentum,
        "breakout": breakout,
        "composite": composite,
        "moving_average":
            moving_average,
        "panic": panic,
    }


# ================================================================
# PORTFOLIO CONSTRUCTION
# ================================================================

def capped_proportional_weights(
    raw_scores: pd.Series,
    gross_target: float,
    maximum_weight: float,
) -> pd.Series:

    scores = (
        raw_scores
        .astype(float)
        .clip(lower=0.0)
        .copy()
    )

    result = pd.Series(
        0.0,
        index=scores.index,
        dtype=float,
    )

    if scores.empty:
        return result

    if scores.sum() <= 0:
        scores[:] = 1.0

    gross_target = min(
        gross_target,
        len(scores)
        * maximum_weight,
        1.0,
    )

    remaining = list(
        scores.index
    )

    remaining_gross = (
        gross_target
    )

    while (
        remaining
        and remaining_gross
        > 1e-12
    ):

        subset = scores.loc[
            remaining
        ]

        if subset.sum() <= 0:

            proposed = pd.Series(
                remaining_gross
                / len(remaining),
                index=remaining,
            )

        else:

            proposed = (
                subset
                / subset.sum()
                * remaining_gross
            )

        over_cap = proposed[
            proposed
            > maximum_weight
            + 1e-12
        ]

        if over_cap.empty:

            result.loc[
                remaining
            ] = proposed

            break

        capped_names = list(
            over_cap.index
        )

        result.loc[
            capped_names
        ] = maximum_weight

        remaining_gross -= (
            maximum_weight
            * len(capped_names)
        )

        remaining = [
            name
            for name in remaining
            if name
            not in capped_names
        ]

    return result


def construct_target_weights(
    date: pd.Timestamp,
    current_weights: pd.Series,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    signals: dict,
    cfg: dict,
) -> pd.Series:

    pcfg = cfg["portfolio"]

    assets = prices.columns

    target = pd.Series(
        0.0,
        index=assets,
        dtype=float,
    )

    score = (
        signals["composite"]
        .loc[date]
    )

    if score.isna().all():
        return target

    trend = (
        signals["trend"]
        .loc[date]
    )

    moving_average = (
        signals["moving_average"]
        .loc[date]
    )

    current_prices = (
        prices.loc[date]
    )

    ranks = score.rank(
        ascending=False,
        method="first",
    )

    absolute_trend_ok = (
        (trend > 0)
        &
        (
            current_prices
            > moving_average
        )
    )

    entry_eligible = (
        absolute_trend_ok
        & (score > 0)
        & (
            ranks
            <= pcfg[
                "max_positions"
            ]
        )
    )

    # ------------------------------------------------------------
    # HYSTERESIS
    # ------------------------------------------------------------

    held = list(
        current_weights[
            current_weights
            > 1e-10
        ].index
    )

    keepers = []

    for asset in held:

        if (
            pd.notna(
                ranks.get(asset)
            )
            and (
                ranks[asset]
                <= pcfg[
                    "keep_rank"
                ]
            )
            and bool(
                absolute_trend_ok
                .get(
                    asset,
                    False,
                )
            )
        ):
            keepers.append(asset)

    selected = (
        keepers.copy()
    )

    ordered = list(
        score
        .sort_values(
            ascending=False
        )
        .index
    )

    for asset in ordered:

        if (
            len(selected)
            >= pcfg[
                "max_positions"
            ]
        ):
            break

        if asset in selected:
            continue

        if bool(
            entry_eligible.get(
                asset,
                False,
            )
        ):
            selected.append(asset)

    if not selected:
        return target

    vol = (
        signals["annual_vol"]
        .loc[
            date,
            selected,
        ]
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .dropna()
    )

    selected = list(
        vol.index
    )

    if not selected:
        return target

    inverse_vol = (
        1.0
        / vol.replace(
            0.0,
            np.nan,
        )
    )

    inverse_vol = (
        inverse_vol.dropna()
    )

    if inverse_vol.empty:
        return target

    selected = list(
        inverse_vol.index
    )

    panic = bool(
        signals["panic"]
        .loc[date]
    )

    max_gross = (
        pcfg[
            "panic_max_gross"
        ]
        if panic
        else pcfg[
            "normal_max_gross"
        ]
    )

    selected_weights = (
        capped_proportional_weights(
            raw_scores=inverse_vol,
            gross_target=max_gross,
            maximum_weight=pcfg[
                "max_asset_weight"
            ],
        )
    )

    # ------------------------------------------------------------
    # PORTFOLIO VOLATILITY TARGET
    # ------------------------------------------------------------

    recent_returns = (
        signals["returns"]
        .loc[
            :date,
            selected,
        ]
        .tail(
            pcfg[
                "covariance_window"
            ]
        )
    )

    covariance = (
        recent_returns.cov()
        * TRADING_DAYS
    )

    vector = (
        selected_weights
        .loc[selected]
        .values
    )

    if (
        covariance
        .notna()
        .all()
        .all()
        and len(vector) > 0
    ):

        variance = float(
            vector.T
            @ covariance.values
            @ vector
        )

        if variance > 0:

            portfolio_vol = (
                math.sqrt(
                    variance
                )
            )

            vol_scale = min(
                1.0,
                pcfg[
                    "annual_volatility_target"
                ]
                / portfolio_vol,
            )

            selected_weights *= (
                vol_scale
            )

    target.loc[
        selected_weights.index
    ] = selected_weights

    return target


# ================================================================
# EXECUTION SIMULATOR
# ================================================================

def apply_trade_threshold(
    current: pd.Series,
    desired: pd.Series,
    minimum_trade: float,
    maximum_weight: float,
    maximum_gross: float,
) -> pd.Series:

    result = desired.copy()

    for asset in desired.index:

        old = float(
            current[asset]
        )

        new = float(
            desired[asset]
        )

        delta = new - old

        # Exits always permitted.
        if new <= 1e-12:

            result[asset] = 0.0
            continue

        # Do not open tiny positions.
        if (
            old <= 1e-12
            and abs(delta)
            < minimum_trade
        ):

            result[asset] = 0.0
            continue

        # Ignore small maintenance
        # reallocations.
        if (
            old > 1e-12
            and abs(delta)
            < minimum_trade
        ):

            result[asset] = old

    result = result.clip(
        lower=0.0,
        upper=maximum_weight,
    )

    gross = float(
        result.sum()
    )

    if (
        gross > maximum_gross
        and gross > 0
    ):

        result *= (
            maximum_gross
            / gross
        )

    return result


# ================================================================
# BACKTEST
# ================================================================

def run_backtest(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    signals: dict,
    cfg: dict,
    one_way_cost_bps: float,
) -> dict:

    pcfg = cfg["portfolio"]

    account_cfg = (
        cfg["account"]
    )

    evaluation_start = (
        pd.Timestamp(
            cfg["data"][
                "evaluation_start"
            ]
        )
    )

    dates = prices.index[
        prices.index
        >= evaluation_start
    ]

    assets = prices.columns

    weights = pd.Series(
        0.0,
        index=assets,
        dtype=float,
    )

    nav = float(
        account_cfg[
            "starting_nav_gbp"
        ]
    )

    nav_rows = []
    weight_rows = []
    trade_rows = []

    total_cost_gbp = 0.0
    total_turnover = 0.0

    cost_rate = (
        one_way_cost_bps
        / 10_000.0
    )

    for date in dates:

        nav_before_day = nav

        daily_asset_returns = (
            signals["returns"]
            .loc[date]
            .reindex(assets)
            .fillna(0.0)
        )

        # Existing portfolio earns
        # today's return first.
        portfolio_return = float(
            (
                weights
                * daily_asset_returns
            ).sum()
        )

        nav *= (
            1.0
            + portfolio_return
        )

        if nav <= 0:
            raise RuntimeError(
                "Portfolio NAV became "
                f"non-positive on {date}."
            )

        denominator = (
            1.0
            + portfolio_return
        )

        if denominator <= 0:
            raise RuntimeError(
                "Invalid portfolio return "
                "denominator."
            )

        weights = (
            weights
            * (
                1.0
                + daily_asset_returns
            )
            / denominator
        )

        turnover_today = 0.0
        cost_today = 0.0

        # Wednesday close rebalance.
        if (
            date.weekday()
            == pcfg[
                "rebalance_weekday"
            ]
        ):

            desired = (
                construct_target_weights(
                    date=date,
                    current_weights=
                        weights,
                    prices=prices,
                    benchmark=benchmark,
                    signals=signals,
                    cfg=cfg,
                )
            )

            panic = bool(
                signals["panic"]
                .loc[date]
            )

            max_gross = (
                pcfg[
                    "panic_max_gross"
                ]
                if panic
                else pcfg[
                    "normal_max_gross"
                ]
            )

            executed = (
                apply_trade_threshold(
                    current=weights,
                    desired=desired,
                    minimum_trade=
                        pcfg[
                            "minimum_trade_fraction_nav"
                        ],
                    maximum_weight=
                        pcfg[
                            "max_asset_weight"
                        ],
                    maximum_gross=
                        max_gross,
                )
            )

            delta = (
                executed
                - weights
            )

            turnover_today = float(
                delta.abs().sum()
            )

            cost_today = (
                nav
                * turnover_today
                * cost_rate
            )

            nav -= cost_today

            total_cost_gbp += (
                cost_today
            )

            total_turnover += (
                turnover_today
            )

            changed_assets = (
                delta[
                    delta.abs()
                    > 1e-12
                ].index
            )

            for asset in (
                changed_assets
            ):

                trade_rows.append({
                    "date": date,
                    "asset": asset,
                    "old_weight":
                        float(
                            weights[
                                asset
                            ]
                        ),
                    "desired_weight":
                        float(
                            desired[
                                asset
                            ]
                        ),
                    "executed_weight":
                        float(
                            executed[
                                asset
                            ]
                        ),
                    "weight_change":
                        float(
                            delta[
                                asset
                            ]
                        ),
                    "panic_regime":
                        panic,
                    "one_way_cost_bps":
                        one_way_cost_bps,
                })

            weights = executed

        daily_net_return = (
            nav
            / nav_before_day
        ) - 1.0

        nav_rows.append({
            "date": date,
            "nav": nav,
            "daily_return":
                daily_net_return,
            "turnover":
                turnover_today,
            "transaction_cost_gbp":
                cost_today,
            "gross_exposure":
                float(
                    weights.sum()
                ),
            "panic_regime":
                bool(
                    signals["panic"]
                    .loc[date]
                ),
        })

        row = {
            "date": date
        }

        for asset in assets:
            row[asset] = float(
                weights[asset]
            )

        weight_rows.append(row)

    history = (
        pd.DataFrame(nav_rows)
        .set_index("date")
    )

    weight_history = (
        pd.DataFrame(
            weight_rows
        )
        .set_index("date")
    )

    trades = pd.DataFrame(
        trade_rows
    )

    # ------------------------------------------------------------
    # BENCHMARK
    # ------------------------------------------------------------

    benchmark_returns = (
        benchmark
        .pct_change(
            fill_method=None
        )
        .reindex(
            history.index
        )
        .fillna(0.0)
    )

    if len(
        benchmark_returns
    ):

        benchmark_returns.iloc[
            0
        ] = 0.0

    benchmark_nav = (
        account_cfg[
            "starting_nav_gbp"
        ]
        * (
            1.0
            + benchmark_returns
        ).cumprod()
    )

    history[
        "benchmark_return"
    ] = benchmark_returns

    history[
        "benchmark_nav"
    ] = benchmark_nav

    return {
        "history": history,
        "weights":
            weight_history,
        "trades": trades,
        "total_cost_gbp":
            total_cost_gbp,
        "total_turnover":
            total_turnover,
    }


# ================================================================
# PERFORMANCE METRICS
# ================================================================

def performance_metrics(
    result: dict,
    starting_nav: float,
) -> dict:

    history = (
        result["history"]
    )

    if len(history) < 2:
        raise RuntimeError(
            "Insufficient observations "
            "for statistics."
        )

    strategy_returns = (
        history[
            "daily_return"
        ]
    )

    benchmark_returns = (
        history[
            "benchmark_return"
        ]
    )

    years = (
        (
            history.index[-1]
            - history.index[0]
        ).days
        / 365.25
    )

    years = max(
        years,
        1.0 / 365.25,
    )

    final_nav = float(
        history["nav"]
        .iloc[-1]
    )

    benchmark_final = float(
        history[
            "benchmark_nav"
        ]
        .iloc[-1]
    )

    total_return = (
        final_nav
        / starting_nav
    ) - 1.0

    benchmark_total_return = (
        benchmark_final
        / starting_nav
    ) - 1.0

    cagr = (
        (
            final_nav
            / starting_nav
        )
        ** (
            1.0
            / years
        )
        - 1.0
    )

    benchmark_cagr = (
        (
            benchmark_final
            / starting_nav
        )
        ** (
            1.0
            / years
        )
        - 1.0
    )

    daily_std = (
        strategy_returns
        .std(ddof=1)
    )

    annual_volatility = (
        daily_std
        * math.sqrt(
            TRADING_DAYS
        )
    )

    sharpe = (
        strategy_returns.mean()
        / daily_std
        * math.sqrt(
            TRADING_DAYS
        )
        if daily_std > 0
        else np.nan
    )

    downside = (
        strategy_returns[
            strategy_returns
            < 0
        ]
    )

    downside_std = (
        downside.std(
            ddof=1
        )
    )

    sortino = (
        strategy_returns.mean()
        / downside_std
        * math.sqrt(
            TRADING_DAYS
        )
        if (
            pd.notna(
                downside_std
            )
            and downside_std > 0
        )
        else np.nan
    )

    running_peak = (
        history["nav"]
        .cummax()
    )

    drawdown = (
        history["nav"]
        / running_peak
    ) - 1.0

    max_drawdown = float(
        drawdown.min()
    )

    excess = (
        strategy_returns
        - benchmark_returns
    )

    excess_std = (
        excess.std(
            ddof=1
        )
    )

    information_ratio = (
        excess.mean()
        / excess_std
        * math.sqrt(
            TRADING_DAYS
        )
        if excess_std > 0
        else np.nan
    )

    benchmark_variance = (
        benchmark_returns.var(
            ddof=1
        )
    )

    if (
        benchmark_variance
        > 0
    ):

        beta = (
            strategy_returns.cov(
                benchmark_returns
            )
            / benchmark_variance
        )

        alpha_daily = (
            strategy_returns.mean()
            - beta
            * benchmark_returns.mean()
        )

        alpha_annualised = (
            alpha_daily
            * TRADING_DAYS
        )

    else:

        beta = np.nan
        alpha_annualised = np.nan

    annual_turnover = (
        result[
            "total_turnover"
        ]
        / years
    )

    return {
        "start":
            str(
                history
                .index[0]
                .date()
            ),

        "end":
            str(
                history
                .index[-1]
                .date()
            ),

        "years": years,

        "starting_nav_gbp":
            starting_nav,

        "final_nav_gbp":
            final_nav,

        "benchmark_final_nav_gbp":
            benchmark_final,

        "total_return":
            total_return,

        "benchmark_total_return":
            benchmark_total_return,

        "cagr":
            cagr,

        "benchmark_cagr":
            benchmark_cagr,

        "annual_volatility":
            annual_volatility,

        "sharpe_ratio_rf0":
            sharpe,

        "sortino_ratio_rf0":
            sortino,

        "max_drawdown":
            max_drawdown,

        "information_ratio":
            information_ratio,

        "beta_to_benchmark":
            beta,

        "annualised_regression_alpha_rf0":
            alpha_annualised,

        "annual_turnover":
            annual_turnover,

        "total_transaction_cost_gbp":
            result[
                "total_cost_gbp"
            ],
    }


# ================================================================
# CHARTING
# ================================================================

def create_chart(
    history: pd.DataFrame,
    output_path: Path,
) -> None:

    fig, axes = (
        plt.subplots(
            2,
            1,
            figsize=(12, 8),
            gridspec_kw={
                "height_ratios":
                    [3, 1]
            },
            sharex=True,
        )
    )

    axes[0].plot(
        history.index,
        history["nav"],
        label="Fund-100 RTE",
        linewidth=1.8,
    )

    axes[0].plot(
        history.index,
        history[
            "benchmark_nav"
        ],
        label=(
            "ACWI ETF proxy "
            "in GBP"
        ),
        linewidth=1.5,
        alpha=0.85,
    )

    axes[0].set_ylabel(
        "NAV (£)"
    )

    axes[0].set_title(
        "Fund-100 Research "
        "Engine v1.0"
    )

    axes[0].legend()

    axes[0].grid(
        alpha=0.25
    )

    strategy_drawdown = (
        history["nav"]
        / history["nav"]
        .cummax()
        - 1.0
    )

    axes[1].fill_between(
        history.index,
        strategy_drawdown,
        0,
        alpha=0.35,
        color="crimson",
    )

    axes[1].set_ylabel(
        "Drawdown"
    )

    axes[1].grid(
        alpha=0.25
    )

    plt.tight_layout()

    fig.savefig(
        output_path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(fig)


# ================================================================
# MAIN
# ================================================================

def main() -> None:

    cfg, config_hash = (
        load_config()
    )

    output_dir = Path(
        "outputs"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    print(
        f"Strategy: "
        f"{cfg['strategy']['name']} "
        f"v{cfg['strategy']['version']}"
    )

    print(
        "Frozen configuration "
        f"SHA256: {config_hash}"
    )

    print(
        "Downloading market data..."
    )

    prices, benchmark = (
        download_prices(cfg)
    )

    print(
        f"Data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "Computing signals..."
    )

    signals = (
        compute_signals(
            prices=prices,
            benchmark=benchmark,
            cfg=cfg,
        )
    )

    starting_nav = float(
        cfg["account"][
            "starting_nav_gbp"
        ]
    )

    scenarios = (
        cfg["costs"][
            "scenarios_bps"
        ]
    )

    base_cost = (
        cfg["costs"][
            "base_one_way_bps"
        ]
    )

    scenario_rows = []

    base_result = None
    base_metrics = None

    for cost_bps in scenarios:

        print(
            "Running transaction-cost "
            f"scenario: {cost_bps} bps..."
        )

        result = run_backtest(
            prices=prices,
            benchmark=benchmark,
            signals=signals,
            cfg=cfg,
            one_way_cost_bps=
                float(
                    cost_bps
                ),
        )

        metrics = (
            performance_metrics(
                result=result,
                starting_nav=
                    starting_nav,
            )
        )

        scenario_rows.append({
            "cost_bps":
                cost_bps,
            **metrics,
        })

        if (
            float(cost_bps)
            == float(base_cost)
        ):

            base_result = (
                result
            )

            base_metrics = (
                metrics
            )

    scenario_table = (
        pd.DataFrame(
            scenario_rows
        )
        .set_index(
            "cost_bps"
        )
    )

    print(
        "\n=== COST-SENSITIVITY "
        "RESULTS ==="
    )

    columns_to_show = [
        "final_nav_gbp",
        "benchmark_final_nav_gbp",
        "cagr",
        "benchmark_cagr",
        "annual_volatility",
        "sharpe_ratio_rf0",
        "max_drawdown",
        "information_ratio",
        "beta_to_benchmark",
        "annualised_regression_alpha_rf0",
        "annual_turnover",
        "total_transaction_cost_gbp",
    ]

    print(
        scenario_table[
            columns_to_show
        ].round(4)
    )

    scenario_table.to_csv(
        output_dir
        / "cost_sensitivity.csv"
    )

    if base_result is None:
        raise RuntimeError(
            "Base transaction-cost "
            "scenario was not present."
        )

    base_result[
        "history"
    ].to_csv(
        output_dir
        / "daily_nav.csv"
    )

    base_result[
        "weights"
    ].to_csv(
        output_dir
        / "daily_weights.csv"
    )

    base_result[
        "trades"
    ].to_csv(
        output_dir
        / "trade_audit.csv",
        index=False,
    )

    with (
        output_dir
        / "performance_metrics.json"
    ).open("w") as f:

        json.dump(
            base_metrics,
            f,
            indent=2,
            default=float,
        )

    with (
        output_dir
        / "strategy_metadata.json"
    ).open("w") as f:

        json.dump(
            {
                "strategy":
                    cfg[
                        "strategy"
                    ]["name"],

                "version":
                    cfg[
                        "strategy"
                    ]["version"],

                "config_sha256":
                    config_hash,

                "benchmark":
                    (
                        "ACWI ETF "
                        "GBP-translated "
                        "research proxy"
                    ),

                "starting_nav_gbp":
                    starting_nav,
            },
            f,
            indent=2,
        )

    create_chart(
        history=
            base_result[
                "history"
            ],

        output_path=
            output_dir
            / "equity_curve.png",
    )

    print(
        "\nOutputs written "
        "to ./outputs/"
    )

    print(
        "Do not interpret a "
        "strong historical backtest "
        "as guaranteed future alpha."
    )


if __name__ == "__main__":
    main()

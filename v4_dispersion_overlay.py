from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from fund100 import (
    load_config,
    download_prices,
)


# ============================================================
# FUND-100 V4
#
# BENCHMARK-RELATIVE MOMENTUM
# + DISPERSION-CONDITIONED ALPHA OVERLAY
#
# Historical research only.
# No live execution.
# ============================================================

TRADING_DAYS = 252

OUTPUT_DIR = Path("v4_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# RESEARCH PERIOD
# ============================================================

EVALUATION_START = "2014-01-01"


# ============================================================
# EQUITY TILT UNIVERSE
# ============================================================

EQUITY_UNIVERSE = [
    # Broad US
    "SPY",
    "IWM",

    # International
    "EFA",
    "EEM",

    # Real estate
    "VNQ",

    # US sectors
    "XLK",
    "XLF",
    "XLI",
    "XLV",
    "XLP",
    "XLY",
    "XLE",
    "XLU",
]


# ============================================================
# DIVERSIFICATION GROUPS
# ============================================================

GROUPS = {
    "US_BROAD": [
        "SPY",
        "IWM",
    ],

    "INTERNATIONAL": [
        "EFA",
        "EEM",
    ],

    "REAL_ESTATE": [
        "VNQ",
    ],

    "US_SECTORS": [
        "XLK",
        "XLF",
        "XLI",
        "XLV",
        "XLP",
        "XLY",
        "XLE",
        "XLU",
    ],
}


GROUP_LIMITS = {
    "US_BROAD": 1,
    "INTERNATIONAL": 1,
    "REAL_ESTATE": 1,
    "US_SECTORS": 2,
}


ASSET_TO_GROUP = {}

for group_name, members in GROUPS.items():
    for ticker in members:
        ASSET_TO_GROUP[ticker] = group_name


# ============================================================
# FROZEN V4 HYPOTHESIS
# ============================================================

# Benchmark-relative return horizons.
MOMENTUM_HORIZONS = [
    63,
    126,
    252,
]

# Relative trend filter.
RELATIVE_TREND_FILTER_WINDOW = 200

# Dispersion reference window.
#
# Current cross-sectional dispersion is compared against
# its own trailing historical distribution.
DISPERSION_LOOKBACK = 504

# Dynamic satellite sleeve:
#
# weak dispersion      -> 10.0%
# medium dispersion    -> 17.5%
# strong dispersion    -> 25.0%
LOW_OVERLAY = 0.10
MEDIUM_OVERLAY = 0.175
HIGH_OVERLAY = 0.25

# Median and 75th-percentile dispersion thresholds.
MEDIUM_DISPERSION_QUANTILE = 0.50
HIGH_DISPERSION_QUANTILE = 0.75

# Maximum number of satellite positions.
MAX_SATELLITES = 3

# Maximum TARGET position.
MAX_SATELLITE_POSITION = 0.125

# Hard drift limits.
#
# Market movement may move weights slightly above their
# target between rebalances.
MAX_SATELLITE_POSITION_DRIFT = 0.15
MAX_TOTAL_SATELLITE_DRIFT = 0.275

# Hysteresis:
#
# a holding can remain while ranked within the top 6.
KEEP_RANK = 6

# Ignore routine changes smaller than 2.5% of NAV.
MINIMUM_TRADE_FRACTION = 0.025

# Rebalance every four weeks.
REBALANCE_WEEKS = 4

# Wednesday = 2.
SIGNAL_WEEKDAY = 2

REBALANCE_ANCHOR = pd.Timestamp(
    "2010-01-06"
)


# ============================================================
# MODELS
# ============================================================

DYNAMIC_MODEL = "V4_DISPERSION"

FIXED_CONTROL = "FIXED_25_REL_MOM"


# ============================================================
# CONFIGURATION HASH
# ============================================================

def build_v4_manifest() -> dict:

    return {
        "research_version":
            "Fund-100 V4",

        "model":
            (
                "Benchmark-relative momentum "
                "with dispersion-conditioned overlay"
            ),

        "evaluation_start":
            EVALUATION_START,

        "momentum_horizons":
            MOMENTUM_HORIZONS,

        "relative_trend_filter_window":
            RELATIVE_TREND_FILTER_WINDOW,

        "dispersion_lookback":
            DISPERSION_LOOKBACK,

        "medium_dispersion_quantile":
            MEDIUM_DISPERSION_QUANTILE,

        "high_dispersion_quantile":
            HIGH_DISPERSION_QUANTILE,

        "low_overlay":
            LOW_OVERLAY,

        "medium_overlay":
            MEDIUM_OVERLAY,

        "high_overlay":
            HIGH_OVERLAY,

        "max_satellites":
            MAX_SATELLITES,

        "max_satellite_position":
            MAX_SATELLITE_POSITION,

        "keep_rank":
            KEEP_RANK,

        "minimum_trade_fraction":
            MINIMUM_TRADE_FRACTION,

        "rebalance_weeks":
            REBALANCE_WEEKS,

        "signal_weekday":
            SIGNAL_WEEKDAY,

        "execution":
            (
                "Signal formed at close; "
                "executed after next trading-session return"
            ),
    }


def manifest_hash(
    manifest: dict,
) -> str:

    encoded = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


# ============================================================
# DATA
# ============================================================

def load_complete_market_data(
    cfg: dict,
) -> tuple[
    pd.DataFrame,
    pd.Series,
]:

    prices, benchmark = (
        download_prices(
            cfg
        )
    )

    prices = prices.copy()
    benchmark = benchmark.copy()

    # --------------------------------------------------------
    # Avoid potentially incomplete same-calendar-day bars.
    #
    # We deliberately accept only dates strictly before the
    # current UTC calendar date.
    # --------------------------------------------------------

    today_utc = datetime.now(
        timezone.utc
    ).date()

    completed_dates = (
        prices.index.date
        < today_utc
    )

    prices = prices.loc[
        completed_dates
    ].copy()

    benchmark = benchmark.reindex(
        prices.index
    )

    if prices.empty:
        raise RuntimeError(
            "No completed market sessions available."
        )

    missing_assets = [
        asset
        for asset in EQUITY_UNIVERSE
        if asset not in prices.columns
    ]

    if missing_assets:
        raise RuntimeError(
            "Missing V4 assets: "
            f"{missing_assets}"
        )

    return (
        prices,
        benchmark,
    )


# ============================================================
# STANDARDISATION
# ============================================================

def cross_sectional_zscore(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    means = frame.mean(
        axis=1
    )

    stds = (
        frame
        .std(
            axis=1,
            ddof=0,
        )
        .replace(
            0.0,
            np.nan,
        )
    )

    return (
        frame
        .sub(
            means,
            axis=0,
        )
        .div(
            stds,
            axis=0,
        )
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def build_signals(
    prices: pd.DataFrame,
    benchmark: pd.Series,
) -> dict:

    equity_prices = (
        prices[
            EQUITY_UNIVERSE
        ]
        .copy()
    )

    raw_relative_components = []

    z_relative_components = []

    for horizon in MOMENTUM_HORIZONS:

        asset_return = (
            equity_prices
            .pct_change(
                horizon
            )
        )

        benchmark_return = (
            benchmark
            .pct_change(
                horizon
            )
        )

        relative_return = (
            asset_return
            .sub(
                benchmark_return,
                axis=0,
            )
        )

        raw_relative_components.append(
            relative_return
        )

        z_relative_components.append(
            cross_sectional_zscore(
                relative_return
            )
        )

    # Average raw benchmark-relative return.
    relative_momentum_raw = (
        sum(
            raw_relative_components
        )
        / len(
            raw_relative_components
        )
    )

    # Average cross-sectional rank signal.
    relative_momentum_score = (
        sum(
            z_relative_components
        )
        / len(
            z_relative_components
        )
    )

    # --------------------------------------------------------
    # RELATIVE LONG-TERM TREND
    #
    # Price of asset relative to ACWI.
    # --------------------------------------------------------

    relative_price = (
        equity_prices
        .div(
            benchmark,
            axis=0,
        )
    )

    relative_sma = (
        relative_price
        .rolling(
            RELATIVE_TREND_FILTER_WINDOW
        )
        .mean()
    )

    relative_trend_ok = (
        relative_price
        > relative_sma
    )

    # --------------------------------------------------------
    # CROSS-SECTIONAL DISPERSION
    #
    # We deliberately use RAW relative returns rather than
    # z-scores, because z-scores are standardised to roughly
    # constant cross-sectional dispersion.
    # --------------------------------------------------------

    dispersion = (
        relative_momentum_raw
        .std(
            axis=1,
            ddof=0,
        )
    )

    medium_threshold = (
        dispersion
        .rolling(
            DISPERSION_LOOKBACK,
            min_periods=252,
        )
        .quantile(
            MEDIUM_DISPERSION_QUANTILE
        )
        .shift(1)
    )

    high_threshold = (
        dispersion
        .rolling(
            DISPERSION_LOOKBACK,
            min_periods=252,
        )
        .quantile(
            HIGH_DISPERSION_QUANTILE
        )
        .shift(1)
    )

    asset_returns = (
        equity_prices
        .pct_change(
            fill_method=None
        )
    )

    benchmark_returns = (
        benchmark
        .pct_change(
            fill_method=None
        )
    )

    return {
        "prices":
            equity_prices,

        "asset_returns":
            asset_returns,

        "benchmark_returns":
            benchmark_returns,

        "relative_momentum_raw":
            relative_momentum_raw,

        "score":
            relative_momentum_score,

        "relative_price":
            relative_price,

        "relative_trend_ok":
            relative_trend_ok,

        "dispersion":
            dispersion,

        "medium_threshold":
            medium_threshold,

        "high_threshold":
            high_threshold,
    }


# ============================================================
# DISPERSION REGIME
# ============================================================

def overlay_cap_for_date(
    date: pd.Timestamp,
    signals: dict,
    model_name: str,
) -> tuple[
    float,
    str,
]:

    if model_name == FIXED_CONTROL:

        return (
            HIGH_OVERLAY,
            "FIXED_25",
        )

    dispersion = float(
        signals[
            "dispersion"
        ]
        .loc[date]
    )

    medium_threshold = (
        signals[
            "medium_threshold"
        ]
        .loc[date]
    )

    high_threshold = (
        signals[
            "high_threshold"
        ]
        .loc[date]
    )

    if (
        pd.isna(
            medium_threshold
        )
        or pd.isna(
            high_threshold
        )
    ):

        return (
            LOW_OVERLAY,
            "LOW",
        )

    if (
        dispersion
        >= float(
            high_threshold
        )
    ):

        return (
            HIGH_OVERLAY,
            "HIGH",
        )

    if (
        dispersion
        >= float(
            medium_threshold
        )
    ):

        return (
            MEDIUM_OVERLAY,
            "MEDIUM",
        )

    return (
        LOW_OVERLAY,
        "LOW",
    )


# ============================================================
# REBALANCE SCHEDULE
# ============================================================

def is_signal_day(
    date: pd.Timestamp,
) -> bool:

    if (
        date.weekday()
        != SIGNAL_WEEKDAY
    ):
        return False

    weeks_since_anchor = (
        date.normalize()
        - REBALANCE_ANCHOR
    ).days // 7

    if weeks_since_anchor < 0:
        return False

    return (
        weeks_since_anchor
        % REBALANCE_WEEKS
        == 0
    )


# ============================================================
# GROUP HELPERS
# ============================================================

def group_of(
    asset: str,
) -> str:

    return ASSET_TO_GROUP.get(
        asset,
        "OTHER",
    )


def can_add_asset(
    asset: str,
    selected: list[str],
) -> bool:

    group_name = group_of(
        asset
    )

    limit = GROUP_LIMITS.get(
        group_name,
        99,
    )

    existing = sum(
        1
        for name in selected
        if (
            group_of(name)
            == group_name
        )
    )

    return (
        existing
        < limit
    )


# ============================================================
# SATELLITE SELECTION
# ============================================================

def select_satellites(
    date: pd.Timestamp,
    current_weights: pd.Series,
    signals: dict,
) -> list[str]:

    score = (
        signals[
            "score"
        ]
        .loc[date]
    )

    trend_ok = (
        signals[
            "relative_trend_ok"
        ]
        .loc[date]
    )

    ranks = (
        score.rank(
            ascending=False,
            method="first",
        )
    )

    eligible = (
        (score > 0)
        &
        trend_ok
    )

    selected = []

    # --------------------------------------------------------
    # HYSTERESIS
    #
    # Existing holdings stay while:
    #
    # - score remains positive,
    # - relative trend remains positive,
    # - rank remains <= KEEP_RANK.
    # --------------------------------------------------------

    held = list(
        current_weights[
            current_weights
            > 1e-10
        ].index
    )

    held = sorted(
        held,
        key=lambda asset: (
            ranks.get(
                asset,
                np.inf,
            )
        ),
    )

    for asset in held:

        if (
            len(selected)
            >= MAX_SATELLITES
        ):
            break

        if not bool(
            eligible.get(
                asset,
                False,
            )
        ):
            continue

        if (
            pd.isna(
                ranks.get(
                    asset
                )
            )
        ):
            continue

        if (
            ranks[asset]
            > KEEP_RANK
        ):
            continue

        if not can_add_asset(
            asset,
            selected,
        ):
            continue

        selected.append(
            asset
        )

    # --------------------------------------------------------
    # Fill vacancies with strongest eligible assets.
    # --------------------------------------------------------

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
            >= MAX_SATELLITES
        ):
            break

        if asset in selected:
            continue

        if not bool(
            eligible.get(
                asset,
                False,
            )
        ):
            continue

        if not can_add_asset(
            asset,
            selected,
        ):
            continue

        selected.append(
            asset
        )

    return selected


# ============================================================
# TARGET PORTFOLIO
# ============================================================

def build_target_weights(
    date: pd.Timestamp,
    current_weights: pd.Series,
    signals: dict,
    model_name: str,
) -> tuple[
    pd.Series,
    float,
    str,
]:

    target = pd.Series(
        0.0,
        index=EQUITY_UNIVERSE,
        dtype=float,
    )

    overlay_cap, regime = (
        overlay_cap_for_date(
            date=
                date,

            signals=
                signals,

            model_name=
                model_name,
        )
    )

    selected = (
        select_satellites(
            date=
                date,

            current_weights=
                current_weights,

            signals=
                signals,
        )
    )

    if not selected:

        return (
            target,
            overlay_cap,
            regime,
        )

    equal_weight = min(
        MAX_SATELLITE_POSITION,
        overlay_cap
        / len(selected),
    )

    for asset in selected:

        target[asset] = (
            equal_weight
        )

    return (
        target,
        overlay_cap,
        regime,
    )


# ============================================================
# TURNOVER-AWARE EXECUTION
# ============================================================

def apply_trade_threshold(
    current: pd.Series,
    desired: pd.Series,
    target_overlay_cap: float,
) -> pd.Series:

    result = (
        desired.copy()
    )

    for asset in desired.index:

        old = float(
            current[asset]
        )

        new = float(
            desired[asset]
        )

        delta = (
            new - old
        )

        # Full exit is always allowed.
        if new <= 1e-12:

            result[asset] = 0.0

            continue

        # Block microscopic new positions.
        if (
            old <= 1e-12
            and abs(delta)
            < MINIMUM_TRADE_FRACTION
        ):

            result[asset] = 0.0

            continue

        # Ignore small maintenance changes.
        if (
            old > 1e-12
            and abs(delta)
            < MINIMUM_TRADE_FRACTION
        ):

            result[asset] = old

    # Target position cap.
    result = result.clip(
        lower=0.0,
        upper=
            MAX_SATELLITE_POSITION,
    )

    total = float(
        result.sum()
    )

    if (
        total
        > target_overlay_cap
        and total > 0
    ):

        result *= (
            target_overlay_cap
            / total
        )

    return result


# ============================================================
# BACKTEST
# ============================================================

def run_model(
    signals: dict,
    model_name: str,
    start_date: str,
    one_way_cost_bps: float,
) -> dict:

    asset_returns = (
        signals[
            "asset_returns"
        ]
    )

    benchmark_returns = (
        signals[
            "benchmark_returns"
        ]
    )

    dates = asset_returns.index[
        asset_returns.index
        >= pd.Timestamp(
            start_date
        )
    ]

    if len(dates) < 2:

        raise RuntimeError(
            "Insufficient dates "
            "for V4 backtest."
        )

    satellite_weights = (
        pd.Series(
            0.0,
            index=EQUITY_UNIVERSE,
            dtype=float,
        )
    )

    nav = 100.0

    pending_target = None
    pending_overlay_cap = None
    pending_regime = None

    current_regime = "NONE"
    current_target_cap = 0.0

    total_turnover = 0.0
    total_cost_gbp = 0.0

    cost_rate = (
        float(
            one_way_cost_bps
        )
        / 10_000.0
    )

    rows = []
    weight_rows = []

    for i, date in enumerate(
        dates
    ):

        nav_before_day = nav

        today_asset_returns = (
            asset_returns
            .loc[date]
            .reindex(
                EQUITY_UNIVERSE
            )
            .fillna(0.0)
        )

        benchmark_return = (
            benchmark_returns
            .loc[date]
        )

        if pd.isna(
            benchmark_return
        ):

            benchmark_return = 0.0

        benchmark_return = float(
            benchmark_return
        )

        # Evaluation starts at exactly £100.
        if i == 0:

            benchmark_return = 0.0

            today_asset_returns = (
                today_asset_returns
                * 0.0
            )

        core_weight = max(
            0.0,
            1.0
            - float(
                satellite_weights.sum()
            ),
        )

        gross_portfolio_return = float(
            core_weight
            * benchmark_return
            +
            (
                satellite_weights
                * today_asset_returns
            ).sum()
        )

        gross_overlay_return = (
            gross_portfolio_return
            - benchmark_return
        )

        nav *= (
            1.0
            + gross_portfolio_return
        )

        denominator = (
            1.0
            + gross_portfolio_return
        )

        if denominator <= 0:

            raise RuntimeError(
                "Invalid V4 "
                "portfolio return."
            )

        # ----------------------------------------------------
        # Drift satellite weights after market movement.
        # ----------------------------------------------------

        satellite_weights = (
            satellite_weights
            * (
                1.0
                + today_asset_returns
            )
            / denominator
        )

        # ----------------------------------------------------
        # Hard drift safety checks.
        # ----------------------------------------------------

        if (
            satellite_weights.sum()
            >
            MAX_TOTAL_SATELLITE_DRIFT
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite sleeve exceeded "
                "27.5% hard drift limit."
            )

        if (
            satellite_weights.max()
            >
            MAX_SATELLITE_POSITION_DRIFT
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite position exceeded "
                "15% hard drift limit."
            )

        turnover_today = 0.0
        cost_today = 0.0

        # ----------------------------------------------------
        # Execute target generated at previous session's close.
        # ----------------------------------------------------

        if pending_target is not None:

            old_satellite = (
                satellite_weights.copy()
            )

            old_core = max(
                0.0,
                1.0
                - float(
                    old_satellite.sum()
                ),
            )

            executed = (
                apply_trade_threshold(
                    current=
                        old_satellite,

                    desired=
                        pending_target,

                    target_overlay_cap=
                        float(
                            pending_overlay_cap
                        ),
                )
            )

            new_core = max(
                0.0,
                1.0
                - float(
                    executed.sum()
                ),
            )

            # Two-sided portfolio turnover:
            # satellite trades + corresponding ACWI core move.
            turnover_today = (
                float(
                    (
                        executed
                        - old_satellite
                    )
                    .abs()
                    .sum()
                )
                +
                abs(
                    new_core
                    - old_core
                )
            )

            cost_today = (
                nav
                * turnover_today
                * cost_rate
            )

            nav -= cost_today

            total_turnover += (
                turnover_today
            )

            total_cost_gbp += (
                cost_today
            )

            satellite_weights = (
                executed
            )

            current_regime = (
                pending_regime
            )

            current_target_cap = (
                float(
                    pending_overlay_cap
                )
            )

            pending_target = None
            pending_overlay_cap = None
            pending_regime = None

        # ----------------------------------------------------
        # Generate today's close signal.
        # It cannot execute until the next session.
        # ----------------------------------------------------

        if is_signal_day(
            date
        ):

            (
                pending_target,
                pending_overlay_cap,
                pending_regime,
            ) = build_target_weights(
                date=
                    date,

                current_weights=
                    satellite_weights,

                signals=
                    signals,

                model_name=
                    model_name,
            )

        daily_net_return = (
            nav
            / nav_before_day
            - 1.0
        )

        active_return = (
            daily_net_return
            - benchmark_return
        )

        cost_drag_return = (
            daily_net_return
            - gross_portfolio_return
        )

        core_weight = max(
            0.0,
            1.0
            - float(
                satellite_weights.sum()
            ),
        )

        rows.append({
            "date":
                date,

            "model":
                model_name,

            "nav":
                nav,

            "daily_return":
                daily_net_return,

            "benchmark_return":
                benchmark_return,

            "active_return":
                active_return,

            "gross_overlay_return":
                gross_overlay_return,

            "cost_drag_return":
                cost_drag_return,

            "core_weight":
                core_weight,

            "satellite_weight":
                float(
                    satellite_weights.sum()
                ),

            "target_overlay_cap":
                current_target_cap,

            "dispersion_regime":
                current_regime,

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,
        })

        weight_row = {
            "date":
                date,

            "model":
                model_name,

            "ACWI_CORE":
                core_weight,
        }

        for asset in EQUITY_UNIVERSE:

            weight_row[
                asset
            ] = float(
                satellite_weights[
                    asset
                ]
            )

        weight_rows.append(
            weight_row
        )

        if abs(
            core_weight
            + float(
                satellite_weights.sum()
            )
            - 1.0
        ) > 1e-8:

            raise RuntimeError(
                "V4 weights do not sum to 1."
            )

    history = (
        pd.DataFrame(
            rows
        )
        .set_index(
            "date"
        )
    )

    history[
        "benchmark_nav"
    ] = (
        100.0
        * (
            1.0
            + history[
                "benchmark_return"
            ]
        )
        .cumprod()
    )

    weights = (
        pd.DataFrame(
            weight_rows
        )
        .set_index(
            "date"
        )
    )

    return {
        "history":
            history,

        "weights":
            weights,

        "total_turnover":
            total_turnover,

        "total_cost_gbp":
            total_cost_gbp,
    }


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    result: dict,
) -> dict:

    history = (
        result[
            "history"
        ]
    )

    strategy = (
        history[
            "daily_return"
        ]
    )

    benchmark = (
        history[
            "benchmark_return"
        ]
    )

    active = (
        strategy
        - benchmark
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
        history[
            "nav"
        ]
        .iloc[-1]
    )

    benchmark_final = float(
        history[
            "benchmark_nav"
        ]
        .iloc[-1]
    )

    cagr = (
        (
            final_nav
            / 100.0
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
            / 100.0
        )
        ** (
            1.0
            / years
        )
        - 1.0
    )

    annual_volatility = (
        strategy.std(
            ddof=1
        )
        * math.sqrt(
            TRADING_DAYS
        )
    )

    benchmark_volatility = (
        benchmark.std(
            ddof=1
        )
        * math.sqrt(
            TRADING_DAYS
        )
    )

    active_std = (
        active.std(
            ddof=1
        )
    )

    tracking_error = (
        active_std
        * math.sqrt(
            TRADING_DAYS
        )
    )

    information_ratio = (
        active.mean()
        / active_std
        * math.sqrt(
            TRADING_DAYS
        )
        if active_std > 0
        else np.nan
    )

    benchmark_variance = (
        benchmark.var(
            ddof=1
        )
    )

    beta = (
        strategy.cov(
            benchmark
        )
        / benchmark_variance
        if benchmark_variance > 0
        else np.nan
    )

    running_peak = (
        history[
            "nav"
        ]
        .cummax()
    )

    max_drawdown = float(
        (
            history[
                "nav"
            ]
            / running_peak
            - 1.0
        )
        .min()
    )

    benchmark_peak = (
        history[
            "benchmark_nav"
        ]
        .cummax()
    )

    benchmark_max_drawdown = float(
        (
            history[
                "benchmark_nav"
            ]
            / benchmark_peak
            - 1.0
        )
        .min()
    )

    # --------------------------------------------------------
    # Active-return significance with HAC / Newey-West errors.
    # --------------------------------------------------------

    clean_active = (
        active.dropna()
    )

    if len(clean_active) > 30:

        X = np.ones(
            (
                len(
                    clean_active
                ),
                1,
            )
        )

        model = (
            sm.OLS(
                clean_active.values,
                X,
            )
            .fit(
                cov_type="HAC",
                cov_kwds={
                    "maxlags": 5
                },
            )
        )

        annualised_active = (
            float(
                model.params[0]
            )
            * TRADING_DAYS
        )

        active_tstat = float(
            model.tvalues[0]
        )

    else:

        annualised_active = np.nan
        active_tstat = np.nan

    annualised_gross_overlay = (
        history[
            "gross_overlay_return"
        ]
        .mean()
        * TRADING_DAYS
    )

    annualised_cost_drag = (
        history[
            "cost_drag_return"
        ]
        .mean()
        * TRADING_DAYS
    )

    annual_turnover = (
        result[
            "total_turnover"
        ]
        / years
    )

    # --------------------------------------------------------
    # Rolling 3-year relative performance.
    # --------------------------------------------------------

    rolling_window = (
        3
        * TRADING_DAYS
    )

    strategy_log = (
        np.log1p(
            strategy
        )
        .rolling(
            rolling_window
        )
        .sum()
    )

    benchmark_log = (
        np.log1p(
            benchmark
        )
        .rolling(
            rolling_window
        )
        .sum()
    )

    strategy_3y_cagr = (
        np.exp(
            strategy_log
            / 3.0
        )
        - 1.0
    )

    benchmark_3y_cagr = (
        np.exp(
            benchmark_log
            / 3.0
        )
        - 1.0
    )

    rolling_excess = (
        strategy_3y_cagr
        - benchmark_3y_cagr
    ).dropna()

    if len(
        rolling_excess
    ):

        fraction_3y_beating = float(
            (
                rolling_excess
                > 0
            )
            .mean()
        )

        median_3y_excess = float(
            rolling_excess
            .median()
        )

    else:

        fraction_3y_beating = np.nan
        median_3y_excess = np.nan

    regime_counts = (
        history[
            "dispersion_regime"
        ]
        .value_counts(
            normalize=True
        )
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

        "years":
            years,

        "final_nav_gbp":
            final_nav,

        "benchmark_final_nav_gbp":
            benchmark_final,

        "cagr":
            cagr,

        "benchmark_cagr":
            benchmark_cagr,

        "excess_cagr":
            cagr
            - benchmark_cagr,

        "annual_volatility":
            annual_volatility,

        "benchmark_volatility":
            benchmark_volatility,

        "tracking_error":
            tracking_error,

        "information_ratio":
            information_ratio,

        "beta_to_acwi":
            beta,

        "max_drawdown":
            max_drawdown,

        "benchmark_max_drawdown":
            benchmark_max_drawdown,

        "annualised_active_return":
            annualised_active,

        "active_hac_tstat":
            active_tstat,

        "annualised_gross_overlay":
            annualised_gross_overlay,

        "annualised_cost_drag":
            annualised_cost_drag,

        "annual_turnover":
            annual_turnover,

        "total_transaction_cost_gbp":
            result[
                "total_cost_gbp"
            ],

        "average_satellite_weight":
            float(
                history[
                    "satellite_weight"
                ]
                .mean()
            ),

        "fraction_3y_windows_beating_acwi":
            fraction_3y_beating,

        "median_3y_excess_cagr":
            median_3y_excess,

        "low_regime_fraction":
            float(
                regime_counts.get(
                    "LOW",
                    0.0,
                )
            ),

        "medium_regime_fraction":
            float(
                regime_counts.get(
                    "MEDIUM",
                    0.0,
                )
            ),

        "high_regime_fraction":
            float(
                regime_counts.get(
                    "HIGH",
                    0.0,
                )
            ),
    }


# ============================================================
# YEARLY RESULTS
# ============================================================

def yearly_results(
    history: pd.DataFrame,
) -> pd.DataFrame:

    def compound(
        values: pd.Series,
    ) -> float:

        return float(
            (
                1.0
                + values
            ).prod()
            - 1.0
        )

    years = (
        history.index.year
    )

    result = pd.DataFrame({
        "strategy_return":
            history[
                "daily_return"
            ]
            .groupby(
                years
            )
            .apply(
                compound
            ),

        "benchmark_return":
            history[
                "benchmark_return"
            ]
            .groupby(
                years
            )
            .apply(
                compound
            ),
    })

    result[
        "excess_return"
    ] = (
        result[
            "strategy_return"
        ]
        - result[
            "benchmark_return"
        ]
    )

    result.index.name = (
        "year"
    )

    return result


# ============================================================
# CHART
# ============================================================

def create_chart(
    dynamic_history: pd.DataFrame,
    control_history: pd.DataFrame,
) -> None:

    fig, axes = (
        plt.subplots(
            2,
            1,
            figsize=(12, 8),
            sharex=True,
            gridspec_kw={
                "height_ratios":
                    [3, 1]
            },
        )
    )

    axes[0].plot(
        dynamic_history.index,
        dynamic_history[
            "nav"
        ],
        label=
            "V4 Dispersion Overlay",
        linewidth=2.0,
    )

    axes[0].plot(
        control_history.index,
        control_history[
            "nav"
        ],
        label=
            "Fixed 25% Relative Momentum",
        linewidth=1.5,
        alpha=0.85,
    )

    axes[0].plot(
        dynamic_history.index,
        dynamic_history[
            "benchmark_nav"
        ],
        label=
            "ACWI GBP proxy",
        linewidth=1.6,
    )

    axes[0].set_ylabel(
        "NAV (£)"
    )

    axes[0].set_title(
        "Fund-100 V4 "
        "Dispersion-Conditioned Overlay"
    )

    axes[0].legend()

    axes[0].grid(
        alpha=0.25
    )

    relative_dynamic = (
        dynamic_history[
            "nav"
        ]
        / dynamic_history[
            "benchmark_nav"
        ]
        - 1.0
    )

    relative_control = (
        control_history[
            "nav"
        ]
        / control_history[
            "benchmark_nav"
        ]
        - 1.0
    )

    axes[1].plot(
        dynamic_history.index,
        relative_dynamic,
        label=
            "V4 vs ACWI",
        linewidth=1.7,
        color="purple",
    )

    axes[1].plot(
        control_history.index,
        relative_control,
        label=
            "Fixed control vs ACWI",
        linewidth=1.3,
        color="steelblue",
        alpha=0.8,
    )

    axes[1].axhline(
        0.0,
        color="black",
        linewidth=0.8,
    )

    axes[1].set_ylabel(
        "Relative wealth"
    )

    axes[1].legend()

    axes[1].grid(
        alpha=0.25
    )

    plt.tight_layout()

    fig.savefig(
        OUTPUT_DIR
        / "v4_equity_curve.png",
        dpi=170,
        bbox_inches="tight",
    )

    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 V4 DISPERSION-CONDITIONED OVERLAY"
    )

    print(
        "============================================"
    )

    cfg, v1_hash = (
        load_config()
    )

    manifest = (
        build_v4_manifest()
    )

    v4_hash = (
        manifest_hash(
            manifest
        )
    )

    print(
        "\nFrozen v1 config SHA256:"
    )

    print(
        v1_hash
    )

    print(
        "\nFrozen V4 research SHA256:"
    )

    print(
        v4_hash
    )

    print(
        "\nDownloading completed market data..."
    )

    prices, benchmark = (
        load_complete_market_data(
            cfg
        )
    )

    print(
        f"\nCompleted market data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "\nBuilding V4 signals..."
    )

    signals = (
        build_signals(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    # ========================================================
    # COST SENSITIVITY
    # ========================================================

    rows = []

    base_dynamic = None
    base_control = None

    for cost_bps in [
        5,
        15,
        35,
    ]:

        for model_name in [
            DYNAMIC_MODEL,
            FIXED_CONTROL,
        ]:

            print(
                f"\nRunning "
                f"{model_name} "
                f"at {cost_bps} bps..."
            )

            result = (
                run_model(
                    signals=
                        signals,

                    model_name=
                        model_name,

                    start_date=
                        EVALUATION_START,

                    one_way_cost_bps=
                        float(
                            cost_bps
                        ),
                )
            )

            metrics = (
                calculate_metrics(
                    result
                )
            )

            rows.append({
                "model":
                    model_name,

                "cost_bps":
                    cost_bps,

                **metrics,
            })

            if (
                cost_bps == 15
                and model_name
                == DYNAMIC_MODEL
            ):

                base_dynamic = (
                    result
                )

            if (
                cost_bps == 15
                and model_name
                == FIXED_CONTROL
            ):

                base_control = (
                    result
                )

    results = (
        pd.DataFrame(
            rows
        )
    )

    results.to_csv(
        OUTPUT_DIR
        / "v4_cost_sensitivity.csv",
        index=False,
    )

    # ========================================================
    # BASE 15 BPS OUTPUTS
    # ========================================================

    dynamic_metrics = (
        calculate_metrics(
            base_dynamic
        )
    )

    control_metrics = (
        calculate_metrics(
            base_control
        )
    )

    base_dynamic[
        "history"
    ].to_csv(
        OUTPUT_DIR
        / "v4_daily_nav.csv"
    )

    base_dynamic[
        "weights"
    ].to_csv(
        OUTPUT_DIR
        / "v4_daily_weights.csv"
    )

    yearly = (
        yearly_results(
            base_dynamic[
                "history"
            ]
        )
    )

    yearly.to_csv(
        OUTPUT_DIR
        / "v4_yearly_returns.csv"
    )

    latest_weights = (
        base_dynamic[
            "weights"
        ]
        .iloc[-1]
        .drop(
            labels=[
                "model"
            ],
            errors="ignore",
        )
    )

    latest_weights = (
        pd.to_numeric(
            latest_weights,
            errors="coerce",
        )
        .dropna()
    )

    latest_weights = (
        latest_weights[
            latest_weights
            > 0.000001
        ]
        .sort_values(
            ascending=False
        )
    )

    latest_df = (
        pd.DataFrame({
            "weight":
                latest_weights
        })
    )

    latest_df.to_csv(
        OUTPUT_DIR
        / "v4_latest_weights.csv"
    )

    create_chart(
        dynamic_history=
            base_dynamic[
                "history"
            ],

        control_history=
            base_control[
                "history"
            ],
    )

    # ========================================================
    # LATEST SIGNAL DIAGNOSTICS
    # ========================================================

    latest_date = (
        prices.index[-1]
    )

    latest_overlay_cap, latest_regime = (
        overlay_cap_for_date(
            date=
                latest_date,

            signals=
                signals,

            model_name=
                DYNAMIC_MODEL,
        )
    )

    latest_score = (
        signals[
            "score"
        ]
        .loc[
            latest_date
        ]
        .sort_values(
            ascending=False
        )
    )

    latest_dispersion = float(
        signals[
            "dispersion"
        ]
        .loc[
            latest_date
        ]
    )

    latest_medium_threshold = float(
        signals[
            "medium_threshold"
        ]
        .loc[
            latest_date
        ]
    )

    latest_high_threshold = float(
        signals[
            "high_threshold"
        ]
        .loc[
            latest_date
        ]
    )

    # ========================================================
    # FORWARD RESEARCH MANIFEST
    # ========================================================

    forward_manifest = {
        **manifest,

        "v4_sha256":
            v4_hash,

        "v1_config_sha256":
            v1_hash,

        "historical_data_cutoff":
            str(
                latest_date.date()
            ),

        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "forward_rule":
            (
                "No historical parameter changes "
                "after this freeze without creating "
                "a new strategy version."
            ),

        "forward_status":
            (
                "Research challenger only; "
                "no live execution."
            ),
    }

    with (
        OUTPUT_DIR
        / "v4_forward_manifest.json"
    ).open("w") as f:

        json.dump(
            forward_manifest,
            f,
            indent=2,
            default=float,
        )

    summary = {
        "research_version":
            "Fund-100 V4",

        "v4_sha256":
            v4_hash,

        "v1_config_sha256":
            v1_hash,

        "historical_data_cutoff":
            str(
                latest_date.date()
            ),

        "dynamic_15bps":
            dynamic_metrics,

        "fixed_control_15bps":
            control_metrics,

        "latest_dispersion_regime":
            latest_regime,

        "latest_target_overlay_cap":
            latest_overlay_cap,

        "latest_dispersion":
            latest_dispersion,

        "latest_medium_threshold":
            latest_medium_threshold,

        "latest_high_threshold":
            latest_high_threshold,
    }

    with (
        OUTPUT_DIR
        / "v4_summary.json"
    ).open("w") as f:

        json.dump(
            summary,
            f,
            indent=2,
            default=float,
        )

    # ========================================================
    # PRINT EVERYTHING IMPORTANT
    # ========================================================

    display_cols = [
        "model",
        "cost_bps",
        "final_nav_gbp",
        "benchmark_final_nav_gbp",
        "cagr",
        "benchmark_cagr",
        "excess_cagr",
        "annual_volatility",
        "benchmark_volatility",
        "tracking_error",
        "information_ratio",
        "beta_to_acwi",
        "max_drawdown",
        "benchmark_max_drawdown",
        "annualised_active_return",
        "active_hac_tstat",
        "annualised_gross_overlay",
        "annualised_cost_drag",
        "annual_turnover",
        "total_transaction_cost_gbp",
        "average_satellite_weight",
        "fraction_3y_windows_beating_acwi",
        "median_3y_excess_cagr",
        "low_regime_fraction",
        "medium_regime_fraction",
        "high_regime_fraction",
    ]

    print(
        "\n============================================"
    )

    print(
        "V4 COST SENSITIVITY"
    )

    print(
        "============================================"
    )

    print(
        results[
            display_cols
        ]
        .round(4)
        .to_string(
            index=False
        )
    )

    print(
        "\n============================================"
    )

    print(
        "V4 YEARLY RETURNS - 15 BPS"
    )

    print(
        "============================================"
    )

    print(
        yearly
        .round(4)
        .to_string()
    )

    print(
        "\n============================================"
    )

    print(
        "LATEST COMPLETED-DATE V4 WEIGHTS"
    )

    print(
        "============================================"
    )

    print(
        latest_df
        .round(4)
        .to_string()
    )

    print(
        "\n============================================"
    )

    print(
        "LATEST V4 SIGNAL STATE"
    )

    print(
        "============================================"
    )

    print(
        f"Completed data date: "
        f"{latest_date.date()}"
    )

    print(
        f"Dispersion regime: "
        f"{latest_regime}"
    )

    print(
        f"Target overlay cap: "
        f"{latest_overlay_cap:.1%}"
    )

    print(
        f"Current dispersion: "
        f"{latest_dispersion:.6f}"
    )

    print(
        f"Trailing median threshold: "
        f"{latest_medium_threshold:.6f}"
    )

    print(
        f"Trailing 75th percentile: "
        f"{latest_high_threshold:.6f}"
    )

    print(
        "\nTop relative-momentum scores:"
    )

    print(
        latest_score
        .head(8)
        .round(4)
        .to_string()
    )

    print(
        "\n============================================"
    )

    print(
        "V4 FORWARD FREEZE"
    )

    print(
        "============================================"
    )

    print(
        f"V4 research hash: "
        f"{v4_hash}"
    )

    print(
        "Historical evaluation is now "
        "considered frozen for this version."
    )

    print(
        "Any subsequent parameter changes "
        "must become V5 or later."
    )

    print(
        "\n============================================"
    )

    print(
        "IMPORTANT"
    )

    print(
        "============================================"
    )

    print(
        "This is historical research only."
    )

    print(
        "The latest weights are diagnostic "
        "outputs, not trade instructions."
    )

    print(
        "The broader research process has "
        "already examined this history."
    )

    print(
        "The forward manifest is only a "
        "timestamped research freeze."
    )

    print(
        "\nFiles written to ./v4_outputs/"
    )


if __name__ == "__main__":
    main()

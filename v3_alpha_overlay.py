from __future__ import annotations

import json
import math
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
# FUND-100 V3
# BENCHMARK + ALPHA OVERLAY RESEARCH
# ============================================================

TRADING_DAYS = 252

OUTPUT_DIR = Path("v3_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# ------------------------------------------------------------
# RESEARCH PERIOD
#
# We use earlier data for signal warm-up.
# Reported v3 evaluation begins in 2014 so it can be compared
# directly with the v2 walk-forward evaluation period.
#
# IMPORTANT:
# The broader research process has already observed 2010-2026.
# Therefore this is NOT pristine unseen evidence.
# Genuine forward evidence begins September 2026 onward.
# ------------------------------------------------------------

EVALUATION_START = "2014-01-01"


# ============================================================
# V3 EQUITY TILT UNIVERSE
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
# FROZEN V3 PARAMETERS
# ============================================================

RELATIVE_MOMENTUM_HORIZONS = [
    63,
    126,
    252,
]

TREND_QUALITY_WINDOW = 126

RELATIVE_TREND_FILTER_WINDOW = 200

# Fixed hypothesis:
# 70% benchmark-relative momentum
# 30% quality / persistence of the relative trend
MOMENTUM_WEIGHT = 0.70
QUALITY_WEIGHT = 0.30

# Only three satellite positions.
MAX_SATELLITES = 3

# Position must be highly ranked to enter,
# but can remain until rank falls below 6.
KEEP_RANK = 6

# Satellite sleeve can never exceed 25%.
MAX_SATELLITE_TOTAL = 0.25

# Individual tilt can never exceed 12.5%.
MAX_SATELLITE_WEIGHT = 0.125

# Ignore routine changes smaller than 2.5% NAV.
MINIMUM_TRADE_FRACTION = 0.025

# Rebalance every four weeks.
REBALANCE_WEEKS = 4

# Wednesday signal.
SIGNAL_WEEKDAY = 2

# Execution is deliberately delayed until the
# next trading session.
REBALANCE_ANCHOR = pd.Timestamp(
    "2010-01-06"
)


# ============================================================
# DIAGNOSTIC SIGNAL VARIANTS
#
# REL_MOM_QUALITY is the actual frozen V3 hypothesis.
#
# The other two are diagnostic ablations only.
# They are NOT dynamically selected.
# ============================================================

VARIANTS = {
    "REL_MOM_QUALITY": {
        "momentum_weight": 0.70,
        "quality_weight": 0.30,
    },

    "REL_MOM_ONLY": {
        "momentum_weight": 1.00,
        "quality_weight": 0.00,
    },

    "QUALITY_ONLY": {
        "momentum_weight": 0.00,
        "quality_weight": 1.00,
    },
}


# ============================================================
# HELPERS
# ============================================================

def cross_sectional_zscore(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Standardise each date across securities.
    """

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

    group_limit = GROUP_LIMITS.get(
        group_name,
        99,
    )

    current_count = sum(
        1
        for name in selected
        if group_of(name)
        == group_name
    )

    return (
        current_count
        < group_limit
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def build_signal_components(
    prices: pd.DataFrame,
    benchmark: pd.Series,
) -> dict:

    prices = prices[
        EQUITY_UNIVERSE
    ].copy()

    # --------------------------------------------------------
    # 1. BENCHMARK-RELATIVE MOMENTUM
    # --------------------------------------------------------

    relative_components = []

    raw_components = []

    for horizon in (
        RELATIVE_MOMENTUM_HORIZONS
    ):

        asset_return = (
            prices.pct_change(
                horizon
            )
        )

        benchmark_return = (
            benchmark.pct_change(
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

        raw_components.append(
            relative_return
        )

        relative_components.append(
            cross_sectional_zscore(
                relative_return
            )
        )

    relative_momentum_raw = (
        sum(raw_components)
        / len(raw_components)
    )

    relative_momentum_z = (
        sum(relative_components)
        / len(relative_components)
    )

    # --------------------------------------------------------
    # 2. RELATIVE TREND QUALITY
    #
    # Work with:
    #
    #     asset price / ACWI price
    #
    # A smooth persistent relative trend receives a larger
    # efficiency score than a noisy path ending at the same
    # relative return.
    # --------------------------------------------------------

    relative_price = (
        prices.div(
            benchmark,
            axis=0,
        )
    )

    log_relative_price = (
        np.log(
            relative_price
        )
    )

    net_change = (
        log_relative_price
        - log_relative_price.shift(
            TREND_QUALITY_WINDOW
        )
    )

    path_length = (
        log_relative_price
        .diff()
        .abs()
        .rolling(
            TREND_QUALITY_WINDOW
        )
        .sum()
    )

    signed_efficiency = (
        net_change.div(
            path_length.replace(
                0.0,
                np.nan,
            )
        )
    )

    signed_efficiency = (
        signed_efficiency
        .clip(
            lower=-1.0,
            upper=1.0,
        )
    )

    quality_z = (
        cross_sectional_zscore(
            signed_efficiency
        )
    )

    # --------------------------------------------------------
    # 3. RELATIVE LONG-TERM TREND FILTER
    # --------------------------------------------------------

    relative_sma = (
        relative_price
        .rolling(
            RELATIVE_TREND_FILTER_WINDOW
        )
        .mean()
    )

    relative_above_sma = (
        relative_price
        > relative_sma
    )

    # Daily returns used by the simulator.
    asset_returns = (
        prices.pct_change(
            fill_method=None
        )
    )

    benchmark_returns = (
        benchmark.pct_change(
            fill_method=None
        )
    )

    return {
        "prices":
            prices,

        "asset_returns":
            asset_returns,

        "benchmark_returns":
            benchmark_returns,

        "relative_price":
            relative_price,

        "relative_momentum_raw":
            relative_momentum_raw,

        "relative_momentum_z":
            relative_momentum_z,

        "quality_raw":
            signed_efficiency,

        "quality_z":
            quality_z,

        "relative_above_sma":
            relative_above_sma,
    }


def build_score(
    components: dict,
    variant_name: str,
) -> pd.DataFrame:

    params = VARIANTS[
        variant_name
    ]

    score = (
        params[
            "momentum_weight"
        ]
        * components[
            "relative_momentum_z"
        ]
        +
        params[
            "quality_weight"
        ]
        * components[
            "quality_z"
        ]
    )

    return score


# ============================================================
# REBALANCE CALENDAR
# ============================================================

def is_signal_day(
    date: pd.Timestamp,
) -> bool:

    if date.weekday() != SIGNAL_WEEKDAY:
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
# SATELLITE SELECTION
# ============================================================

def select_satellites(
    date: pd.Timestamp,
    current_satellite_weights: pd.Series,
    score: pd.DataFrame,
    components: dict,
) -> list[str]:

    today_score = (
        score.loc[date]
    )

    relative_trend_ok = (
        components[
            "relative_above_sma"
        ]
        .loc[date]
    )

    ranks = today_score.rank(
        ascending=False,
        method="first",
    )

    # Entry condition:
    # positive composite score AND relative trend above
    # its own long-term moving average.
    eligible = (
        (today_score > 0)
        &
        relative_trend_ok
    )

    selected = []

    # --------------------------------------------------------
    # HYSTERESIS
    #
    # Existing holdings can remain until their rank
    # deteriorates beyond KEEP_RANK.
    # --------------------------------------------------------

    held = list(
        current_satellite_weights[
            current_satellite_weights
            > 1e-10
        ].index
    )

    held = sorted(
        held,
        key=lambda x: (
            ranks.get(
                x,
                np.inf,
            )
        ),
    )

    for asset in held:

        if len(selected) >= MAX_SATELLITES:
            break

        if (
            pd.notna(
                ranks.get(asset)
            )
            and (
                ranks[asset]
                <= KEEP_RANK
            )
            and bool(
                eligible.get(
                    asset,
                    False,
                )
            )
            and can_add_asset(
                asset,
                selected,
            )
        ):

            selected.append(
                asset
            )

    # --------------------------------------------------------
    # Add new high-ranked candidates.
    # --------------------------------------------------------

    ordered = list(
        today_score
        .sort_values(
            ascending=False
        )
        .index
    )

    for asset in ordered:

        if len(selected) >= MAX_SATELLITES:
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
# TARGET WEIGHTS
# ============================================================

def build_target_satellite_weights(
    date: pd.Timestamp,
    current_satellite_weights: pd.Series,
    score: pd.DataFrame,
    components: dict,
) -> pd.Series:

    target = pd.Series(
        0.0,
        index=EQUITY_UNIVERSE,
        dtype=float,
    )

    selected = select_satellites(
        date=
            date,

        current_satellite_weights=
            current_satellite_weights,

        score=
            score,

        components=
            components,
    )

    if not selected:
        return target

    # --------------------------------------------------------
    # Equal weighting deliberately reduces estimation error
    # and unnecessary portfolio churn.
    # --------------------------------------------------------

    equal_weight = min(
        MAX_SATELLITE_WEIGHT,
        MAX_SATELLITE_TOTAL
        / len(selected),
    )

    for asset in selected:
        target[asset] = (
            equal_weight
        )

    return target


# ============================================================
# TURNOVER-AWARE EXECUTION
# ============================================================

def apply_turnover_threshold(
    current: pd.Series,
    desired: pd.Series,
) -> pd.Series:

    result = desired.copy()

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

        # If an asset is no longer selected,
        # allow the full exit.
        if new <= 1e-12:

            result[asset] = 0.0
            continue

        # Ignore small maintenance changes.
        if (
            old > 1e-12
            and abs(delta)
            < MINIMUM_TRADE_FRACTION
        ):

            result[asset] = old

        # Do not create microscopic new positions.
        elif (
            old <= 1e-12
            and abs(delta)
            < MINIMUM_TRADE_FRACTION
        ):

            result[asset] = 0.0

    result = result.clip(
        lower=0.0,
        upper=MAX_SATELLITE_WEIGHT,
    )

    satellite_total = float(
        result.sum()
    )

    if (
        satellite_total
        > MAX_SATELLITE_TOTAL
        and satellite_total > 0
    ):

        result *= (
            MAX_SATELLITE_TOTAL
            / satellite_total
        )

    return result


# ============================================================
# BACKTEST
# ============================================================

def run_v3(
    components: dict,
    score: pd.DataFrame,
    start_date: str,
    one_way_cost_bps: float,
) -> dict:

    asset_returns = (
        components[
            "asset_returns"
        ]
    )

    benchmark_returns = (
        components[
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
            "Insufficient data for V3."
        )

    satellite_weights = (
        pd.Series(
            0.0,
            index=EQUITY_UNIVERSE,
            dtype=float,
        )
    )

    pending_target = None

    nav = 100.0

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

        # Start the evaluation account at exactly £100.
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

        # ----------------------------------------------------
        # Portfolio return before transaction costs.
        # ----------------------------------------------------

        gross_portfolio_return = float(
            core_weight
            * benchmark_return
            +
            (
                satellite_weights
                * today_asset_returns
            ).sum()
        )

        # Exact gross incremental return from the overlay
        # relative to owning ACWI alone.
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
                "Invalid portfolio return."
            )

        # ----------------------------------------------------
        # Drift satellite weights with market movement.
        # ----------------------------------------------------

        satellite_weights = (
            satellite_weights
            * (
                1.0
                + today_asset_returns
            )
            / denominator
        )

        turnover_today = 0.0
        cost_today = 0.0

        # ----------------------------------------------------
        # Execute target generated at the PREVIOUS session's
        # close.
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

            executed_satellite = (
                apply_turnover_threshold(
                    current=
                        old_satellite,

                    desired=
                        pending_target,
                )
            )

            new_core = max(
                0.0,
                1.0
                - float(
                    executed_satellite.sum()
                ),
            )

            # Include both changes in the satellite sleeve
            # and the corresponding change in ACWI core.
            turnover_today = (
                float(
                    (
                        executed_satellite
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
                executed_satellite
            )

            pending_target = None

        # ----------------------------------------------------
        # Today's close can generate a signal,
        # but it cannot trade until the next session.
        # ----------------------------------------------------

        if is_signal_day(
            date
        ):

            pending_target = (
                build_target_satellite_weights(
                    date=
                        date,

                    current_satellite_weights=
                        satellite_weights,

                    score=
                        score,

                    components=
                        components,
                )
            )

        daily_net_return = (
            nav
            / nav_before_day
            - 1.0
        )

        cost_drag_return = (
            daily_net_return
            - gross_portfolio_return
        )

        active_return = (
            daily_net_return
            - benchmark_return
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

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,
        })

        weight_row = {
            "date":
                date,

            "ACWI_CORE":
                core_weight,
        }

        for asset in (
            EQUITY_UNIVERSE
        ):

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

        # Hard research invariants.
        total_weight = (
            core_weight
            + float(
                satellite_weights.sum()
            )
        )

        if abs(
            total_weight - 1.0
        ) > 1e-8:

            raise RuntimeError(
                "Portfolio weights "
                "do not sum to 1."
            )

        if (
            satellite_weights
            < -1e-12
        ).any():

            raise RuntimeError(
                "Negative satellite weight."
            )

        if (
            satellite_weights.max()
            > MAX_SATELLITE_WEIGHT
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite position cap breached."
            )

        if (
            satellite_weights.sum()
            > MAX_SATELLITE_TOTAL
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite sleeve cap breached."
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
        history[
            "active_return"
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
        history[
            "nav"
        ]
        .iloc[-1]
    )

    benchmark_final_nav = float(
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
            benchmark_final_nav
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

    tracking_error = (
        active.std(
            ddof=1
        )
        * math.sqrt(
            TRADING_DAYS
        )
    )

    information_ratio = (
        active.mean()
        / active.std(
            ddof=1
        )
        * math.sqrt(
            TRADING_DAYS
        )
        if (
            active.std(
                ddof=1
            )
            > 0
        )
        else np.nan
    )

    running_peak = (
        history[
            "nav"
        ]
        .cummax()
    )

    drawdown = (
        history[
            "nav"
        ]
        / running_peak
        - 1.0
    )

    max_drawdown = float(
        drawdown.min()
    )

    benchmark_peak = (
        history[
            "benchmark_nav"
        ]
        .cummax()
    )

    benchmark_drawdown = (
        history[
            "benchmark_nav"
        ]
        / benchmark_peak
        - 1.0
    )

    benchmark_max_drawdown = float(
        benchmark_drawdown.min()
    )

    benchmark_variance = (
        benchmark.var(
            ddof=1
        )
    )

    if benchmark_variance > 0:

        beta = (
            strategy.cov(
                benchmark
            )
            / benchmark_variance
        )

    else:

        beta = np.nan

    # --------------------------------------------------------
    # Benchmark-relative active-return significance.
    #
    # HAC/Newey-West standard errors account for some
    # autocorrelation / heteroskedasticity.
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

        annualised_active_return = (
            float(
                model.params[0]
            )
            * TRADING_DAYS
        )

        active_tstat = float(
            model.tvalues[0]
        )

    else:

        annualised_active_return = (
            np.nan
        )

        active_tstat = (
            np.nan
        )

    annual_turnover = (
        result[
            "total_turnover"
        ]
        / years
    )

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
            benchmark_final_nav,

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
            annualised_active_return,

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
    }


# ============================================================
# YEARLY ANALYSIS
# ============================================================

def yearly_results(
    history: pd.DataFrame,
) -> pd.DataFrame:

    def compound(
        series: pd.Series,
    ) -> float:

        return float(
            (
                1.0
                + series
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

    result.index.name = "year"

    return result


# ============================================================
# CHART
# ============================================================

def create_chart(
    history: pd.DataFrame,
) -> None:

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        gridspec_kw={
            "height_ratios":
                [3, 1]
        },
    )

    axes[0].plot(
        history.index,
        history[
            "nav"
        ],
        label=
            "Fund-100 V3",
        linewidth=2.0,
    )

    axes[0].plot(
        history.index,
        history[
            "benchmark_nav"
        ],
        label=
            "ACWI GBP proxy",
        linewidth=1.7,
    )

    axes[0].set_ylabel(
        "NAV (£)"
    )

    axes[0].set_title(
        "Fund-100 V3 "
        "Benchmark + Alpha Overlay"
    )

    axes[0].legend()

    axes[0].grid(
        alpha=0.25
    )

    relative_wealth = (
        history[
            "nav"
        ]
        / history[
            "benchmark_nav"
        ]
        - 1.0
    )

    axes[1].plot(
        history.index,
        relative_wealth,
        color="purple",
        linewidth=1.5,
    )

    axes[1].axhline(
        0.0,
        color="black",
        linewidth=0.8,
    )

    axes[1].fill_between(
        history.index,
        relative_wealth,
        0.0,
        where=(
            relative_wealth >= 0
        ),
        color="green",
        alpha=0.15,
    )

    axes[1].fill_between(
        history.index,
        relative_wealth,
        0.0,
        where=(
            relative_wealth < 0
        ),
        color="red",
        alpha=0.15,
    )

    axes[1].set_ylabel(
        "Relative wealth"
    )

    axes[1].grid(
        alpha=0.25
    )

    plt.tight_layout()

    fig.savefig(
        OUTPUT_DIR
        / "v3_equity_curve.png",
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
        "FUND-100 V3 BENCHMARK + ALPHA OVERLAY"
    )

    print(
        "============================================"
    )

    cfg, v1_hash = (
        load_config()
    )

    print(
        "\nFrozen v1 config SHA256:"
    )

    print(
        v1_hash
    )

    print(
        "\nDownloading market data..."
    )

    prices, benchmark = (
        download_prices(
            cfg
        )
    )

    missing_assets = [
        asset
        for asset in EQUITY_UNIVERSE
        if asset
        not in prices.columns
    ]

    if missing_assets:

        raise RuntimeError(
            "Missing V3 assets: "
            f"{missing_assets}"
        )

    print(
        f"\nMarket data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "\nBuilding benchmark-relative "
        "signal components..."
    )

    components = (
        build_signal_components(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    # ========================================================
    # BASE V3 COST SENSITIVITY
    # ========================================================

    base_score = (
        build_score(
            components=
                components,

            variant_name=
                "REL_MOM_QUALITY",
        )
    )

    cost_rows = []

    base_result_15 = None
    base_metrics_15 = None

    for cost_bps in [
        5,
        15,
        35,
    ]:

        print(
            f"\nRunning V3 at "
            f"{cost_bps} bps..."
        )

        result = run_v3(
            components=
                components,

            score=
                base_score,

            start_date=
                EVALUATION_START,

            one_way_cost_bps=
                float(
                    cost_bps
                ),
        )

        metrics = (
            calculate_metrics(
                result
            )
        )

        cost_rows.append({
            "variant":
                "REL_MOM_QUALITY",

            "cost_bps":
                cost_bps,

            **metrics,
        })

        if cost_bps == 15:

            base_result_15 = (
                result
            )

            base_metrics_15 = (
                metrics
            )

    cost_table = (
        pd.DataFrame(
            cost_rows
        )
    )

    cost_table.to_csv(
        OUTPUT_DIR
        / "v3_cost_sensitivity.csv",
        index=False,
    )

    # ========================================================
    # SIGNAL ABLATION AT BASE COST
    # ========================================================

    diagnostic_rows = []

    for variant_name in (
        VARIANTS.keys()
    ):

        print(
            f"\nDiagnostic test: "
            f"{variant_name}"
        )

        variant_score = (
            build_score(
                components=
                    components,

                variant_name=
                    variant_name,
            )
        )

        result = run_v3(
            components=
                components,

            score=
                variant_score,

            start_date=
                EVALUATION_START,

            one_way_cost_bps=
                15.0,
        )

        metrics = (
            calculate_metrics(
                result
            )
        )

        diagnostic_rows.append({
            "variant":
                variant_name,

            "cost_bps":
                15,

            **metrics,
        })

    diagnostics = (
        pd.DataFrame(
            diagnostic_rows
        )
    )

    diagnostics.to_csv(
        OUTPUT_DIR
        / "v3_signal_diagnostics.csv",
        index=False,
    )

    # ========================================================
    # BASE 15 BPS OUTPUTS
    # ========================================================

    history = (
        base_result_15[
            "history"
        ]
    )

    weights = (
        base_result_15[
            "weights"
        ]
    )

    history.to_csv(
        OUTPUT_DIR
        / "v3_daily_nav.csv"
    )

    weights.to_csv(
        OUTPUT_DIR
        / "v3_daily_weights.csv"
    )

    yearly = (
        yearly_results(
            history
        )
    )

    yearly.to_csv(
        OUTPUT_DIR
        / "v3_yearly_returns.csv"
    )

    latest = (
        weights
        .iloc[-1]
        .sort_values(
            ascending=False
        )
    )

    latest = (
        latest[
            latest
            > 0.000001
        ]
    )

    latest_df = (
        pd.DataFrame({
            "weight":
                latest
        })
    )

    latest_df.to_csv(
        OUTPUT_DIR
        / "v3_latest_weights.csv"
    )

    create_chart(
        history
    )

    years_beating = float(
        (
            yearly[
                "excess_return"
            ]
            > 0
        ).mean()
    )

    summary = {
        "research_version":
            (
                "Fund-100 v3 "
                "benchmark + alpha overlay"
            ),

        "evaluation_start":
            EVALUATION_START,

        "v1_config_sha256":
            v1_hash,

        "base_variant":
            "REL_MOM_QUALITY",

        "momentum_weight":
            MOMENTUM_WEIGHT,

        "quality_weight":
            QUALITY_WEIGHT,

        "satellite_cap":
            MAX_SATELLITE_TOTAL,

        "max_satellite_positions":
            MAX_SATELLITES,

        "rebalance_weeks":
            REBALANCE_WEEKS,

        "minimum_trade_fraction":
            MINIMUM_TRADE_FRACTION,

        "execution":
            (
                "Signal at close, "
                "execute after next "
                "trading-session return"
            ),

        "fraction_of_calendar_years_beating_acwi":
            years_beating,

        "metrics_15bps":
            base_metrics_15,
    }

    with (
        OUTPUT_DIR
        / "v3_summary.json"
    ).open("w") as f:

        json.dump(
            summary,
            f,
            indent=2,
            default=float,
        )

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    display_cols = [
        "variant",
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
    ]

    print(
        "\n============================================"
    )

    print(
        "V3 COST SENSITIVITY"
    )

    print(
        "============================================"
    )

    print(
        cost_table[
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
        "V3 SIGNAL DIAGNOSTICS - 15 BPS"
    )

    print(
        "============================================"
    )

    print(
        diagnostics[
            display_cols
        ]
        .sort_values(
            "excess_cagr",
            ascending=False,
        )
        .round(4)
        .to_string(
            index=False
        )
    )

    print(
        "\n============================================"
    )

    print(
        "V3 YEARLY RETURNS - 15 BPS"
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
        "LATEST SIMULATED V3 WEIGHTS"
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
        "V3 SUMMARY"
    )

    print(
        "============================================"
    )

    print(
        json.dumps(
            summary,
            indent=2,
            default=float,
        )
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
        "already observed 2010-2026."
    )

    print(
        "Genuinely unseen evidence begins "
        "with forward paper trading from "
        "September 2026 onward."
    )

    print(
        "\nFiles written to ./v3_outputs/"
    )


if __name__ == "__main__":
    main()

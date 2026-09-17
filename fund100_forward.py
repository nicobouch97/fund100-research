from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from fund100 import (
    load_config,
    download_prices,
)


# ============================================================
# FUND-100 FORWARD LAB
# ============================================================
#
# PURPOSE
#
# Maintain a frozen, append-only paper-research record for:
#
#   V3    = relative momentum + trend quality
#   V4    = dispersion-conditioned relative momentum
#   RM25  = fixed 25% relative-momentum overlay
#
# ACWI is the passive benchmark.
#
# NO LIVE TRADING.
# NO BROKER CONNECTION.
# NO API KEYS.
#
# Historical data through 2026-09-16 is considered observed.
# Forward performance begins strictly AFTER that cutoff.
# ============================================================


FORWARD_PROTOCOL_VERSION = "1.0"

HISTORICAL_CUTOFF = pd.Timestamp(
    "2026-09-16"
)

EVALUATION_START = pd.Timestamp(
    "2014-01-01"
)

PAPER_START_NAV = 100.0

ONE_WAY_COST_BPS = 15.0


# ============================================================
# OUTPUTS
# ============================================================

OUTPUT_DIR = Path(
    "forward_outputs"
)

OUTPUT_DIR.mkdir(
    exist_ok=True
)

LEDGER_PATH = (
    OUTPUT_DIR
    / "forward_ledger.csv"
)

MANIFEST_PATH = (
    OUTPUT_DIR
    / "forward_manifest.json"
)

STATE_PATH = (
    OUTPUT_DIR
    / "forward_state.json"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "latest_forward_report.json"
)


# ============================================================
# HISTORICAL LINEAGE
# ============================================================

V1_CONFIG_HASH = (
    "40ec767a1778c8e66f47a43193c2c3e37"
    "bd0833ef1597a17add8e822dbf3e5c0"
)

V4_HISTORICAL_RESEARCH_HASH = (
    "64f9ab20d459ca51acabaef5016b78858"
    "d8e58f16ef9cdd0040d22d7856e425c"
)


# ============================================================
# EQUITY OVERLAY UNIVERSE
# ============================================================

EQUITY_UNIVERSE = [
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
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

        ASSET_TO_GROUP[
            ticker
        ] = group_name


# ============================================================
# COMMON SIGNAL PARAMETERS
# ============================================================

MOMENTUM_HORIZONS = [
    63,
    126,
    252,
]

RELATIVE_TREND_FILTER_WINDOW = 200

QUALITY_WINDOW = 126

MAX_SATELLITES = 3

KEEP_RANK = 6

MAX_SATELLITE_POSITION = 0.125

MAX_SATELLITE_POSITION_DRIFT = 0.15

MAX_TOTAL_SATELLITE_DRIFT = 0.275

MINIMUM_TRADE_FRACTION = 0.025

REBALANCE_WEEKS = 4

SIGNAL_WEEKDAY = 2

REBALANCE_ANCHOR = pd.Timestamp(
    "2010-01-06"
)


# ============================================================
# V3 PARAMETERS
# ============================================================

V3_MOMENTUM_WEIGHT = 0.70

V3_QUALITY_WEIGHT = 0.30

V3_OVERLAY_CAP = 0.25


# ============================================================
# V4 PARAMETERS
# ============================================================

DISPERSION_LOOKBACK = 504

MEDIUM_DISPERSION_QUANTILE = 0.50

HIGH_DISPERSION_QUANTILE = 0.75

V4_LOW_OVERLAY = 0.10

V4_MEDIUM_OVERLAY = 0.175

V4_HIGH_OVERLAY = 0.25


# ============================================================
# RM25 PARAMETERS
# ============================================================

RM25_OVERLAY_CAP = 0.25


# ============================================================
# MODEL NAMES
# ============================================================

MODEL_V3 = "V3"

MODEL_V4 = "V4"

MODEL_RM25 = "RM25"

MODELS = [
    MODEL_V3,
    MODEL_V4,
    MODEL_RM25,
]


# ============================================================
# HASH HELPERS
# ============================================================

def sha256_text(
    text: str,
) -> str:

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_json(
    obj: dict,
) -> str:

    encoded = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )

    return sha256_text(
        encoded
    )


# ============================================================
# STRATEGY MANIFESTS
# ============================================================

def build_strategy_manifests() -> dict:

    common = {
        "equity_universe":
            EQUITY_UNIVERSE,

        "momentum_horizons":
            MOMENTUM_HORIZONS,

        "relative_trend_filter_window":
            RELATIVE_TREND_FILTER_WINDOW,

        "max_satellites":
            MAX_SATELLITES,

        "keep_rank":
            KEEP_RANK,

        "max_satellite_position":
            MAX_SATELLITE_POSITION,

        "minimum_trade_fraction":
            MINIMUM_TRADE_FRACTION,

        "rebalance_weeks":
            REBALANCE_WEEKS,

        "signal_weekday":
            SIGNAL_WEEKDAY,

        "execution":
            (
                "Close signal; execute after "
                "next completed session return"
            ),
    }

    return {
        MODEL_V3: {
            **common,

            "model":
                (
                    "Relative momentum plus "
                    "trend-quality overlay"
                ),

            "momentum_weight":
                V3_MOMENTUM_WEIGHT,

            "quality_weight":
                V3_QUALITY_WEIGHT,

            "quality_window":
                QUALITY_WINDOW,

            "overlay_cap":
                V3_OVERLAY_CAP,
        },

        MODEL_V4: {
            **common,

            "model":
                (
                    "Dispersion-conditioned "
                    "relative-momentum overlay"
                ),

            "dispersion_lookback":
                DISPERSION_LOOKBACK,

            "medium_quantile":
                MEDIUM_DISPERSION_QUANTILE,

            "high_quantile":
                HIGH_DISPERSION_QUANTILE,

            "low_overlay":
                V4_LOW_OVERLAY,

            "medium_overlay":
                V4_MEDIUM_OVERLAY,

            "high_overlay":
                V4_HIGH_OVERLAY,

            "historical_research_hash":
                V4_HISTORICAL_RESEARCH_HASH,
        },

        MODEL_RM25: {
            **common,

            "model":
                (
                    "Fixed 25 percent "
                    "relative-momentum overlay"
                ),

            "overlay_cap":
                RM25_OVERLAY_CAP,
        },
    }


def build_forward_manifest() -> dict:

    strategies = (
        build_strategy_manifests()
    )

    strategy_hashes = {
        model:
            sha256_json(
                strategies[
                    model
                ]
            )
        for model in MODELS
    }

    return {
        "protocol_version":
            FORWARD_PROTOCOL_VERSION,

        "historical_cutoff":
            str(
                HISTORICAL_CUTOFF.date()
            ),

        "paper_start_nav":
            PAPER_START_NAV,

        "one_way_cost_bps":
            ONE_WAY_COST_BPS,

        "v1_config_hash":
            V1_CONFIG_HASH,

        "v4_historical_research_hash":
            V4_HISTORICAL_RESEARCH_HASH,

        "models":
            strategies,

        "strategy_hashes":
            strategy_hashes,

        "forward_rule":
            (
                "Existing ledger observations "
                "must never be rewritten."
            ),

        "data_rule":
            (
                "Only daily market observations "
                "strictly before the current UTC "
                "calendar date are accepted."
            ),
    }


# ============================================================
# DATA
# ============================================================

def load_completed_market_data(
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

    prices = (
        prices.copy()
    )

    benchmark = (
        benchmark.copy()
    )

    today_utc = datetime.now(
        timezone.utc
    ).date()

    completed_mask = (
        prices.index.date
        < today_utc
    )

    prices = (
        prices.loc[
            completed_mask
        ]
        .copy()
    )

    benchmark = (
        benchmark.reindex(
            prices.index
        )
    )

    if prices.empty:

        raise RuntimeError(
            "No completed market data available."
        )

    missing_assets = [
        asset
        for asset in EQUITY_UNIVERSE
        if asset
        not in prices.columns
    ]

    if missing_assets:

        raise RuntimeError(
            "Missing required assets: "
            f"{missing_assets}"
        )

    if (
        HISTORICAL_CUTOFF
        not in prices.index
    ):

        raise RuntimeError(
            "Historical cutoff date is not "
            "present in market data."
        )

    required_prices = (
        prices[
            EQUITY_UNIVERSE
        ]
    )

    forward_region = (
        required_prices.loc[
            HISTORICAL_CUTOFF:
        ]
    )

    if (
        forward_region
        .isna()
        .any()
        .any()
    ):

        bad = (
            forward_region
            .isna()
            .stack()
        )

        bad = bad[
            bad
        ]

        raise RuntimeError(
            "Missing forward-region market data: "
            f"{list(bad.index[:5])}"
        )

    if (
        benchmark.loc[
            HISTORICAL_CUTOFF:
        ]
        .isna()
        .any()
    ):

        raise RuntimeError(
            "Missing benchmark data in "
            "forward region."
        )

    return (
        prices,
        benchmark,
    )


# ============================================================
# MARKET SNAPSHOT HASH
# ============================================================

def market_snapshot_hash(
    date: pd.Timestamp,
    prices: pd.DataFrame,
    benchmark: pd.Series,
) -> str:

    payload = {
        "date":
            str(
                date.date()
            ),

        "benchmark":
            (
                f"{float(benchmark.loc[date]):.8f}"
            ),

        "assets": {
            asset:
                f"{float(prices.loc[date, asset]):.8f}"

            for asset
            in EQUITY_UNIVERSE
        },
    }

    return sha256_json(
        payload
    )


# ============================================================
# CROSS-SECTIONAL STANDARDISATION
# ============================================================

def cross_sectional_zscore(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    means = (
        frame.mean(
            axis=1
        )
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

    relative_momentum_raw = (
        sum(
            raw_relative_components
        )
        / len(
            raw_relative_components
        )
    )

    relative_momentum_score = (
        sum(
            z_relative_components
        )
        / len(
            z_relative_components
        )
    )

    # --------------------------------------------------------
    # Relative price and long-term trend filter
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
    # V3 trend-quality signal
    # --------------------------------------------------------

    log_relative_price = (
        np.log(
            relative_price
        )
    )

    net_change = (
        log_relative_price
        - log_relative_price.shift(
            QUALITY_WINDOW
        )
    )

    path_length = (
        log_relative_price
        .diff()
        .abs()
        .rolling(
            QUALITY_WINDOW
        )
        .sum()
    )

    quality_raw = (
        net_change
        .div(
            path_length.replace(
                0.0,
                np.nan,
            )
        )
        .clip(
            lower=-1.0,
            upper=1.0,
        )
    )

    quality_score = (
        cross_sectional_zscore(
            quality_raw
        )
    )

    # --------------------------------------------------------
    # V4 dispersion state
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

        "relative_momentum_score":
            relative_momentum_score,

        "relative_price":
            relative_price,

        "relative_trend_ok":
            relative_trend_ok,

        "quality_raw":
            quality_raw,

        "quality_score":
            quality_score,

        "dispersion":
            dispersion,

        "medium_threshold":
            medium_threshold,

        "high_threshold":
            high_threshold,
    }


# ============================================================
# MODEL SCORE
# ============================================================

def score_for_model(
    signals: dict,
    model_name: str,
) -> pd.DataFrame:

    if model_name == MODEL_V3:

        return (
            V3_MOMENTUM_WEIGHT
            * signals[
                "relative_momentum_score"
            ]
            +
            V3_QUALITY_WEIGHT
            * signals[
                "quality_score"
            ]
        )

    if model_name in [
        MODEL_V4,
        MODEL_RM25,
    ]:

        return signals[
            "relative_momentum_score"
        ]

    raise RuntimeError(
        f"Unknown model: {model_name}"
    )


# ============================================================
# OVERLAY CAP
# ============================================================

def overlay_cap_for_model(
    date: pd.Timestamp,
    signals: dict,
    model_name: str,
) -> tuple[
    float,
    str,
]:

    if model_name == MODEL_V3:

        return (
            V3_OVERLAY_CAP,
            "FIXED_25",
        )

    if model_name == MODEL_RM25:

        return (
            RM25_OVERLAY_CAP,
            "FIXED_25",
        )

    if model_name != MODEL_V4:

        raise RuntimeError(
            f"Unknown model: {model_name}"
        )

    dispersion = float(
        signals[
            "dispersion"
        ]
        .loc[date]
    )

    medium = (
        signals[
            "medium_threshold"
        ]
        .loc[date]
    )

    high = (
        signals[
            "high_threshold"
        ]
        .loc[date]
    )

    if (
        pd.isna(
            medium
        )
        or pd.isna(
            high
        )
    ):

        return (
            V4_LOW_OVERLAY,
            "LOW",
        )

    if dispersion >= float(
        high
    ):

        return (
            V4_HIGH_OVERLAY,
            "HIGH",
        )

    if dispersion >= float(
        medium
    ):

        return (
            V4_MEDIUM_OVERLAY,
            "MEDIUM",
        )

    return (
        V4_LOW_OVERLAY,
        "LOW",
    )


# ============================================================
# SIGNAL DAY
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

    group_name = (
        group_of(
            asset
        )
    )

    limit = (
        GROUP_LIMITS.get(
            group_name,
            99,
        )
    )

    current_count = sum(
        1
        for existing
        in selected
        if group_of(
            existing
        )
        == group_name
    )

    return (
        current_count
        < limit
    )


# ============================================================
# SATELLITE SELECTION
# ============================================================

def select_satellites(
    date: pd.Timestamp,
    current_weights: pd.Series,
    signals: dict,
    model_name: str,
) -> list[str]:

    score = (
        score_for_model(
            signals=
                signals,

            model_name=
                model_name,
        )
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

    # Existing holdings receive hysteresis.
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

        if pd.isna(
            ranks.get(
                asset
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
# BUILD TARGET
# ============================================================

def build_target(
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
        overlay_cap_for_model(
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

            model_name=
                model_name,
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

        target[
            asset
        ] = equal_weight

    return (
        target,
        overlay_cap,
        regime,
    )


# ============================================================
# TURNOVER THRESHOLD
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
            current[
                asset
            ]
        )

        new = float(
            desired[
                asset
            ]
        )

        delta = (
            new - old
        )

        # Full exits are allowed.
        if new <= 1e-12:

            result[
                asset
            ] = 0.0

            continue

        # Suppress tiny new positions.
        if (
            old <= 1e-12
            and abs(
                delta
            )
            < MINIMUM_TRADE_FRACTION
        ):

            result[
                asset
            ] = 0.0

            continue

        # Ignore tiny maintenance changes.
        if (
            old > 1e-12
            and abs(
                delta
            )
            < MINIMUM_TRADE_FRACTION
        ):

            result[
                asset
            ] = old

    result = (
        result.clip(
            lower=0.0,
            upper=
                MAX_SATELLITE_POSITION,
        )
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
# EMPTY MODEL STATE
# ============================================================

def empty_state(
    model_name: str,
) -> dict:

    return {
        "model":
            model_name,

        "satellite_weights":
            pd.Series(
                0.0,
                index=EQUITY_UNIVERSE,
                dtype=float,
            ),

        "pending_target":
            None,

        "pending_cap":
            None,

        "pending_regime":
            None,

        "active_cap":
            0.0,

        "active_regime":
            "NONE",

        "nav":
            100.0,

        "benchmark_nav":
            100.0,

        "last_date":
            None,

        "days_processed":
            0,
    }


# ============================================================
# HARD RISK CHECK
# ============================================================

def check_drift_limits(
    weights: pd.Series,
) -> None:

    if (
        weights.sum()
        >
        MAX_TOTAL_SATELLITE_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Satellite sleeve exceeded "
            "27.5% hard drift limit."
        )

    if (
        weights.max()
        >
        MAX_SATELLITE_POSITION_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Satellite position exceeded "
            "15% hard drift limit."
        )

    if (
        weights
        < -1e-12
    ).any():

        raise RuntimeError(
            "Negative satellite weight detected."
        )


# ============================================================
# ONE-DAY STATE TRANSITION
# ============================================================

def process_one_day(
    state: dict,
    date: pd.Timestamp,
    signals: dict,
    model_name: str,
    cost_bps: float,
    zero_market_return: bool = False,
) -> dict:

    satellite_weights = (
        state[
            "satellite_weights"
        ].copy()
    )

    nav_before = float(
        state[
            "nav"
        ]
    )

    benchmark_nav_before = float(
        state[
            "benchmark_nav"
        ]
    )

    today_asset_returns = (
        signals[
            "asset_returns"
        ]
        .loc[date]
        .reindex(
            EQUITY_UNIVERSE
        )
        .fillna(0.0)
    )

    benchmark_return = (
        signals[
            "benchmark_returns"
        ]
        .loc[date]
    )

    if pd.isna(
        benchmark_return
    ):

        benchmark_return = 0.0

    benchmark_return = float(
        benchmark_return
    )

    if zero_market_return:

        benchmark_return = 0.0

        today_asset_returns = (
            today_asset_returns
            * 0.0
        )

    core_weight_before = max(
        0.0,
        1.0
        - float(
            satellite_weights.sum()
        ),
    )

    gross_portfolio_return = float(
        core_weight_before
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

    state[
        "nav"
    ] *= (
        1.0
        + gross_portfolio_return
    )

    state[
        "benchmark_nav"
    ] *= (
        1.0
        + benchmark_return
    )

    denominator = (
        1.0
        + gross_portfolio_return
    )

    if denominator <= 0:

        raise RuntimeError(
            "Invalid portfolio return denominator."
        )

    # --------------------------------------------------------
    # Natural market drift
    # --------------------------------------------------------

    satellite_weights = (
        satellite_weights
        * (
            1.0
            + today_asset_returns
        )
        / denominator
    )

    check_drift_limits(
        satellite_weights
    )

    turnover_today = 0.0

    cost_today = 0.0

    executed_pending = False

    # --------------------------------------------------------
    # Execute yesterday's pending target
    # AFTER today's market return.
    # --------------------------------------------------------

    if (
        state[
            "pending_target"
        ]
        is not None
    ):

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
                    state[
                        "pending_target"
                    ],

                target_overlay_cap=
                    float(
                        state[
                            "pending_cap"
                        ]
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

        cost_rate = (
            float(
                cost_bps
            )
            / 10_000.0
        )

        cost_today = (
            float(
                state[
                    "nav"
                ]
            )
            * turnover_today
            * cost_rate
        )

        state[
            "nav"
        ] -= (
            cost_today
        )

        satellite_weights = (
            executed
        )

        state[
            "active_cap"
        ] = float(
            state[
                "pending_cap"
            ]
        )

        state[
            "active_regime"
        ] = str(
            state[
                "pending_regime"
            ]
        )

        state[
            "pending_target"
        ] = None

        state[
            "pending_cap"
        ] = None

        state[
            "pending_regime"
        ] = None

        executed_pending = True

    # --------------------------------------------------------
    # Generate today's close signal
    # --------------------------------------------------------

    signal_generated = False

    if is_signal_day(
        date
    ):

        (
            target,
            target_cap,
            target_regime,
        ) = build_target(
            date=
                date,

            current_weights=
                satellite_weights,

            signals=
                signals,

            model_name=
                model_name,
        )

        state[
            "pending_target"
        ] = target

        state[
            "pending_cap"
        ] = float(
            target_cap
        )

        state[
            "pending_regime"
        ] = str(
            target_regime
        )

        signal_generated = True

    state[
        "satellite_weights"
    ] = (
        satellite_weights
    )

    state[
        "last_date"
    ] = (
        date
    )

    state[
        "days_processed"
    ] += 1

    daily_net_return = (
        float(
            state[
                "nav"
            ]
        )
        / nav_before
        - 1.0
    )

    benchmark_daily_return = (
        float(
            state[
                "benchmark_nav"
            ]
        )
        / benchmark_nav_before
        - 1.0
    )

    active_return = (
        daily_net_return
        - benchmark_daily_return
    )

    cost_drag_return = (
        daily_net_return
        - gross_portfolio_return
    )

    return {
        "daily_return":
            daily_net_return,

        "benchmark_return":
            benchmark_daily_return,

        "active_return":
            active_return,

        "gross_overlay_return":
            gross_overlay_return,

        "cost_drag_return":
            cost_drag_return,

        "turnover":
            turnover_today,

        "transaction_cost_gbp":
            cost_today,

        "signal_generated":
            signal_generated,

        "executed_pending":
            executed_pending,
    }


# ============================================================
# HISTORICAL BOOTSTRAP
# ============================================================

def bootstrap_model_to_cutoff(
    signals: dict,
    model_name: str,
) -> dict:

    state = (
        empty_state(
            model_name
        )
    )

    dates = (
        signals[
            "asset_returns"
        ]
        .index
    )

    dates = dates[
        (dates >= EVALUATION_START)
        &
        (dates <= HISTORICAL_CUTOFF)
    ]

    if len(
        dates
    ) < 2:

        raise RuntimeError(
            "Insufficient historical bootstrap data."
        )

    for i, date in enumerate(
        dates
    ):

        process_one_day(
            state=
                state,

            date=
                date,

            signals=
                signals,

            model_name=
                model_name,

            cost_bps=
                ONE_WAY_COST_BPS,

            zero_market_return=
                (
                    i == 0
                ),
        )

    # --------------------------------------------------------
    # Forward performance starts at £100.
    #
    # Holdings and pending target remain exactly as produced
    # by the frozen historical model.
    # --------------------------------------------------------

    state[
        "nav"
    ] = (
        PAPER_START_NAV
    )

    state[
        "benchmark_nav"
    ] = (
        PAPER_START_NAV
    )

    state[
        "last_date"
    ] = (
        HISTORICAL_CUTOFF
    )

    return state


# ============================================================
# SERIALISATION HELPERS
# ============================================================

def weights_to_dict(
    weights: pd.Series,
) -> dict:

    return {
        asset:
            float(
                weights.get(
                    asset,
                    0.0,
                )
            )

        for asset
        in EQUITY_UNIVERSE
    }


def target_to_dict(
    target,
):

    if target is None:

        return None

    return weights_to_dict(
        target
    )


def top_scores_for_date(
    signals: dict,
    model_name: str,
    date: pd.Timestamp,
) -> dict:

    score = (
        score_for_model(
            signals=
                signals,

            model_name=
                model_name,
        )
        .loc[date]
        .sort_values(
            ascending=False
        )
        .head(5)
    )

    return {
        asset:
            float(
                value
            )

        for asset, value
        in score.items()
        if pd.notna(
            value
        )
    }


# ============================================================
# LEDGER PAYLOAD
# ============================================================

def build_payload(
    row_type: str,
    state: dict,
    date: pd.Timestamp,
    model_name: str,
    strategy_hash: str,
    market_hash: str,
    signals: dict,
    daily: dict | None = None,
) -> dict:

    if daily is None:

        daily = {
            "daily_return":
                0.0,

            "benchmark_return":
                0.0,

            "active_return":
                0.0,

            "gross_overlay_return":
                0.0,

            "cost_drag_return":
                0.0,

            "turnover":
                0.0,

            "transaction_cost_gbp":
                0.0,

            "signal_generated":
                bool(
                    is_signal_day(
                        date
                    )
                ),

            "executed_pending":
                False,
        }

    sat = (
        state[
            "satellite_weights"
        ]
    )

    core_weight = max(
        0.0,
        1.0
        - float(
            sat.sum()
        ),
    )

    dispersion = (
        signals[
            "dispersion"
        ]
        .loc[date]
    )

    medium = (
        signals[
            "medium_threshold"
        ]
        .loc[date]
    )

    high = (
        signals[
            "high_threshold"
        ]
        .loc[date]
    )

    return {
        "row_type":
            row_type,

        "date":
            str(
                date.date()
            ),

        "strategy":
            model_name,

        "strategy_hash":
            strategy_hash,

        "market_snapshot_hash":
            market_hash,

        "nav":
            float(
                state[
                    "nav"
                ]
            ),

        "benchmark_nav":
            float(
                state[
                    "benchmark_nav"
                ]
            ),

        "daily_return":
            float(
                daily[
                    "daily_return"
                ]
            ),

        "benchmark_return":
            float(
                daily[
                    "benchmark_return"
                ]
            ),

        "active_return":
            float(
                daily[
                    "active_return"
                ]
            ),

        "gross_overlay_return":
            float(
                daily[
                    "gross_overlay_return"
                ]
            ),

        "cost_drag_return":
            float(
                daily[
                    "cost_drag_return"
                ]
            ),

        "turnover":
            float(
                daily[
                    "turnover"
                ]
            ),

        "transaction_cost_gbp":
            float(
                daily[
                    "transaction_cost_gbp"
                ]
            ),

        "core_weight":
            core_weight,

        "satellite_weight":
            float(
                sat.sum()
            ),

        "satellite_weights":
            weights_to_dict(
                sat
            ),

        "active_overlay_cap":
            float(
                state[
                    "active_cap"
                ]
            ),

        "active_regime":
            str(
                state[
                    "active_regime"
                ]
            ),

        "pending_target":
            target_to_dict(
                state[
                    "pending_target"
                ]
            ),

        "pending_overlay_cap":
            (
                None

                if state[
                    "pending_cap"
                ]
                is None

                else float(
                    state[
                        "pending_cap"
                    ]
                )
            ),

        "pending_regime":
            (
                None

                if state[
                    "pending_regime"
                ]
                is None

                else str(
                    state[
                        "pending_regime"
                    ]
                )
            ),

        "signal_generated":
            bool(
                daily[
                    "signal_generated"
                ]
            ),

        "executed_pending":
            bool(
                daily[
                    "executed_pending"
                ]
            ),

        "dispersion":
            (
                None

                if pd.isna(
                    dispersion
                )

                else float(
                    dispersion
                )
            ),

        "medium_dispersion_threshold":
            (
                None

                if pd.isna(
                    medium
                )

                else float(
                    medium
                )
            ),

        "high_dispersion_threshold":
            (
                None

                if pd.isna(
                    high
                )

                else float(
                    high
                )
            ),

        "top_signal_scores":
            top_scores_for_date(
                signals=
                    signals,

                model_name=
                    model_name,

                date=
                    date,
            ),
    }


# ============================================================
# LEDGER ROW
# ============================================================

def payload_to_ledger_row(
    payload: dict,
    previous_chain_hash: str,
) -> dict:

    payload_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )

    chain_hash = (
        sha256_text(
            previous_chain_hash
            + "|"
            + payload_json
        )
    )

    return {
        "date":
            payload[
                "date"
            ],

        "strategy":
            payload[
                "strategy"
            ],

        "row_type":
            payload[
                "row_type"
            ],

        "nav":
            payload[
                "nav"
            ],

        "benchmark_nav":
            payload[
                "benchmark_nav"
            ],

        "daily_return":
            payload[
                "daily_return"
            ],

        "benchmark_return":
            payload[
                "benchmark_return"
            ],

        "active_return":
            payload[
                "active_return"
            ],

        "core_weight":
            payload[
                "core_weight"
            ],

        "satellite_weight":
            payload[
                "satellite_weight"
            ],

        "turnover":
            payload[
                "turnover"
            ],

        "transaction_cost_gbp":
            payload[
                "transaction_cost_gbp"
            ],

        "signal_generated":
            payload[
                "signal_generated"
            ],

        "executed_pending":
            payload[
                "executed_pending"
            ],

        "market_snapshot_hash":
            payload[
                "market_snapshot_hash"
            ],

        "strategy_hash":
            payload[
                "strategy_hash"
            ],

        "previous_chain_hash":
            previous_chain_hash,

        "chain_hash":
            chain_hash,

        "payload_json":
            payload_json,
    }


# ============================================================
# SAVE MANIFEST
# ============================================================

def ensure_forward_manifest(
    manifest: dict,
) -> None:

    protocol_hash = (
        sha256_json(
            manifest
        )
    )

    if MANIFEST_PATH.exists():

        with (
            MANIFEST_PATH.open(
                "r"
            )
        ) as f:

            existing = (
                json.load(
                    f
                )
            )

        existing_hash = (
            existing.get(
                "protocol_hash"
            )
        )

        if (
            existing_hash
            != protocol_hash
        ):

            raise RuntimeError(
                "Forward manifest does not match "
                "the frozen strategy definitions. "
                "Refusing to continue."
            )

        return

    output = {
        **manifest,

        "protocol_hash":
            protocol_hash,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    with (
        MANIFEST_PATH.open(
            "w"
        )
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            default=float,
        )


# ============================================================
# INITIALISE LEDGER
# ============================================================

def initialise_ledger(
    signals: dict,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest: dict,
) -> tuple[
    pd.DataFrame,
    dict,
]:

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    rows = []

    states = {}

    snapshot_hash = (
        market_snapshot_hash(
            date=
                HISTORICAL_CUTOFF,

            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    for model_name in MODELS:

        state = (
            bootstrap_model_to_cutoff(
                signals=
                    signals,

                model_name=
                    model_name,
            )
        )

        states[
            model_name
        ] = state

        payload = (
            build_payload(
                row_type=
                    "BASELINE",

                state=
                    state,

                date=
                    HISTORICAL_CUTOFF,

                model_name=
                    model_name,

                strategy_hash=
                    strategy_hashes[
                        model_name
                    ],

                market_hash=
                    snapshot_hash,

                signals=
                    signals,

                daily=
                    None,
            )
        )

        row = (
            payload_to_ledger_row(
                payload=
                    payload,

                previous_chain_hash=
                    "GENESIS",
            )
        )

        rows.append(
            row
        )

    ledger = (
        pd.DataFrame(
            rows
        )
    )

    ledger.to_csv(
        LEDGER_PATH,
        index=False,
        float_format="%.12g",
    )

    return (
        ledger,
        states,
    )


# ============================================================
# VALIDATE EXISTING LEDGER
# ============================================================

def validate_existing_ledger(
    ledger: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest: dict,
) -> None:

    required = {
        "date",
        "strategy",
        "row_type",
        "chain_hash",
        "previous_chain_hash",
        "payload_json",
    }

    missing = (
        required
        - set(
            ledger.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Forward ledger is missing columns: "
            f"{sorted(missing)}"
        )

    duplicate_mask = (
        ledger.duplicated(
            subset=[
                "date",
                "strategy",
            ]
        )
    )

    if duplicate_mask.any():

        raise RuntimeError(
            "Duplicate strategy/date rows found "
            "in forward ledger."
        )

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    for model_name in MODELS:

        subset = (
            ledger[
                ledger[
                    "strategy"
                ]
                == model_name
            ]
            .copy()
        )

        if subset.empty:

            raise RuntimeError(
                f"Ledger missing model {model_name}."
            )

        subset[
            "date_dt"
        ] = pd.to_datetime(
            subset[
                "date"
            ]
        )

        subset = (
            subset.sort_values(
                "date_dt"
            )
        )

        first = (
            subset.iloc[0]
        )

        if (
            first[
                "row_type"
            ]
            != "BASELINE"
        ):

            raise RuntimeError(
                f"{model_name} does not begin "
                "with a BASELINE row."
            )

        if (
            pd.Timestamp(
                first[
                    "date"
                ]
            )
            != HISTORICAL_CUTOFF
        ):

            raise RuntimeError(
                f"{model_name} baseline date "
                "does not match cutoff."
            )

        expected_previous = (
            "GENESIS"
        )

        for _, row in subset.iterrows():

            payload_json = str(
                row[
                    "payload_json"
                ]
            )

            payload = json.loads(
                payload_json
            )

            if (
                payload[
                    "strategy"
                ]
                != model_name
            ):

                raise RuntimeError(
                    "Ledger payload strategy mismatch."
                )

            if (
                payload[
                    "strategy_hash"
                ]
                != strategy_hashes[
                    model_name
                ]
            ):

                raise RuntimeError(
                    f"{model_name} strategy hash changed. "
                    "Refusing to rewrite history."
                )

            if (
                str(
                    row[
                        "previous_chain_hash"
                    ]
                )
                != expected_previous
            ):

                raise RuntimeError(
                    f"{model_name} ledger chain broken."
                )

            expected_chain = (
                sha256_text(
                    expected_previous
                    + "|"
                    + payload_json
                )
            )

            if (
                expected_chain
                != str(
                    row[
                        "chain_hash"
                    ]
                )
            ):

                raise RuntimeError(
                    f"{model_name} ledger hash mismatch."
                )

            date = pd.Timestamp(
                payload[
                    "date"
                ]
            )

            if (
                date
                not in prices.index
            ):

                raise RuntimeError(
                    "Ledger date no longer exists "
                    "in downloaded market data."
                )

            current_market_hash = (
                market_snapshot_hash(
                    date=
                        date,

                    prices=
                        prices,

                    benchmark=
                        benchmark,
                )
            )

            if (
                current_market_hash
                != payload[
                    "market_snapshot_hash"
                ]
            ):

                raise RuntimeError(
                    "\nMARKET DATA REVISION DETECTED\n"
                    f"Date: {date.date()}\n"
                    f"Model: {model_name}\n"
                    "The current downloaded market data "
                    "does not match the snapshot originally "
                    "stored in the forward ledger.\n"
                    "The existing ledger has NOT been changed."
                )

            expected_previous = (
                expected_chain
            )

    dates_by_model = {}

    for model_name in MODELS:

        dates_by_model[
            model_name
        ] = set(
            ledger.loc[
                ledger[
                    "strategy"
                ]
                == model_name,
                "date",
            ]
        )

    reference = (
        dates_by_model[
            MODELS[0]
        ]
    )

    for model_name in MODELS[1:]:

        if (
            dates_by_model[
                model_name
            ]
            != reference
        ):

            raise RuntimeError(
                "Models do not contain identical "
                "forward observation dates."
            )


# ============================================================
# RESTORE STATE FROM LEDGER
# ============================================================

def restore_states_from_ledger(
    ledger: pd.DataFrame,
) -> dict:

    states = {}

    for model_name in MODELS:

        subset = (
            ledger[
                ledger[
                    "strategy"
                ]
                == model_name
            ]
            .copy()
        )

        subset[
            "date_dt"
        ] = pd.to_datetime(
            subset[
                "date"
            ]
        )

        subset = (
            subset.sort_values(
                "date_dt"
            )
        )

        last_row = (
            subset.iloc[-1]
        )

        payload = json.loads(
            str(
                last_row[
                    "payload_json"
                ]
            )
        )

        state = (
            empty_state(
                model_name
            )
        )

        state[
            "satellite_weights"
        ] = (
            pd.Series(
                payload[
                    "satellite_weights"
                ],
                dtype=float,
            )
            .reindex(
                EQUITY_UNIVERSE
            )
            .fillna(
                0.0
            )
        )

        pending = (
            payload[
                "pending_target"
            ]
        )

        if pending is None:

            state[
                "pending_target"
            ] = None

        else:

            state[
                "pending_target"
            ] = (
                pd.Series(
                    pending,
                    dtype=float,
                )
                .reindex(
                    EQUITY_UNIVERSE
                )
                .fillna(
                    0.0
                )
            )

        state[
            "pending_cap"
        ] = (
            payload[
                "pending_overlay_cap"
            ]
        )

        state[
            "pending_regime"
        ] = (
            payload[
                "pending_regime"
            ]
        )

        state[
            "active_cap"
        ] = float(
            payload[
                "active_overlay_cap"
            ]
        )

        state[
            "active_regime"
        ] = str(
            payload[
                "active_regime"
            ]
        )

        state[
            "nav"
        ] = float(
            payload[
                "nav"
            ]
        )

        state[
            "benchmark_nav"
        ] = float(
            payload[
                "benchmark_nav"
            ]
        )

        state[
            "last_date"
        ] = pd.Timestamp(
            payload[
                "date"
            ]
        )

        states[
            model_name
        ] = state

    return states


# ============================================================
# PREVIOUS CHAIN HASHES
# ============================================================

def latest_chain_hashes(
    ledger: pd.DataFrame,
) -> dict:

    result = {}

    for model_name in MODELS:

        subset = (
            ledger[
                ledger[
                    "strategy"
                ]
                == model_name
            ]
            .copy()
        )

        subset[
            "date_dt"
        ] = pd.to_datetime(
            subset[
                "date"
            ]
        )

        subset = (
            subset.sort_values(
                "date_dt"
            )
        )

        result[
            model_name
        ] = str(
            subset.iloc[-1][
                "chain_hash"
            ]
        )

    return result


# ============================================================
# APPEND NEW COMPLETED SESSIONS
# ============================================================

def append_new_sessions(
    ledger: pd.DataFrame,
    states: dict,
    signals: dict,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest: dict,
) -> tuple[
    pd.DataFrame,
    dict,
    int,
]:

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    last_dates = {
        model:
            states[
                model
            ][
                "last_date"
            ]

        for model
        in MODELS
    }

    if len(
        set(
            last_dates.values()
        )
    ) != 1:

        raise RuntimeError(
            "Model states have different "
            "last processed dates."
        )

    last_date = (
        list(
            last_dates.values()
        )[0]
    )

    new_dates = (
        prices.index[
            prices.index
            > last_date
        ]
    )

    if len(
        new_dates
    ) == 0:

        return (
            ledger,
            states,
            0,
        )

    previous_hashes = (
        latest_chain_hashes(
            ledger
        )
    )

    new_rows = []

    for date in new_dates:

        snapshot = (
            market_snapshot_hash(
                date=
                    date,

                prices=
                    prices,

                benchmark=
                    benchmark,
            )
        )

        for model_name in MODELS:

            state = (
                states[
                    model_name
                ]
            )

            daily = (
                process_one_day(
                    state=
                        state,

                    date=
                        date,

                    signals=
                        signals,

                    model_name=
                        model_name,

                    cost_bps=
                        ONE_WAY_COST_BPS,

                    zero_market_return=
                        False,
                )
            )

            payload = (
                build_payload(
                    row_type=
                        "FORWARD",

                    state=
                        state,

                    date=
                        date,

                    model_name=
                        model_name,

                    strategy_hash=
                        strategy_hashes[
                            model_name
                        ],

                    market_hash=
                        snapshot,

                    signals=
                        signals,

                    daily=
                        daily,
                )
            )

            row = (
                payload_to_ledger_row(
                    payload=
                        payload,

                    previous_chain_hash=
                        previous_hashes[
                            model_name
                        ],
                )
            )

            previous_hashes[
                model_name
            ] = (
                row[
                    "chain_hash"
                ]
            )

            new_rows.append(
                row
            )

    if new_rows:

        ledger = pd.concat(
            [
                ledger,
                pd.DataFrame(
                    new_rows
                ),
            ],
            ignore_index=True,
        )

        ledger[
            "date_dt"
        ] = pd.to_datetime(
            ledger[
                "date"
            ]
        )

        ledger = (
            ledger
            .sort_values(
                [
                    "date_dt",
                    "strategy",
                ]
            )
            .drop(
                columns=[
                    "date_dt"
                ]
            )
            .reset_index(
                drop=True
            )
        )

        ledger.to_csv(
            LEDGER_PATH,
            index=False,
            float_format="%.12g",
        )

    return (
        ledger,
        states,
        len(
            new_dates
        ),
    )


# ============================================================
# SAVE STATE SNAPSHOT
# ============================================================

def save_state_snapshot(
    states: dict,
    manifest: dict,
) -> None:

    output = {
        "updated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "historical_cutoff":
            str(
                HISTORICAL_CUTOFF.date()
            ),

        "protocol_hash":
            sha256_json(
                manifest
            ),

        "models": {},
    }

    for model_name in MODELS:

        state = (
            states[
                model_name
            ]
        )

        output[
            "models"
        ][
            model_name
        ] = {
            "last_date":
                str(
                    state[
                        "last_date"
                    ].date()
                ),

            "nav":
                float(
                    state[
                        "nav"
                    ]
                ),

            "benchmark_nav":
                float(
                    state[
                        "benchmark_nav"
                    ]
                ),

            "satellite_weights":
                weights_to_dict(
                    state[
                        "satellite_weights"
                    ]
                ),

            "active_overlay_cap":
                float(
                    state[
                        "active_cap"
                    ]
                ),

            "active_regime":
                str(
                    state[
                        "active_regime"
                    ]
                ),

            "pending_target":
                target_to_dict(
                    state[
                        "pending_target"
                    ]
                ),

            "pending_overlay_cap":
                state[
                    "pending_cap"
                ],

            "pending_regime":
                state[
                    "pending_regime"
                ],
        }

    with (
        STATE_PATH.open(
            "w"
        )
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
            default=float,
        )


# ============================================================
# FORMAT WEIGHTS
# ============================================================

def compact_weights(
    weights: pd.Series,
    include_core: bool = True,
) -> str:

    active = (
        weights[
            weights
            > 0.0005
        ]
        .sort_values(
            ascending=False
        )
    )

    parts = []

    if include_core:

        core = max(
            0.0,
            1.0
            - float(
                weights.sum()
            ),
        )

        parts.append(
            f"ACWI_CORE={core:.2%}"
        )

    for asset, value in active.items():

        parts.append(
            f"{asset}={float(value):.2%}"
        )

    if not parts:

        return "None"

    return ", ".join(
        parts
    )


def compact_pending(
    state: dict,
) -> str:

    target = (
        state[
            "pending_target"
        ]
    )

    if target is None:

        return "None"

    active = (
        target[
            target
            > 0.0005
        ]
        .sort_values(
            ascending=False
        )
    )

    parts = [
        f"{asset}={float(value):.2%}"

        for asset, value
        in active.items()
    ]

    if not parts:

        parts = [
            "100% ACWI core"
        ]

    return (
        ", ".join(
            parts
        )
        +
        " | cap="
        +
        f"{float(state['pending_cap']):.1%}"
        +
        " | regime="
        +
        str(
            state[
                "pending_regime"
            ]
        )
    )


# ============================================================
# REPORT
# ============================================================

def build_latest_report(
    states: dict,
    prices: pd.DataFrame,
    signals: dict,
    new_session_count: int,
    manifest: dict,
) -> dict:

    latest_date = (
        prices.index[-1]
    )

    report = {
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "latest_completed_market_date":
            str(
                latest_date.date()
            ),

        "historical_cutoff":
            str(
                HISTORICAL_CUTOFF.date()
            ),

        "new_sessions_appended":
            int(
                new_session_count
            ),

        "one_way_cost_bps":
            ONE_WAY_COST_BPS,

        "models": {},
    }

    for model_name in MODELS:

        state = (
            states[
                model_name
            ]
        )

        active_since_start = (
            float(
                state[
                    "nav"
                ]
            )
            / float(
                state[
                    "benchmark_nav"
                ]
            )
            - 1.0
        )

        report[
            "models"
        ][
            model_name
        ] = {
            "strategy_hash":
                manifest[
                    "strategy_hashes"
                ][
                    model_name
                ],

            "last_processed_date":
                str(
                    state[
                        "last_date"
                    ].date()
                ),

            "paper_nav":
                float(
                    state[
                        "nav"
                    ]
                ),

            "benchmark_nav":
                float(
                    state[
                        "benchmark_nav"
                    ]
                ),

            "relative_wealth_vs_acwi":
                active_since_start,

            "executed_holdings":
                weights_to_dict(
                    state[
                        "satellite_weights"
                    ]
                ),

            "active_overlay_cap":
                float(
                    state[
                        "active_cap"
                    ]
                ),

            "active_regime":
                str(
                    state[
                        "active_regime"
                    ]
                ),

            "pending_target":
                target_to_dict(
                    state[
                        "pending_target"
                    ]
                ),

            "pending_overlay_cap":
                state[
                    "pending_cap"
                ],

            "pending_regime":
                state[
                    "pending_regime"
                ],
        }

    with (
        REPORT_PATH.open(
            "w"
        )
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            default=float,
        )

    return report


# ============================================================
# PRINT REPORT
# ============================================================

def print_report(
    states: dict,
    prices: pd.DataFrame,
    signals: dict,
    manifest: dict,
    new_session_count: int,
) -> None:

    latest_date = (
        prices.index[-1]
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 FORWARD LAB STATUS"
    )

    print(
        "============================================"
    )

    print(
        f"Historical cutoff: "
        f"{HISTORICAL_CUTOFF.date()}"
    )

    print(
        f"Latest completed market date: "
        f"{latest_date.date()}"
    )

    print(
        f"New forward sessions appended: "
        f"{new_session_count}"
    )

    print(
        f"Paper starting NAV: "
        f"£{PAPER_START_NAV:.2f}"
    )

    print(
        f"One-way simulated cost: "
        f"{ONE_WAY_COST_BPS:.1f} bps"
    )

    print(
        "\nStrategy hashes:"
    )

    for model_name in MODELS:

        print(
            f"{model_name}: "
            f"{manifest['strategy_hashes'][model_name]}"
        )

    print(
        "\n============================================"
    )

    print(
        "LATEST PAPER STATES"
    )

    print(
        "============================================"
    )

    for model_name in MODELS:

        state = (
            states[
                model_name
            ]
        )

        relative_wealth = (
            float(
                state[
                    "nav"
                ]
            )
            / float(
                state[
                    "benchmark_nav"
                ]
            )
            - 1.0
        )

        print(
            f"\n{model_name}"
        )

        print(
            f"Last processed date: "
            f"{state['last_date'].date()}"
        )

        print(
            f"Paper NAV: "
            f"£{float(state['nav']):.4f}"
        )

        print(
            f"ACWI benchmark NAV: "
            f"£{float(state['benchmark_nav']):.4f}"
        )

        print(
            f"Relative wealth vs ACWI: "
            f"{relative_wealth:+.4%}"
        )

        print(
            "Executed holdings:"
        )

        print(
            compact_weights(
                state[
                    "satellite_weights"
                ]
            )
        )

        print(
            f"Active overlay cap/regime: "
            f"{float(state['active_cap']):.1%} "
            f"/ {state['active_regime']}"
        )

        print(
            "Pending next-session target:"
        )

        print(
            compact_pending(
                state
            )
        )

    print(
        "\n============================================"
    )

    print(
        "LATEST COMPLETED-DATE SIGNAL DIAGNOSTICS"
    )

    print(
        "============================================"
    )

    dispersion = (
        signals[
            "dispersion"
        ]
        .loc[
            latest_date
        ]
    )

    medium = (
        signals[
            "medium_threshold"
        ]
        .loc[
            latest_date
        ]
    )

    high = (
        signals[
            "high_threshold"
        ]
        .loc[
            latest_date
        ]
    )

    print(
        f"Date: "
        f"{latest_date.date()}"
    )

    print(
        f"Cross-sectional dispersion: "
        f"{float(dispersion):.6f}"
    )

    if pd.notna(
        medium
    ):

        print(
            f"Trailing median dispersion: "
            f"{float(medium):.6f}"
        )

    if pd.notna(
        high
    ):

        print(
            f"Trailing 75th percentile: "
            f"{float(high):.6f}"
        )

    for model_name in MODELS:

        score = (
            score_for_model(
                signals=
                    signals,

                model_name=
                    model_name,
            )
            .loc[
                latest_date
            ]
            .sort_values(
                ascending=False
            )
            .head(5)
        )

        print(
            f"\nTop {model_name} scores:"
        )

        print(
            score
            .round(4)
            .to_string()
        )

    print(
        "\n============================================"
    )

    print(
        "LEDGER INTEGRITY"
    )

    print(
        "============================================"
    )

    print(
        f"Ledger: {LEDGER_PATH}"
    )

    print(
        f"Manifest: {MANIFEST_PATH}"
    )

    print(
        f"State snapshot: {STATE_PATH}"
    )

    print(
        f"Latest report: {REPORT_PATH}"
    )

    print(
        "Existing observations were validated "
        "before any new rows were appended."
    )

    print(
        "Previously recorded dates are never "
        "rewritten by this program."
    )

    print(
        "Stored market-data hashes are checked "
        "for historical vendor revisions."
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
        "This is paper research only."
    )

    print(
        "No orders were sent anywhere."
    )

    print(
        "Executed holdings and pending targets "
        "are simulated research states."
    )

    print(
        "The first genuine forward performance "
        "observation must occur after "
        f"{HISTORICAL_CUTOFF.date()}."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 FORWARD LAB"
    )

    print(
        "============================================"
    )

    print(
        f"\nProtocol version: "
        f"{FORWARD_PROTOCOL_VERSION}"
    )

    print(
        f"Historical research cutoff: "
        f"{HISTORICAL_CUTOFF.date()}"
    )

    print(
        "\nLoading frozen configuration..."
    )

    cfg, config_hash = (
        load_config()
    )

    print(
        f"Loaded v1 config hash:"
    )

    print(
        config_hash
    )

    if (
        config_hash
        != V1_CONFIG_HASH
    ):

        raise RuntimeError(
            "Frozen v1 configuration hash changed. "
            "Forward Lab refuses to continue."
        )

    manifest = (
        build_forward_manifest()
    )

    protocol_hash = (
        sha256_json(
            manifest
        )
    )

    print(
        "\nForward protocol SHA256:"
    )

    print(
        protocol_hash
    )

    ensure_forward_manifest(
        manifest
    )

    print(
        "\nDownloading completed market data..."
    )

    prices, benchmark = (
        load_completed_market_data(
            cfg
        )
    )

    print(
        f"Completed market data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "\nBuilding frozen signals..."
    )

    signals = (
        build_signals(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    # --------------------------------------------------------
    # New Forward Lab
    # --------------------------------------------------------

    if not LEDGER_PATH.exists():

        print(
            "\nNo existing forward ledger found."
        )

        print(
            "Reconstructing frozen model state "
            "through the historical cutoff..."
        )

        (
            ledger,
            states,
        ) = initialise_ledger(
            signals=
                signals,

            prices=
                prices,

            benchmark=
                benchmark,

            manifest=
                manifest,
        )

        print(
            "Baseline forward ledger created."
        )

    # --------------------------------------------------------
    # Existing Forward Lab
    # --------------------------------------------------------

    else:

        print(
            "\nExisting forward ledger found."
        )

        ledger = pd.read_csv(
            LEDGER_PATH
        )

        print(
            "Validating append-only chain and "
            "stored market snapshots..."
        )

        validate_existing_ledger(
            ledger=
                ledger,

            prices=
                prices,

            benchmark=
                benchmark,

            manifest=
                manifest,
        )

        print(
            "Ledger integrity checks passed."
        )

        states = (
            restore_states_from_ledger(
                ledger
            )
        )

    # --------------------------------------------------------
    # Append any newly completed trading sessions
    # --------------------------------------------------------

    (
        ledger,
        states,
        new_session_count,
    ) = append_new_sessions(
        ledger=
            ledger,

        states=
            states,

        signals=
            signals,

        prices=
            prices,

        benchmark=
            benchmark,

        manifest=
            manifest,
    )

    # Revalidate after writing.
    validate_existing_ledger(
        ledger=
            ledger,

        prices=
            prices,

        benchmark=
            benchmark,

        manifest=
            manifest,
    )

    save_state_snapshot(
        states=
            states,

        manifest=
            manifest,
    )

    build_latest_report(
        states=
            states,

        prices=
            prices,

        signals=
            signals,

        new_session_count=
            new_session_count,

        manifest=
            manifest,
    )

    print_report(
        states=
            states,

        prices=
            prices,

        signals=
            signals,

        manifest=
            manifest,

        new_session_count=
            new_session_count,
    )

    print(
        "\n============================================"
    )

    print(
        "FORWARD LAB RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()

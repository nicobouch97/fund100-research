from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from fund100 import (
    load_config,
    download_prices,
)


# ============================================================
# FUND-100 AUTONOMOUS RESEARCH LAB
# ============================================================
#
# This program runs PRE-REGISTERED challenger experiments.
#
# It does NOT:
#
# - modify Forward Lab strategies
# - promote strategies automatically
# - connect to a broker
# - place orders
# - erase failed experiments
#
# Historical research data are frozen at 2026-09-16.
# ============================================================


PROTOCOL_PATH = Path(
    "research_lab/experiment_protocol.json"
)

REGISTRY_PATH = Path(
    "research_lab/experiment_registry.csv"
)

CHALLENGER_DIR = Path(
    "research_lab/challengers"
)

RESULTS_DIR = Path(
    "research_lab/results"
)

DATA_MANIFEST_PATH = Path(
    "research_lab/historical_data_manifest.json"
)

LATEST_REPORT_PATH = Path(
    "research_lab/latest_research_report.json"
)


RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


TRADING_DAYS = 252

START_NAV = 100.0


# ============================================================
# FROZEN RM25 RESEARCH ARCHITECTURE
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


MOMENTUM_HORIZONS = [
    63,
    126,
    252,
]

RELATIVE_TREND_FILTER_WINDOW = 200

MAX_SATELLITES = 3

KEEP_RANK = 6

MAX_OVERLAY = 0.25

MAX_SATELLITE_POSITION = 0.125

MAX_TOTAL_DRIFT = 0.275

MAX_POSITION_DRIFT = 0.15

MINIMUM_TRADE_FRACTION = 0.025

SIGNAL_WEEKDAY = 2

REBALANCE_ANCHOR = pd.Timestamp(
    "2010-01-06"
)


# ============================================================
# HASHING
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
    obj,
) -> str:

    text = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )

    return sha256_text(
        text
    )


# ============================================================
# PROTOCOL
# ============================================================

def load_protocol() -> dict:

    if not PROTOCOL_PATH.exists():
        raise RuntimeError(
            "Experiment protocol not found."
        )

    with PROTOCOL_PATH.open(
        "r"
    ) as f:
        protocol = json.load(
            f
        )

    required = [
        "protocol_version",
        "historical_cutoff",
        "evaluation_start",
        "base_cost_bps",
        "cost_scenarios_bps",
        "max_experiments_per_run",
    ]

    for key in required:
        if key not in protocol:
            raise RuntimeError(
                f"Protocol missing key: {key}"
            )

    return protocol


# ============================================================
# REGISTRY
# ============================================================

REGISTRY_COLUMNS = [
    "experiment_id",
    "run_utc",
    "status",
    "spec_hash",
    "protocol_hash",
    "data_hash",
    "result_file",
    "previous_chain_hash",
    "chain_hash",
    "payload_json",
]


def load_registry() -> pd.DataFrame:

    if not REGISTRY_PATH.exists():
        raise RuntimeError(
            "Experiment registry not found."
        )

    registry = pd.read_csv(
        REGISTRY_PATH,
        dtype=str,
    )

    missing = (
        set(
            REGISTRY_COLUMNS
        )
        - set(
            registry.columns
        )
    )

    if missing:
        raise RuntimeError(
            "Experiment registry missing columns: "
            f"{sorted(missing)}"
        )

    return registry[
        REGISTRY_COLUMNS
    ].copy()


def validate_registry(
    registry: pd.DataFrame,
) -> None:

    if registry.empty:
        return

    if registry[
        "experiment_id"
    ].duplicated().any():

        raise RuntimeError(
            "Duplicate experiment IDs found."
        )

    expected_previous = (
        "GENESIS"
    )

    for _, row in registry.iterrows():

        payload_json = str(
            row[
                "payload_json"
            ]
        )

        payload = json.loads(
            payload_json
        )

        if (
            str(
                row[
                    "experiment_id"
                ]
            )
            != str(
                payload[
                    "experiment_id"
                ]
            )
        ):

            raise RuntimeError(
                "Registry payload experiment "
                "ID mismatch."
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
                "Experiment registry chain broken."
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
                "Experiment registry hash mismatch."
            )

        expected_previous = (
            expected_chain
        )


# ============================================================
# CHALLENGER SPECS
# ============================================================

def load_specs() -> list[
    tuple[
        Path,
        dict,
        str,
    ]
]:

    if not CHALLENGER_DIR.exists():

        raise RuntimeError(
            "Challenger directory not found."
        )

    specs = []

    for path in sorted(
        CHALLENGER_DIR.glob(
            "*.json"
        )
    ):

        with path.open(
            "r"
        ) as f:

            spec = json.load(
                f
            )

        required = [
            "experiment_id",
            "hypothesis",
            "control",
            "candidate",
            "acceptance_criteria",
        ]

        for key in required:

            if key not in spec:

                raise RuntimeError(
                    f"{path} missing {key}"
                )

        experiment_id = str(
            spec[
                "experiment_id"
            ]
        )

        if not experiment_id.startswith(
            "V"
        ):

            raise RuntimeError(
                f"Invalid experiment ID: "
                f"{experiment_id}"
            )

        spec_hash = (
            sha256_json(
                spec
            )
        )

        specs.append(
            (
                path,
                spec,
                spec_hash,
            )
        )

    return specs


def validate_completed_specs(
    registry: pd.DataFrame,
    specs,
) -> None:

    if registry.empty:
        return

    completed = {
        str(
            row[
                "experiment_id"
            ]
        ):
            str(
                row[
                    "spec_hash"
                ]
            )

        for _, row
        in registry.iterrows()
    }

    for _, spec, spec_hash in specs:

        experiment_id = str(
            spec[
                "experiment_id"
            ]
        )

        if (
            experiment_id
            in completed
            and completed[
                experiment_id
            ]
            != spec_hash
        ):

            raise RuntimeError(
                f"Completed experiment "
                f"{experiment_id} was modified. "
                "Refusing to continue."
            )


# ============================================================
# DATA
# ============================================================

def load_historical_data(
    cfg: dict,
    protocol: dict,
) -> tuple[
    pd.DataFrame,
    pd.Series,
]:

    prices, benchmark = (
        download_prices(
            cfg
        )
    )

    cutoff = pd.Timestamp(
        protocol[
            "historical_cutoff"
        ]
    )

    prices = (
        prices.loc[
            prices.index
            <= cutoff
        ]
        .copy()
    )

    benchmark = (
        benchmark
        .reindex(
            prices.index
        )
        .copy()
    )

    if prices.empty:

        raise RuntimeError(
            "Historical data are empty."
        )

    if (
        prices.index[-1]
        != cutoff
    ):

        raise RuntimeError(
            "Historical cutoff is not present "
            "in market data."
        )

    missing_assets = [
        asset
        for asset in EQUITY_UNIVERSE
        if asset
        not in prices.columns
    ]

    if missing_assets:

        raise RuntimeError(
            "Missing research assets: "
            f"{missing_assets}"
        )

    evaluation_start = pd.Timestamp(
        protocol[
            "evaluation_start"
        ]
    )

    evaluation_prices = (
        prices.loc[
            evaluation_start:
        ][
            EQUITY_UNIVERSE
        ]
    )

    if (
        evaluation_prices
        .isna()
        .any()
        .any()
    ):

        raise RuntimeError(
            "Missing prices in evaluation period."
        )

    if (
        benchmark.loc[
            evaluation_start:
        ]
        .isna()
        .any()
    ):

        raise RuntimeError(
            "Missing benchmark prices "
            "in evaluation period."
        )

    return (
        prices,
        benchmark,
    )


# ============================================================
# HISTORICAL DATA HASH
# ============================================================

def calculate_data_hash(
    prices: pd.DataFrame,
    benchmark: pd.Series,
) -> str:

    data = (
        prices[
            EQUITY_UNIVERSE
        ]
        .copy()
    )

    data[
        "ACWI_BENCHMARK"
    ] = benchmark

    text = data.to_csv(
        index=True,
        float_format="%.10f",
    )

    return sha256_text(
        text
    )


def ensure_data_manifest(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    protocol: dict,
) -> str:

    data_hash = (
        calculate_data_hash(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    if DATA_MANIFEST_PATH.exists():

        with DATA_MANIFEST_PATH.open(
            "r"
        ) as f:

            existing = json.load(
                f
            )

        if (
            existing[
                "data_hash"
            ]
            != data_hash
        ):

            raise RuntimeError(
                "\nHISTORICAL DATA REVISION DETECTED\n"
                "The downloaded historical dataset "
                "no longer matches the dataset used "
                "by the Research Lab.\n"
                "No experiment has been run."
            )

        return data_hash

    manifest = {
        "historical_cutoff":
            protocol[
                "historical_cutoff"
            ],

        "first_market_date":
            str(
                prices.index[
                    0
                ].date()
            ),

        "last_market_date":
            str(
                prices.index[
                    -1
                ].date()
            ),

        "assets":
            EQUITY_UNIVERSE,

        "data_hash":
            data_hash,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    with DATA_MANIFEST_PATH.open(
        "w"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    return data_hash


# ============================================================
# SIGNALS
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

    components = []

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

        components.append(
            cross_sectional_zscore(
                relative_return
            )
        )

    score = (
        sum(
            components
        )
        / len(
            components
        )
    )

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

        "score":
            score,

        "relative_trend_ok":
            relative_trend_ok,

        "asset_returns":
            asset_returns,

        "benchmark_returns":
            benchmark_returns,
    }


# ============================================================
# REBALANCE SCHEDULE
# ============================================================

def is_signal_day(
    date: pd.Timestamp,
    rebalance_weeks: int,
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
        % int(
            rebalance_weeks
        )
        == 0
    )


# ============================================================
# GROUP CONSTRAINTS
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

    limit = GROUP_LIMITS.get(
        group_name,
        99,
    )

    existing = sum(
        1
        for name in selected
        if (
            group_of(
                name
            )
            == group_name
        )
    )

    return (
        existing
        < limit
    )


# ============================================================
# RM25 SATELLITE SELECTION
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

    # --------------------------------------------------------
    # Existing holdings receive the same hysteresis used by
    # RM25 in the frozen Forward Lab.
    # --------------------------------------------------------

    for asset in held:

        if (
            len(
                selected
            )
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
            ranks[
                asset
            ]
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
    # Fill any empty slots with the strongest eligible assets.
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
            len(
                selected
            )
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
# TARGET WEIGHTS
# ============================================================

def build_target(
    date: pd.Timestamp,
    current_weights: pd.Series,
    signals: dict,
) -> pd.Series:

    target = pd.Series(
        0.0,
        index=EQUITY_UNIVERSE,
        dtype=float,
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

        return target

    equal_weight = min(
        MAX_SATELLITE_POSITION,
        MAX_OVERLAY
        / len(
            selected
        ),
    )

    for asset in selected:

        target[
            asset
        ] = equal_weight

    return target


# ============================================================
# TRADE THRESHOLD
# ============================================================

def apply_trade_threshold(
    current: pd.Series,
    desired: pd.Series,
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

        if new <= 1e-12:

            result[
                asset
            ] = 0.0

            continue

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
        > MAX_OVERLAY
        and total > 0
    ):

        result *= (
            MAX_OVERLAY
            / total
        )

    return result


# ============================================================
# BACKTEST
# ============================================================

def run_model(
    signals: dict,
    evaluation_start: str,
    rebalance_weeks: int,
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

    dates = (
        asset_returns.index[
            asset_returns.index
            >= pd.Timestamp(
                evaluation_start
            )
        ]
    )

    if len(
        dates
    ) < 2:

        raise RuntimeError(
            "Insufficient backtest dates."
        )

    satellite_weights = (
        pd.Series(
            0.0,
            index=EQUITY_UNIVERSE,
            dtype=float,
        )
    )

    pending_target = None

    nav = START_NAV

    total_turnover = 0.0

    total_cost_gbp = 0.0

    cost_rate = (
        float(
            one_way_cost_bps
        )
        / 10_000.0
    )

    rows = []

    for i, date in enumerate(
        dates
    ):

        nav_before = (
            nav
        )

        today_asset_returns = (
            asset_returns
            .loc[date]
            .reindex(
                EQUITY_UNIVERSE
            )
            .fillna(
                0.0
            )
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
                "Invalid return denominator."
            )

        satellite_weights = (
            satellite_weights
            * (
                1.0
                + today_asset_returns
            )
            / denominator
        )

        if (
            satellite_weights.sum()
            > MAX_TOTAL_DRIFT
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite sleeve drift limit breached."
            )

        if (
            satellite_weights.max()
            > MAX_POSITION_DRIFT
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite position drift limit breached."
            )

        turnover_today = 0.0

        cost_today = 0.0

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

            cost_today = (
                nav
                * turnover_today
                * cost_rate
            )

            nav -= (
                cost_today
            )

            total_turnover += (
                turnover_today
            )

            total_cost_gbp += (
                cost_today
            )

            satellite_weights = (
                executed
            )

            pending_target = None

        if is_signal_day(
            date=
                date,

            rebalance_weeks=
                rebalance_weeks,
        ):

            pending_target = (
                build_target(
                    date=
                        date,

                    current_weights=
                        satellite_weights,

                    signals=
                        signals,
                )
            )

        daily_net_return = (
            nav
            / nav_before
            - 1.0
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
                daily_net_return
                - benchmark_return,

            "gross_overlay_return":
                gross_overlay_return,

            "cost_drag_return":
                daily_net_return
                - gross_portfolio_return,

            "satellite_weight":
                float(
                    satellite_weights.sum()
                ),

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,
        })

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
        START_NAV
        * (
            1.0
            + history[
                "benchmark_return"
            ]
        )
        .cumprod()
    )

    return {
        "history":
            history,

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
            history.index[
                -1
            ]
            - history.index[
                0
            ]
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
        .iloc[
            -1
        ]
    )

    benchmark_final = float(
        history[
            "benchmark_nav"
        ]
        .iloc[
            -1
        ]
    )

    cagr = (
        (
            final_nav
            / START_NAV
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
            / START_NAV
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

    clean_active = (
        active.dropna()
    )

    if len(
        clean_active
    ) > 30:

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
                model.params[
                    0
                ]
            )
            * TRADING_DAYS
        )

        active_hac_tstat = float(
            model.tvalues[
                0
            ]
        )

    else:

        annualised_active_return = (
            np.nan
        )

        active_hac_tstat = (
            np.nan
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

    annual_turnover = (
        result[
            "total_turnover"
        ]
        / years
    )

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

    return {
        "start":
            str(
                history.index[
                    0
                ].date()
            ),

        "end":
            str(
                history.index[
                    -1
                ].date()
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
            annualised_active_return,

        "active_hac_tstat":
            active_hac_tstat,

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
    }


# ============================================================
# EXPERIMENT CLASSIFICATION
# ============================================================

def classify_experiment(
    spec: dict,
    metrics_by_key: dict,
) -> tuple[
    str,
    dict,
]:

    control_15 = (
        metrics_by_key[
            (
                "CONTROL",
                15,
            )
        ]
    )

    candidate_15 = (
        metrics_by_key[
            (
                "CANDIDATE",
                15,
            )
        ]
    )

    control_35 = (
        metrics_by_key[
            (
                "CONTROL",
                35,
            )
        ]
    )

    candidate_35 = (
        metrics_by_key[
            (
                "CANDIDATE",
                35,
            )
        ]
    )

    criteria = (
        spec[
            "acceptance_criteria"
        ]
    )

    if (
        control_15[
            "annual_turnover"
        ]
        > 0
    ):

        turnover_reduction = (
            1.0
            - candidate_15[
                "annual_turnover"
            ]
            / control_15[
                "annual_turnover"
            ]
        )

    else:

        turnover_reduction = 0.0

    control_gross = (
        control_15[
            "annualised_gross_overlay"
        ]
    )

    candidate_gross = (
        candidate_15[
            "annualised_gross_overlay"
        ]
    )

    if control_gross > 0:

        gross_retention = (
            candidate_gross
            / control_gross
        )

    else:

        gross_retention = (
            1.0
            if candidate_gross
            >= control_gross
            else 0.0
        )

    base_excess_improvement = (
        candidate_15[
            "excess_cagr"
        ]
        - control_15[
            "excess_cagr"
        ]
    )

    high_cost_improvement = (
        candidate_35[
            "excess_cagr"
        ]
        - control_35[
            "excess_cagr"
        ]
    )

    drawdown_worsening = max(
        0.0,
        abs(
            candidate_15[
                "max_drawdown"
            ]
        )
        - abs(
            control_15[
                "max_drawdown"
            ]
        ),
    )

    checks = {
        "turnover_reduction":
            {
                "value":
                    turnover_reduction,

                "required":
                    criteria[
                        "minimum_turnover_reduction_fraction"
                    ],

                "passed":
                    turnover_reduction
                    >= criteria[
                        "minimum_turnover_reduction_fraction"
                    ],
            },

        "gross_overlay_retention":
            {
                "value":
                    gross_retention,

                "required":
                    criteria[
                        "minimum_gross_overlay_retention_fraction"
                    ],

                "passed":
                    gross_retention
                    >= criteria[
                        "minimum_gross_overlay_retention_fraction"
                    ],
            },

        "base_cost_excess_improvement":
            {
                "value":
                    base_excess_improvement,

                "required":
                    criteria[
                        "minimum_base_cost_excess_cagr_improvement"
                    ],

                "passed":
                    base_excess_improvement
                    >= criteria[
                        "minimum_base_cost_excess_cagr_improvement"
                    ],
            },

        "high_cost_excess_improvement":
            {
                "value":
                    high_cost_improvement,

                "required":
                    criteria[
                        "minimum_35bps_excess_cagr_improvement"
                    ],

                "passed":
                    high_cost_improvement
                    >= criteria[
                        "minimum_35bps_excess_cagr_improvement"
                    ],
            },

        "drawdown_worsening":
            {
                "value":
                    drawdown_worsening,

                "maximum":
                    criteria[
                        "maximum_drawdown_worsening"
                    ],

                "passed":
                    drawdown_worsening
                    <= criteria[
                        "maximum_drawdown_worsening"
                    ],
            },
    }

    all_pass = all(
        check[
            "passed"
        ]
        for check
        in checks.values()
    )

    if all_pass:

        status = (
            "RESEARCH_SURVIVOR"
        )

    elif (
        candidate_15[
            "annualised_gross_overlay"
        ]
        <= 0
        and candidate_15[
            "excess_cagr"
        ]
        <= 0
    ):

        status = (
            "REJECTED"
        )

    else:

        status = (
            "INCONCLUSIVE"
        )

    return (
        status,
        checks,
    )


# ============================================================
# RUN ONE EXPERIMENT
# ============================================================

def run_experiment(
    spec: dict,
    spec_hash: str,
    protocol: dict,
    protocol_hash: str,
    data_hash: str,
    signals: dict,
) -> dict:

    experiment_id = str(
        spec[
            "experiment_id"
        ]
    )

    control_weeks = int(
        spec[
            "control"
        ][
            "rebalance_weeks"
        ]
    )

    candidate_weeks = int(
        spec[
            "candidate"
        ][
            "rebalance_weeks"
        ]
    )

    evaluation_start = (
        protocol[
            "evaluation_start"
        ]
    )

    cost_scenarios = (
        protocol[
            "cost_scenarios_bps"
        ]
    )

    rows = []

    metrics_by_key = {}

    for cost_bps in cost_scenarios:

        print(
            f"\nRunning CONTROL "
            f"at {cost_bps} bps..."
        )

        control_result = (
            run_model(
                signals=
                    signals,

                evaluation_start=
                    evaluation_start,

                rebalance_weeks=
                    control_weeks,

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        control_metrics = (
            calculate_metrics(
                control_result
            )
        )

        metrics_by_key[
            (
                "CONTROL",
                int(
                    cost_bps
                ),
            )
        ] = control_metrics

        rows.append({
            "role":
                "CONTROL",

            "model":
                spec[
                    "control"
                ][
                    "name"
                ],

            "cost_bps":
                int(
                    cost_bps
                ),

            **control_metrics,
        })

        print(
            f"Running CANDIDATE "
            f"at {cost_bps} bps..."
        )

        candidate_result = (
            run_model(
                signals=
                    signals,

                evaluation_start=
                    evaluation_start,

                rebalance_weeks=
                    candidate_weeks,

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        candidate_metrics = (
            calculate_metrics(
                candidate_result
            )
        )

        metrics_by_key[
            (
                "CANDIDATE",
                int(
                    cost_bps
                ),
            )
        ] = candidate_metrics

        rows.append({
            "role":
                "CANDIDATE",

            "model":
                spec[
                    "candidate"
                ][
                    "name"
                ],

            "cost_bps":
                int(
                    cost_bps
                ),

            **candidate_metrics,
        })

    status, checks = (
        classify_experiment(
            spec=
                spec,

            metrics_by_key=
                metrics_by_key,
        )
    )

    table = (
        pd.DataFrame(
            rows
        )
    )

    result = {
        "experiment_id":
            experiment_id,

        "run_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            status,

        "hypothesis":
            spec[
                "hypothesis"
            ],

        "spec_hash":
            spec_hash,

        "protocol_hash":
            protocol_hash,

        "data_hash":
            data_hash,

        "historical_cutoff":
            protocol[
                "historical_cutoff"
            ],

        "evaluation_start":
            protocol[
                "evaluation_start"
            ],

        "control":
            spec[
                "control"
            ],

        "candidate":
            spec[
                "candidate"
            ],

        "acceptance_criteria":
            spec[
                "acceptance_criteria"
            ],

        "criterion_results":
            checks,

        "cost_sensitivity":
            table.to_dict(
                orient="records"
            ),

        "research_warning":
            (
                "Historical survivor status is "
                "not evidence of proven alpha. "
                "This history was already observed "
                "during earlier Fund-100 research."
            ),
    }

    return result


# ============================================================
# APPEND REGISTRY
# ============================================================

def append_registry(
    registry: pd.DataFrame,
    result: dict,
    result_file: str,
) -> pd.DataFrame:

    if registry.empty:

        previous_hash = (
            "GENESIS"
        )

    else:

        previous_hash = str(
            registry.iloc[
                -1
            ][
                "chain_hash"
            ]
        )

    base_15 = None

    for row in result[
        "cost_sensitivity"
    ]:

        if (
            row[
                "role"
            ]
            == "CANDIDATE"
            and row[
                "cost_bps"
            ]
            == 15
        ):

            base_15 = row

            break

    if base_15 is None:

        raise RuntimeError(
            "Candidate 15 bps result missing."
        )

    payload = {
        "experiment_id":
            result[
                "experiment_id"
            ],

        "run_utc":
            result[
                "run_utc"
            ],

        "status":
            result[
                "status"
            ],

        "spec_hash":
            result[
                "spec_hash"
            ],

        "protocol_hash":
            result[
                "protocol_hash"
            ],

        "data_hash":
            result[
                "data_hash"
            ],

        "result_file":
            result_file,

        "candidate_excess_cagr_15bps":
            base_15[
                "excess_cagr"
            ],

        "candidate_information_ratio_15bps":
            base_15[
                "information_ratio"
            ],

        "candidate_active_hac_tstat_15bps":
            base_15[
                "active_hac_tstat"
            ],

        "candidate_annual_turnover_15bps":
            base_15[
                "annual_turnover"
            ],
    }

    payload_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )

    chain_hash = (
        sha256_text(
            previous_hash
            + "|"
            + payload_json
        )
    )

    row = {
        "experiment_id":
            result[
                "experiment_id"
            ],

        "run_utc":
            result[
                "run_utc"
            ],

        "status":
            result[
                "status"
            ],

        "spec_hash":
            result[
                "spec_hash"
            ],

        "protocol_hash":
            result[
                "protocol_hash"
            ],

        "data_hash":
            result[
                "data_hash"
            ],

        "result_file":
            result_file,

        "previous_chain_hash":
            previous_hash,

        "chain_hash":
            chain_hash,

        "payload_json":
            payload_json,
    }

    updated = pd.concat(
        [
            registry,
            pd.DataFrame(
                [
                    row
                ]
            ),
        ],
        ignore_index=True,
    )

    updated.to_csv(
        REGISTRY_PATH,
        index=False,
    )

    return updated


# ============================================================
# PRINT RESULT
# ============================================================

def print_result(
    result: dict,
) -> None:

    print(
        "\n============================================"
    )

    print(
        f"EXPERIMENT "
        f"{result['experiment_id']}"
    )

    print(
        "============================================"
    )

    print(
        "\nHypothesis:"
    )

    print(
        result[
            "hypothesis"
        ]
    )

    table = pd.DataFrame(
        result[
            "cost_sensitivity"
        ]
    )

    display_cols = [
        "role",
        "model",
        "cost_bps",
        "final_nav_gbp",
        "benchmark_final_nav_gbp",
        "cagr",
        "benchmark_cagr",
        "excess_cagr",
        "annualised_gross_overlay",
        "annualised_cost_drag",
        "annual_turnover",
        "information_ratio",
        "active_hac_tstat",
        "max_drawdown",
        "tracking_error",
        "fraction_3y_windows_beating_acwi",
        "median_3y_excess_cagr",
    ]

    print(
        "\nCost sensitivity:"
    )

    print(
        table[
            display_cols
        ]
        .round(
            4
        )
        .to_string(
            index=False
        )
    )

    print(
        "\nPre-registered criteria:"
    )

    for name, check in (
        result[
            "criterion_results"
        ]
        .items()
    ):

        print(
            f"{name}: "
            f"{'PASS' if check['passed'] else 'FAIL'} "
            f"| {check}"
        )

    print(
        "\nResearch classification:"
    )

    print(
        result[
            "status"
        ]
    )

    print(
        "\nImportant:"
    )

    print(
        "This classification concerns the "
        "pre-registered historical hypothesis only."
    )

    print(
        "It is not evidence that alpha has "
        "been established."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 AUTONOMOUS RESEARCH LAB"
    )

    print(
        "============================================"
    )

    protocol = (
        load_protocol()
    )

    protocol_hash = (
        sha256_json(
            protocol
        )
    )

    print(
        f"\nProtocol version: "
        f"{protocol['protocol_version']}"
    )

    print(
        f"Protocol SHA256:"
    )

    print(
        protocol_hash
    )

    print(
        f"\nHistorical cutoff: "
        f"{protocol['historical_cutoff']}"
    )

    registry = (
        load_registry()
    )

    validate_registry(
        registry
    )

    specs = (
        load_specs()
    )

    validate_completed_specs(
        registry=
            registry,

        specs=
            specs,
    )

    completed_ids = set(
        registry[
            "experiment_id"
        ].astype(
            str
        )
    )

    pending_specs = [
        item
        for item in specs
        if str(
            item[
                1
            ][
                "experiment_id"
            ]
        )
        not in completed_ids
    ]

    print(
        f"\nCompleted experiments: "
        f"{len(completed_ids)}"
    )

    print(
        f"Pending registered experiments: "
        f"{len(pending_specs)}"
    )

    if not pending_specs:

        print(
            "\nNo registered experiment "
            "is waiting to run."
        )

        print(
            "Research Lab made no changes."
        )

        return

    cfg, config_hash = (
        load_config()
    )

    print(
        "\nFrozen v1 config SHA256:"
    )

    print(
        config_hash
    )

    print(
        "\nDownloading historical market data..."
    )

    prices, benchmark = (
        load_historical_data(
            cfg=
                cfg,

            protocol=
                protocol,
        )
    )

    print(
        f"Historical market data: "
        f"{prices.index[0].date()} "
        f"to "
        f"{prices.index[-1].date()}"
    )

    data_hash = (
        ensure_data_manifest(
            prices=
                prices,

            benchmark=
                benchmark,

            protocol=
                protocol,
        )
    )

    print(
        "\nHistorical dataset SHA256:"
    )

    print(
        data_hash
    )

    print(
        "\nBuilding frozen RM25 signal..."
    )

    signals = (
        build_signals(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    max_to_run = int(
        protocol[
            "max_experiments_per_run"
        ]
    )

    experiments_run = 0

    latest_result = None

    for (
        spec_path,
        spec,
        spec_hash,
    ) in pending_specs:

        if (
            experiments_run
            >= max_to_run
        ):

            break

        experiment_id = str(
            spec[
                "experiment_id"
            ]
        )

        result_path = (
            RESULTS_DIR
            / (
                experiment_id
                + ".json"
            )
        )

        if result_path.exists():

            raise RuntimeError(
                f"Result file already exists for "
                f"{experiment_id}, but registry "
                "does not contain it."
            )

        print(
            "\n============================================"
        )

        print(
            f"STARTING {experiment_id}"
        )

        print(
            "============================================"
        )

        print(
            f"Specification: {spec_path}"
        )

        print(
            f"Specification SHA256: "
            f"{spec_hash}"
        )

        print(
            "\nThe experiment specification is "
            "now frozen for this run."
        )

        result = (
            run_experiment(
                spec=
                    spec,

                spec_hash=
                    spec_hash,

                protocol=
                    protocol,

                protocol_hash=
                    protocol_hash,

                data_hash=
                    data_hash,

                signals=
                    signals,
            )
        )

        with result_path.open(
            "w"
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
                default=float,
            )

        registry = (
            append_registry(
                registry=
                    registry,

                result=
                    result,

                result_file=
                    str(
                        result_path
                    ),
            )
        )

        validate_registry(
            registry
        )

        print_result(
            result
        )

        latest_result = (
            result
        )

        experiments_run += 1

    report = {
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "protocol_hash":
            protocol_hash,

        "data_hash":
            data_hash,

        "total_completed_experiments":
            int(
                len(
                    registry
                )
            ),

        "experiments_run_this_session":
            experiments_run,

        "latest_experiment":
            latest_result,
    }

    with LATEST_REPORT_PATH.open(
        "w"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            default=float,
        )

    print(
        "\n============================================"
    )

    print(
        "RESEARCH LAB STATUS"
    )

    print(
        "============================================"
    )

    print(
        f"Experiments run this session: "
        f"{experiments_run}"
    )

    print(
        f"Total permanently registered: "
        f"{len(registry)}"
    )

    print(
        "\nRegistry:"
    )

    print(
        REGISTRY_PATH
    )

    print(
        "\nResults directory:"
    )

    print(
        RESULTS_DIR
    )

    print(
        "\nNo Forward Lab strategy was changed."
    )

    print(
        "No broker connection was used."
    )

    print(
        "No trades were placed."
    )

    print(
        "\n============================================"
    )

    print(
        "RESEARCH LAB RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()

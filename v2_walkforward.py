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
    compute_signals,
    cross_sectional_zscore,
)


TRADING_DAYS = 252

OUTPUT_DIR = Path("v2_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

BOE_BANK_RATE_URL = (
    "https://www.bankofengland.co.uk/"
    "boeapps/database/Bank-Rate.asp"
)

# ------------------------------------------------------------
# IMPORTANT
#
# These candidate models are deliberately few in number.
#
# We are NOT running a giant parameter search.
#
# All candidates are trend-only because the v1 ablation
# showed that residual momentum was detrimental in this
# ETF implementation.
#
# Candidate differences:
# - trend speed
# - rebalance frequency
#
# Everything else is held structurally constant.
# ------------------------------------------------------------

CANDIDATES = {
    "T_63_126_252_W1": {
        "horizons": [63, 126, 252],
        "rebalance_weeks": 1,
    },

    "T_63_126_252_W2": {
        "horizons": [63, 126, 252],
        "rebalance_weeks": 2,
    },

    "T_63_126_252_W4": {
        "horizons": [63, 126, 252],
        "rebalance_weeks": 4,
    },

    "T_126_252_W1": {
        "horizons": [126, 252],
        "rebalance_weeks": 1,
    },

    "T_126_252_W2": {
        "horizons": [126, 252],
        "rebalance_weeks": 2,
    },

    "T_126_252_W4": {
        "horizons": [126, 252],
        "rebalance_weeks": 4,
    },

    "T_63_126_W2": {
        "horizons": [63, 126],
        "rebalance_weeks": 2,
    },

    "T_126_252_378_W2": {
        "horizons": [126, 252, 378],
        "rebalance_weeks": 2,
    },
}


ASSET_GROUPS = {
    "US_Equity": [
        "SPY",
        "IWM",
        "XLK",
        "XLF",
        "XLI",
        "XLV",
        "XLP",
        "XLY",
        "XLE",
        "XLU",
    ],

    "International_Equity": [
        "EFA",
        "EEM",
    ],

    "Real_Estate": [
        "VNQ",
    ],

    "Fixed_Income": [
        "TLT",
        "IEF",
        "SHY",
        "TIP",
        "LQD",
    ],

    "Real_Assets": [
        "GLD",
        "DBC",
    ],
}


# Structural caps.
#
# These are NOT optimised separately by candidate.
#
# They exist to stop SPY + IWM + sectors from pretending
# to be independent diversification.

GROUP_CAPS = {
    "US_Equity": 0.60,
    "International_Equity": 0.35,
    "Real_Estate": 0.25,
    "Fixed_Income": 0.50,
    "Real_Assets": 0.35,
}


ASSET_TO_GROUP = {}

for group_name, members in ASSET_GROUPS.items():
    for ticker in members:
        ASSET_TO_GROUP[ticker] = group_name


# ============================================================
# BANK OF ENGLAND CASH RATE
# ============================================================

def load_boe_cash_returns(
    trading_index: pd.DatetimeIndex,
    haircut_bps: float = 50.0,
) -> pd.Series:
    """
    Downloads official Bank Rate history directly from
    the Bank of England.

    Cash is credited at:

        Bank Rate - 50 basis points

    with a zero floor.

    This is only a research cash proxy. It is NOT a claim
    that a particular broker pays this rate.
    """

    print(
        "Downloading Bank of England "
        "Bank Rate history..."
    )

    tables = pd.read_html(
        BOE_BANK_RATE_URL
    )

    rate_table = None

    for table in tables:

        table = table.copy()

        table.columns = [
            str(col).strip()
            for col in table.columns
        ]

        if (
            "Date Changed"
            in table.columns
            and "Rate"
            in table.columns
        ):
            rate_table = table[
                [
                    "Date Changed",
                    "Rate",
                ]
            ].copy()

            break

    if rate_table is None:
        raise RuntimeError(
            "Could not locate the official "
            "Bank Rate history table."
        )

    rate_table[
        "date"
    ] = pd.to_datetime(
        rate_table["Date Changed"],
        format="%d %b %y",
        errors="coerce",
    )

    rate_table[
        "rate_percent"
    ] = pd.to_numeric(
        rate_table["Rate"]
        .astype(str)
        .str.replace(
            "%",
            "",
            regex=False,
        ),
        errors="coerce",
    )

    rate_table = (
        rate_table[
            [
                "date",
                "rate_percent",
            ]
        ]
        .dropna()
        .sort_values("date")
        .drop_duplicates(
            "date",
            keep="last",
        )
    )

    date_frame = pd.DataFrame({
        "date":
            pd.DatetimeIndex(
                trading_index
            )
    })

    merged = pd.merge_asof(
        date_frame.sort_values(
            "date"
        ),
        rate_table.sort_values(
            "date"
        ),
        on="date",
        direction="backward",
    )

    if (
        merged[
            "rate_percent"
        ]
        .isna()
        .any()
    ):
        raise RuntimeError(
            "Bank Rate history does not "
            "cover the full strategy period."
        )

    annual_rate = (
        merged[
            "rate_percent"
        ]
        / 100.0
        - haircut_bps
        / 10_000.0
    )

    annual_rate = (
        annual_rate.clip(
            lower=0.0
        )
    )

    calendar_days = (
        merged["date"]
        .diff()
        .dt.days
        .fillna(1)
        .clip(lower=1)
    )

    # Simple daily accrual approximation.
    cash_returns = (
        annual_rate
        * calendar_days
        / 365.25
    )

    result = pd.Series(
        cash_returns.values,
        index=pd.DatetimeIndex(
            trading_index
        ),
        name="cash_return",
    )

    # Portfolio begins at the first close,
    # so no interest is credited beforehand.
    if len(result):
        result.iloc[0] = 0.0

    return result


# ============================================================
# CANDIDATE TREND SIGNALS
# ============================================================

def build_candidate_scores(
    prices: pd.DataFrame,
    base_signals: dict,
) -> dict:

    annual_vol = (
        base_signals[
            "annual_vol"
        ]
        .replace(
            0.0,
            np.nan,
        )
    )

    scores = {}

    for candidate_name, params in (
        CANDIDATES.items()
    ):

        components = []

        for horizon in (
            params["horizons"]
        ):

            risk_adjusted = (
                prices
                .pct_change(
                    horizon
                )
                .div(
                    annual_vol
                )
            )

            components.append(
                cross_sectional_zscore(
                    risk_adjusted
                )
            )

        scores[
            candidate_name
        ] = (
            sum(components)
            / len(components)
        )

    return scores


# ============================================================
# REBALANCE SCHEDULING
# ============================================================

def is_regular_signal_day(
    date: pd.Timestamp,
    rebalance_weeks: int,
) -> bool:

    # Wednesday.
    if date.weekday() != 2:
        return False

    anchor = pd.Timestamp(
        "2010-01-06"
    )

    weeks_since_anchor = (
        date.normalize()
        - anchor
    ).days // 7

    if weeks_since_anchor < 0:
        return False

    return (
        weeks_since_anchor
        % rebalance_weeks
        == 0
    )


# ============================================================
# PORTFOLIO CAP HELPERS
# ============================================================

def group_total(
    weights: pd.Series,
    group_name: str,
) -> float:

    members = [
        asset
        for asset in weights.index
        if (
            ASSET_TO_GROUP
            .get(asset)
            == group_name
        )
    ]

    if not members:
        return 0.0

    return float(
        weights[
            members
        ].sum()
    )


def allocate_with_caps(
    raw_scores: pd.Series,
    gross_target: float,
    max_asset_weight: float,
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
        float(gross_target),
        1.0,
    )

    for _ in range(100):

        remaining_gross = (
            gross_target
            - float(
                result.sum()
            )
        )

        if remaining_gross <= 1e-10:
            break

        active = []

        for asset in scores.index:

            asset_room = (
                max_asset_weight
                - result[asset]
            )

            group_name = (
                ASSET_TO_GROUP
                .get(asset)
            )

            group_cap = (
                GROUP_CAPS.get(
                    group_name,
                    1.0,
                )
            )

            group_room = (
                group_cap
                - group_total(
                    result,
                    group_name,
                )
            )

            if (
                asset_room
                > 1e-10
                and group_room
                > 1e-10
            ):
                active.append(
                    asset
                )

        if not active:
            break

        active_scores = (
            scores.loc[
                active
            ]
        )

        if (
            active_scores.sum()
            <= 0
        ):
            proposal = (
                pd.Series(
                    1.0,
                    index=active,
                )
                / len(active)
                * remaining_gross
            )

        else:
            proposal = (
                active_scores
                / active_scores.sum()
                * remaining_gross
            )

        added = 0.0

        for asset in active:

            asset_room = (
                max_asset_weight
                - result[asset]
            )

            group_name = (
                ASSET_TO_GROUP
                .get(asset)
            )

            group_cap = (
                GROUP_CAPS.get(
                    group_name,
                    1.0,
                )
            )

            group_room = (
                group_cap
                - group_total(
                    result,
                    group_name,
                )
            )

            addition = max(
                0.0,
                min(
                    float(
                        proposal[
                            asset
                        ]
                    ),
                    asset_room,
                    group_room,
                ),
            )

            result[asset] += (
                addition
            )

            added += addition

        if added <= 1e-12:
            break

    return result


def enforce_hard_caps(
    weights: pd.Series,
    max_asset_weight: float,
    max_gross: float,
) -> pd.Series:

    result = (
        weights
        .clip(
            lower=0.0,
            upper=max_asset_weight,
        )
        .copy()
    )

    for (
        group_name,
        group_cap,
    ) in GROUP_CAPS.items():

        members = [
            asset
            for asset in result.index
            if (
                ASSET_TO_GROUP
                .get(asset)
                == group_name
            )
        ]

        if not members:
            continue

        total = float(
            result[
                members
            ].sum()
        )

        if (
            total
            > group_cap
            and total > 0
        ):
            result.loc[
                members
            ] *= (
                group_cap
                / total
            )

    gross = float(
        result.sum()
    )

    if (
        gross > max_gross
        and gross > 0
    ):
        result *= (
            max_gross
            / gross
        )

    return result


def apply_trade_threshold_v2(
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

        delta = (
            new - old
        )

        # Full exit always allowed.
        if new <= 1e-12:
            result[asset] = 0.0
            continue

        # Do not open microscopic positions.
        if (
            old <= 1e-12
            and abs(delta)
            < minimum_trade
        ):
            result[asset] = 0.0
            continue

        # Suppress tiny maintenance trades.
        if (
            old > 1e-12
            and abs(delta)
            < minimum_trade
        ):
            result[asset] = old

    result = enforce_hard_caps(
        result,
        max_asset_weight=
            maximum_weight,
        max_gross=
            maximum_gross,
    )

    return result


# ============================================================
# PORTFOLIO CONSTRUCTOR
# ============================================================

def construct_v2_target(
    date: pd.Timestamp,
    current_weights: pd.Series,
    prices: pd.DataFrame,
    base_signals: dict,
    candidate_scores: dict,
    candidate_name: str,
    cfg: dict,
) -> pd.Series:

    pcfg = cfg[
        "portfolio"
    ]

    assets = (
        prices.columns
    )

    target = pd.Series(
        0.0,
        index=assets,
        dtype=float,
    )

    score = (
        candidate_scores[
            candidate_name
        ]
        .loc[date]
    )

    if score.isna().all():
        return target

    moving_average = (
        base_signals[
            "moving_average"
        ]
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
        (score > 0)
        &
        (
            current_prices
            > moving_average
        )
    )

    held = list(
        current_weights[
            current_weights
            > 1e-10
        ].index
    )

    selected = []

    # Existing positions get hysteresis.
    for asset in held:

        if (
            pd.notna(
                ranks.get(asset)
            )
            and ranks[asset]
            <= pcfg[
                "keep_rank"
            ]
            and bool(
                absolute_trend_ok
                .get(
                    asset,
                    False,
                )
            )
        ):
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
            >= pcfg[
                "max_positions"
            ]
        ):
            break

        if asset in selected:
            continue

        if bool(
            absolute_trend_ok
            .get(
                asset,
                False,
            )
        ):
            selected.append(
                asset
            )

    if not selected:
        return target

    vol = (
        base_signals[
            "annual_vol"
        ]
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
    ).dropna()

    if inverse_vol.empty:
        return target

    panic = bool(
        base_signals[
            "panic"
        ]
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
        allocate_with_caps(
            raw_scores=
                inverse_vol,

            gross_target=
                max_gross,

            max_asset_weight=
                pcfg[
                    "max_asset_weight"
                ],
        )
    )

    # --------------------------------------------------------
    # Portfolio volatility control.
    #
    # This can reduce exposure but never lever it upward.
    # --------------------------------------------------------

    selected = list(
        selected_weights[
            selected_weights > 0
        ].index
    )

    if selected:

        recent_returns = (
            base_signals[
                "returns"
            ]
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
            selected_weights[
                selected
            ]
            .values
        )

        if (
            covariance
            .notna()
            .all()
            .all()
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

                scale = min(
                    1.0,
                    pcfg[
                        "annual_volatility_target"
                    ]
                    / portfolio_vol,
                )

                selected_weights *= (
                    scale
                )

    target.loc[
        selected_weights.index
    ] = selected_weights

    return target


# ============================================================
# BENCHMARKS
# ============================================================

def build_benchmark_returns(
    benchmark: pd.Series,
    cash_returns: pd.Series,
    target_vol: float = 0.12,
) -> tuple[
    pd.Series,
    pd.Series,
]:

    benchmark_returns = (
        benchmark.pct_change(
            fill_method=None
        )
        .fillna(0.0)
    )

    trailing_vol = (
        benchmark_returns
        .rolling(63)
        .std()
        * math.sqrt(
            TRADING_DAYS
        )
    )

    exposure = (
        target_vol
        / trailing_vol.replace(
            0.0,
            np.nan,
        )
    )

    exposure = (
        exposure
        .clip(
            lower=0.0,
            upper=1.0,
        )
        .shift(1)
        .fillna(0.0)
    )

    risk_matched = (
        exposure
        * benchmark_returns
        +
        (
            1.0
            - exposure
        )
        * cash_returns
    )

    return (
        benchmark_returns,
        risk_matched,
    )


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_candidate_backtest(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    cash_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_matched_returns: pd.Series,
    base_signals: dict,
    candidate_scores: dict,
    candidate_name: str,
    cfg: dict,
    start_date: str,
    end_date: str,
    one_way_cost_bps: float,
) -> dict:

    pcfg = cfg[
        "portfolio"
    ]

    candidate = (
        CANDIDATES[
            candidate_name
        ]
    )

    start = pd.Timestamp(
        start_date
    )

    end = pd.Timestamp(
        end_date
    )

    dates = prices.index[
        (prices.index >= start)
        &
        (prices.index <= end)
    ]

    if len(dates) < 2:
        raise RuntimeError(
            "Insufficient dates "
            "for backtest."
        )

    assets = (
        prices.columns
    )

    weights = pd.Series(
        0.0,
        index=assets,
        dtype=float,
    )

    nav = 100.0

    pending_target = None

    total_turnover = 0.0
    total_cost_gbp = 0.0

    rows = []
    weight_rows = []

    cost_rate = (
        one_way_cost_bps
        / 10_000.0
    )

    for i, date in enumerate(
        dates
    ):

        nav_before = nav

        asset_returns = (
            base_signals[
                "returns"
            ]
            .loc[date]
            .reindex(
                assets
            )
            .fillna(0.0)
        )

        cash_return = float(
            cash_returns.loc[
                date
            ]
        )

        if i == 0:
            cash_return = 0.0

        cash_weight = max(
            0.0,
            1.0
            - float(
                weights.sum()
            ),
        )

        portfolio_return = float(
            (
                weights
                * asset_returns
            ).sum()
            +
            cash_weight
            * cash_return
        )

        nav *= (
            1.0
            + portfolio_return
        )

        denominator = (
            1.0
            + portfolio_return
        )

        if denominator <= 0:
            raise RuntimeError(
                "Invalid portfolio "
                "return denominator."
            )

        weights = (
            weights
            * (
                1.0
                + asset_returns
            )
            / denominator
        )

        turnover_today = 0.0
        cost_today = 0.0

        # ----------------------------------------------------
        # Execute yesterday's queued signal AFTER today's
        # market return.
        #
        # Wednesday close signal therefore executes at the
        # following trading session close.
        # ----------------------------------------------------

        if pending_target is not None:

            panic = bool(
                base_signals[
                    "panic"
                ]
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
                apply_trade_threshold_v2(
                    current=
                        weights,

                    desired=
                        pending_target,

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

            total_turnover += (
                turnover_today
            )

            total_cost_gbp += (
                cost_today
            )

            weights = executed

            pending_target = None

        # ----------------------------------------------------
        # Generate the new signal after today's close.
        # Do NOT execute until the following trading session.
        # ----------------------------------------------------

        if is_regular_signal_day(
            date,
            candidate[
                "rebalance_weeks"
            ],
        ):

            pending_target = (
                construct_v2_target(
                    date=date,

                    current_weights=
                        weights,

                    prices=
                        prices,

                    base_signals=
                        base_signals,

                    candidate_scores=
                        candidate_scores,

                    candidate_name=
                        candidate_name,

                    cfg=
                        cfg,
                )
            )

        daily_net_return = (
            nav
            / nav_before
        ) - 1.0

        bret = float(
            benchmark_returns.loc[
                date
            ]
        )

        rmret = float(
            risk_matched_returns.loc[
                date
            ]
        )

        if i == 0:
            bret = 0.0
            rmret = 0.0

        rows.append({
            "date":
                date,

            "nav":
                nav,

            "daily_return":
                daily_net_return,

            "cash_return":
                cash_return,

            "benchmark_return":
                bret,

            "risk_matched_return":
                rmret,

            "gross_exposure":
                float(
                    weights.sum()
                ),

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,

            "panic_regime":
                bool(
                    base_signals[
                        "panic"
                    ]
                    .loc[date]
                ),
        })

        weight_row = {
            "date":
                date,
        }

        for asset in assets:
            weight_row[
                asset
            ] = float(
                weights[
                    asset
                ]
            )

        weight_rows.append(
            weight_row
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

    history[
        "risk_matched_nav"
    ] = (
        100.0
        * (
            1.0
            + history[
                "risk_matched_return"
            ]
        )
        .cumprod()
    )

    weights_df = (
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
            weights_df,

        "total_turnover":
            total_turnover,

        "total_cost_gbp":
            total_cost_gbp,
    }


# ============================================================
# PERFORMANCE METRICS
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

    risk_matched = (
        history[
            "risk_matched_return"
        ]
    )

    cash = (
        history[
            "cash_return"
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

    starting_nav = 100.0

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

    risk_matched_final = float(
        history[
            "risk_matched_nav"
        ]
        .iloc[-1]
    )

    def cagr_from_values(
        start_value,
        end_value,
    ):

        return (
            (
                end_value
                / start_value
            )
            ** (
                1.0
                / years
            )
            - 1.0
        )

    cagr = cagr_from_values(
        starting_nav,
        final_nav,
    )

    benchmark_cagr = (
        cagr_from_values(
            starting_nav,
            benchmark_final,
        )
    )

    risk_matched_cagr = (
        cagr_from_values(
            starting_nav,
            risk_matched_final,
        )
    )

    annual_vol = (
        strategy.std(
            ddof=1
        )
        * math.sqrt(
            TRADING_DAYS
        )
    )

    strategy_excess = (
        strategy
        - cash
    )

    benchmark_excess = (
        benchmark
        - cash
    )

    excess_std = (
        strategy_excess.std(
            ddof=1
        )
    )

    sharpe = (
        strategy_excess.mean()
        / excess_std
        * math.sqrt(
            TRADING_DAYS
        )
        if excess_std > 0
        else np.nan
    )

    tracking = (
        strategy
        - benchmark
    )

    tracking_std = (
        tracking.std(
            ddof=1
        )
    )

    information_ratio = (
        tracking.mean()
        / tracking_std
        * math.sqrt(
            TRADING_DAYS
        )
        if tracking_std > 0
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

    # --------------------------------------------------------
    # Excess-return CAPM regression with HAC/Newey-West
    # standard errors.
    # --------------------------------------------------------

    regression_data = (
        pd.DataFrame({
            "strategy_excess":
                strategy_excess,

            "benchmark_excess":
                benchmark_excess,
        })
        .dropna()
    )

    if len(
        regression_data
    ) > 30:

        X = sm.add_constant(
            regression_data[
                "benchmark_excess"
            ]
        )

        model = (
            sm.OLS(
                regression_data[
                    "strategy_excess"
                ],
                X,
            )
            .fit(
                cov_type="HAC",
                cov_kwds={
                    "maxlags": 5
                },
            )
        )

        alpha_daily = float(
            model.params[
                "const"
            ]
        )

        alpha_annual = (
            alpha_daily
            * TRADING_DAYS
        )

        alpha_tstat = float(
            model.tvalues[
                "const"
            ]
        )

        beta = float(
            model.params[
                "benchmark_excess"
            ]
        )

    else:

        alpha_annual = np.nan
        alpha_tstat = np.nan
        beta = np.nan

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

        "years":
            years,

        "final_nav_gbp":
            final_nav,

        "benchmark_final_nav_gbp":
            benchmark_final,

        "risk_matched_final_nav_gbp":
            risk_matched_final,

        "cagr":
            cagr,

        "benchmark_cagr":
            benchmark_cagr,

        "risk_matched_cagr":
            risk_matched_cagr,

        "excess_cagr_vs_acwi":
            (
                cagr
                - benchmark_cagr
            ),

        "excess_cagr_vs_risk_matched":
            (
                cagr
                - risk_matched_cagr
            ),

        "annual_volatility":
            annual_vol,

        "sharpe_excess_cash":
            sharpe,

        "max_drawdown":
            max_drawdown,

        "information_ratio_vs_acwi":
            information_ratio,

        "beta_to_acwi":
            beta,

        "annualised_alpha":
            alpha_annual,

        "alpha_hac_tstat":
            alpha_tstat,

        "annual_turnover":
            annual_turnover,

        "total_transaction_cost_gbp":
            result[
                "total_cost_gbp"
            ],
    }


# ============================================================
# WALK-FORWARD FOLDS
# ============================================================

def make_folds(
    final_date: pd.Timestamp,
) -> list[dict]:

    return [
        {
            "fold": 1,
            "train_start":
                "2010-01-04",
            "train_end":
                "2013-12-31",
            "test_start":
                "2014-01-01",
            "test_end":
                "2015-12-31",
        },

        {
            "fold": 2,
            "train_start":
                "2010-01-04",
            "train_end":
                "2015-12-31",
            "test_start":
                "2016-01-01",
            "test_end":
                "2017-12-31",
        },

        {
            "fold": 3,
            "train_start":
                "2010-01-04",
            "train_end":
                "2017-12-31",
            "test_start":
                "2018-01-01",
            "test_end":
                "2019-12-31",
        },

        {
            "fold": 4,
            "train_start":
                "2010-01-04",
            "train_end":
                "2019-12-31",
            "test_start":
                "2020-01-01",
            "test_end":
                "2021-12-31",
        },

        {
            "fold": 5,
            "train_start":
                "2010-01-04",
            "train_end":
                "2021-12-31",
            "test_start":
                "2022-01-01",
            "test_end":
                "2023-12-31",
        },

        {
            "fold": 6,
            "train_start":
                "2010-01-04",
            "train_end":
                "2023-12-31",
            "test_start":
                "2024-01-01",
            "test_end":
                str(
                    final_date.date()
                ),
        },
    ]


# ============================================================
# TRAINING SELECTION
# ============================================================

def select_candidates(
    prices,
    benchmark,
    cash_returns,
    benchmark_returns,
    risk_matched_returns,
    base_signals,
    candidate_scores,
    cfg,
    folds,
):

    all_rows = []
    selection_rows = []

    for fold in folds:

        print(
            "\n===================================="
        )

        print(
            f"TRAINING FOLD "
            f"{fold['fold']}"
        )

        print(
            f"{fold['train_start']} "
            f"to "
            f"{fold['train_end']}"
        )

        print(
            "===================================="
        )

        fold_rows = []

        for candidate_name in (
            CANDIDATES.keys()
        ):

            result = (
                run_candidate_backtest(
                    prices=
                        prices,

                    benchmark=
                        benchmark,

                    cash_returns=
                        cash_returns,

                    benchmark_returns=
                        benchmark_returns,

                    risk_matched_returns=
                        risk_matched_returns,

                    base_signals=
                        base_signals,

                    candidate_scores=
                        candidate_scores,

                    candidate_name=
                        candidate_name,

                    cfg=
                        cfg,

                    start_date=
                        fold[
                            "train_start"
                        ],

                    end_date=
                        fold[
                            "train_end"
                        ],

                    one_way_cost_bps=
                        15.0,
                )
            )

            metrics = (
                calculate_metrics(
                    result
                )
            )

            row = {
                "fold":
                    fold[
                        "fold"
                    ],

                "candidate":
                    candidate_name,

                "train_start":
                    fold[
                        "train_start"
                    ],

                "train_end":
                    fold[
                        "train_end"
                    ],

                **metrics,
            }

            fold_rows.append(
                row
            )

            all_rows.append(
                row
            )

        fold_df = pd.DataFrame(
            fold_rows
        )

        # ----------------------------------------------------
        # Selection rule:
        #
        # 1. highest training information ratio vs ACWI
        # 2. lower turnover as first tie-break
        # 3. higher Sharpe as second tie-break
        #
        # No later test data are used here.
        # ----------------------------------------------------

        ranked = (
            fold_df
            .sort_values(
                by=[
                    "information_ratio_vs_acwi",
                    "annual_turnover",
                    "sharpe_excess_cash",
                ],
                ascending=[
                    False,
                    True,
                    False,
                ],
            )
        )

        selected = (
            ranked.iloc[0]
        )

        selected_name = (
            selected[
                "candidate"
            ]
        )

        print(
            "\nSelected from training data:"
        )

        print(
            selected_name
        )

        print(
            "\nTraining IR:"
        )

        print(
            round(
                float(
                    selected[
                        "information_ratio_vs_acwi"
                    ]
                ),
                4,
            )
        )

        selection_rows.append({
            "fold":
                fold[
                    "fold"
                ],

            "train_start":
                fold[
                    "train_start"
                ],

            "train_end":
                fold[
                    "train_end"
                ],

            "test_start":
                fold[
                    "test_start"
                ],

            "test_end":
                fold[
                    "test_end"
                ],

            "selected_candidate":
                selected_name,

            "training_information_ratio":
                float(
                    selected[
                        "information_ratio_vs_acwi"
                    ]
                ),

            "training_sharpe":
                float(
                    selected[
                        "sharpe_excess_cash"
                    ]
                ),

            "training_turnover":
                float(
                    selected[
                        "annual_turnover"
                    ]
                ),
        })

    scores = pd.DataFrame(
        all_rows
    )

    selections = pd.DataFrame(
        selection_rows
    )

    scores.to_csv(
        OUTPUT_DIR
        / "training_candidate_scores.csv",
        index=False,
    )

    selections.to_csv(
        OUTPUT_DIR
        / "walkforward_selections.csv",
        index=False,
    )

    return (
        scores,
        selections,
    )


# ============================================================
# DYNAMIC OOS SIMULATION
# ============================================================

def run_dynamic_oos(
    prices,
    benchmark,
    cash_returns,
    benchmark_returns,
    risk_matched_returns,
    base_signals,
    candidate_scores,
    cfg,
    selections,
    one_way_cost_bps,
):

    pcfg = cfg[
        "portfolio"
    ]

    assets = (
        prices.columns
    )

    start = pd.Timestamp(
        selections[
            "test_start"
        ].iloc[0]
    )

    end = pd.Timestamp(
        selections[
            "test_end"
        ].iloc[-1]
    )

    dates = prices.index[
        (prices.index >= start)
        &
        (prices.index <= end)
    ]

    weights = pd.Series(
        0.0,
        index=assets,
        dtype=float,
    )

    nav = 100.0

    pending_target = None

    current_candidate = None

    force_rebalance = True

    total_turnover = 0.0
    total_cost_gbp = 0.0

    rows = []
    weight_rows = []

    cost_rate = (
        one_way_cost_bps
        / 10_000.0
    )

    def candidate_for_date(
        date,
    ):

        matches = selections[
            (
                pd.to_datetime(
                    selections[
                        "test_start"
                    ]
                )
                <= date
            )
            &
            (
                pd.to_datetime(
                    selections[
                        "test_end"
                    ]
                )
                >= date
            )
        ]

        if matches.empty:
            return None

        return (
            matches.iloc[0][
                "selected_candidate"
            ]
        )

    for i, date in enumerate(
        dates
    ):

        active_candidate = (
            candidate_for_date(
                date
            )
        )

        if active_candidate is None:
            continue

        if (
            active_candidate
            != current_candidate
        ):

            # The new training decision is now
            # available. Cancel any unexecuted
            # signal from the previous fold.
            pending_target = None

            current_candidate = (
                active_candidate
            )

            force_rebalance = True

        nav_before = nav

        asset_returns = (
            base_signals[
                "returns"
            ]
            .loc[date]
            .reindex(
                assets
            )
            .fillna(0.0)
        )

        cash_return = float(
            cash_returns.loc[
                date
            ]
        )

        if i == 0:
            cash_return = 0.0

        cash_weight = max(
            0.0,
            1.0
            - float(
                weights.sum()
            ),
        )

        portfolio_return = float(
            (
                weights
                * asset_returns
            ).sum()
            +
            cash_weight
            * cash_return
        )

        nav *= (
            1.0
            + portfolio_return
        )

        denominator = (
            1.0
            + portfolio_return
        )

        weights = (
            weights
            * (
                1.0
                + asset_returns
            )
            / denominator
        )

        turnover_today = 0.0
        cost_today = 0.0

        # Execute previously queued target.
        if pending_target is not None:

            panic = bool(
                base_signals[
                    "panic"
                ]
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
                apply_trade_threshold_v2(
                    current=
                        weights,

                    desired=
                        pending_target,

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

            total_turnover += (
                turnover_today
            )

            total_cost_gbp += (
                cost_today
            )

            weights = executed

            pending_target = None

        candidate = (
            CANDIDATES[
                current_candidate
            ]
        )

        regular_signal = (
            is_regular_signal_day(
                date,
                candidate[
                    "rebalance_weeks"
                ],
            )
        )

        # Force the newly selected model
        # to issue a target on the first
        # Wednesday of its test fold.
        forced_signal = (
            force_rebalance
            and date.weekday() == 2
        )

        if (
            regular_signal
            or forced_signal
        ):

            pending_target = (
                construct_v2_target(
                    date=date,

                    current_weights=
                        weights,

                    prices=
                        prices,

                    base_signals=
                        base_signals,

                    candidate_scores=
                        candidate_scores,

                    candidate_name=
                        current_candidate,

                    cfg=
                        cfg,
                )
            )

            force_rebalance = False

        daily_net_return = (
            nav
            / nav_before
        ) - 1.0

        bret = float(
            benchmark_returns.loc[
                date
            ]
        )

        rmret = float(
            risk_matched_returns.loc[
                date
            ]
        )

        if i == 0:
            bret = 0.0
            rmret = 0.0

        rows.append({
            "date":
                date,

            "candidate":
                current_candidate,

            "nav":
                nav,

            "daily_return":
                daily_net_return,

            "cash_return":
                cash_return,

            "benchmark_return":
                bret,

            "risk_matched_return":
                rmret,

            "gross_exposure":
                float(
                    weights.sum()
                ),

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,

            "panic_regime":
                bool(
                    base_signals[
                        "panic"
                    ]
                    .loc[date]
                ),
        })

        weight_row = {
            "date":
                date,

            "candidate":
                current_candidate,
        }

        for asset in assets:
            weight_row[
                asset
            ] = float(
                weights[
                    asset
                ]
            )

        weight_rows.append(
            weight_row
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

    history[
        "risk_matched_nav"
    ] = (
        100.0
        * (
            1.0
            + history[
                "risk_matched_return"
            ]
        )
        .cumprod()
    )

    weights_df = (
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
            weights_df,

        "total_turnover":
            total_turnover,

        "total_cost_gbp":
            total_cost_gbp,
    }


# ============================================================
# YEARLY RESULTS
# ============================================================

def yearly_results(
    history,
):

    def compound(
        series,
    ):
        return (
            (
                1.0
                + series
            ).prod()
            - 1.0
        )

    year_index = (
        history.index.year
    )

    result = pd.DataFrame({
        "strategy_return":
            history[
                "daily_return"
            ]
            .groupby(
                year_index
            )
            .apply(
                compound
            ),

        "benchmark_return":
            history[
                "benchmark_return"
            ]
            .groupby(
                year_index
            )
            .apply(
                compound
            ),

        "risk_matched_return":
            history[
                "risk_matched_return"
            ]
            .groupby(
                year_index
            )
            .apply(
                compound
            ),
    })

    result[
        "excess_vs_acwi"
    ] = (
        result[
            "strategy_return"
        ]
        - result[
            "benchmark_return"
        ]
    )

    result[
        "excess_vs_risk_matched"
    ] = (
        result[
            "strategy_return"
        ]
        - result[
            "risk_matched_return"
        ]
    )

    result.index.name = (
        "year"
    )

    return result


# ============================================================
# CHART
# ============================================================

def create_oos_chart(
    dynamic_history,
    fixed_history,
):

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
        dynamic_history.index,
        dynamic_history[
            "nav"
        ],
        label=(
            "V2 Walk-Forward"
        ),
        linewidth=2.0,
    )

    axes[0].plot(
        fixed_history.index,
        fixed_history[
            "nav"
        ],
        label=(
            "Fixed Base Trend"
        ),
        linewidth=1.5,
        alpha=0.85,
    )

    axes[0].plot(
        dynamic_history.index,
        dynamic_history[
            "benchmark_nav"
        ],
        label=(
            "ACWI GBP proxy"
        ),
        linewidth=1.5,
    )

    axes[0].plot(
        dynamic_history.index,
        dynamic_history[
            "risk_matched_nav"
        ],
        label=(
            "12% vol-matched ACWI"
        ),
        linewidth=1.4,
        linestyle="--",
    )

    axes[0].set_ylabel(
        "NAV (£)"
    )

    axes[0].set_title(
        "Fund-100 V2 "
        "Walk-Forward Research"
    )

    axes[0].legend()

    axes[0].grid(
        alpha=0.25
    )

    drawdown = (
        dynamic_history[
            "nav"
        ]
        / dynamic_history[
            "nav"
        ]
        .cummax()
        - 1.0
    )

    axes[1].fill_between(
        dynamic_history.index,
        drawdown,
        0,
        color="crimson",
        alpha=0.35,
    )

    axes[1].set_ylabel(
        "Drawdown"
    )

    axes[1].grid(
        alpha=0.25
    )

    plt.tight_layout()

    fig.savefig(
        OUTPUT_DIR
        / "oos_equity_curve.png",
        dpi=170,
        bbox_inches="tight",
    )

    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )

    print(
        "FUND-100 V2 WALK-FORWARD RESEARCH"
    )

    print(
        "========================================"
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

    print(
        f"\nMarket data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "\nComputing base signals..."
    )

    base_signals = (
        compute_signals(
            prices=
                prices,

            benchmark=
                benchmark,

            cfg=
                cfg,
        )
    )

    print(
        "\nBuilding trend candidates..."
    )

    candidate_scores = (
        build_candidate_scores(
            prices=
                prices,

            base_signals=
                base_signals,
        )
    )

    cash_returns = (
        load_boe_cash_returns(
            trading_index=
                prices.index,

            haircut_bps=
                50.0,
        )
    )

    (
        benchmark_returns,
        risk_matched_returns,
    ) = (
        build_benchmark_returns(
            benchmark=
                benchmark,

            cash_returns=
                cash_returns,

            target_vol=
                cfg[
                    "portfolio"
                ][
                    "annual_volatility_target"
                ],
        )
    )

    folds = make_folds(
        prices.index.max()
    )

    # --------------------------------------------------------
    # Candidate selection using only each fold's past data.
    # --------------------------------------------------------

    (
        training_scores,
        selections,
    ) = (
        select_candidates(
            prices=
                prices,

            benchmark=
                benchmark,

            cash_returns=
                cash_returns,

            benchmark_returns=
                benchmark_returns,

            risk_matched_returns=
                risk_matched_returns,

            base_signals=
                base_signals,

            candidate_scores=
                candidate_scores,

            cfg=
                cfg,

            folds=
                folds,
        )
    )

    print(
        "\n========================================"
    )

    print(
        "WALK-FORWARD SELECTIONS"
    )

    print(
        "========================================"
    )

    print(
        selections.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Out-of-sample cost sensitivity.
    #
    # Model selections are FIXED from the 15bp training runs.
    # We do not reselect models separately for each cost case.
    # --------------------------------------------------------

    cost_rows = []

    dynamic_base = None
    fixed_base = None

    first_test_start = (
        selections[
            "test_start"
        ].iloc[0]
    )

    last_test_end = (
        selections[
            "test_end"
        ].iloc[-1]
    )

    for cost_bps in [
        5,
        15,
        35,
    ]:

        print(
            f"\nRunning OOS dynamic model "
            f"at {cost_bps} bps..."
        )

        dynamic = (
            run_dynamic_oos(
                prices=
                    prices,

                benchmark=
                    benchmark,

                cash_returns=
                    cash_returns,

                benchmark_returns=
                    benchmark_returns,

                risk_matched_returns=
                    risk_matched_returns,

                base_signals=
                    base_signals,

                candidate_scores=
                    candidate_scores,

                cfg=
                    cfg,

                selections=
                    selections,

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        dynamic_metrics = (
            calculate_metrics(
                dynamic
            )
        )

        cost_rows.append({
            "model":
                "WALK_FORWARD",

            "cost_bps":
                cost_bps,

            **dynamic_metrics,
        })

        # ----------------------------------------------------
        # Fixed trend baseline using the corrected v2
        # methodology.
        # ----------------------------------------------------

        fixed = (
            run_candidate_backtest(
                prices=
                    prices,

                benchmark=
                    benchmark,

                cash_returns=
                    cash_returns,

                benchmark_returns=
                    benchmark_returns,

                risk_matched_returns=
                    risk_matched_returns,

                base_signals=
                    base_signals,

                candidate_scores=
                    candidate_scores,

                candidate_name=
                    "T_63_126_252_W1",

                cfg=
                    cfg,

                start_date=
                    first_test_start,

                end_date=
                    last_test_end,

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        fixed_metrics = (
            calculate_metrics(
                fixed
            )
        )

        cost_rows.append({
            "model":
                "FIXED_BASE_TREND",

            "cost_bps":
                cost_bps,

            **fixed_metrics,
        })

        if cost_bps == 15:

            dynamic_base = (
                dynamic
            )

            fixed_base = (
                fixed
            )

    cost_table = pd.DataFrame(
        cost_rows
    )

    cost_table.to_csv(
        OUTPUT_DIR
        / "oos_cost_sensitivity.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Save base 15bp results.
    # --------------------------------------------------------

    dynamic_base[
        "history"
    ].to_csv(
        OUTPUT_DIR
        / "oos_daily_nav.csv"
    )

    dynamic_base[
        "weights"
    ].to_csv(
        OUTPUT_DIR
        / "oos_daily_weights.csv"
    )

    yearly = yearly_results(
        dynamic_base[
            "history"
        ]
    )

    yearly.to_csv(
        OUTPUT_DIR
        / "oos_yearly_returns.csv"
    )

    create_oos_chart(
        dynamic_history=
            dynamic_base[
                "history"
            ],

        fixed_history=
            fixed_base[
                "history"
            ],
    )

    # --------------------------------------------------------
    # Latest simulated holdings.
    # --------------------------------------------------------

    latest_weights = (
        dynamic_base[
            "weights"
        ]
        .iloc[-1]
        .drop(
            labels=[
                "candidate"
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

    latest_active = (
        latest_weights[
            latest_weights
            > 0.000001
        ]
        .sort_values(
            ascending=False
        )
    )

    latest_portfolio = pd.DataFrame({
        "weight":
            latest_active
    })

    latest_portfolio.loc[
        "CASH",
        "weight"
    ] = (
        1.0
        - latest_active.sum()
    )

    latest_portfolio.to_csv(
        OUTPUT_DIR
        / "latest_simulated_weights.csv"
    )

    dynamic_metrics_15 = (
        calculate_metrics(
            dynamic_base
        )
    )

    summary = {
        "research_version":
            "Fund-100 v2 walk-forward",

        "v1_config_sha256":
            v1_hash,

        "cash_proxy":
            (
                "Official Bank Rate "
                "minus 50 bps, "
                "floored at zero"
            ),

        "execution_delay":
            (
                "Signal generated at close; "
                "executed after next "
                "trading session return"
            ),

        "candidate_count":
            len(
                CANDIDATES
            ),

        "oos_metrics_15bps":
            dynamic_metrics_15,
    }

    with (
        OUTPUT_DIR
        / "v2_summary.json"
    ).open("w") as f:

        json.dump(
            summary,
            f,
            indent=2,
            default=float,
        )

    print(
        "\n========================================"
    )

    print(
        "OOS COST SENSITIVITY"
    )

    print(
        "========================================"
    )

    display_cols = [
        "model",
        "cost_bps",
        "final_nav_gbp",
        "benchmark_final_nav_gbp",
        "risk_matched_final_nav_gbp",
        "cagr",
        "benchmark_cagr",
        "risk_matched_cagr",
        "excess_cagr_vs_acwi",
        "excess_cagr_vs_risk_matched",
        "annual_volatility",
        "sharpe_excess_cash",
        "max_drawdown",
        "information_ratio_vs_acwi",
        "beta_to_acwi",
        "annualised_alpha",
        "alpha_hac_tstat",
        "annual_turnover",
        "total_transaction_cost_gbp",
    ]

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
        "\n========================================"
    )

    print(
        "OOS YEARLY RETURNS - 15 BPS"
    )

    print(
        "========================================"
    )

    print(
        yearly
        .round(4)
        .to_string()
    )

    print(
        "\n========================================"
    )

    print(
        "LATEST SIMULATED PORTFOLIO"
    )

    print(
        "========================================"
    )

    print(
        latest_portfolio
        .round(4)
        .to_string()
    )

    print(
        "\n========================================"
    )

    print(
        "IMPORTANT"
    )

    print(
        "========================================"
    )

    print(
        "These walk-forward periods are "
        "methodologically out-of-sample "
        "inside the program, but the broader "
        "research process has already viewed "
        "2010-2026 data."
    )

    print(
        "The genuinely unseen forward test "
        "begins from the current research date."
    )

    print(
        "\nFiles written to ./v2_outputs/"
    )


if __name__ == "__main__":
    main()

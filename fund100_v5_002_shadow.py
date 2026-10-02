from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import fund100_forward as forward_base
import fund100_experiment_runner as research_base
import fund100_experiment_runner_v1_2 as v12
import fund100_experiment_runner_v1_3 as v13


# ============================================================
# FUND-100 V5-002 SHADOW FORWARD LAB
# ============================================================
#
# V5-002 remains separate from the existing V3/V4/RM25
# Forward Lab.
#
# Shadow baseline:
#     2026-10-01
#
# First eligible strict shadow-forward session:
#     2026-10-02
#
# NO BROKER CONNECTION.
# NO LIVE ORDERS.
# PAPER / SHADOW RESEARCH ONLY.
# ============================================================


MODEL_NAME = "V5-002_SHADOW"

SHADOW_BASELINE_DATE = pd.Timestamp(
    "2026-10-01"
)

ONE_WAY_COST_BPS = 15.0

REBALANCE_WEEKS = 8

EMERGENCY_TOTAL_TRIGGER = 0.265
EMERGENCY_POSITION_TRIGGER = 0.14

HARD_TOTAL_LIMIT = 0.275
HARD_POSITION_LIMIT = 0.15

EMERGENCY_TARGET_TOTAL = 0.25
EMERGENCY_TARGET_POSITION = 0.125


# ============================================================
# FILES
# ============================================================

OUTPUT_DIR = Path(
    "shadow_outputs/v5_002"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LEDGER_PATH = (
    OUTPUT_DIR
    / "shadow_ledger.csv"
)

MANIFEST_PATH = (
    OUTPUT_DIR
    / "shadow_manifest.json"
)

STATE_PATH = (
    OUTPUT_DIR
    / "shadow_state.json"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "latest_shadow_report.json"
)

REVISION_LOG_PATH = (
    OUTPUT_DIR
    / "market_revision_log.csv"
)

SPEC_PATH = Path(
    "research_lab/challengers/V5-002.json"
)

RESULT_PATH = Path(
    "research_lab/results/V5-002.json"
)


LEDGER_COLUMNS = [
    "date",
    "row_type",
    "strategy",
    "previous_chain_hash",
    "chain_hash",
    "payload_json",
]


# ============================================================
# JSON HELPERS
# ============================================================

def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )


def sha256_json(
    obj,
) -> str:

    return research_base.sha256_text(
        canonical_json(
            obj
        )
    )


def weights_to_dict(
    weights: pd.Series | None,
):

    if weights is None:
        return None

    return {
        asset:
            float(
                weights.get(
                    asset,
                    0.0,
                )
            )
        for asset
        in research_base.EQUITY_UNIVERSE
    }


def dict_to_weights(
    values,
):

    if values is None:
        return None

    return (
        pd.Series(
            values,
            dtype=float,
        )
        .reindex(
            research_base.EQUITY_UNIVERSE
        )
        .fillna(
            0.0
        )
    )


# ============================================================
# FROZEN STRATEGY LINEAGE
# ============================================================

def load_strategy_lineage():

    if not SPEC_PATH.exists():

        raise RuntimeError(
            "V5-002 challenger specification is missing."
        )

    if not RESULT_PATH.exists():

        raise RuntimeError(
            "V5-002 research result is missing."
        )

    with SPEC_PATH.open(
        "r"
    ) as f:

        spec = json.load(
            f
        )

    with RESULT_PATH.open(
        "r"
    ) as f:

        result = json.load(
            f
        )

    if (
        spec.get(
            "experiment_id"
        )
        != "V5-002"
    ):

        raise RuntimeError(
            "Unexpected challenger specification."
        )

    if (
        result.get(
            "experiment_id"
        )
        != "V5-002"
    ):

        raise RuntimeError(
            "Unexpected research result."
        )

    if (
        result.get(
            "status"
        )
        != "RESEARCH_SURVIVOR"
    ):

        raise RuntimeError(
            "V5-002 is not recorded as "
            "RESEARCH_SURVIVOR."
        )

    spec_hash = (
        sha256_json(
            spec
        )
    )

    if (
        result.get(
            "spec_hash"
        )
        != spec_hash
    ):

        raise RuntimeError(
            "V5-002 specification hash does not "
            "match the completed research result."
        )

    candidate = (
        spec[
            "candidate"
        ]
    )

    required = {
        "rebalance_weeks":
            REBALANCE_WEEKS,

        "emergency_risk_rebalance":
            True,

        "emergency_total_trigger":
            EMERGENCY_TOTAL_TRIGGER,

        "emergency_position_trigger":
            EMERGENCY_POSITION_TRIGGER,

        "hard_total_limit":
            HARD_TOTAL_LIMIT,

        "hard_position_limit":
            HARD_POSITION_LIMIT,

        "emergency_target_total":
            EMERGENCY_TARGET_TOTAL,

        "emergency_target_position":
            EMERGENCY_TARGET_POSITION,
    }

    for key, expected in required.items():

        actual = candidate.get(
            key
        )

        if actual != expected:

            raise RuntimeError(
                f"V5-002 frozen parameter mismatch: "
                f"{key}"
            )

    result_hash = (
        sha256_json(
            result
        )
    )

    return (
        spec,
        result,
        spec_hash,
        result_hash,
    )


# ============================================================
# SHADOW MANIFEST
# ============================================================

def build_manifest(
    spec_hash: str,
    result_hash: str,
    result: dict,
):

    definition = {
        "shadow_protocol_version":
            "1.0",

        "strategy":
            MODEL_NAME,

        "research_experiment":
            "V5-002",

        "research_status":
            result[
                "status"
            ],

        "research_spec_hash":
            spec_hash,

        "research_result_hash":
            result_hash,

        "research_data_hash":
            result[
                "data_hash"
            ],

        "historical_research_cutoff":
            result[
                "historical_cutoff"
            ],

        "shadow_baseline_date":
            str(
                SHADOW_BASELINE_DATE.date()
            ),

        "first_eligible_forward_date":
            "2026-10-02",

        "one_way_cost_bps":
            ONE_WAY_COST_BPS,

        "rebalance_weeks":
            REBALANCE_WEEKS,

        "emergency_total_trigger":
            EMERGENCY_TOTAL_TRIGGER,

        "emergency_position_trigger":
            EMERGENCY_POSITION_TRIGGER,

        "hard_total_limit":
            HARD_TOTAL_LIMIT,

        "hard_position_limit":
            HARD_POSITION_LIMIT,

        "emergency_target_total":
            EMERGENCY_TARGET_TOTAL,

        "emergency_target_position":
            EMERGENCY_TARGET_POSITION,

        "execution_rule":
            (
                "Signal on completed daily data; "
                "pending target executes after the "
                "next completed session return."
            ),

        "ledger_rule":
            (
                "Previously recorded shadow observations "
                "must never be rewritten."
            ),

        "promotion_rule":
            (
                "Shadow evidence does not automatically "
                "replace any Forward Lab strategy."
            ),
    }

    return definition


def ensure_manifest(
    manifest: dict,
):

    manifest_hash = (
        sha256_json(
            manifest
        )
    )

    if MANIFEST_PATH.exists():

        with MANIFEST_PATH.open(
            "r"
        ) as f:

            existing = json.load(
                f
            )

        if (
            existing[
                "manifest_hash"
            ]
            != manifest_hash
        ):

            raise RuntimeError(
                "V5-002 shadow manifest changed. "
                "Refusing to continue."
            )

        return manifest_hash

    output = {
        **manifest,

        "manifest_hash":
            manifest_hash,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    with MANIFEST_PATH.open(
        "w"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )

    return manifest_hash


# ============================================================
# HYBRID DATASET
# ============================================================

def load_shadow_market_data(
    cfg: dict,
    protocol: dict,
):

    # --------------------------------------------------------
    # Research history through 2026-09-16 comes from the
    # immutable Research Dataset v2.
    # --------------------------------------------------------

    frozen_prices, frozen_benchmark = (
        v13.load_frozen_history(
            cfg=
                cfg,
            protocol=
                protocol,
        )
    )

    # --------------------------------------------------------
    # Only observations after the historical cutoff come from
    # the current Forward Lab market-data feed.
    # --------------------------------------------------------

    live_prices, live_benchmark = (
        forward_base.load_completed_market_data(
            cfg
        )
    )

    cutoff = pd.Timestamp(
        protocol[
            "historical_cutoff"
        ]
    )

    frozen_prices = (
        frozen_prices.loc[
            :cutoff
        ]
        .copy()
    )

    frozen_benchmark = (
        frozen_benchmark.loc[
            :cutoff
        ]
        .copy()
    )

    live_prices = (
        live_prices.loc[
            live_prices.index
            > cutoff,
            research_base.EQUITY_UNIVERSE,
        ]
        .copy()
    )

    live_benchmark = (
        live_benchmark.loc[
            live_benchmark.index
            > cutoff
        ]
        .copy()
    )

    prices = (
        pd.concat(
            [
                frozen_prices,
                live_prices,
            ]
        )
        .sort_index()
    )

    prices = (
        prices[
            ~prices.index.duplicated(
                keep="last"
            )
        ]
    )

    benchmark = (
        pd.concat(
            [
                frozen_benchmark,
                live_benchmark,
            ]
        )
        .sort_index()
    )

    benchmark = (
        benchmark[
            ~benchmark.index.duplicated(
                keep="last"
            )
        ]
    )

    benchmark = (
        benchmark.reindex(
            prices.index
        )
    )

    if (
        SHADOW_BASELINE_DATE
        not in prices.index
    ):

        raise RuntimeError(
            "Shadow baseline date 2026-10-01 "
            "is not available in completed market data."
        )

    if (
        prices.loc[
            SHADOW_BASELINE_DATE:
        ]
        .isna()
        .any()
        .any()
    ):

        raise RuntimeError(
            "Missing market data in V5-002 "
            "shadow region."
        )

    if (
        benchmark.loc[
            SHADOW_BASELINE_DATE:
        ]
        .isna()
        .any()
    ):

        raise RuntimeError(
            "Missing benchmark data in V5-002 "
            "shadow region."
        )

    return (
        prices,
        benchmark,
    )


# ============================================================
# MARKET SNAPSHOT HASH
# ============================================================

def market_hash(
    date: pd.Timestamp,
    prices: pd.DataFrame,
    benchmark: pd.Series,
):

    payload = {
        "date":
            str(
                date.date()
            ),

        "benchmark":
            f"{float(benchmark.loc[date]):.8f}",

        "assets": {
            asset:
                f"{float(prices.loc[date, asset]):.8f}"
            for asset
            in research_base.EQUITY_UNIVERSE
        },
    }

    return sha256_json(
        payload
    )


# ============================================================
# EMPTY STATE
# ============================================================

def empty_state():

    return {
        "last_date":
            None,

        "nav":
            100.0,

        "benchmark_nav":
            100.0,

        "satellite_weights":
            pd.Series(
                0.0,
                index=
                    research_base.EQUITY_UNIVERSE,
                dtype=float,
            ),

        "pending_target":
            None,

        "pending_source":
            None,

        "cumulative_turnover":
            0.0,

        "cumulative_cost_gbp":
            0.0,

        "emergency_signals":
            0,

        "emergency_executions":
            0,
    }


# ============================================================
# RISK CHECK
# ============================================================

def check_hard_limits(
    weights: pd.Series,
):

    total = float(
        weights.sum()
    )

    largest = float(
        weights.max()
    )

    if (
        total
        > HARD_TOTAL_LIMIT
        + 1e-8
    ):

        raise RuntimeError(
            "V5-002 shadow hard total "
            "risk limit breached."
        )

    if (
        largest
        > HARD_POSITION_LIMIT
        + 1e-8
    ):

        raise RuntimeError(
            "V5-002 shadow hard position "
            "risk limit breached."
        )

    if (
        weights
        < -1e-12
    ).any():

        raise RuntimeError(
            "Negative satellite weight detected."
        )


# ============================================================
# ONE COMPLETED SESSION
# ============================================================

def process_one_day(
    state: dict,
    date: pd.Timestamp,
    signals: dict,
    zero_market_return: bool = False,
):

    weights = (
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

    asset_returns = (
        signals[
            "asset_returns"
        ]
        .loc[
            date
        ]
        .reindex(
            research_base.EQUITY_UNIVERSE
        )
        .fillna(
            0.0
        )
    )

    benchmark_return = (
        signals[
            "benchmark_returns"
        ]
        .loc[
            date
        ]
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

        asset_returns = (
            asset_returns
            * 0.0
        )

    core_weight = max(
        0.0,
        1.0
        - float(
            weights.sum()
        ),
    )

    gross_portfolio_return = float(
        core_weight
        * benchmark_return
        +
        (
            weights
            * asset_returns
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
    # Natural drift after market movement
    # --------------------------------------------------------

    weights = (
        weights
        * (
            1.0
            + asset_returns
        )
        / denominator
    )

    check_hard_limits(
        weights
    )

    turnover_today = 0.0
    cost_today = 0.0

    emergency_executed = False
    emergency_signal = False

    # --------------------------------------------------------
    # Execute yesterday's pending target
    # --------------------------------------------------------

    if (
        state[
            "pending_target"
        ]
        is not None
    ):

        desired = (
            state[
                "pending_target"
            ].copy()
        )

        old_weights = (
            weights.copy()
        )

        old_core = max(
            0.0,
            1.0
            - float(
                old_weights.sum()
            ),
        )

        if (
            state[
                "pending_source"
            ]
            == "EMERGENCY"
        ):

            executed = (
                desired.copy()
            )

            state[
                "emergency_executions"
            ] += 1

            emergency_executed = True

        else:

            executed = (
                research_base.apply_trade_threshold(
                    current=
                        old_weights,

                    desired=
                        desired,
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
                    - old_weights
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
            state[
                "nav"
            ]
            * turnover_today
            * (
                ONE_WAY_COST_BPS
                / 10_000.0
            )
        )

        state[
            "nav"
        ] -= (
            cost_today
        )

        state[
            "cumulative_turnover"
        ] += (
            turnover_today
        )

        state[
            "cumulative_cost_gbp"
        ] += (
            cost_today
        )

        weights = (
            executed
        )

        state[
            "pending_target"
        ] = None

        state[
            "pending_source"
        ] = None

    check_hard_limits(
        weights
    )

    # --------------------------------------------------------
    # Scheduled 8-week V5-002 strategic signal
    # --------------------------------------------------------

    if research_base.is_signal_day(
        date=
            date,

        rebalance_weeks=
            REBALANCE_WEEKS,
    ):

        state[
            "pending_target"
        ] = (
            research_base.build_target(
                date=
                    date,

                current_weights=
                    weights,

                signals=
                    signals,
            )
        )

        state[
            "pending_source"
        ] = (
            "SCHEDULED"
        )

    # --------------------------------------------------------
    # Emergency risk-band signal
    # --------------------------------------------------------

    else:

        total_weight = float(
            weights.sum()
        )

        largest_position = float(
            weights.max()
        )

        risk_triggered = (
            total_weight
            >= EMERGENCY_TOTAL_TRIGGER
            or
            largest_position
            >= EMERGENCY_POSITION_TRIGGER
        )

        if risk_triggered:

            emergency_target = (
                v12.build_emergency_target(
                    current_weights=
                        weights,

                    target_total=
                        EMERGENCY_TARGET_TOTAL,

                    target_position=
                        EMERGENCY_TARGET_POSITION,
                )
            )

            change_required = float(
                (
                    emergency_target
                    - weights
                )
                .abs()
                .sum()
            )

            if (
                change_required
                > 1e-12
            ):

                state[
                    "pending_target"
                ] = (
                    emergency_target
                )

                state[
                    "pending_source"
                ] = (
                    "EMERGENCY"
                )

                state[
                    "emergency_signals"
                ] += 1

                emergency_signal = True

    state[
        "satellite_weights"
    ] = (
        weights
    )

    state[
        "last_date"
    ] = (
        date
    )

    daily_return = (
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

    return {
        "daily_return":
            daily_return,

        "benchmark_return":
            benchmark_daily_return,

        "active_return":
            (
                daily_return
                - benchmark_daily_return
            ),

        "gross_overlay_return":
            gross_overlay_return,

        "cost_drag_return":
            (
                daily_return
                - gross_portfolio_return
            ),

        "turnover":
            turnover_today,

        "transaction_cost_gbp":
            cost_today,

        "emergency_signal":
            emergency_signal,

        "emergency_execution":
            emergency_executed,
    }


# ============================================================
# BOOTSTRAP STATE TO 1 OCTOBER
# ============================================================

def bootstrap_to_baseline(
    signals: dict,
    protocol: dict,
):

    state = (
        empty_state()
    )

    evaluation_start = pd.Timestamp(
        protocol[
            "evaluation_start"
        ]
    )

    dates = (
        signals[
            "asset_returns"
        ]
        .index
    )

    dates = dates[
        (
            dates
            >= evaluation_start
        )
        &
        (
            dates
            <= SHADOW_BASELINE_DATE
        )
    ]

    if len(
        dates
    ) < 2:

        raise RuntimeError(
            "Insufficient history to bootstrap "
            "V5-002 shadow state."
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

            zero_market_return=
                (
                    i == 0
                ),
        )

    # --------------------------------------------------------
    # Preserve holdings and pending orders, but reset all
    # performance accounting at the shadow baseline.
    # --------------------------------------------------------

    state[
        "nav"
    ] = 100.0

    state[
        "benchmark_nav"
    ] = 100.0

    state[
        "cumulative_turnover"
    ] = 0.0

    state[
        "cumulative_cost_gbp"
    ] = 0.0

    state[
        "emergency_signals"
    ] = 0

    state[
        "emergency_executions"
    ] = 0

    state[
        "last_date"
    ] = (
        SHADOW_BASELINE_DATE
    )

    return state


# ============================================================
# PAYLOAD
# ============================================================

def build_payload(
    row_type: str,
    state: dict,
    date: pd.Timestamp,
    market_snapshot_hash: str,
    manifest_hash: str,
    daily: dict | None = None,
):

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

            "emergency_signal":
                False,

            "emergency_execution":
                False,
        }

    return {
        "date":
            str(
                date.date()
            ),

        "row_type":
            row_type,

        "strategy":
            MODEL_NAME,

        "manifest_hash":
            manifest_hash,

        "market_snapshot_hash":
            market_snapshot_hash,

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

        "relative_wealth_vs_acwi":
            (
                float(
                    state[
                        "nav"
                    ]
                )
                /
                float(
                    state[
                        "benchmark_nav"
                    ]
                )
                - 1.0
            ),

        "satellite_weights":
            weights_to_dict(
                state[
                    "satellite_weights"
                ]
            ),

        "pending_target":
            weights_to_dict(
                state[
                    "pending_target"
                ]
            ),

        "pending_source":
            state[
                "pending_source"
            ],

        "cumulative_turnover":
            float(
                state[
                    "cumulative_turnover"
                ]
            ),

        "cumulative_cost_gbp":
            float(
                state[
                    "cumulative_cost_gbp"
                ]
            ),

        "emergency_signals":
            int(
                state[
                    "emergency_signals"
                ]
            ),

        "emergency_executions":
            int(
                state[
                    "emergency_executions"
                ]
            ),

        **daily,
    }


def payload_to_row(
    payload: dict,
    previous_hash: str,
):

    payload_json = (
        canonical_json(
            payload
        )
    )

    chain_hash = (
        research_base.sha256_text(
            previous_hash
            + "|"
            + payload_json
        )
    )

    return {
        "date":
            payload[
                "date"
            ],

        "row_type":
            payload[
                "row_type"
            ],

        "strategy":
            payload[
                "strategy"
            ],

        "previous_chain_hash":
            previous_hash,

        "chain_hash":
            chain_hash,

        "payload_json":
            payload_json,
    }


# ============================================================
# LEDGER VALIDATION
# ============================================================

def validate_ledger(
    ledger: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest_hash: str,
):

    if ledger.empty:

        raise RuntimeError(
            "V5-002 shadow ledger is empty."
        )

    if list(
        ledger.columns
    ) != LEDGER_COLUMNS:

        raise RuntimeError(
            "Unexpected V5-002 shadow ledger columns."
        )

    previous = (
        "GENESIS"
    )

    revisions = []

    for i, row in ledger.iterrows():

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
            != MODEL_NAME
        ):

            raise RuntimeError(
                "V5-002 shadow strategy mismatch."
            )

        if (
            payload[
                "manifest_hash"
            ]
            != manifest_hash
        ):

            raise RuntimeError(
                "V5-002 shadow manifest lineage "
                "mismatch."
            )

        if (
            str(
                row[
                    "previous_chain_hash"
                ]
            )
            != previous
        ):

            raise RuntimeError(
                "V5-002 shadow hash chain is broken."
            )

        expected = (
            research_base.sha256_text(
                previous
                + "|"
                + payload_json
            )
        )

        if (
            expected
            != str(
                row[
                    "chain_hash"
                ]
            )
        ):

            raise RuntimeError(
                "V5-002 shadow ledger hash mismatch."
            )

        if (
            i == 0
            and payload[
                "row_type"
            ]
            != "BASELINE"
        ):

            raise RuntimeError(
                "V5-002 shadow ledger does not "
                "begin with BASELINE."
            )

        date = pd.Timestamp(
            payload[
                "date"
            ]
        )

        if date in prices.index:

            current_hash = (
                market_hash(
                    date=
                        date,

                    prices=
                        prices,

                    benchmark=
                        benchmark,
                )
            )

            stored_hash = (
                payload[
                    "market_snapshot_hash"
                ]
            )

            if (
                current_hash
                != stored_hash
            ):

                revisions.append({
                    "detected_utc":
                        datetime.now(
                            timezone.utc
                        ).isoformat(),

                    "date":
                        str(
                            date.date()
                        ),

                    "stored_market_hash":
                        stored_hash,

                    "current_market_hash":
                        current_hash,
                })

        previous = (
            expected
        )

    return revisions


# ============================================================
# REVISION LOG
# ============================================================

def save_revisions(
    revisions: list[dict],
):

    if not revisions:
        return

    incoming = pd.DataFrame(
        revisions
    )

    if REVISION_LOG_PATH.exists():

        existing = pd.read_csv(
            REVISION_LOG_PATH,
            dtype=str,
        )

        combined = pd.concat(
            [
                existing,
                incoming,
            ],
            ignore_index=True,
        )

    else:

        combined = (
            incoming
        )

    combined = (
        combined
        .drop_duplicates(
            subset=[
                "date",
                "stored_market_hash",
                "current_market_hash",
            ],
            keep="first",
        )
    )

    combined.to_csv(
        REVISION_LOG_PATH,
        index=False,
    )


# ============================================================
# RESTORE STATE
# ============================================================

def restore_state(
    ledger: pd.DataFrame,
):

    last = (
        ledger.iloc[
            -1
        ]
    )

    payload = json.loads(
        str(
            last[
                "payload_json"
            ]
        )
    )

    state = (
        empty_state()
    )

    state[
        "last_date"
    ] = pd.Timestamp(
        payload[
            "date"
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
        "satellite_weights"
    ] = (
        dict_to_weights(
            payload[
                "satellite_weights"
            ]
        )
    )

    state[
        "pending_target"
    ] = (
        dict_to_weights(
            payload[
                "pending_target"
            ]
        )
    )

    state[
        "pending_source"
    ] = (
        payload[
            "pending_source"
        ]
    )

    state[
        "cumulative_turnover"
    ] = float(
        payload[
            "cumulative_turnover"
        ]
    )

    state[
        "cumulative_cost_gbp"
    ] = float(
        payload[
            "cumulative_cost_gbp"
        ]
    )

    state[
        "emergency_signals"
    ] = int(
        payload[
            "emergency_signals"
        ]
    )

    state[
        "emergency_executions"
    ] = int(
        payload[
            "emergency_executions"
        ]
    )

    return state


# ============================================================
# STATE / REPORT
# ============================================================

def save_state(
    state: dict,
    manifest_hash: str,
):

    output = {
        "updated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            MODEL_NAME,

        "manifest_hash":
            manifest_hash,

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

        "relative_wealth_vs_acwi":
            (
                float(
                    state[
                        "nav"
                    ]
                )
                /
                float(
                    state[
                        "benchmark_nav"
                    ]
                )
                - 1.0
            ),

        "satellite_weights":
            weights_to_dict(
                state[
                    "satellite_weights"
                ]
            ),

        "pending_target":
            weights_to_dict(
                state[
                    "pending_target"
                ]
            ),

        "pending_source":
            state[
                "pending_source"
            ],

        "cumulative_turnover":
            float(
                state[
                    "cumulative_turnover"
                ]
            ),

        "cumulative_cost_gbp":
            float(
                state[
                    "cumulative_cost_gbp"
                ]
            ),

        "emergency_signals":
            int(
                state[
                    "emergency_signals"
                ]
            ),

        "emergency_executions":
            int(
                state[
                    "emergency_executions"
                ]
            ),
    }

    with STATE_PATH.open(
        "w"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )


def save_report(
    state: dict,
    manifest_hash: str,
    new_sessions: int,
    revisions: list[dict],
):

    output = {
        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            MODEL_NAME,

        "manifest_hash":
            manifest_hash,

        "shadow_baseline":
            str(
                SHADOW_BASELINE_DATE.date()
            ),

        "first_eligible_forward_date":
            "2026-10-02",

        "last_processed_date":
            str(
                state[
                    "last_date"
                ].date()
            ),

        "new_sessions_appended":
            new_sessions,

        "paper_nav_gbp":
            float(
                state[
                    "nav"
                ]
            ),

        "benchmark_nav_gbp":
            float(
                state[
                    "benchmark_nav"
                ]
            ),

        "relative_wealth_vs_acwi":
            (
                float(
                    state[
                        "nav"
                    ]
                )
                /
                float(
                    state[
                        "benchmark_nav"
                    ]
                )
                - 1.0
            ),

        "cumulative_turnover":
            float(
                state[
                    "cumulative_turnover"
                ]
            ),

        "cumulative_cost_gbp":
            float(
                state[
                    "cumulative_cost_gbp"
                ]
            ),

        "emergency_signals":
            int(
                state[
                    "emergency_signals"
                ]
            ),

        "emergency_executions":
            int(
                state[
                    "emergency_executions"
                ]
            ),

        "market_revision_records_detected":
            len(
                revisions
            ),
    }

    with REPORT_PATH.open(
        "w"
    ) as f:

        json.dump(
            output,
            f,
            indent=2,
        )


# ============================================================
# PRINT STATUS
# ============================================================

def print_status(
    state: dict,
    new_sessions: int,
    revisions: list[dict],
):

    weights = (
        state[
            "satellite_weights"
        ]
    )

    holdings = (
        weights[
            weights
            > 1e-8
        ]
        .sort_values(
            ascending=False
        )
    )

    print(
        "\n============================================"
    )

    print(
        "V5-002 SHADOW FORWARD STATUS"
    )

    print(
        "============================================"
    )

    print(
        f"Shadow baseline: "
        f"{SHADOW_BASELINE_DATE.date()}"
    )

    print(
        "First strict shadow-forward date: "
        "2026-10-02"
    )

    print(
        f"Last processed date: "
        f"{state['last_date'].date()}"
    )

    print(
        f"New strict shadow sessions appended: "
        f"{new_sessions}"
    )

    print(
        f"Paper NAV: "
        f"£{state['nav']:.4f}"
    )

    print(
        f"ACWI benchmark NAV: "
        f"£{state['benchmark_nav']:.4f}"
    )

    relative = (
        state[
            "nav"
        ]
        /
        state[
            "benchmark_nav"
        ]
        - 1.0
    )

    print(
        f"Relative wealth vs ACWI: "
        f"{relative:.4%}"
    )

    print(
        "\nExecuted holdings:"
    )

    print(
        f"ACWI_CORE="
        f"{1.0 - float(weights.sum()):.2%}"
    )

    for asset, value in holdings.items():

        print(
            f"{asset}="
            f"{float(value):.2%}"
        )

    print(
        "\nPending next-session target:"
    )

    if (
        state[
            "pending_target"
        ]
        is None
    ):

        print(
            "None"
        )

    else:

        print(
            f"Source: "
            f"{state['pending_source']}"
        )

        target = (
            state[
                "pending_target"
            ]
        )

        for asset, value in (
            target[
                target > 1e-8
            ]
            .sort_values(
                ascending=False
            )
            .items()
        ):

            print(
                f"{asset}="
                f"{float(value):.2%}"
            )

    print(
        f"\nCumulative turnover: "
        f"{state['cumulative_turnover']:.4f}"
    )

    print(
        f"Cumulative simulated costs: "
        f"£{state['cumulative_cost_gbp']:.4f}"
    )

    print(
        f"Emergency signals: "
        f"{state['emergency_signals']}"
    )

    print(
        f"Emergency executions: "
        f"{state['emergency_executions']}"
    )

    print(
        f"Historical vendor revision "
        f"records detected this run: "
        f"{len(revisions)}"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "V5-002 remains a shadow research strategy."
    )

    print(
        "It has NOT replaced V3, V4, or RM25."
    )

    print(
        "No broker connection was used."
    )

    print(
        "No orders were sent anywhere."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 V5-002 SHADOW FORWARD LAB"
    )

    print(
        "============================================"
    )

    (
        spec,
        result,
        spec_hash,
        result_hash,
    ) = (
        load_strategy_lineage()
    )

    print(
        "\nV5-002 research lineage verified."
    )

    print(
        f"Specification SHA256: "
        f"{spec_hash}"
    )

    print(
        f"Research result SHA256: "
        f"{result_hash}"
    )

    manifest = (
        build_manifest(
            spec_hash=
                spec_hash,

            result_hash=
                result_hash,

            result=
                result,
        )
    )

    manifest_hash = (
        ensure_manifest(
            manifest
        )
    )

    print(
        f"Shadow manifest SHA256: "
        f"{manifest_hash}"
    )

    protocol = (
        research_base.load_protocol()
    )

    cfg, config_hash = (
        research_base.load_config()
    )

    print(
        f"\nFrozen config SHA256: "
        f"{config_hash}"
    )

    print(
        "\nLoading completed market data..."
    )

    prices, benchmark = (
        load_shadow_market_data(
            cfg=
                cfg,

            protocol=
                protocol,
        )
    )

    print(
        f"Available completed data: "
        f"{prices.index[0].date()} "
        f"to "
        f"{prices.index[-1].date()}"
    )

    print(
        "\nBuilding V5-002 signals..."
    )

    signals = (
        research_base.build_signals(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    revisions = []

    # ========================================================
    # FIRST RUN
    # ========================================================

    if not LEDGER_PATH.exists():

        print(
            "\nNo V5-002 shadow ledger found."
        )

        print(
            "Bootstrapping frozen strategy state "
            "to 2026-10-01..."
        )

        state = (
            bootstrap_to_baseline(
                signals=
                    signals,

                protocol=
                    protocol,
            )
        )

        payload = (
            build_payload(
                row_type=
                    "BASELINE",

                state=
                    state,

                date=
                    SHADOW_BASELINE_DATE,

                market_snapshot_hash=
                    market_hash(
                        date=
                            SHADOW_BASELINE_DATE,

                        prices=
                            prices,

                        benchmark=
                            benchmark,
                    ),

                manifest_hash=
                    manifest_hash,
            )
        )

        row = (
            payload_to_row(
                payload=
                    payload,

                previous_hash=
                    "GENESIS",
            )
        )

        ledger = pd.DataFrame(
            [
                row
            ],
            columns=
                LEDGER_COLUMNS,
        )

        ledger.to_csv(
            LEDGER_PATH,
            index=False,
        )

        print(
            "V5-002 shadow baseline created."
        )

    # ========================================================
    # EXISTING LEDGER
    # ========================================================

    else:

        print(
            "\nExisting V5-002 shadow ledger found."
        )

        ledger = pd.read_csv(
            LEDGER_PATH,
            dtype=str,
        )

        revisions = (
            validate_ledger(
                ledger=
                    ledger,

                prices=
                    prices,

                benchmark=
                    benchmark,

                manifest_hash=
                    manifest_hash,
            )
        )

        save_revisions(
            revisions
        )

        print(
            "V5-002 append-only hash chain passed."
        )

        state = (
            restore_state(
                ledger
            )
        )

    # ========================================================
    # APPEND NEW COMPLETED DATES
    # ========================================================

    last_date = (
        state[
            "last_date"
        ]
    )

    new_dates = (
        prices.index[
            prices.index
            > last_date
        ]
    )

    previous_hash = str(
        ledger.iloc[
            -1
        ][
            "chain_hash"
        ]
    )

    new_rows = []

    for date in new_dates:

        daily = (
            process_one_day(
                state=
                    state,

                date=
                    date,

                signals=
                    signals,
            )
        )

        payload = (
            build_payload(
                row_type=
                    "SHADOW_FORWARD",

                state=
                    state,

                date=
                    date,

                market_snapshot_hash=
                    market_hash(
                        date=
                            date,

                        prices=
                            prices,

                        benchmark=
                            benchmark,
                    ),

                manifest_hash=
                    manifest_hash,

                daily=
                    daily,
            )
        )

        row = (
            payload_to_row(
                payload=
                    payload,

                previous_hash=
                    previous_hash,
            )
        )

        previous_hash = (
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

        ledger.to_csv(
            LEDGER_PATH,
            index=False,
        )

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    revisions_after = (
        validate_ledger(
            ledger=
                ledger,

            prices=
                prices,

            benchmark=
                benchmark,

            manifest_hash=
                manifest_hash,
        )
    )

    save_revisions(
        revisions_after
    )

    save_state(
        state=
            state,

        manifest_hash=
            manifest_hash,
    )

    save_report(
        state=
            state,

        manifest_hash=
            manifest_hash,

        new_sessions=
            len(
                new_dates
            ),

        revisions=
            revisions_after,
    )

    print_status(
        state=
            state,

        new_sessions=
            len(
                new_dates
        ),

        revisions=
            revisions_after,
    )

    print(
        "\n============================================"
    )

    print(
        "V5-002 SHADOW FORWARD RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()

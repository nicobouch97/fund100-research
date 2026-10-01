from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import fund100_experiment_runner as base
import fund100_experiment_runner_v1_1 as v11


# ============================================================
# FUND-100 AUTONOMOUS RESEARCH LAB v1.2
# ============================================================
#
# Adds support for a pre-registered emergency risk-band
# rebalance.
#
# V5-002:
#
# - normal strategic rebalance every 8 weeks
# - emergency trigger if:
#
#       total satellite weight >= 26.5%
#
#   OR
#
#       any satellite position >= 14.0%
#
# - emergency target restores:
#
#       total satellite <= 25.0%
#       individual satellite <= 12.5%
#
# - frozen hard limits remain:
#
#       total satellite <= 27.5%
#       individual satellite <= 15.0%
#
# Hard limits are NOT loosened.
# ============================================================


# ============================================================
# EMERGENCY TARGET
# ============================================================

def build_emergency_target(
    current_weights: pd.Series,
    target_total: float,
    target_position: float,
) -> pd.Series:
    """
    Reduce existing satellite positions without changing
    their identities.

    This is a risk-control rebalance, not a fresh alpha signal.
    """

    target = (
        current_weights
        .copy()
        .clip(
            lower=0.0,
            upper=float(
                target_position
            ),
        )
    )

    total = float(
        target.sum()
    )

    if (
        total > float(
            target_total
        )
        and total > 0
    ):

        target *= (
            float(
                target_total
            )
            / total
        )

    return target


# ============================================================
# V1.2 BACKTEST
# ============================================================

def run_model_v12(
    signals: dict,
    evaluation_start: str,
    rebalance_weeks: int,
    one_way_cost_bps: float,
    emergency_risk_rebalance: bool = False,
    emergency_total_trigger: float = 0.265,
    emergency_position_trigger: float = 0.14,
    hard_total_limit: float = 0.275,
    hard_position_limit: float = 0.15,
    emergency_target_total: float = 0.25,
    emergency_target_position: float = 0.125,
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
            index=base.EQUITY_UNIVERSE,
            dtype=float,
        )
    )

    pending_target = None
    pending_source = None

    nav = (
        base.START_NAV
    )

    total_turnover = 0.0
    total_cost_gbp = 0.0

    emergency_signals = 0
    emergency_executions = 0

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
            .loc[
                date
            ]
            .reindex(
                base.EQUITY_UNIVERSE
            )
            .fillna(
                0.0
            )
        )

        benchmark_return = (
            benchmark_returns.loc[
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

        # Evaluation account begins at £100.
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
        # DAILY MARKET RETURN
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

        # ----------------------------------------------------
        # NATURAL WEIGHT DRIFT
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
        # FROZEN HARD RISK LIMITS
        #
        # If market movement gets beyond these limits before
        # the queued risk rebalance can execute, the challenger
        # still fails.
        # ----------------------------------------------------

        if (
            float(
                satellite_weights.sum()
            )
            > float(
                hard_total_limit
            )
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite sleeve drift limit breached."
            )

        if (
            float(
                satellite_weights.max()
            )
            > float(
                hard_position_limit
            )
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite position drift limit breached."
            )

        turnover_today = 0.0
        cost_today = 0.0

        emergency_executed_today = False
        emergency_signal_today = False

        # ----------------------------------------------------
        # EXECUTE PREVIOUS SESSION'S PENDING TARGET
        #
        # This preserves the same conservative execution timing
        # used elsewhere in Fund-100.
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

            if (
                pending_source
                == "EMERGENCY"
            ):

                # Emergency risk reduction deliberately bypasses
                # the ordinary 2.5% minimum-trade threshold.
                executed = (
                    pending_target.copy()
                )

                emergency_executions += 1
                emergency_executed_today = True

            else:

                executed = (
                    base.apply_trade_threshold(
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
            pending_source = None

        # ----------------------------------------------------
        # AFTER EXECUTION, CONFIRM TARGET IS INSIDE HARD LIMITS
        # ----------------------------------------------------

        if (
            float(
                satellite_weights.sum()
            )
            > float(
                hard_total_limit
            )
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite sleeve drift limit breached."
            )

        if (
            float(
                satellite_weights.max()
            )
            > float(
                hard_position_limit
            )
            + 1e-8
        ):

            raise RuntimeError(
                "Satellite position drift limit breached."
            )

        # ----------------------------------------------------
        # SCHEDULED STRATEGIC SIGNAL
        #
        # Scheduled signal takes priority on scheduled dates.
        # ----------------------------------------------------

        if base.is_signal_day(
            date=
                date,

            rebalance_weeks=
                rebalance_weeks,
        ):

            pending_target = (
                base.build_target(
                    date=
                        date,

                    current_weights=
                        satellite_weights,

                    signals=
                        signals,
                )
            )

            pending_source = (
                "SCHEDULED"
            )

        # ----------------------------------------------------
        # EMERGENCY RISK-BAND SIGNAL
        #
        # Only when today is NOT already a strategic signal
        # date.
        # ----------------------------------------------------

        elif emergency_risk_rebalance:

            total_weight = float(
                satellite_weights.sum()
            )

            largest_position = float(
                satellite_weights.max()
            )

            risk_triggered = (
                total_weight
                >= float(
                    emergency_total_trigger
                )
                or
                largest_position
                >= float(
                    emergency_position_trigger
                )
            )

            if risk_triggered:

                emergency_target = (
                    build_emergency_target(
                        current_weights=
                            satellite_weights,

                        target_total=
                            emergency_target_total,

                        target_position=
                            emergency_target_position,
                    )
                )

                change_required = float(
                    (
                        emergency_target
                        - satellite_weights
                    )
                    .abs()
                    .sum()
                )

                if (
                    change_required
                    > 1e-12
                ):

                    pending_target = (
                        emergency_target
                    )

                    pending_source = (
                        "EMERGENCY"
                    )

                    emergency_signals += 1
                    emergency_signal_today = True

        # ----------------------------------------------------
        # ACCOUNTING
        # ----------------------------------------------------

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

            "largest_satellite_position":
                float(
                    satellite_weights.max()
                ),

            "turnover":
                turnover_today,

            "transaction_cost_gbp":
                cost_today,

            "emergency_signal":
                emergency_signal_today,

            "emergency_execution":
                emergency_executed_today,
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
        base.START_NAV
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

        "emergency_signals":
            emergency_signals,

        "emergency_executions":
            emergency_executions,
    }


# ============================================================
# RUN V5-002
# ============================================================

def run_experiment_v12(
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

    control = (
        spec[
            "control"
        ]
    )

    candidate = (
        spec[
            "candidate"
        ]
    )

    rows = []
    metrics_by_key = {}

    for cost_bps in cost_scenarios:

        # ====================================================
        # CONTROL
        # ====================================================

        print(
            f"\nRunning CONTROL "
            f"at {cost_bps} bps..."
        )

        control_result = (
            base.run_model(
                signals=
                    signals,

                evaluation_start=
                    evaluation_start,

                rebalance_weeks=
                    int(
                        control[
                            "rebalance_weeks"
                        ]
                    ),

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        control_metrics = (
            base.calculate_metrics(
                control_result
            )
        )

        control_metrics[
            "emergency_signals"
        ] = 0

        control_metrics[
            "emergency_executions"
        ] = 0

        metrics_by_key[
            (
                "CONTROL",
                int(
                    cost_bps
                ),
            )
        ] = (
            control_metrics
        )

        rows.append({
            "role":
                "CONTROL",

            "model":
                control[
                    "name"
                ],

            "cost_bps":
                int(
                    cost_bps
                ),

            **control_metrics,
        })

        # ====================================================
        # CANDIDATE
        # ====================================================

        print(
            f"Running CANDIDATE "
            f"at {cost_bps} bps..."
        )

        candidate_result = (
            run_model_v12(
                signals=
                    signals,

                evaluation_start=
                    evaluation_start,

                rebalance_weeks=
                    int(
                        candidate[
                            "rebalance_weeks"
                        ]
                    ),

                one_way_cost_bps=
                    float(
                        cost_bps
                    ),

                emergency_risk_rebalance=
                    bool(
                        candidate.get(
                            "emergency_risk_rebalance",
                            False,
                        )
                    ),

                emergency_total_trigger=
                    float(
                        candidate.get(
                            "emergency_total_trigger",
                            0.265,
                        )
                    ),

                emergency_position_trigger=
                    float(
                        candidate.get(
                            "emergency_position_trigger",
                            0.14,
                        )
                    ),

                hard_total_limit=
                    float(
                        candidate.get(
                            "hard_total_limit",
                            0.275,
                        )
                    ),

                hard_position_limit=
                    float(
                        candidate.get(
                            "hard_position_limit",
                            0.15,
                        )
                    ),

                emergency_target_total=
                    float(
                        candidate.get(
                            "emergency_target_total",
                            0.25,
                        )
                    ),

                emergency_target_position=
                    float(
                        candidate.get(
                            "emergency_target_position",
                            0.125,
                        )
                    ),
            )
        )

        candidate_metrics = (
            base.calculate_metrics(
                candidate_result
            )
        )

        candidate_metrics[
            "emergency_signals"
        ] = int(
            candidate_result[
                "emergency_signals"
            ]
        )

        candidate_metrics[
            "emergency_executions"
        ] = int(
            candidate_result[
                "emergency_executions"
            ]
        )

        metrics_by_key[
            (
                "CANDIDATE",
                int(
                    cost_bps
                ),
            )
        ] = (
            candidate_metrics
        )

        rows.append({
            "role":
                "CANDIDATE",

            "model":
                candidate[
                    "name"
                ],

            "cost_bps":
                int(
                    cost_bps
                ),

            **candidate_metrics,
        })

    # ========================================================
    # ORIGINAL PRE-REGISTERED TESTS
    # ========================================================

    status, checks = (
        base.classify_experiment(
            spec=
                spec,

            metrics_by_key=
                metrics_by_key,
        )
    )

    # Candidate successfully completed, therefore hard risk
    # breaches were zero.
    checks[
        "zero_hard_risk_limit_breaches"
    ] = {
        "value":
            0,

        "required":
            0,

        "passed":
            True,
    }

    # Recalculate survivor decision including the extra
    # preregistered V5-002 risk criterion.
    all_pass = all(
        check[
            "passed"
        ]
        for check
        in checks.values()
    )

    candidate_15 = (
        metrics_by_key[
            (
                "CANDIDATE",
                15,
            )
        ]
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

    table = pd.DataFrame(
        rows
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
            control,

        "candidate":
            candidate,

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
                "Historical survivor status is not proof "
                "of alpha. Fund-100 has already examined "
                "this historical period."
            ),
    }

    return result


# ============================================================
# PRINT V1.2 RESULT
# ============================================================

def print_result_v12(
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
        "emergency_signals",
        "emergency_executions",
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
        "\nIMPORTANT:"
    )

    print(
        "No hard risk limit was loosened."
    )

    print(
        "A historical research survivor is "
        "not evidence of proven alpha."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 AUTONOMOUS RESEARCH LAB v1.2"
    )

    print(
        "============================================"
    )

    # ========================================================
    # PROTOCOL
    # ========================================================

    protocol = (
        base.load_protocol()
    )

    protocol_hash = (
        base.sha256_json(
            protocol
        )
    )

    print(
        f"\nProtocol version: "
        f"{protocol['protocol_version']}"
    )

    print(
        "Protocol SHA256:"
    )

    print(
        protocol_hash
    )

    print(
        f"\nHistorical cutoff: "
        f"{protocol['historical_cutoff']}"
    )

    # ========================================================
    # REGISTRY
    # ========================================================

    registry = (
        base.load_registry()
    )

    base.validate_registry(
        registry
    )

    specs = (
        base.load_specs()
    )

    base.validate_completed_specs(
        registry=
            registry,

        specs=
            specs,
    )

    completed_ids = set(
        registry[
            "experiment_id"
        ]
        .astype(
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
            "\n============================================"
        )

        print(
            "RESEARCH LAB v1.2 RUN COMPLETE"
        )

        print(
            "============================================"
        )

        return

    # ========================================================
    # FROZEN HISTORICAL DATA
    # ========================================================

    cfg, config_hash = (
        base.load_config()
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
        base.load_historical_data(
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
        base.ensure_data_manifest(
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
        base.build_signals(
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

    # ========================================================
    # ONE PRE-REGISTERED EXPERIMENT AT A TIME
    # ========================================================

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
            base.RESULTS_DIR
            / (
                experiment_id
                + ".json"
            )
        )

        if result_path.exists():

            raise RuntimeError(
                f"Result file already exists for "
                f"{experiment_id}, but the registry "
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
            f"Specification: "
            f"{spec_path}"
        )

        print(
            f"Specification SHA256: "
            f"{spec_hash}"
        )

        print(
            "\nThe experiment specification is "
            "frozen before examining the result."
        )

        try:

            if (
                experiment_id
                == "V5-002"
            ):

                result = (
                    run_experiment_v12(
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

            else:

                # Future ordinary experiments can still use
                # the v1.0 research machinery unless a later
                # Research Lab version defines new behaviour.
                result = (
                    base.run_experiment(
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

            risk_rejection = (
                False
            )

        except RuntimeError as exc:

            error_message = str(
                exc
            )

            if (
                error_message
                not in v11.RISK_FAILURE_MESSAGES
            ):

                raise

            risk_rejection = (
                True
            )

            result = (
                v11.build_risk_rejection_result(
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

                    error_message=
                        error_message,
                )
            )

        # ====================================================
        # SAVE RESULT
        # ====================================================

        with result_path.open(
            "w"
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
                default=float,
            )

        # ====================================================
        # APPEND IMMUTABLE REGISTRY
        # ====================================================

        if risk_rejection:

            registry = (
                v11.append_rejected_registry(
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

            v11.print_risk_rejection(
                result
            )

        else:

            registry = (
                base.append_registry(
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

            if (
                experiment_id
                == "V5-002"
            ):

                print_result_v12(
                    result
                )

            else:

                base.print_result(
                    result
                )

        base.validate_registry(
            registry
        )

        latest_result = (
            result
        )

        experiments_run += 1

    # ========================================================
    # LATEST REPORT
    # ========================================================

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

    with base.LATEST_REPORT_PATH.open(
        "w"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            default=float,
        )

    # ========================================================
    # STATUS
    # ========================================================

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
        base.REGISTRY_PATH
    )

    print(
        "\nResults directory:"
    )

    print(
        base.RESULTS_DIR
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
        "RESEARCH LAB v1.2 RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()

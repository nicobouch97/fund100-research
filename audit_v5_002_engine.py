from __future__ import annotations

import numpy as np

import fund100_experiment_runner as base
import fund100_experiment_runner_v1_2 as v12
import fund100_experiment_runner_v1_3 as v13


TOLERANCE = 1e-12

COMPARE_COLUMNS = [
    "nav",
    "daily_return",
    "benchmark_return",
    "active_return",
    "gross_overlay_return",
    "cost_drag_return",
    "satellite_weight",
    "turnover",
    "transaction_cost_gbp",
]


def assert_close(
    name: str,
    left,
    right,
    tolerance: float = TOLERANCE,
):

    difference = abs(
        float(left)
        - float(right)
    )

    print(
        f"{name}: diff={difference:.16g}"
    )

    if difference > tolerance:

        raise RuntimeError(
            f"PARITY FAILURE: {name} "
            f"difference {difference} "
            f"exceeds tolerance {tolerance}"
        )


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 V5-002 ENGINE PARITY AUDIT"
    )

    print(
        "============================================"
    )

    protocol = (
        base.load_protocol()
    )

    cfg, config_hash = (
        base.load_config()
    )

    print(
        "\nConfig SHA256:"
    )

    print(
        config_hash
    )

    prices, benchmark = (
        v13.load_frozen_history(
            cfg=
                cfg,
            protocol=
                protocol,
        )
    )

    data_hash = (
        v13.validate_frozen_history(
            prices=
                prices,
            benchmark=
                benchmark,
            protocol=
                protocol,
        )
    )

    print(
        "\nFrozen Research Dataset:"
    )

    print(
        data_hash
    )

    signals = (
        base.build_signals(
            prices=
                prices,
            benchmark=
                benchmark,
        )
    )

    evaluation_start = (
        protocol[
            "evaluation_start"
        ]
    )

    costs = (
        protocol[
            "cost_scenarios_bps"
        ]
    )

    for cost_bps in costs:

        print(
            "\n============================================"
        )

        print(
            f"PARITY TEST AT {cost_bps} BPS"
        )

        print(
            "============================================"
        )

        # ----------------------------------------------------
        # Original frozen RM25 engine
        # ----------------------------------------------------

        original = (
            base.run_model(
                signals=
                    signals,
                evaluation_start=
                    evaluation_start,
                rebalance_weeks=
                    4,
                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
            )
        )

        # ----------------------------------------------------
        # New v1.2 engine configured to behave exactly like
        # the original:
        #
        # - 4-week rebalance
        # - no emergency risk rebalance
        # - same frozen hard limits
        # ----------------------------------------------------

        new_engine = (
            v12.run_model_v12(
                signals=
                    signals,
                evaluation_start=
                    evaluation_start,
                rebalance_weeks=
                    4,
                one_way_cost_bps=
                    float(
                        cost_bps
                    ),
                emergency_risk_rebalance=
                    False,
                emergency_total_trigger=
                    0.265,
                emergency_position_trigger=
                    0.14,
                hard_total_limit=
                    base.MAX_TOTAL_DRIFT,
                hard_position_limit=
                    base.MAX_POSITION_DRIFT,
                emergency_target_total=
                    base.MAX_OVERLAY,
                emergency_target_position=
                    base.MAX_SATELLITE_POSITION,
            )
        )

        old_history = (
            original[
                "history"
            ]
        )

        new_history = (
            new_engine[
                "history"
            ]
        )

        if not old_history.index.equals(
            new_history.index
        ):

            raise RuntimeError(
                "PARITY FAILURE: "
                "history indexes differ."
            )

        print(
            f"\nRows compared: "
            f"{len(old_history)}"
        )

        for column in COMPARE_COLUMNS:

            left = (
                old_history[
                    column
                ]
                .to_numpy(
                    dtype=float
                )
            )

            right = (
                new_history[
                    column
                ]
                .to_numpy(
                    dtype=float
                )
            )

            max_difference = float(
                np.nanmax(
                    np.abs(
                        left
                        - right
                    )
                )
            )

            print(
                f"{column}: "
                f"max diff="
                f"{max_difference:.16g}"
            )

            if (
                max_difference
                > TOLERANCE
            ):

                raise RuntimeError(
                    "PARITY FAILURE: "
                    f"{column} differs by "
                    f"{max_difference}"
                )

        assert_close(
            "total_turnover",
            original[
                "total_turnover"
            ],
            new_engine[
                "total_turnover"
            ],
        )

        assert_close(
            "total_cost_gbp",
            original[
                "total_cost_gbp"
            ],
            new_engine[
                "total_cost_gbp"
            ],
        )

        if (
            new_engine[
                "emergency_signals"
            ]
            != 0
        ):

            raise RuntimeError(
                "PARITY FAILURE: emergency "
                "signals occurred while disabled."
            )

        if (
            new_engine[
                "emergency_executions"
            ]
            != 0
        ):

            raise RuntimeError(
                "PARITY FAILURE: emergency "
                "executions occurred while disabled."
            )

        print(
            f"\n{cost_bps} bps: PASS"
        )

    print(
        "\n============================================"
    )

    print(
        "ENGINE PARITY AUDIT PASSED"
    )

    print(
        "============================================"
    )

    print(
        "\nThe v1.2 engine reproduces the original "
        "RM25 engine when configured identically."
    )

    print(
        "Therefore V5-002's different historical "
        "result is caused by its strategy rules, "
        "not an unintended difference between "
        "backtest engines."
    )


if __name__ == "__main__":
    main()

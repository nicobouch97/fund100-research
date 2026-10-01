from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

import fund100_experiment_runner as base


# ============================================================
# FUND-100 AUTONOMOUS RESEARCH LAB v1.1
# ============================================================
#
# v1.0 treated a portfolio risk-limit breach as a program
# failure.
#
# v1.1 distinguishes:
#
#   SOFTWARE FAILURE
#       -> workflow fails
#
#   PRE-REGISTERED CANDIDATE VIOLATES FROZEN RISK LIMIT
#       -> experiment is permanently recorded as REJECTED
#
# The underlying strategy, risk limits, data and acceptance
# criteria are NOT changed.
# ============================================================


RISK_FAILURE_MESSAGES = (
    "Satellite sleeve drift limit breached.",
    "Satellite position drift limit breached.",
)


# ============================================================
# RISK-REJECTION RESULT
# ============================================================

def build_risk_rejection_result(
    spec: dict,
    spec_hash: str,
    protocol: dict,
    protocol_hash: str,
    data_hash: str,
    error_message: str,
) -> dict:

    return {
        "experiment_id":
            str(
                spec[
                    "experiment_id"
                ]
            ),

        "run_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            "REJECTED",

        "rejection_type":
            "FROZEN_RISK_LIMIT_BREACH",

        "rejection_reason":
            error_message,

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

        "cost_sensitivity":
            [],

        "criterion_results":
            {
                "frozen_risk_envelope":
                    {
                        "passed":
                            False,

                        "reason":
                            error_message,
                    }
            },

        "research_interpretation":
            (
                "The pre-registered challenger could not "
                "complete the historical experiment without "
                "breaching the frozen Fund-100 portfolio "
                "risk envelope. The risk limits were not "
                "changed after observing the result."
            ),

        "research_warning":
            (
                "Historical rejection or survivor status "
                "is research bookkeeping, not evidence of "
                "future investment performance."
            ),
    }


# ============================================================
# APPEND A RISK-REJECTED EXPERIMENT
# ============================================================

def append_rejected_registry(
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

        "rejection_type":
            result[
                "rejection_type"
            ],

        "rejection_reason":
            result[
                "rejection_reason"
            ],
    }

    payload_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=float,
    )

    chain_hash = (
        base.sha256_text(
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

    updated = updated[
        base.REGISTRY_COLUMNS
    ]

    updated.to_csv(
        base.REGISTRY_PATH,
        index=False,
    )

    return updated


# ============================================================
# PRINT RISK REJECTION
# ============================================================

def print_risk_rejection(
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

    print(
        "\nResearch classification:"
    )

    print(
        "REJECTED"
    )

    print(
        "\nReason:"
    )

    print(
        result[
            "rejection_reason"
        ]
    )

    print(
        "\nInterpretation:"
    )

    print(
        result[
            "research_interpretation"
        ]
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "The frozen risk limit was NOT loosened "
        "to rescue the challenger."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 AUTONOMOUS RESEARCH LAB v1.1"
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
    # PERMANENT REGISTRY
    # ========================================================

    registry = (
        base.load_registry()
    )

    base.validate_registry(
        registry
    )

    # ========================================================
    # PRE-REGISTERED SPECS
    # ========================================================

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
            "Research Lab made no changes."
        )

        print(
            "\n============================================"
        )

        print(
            "RESEARCH LAB v1.1 RUN COMPLETE"
        )

        print(
            "============================================"
        )

        return

    # ========================================================
    # FROZEN DATA
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

    # ========================================================
    # RUN AT MOST THE PRE-REGISTERED LIMIT
    # ========================================================

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

            rejection_from_risk = (
                False
            )

        except RuntimeError as exc:

            error_message = str(
                exc
            )

            if (
                error_message
                not in RISK_FAILURE_MESSAGES
            ):

                # Genuine software/data problems still fail
                # loudly rather than being misclassified as
                # investment research results.
                raise

            rejection_from_risk = (
                True
            )

            result = (
                build_risk_rejection_result(
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
        # SAVE PERMANENT RESULT
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
        # APPEND TO IMMUTABLE REGISTRY
        # ====================================================

        if rejection_from_risk:

            registry = (
                append_rejected_registry(
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

            print_risk_rejection(
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
    # LATEST RESEARCH REPORT
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
        "RESEARCH LAB v1.1 RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()

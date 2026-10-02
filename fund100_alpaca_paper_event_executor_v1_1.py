from __future__ import annotations

import sys

import pandas as pd

import fund100_experiment_runner as research_base
import fund100_alpaca_paper_event_executor as v10


# ============================================================
# FUND-100 V5-002 PAPER EVENT EXECUTOR v1.1
# ============================================================
#
# Adds a scheduled-trade decision-parity gate to v1.0.
#
# V5-002's frozen strategy applies its minimum-trade threshold
# to strategy weights after market drift.
#
# The broker implementation necessarily observes actual broker
# weights near the close.
#
# Therefore:
#
#   - calculate the scheduled BUY/SELL/HOLD decisions using
#     the shadow strategy reference weights
#
#   - calculate them again using actual broker weights
#
#   - if the decisions differ, FAIL CLOSED
#
# Emergency events are unaffected because they execute their
# emergency target directly without this trade threshold.
#
# PAPER ONLY.
# ============================================================


DECISION_EPSILON = 1e-10


ORIGINAL_BUILD_EXECUTED_TARGET = (
    v10.build_executed_target
)


def shadow_satellite_weights(
    state: dict,
) -> pd.Series:

    values = (
        pd.Series(
            state.get(
                "satellite_weights",
                {},
            ),
            dtype=float,
        )
        .reindex(
            research_base.EQUITY_UNIVERSE
        )
        .fillna(
            0.0
        )
    )

    if (
        values < -1e-12
    ).any():

        raise RuntimeError(
            "Negative V5-002 shadow weight detected."
        )

    return values


def decision_signature(
    current: pd.Series,
    executed: pd.Series,
) -> dict[str, str]:

    output = {}

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        old = float(
            current[
                symbol
            ]
        )

        new = float(
            executed[
                symbol
            ]
        )

        delta = (
            new
            - old
        )

        if abs(
            delta
        ) <= DECISION_EPSILON:

            decision = "HOLD"

        elif delta > 0:

            decision = "BUY"

        else:

            decision = "SELL"

        output[
            symbol
        ] = decision

    return output


def validate_scheduled_decision_parity(
    pending: pd.Series,
    positions: dict,
):

    state = (
        v10.load_state()
    )

    shadow_current = (
        shadow_satellite_weights(
            state
        )
    )

    broker_current = (
        v10.current_satellite_weights(
            positions
        )
    )

    shadow_executed = (
        research_base.apply_trade_threshold(
            current=
                shadow_current,

            desired=
                pending,
        )
    )

    broker_executed = (
        research_base.apply_trade_threshold(
            current=
                broker_current,

            desired=
                pending,
        )
    )

    shadow_decisions = (
        decision_signature(
            current=
                shadow_current,

            executed=
                shadow_executed,
        )
    )

    broker_decisions = (
        decision_signature(
            current=
                broker_current,

            executed=
                broker_executed,
        )
    )

    mismatches = []

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        shadow_decision = (
            shadow_decisions[
                symbol
            ]
        )

        broker_decision = (
            broker_decisions[
                symbol
            ]
        )

        if (
            shadow_decision
            != broker_decision
        ):

            mismatches.append(
                (
                    symbol,
                    shadow_decision,
                    broker_decision,
                )
            )

    if mismatches:

        details = "; ".join(
            (
                f"{symbol}: "
                f"shadow={shadow_decision}, "
                f"broker={broker_decision}"
            )
            for (
                symbol,
                shadow_decision,
                broker_decision,
            )
            in mismatches
        )

        raise RuntimeError(
            "SCHEDULED EXECUTION SAFETY STOP: "
            "shadow-reference and broker-current "
            "trade-threshold decisions disagree. "
            + details
        )

    print(
        "Scheduled trade-threshold "
        "decision parity: PASS"
    )


def guarded_build_executed_target(
    pending: pd.Series,
    source: str,
    positions: dict,
):

    if source == "SCHEDULED":

        validate_scheduled_decision_parity(
            pending=
                pending,

            positions=
                positions,
        )

    elif source == "EMERGENCY":

        print(
            "Emergency event: scheduled-threshold "
            "parity check not applicable."
        )

    else:

        raise RuntimeError(
            "Unexpected V5-002 event source."
        )

    return (
        ORIGINAL_BUILD_EXECUTED_TARGET(
            pending=
                pending,

            source=
                source,

            positions=
                positions,
        )
    )


def main():

    print(
        "Fund-100 paper executor safety layer: v1.1"
    )

    # Replace only the target-builder used by v1.0.
    # All existing endpoint, idempotency, fill and
    # reconciliation protections remain intact.

    v10.build_executed_target = (
        guarded_build_executed_target
    )

    v10.main()


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "V5-002 PAPER EXECUTOR v1.1: FAILED",
            file=sys.stderr,
        )

        print(
            "============================================",
            file=sys.stderr,
        )

        print(
            str(
                exc
            ),
            file=sys.stderr,
        )

        raise

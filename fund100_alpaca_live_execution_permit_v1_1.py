from __future__ import annotations

import sys

import fund100_alpaca_live_execution_permit as base


# ============================================================
# FUND-100 LIVE EXECUTION PERMIT GATE v1.1
# ============================================================
#
# DENY ONLY.
#
# v1.1 changes exactly one compatibility boundary:
#
#   accepted scheduled compiler schema:
#
#     V1  ->  V1_1
#
# It does NOT add any authorization path.
#
# The underlying permit remains:
#
#   FUND100_LIVE_EXECUTION_PERMIT_V1
#
# with:
#
#   permit_issued = FALSE
#   live_execution_authorized = FALSE
#   max_live_execution_notional_usd = 0.0
#   network_write_capability = FALSE
#   broker_write_mode = DISABLED
#
# No broker credentials.
# No broker network access.
# No order submission.
# ============================================================


EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)


# ============================================================
# PATCH ONLY THE EXPECTED COMPILER SCHEMA
# ============================================================

base.EXPECTED_SCHEMA = (
    EXPECTED_COMPILER_SCHEMA
)


def verify_safety_contract():

    if (
        base.EXPECTED_SCHEMA
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "V1.1 PERMIT STOP: "
            "compiler schema compatibility patch failed."
        )

    # --------------------------------------------------------
    # The original implementation must remain deny-only.
    # --------------------------------------------------------

    synthetic = {
        "compiler_mode":
            "synthetic",

        "status":
            "SYNTHETIC_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }

    if (
        base.determine_denial_reason(
            synthetic
        )
        != "SYNTHETIC_ARTIFACT_NEVER_EXECUTABLE"
    ):

        raise RuntimeError(
            "V1.1 PERMIT STOP: "
            "synthetic artifact denial changed."
        )

    no_event = {
        "compiler_mode":
            "current",

        "status":
            "NO_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }

    if (
        base.determine_denial_reason(
            no_event
        )
        != "NO_GENUINE_STRATEGY_EVENT"
    ):

        raise RuntimeError(
            "V1.1 PERMIT STOP: "
            "no-event denial changed."
        )

    genuine = {
        "compiler_mode":
            "current",

        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            True,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }

    if (
        base.determine_denial_reason(
            genuine
        )
        != "LIVE_AUTHORIZATION_NOT_IMPLEMENTED"
    ):

        raise RuntimeError(
            "V1.1 PERMIT STOP: "
            "genuine-event deny-only boundary changed."
        )


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE EXECUTION PERMIT GATE v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nCompatibility target: "
        + EXPECTED_COMPILER_SCHEMA
    )

    print(
        "Permit implementation: DENY ONLY"
    )

    print(
        "Broker credentials required: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Live order submission: IMPOSSIBLE"
    )

    verify_safety_contract()

    print(
        "Deny-only regression contract: PASS"
    )

    # --------------------------------------------------------
    # Delegate to the already-audited V1 implementation.
    #
    # Only base.EXPECTED_SCHEMA has changed.
    # --------------------------------------------------------

    base.main()


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "LIVE PERMIT v1.1 GATE: FAILED",
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

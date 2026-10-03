from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import fund100_alpaca_live_permit_v2_simulator as v2
import fund100_alpaca_live_writer_disconnected as writer


# ============================================================
# FUND-100 LIVE ACTIVATION POSITIVE-PATH REHEARSAL v1.0
# ============================================================
#
# COMPLETELY OFFLINE.
#
# NO Alpaca credentials.
# NO broker API.
# NO HTTP.
# NO live account access.
# NO order submission.
#
# PURPOSE
# =======
#
# Prove that the proposed future authorization contract can
# logically satisfy every positive condition while STILL
# remaining structurally incapable of live execution.
#
# The output schema is deliberately:
#
#   FUND100_LIVE_EXECUTION_PERMIT_V2_REHEARSAL
#
# The disconnected writer requires:
#
#   FUND100_LIVE_EXECUTION_PERMIT_V2
#
# Therefore this artifact can never authorize the writer.
# ============================================================


OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_activation_rehearsal.json"
)

REHEARSAL_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2_REHEARSAL"
)

WRITER_REQUIRED_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)

EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1"
)

# ------------------------------------------------------------
# PURELY SYNTHETIC SENTINEL.
#
# This is not a live capital decision.
# It exists only to prove that:
#
#     execution_ceiling > 0
#
# can become TRUE in the contract.
# ------------------------------------------------------------

SYNTHETIC_CAP_SENTINEL_USD = 123.45

FAKE_ACCOUNT_ID = (
    "fund100-offline-rehearsal-account"
)

FAKE_SIGNAL_DATE = (
    "2099-01-05"
)

FAKE_CLOCK_TIMESTAMP = (
    "2099-01-06T15:30:00-05:00"
)

FAKE_SESSION_EXPIRY = (
    "2099-01-06T16:00:00-05:00"
)


# ============================================================
# HASHING
# ============================================================


def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# FAKE GENUINE COMPILER ARTIFACT
# ============================================================


def build_fake_compiler_package():

    compiler = {
        "schema":
            EXPECTED_COMPILER_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            FAKE_SIGNAL_DATE,

        "compiler_mode":
            "current",

        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            True,

        "market_snapshot_sha256":
            sha256_text(
                "offline-market-snapshot"
            ),

        "candidate_intents": [
            {
                "symbol":
                    "EEM",

                "side":
                    "sell",

                "current_weight":
                    0.0835,

                "target_weight":
                    0.0000,

                "delta_weight":
                    -0.0835,

                "client_order_id":
                    "f100live-offline-s-eem",

                "notional_usd":
                    None,

                "executable":
                    False,
            },
            {
                "symbol":
                    "XLK",

                "side":
                    "buy",

                "current_weight":
                    0.0000,

                "target_weight":
                    0.0835,

                "delta_weight":
                    0.0835,

                "client_order_id":
                    "f100live-offline-b-xlk",

                "notional_usd":
                    None,

                "executable":
                    False,
            },
        ],

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }

    return {
        "compiler_sha256":
            sha256_json(
                compiler
            ),

        "compiler":
            compiler,
    }


# ============================================================
# FAKE ACCOUNT
# ============================================================


def build_fake_account():

    return {
        "id":
            FAKE_ACCOUNT_ID,

        "status":
            "ACTIVE",

        "account_blocked":
            False,

        "trading_blocked":
            False,

        "transfers_blocked":
            False,
    }


def build_fake_account_binding():

    material = (
        "FUND100_ALPACA_LIVE_ACCOUNT_V1:"
        + FAKE_ACCOUNT_ID
    )

    return sha256_text(
        material
    )


# ============================================================
# FAKE SESSION
# ============================================================


def build_fake_session():

    now = datetime.fromisoformat(
        FAKE_CLOCK_TIMESTAMP
    )

    expiry = datetime.fromisoformat(
        FAKE_SESSION_EXPIRY
    )

    session_body = {
        "market_is_open":
            True,

        "clock_timestamp":
            FAKE_CLOCK_TIMESTAMP,

        "candidate_expiry":
            FAKE_SESSION_EXPIRY,
    }

    return {
        "market_is_open":
            True,

        "clock_timestamp":
            FAKE_CLOCK_TIMESTAMP,

        "candidate_expiry":
            FAKE_SESSION_EXPIRY,

        "expiry_is_future":
            (
                expiry > now
            ),

        "session_binding_sha256":
            sha256_json(
                session_body
            ),
    }


# ============================================================
# EVENT BINDING
# ============================================================


def build_event_binding(
    compiler_package: dict,
):

    compiler = (
        compiler_package[
            "compiler"
        ]
    )

    event_body = {
        "source_compiler_sha256":
            compiler_package[
                "compiler_sha256"
            ],

        "strategy":
            compiler[
                "strategy"
            ],

        "strategy_state_date":
            compiler[
                "strategy_state_date"
            ],

        "compiler_mode":
            compiler[
                "compiler_mode"
            ],

        "status":
            compiler[
                "status"
            ],

        "market_snapshot_sha256":
            compiler[
                "market_snapshot_sha256"
            ],

        "candidate_intents":
            compiler[
                "candidate_intents"
            ],
    }

    event_hash = (
        sha256_json(
            event_body
        )
    )

    event_id = (
        "f100-live-event-"
        + event_hash[
            :20
        ]
    )

    return (
        event_id,
        event_hash,
    )


# ============================================================
# POSITIVE CONTRACT CONDITIONS
# ============================================================


def evaluate_positive_path(
    compiler_package: dict,
    account: dict,
    session: dict,
    event_id: str,
    consumed_event_ids: set[str],
):

    compiler = (
        compiler_package[
            "compiler"
        ]
    )

    conditions = {
        "compiler_sha256_verified":
            (
                compiler_package[
                    "compiler_sha256"
                ]
                == sha256_json(
                    compiler
                )
            ),

        "source_mode_is_current":
            (
                compiler[
                    "compiler_mode"
                ]
                == "current"
            ),

        "source_status_is_genuine_event":
            (
                compiler[
                    "status"
                ]
                == "GENUINE_SCHEDULED_EVENT"
            ),

        "source_genuine_event_flag":
            (
                compiler[
                    "genuine_scheduled_event"
                ]
                is True
            ),

        "manual_approval_present":
            True,

        "permit_built_while_kill_switch_engaged":
            True,

        "account_status_active":
            (
                account[
                    "status"
                ]
                == "ACTIVE"
            ),

        "account_not_blocked":
            (
                account[
                    "account_blocked"
                ]
                is False
            ),

        "trading_not_blocked":
            (
                account[
                    "trading_blocked"
                ]
                is False
            ),

        "no_open_orders":
            True,

        "market_session_open":
            (
                session[
                    "market_is_open"
                ]
                is True
            ),

        "permit_expiry_is_future":
            (
                session[
                    "expiry_is_future"
                ]
                is True
            ),

        "event_not_previously_consumed":
            (
                event_id
                not in
                consumed_event_ids
            ),

        "positive_execution_ceiling_configured":
            (
                SYNTHETIC_CAP_SENTINEL_USD
                > 0.0
            ),
    }

    return conditions


def failed_conditions(
    conditions: dict,
):

    return [
        name
        for name, passed
        in conditions.items()
        if not bool(
            passed
        )
    ]


# ============================================================
# BUILD REHEARSAL PERMIT
# ============================================================


def build_rehearsal_permit(
    compiler_package: dict,
    account_binding_sha256: str,
    event_id: str,
    event_binding_sha256: str,
    session: dict,
    conditions: dict,
):

    failures = (
        failed_conditions(
            conditions
        )
    )

    all_conditions_pass = (
        len(
            failures
        )
        == 0
    )

    permit = {
        "schema":
            REHEARSAL_SCHEMA,

        "future_writer_required_schema":
            WRITER_REQUIRED_SCHEMA,

        "offline_rehearsal":
            True,

        "simulation_only":
            True,

        "strategy":
            compiler_package[
                "compiler"
            ][
                "strategy"
            ],

        "strategy_state_date":
            compiler_package[
                "compiler"
            ][
                "strategy_state_date"
            ],

        "source_compiler_sha256":
            compiler_package[
                "compiler_sha256"
            ],

        "event_id":
            event_id,

        "event_binding_sha256":
            event_binding_sha256,

        "account_binding_sha256":
            account_binding_sha256,

        "session_binding_sha256":
            session[
                "session_binding_sha256"
            ],

        "candidate_expiry":
            session[
                "candidate_expiry"
            ],

        "conditions":
            conditions,

        "failed_conditions":
            failures,

        "all_contract_conditions_satisfied":
            all_conditions_pass,

        # ----------------------------------------------------
        # POSITIVE-CAP TEST VALUE
        #
        # This is simulation metadata only.
        # It is NOT executable.
        # ----------------------------------------------------

        "synthetic_execution_ceiling_usd":
            SYNTHETIC_CAP_SENTINEL_USD,

        # ----------------------------------------------------
        # HARD DENY STATE
        # ----------------------------------------------------

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "writer_connected":
            False,

        "denial_reason":
            "OFFLINE_POSITIVE_PATH_REHEARSAL_ONLY",
    }

    return {
        "rehearsal_sha256":
            sha256_json(
                permit
            ),

        "rehearsal":
            permit,
    }


# ============================================================
# REPLAY REHEARSAL
# ============================================================


def rehearse_replay_protection(
    compiler_package: dict,
    account: dict,
    session: dict,
    event_id: str,
):

    consumed = set()

    first_conditions = (
        evaluate_positive_path(
            compiler_package=
                compiler_package,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                consumed,
        )
    )

    first_allowed_by_contract = (
        len(
            failed_conditions(
                first_conditions
            )
        )
        == 0
    )

    if not first_allowed_by_contract:

        raise RuntimeError(
            "Positive-path rehearsal could not "
            "satisfy all contract conditions."
        )

    # --------------------------------------------------------
    # Simulate atomic consumption of the event.
    # --------------------------------------------------------

    consumed.add(
        event_id
    )

    second_conditions = (
        evaluate_positive_path(
            compiler_package=
                compiler_package,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                consumed,
        )
    )

    second_allowed_by_contract = (
        len(
            failed_conditions(
                second_conditions
            )
        )
        == 0
    )

    if second_allowed_by_contract:

        raise RuntimeError(
            "REPLAY SAFETY FAILURE: "
            "consumed event passed twice."
        )

    if (
        second_conditions[
            "event_not_previously_consumed"
        ]
        is not False
    ):

        raise RuntimeError(
            "Replay condition did not fail."
        )

    return {
        "first_attempt_all_conditions_pass":
            first_allowed_by_contract,

        "event_marked_consumed":
            True,

        "second_attempt_all_conditions_pass":
            second_allowed_by_contract,

        "second_attempt_replay_condition":
            second_conditions[
                "event_not_previously_consumed"
            ],

        "second_attempt_failed_conditions":
            failed_conditions(
                second_conditions
            ),
    }


# ============================================================
# WRITER INCOMPATIBILITY
# ============================================================


def prove_writer_rejects_rehearsal(
    package: dict,
):

    # --------------------------------------------------------
    # Feed the rehearsal artifact into the writer's permit
    # validator.
    #
    # It MUST reject it because the schema is deliberately
    # incompatible.
    #
    # No network code is called here.
    # --------------------------------------------------------

    writer_shaped_package = {
        "permit_sha256":
            package[
                "rehearsal_sha256"
            ],

        "permit":
            package[
                "rehearsal"
            ],
    }

    try:

        writer.validate_permit_package(
            writer_shaped_package
        )

    except writer.LivePermitRejected as exc:

        return {
            "writer_rejected":
                True,

            "reason":
                str(
                    exc
                ),
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "disconnected writer accepted the "
        "offline rehearsal permit."
    )


def prove_writer_remains_disconnected():

    try:

        writer.require_adapter_connected()

    except writer.LiveWriterDisconnected as exc:

        return {
            "writer_disconnected":
                True,

            "reason":
                str(
                    exc
                ),
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "live writer connection guard passed."
    )


# ============================================================
# HARD ASSERTIONS
# ============================================================


def assert_rehearsal_safety(
    body: dict,
):

    if (
        body[
            "schema"
        ]
        == WRITER_REQUIRED_SCHEMA
    ):

        raise RuntimeError(
            "Rehearsal accidentally emitted "
            "writer-compatible schema."
        )

    if (
        body[
            "all_contract_conditions_satisfied"
        ]
        is not True
    ):

        raise RuntimeError(
            "Positive-path contract did not pass."
        )

    if (
        body[
            "permit_issued"
        ]
        is not False
    ):

        raise RuntimeError(
            "Rehearsal issued a permit."
        )

    if (
        body[
            "live_execution_authorized"
        ]
        is not False
    ):

        raise RuntimeError(
            "Rehearsal authorized execution."
        )

    if (
        body[
            "network_write_capability"
        ]
        is not False
    ):

        raise RuntimeError(
            "Rehearsal gained network-write capability."
        )

    if (
        body[
            "writer_connected"
        ]
        is not False
    ):

        raise RuntimeError(
            "Rehearsal connected the live writer."
        )

    if (
        body[
            "broker_write_mode"
        ]
        != "DISABLED"
    ):

        raise RuntimeError(
            "Rehearsal enabled broker writes."
        )

    if abs(
        float(
            body[
                "max_live_execution_notional_usd"
            ]
        )
    ) > 1e-12:

        raise RuntimeError(
            "Rehearsal produced executable "
            "live monetary ceiling."
        )


# ============================================================
# OUTPUT
# ============================================================


def write_output(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w"
    ) as f:

        json.dump(
            package,
            f,
            indent=2,
            sort_keys=True,
        )

        f.write(
            "\n"
        )

    with OUTPUT_PATH.open(
        "r"
    ) as f:

        stored = json.load(
            f
        )

    recorded = (
        stored[
            "rehearsal_sha256"
        ]
    )

    calculated = (
        sha256_json(
            stored[
                "rehearsal"
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "Stored rehearsal hash "
            "verification failed."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE ACTIVATION POSITIVE REHEARSAL"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: COMPLETELY OFFLINE"
    )

    print(
        "Live credentials required: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Real account access: NONE"
    )

    print(
        "Live writer connection: FALSE"
    )

    # ========================================================
    # FAKE INPUTS
    # ========================================================

    compiler_package = (
        build_fake_compiler_package()
    )

    account = (
        build_fake_account()
    )

    account_binding = (
        build_fake_account_binding()
    )

    session = (
        build_fake_session()
    )

    (
        event_id,
        event_binding,
    ) = (
        build_event_binding(
            compiler_package
        )
    )

    print(
        "\nFake genuine compiler artifact: PASS"
    )

    print(
        "Fake active account state: PASS"
    )

    print(
        "Fake account binding: PASS"
    )

    print(
        "Fake market session: OPEN"
    )

    print(
        "Fake permit expiry: FUTURE"
    )

    print(
        "Fake manual approval: PRESENT"
    )

    print(
        "Fake kill-switch construction state: ENGAGED"
    )

    print(
        f"Synthetic positive-cap sentinel: "
        f"${SYNTHETIC_CAP_SENTINEL_USD:.2f}"
    )

    print(
        "Live executable cap: $0.00"
    )

    # ========================================================
    # CONTRACT
    # ========================================================

    conditions = (
        evaluate_positive_path(
            compiler_package=
                compiler_package,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                set(),
        )
    )

    print(
        "\n============================================"
    )

    print(
        "POSITIVE-PATH V2 CONDITIONS"
    )

    print(
        "============================================"
    )

    for name, result in (
        conditions.items()
    ):

        status = (
            "PASS"
            if result
            else "FAIL"
        )

        print(
            f"{status}: {name}"
        )

    failures = (
        failed_conditions(
            conditions
        )
    )

    if failures:

        raise RuntimeError(
            "Positive-path rehearsal condition "
            "failure: "
            + ", ".join(
                failures
            )
        )

    print(
        "\nAll future authorization "
        "conditions satisfied: TRUE"
    )

    # ========================================================
    # BUILD DENIED REHEARSAL ARTIFACT
    # ========================================================

    package = (
        build_rehearsal_permit(
            compiler_package=
                compiler_package,

            account_binding_sha256=
                account_binding,

            event_id=
                event_id,

            event_binding_sha256=
                event_binding,

            session=
                session,

            conditions=
                conditions,
        )
    )

    body = (
        package[
            "rehearsal"
        ]
    )

    assert_rehearsal_safety(
        body
    )

    # ========================================================
    # WRITER REJECTION
    # ========================================================

    rejection = (
        prove_writer_rejects_rehearsal(
            package
        )
    )

    disconnect = (
        prove_writer_remains_disconnected()
    )

    print(
        "\nWriter schema rejection: PASS"
    )

    print(
        "Writer hard-disconnect guard: PASS"
    )

    # ========================================================
    # REPLAY
    # ========================================================

    replay = (
        rehearse_replay_protection(
            compiler_package=
                compiler_package,

            account=
                account,

            session=
                session,

            event_id=
                event_id,
        )
    )

    print(
        "First-use contract evaluation: PASS"
    )

    print(
        "Synthetic event consumption: PASS"
    )

    print(
        "Second-use replay rejection: PASS"
    )

    # ========================================================
    # ADD PROOFS TO OUTPUT
    # ========================================================

    body[
        "writer_rejection_proof"
    ] = rejection

    body[
        "writer_disconnect_proof"
    ] = disconnect

    body[
        "replay_rehearsal"
    ] = replay

    # Hash changed after adding proof records.
    package[
        "rehearsal_sha256"
    ] = sha256_json(
        body
    )

    assert_rehearsal_safety(
        body
    )

    write_output(
        package
    )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "POSITIVE-PATH REHEARSAL RESULT"
    )

    print(
        "============================================"
    )

    print(
        f"\nEvent ID: "
        f"{event_id}"
    )

    print(
        f"Account binding SHA256: "
        f"{account_binding}"
    )

    print(
        f"Event binding SHA256: "
        f"{event_binding}"
    )

    print(
        f"Session binding SHA256: "
        f"{session['session_binding_sha256']}"
    )

    print(
        "\nAll contract conditions satisfied: TRUE"
    )

    print(
        f"Rehearsal schema: "
        f"{REHEARSAL_SCHEMA}"
    )

    print(
        f"Writer-required schema: "
        f"{WRITER_REQUIRED_SCHEMA}"
    )

    print(
        "Schemas compatible: FALSE"
    )

    print(
        "\nPermit issued: FALSE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Live executable monetary ceiling: $0.00"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Broker write mode: DISABLED"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Replay protection: PASS"
    )

    print(
        f"\nRehearsal SHA256: "
        f"{package['rehearsal_sha256']}"
    )

    print(
        "Rehearsal hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE ACTIVATION POSITIVE REHEARSAL: PASS"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "LIVE ACTIVATION POSITIVE REHEARSAL: FAILED",
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

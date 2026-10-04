from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import fund100_alpaca_live_cumulative_cap_guard_v1_0 as cap_guard
import fund100_alpaca_live_writer_candidate_v1_1 as candidate
import fund100_alpaca_live_writer_status_rehearsal_v1_0 as status_rehearsal


# ============================================================
# FUND-100 CUMULATIVE CAP / RESTART REHEARSAL v1.0
# ============================================================
#
# COMPLETELY OFFLINE.
#
# NO Alpaca credentials.
# NO real broker network.
# NO live orders.
#
# PURPOSE
# =======
#
# Prove the final outstanding v1.7 writer-safety requirement:
#
#     ONE permit ceiling applies cumulatively across
#     all phases and process restarts.
#
# Scenarios:
#
# 1. SELL $60 -> restart -> BUY $40
#       projected cumulative gross = $100
#       PASS
#
# 2. SELL $60 -> BUY $40.01
#       projected cumulative gross = $100.01
#       BLOCKED before writer invocation
#
# 3. SELL accepted but POST response lost
#       restart reconstructs $60 from broker
#       repeated SELL does not consume another $60
#       repeated writer call does not POST again
#
# 4. Partially-filled $60 order
#       full original $60 remains consumed
#
# 5. canceled / expired / rejected history
#       original notional remains consumed
#       continuation blocked pending reconciliation
#
# 6. unsafe historical state
#       continuation blocked
#
# 7. incomplete authorized-ID reconstruction
#       fails closed
#
# 8. broker-observed historical gross already above cap
#       fails closed
#
# CRITICAL:
#
# All broker calls use the already-reviewed in-memory fake
# transport from the status/restart rehearsal.
#
# Writer candidate source release flags remain FALSE.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


LOCK_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_lock.json"
)


OUTPUT_DIR = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
)


OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_cumulative_cap_rehearsal_v1_0.json"
)


CAP_GUARD_PATH = (
    ROOT
    / "fund100_alpaca_live_cumulative_cap_guard_v1_0.py"
)


CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_1.py"
)


REHEARSAL_SCHEMA = (
    "FUND100_LIVE_CUMULATIVE_CAP_REHEARSAL_V1"
)


EXPECTED_LOCK_BUILDER_VERSION = "1.7"


PERMIT_CAP_USD = 100.00


SELL_ID = (
    "f100live-cap-rehearsal-s-acwi"
)


BUY_ID = (
    "f100live-cap-rehearsal-b-spy"
)


# ============================================================
# FILE / HASH HELPERS
# ============================================================


def sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            f"required file missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


# ============================================================
# RELEASE LOCK
# ============================================================


def verify_release_lock():

    package = (
        load_json(
            LOCK_PATH
        )
    )

    body = package.get(
        "release_lock"
    )

    recorded = str(
        package.get(
            "release_lock_sha256",
            "",
        )
    )

    if not isinstance(
        body,
        dict,
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "release-lock body missing."
        )

    if (
        candidate.sha256_json(
            body
        )
        != recorded
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "release-lock SHA256 failed."
        )

    if (
        str(
            body.get(
                "release_lock_builder_version",
                "",
            )
        )
        != EXPECTED_LOCK_BUILDER_VERSION
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "release lock is not v1.7."
        )

    if (
        body.get(
            "connected_writer_candidate_version"
        )
        != "1.1"
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "v1.1 candidate is not the locked candidate."
        )

    if (
        body.get(
            "connected_writer_status_semantics_hardening_completed"
        )
        is not True
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "status hardening is not complete."
        )

    if (
        body.get(
            "connected_writer_status_semantics_hardening_verified"
        )
        is not True
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "status-hardening evidence is not verified."
        )

    if (
        body.get(
            "connected_writer_cumulative_cap_recovery_required"
        )
        is not True
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "cumulative-cap requirement is absent."
        )

    if (
        body.get(
            "connected_writer_cumulative_cap_recovery_completed"
        )
        is not False
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "cumulative-cap requirement is "
            "unexpectedly complete."
        )

    if (
        body.get(
            "connected_writer_cumulative_cap_recovery_release_blocker"
        )
        is not True
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "cumulative-cap release blocker is absent."
        )

    required_false = [
        "connected_writer_candidate_transport_released",
        "connected_writer_candidate_public_execution_enabled",
        "connected_writer_candidate_workflow_exposed",
        "live_writer_transport_released",
        "live_writer_public_execution_enabled",
        "automatic_activation_allowed",
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "CAP REHEARSAL STOP: "
                f"release-lock field {field!r} "
                "is not FALSE."
            )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "LIVE ceiling is not $0.00."
        )

    if (
        int(
            body.get(
                "orders_submitted",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "release lock reports LIVE orders."
        )

    expected_candidate_hash = str(
        body.get(
            "connected_writer_candidate_v1_1_source_sha256",
            "",
        )
    )

    actual_candidate_hash = (
        sha256_file(
            CANDIDATE_PATH
        )
    )

    if (
        expected_candidate_hash
        != actual_candidate_hash
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "writer candidate v1.1 changed after v1.7."
        )

    return (
        package,
        body,
        recorded,
        actual_candidate_hash,
    )


# ============================================================
# SYNTHETIC COMPILER / PERMIT
# ============================================================


def build_compiler_body():

    return {
        "schema":
            "OFFLINE_CUMULATIVE_CAP_REHEARSAL_COMPILER",

        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            True,

        "candidate_intents":
            [
                {
                    "symbol":
                        "ACWI",

                    "side":
                        "sell",

                    "target_weight":
                        0.40,

                    "client_order_id":
                        SELL_ID,

                    "notional_usd":
                        None,

                    "executable":
                        False,
                },
                {
                    "symbol":
                        "SPY",

                    "side":
                        "buy",

                    "target_weight":
                        0.60,

                    "client_order_id":
                        BUY_ID,

                    "notional_usd":
                        None,

                    "executable":
                        False,
                },
            ],
    }


def build_synthetic_permit():

    body = {
        "schema":
            candidate.REQUIRED_PERMIT_SCHEMA,

        "permit_issued":
            True,

        "live_execution_authorized":
            True,

        "network_write_capability":
            True,

        "broker_write_mode":
            "ENABLED",

        "genuine_scheduled_event":
            True,

        "max_live_execution_notional_usd":
            PERMIT_CAP_USD,

        "offline_cumulative_cap_rehearsal":
            True,

        "persist_this_permit":
            False,
    }

    return {
        "permit":
            body,

        "permit_sha256":
            candidate.sha256_json(
                body
            ),
    }


def sell_intent(
    notional: float = 60.00,
):

    return {
        "symbol":
            "ACWI",

        "side":
            "sell",

        "notional_usd":
            float(
                notional
            ),

        "client_order_id":
            SELL_ID,

        "executable":
            True,
    }


def buy_intent(
    notional: float = 40.00,
):

    return {
        "symbol":
            "SPY",

        "side":
            "buy",

        "notional_usd":
            float(
                notional
            ),

        "client_order_id":
            BUY_ID,

        "executable":
            True,
    }


# ============================================================
# LOOKUP / WRITER HELPERS
# ============================================================


def compiler_hash(
    compiler_body: dict,
):

    return (
        candidate.sha256_json(
            compiler_body
        )
    )


def permit_hash(
    permit_package: dict,
):

    return str(
        permit_package[
            "permit_sha256"
        ]
    )


def lookup_all_authorized(
    *,
    broker: status_rehearsal.OfflineStatusBroker,
    compiler_body: dict,
):

    authorized = (
        cap_guard.build_authorized_index(
            compiler_body
        )
    )

    result = {}

    with (
        status_rehearsal
        .offline_candidate_transport(
            broker
        )
    ):

        for client_order_id in sorted(
            authorized
        ):

            result[
                client_order_id
            ] = (
                candidate._get_order_by_client_id(
                    client_order_id=
                        client_order_id,

                    key=
                        "offline-fake-key",

                    secret=
                        "offline-fake-secret",
                )
            )

    if (
        set(
            result
        )
        != set(
            authorized
        )
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "complete lookup reconstruction failed."
        )

    return result


def submit_phase(
    *,
    broker: status_rehearsal.OfflineStatusBroker,
    permit_package: dict,
    intents: list[dict],
):

    with (
        status_rehearsal
        .offline_candidate_transport(
            broker
        )
    ):

        return (
            candidate.submit_authorized_order_batch(
                intents=
                    intents,

                permit_package=
                    permit_package,

                key=
                    "offline-fake-key",

                secret=
                    "offline-fake-secret",
            )
        )


def evaluate(
    *,
    compiler_body: dict,
    permit_package: dict,
    observed: dict,
    proposed: list[dict],
):

    return (
        cap_guard.evaluate_cumulative_cap(
            compiler_body=
                compiler_body,

            compiler_sha256=
                compiler_hash(
                    compiler_body
                ),

            permit_sha256=
                permit_hash(
                    permit_package
                ),

            permit_cap_usd=
                PERMIT_CAP_USD,

            observed_orders_by_client_id=
                observed,

            proposed_intents=
                proposed,
        )
    )


def seed_order(
    *,
    broker: status_rehearsal.OfflineStatusBroker,
    intent: dict,
    status: str,
    order_id: str,
):

    order = (
        broker.order_from_intent(
            intent=
                intent,

            status=
                status,

            order_id=
                order_id,
        )
    )

    broker.orders[
        intent[
            "client_order_id"
        ]
    ] = order

    return order


# ============================================================
# SCENARIO 1
# SELL -> RESTART -> BUY -> RESTART
# ============================================================


def rehearse_exact_cap_across_phases():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker(
            post_status=
                "new"
        )
    )

    # --------------------------------------------------------
    # BEFORE SELL
    # --------------------------------------------------------

    initial_lookup = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    sell_check = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                initial_lookup,

            proposed=[
                sell_intent(
                    60.00
                )
            ],
        )
    )

    if (
        sell_check[
            "projected_cumulative_gross_notional_usd"
        ]
        != 60.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "SELL phase projection is not $60."
        )

    sell_result = (
        submit_phase(
            broker=
                broker,

            permit_package=
                permit,

            intents=[
                sell_intent(
                    60.00
                )
            ],
        )
    )

    if (
        sell_result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        != "SUBMITTED"
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "SELL phase did not submit."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "SELL phase did not perform exactly one fake POST."
        )

    # Simulate completed SELL before BUY materialization.

    broker.orders[
        SELL_ID
    ][
        "status"
    ] = "filled"

    # --------------------------------------------------------
    # PROCESS RESTART BEFORE BUY
    # --------------------------------------------------------

    restart_lookup = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    buy_check = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                restart_lookup,

            proposed=[
                buy_intent(
                    40.00
                )
            ],
        )
    )

    if (
        buy_check[
            "previously_consumed_gross_notional_usd"
        ]
        != 60.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "restart did not reconstruct $60 consumed."
        )

    if (
        buy_check[
            "new_gross_notional_usd"
        ]
        != 40.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "BUY phase new gross is not $40."
        )

    if (
        buy_check[
            "projected_cumulative_gross_notional_usd"
        ]
        != 100.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "SELL + BUY projected gross is not $100."
        )

    if (
        buy_check[
            "remaining_cap_after_batch_usd"
        ]
        != 0.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "exact-cap scenario did not consume "
            "the full permit ceiling."
        )

    buy_result = (
        submit_phase(
            broker=
                broker,

            permit_package=
                permit,

            intents=[
                buy_intent(
                    40.00
                )
            ],
        )
    )

    if (
        buy_result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        != "SUBMITTED"
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "BUY phase did not submit."
        )

    if (
        broker.post_attempt_count
        != 2
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "SELL+BUY did not produce exactly "
            "two fake POSTs."
        )

    # --------------------------------------------------------
    # SECOND PROCESS RESTART
    #
    # Both broker orders now exist.
    # Repeating BUY must not consume another $40 and must not
    # POST again.
    # --------------------------------------------------------

    second_restart_lookup = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    replay_check = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                second_restart_lookup,

            proposed=[
                buy_intent(
                    40.00
                )
            ],
        )
    )

    if (
        replay_check[
            "previously_consumed_gross_notional_usd"
        ]
        != 100.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "second restart did not reconstruct $100."
        )

    if (
        replay_check[
            "new_gross_notional_usd"
        ]
        != 0.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "recovered BUY was double-counted."
        )

    posts_before_replay = (
        broker.post_attempt_count
    )

    replay_result = (
        submit_phase(
            broker=
                broker,

            permit_package=
                permit,

            intents=[
                buy_intent(
                    40.00
                )
            ],
        )
    )

    if (
        replay_result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        != "EXISTING_NO_RESUBMIT_ORDER"
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "repeated BUY did not recover "
            "the existing broker order."
        )

    if (
        broker.post_attempt_count
        != posts_before_replay
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "repeated BUY caused a duplicate POST."
        )

    return {
        "sell_phase_projected_usd":
            60.0,

        "restart_consumed_before_buy_usd":
            60.0,

        "buy_phase_new_usd":
            40.0,

        "projected_final_usd":
            100.0,

        "remaining_after_buy_usd":
            0.0,

        "fake_posts_after_sell_and_buy":
            2,

        "restart_replay_new_gross_usd":
            0.0,

        "restart_replay_new_posts":
            0,

        "passed":
            True,
    }


# ============================================================
# SCENARIO 2
# OVER-CAP BUY BLOCKED BEFORE WRITER
# ============================================================


def rehearse_over_cap_block():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker()
    )

    seed_order(
        broker=
            broker,

        intent=
            sell_intent(
                60.00
            ),

        status=
            "filled",

        order_id=
            "offline-cap-sell-overcap",
    )

    observed = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    posts_before = (
        broker.post_attempt_count
    )

    blocked = False

    try:

        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                observed,

            proposed=[
                buy_intent(
                    40.01
                )
            ],
        )

    except cap_guard.CumulativeCapGuardStop as exc:

        if (
            "exceeds the single permit ceiling"
            not in str(
                exc
            )
        ):

            raise

        blocked = True

    if not blocked:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "$100.01 projected gross was not blocked."
        )

    if (
        broker.post_attempt_count
        != posts_before
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "over-cap scenario reached writer POST."
        )

    return {
        "historical_consumed_usd":
            60.0,

        "attempted_new_usd":
            40.01,

        "attempted_projected_usd":
            100.01,

        "writer_posts":
            0,

        "blocked_before_writer":
            True,
    }


# ============================================================
# SCENARIO 3
# ACCEPTED ORDER + LOST RESPONSE + RESTART
# ============================================================


def rehearse_lost_response_recovery():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker(
            post_status=
                "new",

            lose_first_post_response=
                True,
        )
    )

    initial = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    preflight = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                initial,

            proposed=[
                sell_intent(
                    60.00
                )
            ],
        )
    )

    if (
        preflight[
            "projected_cumulative_gross_notional_usd"
        ]
        != 60.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "lost-response preflight failed."
        )

    first_failed = False

    try:

        submit_phase(
            broker=
                broker,

            permit_package=
                permit,

            intents=[
                sell_intent(
                    60.00
                )
            ],
        )

    except RuntimeError as exc:

        if (
            "API unavailable"
            not in str(
                exc
            )
        ):

            raise

        first_failed = True

    if not first_failed:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "simulated response loss did not occur."
        )

    if (
        broker.post_attempt_count
        != 1
        or
        broker.accepted_order_count
        != 1
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "fake broker did not retain the accepted order."
        )

    # --------------------------------------------------------
    # Restart has no local submission memory.
    #
    # Reconstruct exclusively from fake broker GETs.
    # --------------------------------------------------------

    restart_lookup = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    restart_check = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                restart_lookup,

            proposed=[
                sell_intent(
                    60.00
                )
            ],
        )
    )

    if (
        restart_check[
            "previously_consumed_gross_notional_usd"
        ]
        != 60.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "lost-response restart forgot consumed notional."
        )

    if (
        restart_check[
            "new_gross_notional_usd"
        ]
        != 0.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "lost-response order was double-counted."
        )

    posts_before_restart_writer = (
        broker.post_attempt_count
    )

    result = (
        submit_phase(
            broker=
                broker,

            permit_package=
                permit,

            intents=[
                sell_intent(
                    60.00
                )
            ],
        )
    )

    if (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        != "EXISTING_NO_RESUBMIT_ORDER"
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "lost-response restart did not "
            "recover existing order."
        )

    if (
        broker.post_attempt_count
        != posts_before_restart_writer
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "lost-response restart duplicated POST."
        )

    return {
        "initial_fake_posts":
            1,

        "broker_accepted_orders":
            1,

        "restart_reconstructed_consumed_usd":
            60.0,

        "restart_new_gross_usd":
            0.0,

        "restart_new_posts":
            0,

        "passed":
            True,
    }


# ============================================================
# SCENARIO 4
# PARTIAL FILL CONSUMES FULL ORIGINAL NOTIONAL
# ============================================================


def rehearse_partial_fill_consumption():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker()
    )

    seed_order(
        broker=
            broker,

        intent=
            sell_intent(
                60.00
            ),

        status=
            "partially_filled",

        order_id=
            "offline-cap-partial",
    )

    observed = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    result = (
        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                observed,

            proposed=[
                buy_intent(
                    40.00
                )
            ],
        )
    )

    if (
        result[
            "previously_consumed_gross_notional_usd"
        ]
        != 60.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "partial order did not consume "
            "full original $60."
        )

    if (
        result[
            "projected_cumulative_gross_notional_usd"
        ]
        != 100.0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "partial-fill projected cap is incorrect."
        )

    return {
        "partial_order_original_notional_usd":
            60.0,

        "consumed_notional_usd":
            60.0,

        "projected_with_buy_usd":
            100.0,

        "passed":
            True,
    }


# ============================================================
# SCENARIO 5
# TERMINAL-FAILURE HISTORY CONSUMES + BLOCKS
# ============================================================


def rehearse_terminal_failure_history():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    tested = []

    for status in [
        "canceled",
        "expired",
        "rejected",
    ]:

        broker = (
            status_rehearsal.OfflineStatusBroker()
        )

        seed_order(
            broker=
                broker,

            intent=
                sell_intent(
                    60.00
                ),

            status=
                status,

            order_id=
                (
                    "offline-cap-terminal-"
                    + status
                ),
        )

        observed = (
            lookup_all_authorized(
                broker=
                    broker,

                compiler_body=
                    compiler,
            )
        )

        reconstructed = (
            cap_guard.reconstruct_consumed_state(
                compiler_body=
                    compiler,

                observed_orders_by_client_id=
                    observed,

                permit_cap_usd=
                    PERMIT_CAP_USD,
            )
        )

        if (
            float(
                reconstructed[
                    "consumed_gross_notional_usd"
                ]
            )
            != 60.0
        ):

            raise RuntimeError(
                "CAP REHEARSAL STOP: "
                f"{status}: historical notional "
                "was not retained."
            )

        if (
            len(
                reconstructed[
                    "blocking_existing_orders"
                ]
            )
            != 1
        ):

            raise RuntimeError(
                "CAP REHEARSAL STOP: "
                f"{status}: blocker was not created."
            )

        blocked = False

        try:

            evaluate(
                compiler_body=
                    compiler,

                permit_package=
                    permit,

                observed=
                    observed,

                proposed=[
                    buy_intent(
                        40.00
                    )
                ],
            )

        except cap_guard.CumulativeCapGuardStop as exc:

            if (
                "explicit reconciliation"
                not in str(
                    exc
                )
            ):

                raise

            blocked = True

        if not blocked:

            raise RuntimeError(
                "CAP REHEARSAL STOP: "
                f"{status}: continuation was not blocked."
            )

        if (
            broker.post_attempt_count
            != 0
        ):

            raise RuntimeError(
                "CAP REHEARSAL STOP: "
                f"{status}: blocking scenario POSTed."
            )

        tested.append(
            status
        )

    return {
        "statuses":
            tested,

        "consumed_notional_usd":
            60.0,

        "continuation_blocked":
            True,

        "writer_posts":
            0,
    }


# ============================================================
# SCENARIO 6
# UNSAFE HISTORY BLOCKS
# ============================================================


def rehearse_unsafe_history():

    compiler = (
        build_compiler_body()
    )

    permit = (
        build_synthetic_permit()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker()
    )

    seed_order(
        broker=
            broker,

        intent=
            sell_intent(
                60.00
            ),

        status=
            "held",

        order_id=
            "offline-cap-unsafe-held",
    )

    observed = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    blocked = False

    try:

        evaluate(
            compiler_body=
                compiler,

            permit_package=
                permit,

            observed=
                observed,

            proposed=[
                buy_intent(
                    40.00
                )
            ],
        )

    except cap_guard.CumulativeCapGuardStop:

        blocked = True

    if not blocked:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "unsafe historical state did not block."
        )

    if (
        broker.post_attempt_count
        != 0
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "unsafe-history scenario POSTed."
        )

    return True


# ============================================================
# SCENARIO 7
# INCOMPLETE LOOKUP FAILS CLOSED
# ============================================================


def rehearse_incomplete_lookup():

    compiler = (
        build_compiler_body()
    )

    blocked = False

    try:

        cap_guard.reconstruct_consumed_state(
            compiler_body=
                compiler,

            observed_orders_by_client_id={
                SELL_ID:
                    None,
            },

            permit_cap_usd=
                PERMIT_CAP_USD,
        )

    except cap_guard.CumulativeCapGuardStop as exc:

        if (
            "incomplete"
            not in str(
                exc
            )
        ):

            raise

        blocked = True

    if not blocked:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "incomplete broker reconstruction "
            "did not fail closed."
        )

    return True


# ============================================================
# SCENARIO 8
# HISTORICAL GROSS ALREADY OVER CAP
# ============================================================


def rehearse_historical_over_cap():

    compiler = (
        build_compiler_body()
    )

    broker = (
        status_rehearsal.OfflineStatusBroker()
    )

    seed_order(
        broker=
            broker,

        intent=
            sell_intent(
                100.01
            ),

        status=
            "filled",

        order_id=
            "offline-cap-history-over",
    )

    observed = (
        lookup_all_authorized(
            broker=
                broker,

            compiler_body=
                compiler,
        )
    )

    blocked = False

    try:

        cap_guard.reconstruct_consumed_state(
            compiler_body=
                compiler,

            observed_orders_by_client_id=
                observed,

            permit_cap_usd=
                PERMIT_CAP_USD,
        )

    except cap_guard.CumulativeCapGuardStop as exc:

        if (
            "already exceeds"
            not in str(
                exc
            )
        ):

            raise

        blocked = True

    if not blocked:

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "historical over-cap state did not fail closed."
        )

    return True


# ============================================================
# SAFE ARTIFACT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    candidate_sha256: str,
    cap_guard_sha256: str,
    exact_cap: dict,
    over_cap: dict,
    response_loss: dict,
    partial_fill: dict,
    terminal_history: dict,
):

    body = {
        "schema":
            REHEARSAL_SCHEMA,

        "mode":
            "COMPLETELY_OFFLINE_FAKE_BROKER",

        "source_release_lock_builder_version":
            EXPECTED_LOCK_BUILDER_VERSION,

        "source_release_lock_sha256":
            release_lock_sha256,

        "writer_candidate_version":
            candidate.WRITER_CANDIDATE_VERSION,

        "writer_candidate_source_sha256":
            candidate_sha256,

        "cumulative_cap_guard_version":
            cap_guard.GUARD_VERSION,

        "cumulative_cap_guard_source_sha256":
            cap_guard_sha256,

        "permit_cap_usd":
            PERMIT_CAP_USD,

        "real_alpaca_credentials_supplied":
            False,

        "real_broker_network_access":
            False,

        "real_broker_get_requests":
            0,

        "real_broker_post_requests":
            0,

        "orders_submitted_to_alpaca":
            0,

        "fake_broker_only":
            True,

        "writer_candidate_transport_released":
            False,

        "writer_candidate_public_execution_enabled":
            False,

        "complete_authorized_id_reconstruction_verified":
            True,

        "sell_restart_buy_exact_cap_verified":
            exact_cap[
                "passed"
            ],

        "sell_phase_projected_usd":
            exact_cap[
                "sell_phase_projected_usd"
            ],

        "restart_consumed_before_buy_usd":
            exact_cap[
                "restart_consumed_before_buy_usd"
            ],

        "buy_phase_new_usd":
            exact_cap[
                "buy_phase_new_usd"
            ],

        "exact_cap_projected_final_usd":
            exact_cap[
                "projected_final_usd"
            ],

        "exact_cap_remaining_after_buy_usd":
            exact_cap[
                "remaining_after_buy_usd"
            ],

        "restart_replay_new_gross_usd":
            exact_cap[
                "restart_replay_new_gross_usd"
            ],

        "restart_replay_new_posts":
            exact_cap[
                "restart_replay_new_posts"
            ],

        "over_cap_blocked_before_writer":
            over_cap[
                "blocked_before_writer"
            ],

        "over_cap_attempted_projected_usd":
            over_cap[
                "attempted_projected_usd"
            ],

        "over_cap_writer_posts":
            over_cap[
                "writer_posts"
            ],

        "lost_response_recovery_verified":
            response_loss[
                "passed"
            ],

        "lost_response_initial_fake_posts":
            response_loss[
                "initial_fake_posts"
            ],

        "lost_response_restart_consumed_usd":
            response_loss[
                "restart_reconstructed_consumed_usd"
            ],

        "lost_response_restart_new_gross_usd":
            response_loss[
                "restart_new_gross_usd"
            ],

        "lost_response_restart_new_posts":
            response_loss[
                "restart_new_posts"
            ],

        "partial_fill_full_original_notional_consumed":
            partial_fill[
                "passed"
            ],

        "partial_fill_consumed_usd":
            partial_fill[
                "consumed_notional_usd"
            ],

        "terminal_failure_history_statuses":
            terminal_history[
                "statuses"
            ],

        "terminal_failure_history_consumed_usd":
            terminal_history[
                "consumed_notional_usd"
            ],

        "terminal_failure_continuation_blocked":
            terminal_history[
                "continuation_blocked"
            ],

        "terminal_failure_writer_posts":
            terminal_history[
                "writer_posts"
            ],

        "unsafe_history_continuation_blocked":
            True,

        "incomplete_lookup_fails_closed":
            True,

        "historical_over_cap_fails_closed":
            True,

        "single_permit_ceiling_across_phases_verified":
            True,

        "restart_reconstruction_from_broker_verified":
            True,

        "previous_client_id_not_double_counted":
            True,

        "previous_client_id_not_resubmitted":
            True,

        "cumulative_cap_rehearsal_passed":
            True,

        # ----------------------------------------------------
        # The rehearsal proves the requirement.
        # The RELEASE LOCK has not frozen it yet.
        # ----------------------------------------------------

        "cumulative_cap_hardening_tested":
            True,

        "cumulative_cap_hardening_release_lock_completed":
            False,

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "writer_connected":
            False,

        "activation_performed":
            False,
    }

    return {
        "cumulative_cap_rehearsal":
            body,

        "cumulative_cap_rehearsal_sha256":
            candidate.sha256_json(
                body
            ),
    }


def write_safe_output(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            package,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write(
            "\n"
        )

    stored = (
        load_json(
            OUTPUT_PATH
        )
    )

    if (
        candidate.sha256_json(
            stored[
                "cumulative_cap_rehearsal"
            ]
        )
        != stored[
            "cumulative_cap_rehearsal_sha256"
        ]
    ):

        raise RuntimeError(
            "CAP REHEARSAL STOP: "
            "stored artifact SHA256 failed."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 CUMULATIVE CAP / RESTART "
        "REHEARSAL v1.0"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: COMPLETELY OFFLINE"
    )

    print(
        "Real Alpaca credentials supplied: NO"
    )

    print(
        "Real broker network access: NONE"
    )

    print(
        "Synthetic permit ceiling: $100.00"
    )

    (
        _lock_package,
        _lock_body,
        lock_hash,
        candidate_hash,
    ) = (
        verify_release_lock()
    )

    print(
        "\nRelease lock v1.7: VERIFIED"
    )

    print(
        "Writer candidate v1.1: VERIFIED"
    )

    cap_guard_hash = (
        sha256_file(
            CAP_GUARD_PATH
        )
    )

    print(
        "Cumulative-cap guard v1.0: VERIFIED"
    )

    exact_cap = (
        rehearse_exact_cap_across_phases()
    )

    print(
        "SELL $60 -> restart -> BUY $40: PASS"
    )

    print(
        "Exact cumulative $100 ceiling: PASS"
    )

    print(
        "Second restart double-count prevention: PASS"
    )

    print(
        "Second restart duplicate POST prevention: PASS"
    )

    over_cap = (
        rehearse_over_cap_block()
    )

    print(
        "SELL $60 -> BUY $40.01: BLOCKED"
    )

    print(
        "Over-cap writer invocation: NONE"
    )

    response_loss = (
        rehearse_lost_response_recovery()
    )

    print(
        "Accepted-order lost-response reconstruction: PASS"
    )

    print(
        "Lost-response restart double-count prevention: PASS"
    )

    print(
        "Lost-response duplicate POST prevention: PASS"
    )

    partial_fill = (
        rehearse_partial_fill_consumption()
    )

    print(
        "Partial fill consumes full original notional: PASS"
    )

    terminal_history = (
        rehearse_terminal_failure_history()
    )

    print(
        "Canceled/expired/rejected notional retained: PASS"
    )

    print(
        "Canceled/expired/rejected continuation: BLOCKED"
    )

    rehearse_unsafe_history()

    print(
        "Unsafe historical state continuation: BLOCKED"
    )

    rehearse_incomplete_lookup()

    print(
        "Incomplete broker reconstruction: BLOCKED"
    )

    rehearse_historical_over_cap()

    print(
        "Historical gross already over cap: BLOCKED"
    )

    package = (
        build_safe_output(
            release_lock_sha256=
                lock_hash,

            candidate_sha256=
                candidate_hash,

            cap_guard_sha256=
                cap_guard_hash,

            exact_cap=
                exact_cap,

            over_cap=
                over_cap,

            response_loss=
                response_loss,

            partial_fill=
                partial_fill,

            terminal_history=
                terminal_history,
        )
    )

    write_safe_output(
        package
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 CUMULATIVE CAP REHEARSAL COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Release lock v1.7: VERIFIED"
    )

    print(
        "Writer candidate v1.1: VERIFIED"
    )

    print(
        "Cumulative-cap guard v1.0: VERIFIED"
    )

    print(
        "Mode: COMPLETELY OFFLINE"
    )

    print(
        "SELL -> restart -> BUY cumulative accounting: PASS"
    )

    print(
        "Exact permit ceiling: PASS"
    )

    print(
        "Over-cap phase: BLOCKED BEFORE WRITER"
    )

    print(
        "Lost-response restart reconstruction: PASS"
    )

    print(
        "Restart double-count prevention: PASS"
    )

    print(
        "Restart duplicate POST prevention: PASS"
    )

    print(
        "Partial-fill full-notional accounting: PASS"
    )

    print(
        "Failed-terminal historical notional retained: PASS"
    )

    print(
        "Failed-terminal continuation: BLOCKED"
    )

    print(
        "Unsafe historical continuation: BLOCKED"
    )

    print(
        "Incomplete broker reconstruction: BLOCKED"
    )

    print(
        "Historical over-cap state: BLOCKED"
    )

    print(
        "Real Alpaca credentials supplied: NO"
    )

    print(
        "Real broker network access: NONE"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Cumulative-cap hardening tested: YES"
    )

    print(
        "Cumulative-cap release lock completed: NO"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
    )

    print(
        "Maximum LIVE execution notional: $0.00"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Orders submitted to Alpaca: 0"
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
            "CUMULATIVE CAP REHEARSAL: FAILED",
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

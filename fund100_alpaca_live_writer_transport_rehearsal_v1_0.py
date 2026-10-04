from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import fund100_alpaca_live_writer_candidate_v1_0 as candidate


# ============================================================
# FUND-100 CONNECTED-WRITER TRANSPORT REHEARSAL v1.0
# ============================================================
#
# COMPLETELY OFFLINE.
#
# NO Alpaca credentials.
# NO real network.
# NO broker API calls.
# NO live orders.
#
# PURPOSE
# =======
#
# Exercise the POST-capable writer candidate against a fully
# in-memory fake broker.
#
# The rehearsal proves:
#
# 1. Fresh orders perform:
#
#       GET client_order_id
#       -> absent
#       -> POST
#
# 2. Clean restart performs:
#
#       GET client_order_id
#       -> existing matching order
#       -> NO duplicate POST
#
# 3. Partial restart submits only missing orders.
#
# 4. A POST accepted by the fake broker but followed by a
#    simulated lost response is recovered safely on restart.
#
# 5. Existing-order mismatches fail closed.
#
# 6. Candidate release constants remain hard-coded FALSE
#    before and after the rehearsal.
#
# CRITICAL:
#
# candidate.urlopen is replaced with an in-memory fake before
# the release guards are bypassed.
#
# The real urllib network function is therefore never reached.
#
# Synthetic permits, executable intents and fake broker orders
# are NEVER persisted.
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
    / "live_writer_transport_rehearsal_v1_0.json"
)


REHEARSAL_SCHEMA = (
    "FUND100_LIVE_WRITER_TRANSPORT_REHEARSAL_V1"
)


EXPECTED_LOCK_BUILDER_VERSION = "1.3"


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
            f"Required file missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


# ============================================================
# RELEASE LOCK VERIFICATION
# ============================================================


def verify_writer_candidate_lock():

    package = load_json(
        LOCK_PATH
    )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "invalid release-lock package."
        )

    body = package.get(
        "release_lock"
    )

    recorded_hash = str(
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
            "OFFLINE REHEARSAL STOP: "
            "release-lock body missing."
        )

    calculated_hash = (
        candidate.sha256_json(
            body
        )
    )

    if (
        recorded_hash
        != calculated_hash
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "release-lock SHA256 verification failed."
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
            "OFFLINE REHEARSAL STOP: "
            "writer-candidate v1.3 lock is required."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_source_locked",
        "static_audit_v1_11_source_locked",
        "offline_connected_writer_rehearsal_required",
        "connected_writer_release_still_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"release-lock field {field!r} "
                "is not TRUE."
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
                "OFFLINE REHEARSAL STOP: "
                f"release-lock field {field!r} "
                "is not FALSE."
            )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "locked live notional is not $0.00."
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
            "OFFLINE REHEARSAL STOP: "
            "release lock reports submitted orders."
        )

    hashes = body.get(
        "critical_file_sha256",
        {},
    )

    if not isinstance(
        hashes,
        dict,
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "critical-file hash map invalid."
        )

    required_files = [
        "fund100_alpaca_live_execution_materializer.py",
        "fund100_alpaca_live_writer_candidate_v1_0.py",
        "audit_fund100_live_boundary_v1_11.py",
    ]

    for filename in required_files:

        path = (
            ROOT
            / filename
        )

        expected = str(
            hashes.get(
                filename,
                "",
            )
        )

        if not expected:

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"{filename} is not release-lock bound."
            )

        actual = sha256_file(
            path
        )

        if actual != expected:

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"{filename} changed after release lock."
            )

    return (
        package,
        body,
        recorded_hash,
    )


# ============================================================
# SYNTHETIC INPUTS
# ============================================================


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

        # Purely synthetic rehearsal ceiling.
        "max_live_execution_notional_usd":
            20.00,

        "offline_transport_rehearsal":
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


def build_synthetic_intents():

    return [
        {
            "symbol":
                "SPY",

            "side":
                "buy",

            "notional_usd":
                4.00,

            "client_order_id":
                "f100live-offline-transport-b-spy",

            "executable":
                True,
        },

        {
            "symbol":
                "VNQ",

            "side":
                "sell",

            "notional_usd":
                3.00,

            "client_order_id":
                "f100live-offline-transport-s-vnq",

            "executable":
                True,
        },
    ]


# ============================================================
# FAKE HTTP RESPONSE
# ============================================================


class FakeResponse:

    def __init__(
        self,
        body: dict,
    ):

        self.body = (
            json.dumps(
                body
            ).encode(
                "utf-8"
            )
        )

    def __enter__(
        self,
    ):

        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):

        return False

    def read(
        self,
    ):

        return self.body


# ============================================================
# IN-MEMORY FAKE BROKER
# ============================================================


class OfflineBroker:

    def __init__(
        self,
        *,
        fail_after_accept_once: str | None = None,
    ):

        self.orders = {}

        self.get_count = 0

        self.post_attempt_count = 0

        self.accepted_order_count = 0

        self.fail_after_accept_once = (
            fail_after_accept_once
        )

        self.response_loss_triggered = False

    def seed_matching_order(
        self,
        intent: dict,
    ):

        payload = (
            candidate.build_order_payload(
                intent
            )
        )

        client_order_id = (
            payload[
                "client_order_id"
            ]
        )

        self.orders[
            client_order_id
        ] = {
            "id":
                (
                    "offline-seeded-"
                    + str(
                        len(
                            self.orders
                        )
                        + 1
                    )
                ),

            "client_order_id":
                client_order_id,

            "symbol":
                payload[
                    "symbol"
                ],

            "side":
                payload[
                    "side"
                ],

            "type":
                "market",

            "time_in_force":
                "day",

            "notional":
                payload[
                    "notional"
                ],

            "status":
                "new",
        }

    def seed_mismatching_order(
        self,
        intent: dict,
    ):

        payload = (
            candidate.build_order_payload(
                intent
            )
        )

        self.orders[
            payload[
                "client_order_id"
            ]
        ] = {
            "id":
                "offline-mismatch-1",

            "client_order_id":
                payload[
                    "client_order_id"
                ],

            # Deliberately wrong.
            "symbol":
                "IWM",

            "side":
                payload[
                    "side"
                ],

            "type":
                "market",

            "time_in_force":
                "day",

            "notional":
                payload[
                    "notional"
                ],

            "status":
                "new",
        }

    def urlopen(
        self,
        request,
        timeout=20,
    ):

        del timeout

        method = (
            request.get_method()
            .upper()
        )

        url = (
            request.full_url
        )

        # ----------------------------------------------------
        # GET /v2/orders:by_client_order_id
        # ----------------------------------------------------

        if method == "GET":

            self.get_count += 1

            parsed = urlparse(
                url
            )

            query = parse_qs(
                parsed.query
            )

            client_order_id = str(
                query.get(
                    "client_order_id",
                    [""],
                )[
                    0
                ]
            )

            existing = (
                self.orders.get(
                    client_order_id
                )
            )

            if existing is None:

                raise HTTPError(
                    url,
                    404,
                    "Not Found",
                    None,
                    None,
                )

            return FakeResponse(
                existing
            )

        # ----------------------------------------------------
        # POST /v2/orders
        # ----------------------------------------------------

        if method == "POST":

            self.post_attempt_count += 1

            if request.data is None:

                raise AssertionError(
                    "Offline POST contains no body."
                )

            payload = json.loads(
                request.data.decode(
                    "utf-8"
                )
            )

            client_order_id = str(
                payload[
                    "client_order_id"
                ]
            )

            # ------------------------------------------------
            # If the candidate ever attempts a duplicate POST
            # after an order is already stored, fail loudly.
            # ------------------------------------------------

            if (
                client_order_id
                in self.orders
            ):

                raise AssertionError(
                    "Duplicate POST reached fake broker for "
                    + client_order_id
                )

            response = {
                "id":
                    (
                        "offline-order-"
                        + str(
                            self.accepted_order_count
                            + 1
                        )
                    ),

                "client_order_id":
                    client_order_id,

                "symbol":
                    str(
                        payload[
                            "symbol"
                        ]
                    ).upper(),

                "side":
                    str(
                        payload[
                            "side"
                        ]
                    ).lower(),

                "type":
                    "market",

                "time_in_force":
                    "day",

                "notional":
                    str(
                        payload[
                            "notional"
                        ]
                    ),

                "status":
                    "new",
            }

            # ------------------------------------------------
            # Broker accepts/stores before response.
            # ------------------------------------------------

            self.orders[
                client_order_id
            ] = response

            self.accepted_order_count += 1

            # ------------------------------------------------
            # Simulate:
            #
            # broker accepted order
            #     ↓
            # response disappeared / connection failed
            #
            # Restart must recover by GET instead of POSTing
            # again.
            # ------------------------------------------------

            if (
                self.fail_after_accept_once
                == client_order_id
                and
                self.response_loss_triggered
                is False
            ):

                self.response_loss_triggered = True

                raise URLError(
                    "offline simulated response loss"
                )

            return FakeResponse(
                response
            )

        raise AssertionError(
            f"Unexpected offline HTTP method: {method}"
        )


# ============================================================
# CANDIDATE OFFLINE PATCH
# ============================================================


@contextmanager
def offline_candidate_transport(
    broker: OfflineBroker,
):

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "candidate transport constant is not FALSE."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "candidate public-execution constant is not FALSE."
        )

    original_urlopen = (
        candidate.urlopen
    )

    original_transport_guard = (
        candidate.require_transport_released
    )

    original_public_guard = (
        candidate.require_public_execution_released
    )

    # --------------------------------------------------------
    # ORDER MATTERS:
    #
    # Install fake transport FIRST.
    #
    # Only then bypass guards in memory.
    # --------------------------------------------------------

    candidate.urlopen = (
        broker.urlopen
    )

    candidate.require_transport_released = (
        lambda: None
    )

    candidate.require_public_execution_released = (
        lambda: None
    )

    try:

        yield

    finally:

        candidate.require_public_execution_released = (
            original_public_guard
        )

        candidate.require_transport_released = (
            original_transport_guard
        )

        candidate.urlopen = (
            original_urlopen
        )

    # --------------------------------------------------------
    # Source-level release state must remain untouched.
    # --------------------------------------------------------

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "candidate transport constant changed."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "candidate public-execution constant changed."
        )


# ============================================================
# WRITER CALL
# ============================================================


def execute_against_fake_broker(
    broker: OfflineBroker,
    intents: list,
    permit_package: dict,
):

    with offline_candidate_transport(
        broker
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


# ============================================================
# SCENARIO 1 — FRESH + CLEAN RESTART
# ============================================================


def rehearse_fresh_and_clean_restart(
    intents: list,
    permit_package: dict,
):

    broker = OfflineBroker()

    first = (
        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    first_statuses = [
        item[
            "status"
        ]
        for item
        in first[
            "orders"
        ]
    ]

    if (
        first_statuses
        != [
            "SUBMITTED",
            "SUBMITTED",
        ]
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "fresh submission result unexpected."
        )

    posts_after_first = (
        broker.post_attempt_count
    )

    if posts_after_first != 2:

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "fresh batch did not make exactly two fake POSTs."
        )

    second = (
        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    second_statuses = [
        item[
            "status"
        ]
        for item
        in second[
            "orders"
        ]
    ]

    if (
        second_statuses
        != [
            "EXISTING_MATCHING_ORDER",
            "EXISTING_MATCHING_ORDER",
        ]
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "restart did not recover existing orders."
        )

    if (
        broker.post_attempt_count
        != posts_after_first
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "clean restart attempted duplicate POST."
        )

    return {
        "fresh_fake_posts":
            posts_after_first,

        "fresh_fake_accepts":
            broker.accepted_order_count,

        "clean_restart_new_posts":
            0,

        "clean_restart_existing_orders":
            2,

        "clean_restart_duplicate_suppression":
            True,
    }


# ============================================================
# SCENARIO 2 — PARTIAL RESTART
# ============================================================


def rehearse_partial_restart(
    intents: list,
    permit_package: dict,
):

    broker = OfflineBroker()

    broker.seed_matching_order(
        intents[
            0
        ]
    )

    result = (
        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    statuses = [
        item[
            "status"
        ]
        for item
        in result[
            "orders"
        ]
    ]

    if (
        statuses
        != [
            "EXISTING_MATCHING_ORDER",
            "SUBMITTED",
        ]
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "partial restart result unexpected."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "partial restart did not submit exactly "
            "one missing order."
        )

    return {
        "partial_restart_existing_orders":
            1,

        "partial_restart_new_posts":
            1,

        "partial_restart_missing_only":
            True,
    }


# ============================================================
# SCENARIO 3 — RESPONSE LOST AFTER ACCEPTANCE
# ============================================================


def rehearse_response_loss_restart(
    intents: list,
    permit_package: dict,
):

    lost_client_id = (
        intents[
            1
        ][
            "client_order_id"
        ]
    )

    broker = OfflineBroker(
        fail_after_accept_once=
            lost_client_id
    )

    first_failed_as_expected = False

    try:

        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )

    except RuntimeError as exc:

        if (
            "API unavailable"
            not in str(
                exc
            )
        ):

            raise

        first_failed_as_expected = True

    if not first_failed_as_expected:

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "simulated response loss did not fail."
        )

    if (
        broker.accepted_order_count
        != 2
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "fake broker did not retain both accepted orders."
        )

    posts_before_restart = (
        broker.post_attempt_count
    )

    result = (
        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    statuses = [
        item[
            "status"
        ]
        for item
        in result[
            "orders"
        ]
    ]

    if (
        statuses
        != [
            "EXISTING_MATCHING_ORDER",
            "EXISTING_MATCHING_ORDER",
        ]
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "response-loss restart did not recover "
            "existing broker state."
        )

    if (
        broker.post_attempt_count
        != posts_before_restart
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "response-loss restart attempted duplicate POST."
        )

    return {
        "response_loss_simulated":
            True,

        "orders_accepted_before_response_loss":
            2,

        "response_loss_restart_new_posts":
            0,

        "response_loss_restart_duplicate_suppression":
            True,
    }


# ============================================================
# SCENARIO 4 — EXISTING ORDER MISMATCH
# ============================================================


def rehearse_existing_order_mismatch(
    intents: list,
    permit_package: dict,
):

    broker = OfflineBroker()

    broker.seed_mismatching_order(
        intents[
            0
        ]
    )

    mismatch_rejected = False

    try:

        execute_against_fake_broker(
            broker=
                broker,

            intents=
                intents,

            permit_package=
                permit_package,
        )

    except candidate.ExistingOrderMismatch:

        mismatch_rejected = True

    if not mismatch_rejected:

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "mismatching existing order was accepted."
        )

    if (
        broker.post_attempt_count
        != 0
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "writer POSTed after idempotency mismatch."
        )

    return {
        "existing_order_mismatch_rejected":
            True,

        "posts_after_mismatch":
            0,

        "mismatch_fail_closed":
            True,
    }


# ============================================================
# SAFE OUTPUT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    fresh_restart: dict,
    partial_restart: dict,
    response_loss: dict,
    mismatch: dict,
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

        "writer_candidate_source_locked":
            True,

        "candidate_transport_constant_false_before_after":
            (
                candidate.TRANSPORT_RELEASED
                is False
            ),

        "candidate_public_execution_constant_false_before_after":
            (
                candidate.PUBLIC_EXECUTION_ENABLED
                is False
            ),

        "fake_transport_installed_before_guard_bypass":
            True,

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

        "synthetic_permit_persisted":
            False,

        "synthetic_executable_intents_persisted":
            False,

        "fresh_submission_verified":
            True,

        "fresh_fake_posts":
            fresh_restart[
                "fresh_fake_posts"
            ],

        "clean_restart_duplicate_suppression":
            fresh_restart[
                "clean_restart_duplicate_suppression"
            ],

        "clean_restart_new_posts":
            fresh_restart[
                "clean_restart_new_posts"
            ],

        "partial_restart_missing_only":
            partial_restart[
                "partial_restart_missing_only"
            ],

        "partial_restart_new_posts":
            partial_restart[
                "partial_restart_new_posts"
            ],

        "response_loss_simulated":
            response_loss[
                "response_loss_simulated"
            ],

        "response_loss_restart_duplicate_suppression":
            response_loss[
                "response_loss_restart_duplicate_suppression"
            ],

        "response_loss_restart_new_posts":
            response_loss[
                "response_loss_restart_new_posts"
            ],

        "existing_order_mismatch_rejected":
            mismatch[
                "existing_order_mismatch_rejected"
            ],

        "mismatch_posts":
            mismatch[
                "posts_after_mismatch"
            ],

        "restart_recovery_verified":
            True,

        "at_most_once_client_order_id_behavior_verified":
            True,

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "network_write_capability":
            False,

        "writer_connected":
            False,

        "activation_performed":
            False,
    }

    return {
        "rehearsal":
            body,

        "rehearsal_sha256":
            candidate.sha256_json(
                body
            ),
    }


def assert_safe_output(
    body: dict,
):

    required_true = [
        "writer_candidate_source_locked",
        "candidate_transport_constant_false_before_after",
        "candidate_public_execution_constant_false_before_after",
        "fake_transport_installed_before_guard_bypass",
        "fresh_submission_verified",
        "clean_restart_duplicate_suppression",
        "partial_restart_missing_only",
        "response_loss_simulated",
        "response_loss_restart_duplicate_suppression",
        "existing_order_mismatch_rejected",
        "restart_recovery_verified",
        "at_most_once_client_order_id_behavior_verified",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"{field!r} is not TRUE."
            )

    required_false = [
        "real_alpaca_credentials_supplied",
        "real_broker_network_access",
        "synthetic_permit_persisted",
        "synthetic_executable_intents_persisted",
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
        "activation_performed",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"{field!r} is not FALSE."
            )

    zero_fields = [
        "real_broker_get_requests",
        "real_broker_post_requests",
        "orders_submitted_to_alpaca",
        "clean_restart_new_posts",
        "response_loss_restart_new_posts",
        "mismatch_posts",
    ]

    for field in zero_fields:

        if (
            int(
                body.get(
                    field,
                    -1,
                )
            )
            != 0
        ):

            raise RuntimeError(
                "OFFLINE REHEARSAL STOP: "
                f"{field!r} is not zero."
            )


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

    stored = load_json(
        OUTPUT_PATH
    )

    if (
        candidate.sha256_json(
            stored[
                "rehearsal"
            ]
        )
        != stored[
            "rehearsal_sha256"
        ]
    ):

        raise RuntimeError(
            "OFFLINE REHEARSAL STOP: "
            "stored rehearsal SHA256 failed."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 CONNECTED-WRITER "
        "TRANSPORT REHEARSAL v1.0"
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
        "Writer candidate transport released: FALSE"
    )

    print(
        "Writer candidate public execution enabled: FALSE"
    )

    (
        _lock_package,
        _lock_body,
        lock_hash,
    ) = (
        verify_writer_candidate_lock()
    )

    print(
        "\nWriter-candidate release lock: PASS"
    )

    print(
        "Writer candidate source hash: PASS"
    )

    permit_package = (
        build_synthetic_permit()
    )

    intents = (
        build_synthetic_intents()
    )

    fresh_restart = (
        rehearse_fresh_and_clean_restart(
            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    print(
        "\nFresh fake submission: PASS"
    )

    print(
        "Clean restart duplicate suppression: PASS"
    )

    partial_restart = (
        rehearse_partial_restart(
            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    print(
        "Partial restart missing-only submission: PASS"
    )

    response_loss = (
        rehearse_response_loss_restart(
            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    print(
        "Lost-response restart recovery: PASS"
    )

    print(
        "Lost-response duplicate suppression: PASS"
    )

    mismatch = (
        rehearse_existing_order_mismatch(
            intents=
                intents,

            permit_package=
                permit_package,
        )
    )

    print(
        "Existing-order mismatch fail-closed: PASS"
    )

    package = (
        build_safe_output(
            release_lock_sha256=
                lock_hash,

            fresh_restart=
                fresh_restart,

            partial_restart=
                partial_restart,

            response_loss=
                response_loss,

            mismatch=
                mismatch,
        )
    )

    assert_safe_output(
        package[
            "rehearsal"
        ]
    )

    write_safe_output(
        package
    )

    # Remove in-memory references before final report.
    permit_package = None
    intents = None

    print(
        "\nSynthetic writer-compatible permit persisted: NO"
    )

    print(
        "Synthetic executable intents persisted: NO"
    )

    print(
        "Real broker GET requests: 0"
    )

    print(
        "Real broker POST requests: 0"
    )

    print(
        "Orders submitted to Alpaca: 0"
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 OFFLINE CONNECTED-WRITER "
        "REHEARSAL COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Writer-candidate release lock: VERIFIED"
    )

    print(
        "Fresh submission path: PASS"
    )

    print(
        "Clean restart duplicate suppression: PASS"
    )

    print(
        "Partial restart recovery: PASS"
    )

    print(
        "Lost-response recovery: PASS"
    )

    print(
        "Existing-order mismatch rejection: PASS"
    )

    print(
        "At-most-once client-order behavior: VERIFIED"
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
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
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
            "OFFLINE CONNECTED-WRITER "
            "REHEARSAL: FAILED",
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

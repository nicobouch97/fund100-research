from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 WRITER STATUS / RESTART REHEARSAL v1.0
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
# Exercise writer candidate v1.1 against a fully in-memory
# fake broker and prove the status semantics added after the
# v1.6 release lock.
#
# This rehearsal proves:
#
# 1. FILLED existing orders:
#       recover
#       never POST again
#
# 2. ACTIVE / TRANSITIONAL existing orders:
#       recover as NO-RESUBMIT
#       never POST again
#
# 3. TERMINAL FAILURE existing orders:
#       canceled / expired / rejected
#       fail closed
#       zero POST
#
# 4. AMBIGUOUS / UNKNOWN existing orders:
#       fail closed
#       zero POST
#
# 5. Structural mismatch:
#       fail closed
#       zero POST
#
# 6. Lost response after fake broker acceptance:
#       restart finds existing NEW order
#       no duplicate POST
#
# 7. POST returning terminal failure:
#       immediate fail closed
#       subsequent restart also fails closed
#       no second POST
#
# 8. POST returning unsafe status:
#       immediate fail closed
#       subsequent restart also fails closed
#       no second POST
#
# CRITICAL:
#
# candidate.urlopen is replaced with an in-memory fake BEFORE
# release guards are bypassed.
#
# Candidate source constants remain FALSE before and after.
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
    / "live_writer_status_rehearsal_v1_0.json"
)


CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_1.py"
)


PRIOR_CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_0.py"
)


REHEARSAL_SCHEMA = (
    "FUND100_LIVE_WRITER_STATUS_REHEARSAL_V1"
)


EXPECTED_LOCK_BUILDER_VERSION = "1.6"


# ============================================================
# HASH / FILE HELPERS
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
            f"STATUS REHEARSAL STOP: "
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
# RELEASE LOCK VERIFICATION
# ============================================================


def verify_release_lock():

    package = (
        load_json(
            LOCK_PATH
        )
    )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
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
            "STATUS REHEARSAL STOP: "
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
            "STATUS REHEARSAL STOP: "
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
            "STATUS REHEARSAL STOP: "
            "release lock is not v1.6."
        )

    if (
        body.get(
            "connected_writer_status_semantics_hardening_required"
        )
        is not True
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "v1.6 does not require status hardening."
        )

    if (
        body.get(
            "connected_writer_status_semantics_hardening_completed"
        )
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "status hardening is unexpectedly complete."
        )

    if (
        body.get(
            "connected_writer_cumulative_cap_recovery_required"
        )
        is not True
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "cumulative-cap requirement disappeared."
        )

    if (
        body.get(
            "connected_writer_cumulative_cap_recovery_completed"
        )
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "cumulative-cap hardening is unexpectedly complete."
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
                "STATUS REHEARSAL STOP: "
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
            "STATUS REHEARSAL STOP: "
            "LIVE notional ceiling is not zero."
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
            "STATUS REHEARSAL STOP: "
            "release lock reports LIVE orders."
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
            "STATUS REHEARSAL STOP: "
            "critical-file map missing."
        )

    expected_prior_hash = str(
        hashes.get(
            "fund100_alpaca_live_writer_candidate_v1_0.py",
            "",
        )
    )

    if not expected_prior_hash:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "v1.0 writer candidate is not lock-bound."
        )

    actual_prior_hash = (
        sha256_file(
            PRIOR_CANDIDATE_PATH
        )
    )

    if (
        expected_prior_hash
        != actual_prior_hash
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "locked v1.0 writer candidate changed."
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

        "max_live_execution_notional_usd":
            20.00,

        "offline_status_rehearsal":
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


def build_synthetic_intent():

    return {
        "symbol":
            "SPY",

        "side":
            "buy",

        "notional_usd":
            4.00,

        "client_order_id":
            "f100live-offline-status-b-spy",

        "executable":
            True,
    }


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
# IN-MEMORY BROKER
# ============================================================


class OfflineStatusBroker:

    def __init__(
        self,
        *,
        post_status: str = "new",
        lose_first_post_response: bool = False,
    ):

        self.orders = {}

        self.get_count = 0

        self.post_attempt_count = 0

        self.accepted_order_count = 0

        self.post_status = (
            post_status
        )

        self.lose_first_post_response = (
            lose_first_post_response
        )

        self.response_loss_triggered = False

    def order_from_intent(
        self,
        *,
        intent: dict,
        status: str | None,
        order_id: str,
        mismatch_symbol: bool = False,
        omit_status: bool = False,
    ):

        payload = (
            candidate.build_order_payload(
                intent
            )
        )

        result = {
            "id":
                order_id,

            "client_order_id":
                payload[
                    "client_order_id"
                ],

            "symbol":
                (
                    "IWM"
                    if mismatch_symbol
                    else payload[
                        "symbol"
                    ]
                ),

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
        }

        if not omit_status:

            result[
                "status"
            ] = status

        return result

    def seed_existing(
        self,
        *,
        intent: dict,
        status: str | None,
        mismatch_symbol: bool = False,
        omit_status: bool = False,
    ):

        order = (
            self.order_from_intent(
                intent=
                    intent,

                status=
                    status,

                order_id=
                    "offline-existing-1",

                mismatch_symbol=
                    mismatch_symbol,

                omit_status=
                    omit_status,
            )
        )

        self.orders[
            intent[
                "client_order_id"
            ]
        ] = order

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

        parsed = (
            urlparse(
                request.full_url
            )
        )

        # ----------------------------------------------------
        # GET /v2/orders:by_client_order_id
        # ----------------------------------------------------

        if method == "GET":

            if (
                parsed.path
                != candidate.LIVE_ORDER_BY_CLIENT_ID_PATH
            ):

                raise AssertionError(
                    "Unexpected fake GET path."
                )

            self.get_count += 1

            query = (
                parse_qs(
                    parsed.query
                )
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

                raise candidate.HTTPError(
                    request.full_url,
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

            if (
                parsed.path
                != candidate.LIVE_ORDER_PATH
            ):

                raise AssertionError(
                    "Unexpected fake POST path."
                )

            self.post_attempt_count += 1

            if request.data is None:

                raise AssertionError(
                    "Fake POST body missing."
                )

            payload = (
                json.loads(
                    request.data.decode(
                        "utf-8"
                    )
                )
            )

            client_order_id = str(
                payload[
                    "client_order_id"
                ]
            )

            if (
                client_order_id
                in self.orders
            ):

                raise AssertionError(
                    "Duplicate POST reached fake broker."
                )

            order = {
                "id":
                    (
                        "offline-posted-"
                        + str(
                            self.accepted_order_count
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
                    self.post_status,
            }

            self.orders[
                client_order_id
            ] = order

            self.accepted_order_count += 1

            if (
                self.lose_first_post_response
                and
                not self.response_loss_triggered
            ):

                self.response_loss_triggered = True

                raise candidate.URLError(
                    "simulated offline response loss"
                )

            return FakeResponse(
                order
            )

        raise AssertionError(
            "Unexpected fake HTTP method."
        )


# ============================================================
# OFFLINE CANDIDATE PATCH
# ============================================================


@contextmanager
def offline_candidate_transport(
    broker: OfflineStatusBroker,
):

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "candidate transport constant changed."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "candidate public-execution constant changed."
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
    # SECURITY ORDER:
    #
    # Install fake transport BEFORE bypassing guards.
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

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "candidate transport constant changed."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "candidate public-execution constant changed."
        )


def execute(
    *,
    broker: OfflineStatusBroker,
    intent: dict,
    permit_package: dict,
):

    with offline_candidate_transport(
        broker
    ):

        return (
            candidate.submit_authorized_order_batch(
                intents=[
                    intent
                ],

                permit_package=
                    permit_package,

                key=
                    "offline-fake-key",

                secret=
                    "offline-fake-secret",
            )
        )


# ============================================================
# EXISTING-ORDER SCENARIOS
# ============================================================


def rehearse_filled(
    *,
    intent: dict,
    permit_package: dict,
):

    broker = (
        OfflineStatusBroker()
    )

    broker.seed_existing(
        intent=
            intent,

        status=
            "filled",
    )

    result = (
        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    status = (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
    )

    if (
        status
        != "EXISTING_FILLED_ORDER"
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "filled order was not recovered correctly."
        )

    if (
        broker.post_attempt_count
        != 0
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "filled order triggered a POST."
        )

    return True


def rehearse_no_resubmit_statuses(
    *,
    intent: dict,
    permit_package: dict,
):

    tested = []

    for status in sorted(
        candidate.NO_RESUBMIT_STATUSES
    ):

        broker = (
            OfflineStatusBroker()
        )

        broker.seed_existing(
            intent=
                intent,

            status=
                status,
        )

        result = (
            execute(
                broker=
                    broker,

                intent=
                    intent,

                permit_package=
                    permit_package,
            )
        )

        recovered = (
            result[
                "orders"
            ][
                0
            ][
                "status"
            ]
        )

        if (
            recovered
            != "EXISTING_NO_RESUBMIT_ORDER"
        ):

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} did not recover "
                "as NO-RESUBMIT."
            )

        if (
            broker.post_attempt_count
            != 0
        ):

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} triggered a POST."
            )

        tested.append(
            status
        )

    return tested


def rehearse_terminal_failures(
    *,
    intent: dict,
    permit_package: dict,
):

    tested = []

    for status in sorted(
        candidate.TERMINAL_FAILURE_STATUSES
    ):

        broker = (
            OfflineStatusBroker()
        )

        broker.seed_existing(
            intent=
                intent,

            status=
                status,
        )

        failed = False

        try:

            execute(
                broker=
                    broker,

                intent=
                    intent,

                permit_package=
                    permit_package,
            )

        except candidate.ExistingOrderTerminalFailure:

            failed = True

        if not failed:

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} did not fail closed."
            )

        if (
            broker.post_attempt_count
            != 0
        ):

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} triggered a POST."
            )

        tested.append(
            status
        )

    return tested


def rehearse_unsafe_statuses(
    *,
    intent: dict,
    permit_package: dict,
):

    statuses = sorted(
        candidate.AMBIGUOUS_UNSAFE_STATUSES
    ) + [
        "future_unknown_status",
    ]

    tested = []

    for status in statuses:

        broker = (
            OfflineStatusBroker()
        )

        broker.seed_existing(
            intent=
                intent,

            status=
                status,
        )

        failed = False

        try:

            execute(
                broker=
                    broker,

                intent=
                    intent,

                permit_package=
                    permit_package,
            )

        except candidate.ExistingOrderUnsafeStatus:

            failed = True

        if not failed:

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} did not fail closed."
            )

        if (
            broker.post_attempt_count
            != 0
        ):

            raise RuntimeError(
                "STATUS REHEARSAL STOP: "
                f"{status!r} triggered a POST."
            )

        tested.append(
            status
        )

    # Missing status must also fail closed.

    broker = (
        OfflineStatusBroker()
    )

    broker.seed_existing(
        intent=
            intent,

        status=
            None,

        omit_status=
            True,
    )

    failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.ExistingOrderUnsafeStatus:

        failed = True

    if not failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "missing order status did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 0
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "missing order status triggered a POST."
        )

    return {
        "statuses":
            tested,

        "missing_status_rejected":
            True,
    }


def rehearse_structural_mismatch(
    *,
    intent: dict,
    permit_package: dict,
):

    broker = (
        OfflineStatusBroker()
    )

    broker.seed_existing(
        intent=
            intent,

        status=
            "new",

        mismatch_symbol=
            True,
    )

    failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.ExistingOrderMismatch:

        failed = True

    if not failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "structural mismatch did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 0
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "structural mismatch triggered a POST."
        )

    return True


# ============================================================
# LOST RESPONSE / RESTART
# ============================================================


def rehearse_response_loss_restart(
    *,
    intent: dict,
    permit_package: dict,
):

    broker = (
        OfflineStatusBroker(
            post_status=
                "new",

            lose_first_post_response=
                True,
        )
    )

    first_failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

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

        first_failed = True

    if not first_failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "simulated response loss did not fail."
        )

    if (
        broker.post_attempt_count
        != 1
        or
        broker.accepted_order_count
        != 1
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "response-loss broker state unexpected."
        )

    posts_before_restart = (
        broker.post_attempt_count
    )

    result = (
        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    status = (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
    )

    if (
        status
        != "EXISTING_NO_RESUBMIT_ORDER"
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "response-loss restart did not "
            "recover existing NEW order."
        )

    if (
        broker.post_attempt_count
        != posts_before_restart
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "response-loss restart duplicated POST."
        )

    return {
        "initial_fake_posts":
            1,

        "restart_new_posts":
            0,

        "duplicate_suppression":
            True,
    }


# ============================================================
# POST-RESPONSE STATUS SCENARIOS
# ============================================================


def rehearse_submitted_terminal_failure(
    *,
    intent: dict,
    permit_package: dict,
):

    broker = (
        OfflineStatusBroker(
            post_status=
                "rejected"
        )
    )

    first_failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.SubmittedOrderTerminalFailure:

        first_failed = True

    if not first_failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "terminal POST response did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "terminal-response scenario "
            "did not perform exactly one POST."
        )

    restart_failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.ExistingOrderTerminalFailure:

        restart_failed = True

    if not restart_failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "restart after terminal response "
            "did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "terminal-response restart "
            "performed a second POST."
        )

    return True


def rehearse_submitted_unsafe_status(
    *,
    intent: dict,
    permit_package: dict,
):

    broker = (
        OfflineStatusBroker(
            post_status=
                "replaced"
        )
    )

    first_failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.SubmittedOrderUnsafeStatus:

        first_failed = True

    if not first_failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "unsafe POST response did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "unsafe-response scenario "
            "did not perform exactly one POST."
        )

    restart_failed = False

    try:

        execute(
            broker=
                broker,

            intent=
                intent,

            permit_package=
                permit_package,
        )

    except candidate.ExistingOrderUnsafeStatus:

        restart_failed = True

    if not restart_failed:

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "restart after unsafe response "
            "did not fail closed."
        )

    if (
        broker.post_attempt_count
        != 1
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "unsafe-response restart "
            "performed a second POST."
        )

    return True


# ============================================================
# SAFE EVIDENCE OUTPUT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    candidate_sha256: str,
    prior_candidate_sha256: str,
    no_resubmit_statuses: list[str],
    terminal_statuses: list[str],
    unsafe_result: dict,
    response_loss: dict,
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

        "prior_writer_candidate_source_sha256":
            prior_candidate_sha256,

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

        "synthetic_executable_intent_persisted":
            False,

        "filled_existing_order_recovery_verified":
            True,

        "filled_existing_order_posts":
            0,

        "no_resubmit_statuses_verified":
            no_resubmit_statuses,

        "no_resubmit_status_count":
            len(
                no_resubmit_statuses
            ),

        "no_resubmit_status_posts":
            0,

        "terminal_failure_statuses_verified":
            terminal_statuses,

        "terminal_failure_status_count":
            len(
                terminal_statuses
            ),

        "terminal_failure_posts":
            0,

        "ambiguous_unsafe_statuses_verified":
            unsafe_result[
                "statuses"
            ],

        "missing_status_rejected":
            unsafe_result[
                "missing_status_rejected"
            ],

        "unsafe_status_posts":
            0,

        "existing_order_structural_mismatch_rejected":
            True,

        "structural_mismatch_posts":
            0,

        "response_loss_restart_verified":
            True,

        "response_loss_initial_fake_posts":
            response_loss[
                "initial_fake_posts"
            ],

        "response_loss_restart_new_posts":
            response_loss[
                "restart_new_posts"
            ],

        "response_loss_duplicate_suppression":
            response_loss[
                "duplicate_suppression"
            ],

        "submitted_terminal_failure_rejected":
            True,

        "submitted_terminal_failure_restart_rejected":
            True,

        "submitted_terminal_failure_total_fake_posts":
            1,

        "submitted_unsafe_status_rejected":
            True,

        "submitted_unsafe_restart_rejected":
            True,

        "submitted_unsafe_total_fake_posts":
            1,

        "automatic_resubmission_after_failed_terminal_status":
            False,

        "automatic_resubmission_after_unsafe_status":
            False,

        "status_semantics_rehearsal_passed":
            True,

        "cumulative_cap_hardening_tested":
            False,

        "cumulative_cap_hardening_still_required":
            True,

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
        "status_rehearsal":
            body,

        "status_rehearsal_sha256":
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
                "status_rehearsal"
            ]
        )
        != stored[
            "status_rehearsal_sha256"
        ]
    ):

        raise RuntimeError(
            "STATUS REHEARSAL STOP: "
            "stored evidence SHA256 failed."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 WRITER STATUS / RESTART "
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
        "Candidate v1.1 transport released: FALSE"
    )

    print(
        "Candidate v1.1 public execution enabled: FALSE"
    )

    (
        _lock_package,
        _lock_body,
        lock_hash,
    ) = (
        verify_release_lock()
    )

    print(
        "\nRelease lock v1.6: VERIFIED"
    )

    candidate_hash = (
        sha256_file(
            CANDIDATE_PATH
        )
    )

    prior_candidate_hash = (
        sha256_file(
            PRIOR_CANDIDATE_PATH
        )
    )

    print(
        "Writer candidate v1.1 source hash: CAPTURED"
    )

    permit_package = (
        build_synthetic_permit()
    )

    intent = (
        build_synthetic_intent()
    )

    rehearse_filled(
        intent=
            intent,

        permit_package=
            permit_package,
    )

    print(
        "Filled-order restart recovery: PASS"
    )

    no_resubmit = (
        rehearse_no_resubmit_statuses(
            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    print(
        "Active/transitional NO-RESUBMIT statuses: PASS"
    )

    terminal = (
        rehearse_terminal_failures(
            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    print(
        "Canceled/expired/rejected fail-closed: PASS"
    )

    unsafe = (
        rehearse_unsafe_statuses(
            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    print(
        "Ambiguous/unknown/missing statuses fail-closed: PASS"
    )

    rehearse_structural_mismatch(
        intent=
            intent,

        permit_package=
            permit_package,
    )

    print(
        "Structural mismatch fail-closed: PASS"
    )

    response_loss = (
        rehearse_response_loss_restart(
            intent=
                intent,

            permit_package=
                permit_package,
        )
    )

    print(
        "Lost-response restart recovery: PASS"
    )

    print(
        "Lost-response duplicate POST suppression: PASS"
    )

    rehearse_submitted_terminal_failure(
        intent=
            intent,

        permit_package=
            permit_package,
    )

    print(
        "Terminal POST-response rejection: PASS"
    )

    print(
        "Terminal POST-response restart no-resubmit: PASS"
    )

    rehearse_submitted_unsafe_status(
        intent=
            intent,

        permit_package=
            permit_package,
    )

    print(
        "Unsafe POST-response rejection: PASS"
    )

    print(
        "Unsafe POST-response restart no-resubmit: PASS"
    )

    package = (
        build_safe_output(
            release_lock_sha256=
                lock_hash,

            candidate_sha256=
                candidate_hash,

            prior_candidate_sha256=
                prior_candidate_hash,

            no_resubmit_statuses=
                no_resubmit,

            terminal_statuses=
                terminal,

            unsafe_result=
                unsafe,

            response_loss=
                response_loss,
        )
    )

    write_safe_output(
        package
    )

    permit_package = None
    intent = None

    print(
        "\n============================================"
    )

    print(
        "FUND-100 WRITER STATUS REHEARSAL COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Release lock v1.6: VERIFIED"
    )

    print(
        "Writer candidate v1.1: VERIFIED"
    )

    print(
        "Mode: COMPLETELY OFFLINE"
    )

    print(
        "Filled restart recovery: PASS"
    )

    print(
        "Active/partial no-resubmit: PASS"
    )

    print(
        "Canceled/expired/rejected rejection: PASS"
    )

    print(
        "Ambiguous/unknown status rejection: PASS"
    )

    print(
        "Missing status rejection: PASS"
    )

    print(
        "Existing-order structural mismatch rejection: PASS"
    )

    print(
        "Lost-response duplicate suppression: PASS"
    )

    print(
        "Failed-terminal automatic resubmission: BLOCKED"
    )

    print(
        "Unsafe-status automatic resubmission: BLOCKED"
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
        "Cumulative-cap hardening tested: NO"
    )

    print(
        "Cumulative-cap hardening still required: YES"
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
            "WRITER STATUS REHEARSAL: FAILED",
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

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import fund100_alpaca_live_writer_candidate_v1_0 as candidate
import fund100_alpaca_paper_transport_v1_0 as paper

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 CONNECTED-WRITER PAPER PARITY v1.0
# ============================================================
#
# PAPER ACCOUNT ONLY.
#
# This test performs one real PAPER order submission.
#
# It DOES NOT:
#
# - use LIVE credentials
# - contact the LIVE Alpaca host
# - alter candidate source
# - release candidate transport
# - release candidate public execution
# - issue a real LIVE permit
# - authorize LIVE execution
#
# Sequence:
#
# 1. Verify release lock v1.5.
# 2. Verify candidate source hash.
# 3. Require kill switch ENGAGED.
# 4. Require Alpaca PAPER market CLOSED.
# 5. Require no genuinely open PAPER orders.
# 6. Redirect candidate transport IN MEMORY to PAPER.
# 7. Exercise exact writer candidate:
#
#       GET client_order_id
#       POST $1 PAPER order
#
# 8. Exercise restart:
#
#       GET client_order_id
#       existing matching order
#       NO duplicate POST
#
# 9. Restore candidate immediately.
# 10. Cancel the PAPER order.
# 11. Poll direct order state until terminal + zero-fill.
# 12. Poll the account-wide open-order index until it
#     converges with that terminal state.
# 13. Persist structural evidence only.
#
# Alpaca cancellation is asynchronous. A successful DELETE
# means the cancel request was accepted; an order can pass
# through pending_cancel before all API views converge.
#
# We therefore require BOTH:
#
# - direct order endpoint => terminal + zero-fill
# - open-order index => eventual absence of the test order
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
    / "paper_connected_writer_parity_v1_0.json"
)


CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_0.py"
)


SCHEMA = (
    "FUND100_PAPER_CONNECTED_WRITER_PARITY_V1"
)


EXPECTED_LOCK_BUILDER_VERSION = "1.5"


ARM_ENV = (
    "FUND100_ENABLE_PAPER_WRITER_PARITY"
)


ARM_VALUE = (
    "YES_PAPER_WRITER_PARITY"
)


TEST_SYMBOL = "SPY"

TEST_NOTIONAL_USD = 1.00


SAFE_TERMINAL_STATUSES = {
    "canceled",
    "expired",
    "rejected",
}


TERMINAL_POLL_ATTEMPTS = 45

OPEN_INDEX_POLL_ATTEMPTS = 45

POLL_INTERVAL_SECONDS = 1.0


# ============================================================
# HASHING
# ============================================================


def canonical_json(
    obj,
):

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
):

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_file(
    path: Path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


# ============================================================
# LOAD / VERIFY LOCK
# ============================================================


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            "PAPER PARITY STOP: "
            f"required file missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


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
            "PAPER PARITY STOP: "
            "invalid release-lock package."
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
            "PAPER PARITY STOP: "
            "release-lock body missing."
        )

    if (
        sha256_json(
            body
        )
        != recorded
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
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
            "PAPER PARITY STOP: "
            "release lock is not v1.5."
        )

    if (
        body.get(
            "live_preconnect_runtime_check_completed"
        )
        is not True
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "LIVE GET-only pre-connect check "
            "is not complete."
        )

    if (
        body.get(
            "paper_connected_writer_parity_required"
        )
        is not True
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper parity is not required by lock."
        )

    if (
        body.get(
            "paper_connected_writer_parity_completed"
        )
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "release lock unexpectedly marks "
            "paper parity complete."
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
                "PAPER PARITY STOP: "
                f"release-lock field {field!r} "
                "is not FALSE."
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
            "PAPER PARITY STOP: "
            "release lock reports live orders."
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
            "PAPER PARITY STOP: "
            "live ceiling is not $0.00."
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
            "PAPER PARITY STOP: "
            "critical-file map missing."
        )

    expected_candidate_hash = (
        hashes.get(
            "fund100_alpaca_live_writer_candidate_v1_0.py"
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
            "PAPER PARITY STOP: "
            "writer candidate changed after lock."
        )

    return (
        package,
        body,
        recorded,
        actual_candidate_hash,
    )


# ============================================================
# ENVIRONMENT SAFETY
# ============================================================


def require_arm():

    if (
        os.environ.get(
            ARM_ENV,
            "",
        ).strip()
        != ARM_VALUE
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper transport parity is not armed."
        )


def reject_live_credentials():

    live_key = str(
        os.environ.get(
            "ALPACA_LIVE_KEY",
            "",
        )
    ).strip()

    live_secret = str(
        os.environ.get(
            "ALPACA_LIVE_SECRET",
            "",
        )
    ).strip()

    if (
        live_key
        or
        live_secret
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "LIVE credentials must not be supplied "
            "to PAPER parity workflow."
        )


# ============================================================
# SYNTHETIC PAPER-ONLY PERMIT / INTENT
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
            TEST_NOTIONAL_USD,

        "paper_transport_parity_only":
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


def build_test_intent():

    run_id = str(
        os.environ.get(
            "FUND100_PAPER_PARITY_RUN_ID",
            "",
        )
    ).strip()

    if not run_id:

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "run identifier missing."
        )

    client_order_id = (
        "f100live-paperparity-"
        + run_id
    )

    if (
        len(
            client_order_id
        )
        > candidate.MAX_CLIENT_ORDER_ID_LENGTH
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "client order ID too long."
        )

    return {
        "symbol":
            TEST_SYMBOL,

        "side":
            "buy",

        "notional_usd":
            TEST_NOTIONAL_USD,

        "client_order_id":
            client_order_id,

        "executable":
            True,
    }


# ============================================================
# PAPER-ONLY CANDIDATE PATCH
# ============================================================


@contextmanager
def paper_candidate_transport(
    counters: dict,
):

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "candidate transport source flag changed."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "candidate public execution source flag changed."
        )

    original_base_url = (
        candidate.LIVE_BASE_URL
    )

    original_host = (
        candidate.EXPECTED_LIVE_HOST
    )

    original_validator = (
        candidate.validate_live_url
    )

    original_transport_guard = (
        candidate.require_transport_released
    )

    original_public_guard = (
        candidate.require_public_execution_released
    )

    original_urlopen = (
        candidate.urlopen
    )

    def paper_only_urlopen(
        request,
        timeout=20,
    ):

        url = (
            request.full_url
        )

        parsed = (
            urlparse(
                url
            )
        )

        if (
            parsed.hostname
            != paper.EXPECTED_PAPER_HOST
        ):

            counters[
                "non_paper_host_requests"
            ] += 1

            raise RuntimeError(
                "PAPER PARITY SECURITY STOP: "
                "candidate attempted non-paper host."
            )

        paper.validate_paper_url(
            url
        )

        method = (
            request.get_method()
            .upper()
        )

        if method == "GET":

            counters[
                "candidate_get_requests"
            ] += 1

        elif method == "POST":

            counters[
                "candidate_post_requests"
            ] += 1

        else:

            raise RuntimeError(
                "PAPER PARITY SECURITY STOP: "
                f"candidate attempted {method}."
            )

        return original_urlopen(
            request,
            timeout=timeout,
        )

    # --------------------------------------------------------
    # Install the PAPER-only destination BEFORE guards are
    # bypassed.
    # --------------------------------------------------------

    candidate.LIVE_BASE_URL = (
        paper.PAPER_BASE_URL
    )

    candidate.EXPECTED_LIVE_HOST = (
        paper.EXPECTED_PAPER_HOST
    )

    candidate.validate_live_url = (
        paper.validate_paper_url
    )

    candidate.urlopen = (
        paper_only_urlopen
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

        candidate.validate_live_url = (
            original_validator
        )

        candidate.EXPECTED_LIVE_HOST = (
            original_host
        )

        candidate.LIVE_BASE_URL = (
            original_base_url
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "candidate transport source flag changed."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "candidate public execution source flag changed."
        )


# ============================================================
# PAPER ACCOUNT VALIDATION
# ============================================================


def validate_paper_account(
    account: dict,
):

    if not isinstance(
        account,
        dict,
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "invalid paper account response."
        )

    if (
        str(
            account.get(
                "status",
                "",
            )
        ).upper()
        != "ACTIVE"
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper account is not ACTIVE."
        )

    for field in [
        "account_blocked",
        "trading_blocked",
        "trade_suspended_by_user",
    ]:

        if (
            account.get(
                field
            )
            is True
        ):

            raise RuntimeError(
                "PAPER PARITY STOP: "
                f"paper account field {field!r} "
                "blocks trading."
            )

    try:

        buying_power = float(
            account.get(
                "buying_power",
                0.0,
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "invalid paper buying power."
        ) from exc

    if (
        buying_power
        < TEST_NOTIONAL_USD
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper buying power is below "
            "the synthetic test notional."
        )


def verify_market_closed(
    clock: dict,
):

    if not isinstance(
        clock,
        dict,
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "invalid paper clock."
        )

    if (
        clock.get(
            "is_open"
        )
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper market must be CLOSED "
            "for this no-fill transport test."
        )


# ============================================================
# ORDER-STATE HELPERS
# ============================================================


def normalized_status(
    order: dict,
) -> str:

    return str(
        order.get(
            "status",
            "",
        )
    ).strip().lower()


def zero_filled_quantity(
    order: dict,
) -> bool:

    try:

        return (
            abs(
                float(
                    order.get(
                        "filled_qty",
                        0.0,
                    )
                )
            )
            < 1e-12
        )

    except (
        TypeError,
        ValueError,
    ):

        return False


def is_safe_terminal_zero_fill(
    order: dict,
) -> bool:

    return (
        normalized_status(
            order
        )
        in SAFE_TERMINAL_STATUSES
        and
        zero_filled_quantity(
            order
        )
    )


def get_direct_order_for_index_item(
    *,
    item: dict,
    key: str,
    secret: str,
):

    order_id = str(
        item.get(
            "id",
            "",
        )
    ).strip()

    if order_id:

        return paper.get_order_by_id(
            order_id=
                order_id,

            key=
                key,

            secret=
                secret,
        )

    client_order_id = str(
        item.get(
            "client_order_id",
            "",
        )
    ).strip()

    if client_order_id:

        return paper.get_order_by_client_id(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )

    return None


def classify_open_order_snapshot(
    *,
    open_orders: list,
    key: str,
    secret: str,
):

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "invalid open-order response."
        )

    genuinely_open = []

    stale_terminal = []

    indeterminate = []

    for item in open_orders:

        if not isinstance(
            item,
            dict,
        ):

            indeterminate.append(
                item
            )

            continue

        direct = (
            get_direct_order_for_index_item(
                item=
                    item,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if not isinstance(
            direct,
            dict,
        ):

            indeterminate.append(
                item
            )

            continue

        status = (
            normalized_status(
                direct
            )
        )

        if (
            status
            in SAFE_TERMINAL_STATUSES
        ):

            # The list endpoint can temporarily lag the
            # direct order endpoint after cancellation.
            stale_terminal.append(
                item
            )

            continue

        genuinely_open.append(
            item
        )

    return {
        "genuinely_open":
            genuinely_open,

        "stale_terminal":
            stale_terminal,

        "indeterminate":
            indeterminate,
    }


def get_open_orders(
    *,
    key: str,
    secret: str,
):

    result = (
        paper.get_json(
            path="/v2/orders",
            key=key,
            secret=secret,
            params={
                "status":
                    "open",

                "limit":
                    100,
            },
        )
    )

    if not isinstance(
        result,
        list,
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "invalid open-order response."
        )

    return result


def verify_no_genuinely_open_orders_before_test(
    *,
    key: str,
    secret: str,
):

    open_orders = (
        get_open_orders(
            key=key,
            secret=secret,
        )
    )

    classified = (
        classify_open_order_snapshot(
            open_orders=
                open_orders,

            key=
                key,

            secret=
                secret,
        )
    )

    if (
        classified[
            "indeterminate"
        ]
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper open-order state is indeterminate."
        )

    if (
        classified[
            "genuinely_open"
        ]
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper account contains a genuinely "
            "open order before parity test."
        )

    return len(
        classified[
            "stale_terminal"
        ]
    )


# ============================================================
# CLEANUP
# ============================================================


def cleanup_test_order(
    *,
    client_order_id: str,
    order_id: str | None,
    key: str,
    secret: str,
):

    if not order_id:

        existing = (
            paper.get_order_by_client_id(
                client_order_id=
                    client_order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if existing is None:

            return {
                "order_found":
                    False,

                "cancel_requested":
                    False,

                "cancel_response_code":
                    None,

                "terminal_status":
                    "NOT_FOUND",

                "zero_fill":
                    True,

                "terminal_poll_count":
                    0,
            }

        order_id = str(
            existing.get(
                "id",
                "",
            )
        ).strip()

    if not order_id:

        raise RuntimeError(
            "PAPER PARITY CLEANUP STOP: "
            "paper order ID unavailable."
        )

    current = (
        paper.get_order_by_id(
            order_id=
                order_id,

            key=
                key,

            secret=
                secret,
        )
    )

    if not zero_filled_quantity(
        current
    ):

        raise RuntimeError(
            "PAPER PARITY CLEANUP STOP: "
            "synthetic paper order received a fill."
        )

    cancel_requested = False

    cancel_response_code = None

    if (
        normalized_status(
            current
        )
        not in SAFE_TERMINAL_STATUSES
    ):

        cancel_response_code = (
            paper.cancel_order(
                order_id=
                    order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        cancel_requested = True

    for poll_number in range(
        1,
        TERMINAL_POLL_ATTEMPTS + 1,
    ):

        current = (
            paper.get_order_by_id(
                order_id=
                    order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if not zero_filled_quantity(
            current
        ):

            raise RuntimeError(
                "PAPER PARITY CLEANUP STOP: "
                "synthetic paper order received a fill."
            )

        status = (
            normalized_status(
                current
            )
        )

        if (
            status
            in SAFE_TERMINAL_STATUSES
        ):

            return {
                "order_found":
                    True,

                "cancel_requested":
                    cancel_requested,

                "cancel_response_code":
                    cancel_response_code,

                "terminal_status":
                    status.upper(),

                "zero_fill":
                    True,

                "terminal_poll_count":
                    poll_number,
            }

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

    raise RuntimeError(
        "PAPER PARITY CLEANUP STOP: "
        "paper test order did not reach "
        "a terminal zero-fill state."
    )


def wait_for_test_order_absent_from_open_index(
    *,
    client_order_id: str,
    order_id: str,
    key: str,
    secret: str,
):

    stale_observations = 0

    for poll_number in range(
        1,
        OPEN_INDEX_POLL_ATTEMPTS + 1,
    ):

        open_orders = (
            get_open_orders(
                key=key,
                secret=secret,
            )
        )

        matching = [
            item
            for item
            in open_orders
            if (
                str(
                    item.get(
                        "client_order_id",
                        "",
                    )
                )
                == client_order_id
                or
                str(
                    item.get(
                        "id",
                        "",
                    )
                )
                == order_id
            )
        ]

        if not matching:

            return {
                "converged":
                    True,

                "poll_count":
                    poll_number,

                "stale_open_index_observations":
                    stale_observations,
            }

        direct = (
            paper.get_order_by_id(
                order_id=
                    order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if not zero_filled_quantity(
            direct
        ):

            raise RuntimeError(
                "PAPER PARITY CLEANUP STOP: "
                "synthetic paper order received a fill "
                "while waiting for open-order index "
                "convergence."
            )

        direct_status = (
            normalized_status(
                direct
            )
        )

        if (
            direct_status
            in SAFE_TERMINAL_STATUSES
        ):

            stale_observations += 1

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

    # --------------------------------------------------------
    # Final direct state check before failing.
    #
    # We do NOT silently accept a permanently stale open-order
    # index. Both views must converge for parity evidence.
    # --------------------------------------------------------

    direct = (
        paper.get_order_by_id(
            order_id=
                order_id,

            key=
                key,

            secret=
                secret,
        )
    )

    if not zero_filled_quantity(
        direct
    ):

        raise RuntimeError(
            "PAPER PARITY CLEANUP STOP: "
            "synthetic paper order received a fill."
        )

    raise RuntimeError(
        "PAPER PARITY CLEANUP STOP: "
        "direct order state is "
        f"{normalized_status(direct)!r} but "
        "the PAPER open-order index did not converge."
    )


def verify_no_genuinely_open_orders_after_test(
    *,
    key: str,
    secret: str,
):

    open_orders = (
        get_open_orders(
            key=key,
            secret=secret,
        )
    )

    classified = (
        classify_open_order_snapshot(
            open_orders=
                open_orders,

            key=
                key,

            secret=
                secret,
        )
    )

    if (
        classified[
            "indeterminate"
        ]
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "final paper open-order state "
            "is indeterminate."
        )

    if (
        classified[
            "genuinely_open"
        ]
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper account contains a genuinely "
            "open order after parity cleanup."
        )

    return len(
        classified[
            "stale_terminal"
        ]
    )


# ============================================================
# SAFE OUTPUT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    candidate_sha256: str,
    client_order_id: str,
    counters: dict,
    cleanup: dict,
    open_index: dict | None = None,
    precheck_stale_terminal_count: int = 0,
    final_stale_terminal_count: int = 0,
):

    if open_index is None:

        open_index = {
            "converged":
                True,

            "poll_count":
                1,

            "stale_open_index_observations":
                0,
        }

    body = {
        "schema":
            SCHEMA,

        "mode":
            "REAL_PAPER_TRANSPORT_PARITY",

        "source_release_lock_builder_version":
            EXPECTED_LOCK_BUILDER_VERSION,

        "source_release_lock_sha256":
            release_lock_sha256,

        "writer_candidate_source_sha256":
            candidate_sha256,

        "writer_candidate_version":
            candidate.WRITER_CANDIDATE_VERSION,

        "paper_endpoint_verified":
            True,

        "live_endpoint_contacted":
            False,

        "live_credentials_supplied":
            False,

        "paper_credentials_supplied":
            True,

        "paper_credentials_persisted":
            False,

        "candidate_transport_source_flag_false_before_after":
            True,

        "candidate_public_execution_source_flag_false_before_after":
            True,

        "candidate_destination_redirected_in_memory_only":
            True,

        "paper_market_required_closed":
            True,

        "paper_order_test_symbol":
            TEST_SYMBOL,

        "paper_test_notional_usd":
            TEST_NOTIONAL_USD,

        "client_order_id_sha256":
            hashlib.sha256(
                client_order_id.encode(
                    "utf-8"
                )
            ).hexdigest(),

        "first_submission_status":
            "SUBMITTED",

        "restart_status":
            "EXISTING_MATCHING_ORDER",

        "candidate_get_requests":
            counters[
                "candidate_get_requests"
            ],

        "candidate_post_requests":
            counters[
                "candidate_post_requests"
            ],

        "candidate_non_paper_host_requests":
            counters[
                "non_paper_host_requests"
            ],

        "duplicate_post_requests":
            0,

        "paper_order_cleanup_verified":
            True,

        "paper_order_terminal_status":
            cleanup[
                "terminal_status"
            ],

        "paper_order_zero_fill_verified":
            cleanup[
                "zero_fill"
            ],

        "paper_cancel_requested":
            cleanup.get(
                "cancel_requested",
                False,
            ),

        "paper_cancel_response_code":
            cleanup.get(
                "cancel_response_code"
            ),

        "terminal_state_poll_count":
            cleanup.get(
                "terminal_poll_count",
                0,
            ),

        "open_order_index_converged":
            open_index[
                "converged"
            ],

        "open_order_index_poll_count":
            open_index[
                "poll_count"
            ],

        "open_order_index_stale_observations":
            open_index[
                "stale_open_index_observations"
            ],

        "precheck_stale_terminal_entries_ignored":
            int(
                precheck_stale_terminal_count
            ),

        "final_stale_terminal_entries":
            int(
                final_stale_terminal_count
            ),

        "final_genuinely_open_orders":
            0,

        "paper_position_created":
            False,

        "synthetic_permit_persisted":
            False,

        "synthetic_executable_intent_persisted":
            False,

        "live_execution_authorized":
            False,

        "live_permit_issued":
            False,

        "live_max_execution_notional_usd":
            0.0,

        "live_writer_connected":
            False,

        "live_orders_submitted":
            0,

        "paper_connected_writer_parity_passed":
            True,
    }

    return {
        "paper_parity":
            body,

        "paper_parity_sha256":
            sha256_json(
                body
            ),
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 CONNECTED-WRITER "
        "PAPER PARITY v1.0"
    )

    print(
        "============================================"
    )

    print(
        "\nBroker environment: PAPER ONLY"
    )

    print(
        "LIVE credentials allowed: NO"
    )

    print(
        "LIVE endpoint allowed: NO"
    )

    print(
        "Synthetic PAPER notional: $1.00"
    )

    require_arm()

    reject_live_credentials()

    if (
        get_kill_switch_state()
        != "ENGAGED"
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "broker kill switch must remain ENGAGED."
        )

    (
        _lock_package,
        _lock_body,
        lock_hash,
        candidate_hash,
    ) = (
        verify_release_lock()
    )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
        or
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "candidate source release state changed."
        )

    key, secret = (
        paper.load_paper_credentials()
    )

    account = (
        paper.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    validate_paper_account(
        account
    )

    clock = (
        paper.get_json(
            path="/v2/clock",
            key=key,
            secret=secret,
        )
    )

    verify_market_closed(
        clock
    )

    precheck_stale_count = (
        verify_no_genuinely_open_orders_before_test(
            key=key,
            secret=secret,
        )
    )

    permit = (
        build_synthetic_permit()
    )

    intent = (
        build_test_intent()
    )

    client_order_id = (
        intent[
            "client_order_id"
        ]
    )

    counters = {
        "candidate_get_requests":
            0,

        "candidate_post_requests":
            0,

        "non_paper_host_requests":
            0,
    }

    order_id = None

    first_status = None

    restart_status = None

    cleanup = None

    open_index = None

    try:

        with paper_candidate_transport(
            counters
        ):

            first = (
                candidate.submit_authorized_order_batch(
                    intents=[
                        intent
                    ],

                    permit_package=
                        permit,

                    key=
                        key,

                    secret=
                        secret,
                )
            )

            first_order = (
                first[
                    "orders"
                ][
                    0
                ]
            )

            first_status = (
                first_order[
                    "status"
                ]
            )

            if (
                first_status
                != "SUBMITTED"
            ):

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "fresh candidate call was not SUBMITTED."
                )

            order_id = str(
                first_order[
                    "broker_order"
                ].get(
                    "id",
                    "",
                )
            ).strip()

            if not order_id:

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "paper broker order ID missing."
                )

            restart = (
                candidate.submit_authorized_order_batch(
                    intents=[
                        intent
                    ],

                    permit_package=
                        permit,

                    key=
                        key,

                    secret=
                        secret,
                )
            )

            restart_status = (
                restart[
                    "orders"
                ][
                    0
                ][
                    "status"
                ]
            )

            if (
                restart_status
                != "EXISTING_MATCHING_ORDER"
            ):

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "restart did not detect "
                    "existing matching order."
                )

            if (
                counters[
                    "candidate_post_requests"
                ]
                != 1
            ):

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "candidate performed unexpected "
                    "POST count."
                )

            if (
                counters[
                    "candidate_get_requests"
                ]
                != 2
            ):

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "candidate performed unexpected "
                    "GET count."
                )

            if (
                counters[
                    "non_paper_host_requests"
                ]
                != 0
            ):

                raise RuntimeError(
                    "PAPER PARITY STOP: "
                    "candidate attempted non-paper host."
                )

    finally:

        cleanup = (
            cleanup_test_order(
                client_order_id=
                    client_order_id,

                order_id=
                    order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

    if (
        first_status
        != "SUBMITTED"
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "fresh submission proof missing."
        )

    if (
        restart_status
        != "EXISTING_MATCHING_ORDER"
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "restart idempotency proof missing."
        )

    if (
        cleanup[
            "zero_fill"
        ]
        is not True
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper test was not zero-fill."
        )

    if (
        cleanup[
            "terminal_status"
        ].lower()
        not in SAFE_TERMINAL_STATUSES
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper test order did not finish terminal."
        )

    if not order_id:

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper broker order ID missing "
            "before open-index convergence."
        )

    open_index = (
        wait_for_test_order_absent_from_open_index(
            client_order_id=
                client_order_id,

            order_id=
                order_id,

            key=
                key,

            secret=
                secret,
        )
    )

    if (
        open_index[
            "converged"
        ]
        is not True
    ):

        raise RuntimeError(
            "PAPER PARITY STOP: "
            "paper open-order index did not converge."
        )

    final_stale_count = (
        verify_no_genuinely_open_orders_after_test(
            key=key,
            secret=secret,
        )
    )

    package = (
        build_safe_output(
            release_lock_sha256=
                lock_hash,

            candidate_sha256=
                candidate_hash,

            client_order_id=
                client_order_id,

            counters=
                counters,

            cleanup=
                cleanup,

            open_index=
                open_index,

            precheck_stale_terminal_count=
                precheck_stale_count,

            final_stale_terminal_count=
                final_stale_count,
        )
    )

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

    key = None
    secret = None
    permit = None
    intent = None

    print(
        "\nRelease lock v1.5: VERIFIED"
    )

    print(
        "Connected-writer candidate source: VERIFIED"
    )

    print(
        "Candidate transport source flag: FALSE"
    )

    print(
        "Candidate public-execution source flag: FALSE"
    )

    print(
        "PAPER market clock: CLOSED"
    )

    print(
        "Genuinely open PAPER orders before test: 0"
    )

    print(
        "Candidate destination: PAPER ONLY"
    )

    print(
        "Fresh candidate submission: PASS"
    )

    print(
        "Candidate POST requests: 1"
    )

    print(
        "Restart existing-order detection: PASS"
    )

    print(
        "Duplicate candidate POST requests: 0"
    )

    print(
        "Direct PAPER terminal-state cleanup: PASS"
    )

    print(
        "PAPER open-order index convergence: PASS"
    )

    print(
        "PAPER test order filled: NO"
    )

    print(
        "PAPER position created: NO"
    )

    print(
        "Genuinely open PAPER orders after test: 0"
    )

    print(
        "LIVE endpoint requests: 0"
    )

    print(
        "LIVE orders submitted: 0"
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 PAPER CONNECTED-WRITER "
        "PARITY COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Release lock v1.5: VERIFIED"
    )

    print(
        "Exact writer-candidate transport path: VERIFIED"
    )

    print(
        "Broker environment: PAPER ONLY"
    )

    print(
        "Paper candidate GET-before-POST: PASS"
    )

    print(
        "Paper candidate POST: PASS"
    )

    print(
        "Paper restart duplicate suppression: PASS"
    )

    print(
        "Paper direct-order cleanup / zero-fill: PASS"
    )

    print(
        "Paper open-order index convergence: PASS"
    )

    print(
        "Candidate transport released in source: FALSE"
    )

    print(
        "Candidate public execution enabled in source: FALSE"
    )

    print(
        "LIVE credentials supplied: NO"
    )

    print(
        "LIVE endpoint contacted: NO"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Live permit issued: FALSE"
    )

    print(
        "Maximum LIVE execution notional: $0.00"
    )

    print(
        "LIVE writer connected: FALSE"
    )

    print(
        "LIVE orders submitted: 0"
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
            "PAPER CONNECTED-WRITER PARITY: FAILED",
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

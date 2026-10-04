from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import fund100_alpaca_live_writer_candidate_v1_0 as prior


# ============================================================
# FUND-100 ALPACA LIVE WRITER CANDIDATE v1.1
# ============================================================
#
# REVIEW CANDIDATE ONLY.
#
# v1.1 adds explicit broker-order STATUS semantics.
#
# IMPORTANT:
#
#   TRANSPORT_RELEASED = False
#   PUBLIC_EXECUTION_ENABLED = False
#
# Both remain hard-coded constants.
#
# There is:
#
# - NO environment-variable activation
# - NO secret-based activation
# - NO main()
# - NO workflow execution path
# - NO scheduler
#
# v1.1 preserves:
#
# - exact frozen V5 execution universe
# - market-notional DAY order shape
# - GET-by-client-order-id before POST
# - hard transport guard as first executable call
# - hard public-execution guard as first executable call
#
# NEW STATUS RULE
# ===============
#
# A matching client_order_id is NOT sufficient by itself.
#
# Existing order status is explicitly classified:
#
# FILLED
#   -> recovered filled order
#   -> NEVER POST again
#
# ACTIVE / TRANSITIONAL / NO-RESUBMIT
#   -> recovered existing order
#   -> NEVER POST again
#
# TERMINAL FAILURE
#   canceled / expired / rejected
#   -> FAIL CLOSED
#   -> NEVER POST again under same client_order_id
#
# AMBIGUOUS / UNSAFE
#   replaced / pending_replace / suspended / held / unknown
#   -> FAIL CLOSED
#
# ============================================================


WRITER_CANDIDATE_VERSION = "1.1"


WRITER_CANDIDATE_SCHEMA = (
    "FUND100_ALPACA_LIVE_WRITER_CANDIDATE_V1_1"
)


# ============================================================
# HARD-CODED RELEASE STATE
# ============================================================


TRANSPORT_RELEASED = False

PUBLIC_EXECUTION_ENABLED = False


# ============================================================
# ALPACA LIVE ENDPOINTS
# ============================================================


LIVE_BASE_URL = (
    "https://api.alpaca.markets"
)


EXPECTED_LIVE_HOST = (
    "api.alpaca.markets"
)


LIVE_ORDER_PATH = (
    "/v2/orders"
)


LIVE_ORDER_BY_CLIENT_ID_PATH = (
    "/v2/orders:by_client_order_id"
)


# ============================================================
# REUSED CONTRACT
# ============================================================


REQUIRED_PERMIT_SCHEMA = (
    prior.REQUIRED_PERMIT_SCHEMA
)


ALLOWED_SYMBOLS = set(
    prior.ALLOWED_SYMBOLS
)


ALLOWED_SIDES = set(
    prior.ALLOWED_SIDES
)


MAX_CLIENT_ORDER_ID_LENGTH = (
    prior.MAX_CLIENT_ORDER_ID_LENGTH
)


MIN_NOTIONAL_USD = (
    prior.MIN_NOTIONAL_USD
)


validate_permit_package = (
    prior.validate_permit_package
)


validate_order_intent = (
    prior.validate_order_intent
)


validate_order_batch = (
    prior.validate_order_batch
)


validate_credentials = (
    prior.validate_credentials
)


validate_live_url = (
    prior.validate_live_url
)


sha256_json = (
    prior.sha256_json
)


money_decimal = (
    prior.money_decimal
)


money_string = (
    prior.money_string
)


build_order_payload = (
    prior.build_order_payload
)


# ============================================================
# STATUS SEMANTICS
# ============================================================


FILLED_STATUSES = {
    "filled",
}


NO_RESUBMIT_STATUSES = {
    "accepted",
    "pending_new",
    "accepted_for_bidding",
    "new",
    "partially_filled",
    "pending_cancel",
    "stopped",
    "done_for_day",
    "calculated",
}


TERMINAL_FAILURE_STATUSES = {
    "canceled",
    "expired",
    "rejected",
}


AMBIGUOUS_UNSAFE_STATUSES = {
    "replaced",
    "pending_replace",
    "suspended",
    "held",
}


DOCUMENTED_STATUS_COVERAGE = (
    FILLED_STATUSES
    | NO_RESUBMIT_STATUSES
    | TERMINAL_FAILURE_STATUSES
    | AMBIGUOUS_UNSAFE_STATUSES
)


# ============================================================
# EXCEPTIONS
# ============================================================


class LiveWriterCandidateLocked(
    RuntimeError
):
    pass


class ExistingOrderMismatch(
    RuntimeError
):
    pass


class ExistingOrderTerminalFailure(
    RuntimeError
):
    pass


class ExistingOrderUnsafeStatus(
    RuntimeError
):
    pass


class SubmittedOrderTerminalFailure(
    RuntimeError
):
    pass


class SubmittedOrderUnsafeStatus(
    RuntimeError
):
    pass


# ============================================================
# HARD RELEASE GUARDS
# ============================================================


def require_transport_released() -> None:

    if (
        TRANSPORT_RELEASED
        is not True
    ):

        raise LiveWriterCandidateLocked(
            "LIVE WRITER CANDIDATE LOCKED: "
            "network transport has not been released."
        )


def require_public_execution_released() -> None:

    require_transport_released()

    if (
        PUBLIC_EXECUTION_ENABLED
        is not True
    ):

        raise LiveWriterCandidateLocked(
            "LIVE WRITER CANDIDATE LOCKED: "
            "public execution has not been released."
        )


# ============================================================
# STATUS CLASSIFICATION
# ============================================================


def normalized_order_status(
    order: dict,
) -> str:

    if not isinstance(
        order,
        dict,
    ):

        raise ExistingOrderUnsafeStatus(
            "Broker order is not an object."
        )

    status = str(
        order.get(
            "status",
            "",
        )
    ).strip().lower()

    if not status:

        raise ExistingOrderUnsafeStatus(
            "Broker order status is missing."
        )

    return status


def classify_order_status(
    order: dict,
) -> str:

    status = (
        normalized_order_status(
            order
        )
    )

    if status in FILLED_STATUSES:

        return "FILLED"

    if status in NO_RESUBMIT_STATUSES:

        return "NO_RESUBMIT"

    if (
        status
        in TERMINAL_FAILURE_STATUSES
    ):

        return "TERMINAL_FAILURE"

    if (
        status
        in AMBIGUOUS_UNSAFE_STATUSES
    ):

        return "AMBIGUOUS_UNSAFE"

    return "UNKNOWN_UNSAFE"


# ============================================================
# STRUCTURAL EXISTING-ORDER VALIDATION
# ============================================================


def validate_existing_order_matches_intent(
    existing: dict,
    intent: dict,
):

    try:

        return (
            prior.validate_existing_order_matches_intent(
                existing=
                    existing,

                intent=
                    intent,
            )
        )

    except prior.ExistingOrderMismatch as exc:

        raise ExistingOrderMismatch(
            str(
                exc
            )
        ) from exc


def resolve_existing_order(
    existing: dict,
    intent: dict,
):

    validate_existing_order_matches_intent(
        existing=
            existing,

        intent=
            intent,
    )

    classification = (
        classify_order_status(
            existing
        )
    )

    status = (
        normalized_order_status(
            existing
        )
    )

    if classification == "FILLED":

        return (
            "EXISTING_FILLED_ORDER"
        )

    if classification == "NO_RESUBMIT":

        return (
            "EXISTING_NO_RESUBMIT_ORDER"
        )

    if classification == "TERMINAL_FAILURE":

        raise ExistingOrderTerminalFailure(
            "Existing matching broker order is in "
            f"terminal status {status!r}. "
            "Automatic resubmission under the same "
            "client_order_id is prohibited."
        )

    if (
        classification
        in {
            "AMBIGUOUS_UNSAFE",
            "UNKNOWN_UNSAFE",
        }
    ):

        raise ExistingOrderUnsafeStatus(
            "Existing matching broker order has "
            f"unsafe or ambiguous status {status!r}. "
            "Automatic resubmission is prohibited."
        )

    raise ExistingOrderUnsafeStatus(
        "Existing broker order reached "
        "an unclassified status path."
    )


# ============================================================
# SUBMITTED RESPONSE VALIDATION
# ============================================================


def validate_submitted_order_response(
    response: dict,
    intent: dict,
):

    response = (
        prior.validate_submitted_order_response(
            response=
                response,

            intent=
                intent,
        )
    )

    classification = (
        classify_order_status(
            response
        )
    )

    status = (
        normalized_order_status(
            response
        )
    )

    if classification == "TERMINAL_FAILURE":

        raise SubmittedOrderTerminalFailure(
            "Broker accepted the submission request but "
            "returned terminal order status "
            f"{status!r}. "
            "Execution must stop for reconciliation."
        )

    if (
        classification
        in {
            "AMBIGUOUS_UNSAFE",
            "UNKNOWN_UNSAFE",
        }
    ):

        raise SubmittedOrderUnsafeStatus(
            "Broker submission returned unsafe or "
            f"ambiguous status {status!r}. "
            "Execution must stop for reconciliation."
        )

    return response


# ============================================================
# HTTP GET — CLIENT ORDER ID IDEMPOTENCY
# ============================================================


def _get_order_by_client_id(
    client_order_id: str,
    key: str,
    secret: str,
):

    require_transport_released()

    validate_credentials(
        key,
        secret,
    )

    client_order_id = str(
        client_order_id
    ).strip()

    if not client_order_id:

        raise RuntimeError(
            "Client order ID is missing."
        )

    if (
        len(
            client_order_id
        )
        > MAX_CLIENT_ORDER_ID_LENGTH
    ):

        raise RuntimeError(
            "Client order ID exceeds maximum length."
        )

    if not client_order_id.startswith(
        "f100live-"
    ):

        raise RuntimeError(
            "Client order ID is outside "
            "the Fund-100 namespace."
        )

    url = (
        LIVE_BASE_URL
        + LIVE_ORDER_BY_CLIENT_ID_PATH
        + "?"
        + urlencode({
            "client_order_id":
                client_order_id,
        })
    )

    validate_live_url(
        url
    )

    request = Request(
        url=url,
        method="GET",
        headers={
            "Accept":
                "application/json",

            "APCA-API-KEY-ID":
                key,

            "APCA-API-SECRET-KEY":
                secret,

            "User-Agent":
                "Fund-100-Live-Writer-Candidate/1.1",
        },
    )

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            return json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    except HTTPError as exc:

        if exc.code == 404:

            return None

        request_id = (
            exc.headers.get(
                "X-Request-ID",
                "not-provided",
            )
            if exc.headers
            else "not-provided"
        )

        raise RuntimeError(
            "Alpaca LIVE order lookup failed. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca LIVE API unavailable "
            "during order lookup."
        ) from exc


# ============================================================
# HTTP POST — MARKET NOTIONAL ORDER
# ============================================================


def _post_live_market_order(
    intent: dict,
    key: str,
    secret: str,
):

    require_transport_released()

    validate_credentials(
        key,
        secret,
    )

    payload = (
        build_order_payload(
            {
                **intent,
                "executable":
                    True,
            }
        )
    )

    url = (
        LIVE_BASE_URL
        + LIVE_ORDER_PATH
    )

    validate_live_url(
        url
    )

    request = Request(
        url=url,
        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),
        method="POST",
        headers={
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",

            "APCA-API-KEY-ID":
                key,

            "APCA-API-SECRET-KEY":
                secret,

            "User-Agent":
                "Fund-100-Live-Writer-Candidate/1.1",
        },
    )

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            body = json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    except HTTPError as exc:

        request_id = (
            exc.headers.get(
                "X-Request-ID",
                "not-provided",
            )
            if exc.headers
            else "not-provided"
        )

        message = ""

        try:

            error_body = json.loads(
                exc.read().decode(
                    "utf-8"
                )
            )

            message = str(
                error_body.get(
                    "message",
                    "",
                )
            )

        except Exception:

            message = (
                "Broker error body unavailable."
            )

        raise RuntimeError(
            "Alpaca LIVE order rejected. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca LIVE API unavailable "
            "during order submission."
        ) from exc

    return (
        validate_submitted_order_response(
            response=
                body,

            intent={
                **intent,

                "symbol":
                    str(
                        intent[
                            "symbol"
                        ]
                    ).upper(),

                "side":
                    str(
                        intent[
                            "side"
                        ]
                    ).lower(),
            },
        )
    )


# ============================================================
# FUTURE PUBLIC EXECUTION INTERFACE
# ============================================================


def submit_authorized_order_batch(
    intents: list[dict],
    permit_package: dict,
    key: str,
    secret: str,
):

    require_public_execution_released()

    (
        permit,
        permit_cap,
    ) = (
        validate_permit_package(
            permit_package
        )
    )

    (
        validated,
        gross_notional,
    ) = (
        validate_order_batch(
            intents=
                intents,

            permit_cap=
                permit_cap,
        )
    )

    validate_credentials(
        key,
        secret,
    )

    results = []

    for item in validated:

        existing = (
            _get_order_by_client_id(
                client_order_id=
                    item[
                        "client_order_id"
                    ],

                key=
                    key,

                secret=
                    secret,
            )
        )

        if existing is not None:

            recovered_status = (
                resolve_existing_order(
                    existing=
                        existing,

                    intent={
                        **item,

                        "executable":
                            True,
                    },
                )
            )

            results.append({
                "client_order_id":
                    item[
                        "client_order_id"
                    ],

                "status":
                    recovered_status,

                "broker_order":
                    existing,
            })

            continue

        broker_order = (
            _post_live_market_order(
                intent={
                    **item,

                    "executable":
                        True,
                },

                key=
                    key,

                secret=
                    secret,
            )
        )

        results.append({
            "client_order_id":
                item[
                    "client_order_id"
                ],

            "status":
                "SUBMITTED",

            "broker_order":
                broker_order,
        })

    return {
        "writer_schema":
            WRITER_CANDIDATE_SCHEMA,

        "writer_version":
            WRITER_CANDIDATE_VERSION,

        "permit_schema":
            permit[
                "schema"
            ],

        "gross_notional_usd":
            gross_notional,

        "orders":
            results,
    }


# ============================================================
# DELIBERATELY NO main()
# ============================================================
#
# This candidate remains source-review only.
#
# A future connected release must be separately reviewed,
# rehearsed and hash-locked.
#
# ============================================================

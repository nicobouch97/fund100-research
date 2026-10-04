from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import fund100_alpaca_live_writer_disconnected_v1_1 as contract


# ============================================================
# FUND-100 ALPACA LIVE WRITER CANDIDATE v1.0
# ============================================================
#
# REVIEW CANDIDATE ONLY.
#
# This module contains the real Alpaca Trading API transport
# shape that a future connected writer release may use.
#
# HOWEVER:
#
#   TRANSPORT_RELEASED = False
#   PUBLIC_EXECUTION_ENABLED = False
#
# Both are hard-coded constants.
#
# There is:
#
# - NO environment-variable activation
# - NO secret-based activation
# - NO main()
# - NO workflow invocation
# - NO scheduler
#
# Every GET/POST transport function calls the hard release
# guard before:
#
# - credential validation
# - URL construction
# - Request construction
# - urlopen()
#
# Therefore this candidate cannot currently reach Alpaca.
#
# A future connected release must be created as a separate
# reviewed version. This file must never be silently activated
# by changing an environment variable.
#
# ============================================================


WRITER_CANDIDATE_VERSION = "1.0"

WRITER_CANDIDATE_SCHEMA = (
    "FUND100_ALPACA_LIVE_WRITER_CANDIDATE_V1"
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
# EXECUTION CONTRACT
# ============================================================


REQUIRED_PERMIT_SCHEMA = (
    contract.REQUIRED_PERMIT_SCHEMA
)

ALLOWED_SYMBOLS = set(
    contract.ALLOWED_SYMBOLS
)

ALLOWED_SIDES = set(
    contract.ALLOWED_SIDES
)

MAX_CLIENT_ORDER_ID_LENGTH = (
    contract.MAX_CLIENT_ORDER_ID_LENGTH
)

MIN_NOTIONAL_USD = (
    contract.MIN_NOTIONAL_USD
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


# ============================================================
# HARD RELEASE GUARDS
# ============================================================


def require_transport_released() -> None:

    # --------------------------------------------------------
    # THIS MUST REMAIN THE FIRST EXECUTABLE STEP IN EVERY
    # NETWORK TRANSPORT FUNCTION.
    #
    # v1.0 deliberately has no success path.
    # --------------------------------------------------------

    if (
        TRANSPORT_RELEASED
        is not True
    ):

        raise LiveWriterCandidateLocked(
            "LIVE WRITER CANDIDATE LOCKED: "
            "network transport has not been released."
        )


def require_public_execution_released() -> None:

    # --------------------------------------------------------
    # Transport release is prerequisite #1.
    # --------------------------------------------------------

    require_transport_released()

    # --------------------------------------------------------
    # Public execution release is prerequisite #2.
    #
    # Both constants are hard-coded FALSE in this candidate.
    # --------------------------------------------------------

    if (
        PUBLIC_EXECUTION_ENABLED
        is not True
    ):

        raise LiveWriterCandidateLocked(
            "LIVE WRITER CANDIDATE LOCKED: "
            "public execution has not been released."
        )


# ============================================================
# REUSED REVIEWED VALIDATION CONTRACT
# ============================================================


validate_permit_package = (
    contract.validate_permit_package
)

validate_order_intent = (
    contract.validate_order_intent
)

validate_order_batch = (
    contract.validate_order_batch
)

validate_credentials = (
    contract.validate_credentials
)

validate_live_url = (
    contract.validate_live_url
)

sha256_json = (
    contract.sha256_json
)


# ============================================================
# DECIMAL HELPERS
# ============================================================


def money_decimal(
    value,
    field_name: str,
) -> Decimal:

    try:

        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            f"{field_name}: invalid monetary value."
        ) from exc

    if not result.is_finite():

        raise RuntimeError(
            f"{field_name}: value must be finite."
        )

    if result <= 0:

        raise RuntimeError(
            f"{field_name}: value must be positive."
        )

    return result


def money_string(
    value,
) -> str:

    amount = (
        money_decimal(
            value,
            "notional_usd",
        )
    )

    rounded = (
        amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_DOWN,
        )
    )

    if rounded <= 0:

        raise RuntimeError(
            "Order notional rounds to zero."
        )

    return format(
        rounded,
        ".2f",
    )


# ============================================================
# ORDER PAYLOAD
# ============================================================


def build_order_payload(
    intent: dict,
):

    item = (
        validate_order_intent(
            intent
        )
    )

    payload = {
        "symbol":
            item[
                "symbol"
            ],

        "notional":
            money_string(
                item[
                    "notional_usd"
                ]
            ),

        "side":
            item[
                "side"
            ],

        "type":
            "market",

        "time_in_force":
            "day",

        "extended_hours":
            False,

        "client_order_id":
            item[
                "client_order_id"
            ],
    }

    if (
        "qty"
        in payload
    ):

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "notional order payload unexpectedly "
            "contains qty."
        )

    return payload


# ============================================================
# EXISTING-ORDER IDEMPOTENCY VALIDATION
# ============================================================


def validate_existing_order_matches_intent(
    existing: dict,
    intent: dict,
):

    if not isinstance(
        existing,
        dict,
    ):

        raise ExistingOrderMismatch(
            "Existing broker order is not an object."
        )

    expected = (
        build_order_payload(
            {
                **intent,
                "executable":
                    True,
            }
        )
    )

    existing_client_id = str(
        existing.get(
            "client_order_id",
            "",
        )
    ).strip()

    if (
        existing_client_id
        != expected[
            "client_order_id"
        ]
    ):

        raise ExistingOrderMismatch(
            "Existing order client_order_id mismatch."
        )

    existing_symbol = str(
        existing.get(
            "symbol",
            "",
        )
    ).upper()

    if (
        existing_symbol
        != expected[
            "symbol"
        ]
    ):

        raise ExistingOrderMismatch(
            "Existing order symbol mismatch."
        )

    existing_side = str(
        existing.get(
            "side",
            "",
        )
    ).lower()

    if (
        existing_side
        != expected[
            "side"
        ]
    ):

        raise ExistingOrderMismatch(
            "Existing order side mismatch."
        )

    existing_type = str(
        existing.get(
            "type",
            existing.get(
                "order_type",
                "",
            ),
        )
    ).lower()

    if existing_type != "market":

        raise ExistingOrderMismatch(
            "Existing order type mismatch."
        )

    existing_tif = str(
        existing.get(
            "time_in_force",
            "",
        )
    ).lower()

    if existing_tif != "day":

        raise ExistingOrderMismatch(
            "Existing order time_in_force mismatch."
        )

    existing_notional = (
        existing.get(
            "notional"
        )
    )

    if existing_notional is None:

        raise ExistingOrderMismatch(
            "Existing order does not contain "
            "the expected notional field."
        )

    expected_notional = (
        money_decimal(
            expected[
                "notional"
            ],
            "expected_notional",
        )
    )

    broker_notional = (
        money_decimal(
            existing_notional,
            "existing_notional",
        )
    )

    if (
        abs(
            broker_notional
            - expected_notional
        )
        > Decimal("0.01")
    ):

        raise ExistingOrderMismatch(
            "Existing order notional mismatch."
        )

    return existing


# ============================================================
# BROKER RESPONSE VALIDATION
# ============================================================


def validate_submitted_order_response(
    response: dict,
    intent: dict,
):

    if not isinstance(
        response,
        dict,
    ):

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "broker order response is not an object."
        )

    client_order_id = str(
        response.get(
            "client_order_id",
            "",
        )
    ).strip()

    if (
        client_order_id
        != intent[
            "client_order_id"
        ]
    ):

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "broker response client_order_id mismatch."
        )

    symbol = str(
        response.get(
            "symbol",
            "",
        )
    ).upper()

    if (
        symbol
        != intent[
            "symbol"
        ]
    ):

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "broker response symbol mismatch."
        )

    side = str(
        response.get(
            "side",
            "",
        )
    ).lower()

    if (
        side
        != intent[
            "side"
        ]
    ):

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "broker response side mismatch."
        )

    order_id = str(
        response.get(
            "id",
            "",
        )
    ).strip()

    if not order_id:

        raise RuntimeError(
            "LIVE WRITER SAFETY STOP: "
            "broker response has no order ID."
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

    # --------------------------------------------------------
    # MUST REMAIN FIRST EXECUTABLE STATEMENT.
    # --------------------------------------------------------

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
                "Fund-100-Live-Writer-Candidate/1.0",
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

    # --------------------------------------------------------
    # MUST REMAIN FIRST EXECUTABLE STATEMENT.
    #
    # TRANSPORT_RELEASED is hard-coded FALSE in v1.0.
    # --------------------------------------------------------

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
                "Fund-100-Live-Writer-Candidate/1.0",
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

            intent=
                {
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

    # --------------------------------------------------------
    # MUST REMAIN FIRST EXECUTABLE STATEMENT.
    #
    # This candidate has NO success path because:
    #
    #   TRANSPORT_RELEASED = False
    #   PUBLIC_EXECUTION_ENABLED = False
    #
    # --------------------------------------------------------

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

            validate_existing_order_matches_intent(
                existing=
                    existing,

                intent=
                    {
                        **item,
                        "executable":
                            True,
                    },
            )

            results.append({
                "client_order_id":
                    item[
                        "client_order_id"
                    ],

                "status":
                    "EXISTING_MATCHING_ORDER",

                "broker_order":
                    existing,
            })

            continue

        broker_order = (
            _post_live_market_order(
                intent=
                    {
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
# There is intentionally no command-line execution path.
#
# The file also intentionally contains no:
#
# - os.environ
# - GitHub secret handling
# - scheduler
# - workflow
#
# A future connected release must be separately reviewed and
# hash locked.
#
# ============================================================

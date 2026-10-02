from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


# ============================================================
# FUND-100 ALPACA LIVE WRITER — DISCONNECTED v1.0
# ============================================================
#
# IMPORTANT
# =========
#
# This module contains the shape of a future Alpaca LIVE
# order writer, but it is deliberately impossible to activate.
#
# There is:
#
#   - NO GitHub workflow
#   - NO scheduler
#   - NO activation secret
#   - NO executable main()
#
# And, critically:
#
#   require_adapter_connected()
#
# ALWAYS raises.
#
# Every live-network write function calls that guard before
# any HTTP request is constructed or sent.
#
# The currently committed permit is also schema V1 and
# permit_issued=FALSE. This adapter requires a future,
# not-yet-existing V2 permit.
#
# Therefore current Fund-100 state cannot reach a live POST.
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

PERMIT_PATH = Path(
    "live_dryrun_outputs/v5_002/"
    "live_execution_permit.json"
)

# ------------------------------------------------------------
# Deliberately incompatible with the current V1 deny-only
# permit artifact.
# ------------------------------------------------------------

REQUIRED_PERMIT_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)

ALLOWED_SYMBOLS = {
    "ACWI",
    "EEM",
    "XLE",
    "XLV",
}

ALLOWED_SIDES = {
    "buy",
    "sell",
}

MAX_CLIENT_ORDER_ID_LENGTH = 128

MIN_NOTIONAL_USD = 1.00

LIVE_WRITER_CONNECTED = False


# ============================================================
# EXCEPTIONS
# ============================================================

class LiveWriterDisconnected(
    RuntimeError
):
    pass


class LivePermitRejected(
    RuntimeError
):
    pass


class LiveIntentRejected(
    RuntimeError
):
    pass


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


# ============================================================
# HARD DISCONNECTION
# ============================================================

def require_adapter_connected() -> None:

    # --------------------------------------------------------
    # THIS IS THE PRIMARY HARD STOP.
    #
    # v1.0 intentionally has no possible success path.
    #
    # A future live-enabled version must be created as a
    # separate reviewed version rather than changing an
    # environment variable and accidentally activating this
    # file.
    # --------------------------------------------------------

    raise LiveWriterDisconnected(
        "LIVE WRITER DISCONNECTED: "
        "Fund-100 live writer v1.0 has no "
        "activation mechanism."
    )


# ============================================================
# ENDPOINT VALIDATION
# ============================================================

def validate_live_url(
    url: str,
) -> None:

    parsed = urlparse(
        url
    )

    if parsed.scheme != "https":

        raise RuntimeError(
            "LIVE SECURITY STOP: HTTPS required."
        )

    if parsed.hostname != EXPECTED_LIVE_HOST:

        raise RuntimeError(
            "LIVE SECURITY STOP: "
            "unexpected Alpaca hostname."
        )


# ============================================================
# PERMIT
# ============================================================

def load_permit_package():

    if not PERMIT_PATH.exists():

        raise LivePermitRejected(
            "Live execution permit artifact "
            "does not exist."
        )

    with PERMIT_PATH.open(
        "r"
    ) as f:

        package = json.load(
            f
        )

    return package


def validate_permit_package(
    package: dict,
):

    if not isinstance(
        package,
        dict,
    ):

        raise LivePermitRejected(
            "Invalid permit package."
        )

    if (
        "permit" not in package
        or
        "permit_sha256" not in package
    ):

        raise LivePermitRejected(
            "Permit package is incomplete."
        )

    permit = (
        package[
            "permit"
        ]
    )

    recorded_hash = str(
        package[
            "permit_sha256"
        ]
    )

    calculated_hash = (
        sha256_json(
            permit
        )
    )

    if recorded_hash != calculated_hash:

        raise LivePermitRejected(
            "Permit SHA256 verification failed."
        )

    schema = str(
        permit.get(
            "schema",
            "",
        )
    )

    # --------------------------------------------------------
    # Current V1 deny-only permits can NEVER satisfy this.
    # --------------------------------------------------------

    if schema != REQUIRED_PERMIT_SCHEMA:

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            f"required schema is "
            f"{REQUIRED_PERMIT_SCHEMA}, "
            f"received {schema!r}."
        )

    if not bool(
        permit.get(
            "permit_issued",
            False,
        )
    ):

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "permit_issued is FALSE."
        )

    if not bool(
        permit.get(
            "live_execution_authorized",
            False,
        )
    ):

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "live_execution_authorized is FALSE."
        )

    if not bool(
        permit.get(
            "network_write_capability",
            False,
        )
    ):

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "network_write_capability is FALSE."
        )

    if (
        str(
            permit.get(
                "broker_write_mode",
                "",
            )
        ).upper()
        != "ENABLED"
    ):

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "broker_write_mode is not ENABLED."
        )

    if not bool(
        permit.get(
            "genuine_scheduled_event",
            False,
        )
    ):

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "permit is not for a genuine "
            "scheduled strategy event."
        )

    cap = float(
        permit.get(
            "max_live_execution_notional_usd",
            0.0,
        )
    )

    if cap <= 0:

        raise LivePermitRejected(
            "LIVE PERMIT REJECTED: "
            "monetary ceiling is not positive."
        )

    return (
        permit,
        cap,
    )


# ============================================================
# ORDER INTENT VALIDATION
# ============================================================

def validate_order_intent(
    intent: dict,
):

    if not isinstance(
        intent,
        dict,
    ):

        raise LiveIntentRejected(
            "Order intent must be an object."
        )

    symbol = str(
        intent.get(
            "symbol",
            "",
        )
    ).upper()

    if symbol not in ALLOWED_SYMBOLS:

        raise LiveIntentRejected(
            f"Unsupported live symbol: {symbol!r}."
        )

    side = str(
        intent.get(
            "side",
            "",
        )
    ).lower()

    if side not in ALLOWED_SIDES:

        raise LiveIntentRejected(
            f"Unsupported live side: {side!r}."
        )

    try:

        notional = float(
            intent.get(
                "notional_usd"
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise LiveIntentRejected(
            f"{symbol}: invalid live notional."
        ) from exc

    if notional < MIN_NOTIONAL_USD:

        raise LiveIntentRejected(
            f"{symbol}: live notional is below "
            f"${MIN_NOTIONAL_USD:.2f}."
        )

    client_order_id = str(
        intent.get(
            "client_order_id",
            "",
        )
    ).strip()

    if not client_order_id:

        raise LiveIntentRejected(
            f"{symbol}: client_order_id missing."
        )

    if len(
        client_order_id
    ) > MAX_CLIENT_ORDER_ID_LENGTH:

        raise LiveIntentRejected(
            f"{symbol}: client_order_id exceeds "
            f"{MAX_CLIENT_ORDER_ID_LENGTH} characters."
        )

    if not client_order_id.startswith(
        "f100live-"
    ):

        raise LiveIntentRejected(
            f"{symbol}: client_order_id does not "
            "belong to Fund-100 live namespace."
        )

    executable = bool(
        intent.get(
            "executable",
            False,
        )
    )

    if not executable:

        raise LiveIntentRejected(
            f"{symbol}: intent is marked "
            "non-executable."
        )

    return {
        "symbol":
            symbol,

        "side":
            side,

        "notional_usd":
            notional,

        "client_order_id":
            client_order_id,
    }


# ============================================================
# BATCH VALIDATION
# ============================================================

def validate_order_batch(
    intents: list[dict],
    permit_cap: float,
):

    if not isinstance(
        intents,
        list,
    ):

        raise LiveIntentRejected(
            "Live intents must be a list."
        )

    if len(
        intents
    ) == 0:

        raise LiveIntentRejected(
            "No live order intents supplied."
        )

    validated = []

    seen_client_ids = set()

    gross_notional = 0.0

    for intent in intents:

        item = (
            validate_order_intent(
                intent
            )
        )

        cid = (
            item[
                "client_order_id"
            ]
        )

        if cid in seen_client_ids:

            raise LiveIntentRejected(
                "Duplicate client_order_id "
                "inside live batch."
            )

        seen_client_ids.add(
            cid
        )

        gross_notional += (
            item[
                "notional_usd"
            ]
        )

        validated.append(
            item
        )

    if gross_notional > permit_cap + 1e-9:

        raise LiveIntentRejected(
            "LIVE SAFETY STOP: "
            "aggregate proposed order notional "
            "exceeds the execution permit ceiling."
        )

    return (
        validated,
        gross_notional,
    )


# ============================================================
# CREDENTIAL VALIDATION
# ============================================================

def validate_credentials(
    key: str,
    secret: str,
):

    if not str(
        key
    ).strip():

        raise RuntimeError(
            "Live API key is missing."
        )

    if not str(
        secret
    ).strip():

        raise RuntimeError(
            "Live API secret is missing."
        )


# ============================================================
# HTTP GET — FUTURE IDEMPOTENCY SUPPORT
# ============================================================

def _get_order_by_client_id(
    client_order_id: str,
    key: str,
    secret: str,
):

    # --------------------------------------------------------
    # Even GET is blocked here because the entire writer
    # adapter is disconnected. Current live read-only modules
    # already perform account inspection separately.
    # --------------------------------------------------------

    require_adapter_connected()

    validate_credentials(
        key,
        secret,
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
                "Fund-100-Live-Writer/1.0",
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

        raise

    except URLError as exc:

        raise RuntimeError(
            "Alpaca LIVE API unavailable."
        ) from exc


# ============================================================
# HTTP POST — STRUCTURALLY UNREACHABLE IN v1.0
# ============================================================

def _post_live_market_order(
    intent: dict,
    key: str,
    secret: str,
):

    # --------------------------------------------------------
    # CRITICAL:
    #
    # This executes BEFORE credentials, URL construction,
    # Request creation, or urlopen().
    #
    # v1.0 therefore cannot send a live POST.
    # --------------------------------------------------------

    require_adapter_connected()

    validate_credentials(
        key,
        secret,
    )

    item = (
        validate_order_intent(
            intent
        )
    )

    url = (
        LIVE_BASE_URL
        + LIVE_ORDER_PATH
    )

    validate_live_url(
        url
    )

    payload = {
        "symbol":
            item[
                "symbol"
            ],

        "notional":
            f"{item['notional_usd']:.2f}",

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
                "Fund-100-Live-Writer/1.0",
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

        request_id = (
            exc.headers.get(
                "X-Request-ID",
                "not-provided",
            )
        )

        message = ""

        try:

            body = json.loads(
                exc.read().decode(
                    "utf-8"
                )
            )

            message = str(
                body.get(
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
            "Alpaca LIVE API unavailable."
        ) from exc


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
    # FIRST INSTRUCTION:
    #
    # Hard-disconnect before permit parsing, credentials,
    # broker lookup, or HTTP.
    # --------------------------------------------------------

    require_adapter_connected()

    permit, permit_cap = (
        validate_permit_package(
            permit_package
        )
    )

    validated, gross_notional = (
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

            results.append({
                "client_order_id":
                    item[
                        "client_order_id"
                    ],

                "status":
                    "EXISTING_ORDER",

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
# Running:
#
#     python fund100_alpaca_live_writer_disconnected.py
#
# only loads function definitions and exits.
#
# Nothing calls Alpaca.
# Nothing reads live credentials.
# Nothing submits an order.
# ============================================================

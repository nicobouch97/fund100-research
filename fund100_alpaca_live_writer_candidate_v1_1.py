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


# ============================================================
# V6-S1 — APPENDED ORIGINAL ACWI FRACTIONAL-QTY SELL, HARD LOCKED
# ============================================================
# Existing V5 writer functions above are UNCHANGED. This is the ONLY
# existing reviewed broker writer boundary allowed to hold new POST code.
# New V6 release switches are never environment-controllable.
# No GitHub workflow carries LIVE credentials to this new function.
# ============================================================

V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED = False
V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED = False
V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED = False
V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED = False


def require_v6_s1_acwi_live_release() -> None:
    """The FIRST executable call in the V6 LIVE adapter."""
    require_public_execution_released()  # original V5 hard locks
    if (V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED is not True
        or V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED is not True
        or V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED is not True
        or V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED is not True):
        raise LiveWriterCandidateLocked(
            "V6-S1 first ACWI quantity SELL writer: release locks ENGAGED")


def submit_v6_s1_original_acwi_fractional_sell(*,
                                               original_qty: str,
                                               signed_sources: dict,
                                               owner_sources: dict,
                                               public_release_read_token: str,
                                               key: str,
                                               secret: str,
                                               transport=None,
                                               release_transport=None) -> dict:
    """One reviewed-shape Alpaca POST, completely LOCKED in production.

    Verify a signed unique-claim owner before the signed possible-POST
    boundary, but neither signed input grants order authority. An independently
    authenticated, provider-immutable release with the exact PUBLIC commitment
    to that HMAC-signed owner and seq2 must also be checked here, at the LAST
    POST boundary. Fresh actual order-time broker risk and independently
    authenticated current private HEAD remain separate unreleased prerequisites.
    Dummy fake transports are used ONLY in credentialless offline tests.
    """
    require_v6_s1_acwi_live_release()  # MUST remain the FIRST action.
    # Avoid trusting a user-supplied approved flag/receipt status.
    import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as v6
    if (type(signed_sources) is not dict
        or set(signed_sources)!={
            "reserved_source","prepost_source","genesis_comment",
            "first_comment","prepost_comment","first_comment_id",
            "first_run_id","prepost_comment_id","prepost_run_id",
            "original_qty","key"}
        or signed_sources.get("original_qty")!=original_qty):
        raise LiveWriterCandidateLocked(
            "V6-S1 LIVE writer requires complete original signed private evidence")
    required_owner={
        "current_fence_source","reserved_source","genesis_comment",
        "first_comment","first_comment_id","first_run_id",
        "original_qty","key","owner_run_id","owner_attempt",
        "owner_nonce","current_main_sha","source_broker_run_id",
    }
    if (type(owner_sources) is not dict or set(owner_sources)!=required_owner
        or owner_sources.get("original_qty")!=original_qty
        or type(owner_sources.get("owner_attempt")) is not int
        or owner_sources.get("owner_attempt")!=1
        or any(owner_sources.get(name)!=signed_sources.get(name)
               for name in ("reserved_source","genesis_comment",
                            "first_comment","first_comment_id",
                            "first_run_id","original_qty","key"))):
        raise LiveWriterCandidateLocked(
            "V6-S1 HMAC signed owner/pre-POST evidence missing or divergent")
    try:
        owner=v6.owner_fence.verify_claimed_owner(**owner_sources)
        review=v6.check_prepost_sources(**signed_sources)
        payload=v6.build_exact_sell_payload(original_qty=original_qty)
    except Exception:
        raise LiveWriterCandidateLocked(
            "V6-S1 HMAC owner/pre-POST or original qty payload not authenticated") from None
    if (owner.get("stage")!=
            "OFFLINE_SIGNED_OWNER_MATCHES_ORIGINAL_ACWI_NO_ORDER_RELEASE"
        or owner.get("unique_original_workflow_owner_HMAC_recognized") is not True
        or owner.get("source_signed_reserved_and_prepost_HEADs_bound") is not True
        or owner.get("claimed_fence_signed_current_head_verified") is not True
        or owner.get("claimed_fence_head_immutable_outside_GitHub") is not False
        or owner.get("LIVE_order_released") is not False
        or owner.get("restarted_same_owner_can_submit") is not False
        or owner.get("different_owner_can_submit") is not False
        or owner.get("real_broker_POSTs")!=0):
        raise LiveWriterCandidateLocked(
            "V6 original ACWI HMAC owner claim is invalid or incorrectly released")
    if (review.get("stage")!=
            "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
        or review.get("signed_private_sequence")!=2
        or review.get("stable_original_client_order_id")!=payload["client_order_id"]
        or review.get("canonical_original_fractional_qty")!=payload["qty"]
        or review.get("live_order_authorized") is not False):
        raise LiveWriterCandidateLocked(
            "V6 signed seq2/ACWI original order proof inconsistent")
    # An independently verified provider-immutable public HEAD is mandatory
    # INSIDE the last reviewed broker writer, not a caller-supplied boolean.
    # This makes a future accidental enablement of V6 external watermark
    # flags insufficient to send an order. It does NOT itself establish fresh
    # LIVE risk, a non-rollbackable HMAC HEAD read, or any order permission.
    try:
        import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
        expected_asset=anchor.original_signed_anchor_asset(
            signed_owner_sources=owner_sources,
            prepost_source=signed_sources["prepost_source"])
        anchored=anchor.verify_published_immutable_anchor(
            expected_asset=expected_asset,
            public_read_token=public_release_read_token,
            transport=release_transport)
    except Exception:
        raise LiveWriterCandidateLocked(
            "Original ACWI immutable HMAC owner/seq2 anchor not authenticated") from None
    if (anchored.get("status")!=
            "GITHUB_PROVIDER_IMMUTABLE_ACWI_HEAD_MATCHES_ORIGINAL_SIGNED_SEQ2"
        or anchored.get("provider_immutable_release_and_exact_asset_verified") is not True
        or anchored.get("anchor_outside_github_proven") is not False
        or anchored.get("first_live_broker_order_authorized") is not False
        or anchored.get("public_release_creations")!=0
        or anchored.get("private_git_puts")!=0
        or anchored.get("live_broker_posts")!=0):
        raise LiveWriterCandidateLocked(
            "Original ACWI independently checked immutable release HEAD invalid")
    # Last-mile risk MUST be obtained by the broker-keyed same-process
    # seven-GET reader, never from a caller-supplied boolean or prior job
    # report. The existing original reader still requires an operator STOP
    # and hence CANNOT authorize a funded order. A separately reviewed risk
    # policy will have to implement and release a new active-order contract.
    try:
        import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as risk
        order_time=risk.inspect_actual_original_seven_get(
            original_qty=original_qty,key=key,secret=secret)
    except Exception:
        raise LiveWriterCandidateLocked(
            "Original ACWI actual broker order-time seven-GET risk unavailable") from None
    if (order_time.get("status")!=
            "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
        or order_time.get("same_process_real_broker_gets")!=7
        or order_time.get("original_acwi_exact_fractional_holdings_verified") is not True
        or order_time.get("original_open_market_and_no_pending_order_verified") is not True
        or order_time.get("original_strict_postfunding_6_20_35_risk_pass") is not True
        or order_time.get("broker_order_authorized") is not True
        or order_time.get("broker_post_attempts")!=0):
        raise LiveWriterCandidateLocked(
            "Original order-time broker risk remains STOPPED; no LIVE POST")
    # IMPORTANT: the original V1 reader only returns STILL_STOPPED and
    # broker_order_authorized=False. Live POST is therefore impossible until
    # a separately reviewed, source-authenticated active risk V2 exists.
    validate_credentials(key,secret)
    url=LIVE_BASE_URL+LIVE_ORDER_PATH
    validate_live_url(url)
    if url!="https://api.alpaca.markets/v2/orders":
        raise LiveWriterCandidateLocked("V6 broker endpoint changed")
    request=Request(
        url=url,
        data=json.dumps(
            payload,sort_keys=True,separators=(",",":")
        ).encode("ascii"),
        method="POST",
        headers={
            "Accept":"application/json",
            "Content-Type":"application/json",
            "APCA-API-KEY-ID":key,
            "APCA-API-SECRET-KEY":secret,
            "User-Agent":"fund100-v6-s1-original-acwi-locked-first-attempt",
        },
    )
    # ONE and only one POST request; uncertain results MUST NOT be retried.
    sender=urlopen if transport is None else transport
    try:
        with sender(request,timeout=12) as response:
            if getattr(response,"status",None) not in (200,201):
                raise LiveWriterCandidateLocked("Broker POST not confirmed, no retry")
            body=response.read(v6.RESPONSE_MAX_BYTES+1)
        if len(body)>v6.RESPONSE_MAX_BYTES:
            raise LiveWriterCandidateLocked("Broker response oversized, no retry")
        receipt=json.loads(body.decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise LiveWriterCandidateLocked(
            "V6 broker POST uncertain or rejected; NEVER retry") from None
    try:
        return v6._validate_receipt(receipt,original_qty=original_qty)
    except Exception:
        raise LiveWriterCandidateLocked(
            "Broker response invalid/terminal/ambiguous; HOLD never retry") from None

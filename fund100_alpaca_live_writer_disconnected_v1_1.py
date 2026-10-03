from __future__ import annotations

import fund100_alpaca_live_writer_disconnected as base


# ============================================================
# FUND-100 ALPACA LIVE WRITER — DISCONNECTED v1.1
# ============================================================
#
# This is still a HARD-DISCONNECTED writer.
#
# v1.1 changes only the execution-universe contract:
#
#   - ACWI benchmark core
#   - complete frozen V5 satellite universe
#
# It does NOT activate broker writes.
#
# There is still no successful path through
# require_adapter_connected().
#
# ============================================================


WRITER_VERSION = "1.1"


# ============================================================
# FROZEN V5 EXECUTION UNIVERSE
# ============================================================


FROZEN_V5_SATELLITE_UNIVERSE = {
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
    "XLK",
    "XLF",
    "XLI",
    "XLV",
    "XLP",
    "XLY",
    "XLE",
    "XLU",
}


BENCHMARK_CORE_SYMBOL = "ACWI"


ALLOWED_SYMBOLS = (
    FROZEN_V5_SATELLITE_UNIVERSE
    | {
        BENCHMARK_CORE_SYMBOL,
    }
)


ALLOWED_SIDES = set(
    base.ALLOWED_SIDES
)


REQUIRED_PERMIT_SCHEMA = (
    base.REQUIRED_PERMIT_SCHEMA
)

MAX_CLIENT_ORDER_ID_LENGTH = (
    base.MAX_CLIENT_ORDER_ID_LENGTH
)

MIN_NOTIONAL_USD = (
    base.MIN_NOTIONAL_USD
)

LIVE_WRITER_CONNECTED = False


# ============================================================
# EXISTING TYPES / HASHING
# ============================================================


LiveWriterDisconnected = (
    base.LiveWriterDisconnected
)

LivePermitRejected = (
    base.LivePermitRejected
)

LiveIntentRejected = (
    base.LiveIntentRejected
)


canonical_json = (
    base.canonical_json
)

sha256_json = (
    base.sha256_json
)


# ============================================================
# ENDPOINT CONSTANTS
# ============================================================


LIVE_BASE_URL = (
    base.LIVE_BASE_URL
)

EXPECTED_LIVE_HOST = (
    base.EXPECTED_LIVE_HOST
)

LIVE_ORDER_PATH = (
    base.LIVE_ORDER_PATH
)

LIVE_ORDER_BY_CLIENT_ID_PATH = (
    base.LIVE_ORDER_BY_CLIENT_ID_PATH
)

PERMIT_PATH = (
    base.PERMIT_PATH
)


# ============================================================
# HARD DISCONNECT
# ============================================================


def require_adapter_connected() -> None:

    # --------------------------------------------------------
    # CRITICAL:
    #
    # This deliberately delegates to the original hard-stop
    # implementation, which has no success path.
    # --------------------------------------------------------

    base.require_adapter_connected()


# ============================================================
# UNIVERSE CONTRACT
# ============================================================


def validate_frozen_v5_execution_universe(
    research_symbols,
) -> None:

    research_set = {
        str(
            symbol
        ).upper()
        for symbol
        in research_symbols
    }

    expected = (
        research_set
        | {
            BENCHMARK_CORE_SYMBOL,
        }
    )

    if (
        research_set
        != FROZEN_V5_SATELLITE_UNIVERSE
    ):

        raise RuntimeError(
            "LIVE UNIVERSE STOP: "
            "research satellite universe does not match "
            "the frozen V5 execution contract."
        )

    if (
        ALLOWED_SYMBOLS
        != expected
    ):

        raise RuntimeError(
            "LIVE UNIVERSE STOP: "
            "writer execution universe does not exactly "
            "match benchmark core plus frozen research universe."
        )


# ============================================================
# PERMIT VALIDATION
# ============================================================


load_permit_package = (
    base.load_permit_package
)


validate_permit_package = (
    base.validate_permit_package
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

    if (
        notional
        < MIN_NOTIONAL_USD
    ):

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
# ORDER BATCH VALIDATION
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

        client_id = (
            item[
                "client_order_id"
            ]
        )

        if client_id in seen_client_ids:

            raise LiveIntentRejected(
                "Duplicate client_order_id "
                "inside live batch."
            )

        seen_client_ids.add(
            client_id
        )

        gross_notional += (
            item[
                "notional_usd"
            ]
        )

        validated.append(
            item
        )

    if (
        gross_notional
        > float(
            permit_cap
        )
        + 1e-9
    ):

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
# CREDENTIAL / URL VALIDATION
# ============================================================


validate_credentials = (
    base.validate_credentials
)

validate_live_url = (
    base.validate_live_url
)


# ============================================================
# DISCONNECTED NETWORK METHODS
# ============================================================
#
# These retain the v1.0 implementations.
#
# Both hit the unconditional base disconnect guard before any
# network operation.
# ============================================================


_get_order_by_client_id = (
    base._get_order_by_client_id
)

_post_live_market_order = (
    base._post_live_market_order
)


# ============================================================
# DISCONNECTED BATCH ENTRYPOINT
# ============================================================


def submit_authorized_order_batch(
    *args,
    **kwargs,
):

    # --------------------------------------------------------
    # MUST remain the first executable statement.
    #
    # v1.1 intentionally provides no route beyond this point.
    # --------------------------------------------------------

    require_adapter_connected()


# ============================================================
# NO main()
# ============================================================
#
# This file intentionally has no command-line execution path
# and no workflow that can submit orders.
# ============================================================

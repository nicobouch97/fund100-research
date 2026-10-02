from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import fund100_alpaca_paper_reconcile as reconcile


# ============================================================
# FUND-100 ALPACA PAPER BOOTSTRAP EXECUTOR v1.0
# ============================================================
#
# THIS FILE CAN SUBMIT ORDERS.
#
# SAFETY DESIGN:
#
# - ALPACA PAPER ENDPOINT ONLY
# - $100 TEST SLEEVE ONLY
# - V5-002 BASELINE TARGET ONLY
# - MARKET ORDERS / DAY ONLY
# - FRACTIONAL NOTIONAL ORDERS
# - REGULAR MARKET MUST BE OPEN
# - DETERMINISTIC CLIENT ORDER IDs
# - DUPLICATE ORDER PROTECTION
# - FOREIGN ORDERS/POSITIONS CAUSE HARD STOP
# - NO CANCELLATION CODE
# - NO LIVE ENDPOINT CODE
#
# ============================================================


PAPER_BASE_URL = (
    "https://paper-api.alpaca.markets"
)

EXPECTED_HOST = (
    "paper-api.alpaca.markets"
)

EXPECTED_STATE_DATE = (
    "2026-10-01"
)

EXECUTION_ENABLE_VALUE = (
    "YES_PAPER_ONLY"
)

CLIENT_ID_PREFIX = (
    "f100-v5002-bootstrap-20261001"
)

TIMEOUT_SECONDS = 20


# ============================================================
# SAFETY ARM
# ============================================================

def require_paper_execution_arm():

    value = os.environ.get(
        "FUND100_ENABLE_PAPER_ORDERS",
        "",
    ).strip()

    if value != EXECUTION_ENABLE_VALUE:

        raise RuntimeError(
            "Paper order execution is not armed. "
            "FUND100_ENABLE_PAPER_ORDERS does not "
            "contain the required paper-only value."
        )


# ============================================================
# PAPER URL CHECK
# ============================================================

def validate_paper_url(
    url: str,
):

    parsed = urlparse(
        url
    )

    if parsed.scheme != "https":

        raise RuntimeError(
            "SECURITY STOP: non-HTTPS broker URL."
        )

    if parsed.hostname != EXPECTED_HOST:

        raise RuntimeError(
            "SECURITY STOP: attempted non-paper "
            "broker endpoint."
        )


# ============================================================
# FIND ORDER BY CLIENT ID
# ============================================================

def get_order_by_client_id(
    client_order_id: str,
    key: str,
    secret: str,
):

    params = urlencode({
        "client_order_id":
            client_order_id,
    })

    url = (
        PAPER_BASE_URL
        + "/v2/orders:by_client_order_id?"
        + params
    )

    validate_paper_url(
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
                "Fund-100-Paper-Executor/1.0",
        },
    )

    try:

        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            body = (
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

            return json.loads(
                body
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
            "Alpaca lookup failed. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Could not reach Alpaca paper API: "
            f"{exc.reason}"
        ) from exc


# ============================================================
# SUBMIT ONE PAPER ORDER
# ============================================================

def submit_paper_order(
    symbol: str,
    notional_usd: float,
    client_order_id: str,
    key: str,
    secret: str,
):

    url = (
        PAPER_BASE_URL
        + "/v2/orders"
    )

    validate_paper_url(
        url
    )

    payload = {
        "symbol":
            symbol,

        "notional":
            f"{notional_usd:.2f}",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "extended_hours":
            False,

        "client_order_id":
            client_order_id,
    }

    body = json.dumps(
        payload
    ).encode(
        "utf-8"
    )

    request = Request(
        url=url,
        data=body,
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
                "Fund-100-Paper-Executor/1.0",
        },
    )

    try:

        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            status = int(
                response.status
            )

            response_body = (
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

        safe_message = ""

        try:

            error_body = (
                exc.read()
                .decode(
                    "utf-8"
                )
            )

            error_json = json.loads(
                error_body
            )

            safe_message = str(
                error_json.get(
                    "message",
                    "",
                )
            )

        except Exception:

            safe_message = (
                "Broker error body unavailable."
            )

        raise RuntimeError(
            f"{symbol}: Alpaca rejected paper order. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={safe_message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            f"{symbol}: could not reach "
            "Alpaca paper API."
        ) from exc

    if (
        status < 200
        or status >= 300
    ):

        raise RuntimeError(
            f"{symbol}: unexpected HTTP "
            f"status {status}."
        )

    try:

        result = json.loads(
            response_body
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"{symbol}: Alpaca returned "
            "invalid order JSON."
        ) from exc

    return result


# ============================================================
# ORDER VALIDATION
# ============================================================

def validate_broker_order(
    order: dict,
    symbol: str,
    client_order_id: str,
):

    if not isinstance(
        order,
        dict,
    ):

        raise RuntimeError(
            f"{symbol}: invalid broker order."
        )

    if (
        str(
            order.get(
                "symbol",
                "",
            )
        ).upper()
        != symbol
    ):

        raise RuntimeError(
            f"{symbol}: broker order symbol mismatch."
        )

    if (
        order.get(
            "client_order_id"
        )
        != client_order_id
    ):

        raise RuntimeError(
            f"{symbol}: client-order-ID mismatch."
        )

    if (
        str(
            order.get(
                "side",
                "",
            )
        ).lower()
        != "buy"
    ):

        raise RuntimeError(
            f"{symbol}: unexpected order side."
        )

    order_type = str(
        order.get(
            "type",
            order.get(
                "order_type",
                "",
            ),
        )
    ).lower()

    if order_type != "market":

        raise RuntimeError(
            f"{symbol}: unexpected order type."
        )

    if (
        str(
            order.get(
                "time_in_force",
                "",
            )
        ).lower()
        != "day"
    ):

        raise RuntimeError(
            f"{symbol}: unexpected time in force."
        )


# ============================================================
# EXISTING BROKER ACTIVITY CHECK
# ============================================================

def validate_existing_activity(
    positions,
    open_orders,
    expected_client_ids: dict,
    existing_expected_orders: dict,
):

    target_symbols = set(
        expected_client_ids.keys()
    )

    expected_ids = set(
        expected_client_ids.values()
    )

    # --------------------------------------------------------
    # OPEN ORDERS
    # --------------------------------------------------------

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid Alpaca open-order response."
        )

    for order in open_orders:

        symbol = str(
            order.get(
                "symbol",
                "",
            )
        ).upper()

        client_id = str(
            order.get(
                "client_order_id",
                "",
            )
        )

        if symbol not in target_symbols:

            raise RuntimeError(
                "SECURITY STOP: paper account contains "
                "an open order outside Fund-100's "
                "bootstrap target."
            )

        if client_id not in expected_ids:

            raise RuntimeError(
                "SECURITY STOP: paper account contains "
                "an open order that was not created by "
                "this Fund-100 bootstrap execution."
            )

    # --------------------------------------------------------
    # POSITIONS
    # --------------------------------------------------------

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid Alpaca position response."
        )

    for position in positions:

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).upper()

        if symbol not in target_symbols:

            raise RuntimeError(
                "SECURITY STOP: paper account contains "
                "a position outside the V5-002 target."
            )

        # If a target position already exists, require evidence
        # that our deterministic bootstrap order for that
        # symbol already exists at the broker.

        if (
            existing_expected_orders.get(
                symbol
            )
            is None
        ):

            raise RuntimeError(
                f"SECURITY STOP: {symbol} position exists "
                "without the expected Fund-100 bootstrap "
                "order record."
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA PAPER EXECUTION"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: PAPER ORDERS"
    )

    print(
        f"Broker endpoint: "
        f"{PAPER_BASE_URL}"
    )

    print(
        "Live trading endpoint capability: DISABLED"
    )

    print(
        "Cancellation capability: DISABLED"
    )

    print(
        f"Maximum planned test sleeve: "
        f"${reconcile.PAPER_TEST_CAPITAL_USD:.2f}"
    )

    require_paper_execution_arm()

    print(
        "\nPaper execution safety arm: PASS"
    )

    key, secret = (
        reconcile.load_credentials()
    )

    # ========================================================
    # STRATEGY TARGET
    # ========================================================

    state, target = (
        reconcile.load_v5_target()
    )

    if (
        str(
            state.get(
                "last_date"
            )
        )
        != EXPECTED_STATE_DATE
    ):

        raise RuntimeError(
            "BOOTSTRAP STOP: V5-002 shadow state "
            "has moved beyond the frozen 2026-10-01 "
            "bootstrap target."
        )

    plan = (
        reconcile.build_plan(
            target
        )
    )

    print(
        f"V5-002 target date: "
        f"{EXPECTED_STATE_DATE}"
    )

    print(
        f"Planned paper orders: "
        f"{len(plan)}"
    )

    print(
        "Target validation: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        reconcile.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    reconcile.validate_account(
        account
    )

    print(
        "Paper account safety check: PASS"
    )

    # ========================================================
    # MARKET CLOCK
    # ========================================================

    clock = (
        reconcile.get_json(
            path="/v2/clock",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        clock,
        dict,
    ):

        raise RuntimeError(
            "Invalid Alpaca market-clock response."
        )

    if not bool(
        clock.get(
            "is_open",
            False,
        )
    ):

        raise RuntimeError(
            "MARKET CLOSED: no paper orders submitted. "
            "Run this workflow during the regular "
            "US equity session."
        )

    print(
        "US regular market open: PASS"
    )

    # ========================================================
    # ASSET ELIGIBILITY AGAIN
    # ========================================================

    for symbol in sorted(
        target.keys()
    ):

        asset = (
            reconcile.get_json(
                path=(
                    "/v2/assets/"
                    + symbol
                ),
                key=key,
                secret=secret,
            )
        )

        reconcile.validate_asset(
            symbol=
                symbol,

            asset=
                asset,
        )

    print(
        "Target instrument eligibility: PASS"
    )

    # ========================================================
    # DETERMINISTIC CLIENT ORDER IDs
    # ========================================================

    expected_client_ids = {
        item[
            "symbol"
        ]:
            (
                CLIENT_ID_PREFIX
                + "-"
                + item[
                    "symbol"
                ].lower()
            )
        for item
        in plan
    }

    existing_expected_orders = {}

    for symbol, client_id in (
        expected_client_ids.items()
    ):

        existing = (
            get_order_by_client_id(
                client_order_id=
                    client_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if existing is not None:

            validate_broker_order(
                order=
                    existing,

                symbol=
                    symbol,

                client_order_id=
                    client_id,
            )

        existing_expected_orders[
            symbol
        ] = (
            existing
        )

    # ========================================================
    # CURRENT BROKER ACTIVITY
    # ========================================================

    open_orders = (
        reconcile.get_json(
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

    positions = (
        reconcile.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    validate_existing_activity(
        positions=
            positions,

        open_orders=
            open_orders,

        expected_client_ids=
            expected_client_ids,

        existing_expected_orders=
            existing_expected_orders,
    )

    print(
        "Foreign broker activity: NONE"
    )

    # ========================================================
    # SUBMIT MISSING PAPER ORDERS
    # ========================================================

    submitted_count = 0
    duplicate_skip_count = 0

    print(
        "\n============================================"
    )

    print(
        "PAPER ORDER EXECUTION"
    )

    print(
        "============================================"
    )

    for item in plan:

        symbol = (
            item[
                "symbol"
            ]
        )

        notional = float(
            item[
                "paper_notional_usd"
            ]
        )

        client_id = (
            expected_client_ids[
                symbol
            ]
        )

        existing = (
            existing_expected_orders[
                symbol
            ]
        )

        if existing is not None:

            status = str(
                existing.get(
                    "status",
                    "unknown",
                )
            )

            print(
                f"{symbol}: SKIP — deterministic "
                f"paper order already exists "
                f"(status={status})"
            )

            duplicate_skip_count += 1

            continue

        # ----------------------------------------------------
        # Last-second duplicate lookup immediately before POST.
        # ----------------------------------------------------

        duplicate_check = (
            get_order_by_client_id(
                client_order_id=
                    client_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if duplicate_check is not None:

            validate_broker_order(
                order=
                    duplicate_check,

                symbol=
                    symbol,

                client_order_id=
                    client_id,
            )

            print(
                f"{symbol}: SKIP — order appeared "
                "during duplicate check"
            )

            duplicate_skip_count += 1

            continue

        print(
            f"{symbol}: submitting PAPER market order "
            f"for ${notional:.2f}"
        )

        order = (
            submit_paper_order(
                symbol=
                    symbol,

                notional_usd=
                    notional,

                client_order_id=
                    client_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        validate_broker_order(
            order=
                order,

            symbol=
                symbol,

            client_order_id=
                client_id,
        )

        status = str(
            order.get(
                "status",
                "unknown",
            )
        )

        print(
            f"{symbol}: ACCEPTED "
            f"(status={status})"
        )

        submitted_count += 1

    # ========================================================
    # FINAL ORDER EXISTENCE CHECK
    # ========================================================

    print(
        "\nVerifying deterministic broker records..."
    )

    verified_count = 0

    for symbol, client_id in (
        expected_client_ids.items()
    ):

        order = (
            get_order_by_client_id(
                client_order_id=
                    client_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if order is None:

            raise RuntimeError(
                f"{symbol}: expected paper order "
                "cannot be found after execution."
            )

        validate_broker_order(
            order=
                order,

            symbol=
                symbol,

            client_order_id=
                client_id,
        )

        verified_count += 1

        print(
            f"{symbol}: broker order record VERIFIED "
            f"(status={order.get('status', 'unknown')})"
        )

    if (
        verified_count
        != len(
            plan
        )
    ):

        raise RuntimeError(
            "Not every planned order has a "
            "verified broker record."
        )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "PAPER EXECUTION GATE: PASS"
    )

    print(
        "============================================"
    )

    print(
        f"\nNew paper orders submitted: "
        f"{submitted_count}"
    )

    print(
        f"Existing orders safely skipped: "
        f"{duplicate_skip_count}"
    )

    print(
        f"Verified Fund-100 broker records: "
        f"{verified_count}"
    )

    print(
        "\nExecution environment: ALPACA PAPER"
    )

    print(
        "Live endpoint contacted: NO"
    )

    print(
        "Real money used: NO"
    )

    print(
        "Cancellation capability: NONE"
    )

    print(
        "\nNEXT GATE:"
    )

    print(
        "Verify fills and reconcile actual paper "
        "positions against the V5-002 target."
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
            "PAPER EXECUTION GATE: FAILED",
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

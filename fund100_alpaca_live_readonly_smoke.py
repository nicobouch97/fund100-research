from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE READ-ONLY SMOKE TEST v1.0
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# This file intentionally contains:
#
#   GET requests only.
#
# It contains NO:
#
#   POST
#   PATCH
#   PUT
#   DELETE
#
# Therefore it cannot submit, replace, or cancel orders.
#
# Purpose:
#
#   - prove live credentials authenticate
#   - prove correct live API hostname
#   - inspect account status
#   - inspect market clock
#   - count positions
#   - count open orders
#
# Sensitive account identifiers and balances are NOT printed.
# ============================================================


LIVE_BASE_URL = (
    "https://api.alpaca.markets"
)

EXPECTED_LIVE_HOST = (
    "api.alpaca.markets"
)

READONLY_ARM_VALUE = (
    "YES_READ_ONLY_LIVE"
)


# ============================================================
# SAFETY
# ============================================================

def require_readonly_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_READONLY",
            "",
        )
        .strip()
    )

    if value != READONLY_ARM_VALUE:

        raise RuntimeError(
            "Live read-only inspection is not armed."
        )


def validate_live_url(
    url: str,
):

    parsed = urlparse(
        url
    )

    if parsed.scheme != "https":

        raise RuntimeError(
            "SECURITY STOP: live API must use HTTPS."
        )

    if parsed.hostname != EXPECTED_LIVE_HOST:

        raise RuntimeError(
            "SECURITY STOP: unexpected live API host."
        )


# ============================================================
# CREDENTIALS
# ============================================================

def load_credentials():

    key = (
        os.environ.get(
            "ALPACA_LIVE_KEY",
            "",
        )
        .strip()
    )

    secret = (
        os.environ.get(
            "ALPACA_LIVE_SECRET",
            "",
        )
        .strip()
    )

    if not key:

        raise RuntimeError(
            "ALPACA_LIVE_KEY is missing."
        )

    if not secret:

        raise RuntimeError(
            "ALPACA_LIVE_SECRET is missing."
        )

    return (
        key,
        secret,
    )


# ============================================================
# GET ONLY
# ============================================================

def get_json(
    path: str,
    key: str,
    secret: str,
    params: dict | None = None,
):

    if not path.startswith(
        "/"
    ):

        raise RuntimeError(
            "API path must begin with '/'."
        )

    url = (
        LIVE_BASE_URL
        + path
    )

    if params:

        url = (
            url
            + "?"
            + urlencode(
                params
            )
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
                "Fund-100-Live-ReadOnly/1.0",
        },
    )

    if request.get_method() != "GET":

        raise RuntimeError(
            "SECURITY STOP: non-GET request attempted."
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
            "Alpaca LIVE read-only request failed. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca LIVE API is unavailable."
        ) from exc


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE READ-ONLY SMOKE TEST"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        f"Broker endpoint: "
        f"{LIVE_BASE_URL}"
    )

    print(
        "\nHTTP write methods available: NONE"
    )

    print(
        "Order submission capability: DISABLED"
    )

    print(
        "Order cancellation capability: DISABLED"
    )

    print(
        "Position modification capability: DISABLED"
    )

    # ========================================================
    # REQUIRE KILL SWITCH TO REMAIN ENGAGED
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nFund-100 broker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE READ-ONLY SAFETY STOP: "
            "Fund-100 kill switch must be ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    # ========================================================
    # EXPLICIT READ-ONLY ARM
    # ========================================================

    require_readonly_arm()

    print(
        "Live read-only arm: PASS"
    )

    # ========================================================
    # CREDENTIALS
    # ========================================================

    key, secret = (
        load_credentials()
    )

    print(
        "Live credential presence: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        account,
        dict,
    ):

        raise RuntimeError(
            "Invalid live account response."
        )

    if not account.get(
        "id"
    ):

        raise RuntimeError(
            "Live account response missing account ID."
        )

    if not account.get(
        "account_number"
    ):

        raise RuntimeError(
            "Live account response missing "
            "account number."
        )

    print(
        "\nLive API authentication: PASS"
    )

    print(
        f"Account status: "
        f"{account.get('status', 'unknown')}"
    )

    print(
        f"Account blocked: "
        f"{bool(account.get('account_blocked', False))}"
    )

    print(
        f"Trading blocked: "
        f"{bool(account.get('trading_blocked', False))}"
    )

    print(
        f"Transfers blocked: "
        f"{bool(account.get('transfers_blocked', False))}"
    )

    # ========================================================
    # MARKET CLOCK
    # ========================================================

    clock = (
        get_json(
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
            "Invalid live market-clock response."
        )

    print(
        "\nLive market clock: PASS"
    )

    print(
        f"US regular market open: "
        f"{bool(clock.get('is_open', False))}"
    )

    print(
        f"Next market open: "
        f"{clock.get('next_open', 'unknown')}"
    )

    print(
        f"Next market close: "
        f"{clock.get('next_close', 'unknown')}"
    )

    # ========================================================
    # POSITIONS
    # ========================================================

    positions = (
        get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid live positions response."
        )

    # Deliberately do not print symbols, quantities,
    # values, cost basis, or P/L.

    print(
        "\nLive positions endpoint: PASS"
    )

    print(
        f"Number of current positions: "
        f"{len(positions)}"
    )

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    open_orders = (
        get_json(
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
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid live open-order response."
        )

    # Again, deliberately do not print order details.

    print(
        "\nLive open-orders endpoint: PASS"
    )

    print(
        f"Number of open orders: "
        f"{len(open_orders)}"
    )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE READ-ONLY GATE: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nLive API authenticated: YES"
    )

    print(
        "GET requests only: YES"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Orders replaced: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Fund-100 kill switch remained: ENGAGED"
    )

    print(
        "\nNO LIVE EXECUTION CAPABILITY EXISTS "
        "IN THIS SCRIPT."
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
            "LIVE READ-ONLY GATE: FAILED",
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

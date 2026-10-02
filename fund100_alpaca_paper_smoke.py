from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


# ============================================================
# FUND-100 ALPACA PAPER CONNECTIVITY SMOKE TEST
# ============================================================
#
# SECURITY RULES:
#
# - PAPER API ONLY
# - READ-ONLY HTTP GET REQUESTS ONLY
# - NO ORDERS
# - NO CANCELLATIONS
# - NO ACCOUNT MODIFICATIONS
# - NO CREDENTIALS PRINTED
# - NO ACCOUNT ID PRINTED
# - NO BALANCES PRINTED
# - NO POSITION SYMBOLS PRINTED
#
# This file is deliberately incapable of placing a trade.
# ============================================================


PAPER_BASE_URL = "https://paper-api.alpaca.markets"

EXPECTED_SCHEME = "https"
EXPECTED_HOST = "paper-api.alpaca.markets"

TIMEOUT_SECONDS = 20


# ============================================================
# CREDENTIALS
# ============================================================

def load_credentials() -> tuple[str, str]:

    api_key = os.environ.get(
        "ALPACA_PAPER_KEY",
        "",
    ).strip()

    api_secret = os.environ.get(
        "ALPACA_PAPER_SECRET",
        "",
    ).strip()

    if not api_key:

        raise RuntimeError(
            "ALPACA_PAPER_KEY GitHub secret is missing."
        )

    if not api_secret:

        raise RuntimeError(
            "ALPACA_PAPER_SECRET GitHub secret is missing."
        )

    if api_key == api_secret:

        raise RuntimeError(
            "Paper API key and secret unexpectedly match."
        )

    return (
        api_key,
        api_secret,
    )


# ============================================================
# READ-ONLY REQUEST
# ============================================================

def get_json(
    path: str,
    api_key: str,
    api_secret: str,
    params: dict | None = None,
):

    if not path.startswith("/v2/"):

        raise RuntimeError(
            "Only Alpaca /v2/ endpoints are allowed."
        )

    url = (
        PAPER_BASE_URL
        + path
    )

    if params:

        url += (
            "?"
            + urlencode(
                params
            )
        )

    parsed = urlparse(
        url
    )

    if parsed.scheme != EXPECTED_SCHEME:

        raise RuntimeError(
            "SECURITY STOP: non-HTTPS broker URL."
        )

    if parsed.hostname != EXPECTED_HOST:

        raise RuntimeError(
            "SECURITY STOP: broker host is not "
            "the Alpaca paper API."
        )

    request = Request(
        url=url,
        method="GET",
        headers={
            "Accept":
                "application/json",

            "APCA-API-KEY-ID":
                api_key,

            "APCA-API-SECRET-KEY":
                api_secret,

            "User-Agent":
                "Fund-100-Paper-Smoke-Test/1.0",
        },
    )

    try:

        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            status_code = int(
                response.status
            )

            body = (
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

        safe_body = ""

        try:

            safe_body = (
                exc.read()
                .decode(
                    "utf-8"
                )
            )

        except Exception:

            safe_body = (
                "<response body unavailable>"
            )

        raise RuntimeError(
            "Alpaca paper API returned an HTTP error.\n"
            f"Status: {exc.code}\n"
            f"Request ID: {request_id}\n"
            f"Response: {safe_body}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Could not reach Alpaca paper API: "
            f"{exc.reason}"
        ) from exc

    if status_code != 200:

        raise RuntimeError(
            "Unexpected Alpaca response status: "
            f"{status_code}"
        )

    try:

        return json.loads(
            body
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Alpaca returned invalid JSON."
        ) from exc


# ============================================================
# RESPONSE VALIDATION
# ============================================================

def require_dict(
    value,
    endpoint: str,
):

    if not isinstance(
        value,
        dict,
    ):

        raise RuntimeError(
            f"{endpoint} did not return "
            "a JSON object."
        )


def require_list(
    value,
    endpoint: str,
):

    if not isinstance(
        value,
        list,
    ):

        raise RuntimeError(
            f"{endpoint} did not return "
            "a JSON list."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA PAPER BROKER SMOKE TEST"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        f"Broker endpoint: {PAPER_BASE_URL}"
    )

    print(
        "Order submission capability: DISABLED"
    )

    print(
        "Live trading endpoint capability: DISABLED"
    )

    api_key, api_secret = (
        load_credentials()
    )

    print(
        "\nGitHub paper credentials found: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    print(
        "\nChecking paper account..."
    )

    account = (
        get_json(
            path="/v2/account",
            api_key=api_key,
            api_secret=api_secret,
        )
    )

    require_dict(
        account,
        "/v2/account",
    )

    status = str(
        account.get(
            "status",
            "UNKNOWN",
        )
    )

    account_blocked = bool(
        account.get(
            "account_blocked",
            False,
        )
    )

    trading_blocked = bool(
        account.get(
            "trading_blocked",
            False,
        )
    )

    print(
        "Account authentication: PASS"
    )

    print(
        f"Account status: {status}"
    )

    print(
        f"Account blocked: {account_blocked}"
    )

    print(
        f"Trading blocked: {trading_blocked}"
    )

    if account_blocked:

        raise RuntimeError(
            "Paper account is blocked."
        )

    if trading_blocked:

        raise RuntimeError(
            "Trading is blocked on the paper account."
        )

    # ========================================================
    # MARKET CLOCK
    # ========================================================

    print(
        "\nChecking market clock..."
    )

    clock = (
        get_json(
            path="/v2/clock",
            api_key=api_key,
            api_secret=api_secret,
        )
    )

    require_dict(
        clock,
        "/v2/clock",
    )

    market_open = bool(
        clock.get(
            "is_open",
            False,
        )
    )

    print(
        "Market clock endpoint: PASS"
    )

    print(
        f"Market currently open: {market_open}"
    )

    # ========================================================
    # POSITIONS
    # ========================================================

    print(
        "\nChecking broker positions..."
    )

    positions = (
        get_json(
            path="/v2/positions",
            api_key=api_key,
            api_secret=api_secret,
        )
    )

    require_list(
        positions,
        "/v2/positions",
    )

    print(
        "Positions endpoint: PASS"
    )

    print(
        f"Open position count: {len(positions)}"
    )

    # We intentionally do NOT print:
    #
    # - symbols
    # - quantities
    # - market values
    # - cost bases
    #
    # because the Fund-100 repository is public.

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    print(
        "\nChecking open orders..."
    )

    orders = (
        get_json(
            path="/v2/orders",
            api_key=api_key,
            api_secret=api_secret,
            params={
                "status":
                    "open",

                "limit":
                    100,
            },
        )
    )

    require_list(
        orders,
        "/v2/orders",
    )

    print(
        "Orders endpoint: PASS"
    )

    print(
        f"Open order count: {len(orders)}"
    )

    # Again, no order details are printed.

    # ========================================================
    # FINAL SECURITY CHECK
    # ========================================================

    if (
        urlparse(
            PAPER_BASE_URL
        ).hostname
        != EXPECTED_HOST
    ):

        raise RuntimeError(
            "SECURITY STOP: paper endpoint changed."
        )

    print(
        "\n============================================"
    )

    print(
        "PAPER BROKER CONNECTIVITY: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nPaper authentication: PASS"
    )

    print(
        "Account read: PASS"
    )

    print(
        "Market clock read: PASS"
    )

    print(
        "Position read: PASS"
    )

    print(
        "Open-order read: PASS"
    )

    print(
        "Live API contacted: NO"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Account changes made: 0"
    )

    print(
        "\nThe next Fund-100 broker stage is "
        "target-vs-broker reconciliation."
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
            "PAPER BROKER CONNECTIVITY: FAILED",
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

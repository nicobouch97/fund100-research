from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


# ============================================================
# FUND-100 ALPACA PAPER TRANSPORT v1.0
# ============================================================
#
# PAPER ACCOUNT ONLY.
#
# Allowed methods in this helper:
#
#   GET
#   DELETE
#
# It does NOT submit orders.
#
# The connected-writer candidate itself supplies the POST
# transport during the parity test after its destination is
# redirected in memory to the PAPER host.
#
# ============================================================


PAPER_BASE_URL = (
    "https://paper-api.alpaca.markets"
)

EXPECTED_PAPER_HOST = (
    "paper-api.alpaca.markets"
)


def validate_paper_url(
    url: str,
) -> None:

    parsed = urlparse(
        url
    )

    if parsed.scheme != "https":

        raise RuntimeError(
            "PAPER SECURITY STOP: HTTPS required."
        )

    if (
        parsed.hostname
        != EXPECTED_PAPER_HOST
    ):

        raise RuntimeError(
            "PAPER SECURITY STOP: "
            "unexpected broker hostname."
        )

    if parsed.port is not None:

        raise RuntimeError(
            "PAPER SECURITY STOP: "
            "explicit port is not permitted."
        )


def load_paper_credentials():

    key = str(
        os.environ.get(
            "ALPACA_PAPER_KEY",
            "",
        )
    ).strip()

    secret = str(
        os.environ.get(
            "ALPACA_PAPER_SECRET",
            "",
        )
    ).strip()

    if not key:

        raise RuntimeError(
            "PAPER STOP: paper API key missing."
        )

    if not secret:

        raise RuntimeError(
            "PAPER STOP: paper API secret missing."
        )

    return (
        key,
        secret,
    )


def request_headers(
    *,
    key: str,
    secret: str,
):

    return {
        "Accept":
            "application/json",

        "APCA-API-KEY-ID":
            key,

        "APCA-API-SECRET-KEY":
            secret,

        "User-Agent":
            "Fund-100-Paper-Transport-Parity/1.0",
    }


def get_json(
    *,
    path: str,
    key: str,
    secret: str,
    params: dict | None = None,
):

    if not str(
        path
    ).startswith(
        "/v2/"
    ):

        raise RuntimeError(
            "PAPER SECURITY STOP: "
            "unexpected API path."
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

    validate_paper_url(
        url
    )

    request = Request(
        url=url,
        method="GET",
        headers=
            request_headers(
                key=key,
                secret=secret,
            ),
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
            if exc.headers
            else "not-provided"
        )

        raise RuntimeError(
            "Alpaca PAPER GET failed. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca PAPER API unavailable "
            "during GET."
        ) from exc


def get_order_by_client_id(
    *,
    client_order_id: str,
    key: str,
    secret: str,
):

    url = (
        PAPER_BASE_URL
        + "/v2/orders:by_client_order_id?"
        + urlencode({
            "client_order_id":
                client_order_id,
        })
    )

    validate_paper_url(
        url
    )

    request = Request(
        url=url,
        method="GET",
        headers=
            request_headers(
                key=key,
                secret=secret,
            ),
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

        raise RuntimeError(
            "Alpaca PAPER order lookup failed. "
            f"HTTP={exc.code}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca PAPER API unavailable "
            "during order lookup."
        ) from exc


def get_order_by_id(
    *,
    order_id: str,
    key: str,
    secret: str,
):

    order_id = str(
        order_id
    ).strip()

    if not order_id:

        raise RuntimeError(
            "PAPER STOP: order ID missing."
        )

    return get_json(
        path=(
            "/v2/orders/"
            + order_id
        ),
        key=key,
        secret=secret,
    )


def cancel_order(
    *,
    order_id: str,
    key: str,
    secret: str,
):

    order_id = str(
        order_id
    ).strip()

    if not order_id:

        raise RuntimeError(
            "PAPER STOP: order ID missing."
        )

    url = (
        PAPER_BASE_URL
        + "/v2/orders/"
        + order_id
    )

    validate_paper_url(
        url
    )

    request = Request(
        url=url,
        method="DELETE",
        headers=
            request_headers(
                key=key,
                secret=secret,
            ),
    )

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            status = int(
                getattr(
                    response,
                    "status",
                    204,
                )
            )

            if (
                status
                not in {
                    200,
                    202,
                    204,
                }
            ):

                raise RuntimeError(
                    "PAPER STOP: "
                    "unexpected cancellation status."
                )

            return status

    except HTTPError as exc:

        if exc.code == 422:

            # Caller will fetch current state and decide
            # whether the order is already terminal.
            return 422

        raise RuntimeError(
            "Alpaca PAPER cancellation failed. "
            f"HTTP={exc.code}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca PAPER API unavailable "
            "during cancellation."
        ) from exc

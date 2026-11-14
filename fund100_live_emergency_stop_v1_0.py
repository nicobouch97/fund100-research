"""Manual operator emergency-stop broker cleanup.

Only cancel *open* orders with Fund-100's exact deterministic ID patterns.
Never cancel other account orders, close positions, or create orders.
No broker connection happens on import.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import UUID


LIVE_HOST = "https://api.alpaca.markets"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
EXACT_OPEN_ORDERS_PATH = "/v2/orders?status=open&limit=500"
EXACT_ORDER_DELETE = re.compile(
    r"/v2/orders/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
)

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Never forward Alpaca trading-capable credentials to 30x Location.
        raise EmergencyStopError("Alpaca emergency request redirect forbidden")

FUND100_CLIENT_IDS = (
    re.compile(r"^f100live-[0-9a-f]{12}-[bs]-[a-z0-9]{1,12}$"),
    re.compile(r"^f100live-prod-[0-9a-f]{16}-[bs]-[a-z0-9]{1,12}$"),
    re.compile(r"^f100-live-bootstrap-[0-9a-f]{16}-[bs]-[a-z0-9]{1,12}$"),
)


class EmergencyStopError(RuntimeError):
    pass


def is_fund100_client_id(value: object) -> bool:
    return isinstance(value, str) and any(
        expression.fullmatch(value) for expression in FUND100_CLIENT_IDS
    )


def select_fund100_open_orders(orders: object) -> list[str]:
    """Validate entire response before cancelling any selected order."""
    if not isinstance(orders, list):
        raise EmergencyStopError("Invalid Alpaca open-orders response.")
    if len(orders) >= 500:
        raise EmergencyStopError("Open-order listing may be truncated.")
    found = []
    for order in orders:
        if not isinstance(order, dict):
            raise EmergencyStopError("Malformed Alpaca order.")
        if not is_fund100_client_id(order.get("client_order_id")):
            continue
        order_id = order.get("id")
        try:
            normalized = str(UUID(str(order_id)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise EmergencyStopError("Invalid Fund-100 broker order ID.") from exc
        found.append(normalized)
    if len(found) != len(set(found)):
        raise EmergencyStopError("Duplicate Fund-100 broker order ID.")
    return found


def _alpaca_request(method: str, path: str):
    """Only fixed live-host GET or one UUID-bound DELETE; no HTTP redirects.

    The LIVE key/secret are trading-capable even though this module uses
    only GET/DELETE. An accepted DELETE is NOT evidence of cancellation:
    cancel_open_fund100_orders() reconciles fresh broker open orders.
    """
    if method == "GET":
        if path != EXACT_OPEN_ORDERS_PATH:
            raise EmergencyStopError("Unapproved emergency broker GET")
    elif method == "DELETE":
        if type(path) is not str or EXACT_ORDER_DELETE.fullmatch(path) is None:
            raise EmergencyStopError("Unapproved emergency broker DELETE")
    else:
        raise EmergencyStopError("Unsupported emergency broker method")

    key = os.environ.get("ALPACA_LIVE_KEY", "").strip()
    secret = os.environ.get("ALPACA_LIVE_SECRET", "").strip()
    if not key or not secret:
        raise EmergencyStopError("LIVE credentials missing.")

    url = LIVE_HOST + path
    request = Request(
        url, method=method,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
            "Cache-Control": "no-store",
        },
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=15) as resp:
            accepted = (resp.status == 200 if method == "GET"
                        else resp.status in (200, 202, 204))
            if not accepted or resp.geturl() != url:
                raise EmergencyStopError(
                    "Broker emergency response status/origin unverified")
            content = resp.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise EmergencyStopError("Broker emergency response oversized")
    except HTTPError as exc:
        if method == "DELETE" and exc.code in (404, 422):
            # A possible fill/cancel race. Only later GET can prove closed.
            return None
        raise EmergencyStopError(
            "Alpaca emergency cancellation request failed.") from None
    except (URLError, TimeoutError, OSError):
        raise EmergencyStopError(
            "Alpaca emergency cancellation unavailable.") from None

    if not content:
        return None
    try:
        return json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise EmergencyStopError("Invalid Alpaca response.") from None


def fetch_open_fund100_orders() -> list[str]:
    response = _alpaca_request("GET", "/v2/orders?status=open&limit=500")
    return select_fund100_open_orders(response)


def cancel_open_fund100_orders() -> int:
    targets = fetch_open_fund100_orders()
    for order_id in targets:
        _alpaca_request(
            "DELETE", "/v2/orders/" + quote(order_id, safe="")
        )

    # A 204 means the cancellation REQUEST was accepted, not that
    # the order cannot still fill. Reconcile from the broker.
    for attempt in range(5):
        remaining = fetch_open_fund100_orders()
        if not remaining:
            return len(targets)
        if attempt < 4:
            time.sleep(2)
    raise EmergencyStopError(
        "STOP requested, but Fund-100 open orders remain at Alpaca."
    )


if __name__ == "__main__":
    cancelled = cancel_open_fund100_orders()
    print("FUND-100 STOP: cancellation requests accepted, open orders checked.")
    print("Fund-100 orders selected for cancellation:", cancelled)
    print("Other account orders touched: NO")
    print("Portfolio positions liquidated: NO")

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
from urllib.request import Request, urlopen
from uuid import UUID


LIVE_HOST = "https://api.alpaca.markets"
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
    if method not in ("GET", "DELETE"):
        raise EmergencyStopError("Unsupported broker request method.")
    if not (
        path == "/v2/orders?status=open&limit=500"
        or (method == "DELETE" and path.startswith("/v2/orders/"))
    ):
        raise EmergencyStopError("Unapproved broker API path.")
    key = os.environ.get("ALPACA_LIVE_KEY", "").strip()
    secret = os.environ.get("ALPACA_LIVE_SECRET", "").strip()
    if not key or not secret:
        raise EmergencyStopError("LIVE credentials missing.")
    request = Request(
        LIVE_HOST + path,
        method=method,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as resp:
            content = resp.read()
    except HTTPError as exc:
        if method == "DELETE" and exc.code in (404, 422):
            # A fill/cancel race: final GET must prove the order is closed.
            return None
        raise EmergencyStopError("Alpaca emergency cancellation request failed.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise EmergencyStopError("Alpaca emergency cancellation unavailable.") from exc

    if not content:
        return None
    try:
        return json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise EmergencyStopError("Invalid Alpaca response.") from exc


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

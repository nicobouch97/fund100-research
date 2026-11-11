"""V6 FIRST ORIGINAL ACWI only: selective signed broker-order cancellation.

Separate from the previously reviewed, immutable V5 emergency STOP source.
No new broker method: delegates only GET and DELETE to that pinned module.
Never submits a new order, edits operator GO, or liquidates any position.
"""
from __future__ import annotations

from urllib.parse import quote
from uuid import UUID
import time

import fund100_live_emergency_stop_v1_0 as v5_emergency
import fund100_v6_s1_private_git_cas_protocol_v1_0 as signed

SCHEMA = "FUND100_V6_S1_FIRST_ACWI_SELECTIVE_CANCEL_V1"
SIGNED_FIRST_ACWI_CLIENT_ID = signed.CLIENT_IDS["ACWI"]
NO_BROKER_POST = True
NO_LIQUIDATION = True
NO_OPERATOR_WRITE = True
OPEN_ORDERS_PATH = "/v2/orders?status=open&limit=500"
MAX_OPEN_ORDERS = 499
RECONCILIATION_ATTEMPTS = 5


class FirstAcwiCancelStop(RuntimeError):
    pass


def _targets(orders: object) -> list[str]:
    """Validate the entire open-orders page before cancelling any candidate."""
    if type(orders) is not list or len(orders) > MAX_OPEN_ORDERS:
        raise FirstAcwiCancelStop("Broker open-orders listing invalid or truncated")
    ids = []
    for order in orders:
        if type(order) is not dict:
            raise FirstAcwiCancelStop("Malformed broker open order")
        if order.get("client_order_id") != SIGNED_FIRST_ACWI_CLIENT_ID:
            continue
        # Strong match: exact signed migration ID plus immutable intended
        # instrument and sell side. Conflicting/missing fields are anomalous,
        # not a reason to target a potentially unrelated order.
        if order.get("symbol") != "ACWI" or order.get("side") != "sell":
            raise FirstAcwiCancelStop("Signed ACWI order identity ambiguous")
        try:
            order_id = str(UUID(order["id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise FirstAcwiCancelStop("Signed ACWI broker order UUID invalid") from None
        ids.append(order_id)
    if len(ids) != len(set(ids)) or len(ids) > 1:
        raise FirstAcwiCancelStop("Duplicate signed first ACWI broker order")
    return ids


def cancel_open_first_signed_acwi_orders() -> int:
    """At most one signed original ACWI SELL; verify cancellation with GETs.

    A successful DELETE is merely a cancellation request; final GET must
    confirm no such open order remains, and does NOT prove the order unfilled.
    """
    to_cancel = _targets(v5_emergency._alpaca_request("GET", OPEN_ORDERS_PATH))
    for order_id in to_cancel:
        v5_emergency._alpaca_request(
            "DELETE", "/v2/orders/" + quote(order_id, safe=""))
    for attempt in range(RECONCILIATION_ATTEMPTS):
        pending = _targets(v5_emergency._alpaca_request("GET", OPEN_ORDERS_PATH))
        if not pending:
            return len(to_cancel)
        if attempt < RECONCILIATION_ATTEMPTS - 1:
            time.sleep(2)
    raise FirstAcwiCancelStop("Signed original ACWI broker order remains open")


if __name__ == "__main__":
    count = cancel_open_first_signed_acwi_orders()
    print("Original V6 ACWI emergency cancellation checked; no trade submitted.")
    print("Exact signed ACWI orders selected for cancellation:", count)
    print("Other account orders cancelled: NO")
    print("Portfolio positions liquidated: NO")

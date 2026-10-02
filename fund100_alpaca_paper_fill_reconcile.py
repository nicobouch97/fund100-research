from __future__ import annotations

import sys

import fund100_alpaca_paper_reconcile as reconcile
import fund100_alpaca_paper_execute_bootstrap as execute


# ============================================================
# FUND-100 ALPACA PAPER FILL RECONCILIATION v1.0
# ============================================================
#
# READ ONLY.
#
# Verifies:
#
# 1. All four deterministic Fund-100 orders exist.
# 2. Every order is FILLED.
# 3. Filled quantities are positive.
# 4. Filled notional is close to intended notional.
# 5. Alpaca position quantities match filled quantities.
# 6. No unexpected positions exist.
# 7. No open orders remain.
#
# NO POST / PATCH / DELETE REQUESTS ARE USED.
# ============================================================


EXPECTED_STATE_DATE = "2026-10-01"

NOTIONAL_TOLERANCE_FRACTION = 0.01

MIN_NOTIONAL_TOLERANCE_USD = 0.05

QTY_RELATIVE_TOLERANCE = 1e-6

QTY_ABSOLUTE_TOLERANCE = 1e-8


# ============================================================
# NUMERIC HELPERS
# ============================================================

def as_float(
    value,
    label: str,
) -> float:

    try:

        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            f"Invalid numeric value for {label}: "
            f"{value}"
        ) from exc

    return number


def quantities_match(
    left: float,
    right: float,
) -> bool:

    tolerance = max(
        QTY_ABSOLUTE_TOLERANCE,
        abs(
            right
        )
        * QTY_RELATIVE_TOLERANCE,
    )

    return (
        abs(
            left
            - right
        )
        <= tolerance
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA PAPER FILL RECONCILIATION"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "Order submission capability: DISABLED"
    )

    print(
        "Order cancellation capability: DISABLED"
    )

    print(
        "Live endpoint capability: DISABLED"
    )

    key, secret = (
        reconcile.load_credentials()
    )

    # ========================================================
    # LOAD THE EXACT V5-002 BOOTSTRAP TARGET
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
            "RECONCILIATION STOP: shadow state "
            "has moved beyond the original "
            "2026-10-01 bootstrap target."
        )

    plan = (
        reconcile.build_plan(
            target
        )
    )

    target_symbols = {
        item[
            "symbol"
        ]
        for item
        in plan
    }

    print(
        f"\nV5-002 bootstrap target date: "
        f"{EXPECTED_STATE_DATE}"
    )

    print(
        f"Expected symbols: "
        f"{len(target_symbols)}"
    )

    print(
        "Target loading: PASS"
    )

    # ========================================================
    # ACCOUNT SAFETY
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
    # OPEN ORDERS MUST NOW BE ZERO
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

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid open-order response."
        )

    if len(
        open_orders
    ) != 0:

        raise RuntimeError(
            "FILL RECONCILIATION STOP: "
            "one or more paper orders are "
            "still open."
        )

    print(
        "Open paper orders: 0 — PASS"
    )

    # ========================================================
    # CURRENT POSITIONS
    # ========================================================

    positions = (
        reconcile.get_json(
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
            "Invalid Alpaca positions response."
        )

    positions_by_symbol = {}

    for position in positions:

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).upper()

        if not symbol:

            raise RuntimeError(
                "Position with missing symbol."
            )

        if symbol in positions_by_symbol:

            raise RuntimeError(
                f"Duplicate broker position: {symbol}"
            )

        positions_by_symbol[
            symbol
        ] = (
            position
        )

    actual_symbols = set(
        positions_by_symbol.keys()
    )

    unexpected = (
        actual_symbols
        - target_symbols
    )

    missing = (
        target_symbols
        - actual_symbols
    )

    if unexpected:

        raise RuntimeError(
            "SECURITY STOP: unexpected paper "
            "positions detected: "
            + ", ".join(
                sorted(
                    unexpected
                )
            )
        )

    if missing:

        raise RuntimeError(
            "Expected paper positions are missing: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    if (
        len(
            positions_by_symbol
        )
        != len(
            target_symbols
        )
    ):

        raise RuntimeError(
            "Unexpected paper position count."
        )

    print(
        f"Paper positions found: "
        f"{len(positions_by_symbol)} — PASS"
    )

    # ========================================================
    # ORDER / FILL / POSITION RECONCILIATION
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "FILL-BY-FILL RECONCILIATION"
    )

    print(
        "============================================"
    )

    total_target_notional = 0.0

    total_filled_notional = 0.0

    reconciled_count = 0

    for item in sorted(
        plan,
        key=lambda x: x[
            "symbol"
        ],
    ):

        symbol = (
            item[
                "symbol"
            ]
        )

        target_notional = float(
            item[
                "paper_notional_usd"
            ]
        )

        client_order_id = (
            execute.CLIENT_ID_PREFIX
            + "-"
            + symbol.lower()
        )

        # ----------------------------------------------------
        # Retrieve deterministic Fund-100 order
        # ----------------------------------------------------

        order = (
            execute.get_order_by_client_id(
                client_order_id=
                    client_order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if order is None:

            raise RuntimeError(
                f"{symbol}: deterministic Fund-100 "
                "order cannot be found."
            )

        execute.validate_broker_order(
            order=
                order,

            symbol=
                symbol,

            client_order_id=
                client_order_id,
        )

        status = str(
            order.get(
                "status",
                "",
            )
        ).lower()

        if status != "filled":

            raise RuntimeError(
                f"{symbol}: expected FILLED order, "
                f"broker status is {status}."
            )

        # ----------------------------------------------------
        # Filled quantity / price
        # ----------------------------------------------------

        filled_qty = as_float(
            order.get(
                "filled_qty"
            ),
            f"{symbol} filled_qty",
        )

        filled_avg_price = as_float(
            order.get(
                "filled_avg_price"
            ),
            f"{symbol} filled_avg_price",
        )

        if filled_qty <= 0:

            raise RuntimeError(
                f"{symbol}: filled quantity is "
                "not positive."
            )

        if filled_avg_price <= 0:

            raise RuntimeError(
                f"{symbol}: average fill price is "
                "not positive."
            )

        filled_notional = (
            filled_qty
            * filled_avg_price
        )

        notional_difference = abs(
            filled_notional
            - target_notional
        )

        notional_tolerance = max(
            MIN_NOTIONAL_TOLERANCE_USD,
            target_notional
            * NOTIONAL_TOLERANCE_FRACTION,
        )

        if (
            notional_difference
            > notional_tolerance
        ):

            raise RuntimeError(
                f"{symbol}: filled notional differs "
                "too much from intended notional. "
                f"Target=${target_notional:.4f}, "
                f"Filled=${filled_notional:.4f}, "
                f"Difference=${notional_difference:.4f}"
            )

        # ----------------------------------------------------
        # Match broker position to fill
        # ----------------------------------------------------

        position = (
            positions_by_symbol[
                symbol
            ]
        )

        side = str(
            position.get(
                "side",
                "",
            )
        ).lower()

        if (
            side
            and side != "long"
        ):

            raise RuntimeError(
                f"{symbol}: unexpected broker "
                f"position side {side}."
            )

        position_qty = as_float(
            position.get(
                "qty"
            ),
            f"{symbol} position qty",
        )

        if not quantities_match(
            position_qty,
            filled_qty,
        ):

            raise RuntimeError(
                f"{symbol}: broker position "
                "quantity does not match "
                "Fund-100 filled quantity. "
                f"Position={position_qty}, "
                f"Filled={filled_qty}"
            )

        total_target_notional += (
            target_notional
        )

        total_filled_notional += (
            filled_notional
        )

        reconciled_count += 1

        print(
            f"\n{symbol}: PASS"
        )

        print(
            f"  Intended notional: "
            f"${target_notional:.2f}"
        )

        print(
            f"  Filled notional: "
            f"${filled_notional:.2f}"
        )

        print(
            f"  Filled quantity: "
            f"{filled_qty:.8f}"
        )

        print(
            f"  Broker position: "
            f"{position_qty:.8f}"
        )

        print(
            "  Position/fill quantity match: YES"
        )

    # ========================================================
    # PORTFOLIO TOTAL CHECK
    # ========================================================

    if (
        reconciled_count
        != len(
            plan
        )
    ):

        raise RuntimeError(
            "Not every V5-002 bootstrap order "
            "was reconciled."
        )

    total_difference = abs(
        total_filled_notional
        - total_target_notional
    )

    total_tolerance = max(
        0.10,
        total_target_notional
        * 0.01,
    )

    if (
        total_difference
        > total_tolerance
    ):

        raise RuntimeError(
            "Aggregate filled notional differs "
            "too much from the Fund-100 target."
        )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "PAPER FILL RECONCILIATION: PASS"
    )

    print(
        "============================================"
    )

    print(
        f"\nOrders reconciled: "
        f"{reconciled_count}"
    )

    print(
        f"Expected paper sleeve: "
        f"${total_target_notional:.2f}"
    )

    print(
        f"Approximate filled notional: "
        f"${total_filled_notional:.2f}"
    )

    print(
        f"Difference: "
        f"${total_difference:.4f}"
    )

    print(
        "\nUnexpected positions: 0"
    )

    print(
        "Missing positions: 0"
    )

    print(
        "Open orders remaining: 0"
    )

    print(
        "Orders submitted by this test: 0"
    )

    print(
        "Orders cancelled by this test: 0"
    )

    print(
        "Live endpoint contacted: NO"
    )

    print(
        "\nNEXT GATE:"
    )

    print(
        "Deliberate Fund-100 kill-switch test."
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
            "PAPER FILL RECONCILIATION: FAILED",
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

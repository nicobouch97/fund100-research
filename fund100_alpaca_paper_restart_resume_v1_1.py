from __future__ import annotations

import sys

import fund100_alpaca_paper_reconcile as broker
import fund100_alpaca_paper_execute_bootstrap as bootstrap
import fund100_alpaca_paper_twosided_rehearsal as two
import fund100_alpaca_paper_restart_rehearsal as v10

from fund100_broker_safety import (
    require_broker_writes_allowed,
)


# ============================================================
# FUND-100 PAPER CRASH/RESTART RECOVERY v1.1
# ============================================================
#
# RESUME ONLY.
#
# Fixes v1.0 recovery bug:
#
# v1.0 tried to rediscover the interrupted SELL from the
# portfolio AFTER the SELL had already changed the weights.
#
# v1.1 instead uses the original frozen synthetic-event donor
# to reconstruct the exact deterministic client_order_id.
#
# NO NEW INTERRUPT PHASE EXISTS HERE.
#
# PAPER ONLY.
# ============================================================


def as_positive_float(
    value,
    label: str,
) -> float:

    try:

        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            f"Invalid {label}: {value}"
        ) from exc

    if result <= 0:

        raise RuntimeError(
            f"{label} must be positive."
        )

    return result


def filled_notional(
    order: dict,
) -> float:

    qty = as_positive_float(
        order.get(
            "filled_qty"
        ),
        "filled quantity",
    )

    price = as_positive_float(
        order.get(
            "filled_avg_price"
        ),
        "filled average price",
    )

    return (
        qty
        * price
    )


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PAPER RESTART RECOVERY v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: RESUME ONLY"
    )

    print(
        "Environment: ALPACA PAPER"
    )

    print(
        "Live endpoint capability: DISABLED"
    )

    print(
        "New interruption capability: DISABLED"
    )

    print(
        "Shadow-state modification: DISABLED"
    )

    # ========================================================
    # SAFETY ARMS
    # ========================================================

    v10.require_restart_arm()

    require_broker_writes_allowed()

    print(
        "\nRestart-test arm: PASS"
    )

    print(
        "Broker kill switch: DISENGAGED"
    )

    # ========================================================
    # BROKER
    # ========================================================

    key, secret = (
        broker.load_credentials()
    )

    v10.ensure_market_ready(
        key=
            key,

        secret=
            secret,
    )

    # ========================================================
    # RECONSTRUCT ORIGINAL EVENT
    # ========================================================

    (
        state,
        real_target,
        synthetic_target,
        donor,
        receiver,
        shift,
        prefix,
    ) = (
        v10.load_test_context()
    )

    print(
        f"\nV5-002 state date: "
        f"{state['last_date']}"
    )

    print(
        f"Synthetic shift: "
        f"{shift:.2%}"
    )

    print(
        f"Original donor: "
        f"{donor}"
    )

    print(
        f"Original receiver: "
        f"{receiver}"
    )

    print(
        f"Deterministic restart event: "
        f"{prefix}"
    )

    # ========================================================
    # RECOVER THE EXACT INTERRUPTED SELL
    # ========================================================

    sell_cid = (
        v10.client_id(
            prefix=
                prefix,

            stage=
                "shift",

            side=
                "sell",

            symbol=
                donor,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "RECOVERING INTERRUPTED BROKER ORDER"
    )

    print(
        "============================================"
    )

    print(
        f"\nExpected interrupted client ID:"
    )

    print(
        sell_cid
    )

    existing_sell = (
        bootstrap.get_order_by_client_id(
            client_order_id=
                sell_cid,

            key=
                key,

            secret=
                secret,
        )
    )

    if existing_sell is None:

        raise RuntimeError(
            "RESTART RECOVERY FAILED: "
            "the ORIGINAL donor SELL cannot "
            "be found at Alpaca."
        )

    broker_symbol = str(
        existing_sell.get(
            "symbol",
            "",
        )
    ).upper()

    broker_side = str(
        existing_sell.get(
            "side",
            "",
        )
    ).lower()

    if broker_symbol != donor:

        raise RuntimeError(
            "Recovered order symbol does not "
            "match the original donor."
        )

    if broker_side != "sell":

        raise RuntimeError(
            "Recovered order is not a SELL."
        )

    status = str(
        existing_sell.get(
            "status",
            "",
        )
    ).lower()

    if status != "filled":

        existing_sell = (
            two.wait_for_fill(
                client_order_id=
                    sell_cid,

                key=
                    key,

                secret=
                    secret,
            )
        )

    sold_notional = (
        filled_notional(
            existing_sell
        )
    )

    print(
        "\nInterrupted SELL recovered: PASS"
    )

    print(
        f"Recovered symbol: "
        f"{donor}"
    )

    print(
        f"Recovered filled notional: "
        f"${sold_notional:.2f}"
    )

    print(
        "Duplicate interrupted SELL submitted: NO"
    )

    # ========================================================
    # COMPLETE THE MISSING SYNTHETIC BUY
    # ========================================================

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    invested_after_sell = sum(
        float(
            value
        )
        for value
        in positions.values()
    )

    # Approximate the sleeve immediately before interruption
    # by adding the recovered sale proceeds back to the
    # currently invested sleeve.
    estimated_original_sleeve = (
        invested_after_sell
        + sold_notional
    )

    desired_receiver_value = (
        estimated_original_sleeve
        * float(
            synthetic_target[
                receiver
            ]
        )
    )

    current_receiver_value = float(
        positions.get(
            receiver,
            0.0,
        )
    )

    required_buy = (
        desired_receiver_value
        - current_receiver_value
    )

    if required_buy < two.MIN_ORDER_NOTIONAL:

        # The original SELL proceeds remain the safest
        # deterministic approximation if ordinary price
        # movement makes the recalculated delta too small.
        required_buy = (
            sold_notional
        )

    buy_cid = (
        v10.client_id(
            prefix=
                prefix,

            stage=
                "shift",

            side=
                "buy",

            symbol=
                receiver,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "COMPLETING INTERRUPTED SYNTHETIC EVENT"
    )

    print(
        "============================================"
    )

    print(
        f"\nMissing BUY: "
        f"{receiver} "
        f"${required_buy:.2f}"
    )

    print(
        f"Deterministic BUY client ID:"
    )

    print(
        buy_cid
    )

    two.ensure_order(
        symbol=
            receiver,

        side=
            "buy",

        notional=
            required_buy,

        client_order_id=
            buy_cid,

        key=
            key,

        secret=
            secret,
    )

    print(
        "Missing BUY fill: PASS"
    )

    # ========================================================
    # VERIFY SYNTHETIC EVENT
    # ========================================================

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    two.verify_real_target(
        target=
            synthetic_target,

        positions=
            positions,
    )

    print(
        "\nSynthetic interrupted event recovery: PASS"
    )

    # ========================================================
    # RESTORE THE TRUE V5-002 TARGET
    # ========================================================

    (
        _,
        restore_actions,
    ) = (
        two.actionable_plan(
            target=
                real_target,

            positions=
                positions,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "RESTORING TRUE V5-002 TARGET"
    )

    print(
        "============================================"
    )

    if not restore_actions:

        print(
            "\nNo restoration trades required."
        )

    for action in (
        restore_actions
    ):

        print(
            f"\n{action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    v10.execute_actions(
        actions=
            restore_actions,

        prefix=
            prefix,

        stage=
            "restore",

        key=
            key,

        secret=
            secret,
    )

    # ========================================================
    # FINAL RECONCILIATION
    # ========================================================

    final_positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    two.verify_real_target(
        target=
            real_target,

        positions=
            final_positions,
    )

    open_orders = (
        broker.get_json(
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
            "Invalid Alpaca open-order response."
        )

    if len(
        open_orders
    ) != 0:

        raise RuntimeError(
            "Open paper orders remain after "
            "restart recovery."
        )

    print(
        "\n============================================"
    )

    print(
        "CRASH / RESTART REHEARSAL v1.1: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nOriginal interrupted SELL recovered: PASS"
    )

    print(
        "Duplicate interrupted SELL submitted: 0"
    )

    print(
        "Missing BUY completed: PASS"
    )

    print(
        "Synthetic event completed: PASS"
    )

    print(
        "Real V5-002 target restored: PASS"
    )

    print(
        "Open orders remaining: 0"
    )

    print(
        "V5-002 shadow state changed: NO"
    )

    print(
        "Live endpoint contacted: NO"
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
            "RESTART RECOVERY v1.1: FAILED",
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

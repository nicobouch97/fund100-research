from __future__ import annotations

import json
import sys
from pathlib import Path

import fund100_experiment_runner as research_base
import fund100_alpaca_paper_reconcile as broker
from fund100_broker_safety import get_kill_switch_state


# ============================================================
# FUND-100 ALPACA PAPER REBALANCE DRY RUN v1.0
# ============================================================
#
# READ ONLY.
#
# - Reads latest V5-002 executed shadow holdings
# - Reads actual Alpaca paper positions
# - Calculates target dollar values
# - Calculates BUY / SELL differences
# - SUBMITS NOTHING
#
# Kill switch must remain ENGAGED for this test.
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

CORE_SYMBOL = "ACWI"

EXPECTED_STRATEGY = "V5-002_SHADOW"

MIN_PLAN_NOTIONAL_USD = 0.10


# ============================================================
# LOAD TARGET
# ============================================================

def load_target():

    if not STATE_PATH.exists():

        raise RuntimeError(
            "V5-002 shadow state is missing."
        )

    with STATE_PATH.open(
        "r"
    ) as f:

        state = json.load(
            f
        )

    if (
        state.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected V5-002 shadow strategy."
        )

    # --------------------------------------------------------
    # During this engineering stage we reconcile only the
    # strategy's already-executed shadow holdings.
    #
    # If a next-session target is waiting, stop rather than
    # create ambiguous execution timing.
    # --------------------------------------------------------

    if (
        state.get(
            "pending_target"
        )
        is not None
    ):

        raise RuntimeError(
            "V5-002 has a pending next-session target. "
            "Dry-run reconciliation stopped to preserve "
            "execution-timing integrity."
        )

    satellites = (
        state.get(
            "satellite_weights",
            {}
        )
    )

    target = {}

    satellite_total = 0.0

    for symbol, value in (
        satellites.items()
    ):

        weight = float(
            value
        )

        if weight < -1e-10:

            raise RuntimeError(
                f"Negative target weight: {symbol}"
            )

        satellite_total += (
            weight
        )

        if weight > 1e-10:

            target[
                symbol
            ] = (
                weight
            )

    core_weight = (
        1.0
        - satellite_total
    )

    if core_weight < -1e-8:

        raise RuntimeError(
            "Invalid negative ACWI core weight."
        )

    target[
        CORE_SYMBOL
    ] = (
        core_weight
    )

    total = sum(
        target.values()
    )

    if abs(
        total
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "Target weights do not sum to 100%."
        )

    return (
        state,
        target,
    )


# ============================================================
# BROKER POSITIONS
# ============================================================

def load_positions(
    key: str,
    secret: str,
):

    positions = (
        broker.get_json(
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

    allowed_symbols = (
        set(
            research_base.EQUITY_UNIVERSE
        )
        | {
            CORE_SYMBOL
        }
    )

    output = {}

    for position in positions:

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).upper()

        if not symbol:

            raise RuntimeError(
                "Broker position is missing a symbol."
            )

        if symbol not in allowed_symbols:

            raise RuntimeError(
                "SECURITY STOP: unexpected broker "
                f"position detected: {symbol}"
            )

        if symbol in output:

            raise RuntimeError(
                f"Duplicate broker position: {symbol}"
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
                f"{symbol}: unexpected position side."
            )

        market_value = float(
            position.get(
                "market_value",
                0.0,
            )
        )

        quantity = float(
            position.get(
                "qty",
                0.0,
            )
        )

        if market_value < 0:

            raise RuntimeError(
                f"{symbol}: negative market value."
            )

        if quantity < 0:

            raise RuntimeError(
                f"{symbol}: negative quantity."
            )

        output[
            symbol
        ] = {
            "market_value":
                market_value,

            "quantity":
                quantity,
        }

    return output


# ============================================================
# BUILD REBALANCE PLAN
# ============================================================

def build_rebalance_plan(
    target: dict,
    positions: dict,
):

    sleeve_value = sum(
        item[
            "market_value"
        ]
        for item
        in positions.values()
    )

    if sleeve_value <= 0:

        raise RuntimeError(
            "Paper sleeve market value is not positive."
        )

    symbols = sorted(
        set(
            target.keys()
        )
        | set(
            positions.keys()
        )
    )

    rows = []

    for symbol in symbols:

        target_weight = float(
            target.get(
                symbol,
                0.0,
            )
        )

        current_value = float(
            positions.get(
                symbol,
                {},
            ).get(
                "market_value",
                0.0,
            )
        )

        desired_value = (
            sleeve_value
            * target_weight
        )

        delta = (
            desired_value
            - current_value
        )

        if (
            delta
            > MIN_PLAN_NOTIONAL_USD
        ):

            action = "BUY"

        elif (
            delta
            < -MIN_PLAN_NOTIONAL_USD
        ):

            action = "SELL"

        else:

            action = "HOLD"

        current_weight = (
            current_value
            / sleeve_value
        )

        rows.append({
            "symbol":
                symbol,

            "current_value":
                current_value,

            "current_weight":
                current_weight,

            "target_weight":
                target_weight,

            "desired_value":
                desired_value,

            "delta":
                delta,

            "action":
                action,
        })

    return (
        sleeve_value,
        rows,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA PAPER REBALANCE DRY RUN"
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

    kill_switch = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_switch}"
    )

    if kill_switch != "ENGAGED":

        raise RuntimeError(
            "DRY-RUN SAFETY STOP: kill switch "
            "must remain ENGAGED during this test."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    key, secret = (
        broker.load_credentials()
    )

    # ========================================================
    # TARGET
    # ========================================================

    state, target = (
        load_target()
    )

    print(
        f"\nV5-002 executed target date: "
        f"{state['last_date']}"
    )

    print(
        "V5-002 target loading: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        broker.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    broker.validate_account(
        account
    )

    print(
        "Paper account safety check: PASS"
    )

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    orders = (
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
        orders,
        list,
    ):

        raise RuntimeError(
            "Invalid open-order response."
        )

    if len(
        orders
    ) != 0:

        raise RuntimeError(
            "REBALANCE STOP: Alpaca currently "
            "has open paper orders."
        )

    print(
        "Open paper orders: 0 — PASS"
    )

    # ========================================================
    # POSITIONS
    # ========================================================

    positions = (
        load_positions(
            key=
                key,

            secret=
                secret,
        )
    )

    print(
        f"Paper positions loaded: "
        f"{len(positions)}"
    )

    # ========================================================
    # PLAN
    # ========================================================

    (
        sleeve_value,
        rows,
    ) = (
        build_rebalance_plan(
            target=
                target,

            positions=
                positions,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "DRY-RUN REBALANCE PLAN"
    )

    print(
        "============================================"
    )

    print(
        f"\nCurrent Fund-100 paper sleeve value: "
        f"${sleeve_value:.2f}"
    )

    buy_total = 0.0
    sell_total = 0.0

    actionable = 0

    for row in rows:

        symbol = (
            row[
                "symbol"
            ]
        )

        action = (
            row[
                "action"
            ]
        )

        delta = float(
            row[
                "delta"
            ]
        )

        print(
            f"\n{symbol}"
        )

        print(
            f"  Current: "
            f"${row['current_value']:.2f} "
            f"({row['current_weight']:.2%})"
        )

        print(
            f"  Target:  "
            f"${row['desired_value']:.2f} "
            f"({row['target_weight']:.2%})"
        )

        if action == "BUY":

            print(
                f"  DRY RUN: BUY "
                f"${delta:.2f}"
            )

            buy_total += (
                delta
            )

            actionable += 1

        elif action == "SELL":

            amount = abs(
                delta
            )

            print(
                f"  DRY RUN: SELL "
                f"${amount:.2f}"
            )

            sell_total += (
                amount
            )

            actionable += 1

        else:

            print(
                "  DRY RUN: HOLD"
            )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "DRY-RUN REBALANCE: PASS"
    )

    print(
        "============================================"
    )

    print(
        f"\nActionable differences: "
        f"{actionable}"
    )

    print(
        f"Simulated buys: "
        f"${buy_total:.2f}"
    )

    print(
        f"Simulated sells: "
        f"${sell_total:.2f}"
    )

    print(
        "\nOrders submitted: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Live API contacted: NO"
    )

    print(
        "Kill switch remained: ENGAGED"
    )

    print(
        "\nNEXT GATE:"
    )

    print(
        "Automated guarded paper rebalancing."
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
            "DRY-RUN REBALANCE: FAILED",
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

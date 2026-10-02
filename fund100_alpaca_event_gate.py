from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import fund100_experiment_runner as research_base
import fund100_alpaca_paper_reconcile as broker

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 V5-002 BROKER EVENT GATE v1.0
# ============================================================
#
# READ ONLY.
#
# The broker must NOT continuously rebalance against normal
# market drift.
#
# A broker rebalance becomes eligible only when V5-002 has
# generated a genuine pending strategy target:
#
#     pending_target != null
#
# This script also supports a synthetic READ-ONLY event for
# engineering validation.
#
# NO ORDERS.
# NO CANCELLATIONS.
# PAPER API ONLY.
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

CORE_SYMBOL = "ACWI"

EXPECTED_STRATEGY = "V5-002_SHADOW"

MIN_ACTION_USD = 0.10

SYNTHETIC_SHIFT = 0.01


# ============================================================
# STATE
# ============================================================

def load_state():

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
            "Unexpected shadow strategy."
        )

    return state


# ============================================================
# TARGET HELPERS
# ============================================================

def normalise_target(
    satellites: dict,
):

    target = {}

    satellite_total = 0.0

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        weight = float(
            satellites.get(
                symbol,
                0.0,
            )
        )

        if weight < -1e-10:

            raise RuntimeError(
                f"Negative target weight: {symbol}"
            )

        satellite_total += weight

        if weight > 1e-10:

            target[
                symbol
            ] = weight

    core_weight = (
        1.0
        - satellite_total
    )

    if core_weight < -1e-8:

        raise RuntimeError(
            "Target has negative ACWI core."
        )

    target[
        CORE_SYMBOL
    ] = core_weight

    total = sum(
        target.values()
    )

    if abs(
        total
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "Target does not sum to 100%."
        )

    return target


def synthetic_test_target(
    state: dict,
):

    satellites = {
        symbol:
            float(
                state[
                    "satellite_weights"
                ].get(
                    symbol,
                    0.0,
                )
            )
        for symbol
        in research_base.EQUITY_UNIVERSE
    }

    positive = [
        symbol
        for symbol, weight
        in satellites.items()
        if weight > 0.001
    ]

    positive = sorted(
        positive,
        key=lambda symbol:
            satellites[
                symbol
            ],
        reverse=True,
    )

    if len(
        positive
    ) < 2:

        raise RuntimeError(
            "Synthetic event requires at least "
            "two existing satellite positions."
        )

    donor = (
        positive[
            0
        ]
    )

    receiver = (
        positive[
            1
        ]
    )

    shift = min(
        SYNTHETIC_SHIFT,
        satellites[
            donor
        ] / 2.0,
        max(
            0.0,
            0.125
            - satellites[
                receiver
            ],
        ),
    )

    if shift <= 0:

        raise RuntimeError(
            "Unable to construct safe "
            "synthetic event."
        )

    satellites[
        donor
    ] -= shift

    satellites[
        receiver
    ] += shift

    return (
        normalise_target(
            satellites
        ),
        "SYNTHETIC_TEST",
    )


def load_event_target(
    state: dict,
):

    synthetic_mode = (
        os.environ.get(
            "FUND100_SYNTHETIC_EVENT_TEST",
            "",
        )
        .strip()
        .upper()
        == "YES"
    )

    if synthetic_mode:

        target, source = (
            synthetic_test_target(
                state
            )
        )

        return (
            target,
            source,
            True,
        )

    pending = (
        state.get(
            "pending_target"
        )
    )

    if pending is None:

        return (
            None,
            None,
            False,
        )

    source = str(
        state.get(
            "pending_source"
        )
    )

    if source not in {
        "SCHEDULED",
        "EMERGENCY",
    }:

        raise RuntimeError(
            "Unexpected V5-002 pending-source value."
        )

    return (
        normalise_target(
            pending
        ),
        source,
        False,
    )


# ============================================================
# EVENT ID
# ============================================================

def build_event_id(
    state_date: str,
    source: str,
    target: dict,
):

    payload = {
        "strategy":
            EXPECTED_STRATEGY,

        "signal_date":
            state_date,

        "source":
            source,

        "target":
            {
                symbol:
                    round(
                        float(
                            weight
                        ),
                        12,
                    )
                for symbol, weight
                in sorted(
                    target.items()
                )
            },
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = (
        hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        )
        .hexdigest()
    )

    return (
        "f100-v5002-"
        + state_date.replace(
            "-",
            "",
        )
        + "-"
        + digest[
            :12
        ]
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

    allowed = (
        set(
            research_base.EQUITY_UNIVERSE
        )
        | {
            CORE_SYMBOL
        }
    )

    output = {}

    for item in positions:

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        if symbol not in allowed:

            raise RuntimeError(
                "SECURITY STOP: unexpected "
                f"broker position {symbol}"
            )

        market_value = float(
            item.get(
                "market_value",
                0.0,
            )
        )

        if market_value < 0:

            raise RuntimeError(
                f"{symbol}: negative market value."
            )

        output[
            symbol
        ] = (
            market_value
        )

    return output


# ============================================================
# PLAN
# ============================================================

def build_plan(
    target: dict,
    positions: dict,
):

    sleeve_value = sum(
        positions.values()
    )

    if sleeve_value <= 0:

        raise RuntimeError(
            "Fund-100 paper sleeve has "
            "no positive market value."
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

        current_value = float(
            positions.get(
                symbol,
                0.0,
            )
        )

        target_weight = float(
            target.get(
                symbol,
                0.0,
            )
        )

        target_value = (
            sleeve_value
            * target_weight
        )

        delta = (
            target_value
            - current_value
        )

        if delta > MIN_ACTION_USD:

            action = "BUY"

        elif delta < -MIN_ACTION_USD:

            action = "SELL"

        else:

            action = "HOLD"

        rows.append({
            "symbol":
                symbol,

            "current_value":
                current_value,

            "target_weight":
                target_weight,

            "target_value":
                target_value,

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
        "FUND-100 V5-002 BROKER EVENT GATE"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "Broker endpoint: ALPACA PAPER"
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

    # ========================================================
    # KILL SWITCH
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "EVENT-GATE SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch state: PASS"
    )

    # ========================================================
    # STATE / EVENT
    # ========================================================

    state = (
        load_state()
    )

    print(
        f"\nV5-002 shadow state date: "
        f"{state['last_date']}"
    )

    (
        target,
        source,
        synthetic,
    ) = (
        load_event_target(
            state
        )
    )

    if target is None:

        print(
            "\n============================================"
        )

        print(
            "NO STRATEGY EXECUTION EVENT"
        )

        print(
            "============================================"
        )

        print(
            "\nV5-002 pending_target: NONE"
        )

        print(
            "Broker rebalance required: NO"
        )

        print(
            "Orders submitted: 0"
        )

        print(
            "Broker state modified: NO"
        )

        return

    event_id = (
        build_event_id(
            state_date=
                str(
                    state[
                        "last_date"
                    ]
                ),

            source=
                source,

            target=
                target,
        )
    )

    print(
        "\nStrategy execution event detected."
    )

    print(
        f"Event source: {source}"
    )

    print(
        f"Synthetic engineering test: "
        f"{synthetic}"
    )

    print(
        f"Deterministic event ID: "
        f"{event_id}"
    )

    # ========================================================
    # BROKER ACCOUNT
    # ========================================================

    key, secret = (
        broker.load_credentials()
    )

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
            "EVENT GATE STOP: "
            "broker currently has open orders."
        )

    print(
        "Open broker orders: 0 — PASS"
    )

    # ========================================================
    # MARKET CLOCK
    # ========================================================

    clock = (
        broker.get_json(
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
            "Invalid market-clock response."
        )

    print(
        f"US market currently open: "
        f"{bool(clock.get('is_open', False))}"
    )

    print(
        f"Next market close: "
        f"{clock.get('next_close', 'unknown')}"
    )

    # ========================================================
    # BROKER POSITIONS
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
        f"Broker positions loaded: "
        f"{len(positions)}"
    )

    # ========================================================
    # EVENT PLAN
    # ========================================================

    (
        sleeve_value,
        rows,
    ) = (
        build_plan(
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
        "EVENT-DRIVEN REBALANCE PLAN"
    )

    print(
        "============================================"
    )

    print(
        f"\nCurrent paper sleeve: "
        f"${sleeve_value:.2f}"
    )

    buys = 0.0
    sells = 0.0
    actions = 0

    for row in rows:

        print(
            f"\n{row['symbol']}"
        )

        print(
            f"  Current: "
            f"${row['current_value']:.2f}"
        )

        print(
            f"  Target: "
            f"${row['target_value']:.2f} "
            f"({row['target_weight']:.2%})"
        )

        if (
            row[
                "action"
            ]
            == "BUY"
        ):

            amount = float(
                row[
                    "delta"
                ]
            )

            print(
                f"  PLAN: BUY ${amount:.2f}"
            )

            buys += amount
            actions += 1

        elif (
            row[
                "action"
            ]
            == "SELL"
        ):

            amount = abs(
                float(
                    row[
                        "delta"
                    ]
                )
            )

            print(
                f"  PLAN: SELL ${amount:.2f}"
            )

            sells += amount
            actions += 1

        else:

            print(
                "  PLAN: HOLD"
            )

    print(
        "\n============================================"
    )

    print(
        "BROKER EVENT GATE: PASS"
    )

    print(
        "============================================"
    )

    print(
        f"\nActionable trades: "
        f"{actions}"
    )

    print(
        f"Planned buys: "
        f"${buys:.2f}"
    )

    print(
        f"Planned sells: "
        f"${sells:.2f}"
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
        "Kill switch remained: ENGAGED"
    )

    if synthetic:

        print(
            "\nSynthetic target was used only "
            "to test event planning."
        )

        print(
            "V5-002 shadow state was NOT changed."
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
            "BROKER EVENT GATE: FAILED",
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

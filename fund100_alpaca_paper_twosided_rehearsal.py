from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import fund100_alpaca_paper_reconcile as broker
import fund100_alpaca_paper_execute_bootstrap as bootstrap
import fund100_alpaca_event_gate as gate

from fund100_broker_safety import (
    require_broker_writes_allowed,
)


# ============================================================
# FUND-100 ALPACA PAPER TWO-SIDED REHEARSAL v1.0
# ============================================================
#
# PAPER ONLY.
#
# Purpose:
#
#   1. Create a synthetic ~2% redistribution between two
#      existing V5-002 satellite positions.
#   2. Execute SELL first, then BUY.
#   3. Verify fills.
#   4. Restore the genuine V5-002 executed target.
#   5. Verify final portfolio is close to the real target.
#
# V5-002 shadow state itself is NEVER changed.
#
# Hard-coded Alpaca PAPER endpoint only.
# ============================================================


PAPER_BASE_URL = (
    "https://paper-api.alpaca.markets"
)

EXPECTED_HOST = (
    "paper-api.alpaca.markets"
)

REHEARSAL_ARM = (
    "YES_PAPER_ONLY_REHEARSAL"
)

SHIFT_WEIGHT = 0.02

MIN_ORDER_NOTIONAL = 1.00

FINAL_WEIGHT_TOLERANCE = 0.005

POLL_ATTEMPTS = 30

POLL_SECONDS = 1


# ============================================================
# PAPER ENDPOINT SAFETY
# ============================================================

def validate_paper_url(
    url: str,
):

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_HOST
    ):

        raise RuntimeError(
            "SECURITY STOP: non-paper "
            "broker endpoint."
        )


# ============================================================
# REHEARSAL ARM
# ============================================================

def require_rehearsal_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_SYNTHETIC_PAPER_REHEARSAL",
            "",
        )
        .strip()
    )

    if value != REHEARSAL_ARM:

        raise RuntimeError(
            "Synthetic paper rehearsal is "
            "not explicitly armed."
        )


# ============================================================
# GENERIC PAPER NOTIONAL ORDER
# ============================================================

def submit_notional_order(
    symbol: str,
    side: str,
    notional: float,
    client_order_id: str,
    key: str,
    secret: str,
):

    require_broker_writes_allowed()

    if side not in {
        "buy",
        "sell",
    }:

        raise RuntimeError(
            f"Invalid order side: {side}"
        )

    if notional < MIN_ORDER_NOTIONAL:

        raise RuntimeError(
            f"{symbol}: requested paper notional "
            f"${notional:.2f} is below the "
            "rehearsal minimum."
        )

    url = (
        PAPER_BASE_URL
        + "/v2/orders"
    )

    validate_paper_url(
        url
    )

    payload = {
        "symbol":
            symbol,

        "notional":
            f"{notional:.2f}",

        "side":
            side,

        "type":
            "market",

        "time_in_force":
            "day",

        "extended_hours":
            False,

        "client_order_id":
            client_order_id,
    }

    request = Request(
        url=url,
        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),
        method="POST",
        headers={
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",

            "APCA-API-KEY-ID":
                key,

            "APCA-API-SECRET-KEY":
                secret,

            "User-Agent":
                "Fund-100-Paper-Two-Sided-Rehearsal/1.0",
        },
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
            f"{symbol}: Alpaca paper order rejected. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            f"{symbol}: paper API unavailable."
        ) from exc


# ============================================================
# WAIT FOR FILL
# ============================================================

def wait_for_fill(
    client_order_id: str,
    key: str,
    secret: str,
):

    for _ in range(
        POLL_ATTEMPTS
    ):

        order = (
            bootstrap.get_order_by_client_id(
                client_order_id=
                    client_order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if order is None:

            time.sleep(
                POLL_SECONDS
            )

            continue

        status = str(
            order.get(
                "status",
                "",
            )
        ).lower()

        if status == "filled":

            return order

        if status in {
            "canceled",
            "expired",
            "rejected",
            "suspended",
        }:

            raise RuntimeError(
                f"Order {client_order_id} "
                f"ended with status={status}."
            )

        time.sleep(
            POLL_SECONDS
        )

    raise RuntimeError(
        f"Timed out waiting for "
        f"{client_order_id} to fill."
    )


# ============================================================
# IDEMPOTENT ORDER
# ============================================================

def ensure_order(
    symbol: str,
    side: str,
    notional: float,
    client_order_id: str,
    key: str,
    secret: str,
):

    existing = (
        bootstrap.get_order_by_client_order_id(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )
        if hasattr(
            bootstrap,
            "get_order_by_client_order_id",
        )
        else
        bootstrap.get_order_by_client_id(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )
    )

    if existing is not None:

        status = str(
            existing.get(
                "status",
                "unknown",
            )
        )

        print(
            f"{symbol}: existing rehearsal "
            f"order found ({status})"
        )

        return wait_for_fill(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )

    print(
        f"{symbol}: PAPER {side.upper()} "
        f"${notional:.2f}"
    )

    submit_notional_order(
        symbol=
            symbol,

        side=
            side,

        notional=
            notional,

        client_order_id=
            client_order_id,

        key=
            key,

        secret=
            secret,
    )

    return wait_for_fill(
        client_order_id=
            client_order_id,

        key=
            key,

        secret=
            secret,
    )


# ============================================================
# REAL V5 TARGET
# ============================================================

def real_target(
    state: dict,
):

    return gate.normalise_target(
        state[
            "satellite_weights"
        ]
    )


# ============================================================
# SYNTHETIC TARGET
# ============================================================

def synthetic_target(
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
        in gate.research_base.EQUITY_UNIVERSE
    }

    ranked = sorted(
        [
            symbol
            for symbol, weight
            in satellites.items()
            if weight > 0.001
        ],
        key=lambda symbol:
            satellites[
                symbol
            ],
        reverse=True,
    )

    if len(
        ranked
    ) < 2:

        raise RuntimeError(
            "Not enough satellite positions "
            "for rehearsal."
        )

    donor = ranked[0]
    receiver = ranked[1]

    shift = min(
        SHIFT_WEIGHT,
        satellites[
            donor
        ] / 2.0,
        0.125
        - satellites[
            receiver
        ],
    )

    if shift < 0.015:

        raise RuntimeError(
            "Unable to construct sufficiently "
            "large safe rehearsal shift."
        )

    satellites[
        donor
    ] -= shift

    satellites[
        receiver
    ] += shift

    return (
        gate.normalise_target(
            satellites
        ),
        donor,
        receiver,
        shift,
    )


# ============================================================
# POSITIONS
# ============================================================

def current_market_values(
    key: str,
    secret: str,
):

    return gate.load_positions(
        key=
            key,

        secret=
            secret,
    )


# ============================================================
# CREATE TRADE PLAN
# ============================================================

def actionable_plan(
    target: dict,
    positions: dict,
):

    sleeve_value, rows = (
        gate.build_plan(
            target=
                target,

            positions=
                positions,
        )
    )

    actions = []

    for row in rows:

        if (
            row[
                "action"
            ]
            == "HOLD"
        ):

            continue

        amount = abs(
            float(
                row[
                    "delta"
                ]
            )
        )

        if amount < MIN_ORDER_NOTIONAL:

            continue

        actions.append({
            "symbol":
                row[
                    "symbol"
                ],

            "side":
                (
                    "buy"
                    if row[
                        "action"
                    ]
                    == "BUY"
                    else "sell"
                ),

            "notional":
                amount,
        })

    return (
        sleeve_value,
        actions,
    )


# ============================================================
# EXECUTE PLAN
# ============================================================

def execute_plan(
    actions: list[dict],
    prefix: str,
    key: str,
    secret: str,
):

    sells = [
        action
        for action
        in actions
        if action[
            "side"
        ]
        == "sell"
    ]

    buys = [
        action
        for action
        in actions
        if action[
            "side"
        ]
        == "buy"
    ]

    # Sell first so the rehearsal does not
    # depend on spare broker cash.

    for sequence in (
        sells,
        buys,
    ):

        for action in sequence:

            client_id = (
                prefix
                + "-"
                + action[
                    "side"
                ]
                + "-"
                + action[
                    "symbol"
                ].lower()
            )

            ensure_order(
                symbol=
                    action[
                        "symbol"
                    ],

                side=
                    action[
                        "side"
                    ],

                notional=
                    action[
                        "notional"
                    ],

                client_order_id=
                    client_id,

                key=
                    key,

                secret=
                    secret,
            )


# ============================================================
# FINAL TARGET CHECK
# ============================================================

def verify_real_target(
    target: dict,
    positions: dict,
):

    sleeve_value = sum(
        positions.values()
    )

    if sleeve_value <= 0:

        raise RuntimeError(
            "Paper sleeve is not positive."
        )

    failures = []

    print(
        "\nFinal restored weights:"
    )

    for symbol in sorted(
        set(
            target.keys()
        )
        | set(
            positions.keys()
        )
    ):

        current_weight = (
            float(
                positions.get(
                    symbol,
                    0.0,
                )
            )
            / sleeve_value
        )

        target_weight = float(
            target.get(
                symbol,
                0.0,
            )
        )

        difference = abs(
            current_weight
            - target_weight
        )

        print(
            f"{symbol}: "
            f"actual={current_weight:.3%}, "
            f"target={target_weight:.3%}, "
            f"diff={difference:.3%}"
        )

        if (
            difference
            > FINAL_WEIGHT_TOLERANCE
        ):

            failures.append(
                symbol
            )

    if failures:

        raise RuntimeError(
            "Restore reconciliation outside "
            "engineering tolerance for: "
            + ", ".join(
                failures
            )
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PAPER TWO-SIDED REHEARSAL"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA PAPER"
    )

    print(
        "Live endpoint capability: DISABLED"
    )

    print(
        "V5-002 shadow-state modification: DISABLED"
    )

    require_rehearsal_arm()

    require_broker_writes_allowed()

    print(
        "Synthetic rehearsal arm: PASS"
    )

    print(
        "Broker kill switch: DISENGAGED"
    )

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

    clock = (
        broker.get_json(
            path="/v2/clock",
            key=key,
            secret=secret,
        )
    )

    if not bool(
        clock.get(
            "is_open",
            False,
        )
    ):

        raise RuntimeError(
            "US regular market is closed. "
            "No rehearsal orders submitted."
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

    if len(
        open_orders
    ) != 0:

        raise RuntimeError(
            "Paper broker has open orders."
        )

    state = (
        gate.load_state()
    )

    if (
        state.get(
            "pending_target"
        )
        is not None
    ):

        raise RuntimeError(
            "Real V5-002 pending target exists. "
            "Synthetic rehearsal aborted."
        )

    actual_target = (
        real_target(
            state
        )
    )

    (
        test_target,
        donor,
        receiver,
        shift,
    ) = (
        synthetic_target(
            state
        )
    )

    print(
        f"\nSynthetic shift: "
        f"{shift:.2%}"
    )

    print(
        f"Donor: {donor}"
    )

    print(
        f"Receiver: {receiver}"
    )

    # ========================================================
    # STAGE A — SYNTHETIC SHIFT
    # ========================================================

    positions = (
        current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    sleeve_value, shift_actions = (
        actionable_plan(
            target=
                test_target,

            positions=
                positions,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "STAGE A — SYNTHETIC PAPER EVENT"
    )

    print(
        "============================================"
    )

    print(
        f"Paper sleeve: "
        f"${sleeve_value:.2f}"
    )

    for action in shift_actions:

        print(
            f"{action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    sides = {
        action[
            "side"
        ]
        for action
        in shift_actions
    }

    if not {
        "buy",
        "sell",
    }.issubset(
        sides
    ):

        raise RuntimeError(
            "Synthetic test did not produce "
            "both BUY and SELL actions."
        )

    execute_plan(
        actions=
            shift_actions,

        prefix=
            "f100-v5002-rehearsal-shift",

        key=
            key,

        secret=
            secret,
    )

    print(
        "Synthetic shift fills: PASS"
    )

    # ========================================================
    # STAGE B — RESTORE REAL V5 TARGET
    # ========================================================

    positions = (
        current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    sleeve_value, restore_actions = (
        actionable_plan(
            target=
                actual_target,

            positions=
                positions,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "STAGE B — RESTORE REAL V5-002 TARGET"
    )

    print(
        "============================================"
    )

    for action in restore_actions:

        print(
            f"{action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    execute_plan(
        actions=
            restore_actions,

        prefix=
            "f100-v5002-rehearsal-restore",

        key=
            key,

        secret=
            secret,
    )

    print(
        "Restore fills: PASS"
    )

    # ========================================================
    # FINAL RECONCILIATION
    # ========================================================

    time.sleep(
        1
    )

    final_positions = (
        current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    verify_real_target(
        target=
            actual_target,

        positions=
            final_positions,
    )

    remaining_orders = (
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

    if len(
        remaining_orders
    ) != 0:

        raise RuntimeError(
            "Open paper orders remain after rehearsal."
        )

    print(
        "\n============================================"
    )

    print(
        "TWO-SIDED PAPER REHEARSAL: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nFractional SELL path: PASS"
    )

    print(
        "Fractional BUY path: PASS"
    )

    print(
        "Deterministic order IDs: PASS"
    )

    print(
        "Fill polling: PASS"
    )

    print(
        "Real-target restoration: PASS"
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

    print(
        "\nIMPORTANT:"
    )

    print(
        "Re-engage FUND100_BROKER_KILL_SWITCH "
        "immediately after this test."
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
            "TWO-SIDED PAPER REHEARSAL: FAILED",
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

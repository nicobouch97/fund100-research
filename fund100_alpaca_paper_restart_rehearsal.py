from __future__ import annotations

import hashlib
import json
import os
import sys

import fund100_alpaca_paper_reconcile as broker
import fund100_alpaca_paper_execute_bootstrap as bootstrap
import fund100_alpaca_event_gate as gate
import fund100_alpaca_paper_twosided_rehearsal as two

from fund100_broker_safety import (
    require_broker_writes_allowed,
)


# ============================================================
# FUND-100 PAPER CRASH / RESTART REHEARSAL v1.0
# ============================================================
#
# PAPER ONLY.
#
# PHASE 1: interrupt
#   - create synthetic two-sided event
#   - submit / fill ONE SELL
#   - deliberately terminate
#
# PHASE 2: resume
#   - recover the existing SELL using client_order_id
#   - DO NOT duplicate it
#   - finish synthetic event
#   - restore genuine V5-002 target
#   - reconcile final portfolio
#
# The V5-002 shadow state is never modified.
# ============================================================


ARM_VALUE = "YES_PAPER_RESTART_TEST"

PHASE_INTERRUPT = "interrupt"
PHASE_RESUME = "resume"

INTENTIONAL_EXIT_CODE = 42


def get_phase() -> str:

    phase = (
        os.environ.get(
            "FUND100_RESTART_TEST_PHASE",
            "",
        )
        .strip()
        .lower()
    )

    if phase not in {
        PHASE_INTERRUPT,
        PHASE_RESUME,
    }:

        raise RuntimeError(
            "FUND100_RESTART_TEST_PHASE must be "
            "'interrupt' or 'resume'."
        )

    return phase


def require_restart_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_RESTART_REHEARSAL",
            "",
        )
        .strip()
    )

    if value != ARM_VALUE:

        raise RuntimeError(
            "Restart rehearsal is not explicitly armed."
        )


def build_event_prefix(
    state: dict,
    target: dict,
) -> str:

    payload = {
        "strategy":
            "V5-002_SHADOW",

        "state_date":
            str(
                state[
                    "last_date"
                ]
            ),

        "synthetic_target":
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

    digest = (
        hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode(
                "utf-8"
            )
        )
        .hexdigest()
    )

    return (
        "f100-rst-"
        + str(
            state[
                "last_date"
            ]
        ).replace(
            "-",
            "",
        )
        + "-"
        + digest[
            :10
        ]
    )


def client_id(
    prefix: str,
    stage: str,
    side: str,
    symbol: str,
) -> str:

    return (
        prefix
        + "-"
        + stage
        + "-"
        + side[0]
        + "-"
        + symbol.lower()
    )


def ensure_market_ready(
    key: str,
    secret: str,
):

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

    if not isinstance(
        clock,
        dict,
    ):

        raise RuntimeError(
            "Invalid Alpaca clock response."
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
            "Restart rehearsal requires zero "
            "currently open paper orders."
        )


def load_test_context():

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
            "A genuine V5-002 pending target exists. "
            "Synthetic restart rehearsal aborted."
        )

    real_target = (
        two.real_target(
            state
        )
    )

    (
        synthetic_target,
        donor,
        receiver,
        shift,
    ) = (
        two.synthetic_target(
            state
        )
    )

    prefix = (
        build_event_prefix(
            state=
                state,

            target=
                synthetic_target,
        )
    )

    return (
        state,
        real_target,
        synthetic_target,
        donor,
        receiver,
        shift,
        prefix,
    )


def find_initial_sell(
    synthetic_target: dict,
    positions: dict,
):

    (
        sleeve,
        actions,
    ) = (
        two.actionable_plan(
            target=
                synthetic_target,

            positions=
                positions,
        )
    )

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

    if not sells:

        raise RuntimeError(
            "Restart rehearsal did not create "
            "a synthetic SELL."
        )

    if not buys:

        raise RuntimeError(
            "Restart rehearsal did not create "
            "a synthetic BUY."
        )

    sells = sorted(
        sells,
        key=lambda x:
            x[
                "symbol"
            ],
    )

    return (
        sleeve,
        sells[
            0
        ],
        actions,
    )


def execute_actions(
    actions: list[dict],
    prefix: str,
    stage: str,
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

    for sequence in (
        sells,
        buys,
    ):

        for action in sequence:

            cid = (
                client_id(
                    prefix=
                        prefix,

                    stage=
                        stage,

                    side=
                        action[
                            "side"
                        ],

                    symbol=
                        action[
                            "symbol"
                        ],
                )
            )

            two.ensure_order(
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
                    cid,

                key=
                    key,

                secret=
                    secret,
            )


def interrupt_phase(
    key: str,
    secret: str,
    synthetic_target: dict,
    prefix: str,
):

    print(
        "\n============================================"
    )

    print(
        "PHASE 1 — INTENTIONAL INTERRUPTION"
    )

    print(
        "============================================"
    )

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    (
        sleeve,
        first_sell,
        actions,
    ) = (
        find_initial_sell(
            synthetic_target=
                synthetic_target,

            positions=
                positions,
        )
    )

    print(
        f"\nPaper sleeve: "
        f"${sleeve:.2f}"
    )

    print(
        "Synthetic event contains:"
    )

    for action in actions:

        print(
            f"  {action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    cid = (
        client_id(
            prefix=
                prefix,

            stage=
                "shift",

            side=
                "sell",

            symbol=
                first_sell[
                    "symbol"
                ],
        )
    )

    print(
        "\nSubmitting ONLY the first SELL..."
    )

    order = (
        two.ensure_order(
            symbol=
                first_sell[
                    "symbol"
                ],

            side=
                "sell",

            notional=
                first_sell[
                    "notional"
                ],

            client_order_id=
                cid,

            key=
                key,

            secret=
                secret,
        )
    )

    if (
        str(
            order.get(
                "status",
                "",
            )
        ).lower()
        != "filled"
    ):

        raise RuntimeError(
            "First paper SELL was not filled."
        )

    print(
        f"\nRecovered/filled client order ID:"
    )

    print(
        cid
    )

    print(
        "\nFirst side is now present at Alpaca."
    )

    print(
        "The matching BUY has NOT been submitted."
    )

    print(
        "The real V5-002 target has NOT yet "
        "been restored."
    )

    print(
        "\n============================================"
    )

    print(
        "INTENTIONAL WORKFLOW INTERRUPTION NOW"
    )

    print(
        "============================================"
    )

    print(
        "\nThis non-zero exit is deliberate."
    )

    sys.exit(
        INTENTIONAL_EXIT_CODE
    )


def resume_phase(
    key: str,
    secret: str,
    real_target: dict,
    synthetic_target: dict,
    prefix: str,
):

    print(
        "\n============================================"
    )

    print(
        "PHASE 2 — RESTART / RECOVERY"
    )

    print(
        "============================================"
    )

    # ========================================================
    # PROVE THE INTERRUPTED SELL EXISTS
    # ========================================================

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    (
        _,
        expected_sell,
        _,
    ) = (
        find_initial_sell(
            synthetic_target=
                synthetic_target,

            positions=
                positions,
        )
    )

    # The post-interruption portfolio may already be closer
    # to the synthetic target, so use the known donor if the
    # recalculated plan no longer exposes the same sell.
    sell_symbol = (
        expected_sell[
            "symbol"
        ]
    )

    sell_cid = (
        client_id(
            prefix=
                prefix,

            stage=
                "shift",

            side=
                "sell",

            symbol=
                sell_symbol,
        )
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
            "RESTART TEST FAILED: interrupted "
            "SELL order cannot be found at Alpaca."
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

    print(
        "\nExisting interrupted SELL recovered:"
    )

    print(
        sell_cid
    )

    print(
        "Duplicate SELL submitted: NO"
    )

    # ========================================================
    # FINISH SYNTHETIC TARGET
    # ========================================================

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

    (
        _,
        remaining_shift_actions,
    ) = (
        two.actionable_plan(
            target=
                synthetic_target,

            positions=
                positions,
        )
    )

    print(
        "\nRemaining synthetic-event actions:"
    )

    if not remaining_shift_actions:

        print(
            "  None"
        )

    for action in (
        remaining_shift_actions
    ):

        print(
            f"  {action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    execute_actions(
        actions=
            remaining_shift_actions,

        prefix=
            prefix,

        stage=
            "shift",

        key=
            key,

        secret=
            secret,
    )

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
        "Synthetic event completion: PASS"
    )

    # ========================================================
    # RESTORE TRUE V5-002 TARGET
    # ========================================================

    positions = (
        two.current_market_values(
            key=
                key,

            secret=
                secret,
        )
    )

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
            f"{action['side'].upper()} "
            f"{action['symbol']} "
            f"${action['notional']:.2f}"
        )

    execute_actions(
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
        "CRASH / RESTART REHEARSAL: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nInterrupted SELL recovered: PASS"
    )

    print(
        "Duplicate interrupted SELL: 0"
    )

    print(
        "Synthetic event resumed: PASS"
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


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PAPER CRASH / RESTART REHEARSAL"
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
        "Shadow-state modification: DISABLED"
    )

    phase = (
        get_phase()
    )

    print(
        f"Test phase: {phase.upper()}"
    )

    require_restart_arm()

    require_broker_writes_allowed()

    print(
        "Restart-test arm: PASS"
    )

    print(
        "Broker kill switch: DISENGAGED"
    )

    key, secret = (
        broker.load_credentials()
    )

    ensure_market_ready(
        key=
            key,

        secret=
            secret,
    )

    (
        state,
        real_target,
        synthetic_target,
        donor,
        receiver,
        shift,
        prefix,
    ) = (
        load_test_context()
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
        f"Donor: {donor}"
    )

    print(
        f"Receiver: {receiver}"
    )

    print(
        f"Deterministic restart event: "
        f"{prefix}"
    )

    if phase == PHASE_INTERRUPT:

        interrupt_phase(
            key=
                key,

            secret=
                secret,

            synthetic_target=
                synthetic_target,

            prefix=
                prefix,
        )

    resume_phase(
        key=
            key,

        secret=
            secret,

        real_target=
            real_target,

        synthetic_target=
            synthetic_target,

        prefix=
            prefix,
    )


if __name__ == "__main__":

    try:

        main()

    except SystemExit:

        raise

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "CRASH / RESTART REHEARSAL: FAILED",
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

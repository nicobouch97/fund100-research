from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 EXECUTION ORCHESTRATOR REHEARSAL v1.0
# ============================================================
#
# COMPLETELY OFFLINE.
#
# NO Alpaca credentials.
# NO real broker network.
# NO LIVE GET.
# NO LIVE POST.
# NO order submission to Alpaca.
#
# This rehearsal simulates:
#
# - SELL -> process restart -> BUY
# - one cumulative permit ceiling
# - over-cap blocking before writer
# - lost-response recovery
# - duplicate POST suppression
# - partial-fill full-notional accounting
# - terminal-history fail-closed behavior
# - incomplete authorized-ID reconstruction
#
# ============================================================


SELL_ID = (
    "f100live-orch-rehearsal-s-acwi"
)

BUY_ID = (
    "f100live-orch-rehearsal-b-spy"
)

SAFE_STATUSES = {
    "new",
    "accepted",
    "pending_new",
    "partially_filled",
    "filled",
}

TERMINAL_UNSAFE = {
    "canceled",
    "cancelled",
    "expired",
    "rejected",
}


class OfflineBroker:

    def __init__(
        self,
    ):

        self.orders = {}

        self.snapshot_count = 0

        self.writer_calls = 0

        self.post_count = 0

        self.lose_response_once = set()


def release_lock():

    return {
        "version":
            "1.8",
        "execution_orchestrator_integration_required":
            True,
    }


def compiler():

    return {
        "authorized_client_order_ids": [
            SELL_ID,
            BUY_ID,
        ],
    }


def permit():

    return {
        "maximum_live_execution_notional_usd":
            "100",
    }


def utcnow():

    return datetime.now(
        timezone.utc
    )


def dependencies(
    *,
    broker: OfflineBroker,
    sell_notional="60",
    buy_notional="40",
    incomplete_history=False,
):

    sell_notional = Decimal(
        sell_notional
    )

    buy_notional = Decimal(
        buy_notional
    )


    def verify_release_lock(
        *,
        release_lock_package,
        **kwargs,
    ):

        if (
            release_lock_package.get(
                "version"
            )
            != "1.8"
        ):

            raise RuntimeError(
                "REHEARSAL STOP: release lock mismatch."
            )


    def reconstruct_broker_snapshot(
        **kwargs,
    ):

        broker.snapshot_count += 1

        return {
            "account": {
                "cash":
                    "100",
                "portfolio_value":
                    "100",
            },
            "positions": {},
            "open_orders": [],
        }


    def materialize_execution_phase(
        *,
        phase,
        **kwargs,
    ):

        if phase == "SELL":

            return {
                "orders": [
                    {
                        "symbol":
                            "ACWI",
                        "side":
                            "sell",
                        "notional_usd":
                            str(
                                sell_notional
                            ),
                        "client_order_id":
                            SELL_ID,
                    }
                ]
            }

        return {
            "orders": [
                {
                    "symbol":
                        "SPY",
                    "side":
                        "buy",
                    "notional_usd":
                        str(
                            buy_notional
                        ),
                    "client_order_id":
                        BUY_ID,
                }
            ]
        }


    def reconstruct_authorized_order_history(
        *,
        compiler_package,
        **kwargs,
    ):

        result = {}

        for client_id in (
            compiler_package[
                "authorized_client_order_ids"
            ]
        ):

            result[
                client_id
            ] = (
                broker.orders.get(
                    client_id
                )
            )

        if incomplete_history:

            result.pop(
                BUY_ID
            )

        return result


    def enforce_cumulative_cap(
        *,
        compiler_package,
        permit_package,
        authorized_order_history,
        new_orders,
        **kwargs,
    ):

        authorized_ids = set(
            compiler_package[
                "authorized_client_order_ids"
            ]
        )

        if (
            set(
                authorized_order_history
            )
            != authorized_ids
        ):

            raise RuntimeError(
                "CAP STOP: incomplete broker reconstruction."
            )

        historical = Decimal(
            "0"
        )

        for client_id in sorted(
            authorized_ids
        ):

            order = (
                authorized_order_history[
                    client_id
                ]
            )

            if order is None:
                continue

            status = (
                str(
                    order.get(
                        "status",
                        "",
                    )
                )
                .lower()
            )

            if status in TERMINAL_UNSAFE:

                raise RuntimeError(
                    "CAP STOP: unsafe terminal history."
                )

            if status not in SAFE_STATUSES:

                raise RuntimeError(
                    "CAP STOP: ambiguous order history."
                )

            # IMPORTANT:
            #
            # Use ORIGINAL submitted notional.
            # A partially-filled $60 order consumes $60 of the
            # permit ceiling, not merely the filled fraction.

            historical += Decimal(
                str(
                    order[
                        "notional_usd"
                    ]
                )
            )

        unseen = Decimal(
            "0"
        )

        for order in new_orders:

            client_id = (
                order[
                    "client_order_id"
                ]
            )

            if (
                authorized_order_history[
                    client_id
                ]
                is None
            ):

                unseen += Decimal(
                    str(
                        order[
                            "notional_usd"
                        ]
                    )
                )

        projected = (
            historical
            + unseen
        )

        ceiling = Decimal(
            str(
                permit_package[
                    "maximum_live_execution_notional_usd"
                ]
            )
        )

        if projected > ceiling:

            raise RuntimeError(
                "CAP STOP: cumulative permit ceiling exceeded."
            )

        return {
            "approved":
                True,
            "historical_notional_usd":
                str(
                    historical
                ),
            "new_unseen_notional_usd":
                str(
                    unseen
                ),
            "projected_notional_usd":
                str(
                    projected
                ),
            "permit_ceiling_usd":
                str(
                    ceiling
                ),
        }


    def submit_authorized_order_batch(
        *,
        orders,
        **kwargs,
    ):

        broker.writer_calls += 1

        results = []

        for order in orders:

            client_id = (
                order[
                    "client_order_id"
                ]
            )

            existing = (
                broker.orders.get(
                    client_id
                )
            )

            if existing is not None:

                results.append(
                    {
                        "client_order_id":
                            client_id,
                        "action":
                            "existing_order_recovered",
                    }
                )

                continue

            broker.post_count += 1

            broker.orders[
                client_id
            ] = {
                "client_order_id":
                    client_id,
                "symbol":
                    order[
                        "symbol"
                    ],
                "side":
                    order[
                        "side"
                    ],
                "notional_usd":
                    order[
                        "notional_usd"
                    ],
                "status":
                    "filled",
            }

            if (
                client_id
                in broker.lose_response_once
            ):

                broker.lose_response_once.remove(
                    client_id
                )

                raise RuntimeError(
                    "SIMULATED LOST RESPONSE AFTER BROKER ACCEPT."
                )

            results.append(
                {
                    "client_order_id":
                        client_id,
                    "action":
                        "fake_post",
                }
            )

        return {
            "results":
                results,
        }


    return (
        orchestrator.OrchestratorDependencies(
            verify_release_lock=(
                verify_release_lock
            ),
            reconstruct_broker_snapshot=(
                reconstruct_broker_snapshot
            ),
            materialize_execution_phase=(
                materialize_execution_phase
            ),
            reconstruct_authorized_order_history=(
                reconstruct_authorized_order_history
            ),
            enforce_cumulative_cap=(
                enforce_cumulative_cap
            ),
            submit_authorized_order_batch=(
                submit_authorized_order_batch
            ),
        )
    )


def run_phase(
    *,
    broker,
    phase,
    sell_notional="60",
    buy_notional="40",
    incomplete_history=False,
):

    return (
        orchestrator.run_execution_phase(
            release_lock_package=(
                release_lock()
            ),
            compiler_package=(
                compiler()
            ),
            permit_package=(
                permit()
            ),
            phase=(
                phase
            ),
            now=(
                utcnow()
            ),
            deps=(
                dependencies(
                    broker=broker,
                    sell_notional=(
                        sell_notional
                    ),
                    buy_notional=(
                        buy_notional
                    ),
                    incomplete_history=(
                        incomplete_history
                    ),
                )
            ),
        )
    )


def exact_cap_case():

    broker = OfflineBroker()

    sell = run_phase(
        broker=broker,
        phase="SELL",
        sell_notional="60",
        buy_notional="40",
    )

    # Simulated process restart:
    #
    # The second invocation receives a newly-created dependency
    # bundle and reconstructs prior expenditure only from the
    # fake broker's observed order history.

    buy = run_phase(
        broker=broker,
        phase="BUY",
        sell_notional="60",
        buy_notional="40",
    )

    assert (
        sell[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "60"
    )

    assert (
        buy[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "100"
    )

    assert (
        broker.snapshot_count
        == 2
    )

    assert (
        broker.post_count
        == 2
    )

    return True


def over_cap_case():

    broker = OfflineBroker()

    run_phase(
        broker=broker,
        phase="SELL",
        sell_notional="60",
        buy_notional="41",
    )

    writer_calls_before = (
        broker.writer_calls
    )

    posts_before = (
        broker.post_count
    )

    blocked = False

    try:

        run_phase(
            broker=broker,
            phase="BUY",
            sell_notional="60",
            buy_notional="41",
        )

    except RuntimeError as exc:

        blocked = (
            "CAP STOP"
            in str(
                exc
            )
        )

    assert blocked is True

    assert (
        broker.writer_calls
        == writer_calls_before
    )

    assert (
        broker.post_count
        == posts_before
    )

    return True


def lost_response_case():

    broker = OfflineBroker()

    broker.lose_response_once.add(
        SELL_ID
    )

    lost = False

    try:

        run_phase(
            broker=broker,
            phase="SELL",
        )

    except RuntimeError as exc:

        lost = (
            "SIMULATED LOST RESPONSE"
            in str(
                exc
            )
        )

    assert lost is True

    assert (
        broker.post_count
        == 1
    )

    # Process restart.
    #
    # Broker already contains SELL_ID, so replay must recover
    # the existing order instead of posting again.

    recovered = run_phase(
        broker=broker,
        phase="SELL",
    )

    assert (
        broker.post_count
        == 1
    )

    assert (
        recovered[
            "cap_proof"
        ][
            "historical_notional_usd"
        ]
        == "60"
    )

    return True


def partial_fill_case():

    broker = OfflineBroker()

    broker.orders[
        SELL_ID
    ] = {
        "client_order_id":
            SELL_ID,
        "symbol":
            "ACWI",
        "side":
            "sell",
        "notional_usd":
            "60",
        "filled_notional_usd":
            "10",
        "status":
            "partially_filled",
    }

    buy = run_phase(
        broker=broker,
        phase="BUY",
        buy_notional="40",
    )

    assert (
        buy[
            "cap_proof"
        ][
            "historical_notional_usd"
        ]
        == "60"
    )

    assert (
        buy[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "100"
    )

    return True


def unsafe_terminal_case():

    broker = OfflineBroker()

    broker.orders[
        SELL_ID
    ] = {
        "client_order_id":
            SELL_ID,
        "symbol":
            "ACWI",
        "side":
            "sell",
        "notional_usd":
            "60",
        "status":
            "rejected",
    }

    blocked = False

    try:

        run_phase(
            broker=broker,
            phase="BUY",
        )

    except RuntimeError as exc:

        blocked = (
            "unsafe terminal"
            in str(
                exc
            )
        )

    assert blocked is True

    assert (
        broker.writer_calls
        == 0
    )

    return True


def incomplete_history_case():

    broker = OfflineBroker()

    blocked = False

    try:

        run_phase(
            broker=broker,
            phase="SELL",
            incomplete_history=True,
        )

    except RuntimeError as exc:

        blocked = (
            "incomplete broker reconstruction"
            in str(
                exc
            )
        )

    assert blocked is True

    assert (
        broker.writer_calls
        == 0
    )

    return True


def run_rehearsal():

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "REHEARSAL STOP: "
            "candidate transport unexpectedly released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "REHEARSAL STOP: "
            "candidate public execution unexpectedly enabled."
        )

    if (
        orchestrator.ORCHESTRATOR_RELEASED
        is not False
    ):

        raise RuntimeError(
            "REHEARSAL STOP: "
            "orchestrator unexpectedly released."
        )

    if not Path(
        "fund100_pre_live_release_lock_v1_8.py"
    ).exists():

        raise RuntimeError(
            "REHEARSAL STOP: "
            "Release Lock v1.8 source is missing."
        )

    results = {
        "schema":
            "FUND100_EXECUTION_ORCHESTRATOR_REHEARSAL_V1",
        "release_lock_v1_8_source_present":
            True,
        "writer_candidate_v1_1_transport_released":
            False,
        "writer_candidate_v1_1_public_execution_enabled":
            False,
        "orchestrator_released":
            False,
        "broker_mode":
            "COMPLETELY_OFFLINE",
        "real_broker_network_access":
            "NONE",
        "broker_credentials_accessed":
            False,
        "exact_cap_across_sell_restart_buy":
            exact_cap_case(),
        "over_cap_blocked_before_writer":
            over_cap_case(),
        "lost_response_restart_reconstruction":
            lost_response_case(),
        "restart_duplicate_post_prevention":
            True,
        "partial_fill_full_notional_accounting":
            partial_fill_case(),
        "unsafe_terminal_history_blocked":
            unsafe_terminal_case(),
        "incomplete_history_blocked":
            incomplete_history_case(),
        "orders_submitted_to_alpaca":
            0,
    }

    return results


def main():

    results = run_rehearsal()

    output_dir = Path(
        "live_activation_outputs/v5_002"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / (
            "execution_orchestrator_"
            "rehearsal_v1_0.json"
        )
    )

    output_path.write_text(
        json.dumps(
            results,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 EXECUTION ORCHESTRATOR "
        "REHEARSAL COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Release Lock v1.8 source: PRESENT"
    )

    print(
        "Writer candidate v1.1: HARD LOCKED"
    )

    print(
        "Execution orchestrator v1.0: "
        "OFFLINE ONLY"
    )

    print(
        "Fresh broker reconstruction per phase: PASS"
    )

    print(
        "SELL -> restart -> BUY cumulative accounting: PASS"
    )

    print(
        "Exact single permit ceiling: PASS"
    )

    print(
        "Over-cap phase: BLOCKED BEFORE WRITER"
    )

    print(
        "Lost-response reconstruction: PASS"
    )

    print(
        "Restart duplicate POST prevention: PASS"
    )

    print(
        "Partial-fill full-notional accounting: PASS"
    )

    print(
        "Unsafe terminal history: BLOCKED"
    )

    print(
        "Incomplete broker reconstruction: BLOCKED"
    )

    print(
        "Real Alpaca credentials accessed: NO"
    )

    print(
        "Real broker network access: NONE"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Orchestrator released: FALSE"
    )

    print(
        "Orders submitted to Alpaca: 0"
    )

    print(
        "Evidence: "
        + str(
            output_path
        )
    )


if __name__ == "__main__":
    main()

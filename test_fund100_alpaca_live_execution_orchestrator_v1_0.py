from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


SELL_ID = (
    "f100live-orchestrator-s-acwi"
)

BUY_ID = (
    "f100live-orchestrator-b-spy"
)


def now():
    return datetime.now(
        timezone.utc
    )


def release_lock():
    return {
        "version":
            "1.8",
        "execution_orchestrator_integration_required":
            True,
    }


def compiler():
    return {
        "schema":
            "TEST_COMPILER",
        "authorized_client_order_ids": [
            SELL_ID,
            BUY_ID,
        ],
    }


def permit(
    ceiling: str = "100",
):
    return {
        "schema":
            "TEST_PERMIT",
        "maximum_live_execution_notional_usd":
            ceiling,
    }


class Harness:

    def __init__(
        self,
        *,
        sell_notional="60",
        buy_notional="40",
    ):

        self.sell_notional = Decimal(
            sell_notional
        )

        self.buy_notional = Decimal(
            buy_notional
        )

        self.events = []

        self.snapshot_calls = 0

        self.writer_calls = 0

        self.post_count = 0

        self.history = {}


    def verify_release_lock(
        self,
        **kwargs,
    ):

        self.events.append(
            "lock"
        )


    def reconstruct_broker_snapshot(
        self,
        **kwargs,
    ):

        self.events.append(
            "broker"
        )

        self.snapshot_calls += 1

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
        self,
        *,
        phase,
        **kwargs,
    ):

        self.events.append(
            "materialize"
        )

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
                                self.sell_notional
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
                            self.buy_notional
                        ),
                    "client_order_id":
                        BUY_ID,
                }
            ]
        }


    def reconstruct_authorized_order_history(
        self,
        *,
        compiler_package,
        **kwargs,
    ):

        self.events.append(
            "history"
        )

        result = {}

        for client_id in (
            compiler_package[
                "authorized_client_order_ids"
            ]
        ):

            result[
                client_id
            ] = (
                self.history.get(
                    client_id
                )
            )

        return result


    def enforce_cumulative_cap(
        self,
        *,
        compiler_package,
        permit_package,
        authorized_order_history,
        new_orders,
        **kwargs,
    ):

        self.events.append(
            "cap"
        )

        expected = set(
            compiler_package[
                "authorized_client_order_ids"
            ]
        )

        actual = set(
            authorized_order_history
        )

        if actual != expected:

            raise RuntimeError(
                "CAP STOP: incomplete reconstruction."
            )

        historical = Decimal(
            "0"
        )

        for client_id in sorted(
            expected
        ):

            broker_order = (
                authorized_order_history[
                    client_id
                ]
            )

            if broker_order is None:
                continue

            status = (
                str(
                    broker_order.get(
                        "status",
                        "",
                    )
                )
                .lower()
            )

            if status in {
                "canceled",
                "cancelled",
                "expired",
                "rejected",
            }:

                raise RuntimeError(
                    "CAP STOP: unsafe terminal history."
                )

            if status not in {
                "new",
                "accepted",
                "pending_new",
                "partially_filled",
                "filled",
            }:

                raise RuntimeError(
                    "CAP STOP: ambiguous history."
                )

            historical += Decimal(
                str(
                    broker_order[
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
                "CAP STOP: projected cumulative "
                "notional exceeds permit ceiling."
            )

        return {
            "approved":
                True,
            "historical_notional_usd":
                str(
                    historical
                ),
            "unseen_notional_usd":
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
        self,
        *,
        orders,
        **kwargs,
    ):

        self.events.append(
            "writer"
        )

        self.writer_calls += 1

        results = []

        for order in orders:

            client_id = (
                order[
                    "client_order_id"
                ]
            )

            existing = (
                self.history.get(
                    client_id
                )
            )

            if existing is not None:

                results.append(
                    {
                        "client_order_id":
                            client_id,
                        "result":
                            "existing",
                    }
                )

                continue

            self.post_count += 1

            self.history[
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

            results.append(
                {
                    "client_order_id":
                        client_id,
                    "result":
                        "submitted",
                }
            )

        return {
            "results":
                results,
        }


    def deps(
        self,
    ):

        return (
            orchestrator.OrchestratorDependencies(
                verify_release_lock=(
                    self.verify_release_lock
                ),
                reconstruct_broker_snapshot=(
                    self.reconstruct_broker_snapshot
                ),
                materialize_execution_phase=(
                    self.materialize_execution_phase
                ),
                reconstruct_authorized_order_history=(
                    self.reconstruct_authorized_order_history
                ),
                enforce_cumulative_cap=(
                    self.enforce_cumulative_cap
                ),
                submit_authorized_order_batch=(
                    self.submit_authorized_order_batch
                ),
            )
        )


def run_phase(
    harness,
    phase,
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
                now()
            ),
            deps=(
                harness.deps()
            ),
        )
    )


def test_writer_candidate_remains_hard_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_orchestrator_itself_is_not_released():

    assert (
        orchestrator.ORCHESTRATOR_RELEASED
        is False
    )

    assert (
        orchestrator.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_exact_required_call_order():

    harness = Harness()

    result = run_phase(
        harness,
        "SELL",
    )

    assert (
        harness.events
        == [
            "lock",
            "broker",
            "materialize",
            "history",
            "cap",
            "writer",
        ]
    )

    assert (
        result[
            "trace"
        ]
        == [
            "release_lock_verified",
            "broker_snapshot_reconstructed",
            "phase_materialized",
            "authorized_history_reconstructed",
            "cumulative_cap_approved",
            "writer_invoked",
        ]
    )


def test_cap_failure_blocks_writer():

    harness = Harness(
        sell_notional="101",
    )

    with pytest.raises(
        RuntimeError,
        match="CAP STOP",
    ):

        run_phase(
            harness,
            "SELL",
        )

    assert (
        harness.writer_calls
        == 0
    )

    assert (
        harness.post_count
        == 0
    )

    assert (
        harness.events
        == [
            "lock",
            "broker",
            "materialize",
            "history",
            "cap",
        ]
    )


def test_sell_then_restart_then_buy_uses_one_ceiling():

    harness = Harness(
        sell_notional="60",
        buy_notional="40",
    )

    sell = run_phase(
        harness,
        "SELL",
    )

    assert (
        sell[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "60"
    )

    # Simulated process restart:
    #
    # run_execution_phase has no local cumulative state.
    # A fresh dependency object is reconstructed from the
    # broker-observed history retained by the fake broker.

    restarted_deps = (
        harness.deps()
    )

    buy = (
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
            phase="BUY",
            now=now(),
            deps=restarted_deps,
        )
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

    assert (
        harness.snapshot_calls
        == 2
    )

    assert (
        harness.post_count
        == 2
    )


def test_over_cap_buy_after_restart_is_blocked_before_writer():

    harness = Harness(
        sell_notional="60",
        buy_notional="41",
    )

    run_phase(
        harness,
        "SELL",
    )

    writer_calls_before = (
        harness.writer_calls
    )

    posts_before = (
        harness.post_count
    )

    with pytest.raises(
        RuntimeError,
        match="CAP STOP",
    ):

        run_phase(
            harness,
            "BUY",
        )

    assert (
        harness.writer_calls
        == writer_calls_before
    )

    assert (
        harness.post_count
        == posts_before
    )


def test_existing_client_id_is_not_double_counted():

    harness = Harness(
        sell_notional="60",
    )

    harness.history[
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
            "filled",
    }

    result = run_phase(
        harness,
        "SELL",
    )

    assert (
        result[
            "cap_proof"
        ][
            "historical_notional_usd"
        ]
        == "60"
    )

    assert (
        result[
            "cap_proof"
        ][
            "unseen_notional_usd"
        ]
        == "0"
    )

    assert (
        result[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "60"
    )

    assert (
        harness.post_count
        == 0
    )


def test_partial_fill_consumes_full_original_notional():

    harness = Harness(
        buy_notional="40",
    )

    harness.history[
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
            "partially_filled",
        "filled_notional_usd":
            "10",
    }

    result = run_phase(
        harness,
        "BUY",
    )

    assert (
        result[
            "cap_proof"
        ][
            "historical_notional_usd"
        ]
        == "60"
    )

    assert (
        result[
            "cap_proof"
        ][
            "projected_notional_usd"
        ]
        == "100"
    )


def test_failed_terminal_history_blocks_continuation():

    harness = Harness()

    harness.history[
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

    with pytest.raises(
        RuntimeError,
        match="unsafe terminal",
    ):

        run_phase(
            harness,
            "BUY",
        )

    assert (
        harness.writer_calls
        == 0
    )


def test_incomplete_authorized_history_blocks_writer():

    harness = Harness()

    original = (
        harness.reconstruct_authorized_order_history
    )

    def incomplete(
        **kwargs,
    ):

        result = original(
            **kwargs
        )

        result.pop(
            BUY_ID
        )

        return result

    deps = (
        orchestrator.OrchestratorDependencies(
            verify_release_lock=(
                harness.verify_release_lock
            ),
            reconstruct_broker_snapshot=(
                harness.reconstruct_broker_snapshot
            ),
            materialize_execution_phase=(
                harness.materialize_execution_phase
            ),
            reconstruct_authorized_order_history=(
                incomplete
            ),
            enforce_cumulative_cap=(
                harness.enforce_cumulative_cap
            ),
            submit_authorized_order_batch=(
                harness.submit_authorized_order_batch
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="incomplete reconstruction",
    ):

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
            phase="SELL",
            now=now(),
            deps=deps,
        )

    assert (
        harness.writer_calls
        == 0
    )


def test_invalid_phase_fails_before_any_dependency_runs():

    harness = Harness()

    with pytest.raises(
        orchestrator.OrchestrationStop,
        match="invalid execution phase",
    ):

        run_phase(
            harness,
            "HOLD",
        )

    assert (
        harness.events
        == []
    )

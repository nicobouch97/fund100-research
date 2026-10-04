from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


# ============================================================
# FUND-100 LIVE EXECUTION ORCHESTRATOR v1.0
# ============================================================
#
# PURE / OFFLINE ORCHESTRATION CORE.
#
# NO broker credentials.
# NO HTTP.
# NO GET.
# NO POST.
# NO persistence.
# NO environment-variable access.
# NO automatic activation.
#
# The purpose of this module is to enforce the ordering:
#
#   release lock
#       ->
#   fresh broker reconstruction
#       ->
#   phase materialization
#       ->
#   complete authorized-client-ID reconstruction
#       ->
#   cumulative permit-cap guard
#       ->
#   writer
#
# The writer must NEVER be reachable before the cumulative-cap
# guard has approved the current broker-reconstructed state.
#
# Each phase invocation is intentionally STATELESS. A process
# restart therefore cannot rely on an in-memory "spent" value.
# Prior permit consumption must be reconstructed from broker-
# observed client_order_id history.
#
# ============================================================


ORCHESTRATOR_SCHEMA = (
    "FUND100_LIVE_EXECUTION_ORCHESTRATOR_V1"
)

ORCHESTRATOR_RELEASED = False
PUBLIC_EXECUTION_ENABLED = False

VALID_PHASES = {
    "SELL",
    "BUY",
}


class OrchestrationStop(RuntimeError):
    """
    Fail-closed execution-orchestration stop.
    """


@dataclass(frozen=True)
class OrchestratorDependencies:
    """
    All side-effect-capable operations are injected.

    The production binding is deliberately NOT released here.

    Offline rehearsals can provide in-memory implementations,
    while a future reviewed connected binding can point these
    interfaces at the already reviewed Fund-100 components.
    """

    verify_release_lock: Callable[..., Any]

    reconstruct_broker_snapshot: Callable[..., dict]

    materialize_execution_phase: Callable[..., dict]

    reconstruct_authorized_order_history: Callable[..., dict]

    enforce_cumulative_cap: Callable[..., dict]

    submit_authorized_order_batch: Callable[..., Any]


def _require_callable(
    name: str,
    value: Any,
) -> None:

    if not callable(value):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            f"dependency {name!r} is not callable."
        )


def validate_dependencies(
    deps: OrchestratorDependencies,
) -> None:

    _require_callable(
        "verify_release_lock",
        deps.verify_release_lock,
    )

    _require_callable(
        "reconstruct_broker_snapshot",
        deps.reconstruct_broker_snapshot,
    )

    _require_callable(
        "materialize_execution_phase",
        deps.materialize_execution_phase,
    )

    _require_callable(
        "reconstruct_authorized_order_history",
        deps.reconstruct_authorized_order_history,
    )

    _require_callable(
        "enforce_cumulative_cap",
        deps.enforce_cumulative_cap,
    )

    _require_callable(
        "submit_authorized_order_batch",
        deps.submit_authorized_order_batch,
    )


def validate_now(
    now: datetime,
) -> None:

    if not isinstance(
        now,
        datetime,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: now must be datetime."
        )

    if (
        now.tzinfo
        is None
        or now.utcoffset()
        is None
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: now must be timezone-aware."
        )


def validate_phase(
    phase: str,
) -> str:

    phase_normalized = (
        str(
            phase
        )
        .strip()
        .upper()
    )

    if (
        phase_normalized
        not in VALID_PHASES
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            f"invalid execution phase {phase!r}."
        )

    return phase_normalized


def validate_broker_snapshot(
    snapshot: dict,
) -> None:

    if not isinstance(
        snapshot,
        dict,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "broker reconstruction did not return a dict."
        )

    required = {
        "account",
        "positions",
        "open_orders",
    }

    missing = (
        required
        - set(
            snapshot
        )
    )

    if missing:
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "broker reconstruction incomplete: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )


def _decimal_positive(
    value: Any,
    *,
    field_name: str,
) -> Decimal:

    try:
        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ) as exc:

        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            f"{field_name} is not a valid decimal."
        ) from exc

    if not result.is_finite():

        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            f"{field_name} must be finite."
        )

    if result <= Decimal("0"):

        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            f"{field_name} must be positive."
        )

    return result


def validate_materialized_orders(
    materialized: dict,
) -> list[dict]:

    if not isinstance(
        materialized,
        dict,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "materializer did not return a dict."
        )

    if (
        "orders"
        not in materialized
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "materializer result has no orders field."
        )

    orders = (
        materialized[
            "orders"
        ]
    )

    if not isinstance(
        orders,
        list,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "materialized orders must be a list."
        )

    seen_client_ids: set[str] = set()

    validated: list[dict] = []

    for index, order in enumerate(
        orders
    ):

        if not isinstance(
            order,
            dict,
        ):
            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                f"order {index} is not a dict."
            )

        required = {
            "symbol",
            "side",
            "notional_usd",
            "client_order_id",
        }

        missing = (
            required
            - set(
                order
            )
        )

        if missing:
            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                f"order {index} missing: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        symbol = (
            str(
                order[
                    "symbol"
                ]
            )
            .strip()
            .upper()
        )

        if not symbol:

            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                "empty order symbol."
            )

        side = (
            str(
                order[
                    "side"
                ]
            )
            .strip()
            .lower()
        )

        if side not in {
            "buy",
            "sell",
        }:

            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                f"unsupported side {side!r}."
            )

        client_order_id = (
            str(
                order[
                    "client_order_id"
                ]
            )
            .strip()
        )

        if not client_order_id:

            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                "empty client_order_id."
            )

        if (
            client_order_id
            in seen_client_ids
        ):

            raise OrchestrationStop(
                "ORCHESTRATOR STOP: "
                "duplicate client_order_id "
                f"{client_order_id!r} "
                "inside materialized phase."
            )

        seen_client_ids.add(
            client_order_id
        )

        notional = (
            _decimal_positive(
                order[
                    "notional_usd"
                ],
                field_name=(
                    "notional_usd"
                ),
            )
        )

        normalized = dict(
            order
        )

        normalized[
            "symbol"
        ] = symbol

        normalized[
            "side"
        ] = side

        normalized[
            "client_order_id"
        ] = client_order_id

        normalized[
            "notional_usd"
        ] = str(
            notional
        )

        validated.append(
            normalized
        )

    return validated


def validate_history(
    history: dict,
) -> None:

    if not isinstance(
        history,
        dict,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "authorized-order reconstruction "
            "did not return a dict."
        )


def validate_cap_proof(
    proof: dict,
) -> None:

    if not isinstance(
        proof,
        dict,
    ):
        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "cumulative-cap guard did not "
            "return a dict."
        )

    if (
        proof.get(
            "approved"
        )
        is not True
    ):

        raise OrchestrationStop(
            "ORCHESTRATOR STOP: "
            "cumulative-cap guard did not "
            "explicitly approve execution."
        )


def run_execution_phase(
    *,
    release_lock_package: dict,
    compiler_package: dict,
    permit_package: dict,
    phase: str,
    now: datetime,
    deps: OrchestratorDependencies,
) -> dict:
    """
    Run exactly one execution phase.

    IMPORTANT:

    This function intentionally holds no persistent state.

    Calling it again after process loss/restart must trigger
    fresh broker reconstruction and fresh cumulative-cap
    reconstruction before any writer invocation.
    """

    validate_dependencies(
        deps
    )

    validate_now(
        now
    )

    phase_normalized = (
        validate_phase(
            phase
        )
    )

    trace: list[str] = []

    # --------------------------------------------------------
    # 1. Re-verify frozen release authority.
    # --------------------------------------------------------

    deps.verify_release_lock(
        release_lock_package=(
            release_lock_package
        ),
        compiler_package=(
            compiler_package
        ),
        permit_package=(
            permit_package
        ),
        phase=(
            phase_normalized
        ),
        now=(
            now
        ),
    )

    trace.append(
        "release_lock_verified"
    )

    # --------------------------------------------------------
    # 2. Reconstruct broker state FRESH for this phase.
    #
    # No cached broker portfolio is accepted by this API.
    # --------------------------------------------------------

    broker_snapshot = (
        deps.reconstruct_broker_snapshot(
            release_lock_package=(
                release_lock_package
            ),
            compiler_package=(
                compiler_package
            ),
            permit_package=(
                permit_package
            ),
            phase=(
                phase_normalized
            ),
            now=(
                now
            ),
        )
    )

    validate_broker_snapshot(
        broker_snapshot
    )

    trace.append(
        "broker_snapshot_reconstructed"
    )

    # --------------------------------------------------------
    # 3. Materialize this phase from the fresh broker state.
    # --------------------------------------------------------

    materialized = (
        deps.materialize_execution_phase(
            release_lock_package=(
                release_lock_package
            ),
            compiler_package=(
                compiler_package
            ),
            permit_package=(
                permit_package
            ),
            broker_snapshot=(
                broker_snapshot
            ),
            phase=(
                phase_normalized
            ),
            now=(
                now
            ),
        )
    )

    orders = (
        validate_materialized_orders(
            materialized
        )
    )

    trace.append(
        "phase_materialized"
    )

    # --------------------------------------------------------
    # 4. Reconstruct EVERY compiler-authorized client ID.
    #
    # This must happen even when the current phase contains
    # only one side of the rebalance.
    # --------------------------------------------------------

    authorized_order_history = (
        deps.reconstruct_authorized_order_history(
            release_lock_package=(
                release_lock_package
            ),
            compiler_package=(
                compiler_package
            ),
            permit_package=(
                permit_package
            ),
            broker_snapshot=(
                broker_snapshot
            ),
            phase=(
                phase_normalized
            ),
            now=(
                now
            ),
        )
    )

    validate_history(
        authorized_order_history
    )

    trace.append(
        "authorized_history_reconstructed"
    )

    # --------------------------------------------------------
    # 5. Apply the SINGLE cumulative permit ceiling.
    #
    # Historical broker-observed submissions +
    # genuinely unseen current-phase orders
    # must fit under one permit budget.
    # --------------------------------------------------------

    cap_proof = (
        deps.enforce_cumulative_cap(
            release_lock_package=(
                release_lock_package
            ),
            compiler_package=(
                compiler_package
            ),
            permit_package=(
                permit_package
            ),
            broker_snapshot=(
                broker_snapshot
            ),
            authorized_order_history=(
                authorized_order_history
            ),
            new_orders=(
                orders
            ),
            phase=(
                phase_normalized
            ),
            now=(
                now
            ),
        )
    )

    validate_cap_proof(
        cap_proof
    )

    trace.append(
        "cumulative_cap_approved"
    )

    # --------------------------------------------------------
    # 6. No-op phase.
    #
    # We still reconstructed history and ran the cap guard,
    # but there is nothing for the writer.
    # --------------------------------------------------------

    if not orders:

        trace.append(
            "writer_not_required"
        )

        return {
            "schema":
                ORCHESTRATOR_SCHEMA,
            "phase":
                phase_normalized,
            "orders":
                [],
            "cap_proof":
                cap_proof,
            "writer_result":
                None,
            "trace":
                trace,
        }

    # --------------------------------------------------------
    # 7. Writer is reachable ONLY after cap approval.
    # --------------------------------------------------------

    writer_result = (
        deps.submit_authorized_order_batch(
            release_lock_package=(
                release_lock_package
            ),
            compiler_package=(
                compiler_package
            ),
            permit_package=(
                permit_package
            ),
            broker_snapshot=(
                broker_snapshot
            ),
            authorized_order_history=(
                authorized_order_history
            ),
            orders=(
                orders
            ),
            cap_proof=(
                cap_proof
            ),
            phase=(
                phase_normalized
            ),
            now=(
                now
            ),
        )
    )

    trace.append(
        "writer_invoked"
    )

    return {
        "schema":
            ORCHESTRATOR_SCHEMA,
        "phase":
            phase_normalized,
        "orders":
            orders,
        "cap_proof":
            cap_proof,
        "writer_result":
            writer_result,
        "trace":
            trace,
    }

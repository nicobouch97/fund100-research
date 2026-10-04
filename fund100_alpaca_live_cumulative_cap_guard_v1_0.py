from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_DOWN,
)

import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE CUMULATIVE PERMIT-CAP GUARD v1.0
# ============================================================
#
# PURE / OFFLINE LOGIC.
#
# NO BROKER NETWORK ACCESS.
# NO CREDENTIAL ACCESS.
# NO ORDER SUBMISSION.
# NO PERSISTENCE.
#
# PURPOSE
# =======
#
# The existing materializer proves:
#
#     current remaining batch <= permit cap
#
# That is necessary but not sufficient for a multi-phase
# execution.
#
# Example:
#
#     permit cap = $100
#
#     SELL phase previously submitted = $60
#
#     fresh BUY phase = $50
#
# Looking only at the fresh BUY batch:
#
#     $50 <= $100
#
# looks valid.
#
# But cumulatively:
#
#     $60 + $50 = $110
#
# which exceeds the one permit ceiling.
#
# THIS GUARD'S RULE
# =================
#
# Before ANY future phase is submitted:
#
# 1. Take the complete compiler-authorized client_order_id set.
#
# 2. Require a broker lookup result for EVERY authorized ID:
#
#       client_order_id -> order object
#
#    or:
#
#       client_order_id -> None
#
#    where None means GET-by-client-order-id returned not found.
#
# 3. Every broker-observed matching order consumes its original
#    notional ONCE, regardless of whether it is:
#
#       filled
#       active
#       partially filled
#       canceled
#       expired
#       rejected
#
#    This is deliberately conservative.
#
# 4. Terminal-failure or unsafe/ambiguous historical states
#    also block continued execution until reconciliation.
#
# 5. For the proposed phase:
#
#       previously consumed gross
#       +
#       notional of genuinely unseen client IDs
#
#    must be <= the SINGLE permit ceiling.
#
# 6. Previously observed client IDs never consume the budget
#    a second time after restart.
#
# IMPORTANT
# =========
#
# This module deliberately does NOT perform the GET requests.
#
# A future reviewed orchestrator must obtain every lookup using
# the writer's reviewed GET-by-client-order-id path and feed the
# complete lookup map into this pure guard.
#
# The result is EPHEMERAL_DO_NOT_COMMIT because it contains
# execution dollar notionals.
#
# ============================================================


GUARD_VERSION = "1.0"


GUARD_SCHEMA = (
    "FUND100_LIVE_CUMULATIVE_CAP_GUARD_V1"
)


CENT = Decimal(
    "0.01"
)


PERSISTENCE_POLICY = (
    "EPHEMERAL_DO_NOT_COMMIT"
)


SAFE_RECOVERABLE_CLASSIFICATIONS = {
    "FILLED",
    "NO_RESUBMIT",
}


BLOCKING_CLASSIFICATIONS = {
    "TERMINAL_FAILURE",
    "AMBIGUOUS_UNSAFE",
    "UNKNOWN_UNSAFE",
}


class CumulativeCapGuardStop(
    RuntimeError
):
    pass


# ============================================================
# DECIMAL / HASH HELPERS
# ============================================================


def money_decimal(
    value,
    field_name: str,
    *,
    allow_zero: bool = False,
) -> Decimal:

    try:

        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise CumulativeCapGuardStop(
            f"CUMULATIVE CAP STOP: "
            f"{field_name}: invalid monetary value."
        ) from exc

    if not result.is_finite():

        raise CumulativeCapGuardStop(
            f"CUMULATIVE CAP STOP: "
            f"{field_name}: value must be finite."
        )

    if allow_zero:

        if result < 0:

            raise CumulativeCapGuardStop(
                f"CUMULATIVE CAP STOP: "
                f"{field_name}: value cannot be negative."
            )

    elif result <= 0:

        raise CumulativeCapGuardStop(
            f"CUMULATIVE CAP STOP: "
            f"{field_name}: value must be positive."
        )

    return result


def floor_money(
    value,
    field_name: str,
    *,
    allow_zero: bool = False,
) -> Decimal:

    return (
        money_decimal(
            value,
            field_name,
            allow_zero=
                allow_zero,
        )
        .quantize(
            CENT,
            rounding=
                ROUND_DOWN,
        )
    )


def validate_sha256(
    value,
    field_name: str,
) -> str:

    text = str(
        value
    ).strip().lower()

    if len(
        text
    ) != 64:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{field_name} is not a SHA256 digest."
        )

    try:

        int(
            text,
            16,
        )

    except ValueError as exc:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{field_name} is not hexadecimal."
        ) from exc

    return text


# ============================================================
# COMPILER AUTHORIZATION SET
# ============================================================


def build_authorized_index(
    compiler_body: dict,
):

    if not isinstance(
        compiler_body,
        dict,
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "compiler body is invalid."
        )

    if (
        compiler_body.get(
            "status"
        )
        != "GENUINE_SCHEDULED_EVENT"
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "compiler is not a genuine scheduled event."
        )

    if (
        compiler_body.get(
            "genuine_scheduled_event"
        )
        is not True
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "compiler genuine-event proof is missing."
        )

    intents = (
        compiler_body.get(
            "candidate_intents"
        )
    )

    if not isinstance(
        intents,
        list,
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "compiler candidate intents are invalid."
        )

    if not intents:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "genuine event has no authorized candidates."
        )

    result = {}

    seen_symbols = set()

    for item in intents:

        if not isinstance(
            item,
            dict,
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "invalid compiler candidate."
            )

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        if (
            symbol
            not in candidate.ALLOWED_SYMBOLS
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"unsupported symbol {symbol!r}."
            )

        if symbol in seen_symbols:

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"duplicate compiler symbol {symbol!r}."
            )

        seen_symbols.add(
            symbol
        )

        side = str(
            item.get(
                "side",
                "",
            )
        ).lower()

        if (
            side
            not in candidate.ALLOWED_SIDES
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"{symbol}: invalid side."
            )

        client_order_id = str(
            item.get(
                "client_order_id",
                "",
            )
        ).strip()

        if not client_order_id.startswith(
            "f100live-"
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"{symbol}: invalid Fund-100 "
                "client_order_id."
            )

        if (
            len(
                client_order_id
            )
            > candidate.MAX_CLIENT_ORDER_ID_LENGTH
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"{symbol}: client_order_id too long."
            )

        if (
            client_order_id
            in result
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "duplicate client_order_id."
            )

        if (
            item.get(
                "notional_usd"
            )
            is not None
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "compiler candidate unexpectedly contains "
                "an executable notional."
            )

        if (
            item.get(
                "executable"
            )
            is not False
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "compiler candidate is executable."
            )

        result[
            client_order_id
        ] = {
            "symbol":
                symbol,

            "side":
                side,

            "client_order_id":
                client_order_id,
        }

    return result


# ============================================================
# BROKER LOOKUP COMPLETENESS
# ============================================================


def validate_complete_lookup_map(
    *,
    authorized_index: dict,
    observed_orders_by_client_id: dict,
):

    if not isinstance(
        observed_orders_by_client_id,
        dict,
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "broker lookup map is invalid."
        )

    expected = set(
        authorized_index
    )

    actual = set(
        observed_orders_by_client_id
    )

    missing = sorted(
        expected
        - actual
    )

    extra = sorted(
        actual
        - expected
    )

    if missing:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "broker reconstruction is incomplete; "
            "missing client_order_id lookup(s): "
            + ", ".join(
                missing
            )
        )

    if extra:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "broker reconstruction contains "
            "unauthorized client_order_id(s): "
            + ", ".join(
                extra
            )
        )

    return True


# ============================================================
# OBSERVED ORDER VALIDATION
# ============================================================


def validate_observed_order(
    *,
    order: dict,
    authorization: dict,
):

    if not isinstance(
        order,
        dict,
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "observed broker order is invalid."
        )

    client_order_id = str(
        order.get(
            "client_order_id",
            "",
        )
    ).strip()

    if (
        client_order_id
        != authorization[
            "client_order_id"
        ]
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "observed client_order_id mismatch."
        )

    order_id = str(
        order.get(
            "id",
            "",
        )
    ).strip()

    if not order_id:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "observed broker order has no order ID."
        )

    symbol = str(
        order.get(
            "symbol",
            "",
        )
    ).upper()

    if (
        symbol
        != authorization[
            "symbol"
        ]
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: symbol mismatch."
        )

    side = str(
        order.get(
            "side",
            "",
        )
    ).lower()

    if (
        side
        != authorization[
            "side"
        ]
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: side mismatch."
        )

    order_type = str(
        order.get(
            "type",
            order.get(
                "order_type",
                "",
            ),
        )
    ).lower()

    if order_type != "market":

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: order type mismatch."
        )

    time_in_force = str(
        order.get(
            "time_in_force",
            "",
        )
    ).lower()

    if time_in_force != "day":

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: time_in_force mismatch."
        )

    notional = (
        floor_money(
            order.get(
                "notional"
            ),
            (
                f"{client_order_id}."
                "broker_notional"
            ),
        )
    )

    try:

        classification = (
            candidate.classify_order_status(
                order
            )
        )

    except Exception as exc:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: broker status "
            "cannot be classified."
        ) from exc

    if (
        classification
        not in (
            SAFE_RECOVERABLE_CLASSIFICATIONS
            | BLOCKING_CLASSIFICATIONS
        )
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            f"{client_order_id}: unexpected "
            "status classification."
        )

    return {
        "client_order_id":
            client_order_id,

        "symbol":
            symbol,

        "side":
            side,

        "notional_usd":
            notional,

        "classification":
            classification,

        "status":
            str(
                order.get(
                    "status",
                    "",
                )
            ).strip().lower(),
    }


# ============================================================
# RECONSTRUCT CUMULATIVE CONSUMPTION
# ============================================================


def reconstruct_consumed_state(
    *,
    compiler_body: dict,
    observed_orders_by_client_id: dict,
    permit_cap_usd,
):

    permit_cap = (
        floor_money(
            permit_cap_usd,
            "permit_cap_usd",
        )
    )

    authorized = (
        build_authorized_index(
            compiler_body
        )
    )

    validate_complete_lookup_map(
        authorized_index=
            authorized,

        observed_orders_by_client_id=
            observed_orders_by_client_id,
    )

    consumed = Decimal(
        "0"
    )

    observed = {}

    blockers = []

    for client_order_id in sorted(
        authorized
    ):

        order = (
            observed_orders_by_client_id[
                client_order_id
            ]
        )

        if order is None:

            continue

        normalized = (
            validate_observed_order(
                order=
                    order,

                authorization=
                    authorized[
                        client_order_id
                    ],
            )
        )

        observed[
            client_order_id
        ] = normalized

        consumed += (
            normalized[
                "notional_usd"
            ]
        )

        if (
            normalized[
                "classification"
            ]
            in BLOCKING_CLASSIFICATIONS
        ):

            blockers.append({
                "client_order_id":
                    client_order_id,

                "classification":
                    normalized[
                        "classification"
                    ],

                "status":
                    normalized[
                        "status"
                    ],
            })

    consumed = (
        consumed.quantize(
            CENT,
            rounding=
                ROUND_DOWN,
        )
    )

    if consumed > permit_cap:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP VIOLATION: "
            "broker-observed historical gross "
            "already exceeds the permit ceiling."
        )

    remaining = (
        permit_cap
        - consumed
    ).quantize(
        CENT,
        rounding=
            ROUND_DOWN,
    )

    return {
        "permit_cap_usd":
            permit_cap,

        "consumed_gross_notional_usd":
            consumed,

        "remaining_cap_usd":
            remaining,

        "authorized_index":
            authorized,

        "observed_orders":
            observed,

        "observed_client_order_ids":
            sorted(
                observed
            ),

        "blocking_existing_orders":
            blockers,

        "complete_lookup_verified":
            True,
    }


# ============================================================
# PROPOSED PHASE VALIDATION
# ============================================================


def validate_proposed_batch(
    *,
    proposed_intents: list,
    authorized_index: dict,
):

    if not isinstance(
        proposed_intents,
        list,
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "proposed phase batch is invalid."
        )

    result = []

    seen = set()

    for raw in proposed_intents:

        if not isinstance(
            raw,
            dict,
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "invalid proposed intent."
            )

        try:

            item = (
                candidate.validate_order_intent(
                    raw
                )
            )

        except Exception as exc:

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "proposed intent failed writer validation."
            ) from exc

        client_order_id = (
            item[
                "client_order_id"
            ]
        )

        if client_order_id in seen:

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "duplicate proposed client_order_id."
            )

        seen.add(
            client_order_id
        )

        if (
            client_order_id
            not in authorized_index
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                "proposed order is outside "
                "the compiler-authorized ID set."
            )

        authorization = (
            authorized_index[
                client_order_id
            ]
        )

        if (
            item[
                "symbol"
            ]
            != authorization[
                "symbol"
            ]
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"{client_order_id}: proposed symbol mismatch."
            )

        if (
            item[
                "side"
            ]
            != authorization[
                "side"
            ]
        ):

            raise CumulativeCapGuardStop(
                "CUMULATIVE CAP STOP: "
                f"{client_order_id}: proposed side mismatch."
            )

        notional = (
            floor_money(
                item[
                    "notional_usd"
                ],
                (
                    f"{client_order_id}."
                    "proposed_notional_usd"
                ),
            )
        )

        result.append({
            **item,

            "notional_usd_decimal":
                notional,
        })

    return result


# ============================================================
# CUMULATIVE CAP EVALUATION
# ============================================================


def evaluate_cumulative_cap(
    *,
    compiler_body: dict,
    compiler_sha256: str,
    permit_sha256: str,
    permit_cap_usd,
    observed_orders_by_client_id: dict,
    proposed_intents: list,
):

    compiler_hash = (
        validate_sha256(
            compiler_sha256,
            "compiler_sha256",
        )
    )

    permit_hash = (
        validate_sha256(
            permit_sha256,
            "permit_sha256",
        )
    )

    calculated_compiler_hash = (
        candidate.sha256_json(
            compiler_body
        )
    )

    if (
        compiler_hash
        != calculated_compiler_hash
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "compiler SHA256 binding failed."
        )

    state = (
        reconstruct_consumed_state(
            compiler_body=
                compiler_body,

            observed_orders_by_client_id=
                observed_orders_by_client_id,

            permit_cap_usd=
                permit_cap_usd,
        )
    )

    # --------------------------------------------------------
    # A failed-terminal or ambiguous historical order means
    # execution state requires explicit reconciliation.
    #
    # We count its notional conservatively, but do not allow
    # another phase to proceed automatically.
    # --------------------------------------------------------

    if (
        state[
            "blocking_existing_orders"
        ]
    ):

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP STOP: "
            "broker history contains a terminal-failure "
            "or unsafe order; execution requires "
            "explicit reconciliation."
        )

    proposed = (
        validate_proposed_batch(
            proposed_intents=
                proposed_intents,

            authorized_index=
                state[
                    "authorized_index"
                ],
        )
    )

    new_gross = Decimal(
        "0"
    )

    recovered_client_ids = []

    new_client_ids = []

    for item in proposed:

        client_order_id = (
            item[
                "client_order_id"
            ]
        )

        existing = (
            state[
                "observed_orders"
            ].get(
                client_order_id
            )
        )

        if existing is not None:

            raw_existing = (
                observed_orders_by_client_id[
                    client_order_id
                ]
            )

            # ------------------------------------------------
            # Exact original-notional binding.
            #
            # If a fresh materialization tries to use the same
            # client ID with a different notional, the writer
            # itself would fail closed. The cap guard catches
            # it before writer invocation as well.
            # ------------------------------------------------

            try:

                candidate.validate_existing_order_matches_intent(
                    existing=
                        raw_existing,

                    intent={
                        **item,

                        "executable":
                            True,
                    },
                )

            except Exception as exc:

                raise CumulativeCapGuardStop(
                    "CUMULATIVE CAP STOP: "
                    f"{client_order_id}: proposed intent "
                    "does not exactly match the previously "
                    "observed broker order."
                ) from exc

            recovered_client_ids.append(
                client_order_id
            )

            continue

        new_gross += (
            item[
                "notional_usd_decimal"
            ]
        )

        new_client_ids.append(
            client_order_id
        )

    new_gross = (
        new_gross.quantize(
            CENT,
            rounding=
                ROUND_DOWN,
        )
    )

    consumed = (
        state[
            "consumed_gross_notional_usd"
        ]
    )

    projected = (
        consumed
        + new_gross
    ).quantize(
        CENT,
        rounding=
            ROUND_DOWN,
    )

    permit_cap = (
        state[
            "permit_cap_usd"
        ]
    )

    if projected > permit_cap:

        raise CumulativeCapGuardStop(
            "CUMULATIVE CAP VIOLATION: "
            "historical consumed gross plus newly "
            "proposed gross exceeds the single "
            "permit ceiling."
        )

    remaining_after = (
        permit_cap
        - projected
    ).quantize(
        CENT,
        rounding=
            ROUND_DOWN,
    )

    return {
        "schema":
            GUARD_SCHEMA,

        "version":
            GUARD_VERSION,

        "source_compiler_sha256":
            compiler_hash,

        "source_permit_sha256":
            permit_hash,

        "permit_cap_usd":
            float(
                permit_cap
            ),

        "broker_lookup_complete":
            True,

        "authorized_client_order_id_count":
            len(
                state[
                    "authorized_index"
                ]
            ),

        "previously_observed_order_count":
            len(
                state[
                    "observed_orders"
                ]
            ),

        "previously_consumed_gross_notional_usd":
            float(
                consumed
            ),

        "remaining_cap_before_batch_usd":
            float(
                state[
                    "remaining_cap_usd"
                ]
            ),

        "proposed_phase_intent_count":
            len(
                proposed
            ),

        "recovered_existing_intent_count":
            len(
                recovered_client_ids
            ),

        "new_intent_count":
            len(
                new_client_ids
            ),

        "new_gross_notional_usd":
            float(
                new_gross
            ),

        "projected_cumulative_gross_notional_usd":
            float(
                projected
            ),

        "remaining_cap_after_batch_usd":
            float(
                remaining_after
            ),

        "recovered_client_order_ids":
            sorted(
                recovered_client_ids
            ),

        "new_client_order_ids":
            sorted(
                new_client_ids
            ),

        "terminal_or_unsafe_history_present":
            False,

        "cumulative_cap_verified":
            True,

        "persistence_policy":
            PERSISTENCE_POLICY,

        "broker_network_access":
            False,

        "broker_write_capability":
            False,

        "orders_submitted":
            0,
    }


# ============================================================
# DELIBERATELY NO main()
# ============================================================
#
# This module is pure cap/restart accounting logic.
#
# It cannot:
#
# - read credentials
# - call Alpaca
# - submit orders
# - persist live dollar values
#
# ============================================================

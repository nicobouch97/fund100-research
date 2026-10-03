from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN

import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_alpaca_live_position_reconcile as reconcile
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


# ============================================================
# FUND-100 LIVE EXECUTION MATERIALIZER v1.0
# ============================================================
#
# PURE / OFFLINE LOGIC ONLY.
#
# NO broker credentials.
# NO HTTP.
# NO GET.
# NO POST.
# NO broker mutation.
# NO main().
#
# PURPOSE
# =======
#
# Convert:
#
#   - final position-aware compiler target
#   - writer-compatible V2 permit
#   - fresh broker account/position objects supplied by caller
#
# into:
#
#   - executable dollar-notional intents
#
# Important:
#
# This component DOES NOT fetch broker data itself.
# A future connected execution orchestrator must provide fresh
# account/position/open-order objects.
#
# This component:
#
# - verifies permit/compiler/release-lock bindings
# - reconstructs final target weights
# - restricts execution to compiler-authorized candidate symbols
# - refuses direction changes
# - refuses stale sub-$1 deltas
# - refuses shorts
# - enforces aggregate permit cap
# - supports SELL and BUY phases separately
# - requires BUY phase to be cash-funded at that moment
#
# Executable materialized intents are EPHEMERAL and must never
# be committed to the repository.
#
# ============================================================


MATERIALIZER_VERSION = "1.0"

MATERIALIZER_SCHEMA = (
    "FUND100_LIVE_EXECUTION_MATERIALIZER_V1"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)

EXPECTED_PERMIT_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)

EXPECTED_LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)

PHASE_SELL = "SELL"

PHASE_BUY = "BUY"

ALLOWED_PHASES = {
    PHASE_SELL,
    PHASE_BUY,
}

CENT = Decimal("0.01")

WEIGHT_TOLERANCE = Decimal("0.00000001")

DIRECTION_TOLERANCE_USD = Decimal("0.005")

MIN_NOTIONAL_USD = Decimal(
    str(
        writer.MIN_NOTIONAL_USD
    )
)


# ============================================================
# DECIMAL HELPERS
# ============================================================


def as_decimal(
    value,
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
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            f"{field_name}: invalid numeric value."
        ) from exc

    if not result.is_finite():

        raise RuntimeError(
            f"{field_name}: value must be finite."
        )

    return result


def floor_money(
    value: Decimal,
) -> Decimal:

    if value < 0:

        raise RuntimeError(
            "Cannot floor a negative monetary value."
        )

    return value.quantize(
        CENT,
        rounding=ROUND_DOWN,
    )


def parse_timestamp(
    value,
):

    text = str(
        value or ""
    ).strip()

    if not text:

        raise RuntimeError(
            "Missing timestamp."
        )

    result = datetime.fromisoformat(
        text.replace(
            "Z",
            "+00:00",
        )
    )

    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )

    return result


# ============================================================
# HASH PACKAGE VERIFICATION
# ============================================================


def verify_hashed_package(
    package: dict,
    *,
    body_key: str,
    hash_key: str,
):

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid hashed package."
        )

    if (
        body_key not in package
        or
        hash_key not in package
    ):

        raise RuntimeError(
            "Incomplete hashed package."
        )

    body = package[
        body_key
    ]

    recorded = str(
        package[
            hash_key
        ]
    )

    calculated = (
        writer.sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            f"{body_key}: SHA256 verification failed."
        )

    return (
        body,
        recorded,
    )


# ============================================================
# FINAL STRATEGY TARGET
# ============================================================


def build_full_target_weights(
    compiler: dict,
):

    if (
        compiler.get(
            "schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "unexpected compiler schema."
        )

    if (
        compiler.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "unexpected strategy."
        )

    if (
        compiler.get(
            "status"
        )
        != "GENUINE_SCHEDULED_EVENT"
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "compiler is not a genuine scheduled event."
        )

    if (
        compiler.get(
            "genuine_scheduled_event"
        )
        is not True
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "compiler genuine-event flag is FALSE."
        )

    if (
        compiler.get(
            "broker_delta_source"
        )
        != "FRESH_EPHEMERAL_RECONCILIATION"
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "compiler is not position-aware."
        )

    satellites = (
        compiler.get(
            "executed_satellite_weights"
        )
    )

    if not isinstance(
        satellites,
        dict,
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "executed satellite weights are missing."
        )

    expected_satellites = set(
        writer.FROZEN_V5_SATELLITE_UNIVERSE
    )

    if set(
        satellites
    ) != expected_satellites:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "compiler satellite universe mismatch."
        )

    target = {}

    satellite_total = Decimal("0")

    for symbol in sorted(
        expected_satellites
    ):

        weight = as_decimal(
            satellites[
                symbol
            ],
            f"{symbol}.target_weight",
        )

        if (
            weight < 0
            or
            weight > 1
        ):

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"{symbol}: invalid target weight."
            )

        target[
            symbol
        ] = weight

        satellite_total += weight

    if satellite_total > 1 + WEIGHT_TOLERANCE:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "satellite weights exceed 100%."
        )

    core = (
        Decimal("1")
        - satellite_total
    )

    if core < -WEIGHT_TOLERANCE:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "negative ACWI core target."
        )

    if core < 0:

        core = Decimal("0")

    target[
        writer.BENCHMARK_CORE_SYMBOL
    ] = core

    total = sum(
        target.values(),
        Decimal("0"),
    )

    if (
        abs(
            total
            - Decimal("1")
        )
        > WEIGHT_TOLERANCE
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "full target does not sum to 100%."
        )

    if set(
        target
    ) != writer.ALLOWED_SYMBOLS:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "full target universe does not match writer."
        )

    return target


# ============================================================
# COMPILER-AUTHORIZED CANDIDATES
# ============================================================


def build_authorized_candidates(
    compiler: dict,
    permit: dict,
    target: dict,
):

    intents = (
        compiler.get(
            "candidate_intents"
        )
    )

    if not isinstance(
        intents,
        list,
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "compiler candidate intents are invalid."
        )

    if not intents:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "genuine event has no candidate intents."
        )

    result = {}

    for item in intents:

        if not isinstance(
            item,
            dict,
        ):

            raise RuntimeError(
                "MATERIALIZER STOP: "
                "invalid compiler candidate intent."
            )

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        if symbol not in writer.ALLOWED_SYMBOLS:

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"unsupported compiler symbol {symbol!r}."
            )

        if symbol in result:

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"duplicate compiler candidate {symbol!r}."
            )

        side = str(
            item.get(
                "side",
                "",
            )
        ).lower()

        if side not in writer.ALLOWED_SIDES:

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"{symbol}: invalid candidate side."
            )

        if (
            item.get(
                "notional_usd"
            )
            is not None
        ):

            raise RuntimeError(
                "MATERIALIZER STOP: "
                "compiler source intent unexpectedly "
                "contains an executable notional."
            )

        if (
            item.get(
                "executable"
            )
            is not False
        ):

            raise RuntimeError(
                "MATERIALIZER STOP: "
                "compiler source intent is executable."
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

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"{symbol}: invalid Fund-100 client order ID."
            )

        item_target = as_decimal(
            item.get(
                "target_weight"
            ),
            f"{symbol}.candidate_target_weight",
        )

        expected_target = target[
            symbol
        ]

        if (
            abs(
                item_target
                - expected_target
            )
            > WEIGHT_TOLERANCE
        ):

            raise RuntimeError(
                "MATERIALIZER STOP: "
                f"{symbol}: compiler candidate target "
                "does not match final strategy target."
            )

        result[
            symbol
        ] = {
            "symbol":
                symbol,

            "side":
                side,

            "target_weight":
                expected_target,

            "client_order_id":
                client_order_id,
        }

    permit_symbols = {
        str(
            symbol
        ).upper()
        for symbol
        in permit.get(
            "candidate_symbols",
            []
        )
    }

    if (
        permit_symbols
        != set(
            result
        )
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit candidate-symbol set does not "
            "exactly match compiler candidates."
        )

    return result


# ============================================================
# RELEASE LOCK / PERMIT / COMPILER BINDING
# ============================================================


def validate_execution_bindings(
    *,
    release_lock_package: dict,
    compiler_package: dict,
    permit_package: dict,
    now,
):

    (
        lock,
        lock_hash,
    ) = (
        verify_hashed_package(
            release_lock_package,
            body_key=
                "release_lock",
            hash_key=
                "release_lock_sha256",
        )
    )

    (
        compiler,
        compiler_hash,
    ) = (
        verify_hashed_package(
            compiler_package,
            body_key=
                "compiler",
            hash_key=
                "compiler_sha256",
        )
    )

    (
        permit,
        permit_hash,
    ) = (
        verify_hashed_package(
            permit_package,
            body_key=
                "permit",
            hash_key=
                "permit_sha256",
        )
    )

    if (
        lock.get(
            "schema"
        )
        != EXPECTED_LOCK_SCHEMA
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "unexpected release-lock schema."
        )

    if not issuer.final_lock_is_ready(
        lock
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "issuer-aware release lock is not ready."
        )

    if (
        permit.get(
            "schema"
        )
        != EXPECTED_PERMIT_SCHEMA
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "unexpected permit schema."
        )

    # Existing writer permit validation is deliberately reused.
    validated_permit, permit_cap = (
        writer.validate_permit_package(
            permit_package
        )
    )

    if (
        validated_permit
        is not permit
    ):

        # Defensive only; current writer returns the same body.
        permit = validated_permit

    if (
        permit.get(
            "single_use"
        )
        is not True
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit is not single-use."
        )

    if (
        permit.get(
            "event_previously_permitted"
        )
        is not False
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit event replay flag is unsafe."
        )

    if (
        permit.get(
            "execution_requires_separate_kill_switch_transition"
        )
        is not True
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit does not require independent "
            "kill-switch transition."
        )

    if (
        permit.get(
            "writer_connected_at_issuance"
        )
        is not False
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit was issued while writer was connected."
        )

    if (
        permit.get(
            "issuer_broker_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit issuer had broker-write capability."
        )

    if (
        permit.get(
            "orders_submitted_by_issuer"
        )
        != 0
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit issuer submitted orders."
        )

    if (
        permit.get(
            "source_release_lock_sha256"
        )
        != lock_hash
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit is not bound to current release lock."
        )

    if (
        permit.get(
            "source_compiler_sha256"
        )
        != compiler_hash
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit is not bound to current compiler."
        )

    if (
        permit.get(
            "source_release_lock_schema"
        )
        != EXPECTED_LOCK_SCHEMA
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit release-lock schema binding mismatch."
        )

    if (
        permit.get(
            "source_compiler_schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit compiler-schema binding mismatch."
        )

    expiry = parse_timestamp(
        permit.get(
            "candidate_expiry"
        )
    )

    current = (
        now
        if isinstance(
            now,
            datetime,
        )
        else parse_timestamp(
            now
        )
    )

    if current.tzinfo is None:

        current = current.replace(
            tzinfo=timezone.utc
        )

    if current >= expiry:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "permit has expired."
        )

    target = (
        build_full_target_weights(
            compiler
        )
    )

    candidates = (
        build_authorized_candidates(
            compiler=
                compiler,

            permit=
                permit,

            target=
                target,
        )
    )

    return {
        "release_lock":
            lock,

        "release_lock_sha256":
            lock_hash,

        "compiler":
            compiler,

        "compiler_sha256":
            compiler_hash,

        "permit":
            permit,

        "permit_sha256":
            permit_hash,

        "permit_cap":
            as_decimal(
                permit_cap,
                "permit_cap",
            ),

        "target_weights":
            target,

        "candidates":
            candidates,
    }


# ============================================================
# BROKER SNAPSHOT VALIDATION
# ============================================================


def validate_broker_snapshot(
    *,
    account: dict,
    positions,
    open_orders,
    permit: dict,
):

    reconcile.validate_open_orders(
        open_orders
    )

    account_values = (
        reconcile.validate_account_for_reconciliation(
            account
        )
    )

    parsed_positions = (
        reconcile.parse_positions(
            positions
        )
    )

    binding = (
        reconcile.account_binding_sha256(
            account
        )
    )

    if (
        binding
        != permit.get(
            "live_account_binding_sha256"
        )
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "live account binding does not match permit."
        )

    portfolio_value = (
        account_values[
            "portfolio_value"
        ]
    )

    if portfolio_value <= 0:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "positive portfolio value is required."
        )

    return {
        "account_values":
            account_values,

        "positions":
            parsed_positions,

        "portfolio_value":
            portfolio_value,

        "cash":
            account_values[
                "cash"
            ],

        "account_binding_sha256":
            binding,
    }


# ============================================================
# EXECUTABLE ORDER MATERIALIZATION
# ============================================================


def materialize_all_authorized_orders(
    *,
    broker_snapshot: dict,
    target_weights: dict,
    candidates: dict,
):

    portfolio_value = (
        broker_snapshot[
            "portfolio_value"
        ]
    )

    positions = (
        broker_snapshot[
            "positions"
        ]
    )

    orders = []

    for symbol in sorted(
        candidates
    ):

        candidate = (
            candidates[
                symbol
            ]
        )

        current_value = (
            positions.get(
                symbol,
                {},
            ).get(
                "market_value",
                Decimal("0"),
            )
        )

        target_value = (
            target_weights[
                symbol
            ]
            * portfolio_value
        )

        delta = (
            target_value
            - current_value
        )

        if (
            delta
            > DIRECTION_TOLERANCE_USD
        ):

            actual_side = "buy"

        elif (
            delta
            < -DIRECTION_TOLERANCE_USD
        ):

            actual_side = "sell"

        else:

            raise RuntimeError(
                "MATERIALIZER STALE STOP: "
                f"{symbol}: authorized candidate no longer "
                "requires a material trade."
            )

        if (
            actual_side
            != candidate[
                "side"
            ]
        ):

            raise RuntimeError(
                "MATERIALIZER STALE STOP: "
                f"{symbol}: fresh broker delta changed "
                f"direction from "
                f"{candidate['side'].upper()} to "
                f"{actual_side.upper()}."
            )

        notional = (
            floor_money(
                abs(
                    delta
                )
            )
        )

        if (
            notional
            < MIN_NOTIONAL_USD
        ):

            raise RuntimeError(
                "MATERIALIZER STALE STOP: "
                f"{symbol}: fresh executable notional "
                "is below the writer minimum."
            )

        if actual_side == "sell":

            available_value = (
                floor_money(
                    current_value
                )
            )

            if (
                notional
                > available_value
            ):

                raise RuntimeError(
                    "MATERIALIZER STOP: "
                    f"{symbol}: proposed sell exceeds "
                    "current long market value."
                )

            if symbol not in positions:

                raise RuntimeError(
                    "MATERIALIZER STOP: "
                    f"{symbol}: cannot sell a position "
                    "that does not exist."
                )

        orders.append({
            "symbol":
                symbol,

            "side":
                actual_side,

            "notional_usd":
                float(
                    notional
                ),

            "client_order_id":
                candidate[
                    "client_order_id"
                ],

            "executable":
                True,
        })

    return orders


# ============================================================
# PERMIT CAP
# ============================================================


def validate_total_permit_cap(
    orders: list,
    permit_cap: Decimal,
):

    gross = sum(
        (
            as_decimal(
                order[
                    "notional_usd"
                ],
                "notional_usd",
            )
            for order
            in orders
        ),
        Decimal("0"),
    )

    if (
        gross
        > permit_cap
    ):

        raise RuntimeError(
            "MATERIALIZER STOP: "
            "fresh executable gross notional exceeds "
            "the V2 permit ceiling."
        )

    return gross


# ============================================================
# PHASE SELECTION
# ============================================================


def select_phase(
    *,
    orders: list,
    phase: str,
    cash: Decimal,
):

    phase = str(
        phase
    ).strip().upper()

    if phase not in ALLOWED_PHASES:

        raise RuntimeError(
            "MATERIALIZER STOP: "
            f"invalid execution phase {phase!r}."
        )

    side = (
        "sell"
        if phase == PHASE_SELL
        else "buy"
    )

    selected = [
        dict(
            order
        )
        for order
        in orders
        if order[
            "side"
        ]
        == side
    ]

    gross = sum(
        (
            as_decimal(
                order[
                    "notional_usd"
                ],
                "notional_usd",
            )
            for order
            in selected
        ),
        Decimal("0"),
    )

    # --------------------------------------------------------
    # BUY PHASE MUST BE FUNDED BY CASH THAT EXISTS NOW.
    #
    # A future orchestrator must therefore:
    #
    #   1. execute/reconcile SELL phase
    #   2. fetch a fresh broker snapshot
    #   3. materialize BUY phase again
    #
    # It may not assume pending sell proceeds.
    # --------------------------------------------------------

    if (
        phase == PHASE_BUY
        and
        gross
        > cash
        + CENT
    ):

        raise RuntimeError(
            "MATERIALIZER FUNDING STOP: "
            "BUY phase exceeds currently available cash. "
            "SELL phase must be filled/reconciled first."
        )

    return (
        selected,
        gross,
    )


# ============================================================
# PUBLIC PURE MATERIALIZATION API
# ============================================================


def materialize_execution_phase(
    *,
    release_lock_package: dict,
    compiler_package: dict,
    permit_package: dict,
    account: dict,
    positions,
    open_orders,
    phase: str,
    now,
):

    bindings = (
        validate_execution_bindings(
            release_lock_package=
                release_lock_package,

            compiler_package=
                compiler_package,

            permit_package=
                permit_package,

            now=
                now,
        )
    )

    broker = (
        validate_broker_snapshot(
            account=
                account,

            positions=
                positions,

            open_orders=
                open_orders,

            permit=
                bindings[
                    "permit"
                ],
        )
    )

    all_orders = (
        materialize_all_authorized_orders(
            broker_snapshot=
                broker,

            target_weights=
                bindings[
                    "target_weights"
                ],

            candidates=
                bindings[
                    "candidates"
                ],
        )
    )

    full_gross = (
        validate_total_permit_cap(
            orders=
                all_orders,

            permit_cap=
                bindings[
                    "permit_cap"
                ],
        )
    )

    (
        selected,
        phase_gross,
    ) = (
        select_phase(
            orders=
                all_orders,

            phase=
                phase,

            cash=
                broker[
                    "cash"
                ],
        )
    )

    body = {
        "schema":
            MATERIALIZER_SCHEMA,

        "version":
            MATERIALIZER_VERSION,

        "strategy":
            EXPECTED_STRATEGY,

        "phase":
            str(
                phase
            ).upper(),

        "source_release_lock_sha256":
            bindings[
                "release_lock_sha256"
            ],

        "source_compiler_sha256":
            bindings[
                "compiler_sha256"
            ],

        "source_permit_sha256":
            bindings[
                "permit_sha256"
            ],

        "live_account_binding_sha256":
            broker[
                "account_binding_sha256"
            ],

        "candidate_symbol_count":
            len(
                bindings[
                    "candidates"
                ]
            ),

        "full_execution_gross_notional_usd":
            float(
                full_gross
            ),

        "phase_gross_notional_usd":
            float(
                phase_gross
            ),

        "permit_cap_usd":
            float(
                bindings[
                    "permit_cap"
                ]
            ),

        "executable_intents":
            selected,

        "persistence_policy":
            "EPHEMERAL_DO_NOT_COMMIT",

        "broker_network_access":
            False,

        "orders_submitted":
            0,
    }

    return body


# ============================================================
# DELIBERATELY NO main()
# ============================================================
#
# This module is pure execution-materialization logic.
#
# It cannot:
#
# - read Alpaca credentials
# - call Alpaca
# - submit an order
# - persist an executable batch by itself
#
# ============================================================

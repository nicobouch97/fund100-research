from __future__ import annotations

import json
import sys

import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_intent_validator as base
import fund100_alpaca_live_manifest_v1_1 as manifest_v11
import fund100_alpaca_live_position_reconcile as reconcile
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_writer_disconnected_v1_1 as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE ORDER-INTENT VALIDATOR v1.1
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# v1.1 consumes:
#
#   FUND100_LIVE_DRYRUN_MANIFEST_V1_1
#
# and obtains a FRESH, EPHEMERAL broker reconciliation.
#
# Important properties:
#
# - complete frozen V5 execution universe
# - portfolio-value based broker weights
# - existing positions supported
# - account binding checked against manifest
# - position structure checked against manifest
# - complete structural reconciliation proof carried forward
# - live dollar balances are NOT persisted
# - live holdings are NOT persisted
# - volatile broker snapshot hashes are NOT persisted
#
# Scheduled events still fail closed here because their frozen
# 2.5% threshold must be calculated at execution time by the
# scheduled execution compiler.
#
# ============================================================


INTENT_SCHEMA = (
    "FUND100_LIVE_ORDER_INTENTS_V1_1"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

LIVE_EXECUTION_AUTHORIZED = False

MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.0

NETWORK_WRITE_CAPABILITY = False

BROKER_WRITE_MODE = "DISABLED"

ORDERS_SUBMITTED = 0


# ============================================================
# MANIFEST
# ============================================================


def load_manifest_v1_1():

    path = (
        base.MANIFEST_PATH
    )

    if not path.exists():

        raise RuntimeError(
            "Live dry-run manifest is missing."
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        package = json.load(
            handle
        )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid live manifest package."
        )

    if (
        "manifest"
        not in package
        or
        "manifest_sha256"
        not in package
        or
        "manifest_id"
        not in package
    ):

        raise RuntimeError(
            "Incomplete live manifest package."
        )

    body = (
        package[
            "manifest"
        ]
    )

    calculated = (
        base.sha256_json(
            body
        )
    )

    recorded = str(
        package[
            "manifest_sha256"
        ]
    )

    if calculated != recorded:

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest SHA256 verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != manifest_v11.MANIFEST_SCHEMA
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest is not position-aware v1.1."
        )

    if (
        body.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected strategy in live manifest."
        )

    if (
        body.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "manifest unexpectedly authorizes execution."
        )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "manifest monetary ceiling is not $0.00."
        )

    if (
        body.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "manifest unexpectedly has "
            "network-write capability."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "manifest write mode is not DISABLED."
        )

    structure = (
        body.get(
            "position_reconciliation"
        )
    )

    if not isinstance(
        structure,
        dict,
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest has no position-reconciliation proof."
        )

    if (
        structure.get(
            "policy"
        )
        != manifest_v11.RECONCILIATION_POLICY
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "unexpected reconciliation policy."
        )

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            structure.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "LIVE INTENT STOP: "
                f"manifest reconciliation field "
                f"{field!r} is not TRUE."
            )

    if (
        structure.get(
            "live_holdings_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest unexpectedly persists holdings."
        )

    if (
        structure.get(
            "live_dollar_values_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest unexpectedly persists "
            "live dollar values."
        )

    if (
        structure.get(
            "volatile_broker_snapshot_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest unexpectedly persists "
            "volatile broker state."
        )

    return package


# ============================================================
# CURRENT SHADOW STATE
# ============================================================


def load_and_verify_state(
    manifest_body: dict,
):

    return (
        base.load_and_verify_state(
            manifest_body
        )
    )


# ============================================================
# FRESH EPHEMERAL RECONCILIATION
# ============================================================


def build_fresh_reconciliation(
    state: dict,
    key: str,
    secret: str,
):

    account = (
        live.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    preflight.validate_account(
        account
    )

    positions = (
        live.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    open_orders = (
        live.get_json(
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

    return (
        reconcile.build_reconciliation(
            state=
                state,

            account=
                account,

            positions=
                positions,

            open_orders=
                open_orders,
        )
    )


# ============================================================
# RECONCILIATION / MANIFEST BINDING
# ============================================================


def verify_fresh_reconciliation(
    manifest_body: dict,
    state: dict,
    package: dict,
):

    if (
        not isinstance(
            package,
            dict,
        )
        or
        "reconciliation"
        not in package
        or
        "reconciliation_sha256"
        not in package
    ):

        raise RuntimeError(
            "Invalid fresh reconciliation package."
        )

    body = (
        package[
            "reconciliation"
        ]
    )

    calculated = (
        reconcile.sha256_json(
            body
        )
    )

    recorded = str(
        package[
            "reconciliation_sha256"
        ]
    )

    if calculated != recorded:

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation hash failed."
        )

    if (
        body.get(
            "schema"
        )
        != reconcile.SCHEMA
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "unexpected reconciliation schema."
        )

    expected_state_hash = (
        base.sha256_json(
            state
        )
    )

    if (
        body.get(
            "strategy_state_sha256"
        )
        != expected_state_hash
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation is not bound "
            "to current strategy state."
        )

    if (
        str(
            body.get(
                "strategy_state_date"
            )
        )
        != str(
            state.get(
                "last_date"
            )
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation date mismatch."
        )

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "LIVE INTENT STOP: "
                f"fresh reconciliation field "
                f"{field!r} is not TRUE."
            )

    if (
        body.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation unexpectedly "
            "authorizes execution."
        )

    if (
        body.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation unexpectedly "
            "has network writes."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "fresh reconciliation write mode "
            "is not DISABLED."
        )

    if (
        int(
            body.get(
                "open_order_count",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "open orders exist."
        )

    structure = (
        manifest_body[
            "position_reconciliation"
        ]
    )

    if (
        body.get(
            "live_account_binding_sha256"
        )
        != structure.get(
            "live_account_binding_sha256"
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "live account binding changed since "
            "manifest compilation."
        )

    if (
        body.get(
            "reconciliation_status"
        )
        != structure.get(
            "reconciliation_status"
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "live account reconciliation status changed. "
            "Regenerate manifest first."
        )

    if (
        int(
            body.get(
                "position_count",
                -1,
            )
        )
        != int(
            structure.get(
                "position_count",
                -2,
            )
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "live position structure changed since "
            "manifest compilation. "
            "Regenerate manifest first."
        )

    if (
        body.get(
            "manifest_type"
        )
        != manifest_body.get(
            "manifest_type"
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "event type changed during reconciliation."
        )

    if (
        body.get(
            "event_source"
        )
        != manifest_body.get(
            "event_source"
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "event source changed during reconciliation."
        )

    if (
        body.get(
            "strategy_event_present"
        )
        is not manifest_body.get(
            "strategy_event_present"
        )
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "event-presence flag changed during reconciliation."
        )

    return body


# ============================================================
# NON-EXECUTABLE INTENTS
# ============================================================


def compile_candidate_intents(
    manifest_id: str,
    manifest_body: dict,
    reconciliation_body: dict,
):

    if not bool(
        manifest_body.get(
            "strategy_event_present",
            False,
        )
    ):

        return []

    source = str(
        manifest_body.get(
            "event_source",
            "",
        )
    )

    # --------------------------------------------------------
    # Scheduled events require the execution-time compiler.
    # --------------------------------------------------------

    if source == "SCHEDULED":

        raise RuntimeError(
            "SCHEDULED LIVE INTENT SAFETY STOP: "
            "scheduled events must be compiled by "
            "the position-aware scheduled execution "
            "compiler v1.1."
        )

    if source != "EMERGENCY":

        raise RuntimeError(
            "Unexpected live event source."
        )

    rows = (
        reconciliation_body.get(
            "reconciliation_rows",
            []
        )
    )

    if not isinstance(
        rows,
        list,
    ):

        raise RuntimeError(
            "Invalid reconciliation rows."
        )

    intents = []

    for row in rows:

        if not isinstance(
            row,
            dict,
        ):

            raise RuntimeError(
                "Invalid reconciliation row."
            )

        direction = str(
            row.get(
                "diagnostic_direction",
                "",
            )
        ).upper()

        if direction == "HOLD":

            continue

        if direction not in {
            "BUY",
            "SELL",
        }:

            raise RuntimeError(
                "LIVE INTENT STOP: "
                "broker reconciliation cannot determine "
                "an emergency trade direction."
            )

        symbol = str(
            row.get(
                "symbol",
                "",
            )
        ).upper()

        if (
            symbol
            not in writer.ALLOWED_SYMBOLS
        ):

            raise RuntimeError(
                "LIVE INTENT STOP: "
                f"unsupported symbol {symbol!r}."
            )

        side = (
            direction.lower()
        )

        client_order_id = (
            base.build_client_order_id(
                manifest_id=
                    manifest_id,

                side=
                    side,

                symbol=
                    symbol,
            )
        )

        # ----------------------------------------------------
        # Persist only strategy target information.
        #
        # Do NOT persist:
        #
        # - current live weights
        # - live quantities
        # - live prices
        # - market values
        # - dollar deltas
        # ----------------------------------------------------

        intents.append({
            "symbol":
                symbol,

            "side":
                side,

            "target_weight":
                round(
                    float(
                        row.get(
                            "target_weight",
                            0.0,
                        )
                    ),
                    12,
                ),

            "client_order_id":
                client_order_id,

            "notional_usd":
                None,

            "executable":
                False,
        })

    return intents


# ============================================================
# INTENT PACKAGE
# ============================================================


def build_intent_package_v1_1(
    manifest_package: dict,
    intents: list,
):

    manifest_body = (
        manifest_package[
            "manifest"
        ]
    )

    structure = (
        manifest_body[
            "position_reconciliation"
        ]
    )

    # ========================================================
    # COMPLETE STRUCTURAL RECONCILIATION PROOF
    # ========================================================
    #
    # These are stable safety attestations.
    #
    # They contain no:
    #
    # - live quantities
    # - live market values
    # - live prices
    # - broker weight deltas
    # - cash balances
    #
    # ========================================================

    position_reconciliation = {
        "policy":
            structure[
                "policy"
            ],

        "live_account_binding_sha256":
            structure[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            structure[
                "reconciliation_status"
            ],

        "position_count":
            structure[
                "position_count"
            ],

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            structure[
                "frozen_execution_universe_verified"
            ],

        "long_only_verified":
            structure[
                "long_only_verified"
            ],

        "no_unmanaged_positions_verified":
            structure[
                "no_unmanaged_positions_verified"
            ],

        "no_open_orders_verified":
            structure[
                "no_open_orders_verified"
            ],

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,
    }

    # ========================================================
    # FAIL CLOSED IF STRUCTURAL PROOF IS INCOMPLETE
    # ========================================================

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            position_reconciliation.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "LIVE INTENT STOP: "
                f"structural reconciliation proof "
                f"{field!r} is not TRUE."
            )

    if (
        int(
            position_reconciliation[
                "open_order_count"
            ]
        )
        != 0
    ):

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "structural reconciliation proof "
            "contains open orders."
        )

    body = {
        "schema":
            INTENT_SCHEMA,

        "manifest_id":
            manifest_package[
                "manifest_id"
            ],

        "manifest_sha256":
            manifest_package[
                "manifest_sha256"
            ],

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            manifest_body[
                "strategy_state_date"
            ],

        "strategy_state_sha256":
            manifest_body[
                "strategy_state_sha256"
            ],

        "manifest_type":
            manifest_body[
                "manifest_type"
            ],

        "event_source":
            manifest_body[
                "event_source"
            ],

        "strategy_event_present":
            manifest_body[
                "strategy_event_present"
            ],

        "position_reconciliation":
            position_reconciliation,

        "candidate_intents":
            intents,

        "scheduled_event_requires_execution_compiler":
            (
                manifest_body[
                    "event_source"
                ]
                == "SCHEDULED"
            ),

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "max_live_execution_notional_usd":
            MAX_LIVE_EXECUTION_NOTIONAL_USD,

        "network_write_capability":
            NETWORK_WRITE_CAPABILITY,

        "broker_write_mode":
            BROKER_WRITE_MODE,

        "orders_submitted":
            ORDERS_SUBMITTED,
    }

    return {
        "intent_bundle_sha256":
            base.sha256_json(
                body
            ),

        "intent_bundle":
            body,
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE ORDER-INTENT "
        "VALIDATOR v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: READ ONLY"
    )

    print(
        "Position-aware reconciliation: ENABLED"
    )

    print(
        "Structural reconciliation proof: COMPLETE"
    )

    print(
        "Live holdings persistence: NONE"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    # ========================================================
    # SAFETY
    # ========================================================

    base.require_intent_arm()

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    writer.validate_frozen_v5_execution_universe(
        writer.FROZEN_V5_SATELLITE_UNIVERSE
    )

    print(
        "\nBroker kill switch: ENGAGED — PASS"
    )

    print(
        "Live write mode: DISABLED — PASS"
    )

    print(
        "Frozen V5 execution universe: PASS"
    )

    # ========================================================
    # MANIFEST / STATE
    # ========================================================

    manifest_package = (
        load_manifest_v1_1()
    )

    manifest_body = (
        manifest_package[
            "manifest"
        ]
    )

    state = (
        load_and_verify_state(
            manifest_body
        )
    )

    print(
        "\nPosition-aware manifest schema: PASS"
    )

    print(
        "Manifest SHA256 verification: PASS"
    )

    print(
        "Strategy-state hash match: PASS"
    )

    print(
        f"Manifest ID: "
        f"{manifest_package['manifest_id']}"
    )

    # ========================================================
    # FRESH LIVE RECONCILIATION
    # ========================================================

    key, secret = (
        live.load_credentials()
    )

    fresh_package = (
        build_fresh_reconciliation(
            state=
                state,

            key=
                key,

            secret=
                secret,
        )
    )

    fresh_body = (
        verify_fresh_reconciliation(
            manifest_body=
                manifest_body,

            state=
                state,

            package=
                fresh_package,
        )
    )

    print(
        "\nFresh broker reconciliation: PASS"
    )

    print(
        "Live account binding: PASS"
    )

    print(
        "Live position structure: PASS"
    )

    print(
        "Complete structural proof: PASS"
    )

    print(
        "Open orders: 0 — PASS"
    )

    print(
        "Live dollar values persisted: NO"
    )

    print(
        "Individual live holdings persisted: NO"
    )

    # ========================================================
    # NON-EXECUTABLE INTENTS
    # ========================================================

    intents = (
        compile_candidate_intents(
            manifest_id=
                manifest_package[
                    "manifest_id"
                ],

            manifest_body=
                manifest_body,

            reconciliation_body=
                fresh_body,
        )
    )

    intent_package = (
        build_intent_package_v1_1(
            manifest_package=
                manifest_package,

            intents=
                intents,
        )
    )

    base.write_intent_package(
        intent_package
    )

    # ========================================================
    # REPORT
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "POSITION-AWARE LIVE ORDER INTENTS"
    )

    print(
        "============================================"
    )

    print(
        f"\nManifest type: "
        f"{manifest_body['manifest_type']}"
    )

    print(
        f"Event source: "
        f"{manifest_body['event_source']}"
    )

    print(
        f"Genuine strategy event present: "
        f"{manifest_body['strategy_event_present']}"
    )

    print(
        f"Candidate intents: "
        f"{len(intents)}"
    )

    for intent in intents:

        print(
            f"\n{intent['symbol']}: "
            f"{intent['side'].upper()}"
        )

        print(
            f"  Target weight: "
            f"{float(intent['target_weight']):.3%}"
        )

        print(
            f"  Client order ID: "
            f"{intent['client_order_id']}"
        )

        print(
            "  Notional USD: UNASSIGNED"
        )

        print(
            "  Executable: FALSE"
        )

    print(
        f"\nIntent bundle SHA256: "
        f"{intent_package['intent_bundle_sha256']}"
    )

    print(
        "\nLive execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE ORDER-INTENT v1.1 GATE: PASS"
    )

    print(
        "============================================"
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
            "LIVE ORDER-INTENT v1.1 GATE: FAILED",
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

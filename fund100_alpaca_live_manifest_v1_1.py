from __future__ import annotations

import json
import sys

import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_manifest as base
import fund100_alpaca_live_position_reconcile as reconcile
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_writer_disconnected_v1_1 as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE DRY-RUN MANIFEST v1.1
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# v1.1 replaces the old:
#
#     "live account must contain zero positions"
#
# rule with:
#
#     "existing live positions must pass the Fund-100
#      position-reconciliation contract"
#
# IMPORTANT:
#
# - GET only
# - no broker writes
# - no live execution authorization
# - no order notionals
# - no live holdings persisted
# - no live dollar balances persisted
# - no volatile broker market-value snapshot persisted
#
# The actual market-value reconciliation remains ephemeral.
#
# ============================================================


MANIFEST_SCHEMA = (
    "FUND100_LIVE_DRYRUN_MANIFEST_V1_1"
)

RECONCILIATION_POLICY = (
    "EPHEMERAL_POSITION_AWARE_V1"
)

LIVE_EXECUTION_AUTHORIZED = False

MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.00

NETWORK_WRITE_CAPABILITY = False

BROKER_WRITE_MODE = "DISABLED"

ORDERS_SUBMITTED = 0


# ============================================================
# RECONCILIATION VALIDATION
# ============================================================


def validate_reconciliation_package(
    state: dict,
    strategy_context: dict,
    package: dict,
):

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid reconciliation package."
        )

    if (
        "reconciliation_sha256"
        not in package
        or
        "reconciliation"
        not in package
    ):

        raise RuntimeError(
            "Incomplete reconciliation package."
        )

    body = (
        package[
            "reconciliation"
        ]
    )

    recorded_hash = str(
        package[
            "reconciliation_sha256"
        ]
    )

    calculated_hash = (
        reconcile.sha256_json(
            body
        )
    )

    if recorded_hash != calculated_hash:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation SHA256 verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != reconcile.SCHEMA
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "unexpected reconciliation schema."
        )

    if (
        body.get(
            "strategy"
        )
        != base.EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation strategy mismatch."
        )

    state_hash = (
        base.sha256_json(
            state
        )
    )

    if (
        body.get(
            "strategy_state_sha256"
        )
        != state_hash
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation is not bound to "
            "the current shadow state."
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
            "LIVE MANIFEST STOP: "
            "reconciliation state date mismatch."
        )

    if (
        body.get(
            "manifest_type"
        )
        != strategy_context[
            "manifest_type"
        ]
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation manifest type mismatch."
        )

    if (
        body.get(
            "event_source"
        )
        != strategy_context[
            "event_source"
        ]
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation event source mismatch."
        )

    if (
        body.get(
            "strategy_event_present"
        )
        is not strategy_context[
            "strategy_event_present"
        ]
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation event flag mismatch."
        )

    if (
        body.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation unexpectedly authorizes execution."
        )

    if (
        body.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation unexpectedly has "
            "network-write capability."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation write mode is not DISABLED."
        )

    if (
        int(
            body.get(
                "orders_submitted",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "reconciliation order count is not zero."
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
                "LIVE MANIFEST STOP: "
                f"reconciliation safety field "
                f"{field!r} is not TRUE."
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
            "LIVE MANIFEST STOP: "
            "reconciliation contains open orders."
        )

    account_binding = str(
        body.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip()

    if not account_binding:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "live account binding is missing."
        )

    position_count = int(
        body.get(
            "position_count",
            -1,
        )
    )

    if position_count < 0:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "invalid live position count."
        )

    status = str(
        body.get(
            "reconciliation_status",
            "",
        )
    )

    if status not in {
        "EMPTY_ZERO_EQUITY",
        "POSITION_AWARE",
    }:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "unexpected reconciliation status."
        )

    return body


# ============================================================
# LIVE READ-ONLY ENVIRONMENT
# ============================================================


def validate_live_environment_and_reconcile(
    state: dict,
):

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE MANIFEST SAFETY STOP: "
            "broker kill switch must be ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    writer.validate_frozen_v5_execution_universe(
        writer.FROZEN_V5_SATELLITE_UNIVERSE
    )

    key, secret = (
        live.load_credentials()
    )

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

    package = (
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

    return (
        key,
        secret,
        package,
    )


# ============================================================
# MANIFEST v1.1
# ============================================================


def build_manifest_v1_1(
    state: dict,
    strategy_context: dict,
    reconciliation_package: dict,
):

    reconciliation_body = (
        validate_reconciliation_package(
            state=
                state,

            strategy_context=
                strategy_context,

            package=
                reconciliation_package,
        )
    )

    state_hash = (
        base.sha256_json(
            state
        )
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Deliberately DO NOT copy any of these volatile/private
    # reconciliation fields into the persistent manifest:
    #
    # - broker_snapshot_sha256
    # - reconciliation_rows
    # - cash_weight
    # - diagnostic dollar deltas
    # - live market values
    # - live quantities
    # - live prices
    #
    # This keeps the manifest stable across ordinary market
    # price changes while still proving that the live account
    # passed reconciliation at compilation time.
    # --------------------------------------------------------

    structural_reconciliation = {
        "schema":
            reconciliation_body[
                "schema"
            ],

        "policy":
            RECONCILIATION_POLICY,

        "live_account_binding_sha256":
            reconciliation_body[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            reconciliation_body[
                "reconciliation_status"
            ],

        "position_count":
            int(
                reconciliation_body[
                    "position_count"
                ]
            ),

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,
    }

    manifest_body = {
        "schema":
            MANIFEST_SCHEMA,

        "strategy":
            base.EXPECTED_STRATEGY,

        "strategy_state_date":
            str(
                state[
                    "last_date"
                ]
            ),

        "strategy_state_sha256":
            state_hash,

        "manifest_type":
            strategy_context[
                "manifest_type"
            ],

        "event_source":
            strategy_context[
                "event_source"
            ],

        "strategy_event_present":
            strategy_context[
                "strategy_event_present"
            ],

        "target_weights":
            strategy_context[
                "target_weights"
            ],

        "position_reconciliation":
            structural_reconciliation,

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "max_live_execution_notional_usd":
            MAX_LIVE_EXECUTION_NOTIONAL_USD,

        "network_write_capability":
            NETWORK_WRITE_CAPABILITY,

        "proposed_orders":
            [],

        "broker_environment":
            "ALPACA_LIVE",

        "broker_write_mode":
            BROKER_WRITE_MODE,

        "kill_switch_required":
            "ENGAGED",

        "orders_submitted":
            ORDERS_SUBMITTED,
    }

    manifest_hash = (
        base.sha256_json(
            manifest_body
        )
    )

    manifest_id = (
        "f100-live-"
        + str(
            state[
                "last_date"
            ]
        ).replace(
            "-",
            "",
        )
        + "-"
        + manifest_hash[
            :16
        ]
    )

    return {
        "manifest_id":
            manifest_id,

        "manifest_sha256":
            manifest_hash,

        "manifest":
            manifest_body,
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE DRY-RUN MANIFEST v1.1"
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
        "Position reconciliation: ENABLED"
    )

    print(
        "Live holdings persistence: NONE"
    )

    print(
        "HTTP live-write implementation: ABSENT"
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

    base.require_manifest_arm()

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE MANIFEST SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    boundary.require_live_writes_disabled()

    print(
        "Kill-switch safety state: PASS"
    )

    print(
        "Live write mode: DISABLED — PASS"
    )

    # ========================================================
    # STRATEGY
    # ========================================================

    state = (
        base.load_state()
    )

    context = (
        base.build_strategy_context(
            state
        )
    )

    print(
        f"\nV5-002 state date: "
        f"{state['last_date']}"
    )

    print(
        f"Manifest type: "
        f"{context['manifest_type']}"
    )

    print(
        f"Genuine strategy event present: "
        f"{context['strategy_event_present']}"
    )

    # ========================================================
    # POSITION-AWARE LIVE VALIDATION
    # ========================================================

    (
        key,
        secret,
        reconciliation_package,
    ) = (
        validate_live_environment_and_reconcile(
            state
        )
    )

    reconciliation_body = (
        validate_reconciliation_package(
            state=
                state,

            strategy_context=
                context,

            package=
                reconciliation_package,
        )
    )

    print(
        "\nLive account validation: PASS"
    )

    print(
        "Position-aware reconciliation: PASS"
    )

    print(
        f"Validated live position count: "
        f"{reconciliation_body['position_count']}"
    )

    print(
        "Live open orders: 0 — PASS"
    )

    print(
        "Frozen V5 execution universe: PASS"
    )

    print(
        "Long-only broker state: PASS"
    )

    print(
        "Unmanaged positions: NONE"
    )

    print(
        "Live dollar values persisted: NO"
    )

    print(
        "Individual live holdings persisted: NO"
    )

    # ========================================================
    # TARGET ASSET VALIDATION
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "TARGET ASSET VALIDATION"
    )

    print(
        "============================================"
    )

    base.validate_target_assets(
        target=
            context[
                "target_weights"
            ],

        key=
            key,

        secret=
            secret,
    )

    # ========================================================
    # BUILD / STORE MANIFEST
    # ========================================================

    manifest = (
        build_manifest_v1_1(
            state=
                state,

            strategy_context=
                context,

            reconciliation_package=
                reconciliation_package,
        )
    )

    base.write_manifest(
        manifest
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE DRY-RUN MANIFEST v1.1"
    )

    print(
        "============================================"
    )

    print(
        f"\nManifest ID: "
        f"{manifest['manifest_id']}"
    )

    print(
        f"Manifest SHA256: "
        f"{manifest['manifest_sha256']}"
    )

    print(
        "\nTarget weights:"
    )

    for symbol, weight in (
        manifest[
            "manifest"
        ][
            "target_weights"
        ].items()
    ):

        print(
            f"  {symbol}: "
            f"{float(weight):.3%}"
        )

    print(
        "\nPosition reconciliation policy: "
        + RECONCILIATION_POLICY
    )

    print(
        "Volatile broker snapshot persisted: FALSE"
    )

    print(
        "Proposed live orders: 0"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Manifest hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE MANIFEST v1.1 GATE: PASS"
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
            "LIVE MANIFEST v1.1 GATE: FAILED",
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

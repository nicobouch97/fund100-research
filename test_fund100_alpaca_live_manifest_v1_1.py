from __future__ import annotations

import json

import pytest

import fund100_alpaca_live_manifest as base
import fund100_alpaca_live_manifest_v1_1 as manifest
import fund100_alpaca_live_position_reconcile as reconcile


def state():

    return {
        "strategy":
            "V5-002_SHADOW",

        "last_date":
            "2099-01-01",

        "satellite_weights": {
            "EEM":
                0.083333333333,

            "XLE":
                0.083333333333,

            "XLV":
                0.083333333334,
        },

        "pending_target":
            None,

        "pending_source":
            None,
    }


def strategy_context():

    return (
        base.build_strategy_context(
            state()
        )
    )


def reconciliation_body(
    *,
    position_count=4,
    broker_snapshot_sha256="private-broker-hash-a",
    gross_delta=1.23,
):

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    return {
        "schema":
            reconcile.SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            current_state[
                "last_date"
            ],

        "strategy_state_sha256":
            base.sha256_json(
                current_state
            ),

        "manifest_type":
            context[
                "manifest_type"
            ],

        "event_source":
            context[
                "event_source"
            ],

        "strategy_event_present":
            context[
                "strategy_event_present"
            ],

        "reconciliation_status":
            "POSITION_AWARE",

        "live_account_binding_sha256":
            "stable-account-binding",

        "broker_snapshot_sha256":
            broker_snapshot_sha256,

        "position_count":
            position_count,

        "open_order_count":
            0,

        "target_weights":
            context[
                "target_weights"
            ],

        "cash_weight":
            0.0,

        "reconciliation_rows": [
            {
                "symbol":
                    "ACWI",

                "current_market_value_usd":
                    75.0,

                "diagnostic_delta_usd":
                    gross_delta,

                "executable":
                    False,
            }
        ],

        "gross_diagnostic_delta_usd":
            gross_delta,

        "diagnostic_buy_total_usd":
            gross_delta,

        "diagnostic_sell_total_usd":
            0.0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_execution_authorized":
            False,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "orders_submitted":
            0,

        "persistence_policy":
            "EPHEMERAL_NOT_COMMITTED",
    }


def package_from_body(
    body,
):

    return {
        "reconciliation_sha256":
            reconcile.sha256_json(
                body
            ),

        "reconciliation":
            body,
    }


def test_position_aware_manifest_builds():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    package = (
        package_from_body(
            reconciliation_body()
        )
    )

    result = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package,
        )
    )

    body = (
        result[
            "manifest"
        ]
    )

    assert (
        body[
            "schema"
        ]
        == manifest.MANIFEST_SCHEMA
    )

    assert (
        body[
            "position_reconciliation"
        ][
            "position_count"
        ]
        == 4
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "network_write_capability"
        ]
        is False
    )

    assert (
        body[
            "proposed_orders"
        ]
        == []
    )


def test_manifest_does_not_persist_live_holdings_or_values():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    result = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    reconciliation_body()
                ),
        )
    )

    serialized = (
        json.dumps(
            result,
            sort_keys=True,
        )
    )

    assert (
        "broker_snapshot_sha256"
        not in serialized
    )

    assert (
        "reconciliation_rows"
        not in serialized
    )

    assert (
        "gross_diagnostic_delta_usd"
        not in serialized
    )

    assert (
        "diagnostic_buy_total_usd"
        not in serialized
    )

    assert (
        "diagnostic_sell_total_usd"
        not in serialized
    )

    assert (
        "current_market_value_usd"
        not in serialized
    )


def test_manifest_is_stable_when_only_market_values_change():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    body_a = (
        reconciliation_body(
            broker_snapshot_sha256=
                "private-broker-hash-a",

            gross_delta=
                1.23,
        )
    )

    body_b = (
        reconciliation_body(
            broker_snapshot_sha256=
                "private-broker-hash-b",

            gross_delta=
                9.87,
        )
    )

    result_a = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    body_a
                ),
        )
    )

    result_b = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    body_b
                ),
        )
    )

    assert (
        result_a
        == result_b
    )


def test_manifest_changes_when_position_count_changes():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    result_a = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    reconciliation_body(
                        position_count=3
                    )
                ),
        )
    )

    result_b = (
        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    reconciliation_body(
                        position_count=4
                    )
                ),
        )
    )

    assert (
        result_a[
            "manifest_sha256"
        ]
        != result_b[
            "manifest_sha256"
        ]
    )


def test_reconciliation_hash_mismatch_is_rejected():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    package = (
        package_from_body(
            reconciliation_body()
        )
    )

    package[
        "reconciliation_sha256"
    ] = "wrong-hash"

    with pytest.raises(
        RuntimeError,
        match="SHA256 verification failed",
    ):

        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package,
        )


def test_open_orders_are_rejected():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    body = (
        reconciliation_body()
    )

    body[
        "open_order_count"
    ] = 1

    body[
        "no_open_orders_verified"
    ] = False

    with pytest.raises(
        RuntimeError,
        match="safety field",
    ):

        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    body
                ),
        )


def test_execution_authorization_is_rejected():

    current_state = (
        state()
    )

    context = (
        base.build_strategy_context(
            current_state
        )
    )

    body = (
        reconciliation_body()
    )

    body[
        "live_execution_authorized"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="unexpectedly authorizes execution",
    ):

        manifest.build_manifest_v1_1(
            state=
                current_state,

            strategy_context=
                context,

            reconciliation_package=
                package_from_body(
                    body
                ),
        )

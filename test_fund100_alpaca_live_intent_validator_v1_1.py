from __future__ import annotations

import json

import pytest

import fund100_alpaca_live_intent_validator as base
import fund100_alpaca_live_intent_validator_v1_1 as validator
import fund100_alpaca_live_manifest_v1_1 as manifest
import fund100_alpaca_live_position_reconcile as reconcile


def state():

    return {
        "strategy":
            "V5-002_SHADOW",

        "last_date":
            "2099-01-01",

        "satellite_weights": {
            "SPY":
                0.0,

            "IWM":
                0.0,

            "EFA":
                0.0,

            "EEM":
                0.083333333333,

            "VNQ":
                0.0,

            "XLK":
                0.0,

            "XLF":
                0.0,

            "XLI":
                0.0,

            "XLV":
                0.083333333334,

            "XLP":
                0.0,

            "XLY":
                0.0,

            "XLE":
                0.083333333333,

            "XLU":
                0.0,
        },

        "pending_target":
            None,

        "pending_source":
            None,
    }


def structural_reconciliation(
    *,
    position_count=4,
    status="POSITION_AWARE",
):

    return {
        "schema":
            reconcile.SCHEMA,

        "policy":
            manifest.RECONCILIATION_POLICY,

        "live_account_binding_sha256":
            "account-binding-test",

        "reconciliation_status":
            status,

        "position_count":
            position_count,

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


def manifest_package(
    *,
    event=False,
    source="NONE",
    manifest_type="NO_EVENT_SNAPSHOT",
):

    current_state = (
        state()
    )

    body = {
        "schema":
            manifest.MANIFEST_SCHEMA,

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
            manifest_type,

        "event_source":
            source,

        "strategy_event_present":
            event,

        "target_weights": {
            "ACWI":
                0.75,

            "EEM":
                0.083333333333,

            "XLE":
                0.083333333333,

            "XLV":
                0.083333333334,
        },

        "position_reconciliation":
            structural_reconciliation(),

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "proposed_orders":
            [],

        "broker_environment":
            "ALPACA_LIVE",

        "broker_write_mode":
            "DISABLED",

        "kill_switch_required":
            "ENGAGED",

        "orders_submitted":
            0,
    }

    manifest_hash = (
        base.sha256_json(
            body
        )
    )

    return {
        "manifest_id":
            "f100-live-test-"
            + manifest_hash[
                :16
            ],

        "manifest_sha256":
            manifest_hash,

        "manifest":
            body,
    }


def fresh_reconciliation_package(
    *,
    event=False,
    source="NONE",
    manifest_type="NO_EVENT_SNAPSHOT",
    position_count=4,
    account_binding="account-binding-test",
    broker_snapshot="volatile-a",
    rows=None,
):

    if rows is None:

        rows = []

    current_state = (
        state()
    )

    body = {
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
            manifest_type,

        "event_source":
            source,

        "strategy_event_present":
            event,

        "reconciliation_status":
            "POSITION_AWARE",

        "live_account_binding_sha256":
            account_binding,

        "broker_snapshot_sha256":
            broker_snapshot,

        "position_count":
            position_count,

        "open_order_count":
            0,

        "target_weights":
            {},

        "cash_weight":
            0.0,

        "reconciliation_rows":
            rows,

        "gross_diagnostic_delta_usd":
            0.0,

        "diagnostic_buy_total_usd":
            0.0,

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

    return {
        "reconciliation_sha256":
            reconcile.sha256_json(
                body
            ),

        "reconciliation":
            body,
    }


def test_no_event_produces_no_intents():

    package = (
        manifest_package()
    )

    fresh = (
        fresh_reconciliation_package()
    )

    body = (
        validator.verify_fresh_reconciliation(
            manifest_body=
                package[
                    "manifest"
                ],

            state=
                state(),

            package=
                fresh,
        )
    )

    intents = (
        validator.compile_candidate_intents(
            manifest_id=
                package[
                    "manifest_id"
                ],

            manifest_body=
                package[
                    "manifest"
                ],

            reconciliation_body=
                body,
        )
    )

    assert intents == []


def test_account_binding_change_is_rejected():

    package = (
        manifest_package()
    )

    fresh = (
        fresh_reconciliation_package(
            account_binding=
                "different-account"
        )
    )

    with pytest.raises(
        RuntimeError,
        match="account binding changed",
    ):

        validator.verify_fresh_reconciliation(
            manifest_body=
                package[
                    "manifest"
                ],

            state=
                state(),

            package=
                fresh,
        )


def test_position_count_change_is_rejected():

    package = (
        manifest_package()
    )

    fresh = (
        fresh_reconciliation_package(
            position_count=3
        )
    )

    with pytest.raises(
        RuntimeError,
        match="position structure changed",
    ):

        validator.verify_fresh_reconciliation(
            manifest_body=
                package[
                    "manifest"
                ],

            state=
                state(),

            package=
                fresh,
        )


def test_scheduled_event_still_fails_closed():

    package = (
        manifest_package(
            event=True,
            source="SCHEDULED",
            manifest_type="PENDING_STRATEGY_EVENT",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="scheduled execution compiler v1.1",
    ):

        validator.compile_candidate_intents(
            manifest_id=
                package[
                    "manifest_id"
                ],

            manifest_body=
                package[
                    "manifest"
                ],

            reconciliation_body=
                fresh_reconciliation_package(
                    event=True,
                    source="SCHEDULED",
                    manifest_type="PENDING_STRATEGY_EVENT",
                )[
                    "reconciliation"
                ],
        )


def test_emergency_intents_persist_no_live_values():

    package = (
        manifest_package(
            event=True,
            source="EMERGENCY",
            manifest_type="PENDING_STRATEGY_EVENT",
        )
    )

    rows = [
        {
            "symbol":
                "ACWI",

            "target_weight":
                0.75,

            "current_weight":
                0.70,

            "weight_delta":
                0.05,

            "current_market_value_usd":
                70.0,

            "target_market_value_usd":
                75.0,

            "diagnostic_delta_usd":
                5.0,

            "diagnostic_direction":
                "BUY",

            "executable":
                False,
        },
        {
            "symbol":
                "EEM",

            "target_weight":
                0.083333333333,

            "current_weight":
                0.10,

            "weight_delta":
                -0.016666666667,

            "current_market_value_usd":
                10.0,

            "target_market_value_usd":
                8.3333333333,

            "diagnostic_delta_usd":
                -1.6666666667,

            "diagnostic_direction":
                "SELL",

            "executable":
                False,
        },
    ]

    intents = (
        validator.compile_candidate_intents(
            manifest_id=
                package[
                    "manifest_id"
                ],

            manifest_body=
                package[
                    "manifest"
                ],

            reconciliation_body=
                fresh_reconciliation_package(
                    event=True,
                    source="EMERGENCY",
                    manifest_type="PENDING_STRATEGY_EVENT",
                    rows=rows,
                )[
                    "reconciliation"
                ],
        )
    )

    assert len(
        intents
    ) == 2

    serialized = (
        json.dumps(
            intents,
            sort_keys=True,
        )
    )

    assert (
        "current_weight"
        not in serialized
    )

    assert (
        "weight_delta"
        not in serialized
    )

    assert (
        "current_market_value_usd"
        not in serialized
    )

    assert (
        "target_market_value_usd"
        not in serialized
    )

    assert (
        "diagnostic_delta_usd"
        not in serialized
    )

    assert all(
        intent[
            "notional_usd"
        ]
        is None
        for intent
        in intents
    )

    assert all(
        intent[
            "executable"
        ]
        is False
        for intent
        in intents
    )


def test_bundle_is_stable_across_volatile_broker_snapshots():

    package = (
        manifest_package()
    )

    intents = []

    bundle_a = (
        validator.build_intent_package_v1_1(
            manifest_package=
                package,

            intents=
                intents,
        )
    )

    bundle_b = (
        validator.build_intent_package_v1_1(
            manifest_package=
                package,

            intents=
                intents,
        )
    )

    assert bundle_a == bundle_b

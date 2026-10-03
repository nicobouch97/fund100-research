from __future__ import annotations

import fund100_alpaca_live_intent_validator as base
import fund100_alpaca_live_intent_validator_v1_1 as validator
import fund100_alpaca_live_manifest_v1_1 as manifest


def manifest_package():

    body = {
        "schema":
            manifest.MANIFEST_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            "2099-01-01",

        "strategy_state_sha256":
            "state-hash",

        "manifest_type":
            "NO_EVENT_SNAPSHOT",

        "event_source":
            "NONE",

        "strategy_event_present":
            False,

        "target_weights": {
            "ACWI":
                1.0,
        },

        "position_reconciliation": {
            "schema":
                "FUND100_LIVE_POSITION_RECONCILIATION_V1",

            "policy":
                manifest.RECONCILIATION_POLICY,

            "live_account_binding_sha256":
                "account-binding-test",

            "reconciliation_status":
                "EMPTY_ZERO_EQUITY",

            "position_count":
                0,

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
        },

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

    digest = (
        base.sha256_json(
            body
        )
    )

    return {
        "manifest_id":
            "f100-live-structural-test",

        "manifest_sha256":
            digest,

        "manifest":
            body,
    }


def test_intent_bundle_preserves_complete_structural_proof():

    package = (
        validator.build_intent_package_v1_1(
            manifest_package=
                manifest_package(),

            intents=[],
        )
    )

    structure = (
        package[
            "intent_bundle"
        ][
            "position_reconciliation"
        ]
    )

    assert (
        structure[
            "frozen_execution_universe_verified"
        ]
        is True
    )

    assert (
        structure[
            "long_only_verified"
        ]
        is True
    )

    assert (
        structure[
            "no_unmanaged_positions_verified"
        ]
        is True
    )

    assert (
        structure[
            "no_open_orders_verified"
        ]
        is True
    )

    assert (
        structure[
            "live_holdings_persisted"
        ]
        is False
    )

    assert (
        structure[
            "live_dollar_values_persisted"
        ]
        is False
    )

    assert (
        structure[
            "volatile_broker_snapshot_persisted"
        ]
        is False
    )


def test_intent_bundle_still_contains_no_sensitive_position_values():

    package = (
        validator.build_intent_package_v1_1(
            manifest_package=
                manifest_package(),

            intents=[],
        )
    )

    structure = (
        package[
            "intent_bundle"
        ][
            "position_reconciliation"
        ]
    )

    forbidden = {
        "broker_snapshot_sha256",
        "reconciliation_rows",
        "cash_weight",
        "gross_diagnostic_delta_usd",
        "diagnostic_buy_total_usd",
        "diagnostic_sell_total_usd",
    }

    assert (
        forbidden
        .intersection(
            structure.keys()
        )
        == set()
    )

from __future__ import annotations

import pytest

import fund100_pre_live_release_gate_v1_1 as gate


def safe_structure():

    return {
        "schema":
            gate.EXPECTED_POSITION_RECONCILIATION_SCHEMA,

        "policy":
            gate.EXPECTED_POSITION_POLICY,

        "live_account_binding_sha256":
            "account-binding-test",

        "reconciliation_status":
            "POSITION_AWARE",

        "position_count":
            4,

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


def safe_compiler():

    return {
        "schema":
            gate.EXPECTED_COMPILER_SCHEMA,

        "compiler_mode":
            "current",

        "status":
            "NO_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            False,

        "candidate_intents":
            [],

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "orders_submitted":
            0,
    }


def test_safe_current_no_event_is_accepted():

    assert (
        gate.is_safe_current_no_event(
            safe_compiler()
        )
        is True
    )


def test_synthetic_is_not_release_baseline():

    compiler = (
        safe_compiler()
    )

    compiler[
        "compiler_mode"
    ] = "synthetic"

    compiler[
        "status"
    ] = "SYNTHETIC_SCHEDULED_EVENT"

    assert (
        gate.is_safe_current_no_event(
            compiler
        )
        is False
    )


def test_genuine_event_is_not_release_baseline():

    compiler = (
        safe_compiler()
    )

    compiler[
        "status"
    ] = "GENUINE_SCHEDULED_EVENT"

    compiler[
        "genuine_scheduled_event"
    ] = True

    assert (
        gate.is_safe_current_no_event(
            compiler
        )
        is False
    )


def test_candidate_intents_are_not_release_baseline():

    compiler = (
        safe_compiler()
    )

    compiler[
        "candidate_intents"
    ] = [
        {
            "symbol":
                "SPY"
        }
    ]

    assert (
        gate.is_safe_current_no_event(
            compiler
        )
        is False
    )


def test_position_structure_passes():

    result = (
        gate.validate_position_structure(
            safe_structure(),
            require_schema=True,
        )
    )

    assert (
        result[
            "position_count"
        ]
        == 4
    )

    assert (
        result[
            "status"
        ]
        == "POSITION_AWARE"
    )


def test_open_orders_fail_position_structure():

    structure = (
        safe_structure()
    )

    structure[
        "open_order_count"
    ] = 1

    with pytest.raises(
        RuntimeError,
        match="open orders",
    ):

        gate.validate_position_structure(
            structure,
            require_schema=True,
        )


def test_persisted_live_values_fail_position_structure():

    structure = (
        safe_structure()
    )

    structure[
        "live_dollar_values_persisted"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="privacy field",
    ):

        gate.validate_position_structure(
            structure,
            require_schema=True,
        )


def test_unmanaged_position_proof_must_be_true():

    structure = (
        safe_structure()
    )

    structure[
        "no_unmanaged_positions_verified"
    ] = False

    with pytest.raises(
        RuntimeError,
        match="is not TRUE",
    ):

        gate.validate_position_structure(
            structure,
            require_schema=True,
        )


def test_empty_zero_equity_is_valid_structural_state():

    structure = (
        safe_structure()
    )

    structure[
        "reconciliation_status"
    ] = "EMPTY_ZERO_EQUITY"

    structure[
        "position_count"
    ] = 0

    result = (
        gate.validate_position_structure(
            structure,
            require_schema=True,
        )
    )

    assert (
        result[
            "status"
        ]
        == "EMPTY_ZERO_EQUITY"
    )

    assert (
        result[
            "position_count"
        ]
        == 0
    )

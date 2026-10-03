from __future__ import annotations

import pytest

import fund100_alpaca_live_activation_rehearsal_v1_1 as rehearsal
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


def fake_lock_hash():

    return (
        "a" * 64
    )


def test_rehearsal_uses_writer_v1_1():

    assert (
        writer.WRITER_VERSION
        == "1.1"
    )

    assert (
        writer.LIVE_WRITER_CONNECTED
        is False
    )


def test_rehearsal_targets_real_v2_writer_schema():

    assert (
        rehearsal.EXPECTED_PERMIT_SCHEMA
        == "FUND100_LIVE_EXECUTION_PERMIT_V2"
    )

    assert (
        rehearsal.EXPECTED_PERMIT_SCHEMA
        == writer.REQUIRED_PERMIT_SCHEMA
    )


def test_synthetic_permit_is_writer_compatible_in_memory():

    package = (
        rehearsal.build_in_memory_permit(
            release_lock_sha256=
                fake_lock_hash()
        )
    )

    permit, cap = (
        writer.validate_permit_package(
            package
        )
    )

    assert (
        permit[
            "schema"
        ]
        == writer.REQUIRED_PERMIT_SCHEMA
    )

    assert (
        permit[
            "permit_issued"
        ]
        is True
    )

    assert (
        permit[
            "live_execution_authorized"
        ]
        is True
    )

    assert (
        permit[
            "network_write_capability"
        ]
        is True
    )

    assert (
        permit[
            "broker_write_mode"
        ]
        == "ENABLED"
    )

    assert (
        permit[
            "genuine_scheduled_event"
        ]
        is True
    )

    assert (
        cap
        == pytest.approx(
            rehearsal.SYNTHETIC_PERMIT_CAP_USD
        )
    )


def test_full_v5_symbols_pass_writer_validation():

    intents = (
        rehearsal.build_in_memory_intents()
    )

    symbols = {
        item[
            "symbol"
        ]
        for item
        in intents
    }

    assert (
        "SPY"
        in symbols
    )

    assert (
        "VNQ"
        in symbols
    )

    validated, gross = (
        writer.validate_order_batch(
            intents=
                intents,

            permit_cap=
                rehearsal.SYNTHETIC_PERMIT_CAP_USD,
        )
    )

    assert (
        len(
            validated
        )
        == 2
    )

    assert (
        gross
        == pytest.approx(
            4.0
        )
    )


def test_oversized_batch_is_rejected():

    result = (
        rehearsal.prove_cap_enforcement()
    )

    assert (
        result[
            "oversized_batch_rejected"
        ]
        is True
    )

    assert (
        result[
            "permit_cap_enforcement"
        ]
        is True
    )


def test_public_execution_entrypoint_still_disconnects():

    permit_package = (
        rehearsal.build_in_memory_permit(
            release_lock_sha256=
                fake_lock_hash()
        )
    )

    intents = (
        rehearsal.build_in_memory_intents()
    )

    result = (
        rehearsal.prove_public_batch_entrypoint_disconnected(
            permit_package=
                permit_package,

            intents=
                intents,
        )
    )

    assert (
        result[
            "public_batch_entrypoint_disconnected"
        ]
        is True
    )


def test_direct_get_still_disconnects():

    result = (
        rehearsal.prove_direct_get_disconnected()
    )

    assert (
        result[
            "direct_get_disconnected"
        ]
        is True
    )


def test_direct_post_still_disconnects():

    intent = (
        rehearsal.build_in_memory_intents()[
            0
        ]
    )

    result = (
        rehearsal.prove_direct_post_disconnected(
            intent
        )
    )

    assert (
        result[
            "direct_post_disconnected"
        ]
        is True
    )


def test_persisted_output_is_non_authorizing():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                fake_lock_hash(),

            contract_result={
                "permit_schema_accepted":
                    True,

                "full_v5_symbols_accepted":
                    True,

                "order_batch_accepted":
                    True,

                "synthetic_gross_notional_usd":
                    4.0,

                "synthetic_permit_cap_usd":
                    5.0,
            },

            cap_result={
                "oversized_batch_rejected":
                    True,

                "permit_cap_enforcement":
                    True,
            },

            batch_disconnect={
                "public_batch_entrypoint_disconnected":
                    True,
            },

            get_disconnect={
                "direct_get_disconnected":
                    True,
            },

            post_disconnect={
                "direct_post_disconnected":
                    True,
            },
        )
    )

    body = (
        package[
            "rehearsal"
        ]
    )

    rehearsal.assert_safe_output(
        body
    )

    assert (
        body[
            "synthetic_writer_compatible_permit_persisted"
        ]
        is False
    )

    assert (
        body[
            "synthetic_executable_intents_persisted"
        ]
        is False
    )

    assert (
        body[
            "broker_credentials_supplied"
        ]
        is False
    )

    assert (
        body[
            "broker_network_access"
        ]
        is False
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "max_live_execution_notional_usd"
        ]
        == 0.0
    )

    assert (
        body[
            "writer_connected"
        ]
        is False
    )

    assert (
        body[
            "orders_submitted"
        ]
        == 0
    )


def test_safe_output_contains_no_writer_compatible_permit_body():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                fake_lock_hash(),

            contract_result={
                "permit_schema_accepted":
                    True,

                "full_v5_symbols_accepted":
                    True,

                "order_batch_accepted":
                    True,

                "synthetic_gross_notional_usd":
                    4.0,

                "synthetic_permit_cap_usd":
                    5.0,
            },

            cap_result={
                "oversized_batch_rejected":
                    True,

                "permit_cap_enforcement":
                    True,
            },

            batch_disconnect={
                "public_batch_entrypoint_disconnected":
                    True,
            },

            get_disconnect={
                "direct_get_disconnected":
                    True,
            },

            post_disconnect={
                "direct_post_disconnected":
                    True,
            },
        )
    )

    body = (
        package[
            "rehearsal"
        ]
    )

    forbidden = {
        "permit",
        "candidate_intents",
        "intents",
        "orders",
        "approval_token",
        "api_key",
        "api_secret",
    }

    assert (
        forbidden
        .intersection(
            body.keys()
        )
        == set()
    )

from __future__ import annotations

import fund100_alpaca_live_execution_permit as base
import fund100_alpaca_live_execution_permit_v1_1 as permit


def safe_body(
    *,
    mode="current",
    status="NO_SCHEDULED_EVENT",
    genuine=False,
):

    return {
        "schema":
            permit.EXPECTED_COMPILER_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            "2099-01-01",

        "compiler_mode":
            mode,

        "status":
            status,

        "genuine_scheduled_event":
            genuine,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }


def test_expected_compiler_schema_is_v1_1():

    assert (
        permit.EXPECTED_COMPILER_SCHEMA
        == "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
    )

    assert (
        base.EXPECTED_SCHEMA
        == permit.EXPECTED_COMPILER_SCHEMA
    )


def test_no_event_remains_denied():

    reason = (
        base.determine_denial_reason(
            safe_body()
        )
    )

    assert (
        reason
        == "NO_GENUINE_STRATEGY_EVENT"
    )


def test_synthetic_remains_denied():

    reason = (
        base.determine_denial_reason(
            safe_body(
                mode="synthetic",
                status="SYNTHETIC_SCHEDULED_EVENT",
                genuine=False,
            )
        )
    )

    assert (
        reason
        == "SYNTHETIC_ARTIFACT_NEVER_EXECUTABLE"
    )


def test_even_genuine_event_remains_denied():

    reason = (
        base.determine_denial_reason(
            safe_body(
                mode="current",
                status="GENUINE_SCHEDULED_EVENT",
                genuine=True,
            )
        )
    )

    assert (
        reason
        == "LIVE_AUTHORIZATION_NOT_IMPLEMENTED"
    )


def test_built_permit_can_never_authorize():

    compiler_package = {
        "compiler_sha256":
            "compiler-hash-test",

        "compiler":
            safe_body(
                mode="current",
                status="GENUINE_SCHEDULED_EVENT",
                genuine=True,
            ),
    }

    package = (
        base.build_permit(
            compiler_package=
                compiler_package,

            denial_reason=
                "LIVE_AUTHORIZATION_NOT_IMPLEMENTED",
        )
    )

    body = (
        package[
            "permit"
        ]
    )

    assert (
        body[
            "schema"
        ]
        == "FUND100_LIVE_EXECUTION_PERMIT_V1"
    )

    assert (
        body[
            "permit_issued"
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
            "network_write_capability"
        ]
        is False
    )

    assert (
        body[
            "broker_write_mode"
        ]
        == "DISABLED"
    )

    assert (
        body[
            "max_live_execution_notional_usd"
        ]
        == 0.0
    )

    assert (
        body[
            "source_compiler_sha256"
        ]
        == "compiler-hash-test"
    )


def test_v1_1_safety_contract():

    permit.verify_safety_contract()

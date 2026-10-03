from __future__ import annotations

import fund100_pre_live_release_lock_v1_1 as lock


def safe_evidence():

    return {
        "schema":
            lock.EXPECTED_EVIDENCE_SCHEMA,

        "evidence_layer":
            lock.EXPECTED_EVIDENCE_LAYER,

        "engineering_evidence_status":
            "PASS",

        "live_activation_decision":
            "NOT_MADE",

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "writer_connected":
            False,

        "position_aware_live_chain_verified":
            True,
    }


def test_lock_schema_is_v1_1():

    assert (
        lock.LOCK_SCHEMA
        == "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
    )


def test_position_aware_files_are_in_critical_set():

    required = {
        "fund100_alpaca_live_writer_disconnected_v1_1.py",
        "fund100_alpaca_live_position_reconcile.py",
        "fund100_alpaca_live_manifest_v1_1.py",
        "fund100_alpaca_live_intent_validator_v1_1.py",
        "fund100_alpaca_live_scheduled_compiler_v1_1.py",
        "fund100_alpaca_live_execution_permit_v1_1.py",
        "fund100_pre_live_release_gate_v1_1.py",
        "audit_fund100_live_boundary_v1_8.py",
    }

    assert required.issubset(
        set(
            lock.CRITICAL_FILES
        )
    )


def test_current_real_v2_issuer_source_is_snapshotted():

    assert (
        "fund100_alpaca_live_permit_v2_issuer.py"
        in lock.CRITICAL_FILES
    )


def test_release_evidence_is_in_critical_set():

    assert (
        "release_outputs/v5_002/"
        "pre_live_release_evidence.json"
        in lock.CRITICAL_FILES
    )


def test_build_lock_remains_non_authorizing():

    evidence = (
        safe_evidence()
    )

    critical_hashes = {
        "test-file-a":
            "a" * 64,

        "test-file-b":
            "b" * 64,
    }

    lock.apply_v1_1()

    package = (
        lock.build_lock_v1_1(
            evidence=
                evidence,

            evidence_sha256=
                "c" * 64,

            critical_hashes=
                critical_hashes,
        )
    )

    body = (
        package[
            "release_lock"
        ]
    )

    assert (
        body[
            "schema"
        ]
        == lock.LOCK_SCHEMA
    )

    assert (
        body[
            "position_aware_live_chain_verified"
        ]
        is True
    )

    assert (
        body[
            "current_v2_issuer_source_snapshot_locked"
        ]
        is True
    )

    assert (
        body[
            "v2_issuer_v1_1_compatibility_upgrade_required"
        ]
        is True
    )

    assert (
        body[
            "final_activation_lock_required_after_issuer_upgrade"
        ]
        is True
    )

    assert (
        body[
            "automatic_activation_allowed"
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
            "permit_issued"
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
            "network_write_capability"
        ]
        is False
    )

    assert (
        body[
            "writer_connected"
        ]
        is False
    )

from __future__ import annotations

from pathlib import Path

import pytest

import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_pre_live_release_lock_v1_2 as lock


def safe_evidence():

    return {
        "schema":
            lock.base.EXPECTED_EVIDENCE_SCHEMA,

        "evidence_layer":
            lock.base.EXPECTED_EVIDENCE_LAYER,

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


def fake_hashes():

    hashes = {
        "placeholder":
            "a" * 64,
    }

    for filename in (
        lock.FINAL_ISSUER_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = (
            "b" * 64
        )

    return hashes


def test_output_schema_remains_issuer_compatible_v1_1():

    assert (
        lock.LOCK_SCHEMA
        == "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
    )


def test_builder_version_is_v1_2():

    assert (
        lock.BUILDER_VERSION
        == "1.2"
    )


def test_issuer_v1_1_is_in_critical_set():

    assert (
        "fund100_alpaca_live_permit_v2_issuer_v1_1.py"
        in lock.CRITICAL_FILES
    )


def test_static_audit_v1_9_is_in_critical_set():

    assert (
        "audit_fund100_live_boundary_v1_9.py"
        in lock.CRITICAL_FILES
    )


def test_final_lock_builder_is_itself_in_critical_set():

    assert (
        "fund100_pre_live_release_lock_v1_2.py"
        in lock.CRITICAL_FILES
    )


def test_missing_issuer_hash_fails_closed():

    hashes = (
        fake_hashes()
    )

    del hashes[
        "fund100_alpaca_live_permit_v2_issuer_v1_1.py"
    ]

    with pytest.raises(
        RuntimeError,
        match="not hash locked",
    ):

        lock.verify_issuer_hashes_present(
            hashes
        )


def test_missing_static_audit_hash_fails_closed():

    hashes = (
        fake_hashes()
    )

    del hashes[
        "audit_fund100_live_boundary_v1_9.py"
    ]

    with pytest.raises(
        RuntimeError,
        match="not hash locked",
    ):

        lock.verify_issuer_hashes_present(
            hashes
        )


def test_final_lock_clears_only_issuer_compatibility_blockers():

    package = (
        lock.build_lock_v1_2(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "c" * 64,

            critical_hashes=
                fake_hashes(),
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
        == "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
    )

    assert (
        body[
            "release_lock_builder_version"
        ]
        == "1.2"
    )

    assert (
        body[
            "issuer_aware_release_lock"
        ]
        is True
    )

    assert (
        body[
            "v2_issuer_v1_1_source_locked"
        ]
        is True
    )

    assert (
        body[
            "static_audit_v1_9_source_locked"
        ]
        is True
    )

    assert (
        body[
            "v2_issuer_v1_1_compatibility_upgrade_required"
        ]
        is False
    )

    assert (
        body[
            "final_activation_lock_required_after_issuer_upgrade"
        ]
        is False
    )


def test_final_lock_still_does_not_authorize_execution():

    package = (
        lock.build_lock_v1_2(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "d" * 64,

            critical_hashes=
                fake_hashes(),
        )
    )

    body = (
        package[
            "release_lock"
        ]
    )

    assert (
        body[
            "automatic_activation_allowed"
        ]
        is False
    )

    assert (
        body[
            "live_activation_decision"
        ]
        == "NOT_MADE"
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

    assert (
        body[
            "orders_submitted"
        ]
        == 0
    )

    assert (
        body[
            "connected_writer_release_still_required"
        ]
        is True
    )

    assert (
        body[
            "future_activation_requires_new_release"
        ]
        is True
    )


def test_current_source_hashes_can_satisfy_issuer_final_lock():

    root = (
        Path(
            __file__
        )
        .resolve()
        .parent
    )

    required_hashes = {}

    for filename in (
        issuer.FINAL_LOCK_REQUIRED_FILES
    ):

        required_hashes[
            filename
        ] = (
            issuer.base.sha256_file(
                root
                / filename
            )
        )

    body = {
        "schema":
            issuer.RELEASE_LOCK_SCHEMA,

        "position_aware_live_chain_verified":
            True,

        "v2_issuer_v1_1_compatibility_upgrade_required":
            False,

        "final_activation_lock_required_after_issuer_upgrade":
            False,

        "critical_file_sha256":
            required_hashes,
    }

    assert (
        issuer.final_lock_is_ready(
            body
        )
        is True
    )


def test_interim_lock_remains_not_ready():

    body = {
        "schema":
            issuer.RELEASE_LOCK_SCHEMA,

        "position_aware_live_chain_verified":
            True,

        "v2_issuer_v1_1_compatibility_upgrade_required":
            True,

        "final_activation_lock_required_after_issuer_upgrade":
            True,

        "critical_file_sha256":
            {},
    }

    assert (
        issuer.final_lock_is_ready(
            body
        )
        is False
    )

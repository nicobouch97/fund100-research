from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_candidate_v1_0 as candidate
import fund100_pre_live_release_lock_v1_3 as lock


def safe_evidence():

    return {
        "schema":
            lock.base.base.EXPECTED_EVIDENCE_SCHEMA,

        "evidence_layer":
            lock.base.base.EXPECTED_EVIDENCE_LAYER,

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

    # --------------------------------------------------------
    # v1.2 still requires these issuer-aware hashes.
    # --------------------------------------------------------

    for filename in (
        lock.base.FINAL_ISSUER_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = (
            "b" * 64
        )

    # --------------------------------------------------------
    # v1.3 requires these new writer-candidate hashes.
    # --------------------------------------------------------

    for filename in (
        lock.WRITER_CANDIDATE_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = (
            "c" * 64
        )

    return hashes


def test_builder_version_is_v1_3():

    assert (
        lock.BUILDER_VERSION
        == "1.3"
    )


def test_serialized_schema_remains_v1_1():

    assert (
        lock.LOCK_SCHEMA
        == "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
    )


def test_materializer_is_in_critical_set():

    assert (
        "fund100_alpaca_live_execution_materializer.py"
        in lock.CRITICAL_FILES
    )


def test_writer_candidate_is_in_critical_set():

    assert (
        "fund100_alpaca_live_writer_candidate_v1_0.py"
        in lock.CRITICAL_FILES
    )


def test_static_audit_v1_11_is_in_critical_set():

    assert (
        "audit_fund100_live_boundary_v1_11.py"
        in lock.CRITICAL_FILES
    )


def test_lock_builder_is_in_critical_set():

    assert (
        "fund100_pre_live_release_lock_v1_3.py"
        in lock.CRITICAL_FILES
    )


def test_missing_candidate_hash_fails_closed():

    hashes = (
        fake_hashes()
    )

    del hashes[
        "fund100_alpaca_live_writer_candidate_v1_0.py"
    ]

    with pytest.raises(
        RuntimeError,
        match="not hash locked",
    ):

        lock.verify_writer_candidate_hashes_present(
            hashes
        )


def test_missing_materializer_hash_fails_closed():

    hashes = (
        fake_hashes()
    )

    del hashes[
        "fund100_alpaca_live_execution_materializer.py"
    ]

    with pytest.raises(
        RuntimeError,
        match="not hash locked",
    ):

        lock.verify_writer_candidate_hashes_present(
            hashes
        )


def test_build_lock_records_candidate_but_does_not_release_it():

    package = (
        lock.build_lock_v1_3(
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
            "release_lock_builder_version"
        ]
        == "1.3"
    )

    assert (
        body[
            "connected_writer_candidate_source_locked"
        ]
        is True
    )

    assert (
        body[
            "execution_materializer_source_locked"
        ]
        is True
    )

    assert (
        body[
            "static_audit_v1_11_source_locked"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_candidate_transport_released"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_candidate_public_execution_enabled"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_candidate_workflow_exposed"
        ]
        is False
    )


def test_candidate_source_itself_remains_hard_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_lock_still_does_not_authorize_execution():

    package = (
        lock.build_lock_v1_3(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "e" * 64,

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
            "connected_writer_release_still_required"
        ]
        is True
    )

    assert (
        body[
            "offline_connected_writer_rehearsal_required"
        ]
        is True
    )

    assert (
        body[
            "live_writer_transport_released"
        ]
        is False
    )

    assert (
        body[
            "live_writer_public_execution_enabled"
        ]
        is False
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

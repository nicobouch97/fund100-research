from __future__ import annotations

import pytest

import fund100_pre_live_release_lock_v1_4 as lock


def safe_evidence():

    return {
        "schema":
            lock.base.base.base.EXPECTED_EVIDENCE_SCHEMA,

        "evidence_layer":
            lock.base.base.base.EXPECTED_EVIDENCE_LAYER,

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
        lock.base.base.FINAL_ISSUER_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = "b" * 64

    for filename in (
        lock.base.WRITER_CANDIDATE_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = "c" * 64

    for filename in (
        lock.REHEARSAL_REQUIRED_FILES
    ):

        hashes[
            filename
        ] = "d" * 64

    return hashes


def fake_rehearsal_verification():

    return {
        "rehearsal_sha256":
            "e" * 64,

        "source_release_lock_sha256":
            "f" * 64,

        "writer_candidate_version":
            "1.0",
    }


def test_builder_version_is_v1_4():

    assert (
        lock.BUILDER_VERSION
        == "1.4"
    )


def test_rehearsal_artifact_is_critical():

    assert (
        "live_dryrun_outputs/v5_002/"
        "live_writer_transport_rehearsal_v1_0.json"
        in lock.CRITICAL_FILES
    )


def test_rehearsal_source_is_critical():

    assert (
        "fund100_alpaca_live_writer_transport_rehearsal_v1_0.py"
        in lock.CRITICAL_FILES
    )


def test_static_audit_v1_12_is_critical():

    assert (
        "audit_fund100_live_boundary_v1_12.py"
        in lock.CRITICAL_FILES
    )


def test_rehearsal_workflow_is_critical():

    assert (
        ".github/workflows/"
        "fund100-live-writer-transport-rehearsal.yml"
        in lock.CRITICAL_FILES
    )


def test_missing_rehearsal_artifact_hash_fails_closed():

    hashes = (
        fake_hashes()
    )

    del hashes[
        "live_dryrun_outputs/v5_002/"
        "live_writer_transport_rehearsal_v1_0.json"
    ]

    with pytest.raises(
        RuntimeError,
        match="not hash locked",
    ):

        lock.verify_rehearsal_hashes_present(
            hashes
        )


def test_v1_4_clears_only_rehearsal_requirement(
    monkeypatch,
):

    monkeypatch.setattr(
        lock,
        "verify_rehearsal_evidence",
        fake_rehearsal_verification,
    )

    package = (
        lock.build_lock_v1_4(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "1" * 64,

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
        == "1.4"
    )

    assert (
        body[
            "offline_connected_writer_rehearsal_completed"
        ]
        is True
    )

    assert (
        body[
            "offline_connected_writer_rehearsal_verified"
        ]
        is True
    )

    assert (
        body[
            "offline_connected_writer_rehearsal_required"
        ]
        is False
    )

    assert (
        body[
            "offline_connected_writer_rehearsal_artifact_locked"
        ]
        is True
    )

    assert (
        body[
            "static_audit_v1_12_source_locked"
        ]
        is True
    )


def test_v1_4_still_keeps_writer_unreleased(
    monkeypatch,
):

    monkeypatch.setattr(
        lock,
        "verify_rehearsal_evidence",
        fake_rehearsal_verification,
    )

    package = (
        lock.build_lock_v1_4(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "2" * 64,

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


def test_next_boundary_is_get_only_runtime_check(
    monkeypatch,
):

    monkeypatch.setattr(
        lock,
        "verify_rehearsal_evidence",
        fake_rehearsal_verification,
    )

    package = (
        lock.build_lock_v1_4(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "3" * 64,

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
            "live_preconnect_runtime_check_required"
        ]
        is True
    )

    assert (
        body[
            "live_preconnect_runtime_check_completed"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_release_still_required"
        ]
        is True
    )


def test_v1_4_remains_non_authorizing(
    monkeypatch,
):

    monkeypatch.setattr(
        lock,
        "verify_rehearsal_evidence",
        fake_rehearsal_verification,
    )

    package = (
        lock.build_lock_v1_4(
            evidence=
                safe_evidence(),

            evidence_sha256=
                "4" * 64,

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

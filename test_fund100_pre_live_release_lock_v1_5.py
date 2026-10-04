from __future__ import annotations

import copy

import pytest

import fund100_pre_live_release_lock as root_lock
import fund100_pre_live_release_lock_v1_5 as lock


def prior_body():

    hashes = {
        "fund100_alpaca_live_writer_candidate_v1_0.py":
            "a" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "b" * 64,
    }

    return {
        "schema":
            lock.LOCK_SCHEMA,

        "release_lock_builder_version":
            "1.4",

        "release_layer":
            "v1.1-position-aware-issuer-aware-"
            "writer-rehearsed-locked",

        "release_lock_id":
            "prior-lock",

        "strategy":
            "V5-002_SHADOW",

        "experiment":
            "V5-002",

        "pre_live_evidence_sha256":
            "c" * 64,

        "critical_file_sha256":
            hashes,

        "critical_file_set_sha256":
            root_lock.sha256_json(
                hashes
            ),

        "critical_file_count":
            len(
                hashes
            ),

        "position_aware_live_chain_verified":
            True,

        "issuer_aware_release_lock":
            True,

        "execution_materializer_source_locked":
            True,

        "connected_writer_candidate_source_locked":
            True,

        "offline_connected_writer_rehearsal_completed":
            True,

        "offline_connected_writer_rehearsal_verified":
            True,

        "offline_connected_writer_rehearsal_artifact_locked":
            True,

        "offline_connected_writer_rehearsal_required":
            False,

        "static_audit_v1_12_source_locked":
            True,

        "live_preconnect_runtime_check_required":
            True,

        "live_preconnect_runtime_check_completed":
            False,

        "connected_writer_release_still_required":
            True,

        "connected_writer_candidate_transport_released":
            False,

        "connected_writer_candidate_public_execution_enabled":
            False,

        "connected_writer_candidate_workflow_exposed":
            False,

        "live_writer_transport_released":
            False,

        "live_writer_public_execution_enabled":
            False,

        "automatic_activation_allowed":
            False,

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

        "orders_submitted":
            0,
    }


def prior_package():

    body = (
        prior_body()
    )

    return {
        "release_lock":
            body,

        "release_lock_sha256":
            root_lock.sha256_json(
                body
            ),
    }


def runtime_body(
    *,
    prior_hash: str,
):

    return {
        "schema":
            lock.EXPECTED_RUNTIME_SCHEMA,

        "mode":
            "LIVE_GET_ONLY_PRECONNECT",

        "source_release_lock_builder_version":
            "1.4",

        "source_release_lock_sha256":
            prior_hash,

        "writer_candidate_source_sha256":
            "a" * 64,

        "source_manifest_sha256":
            "d" * 64,

        "source_compiler_sha256":
            "e" * 64,

        "candidate_module_imported":
            False,

        "candidate_transport_released":
            False,

        "candidate_public_execution_enabled":
            False,

        "release_lock_verified":
            True,

        "locked_manifest_verified":
            True,

        "locked_compiler_verified":
            True,

        "runtime_binding_matches_locked_chain":
            True,

        "live_account_binding_sha256":
            "f" * 64,

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

        "market_clock_checked":
            True,

        "market_clock_value_persisted":
            False,

        "live_credentials_supplied":
            True,

        "live_credentials_persisted":
            False,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,

        "broker_snapshot_hash_persisted":
            False,

        "broker_http_methods":
            "GET_ONLY",

        "broker_get_request_count":
            4,

        "broker_post_request_count":
            0,

        "broker_put_request_count":
            0,

        "broker_patch_request_count":
            0,

        "broker_delete_request_count":
            0,

        "executable_intents_persisted":
            False,

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "writer_connected":
            False,

        "orders_submitted":
            0,

        "preconnect_runtime_check_passed":
            True,

        "connected_writer_release_still_required":
            True,
    }


def runtime_summary():

    return {
        "runtime_check_sha256":
            "1" * 64,

        "source_release_lock_sha256":
            "2" * 64,

        "live_account_binding_sha256":
            "3" * 64,

        "reconciliation_status":
            "EMPTY_ZERO_EQUITY",

        "position_count":
            0,

        "broker_http_methods":
            "GET_ONLY",

        "broker_get_request_count":
            4,

        "broker_write_request_count":
            0,
    }


def critical_hashes():

    result = {
        "fund100_alpaca_live_writer_candidate_v1_0.py":
            "a" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "4" * 64,

        "fund100_alpaca_live_preconnect_runtime_check.py":
            "5" * 64,

        "test_fund100_alpaca_live_preconnect_runtime_check.py":
            "6" * 64,

        "audit_fund100_live_boundary_v1_13.py":
            "7" * 64,

        ".github/workflows/"
        "fund100-alpaca-live-preconnect-runtime-check.yml":
            "8" * 64,

        "live_dryrun_outputs/v5_002/"
        "live_preconnect_runtime_check.json":
            "9" * 64,
    }

    return result


def test_builder_version_is_v1_5():

    assert (
        lock.BUILDER_VERSION
        == "1.5"
    )


def test_prior_v1_4_lock_verifies():

    body, recorded = (
        lock.verify_prior_v1_4_lock(
            prior_package()
        )
    )

    assert (
        body[
            "release_lock_builder_version"
        ]
        == "1.4"
    )

    assert (
        recorded
        == root_lock.sha256_json(
            body
        )
    )


def test_runtime_body_accepts_get_only_evidence():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    result = (
        lock.validate_runtime_body(
            body=
                runtime_body(
                    prior_hash=
                        prior_hash
                ),

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            manifest_sha256=
                "d" * 64,

            compiler_sha256=
                "e" * 64,
        )
    )

    assert (
        result[
            "reconciliation_status"
        ]
        == "EMPTY_ZERO_EQUITY"
    )

    assert (
        result[
            "position_count"
        ]
        == 0
    )


def test_runtime_binding_mismatch_fails_closed():

    prior = (
        prior_body()
    )

    expected_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        runtime_body(
            prior_hash=
                "0" * 64
        )
    )

    with pytest.raises(
        RuntimeError,
        match="exact current v1.4 lock",
    ):

        lock.validate_runtime_body(
            body=
                body,

            prior_lock_sha256=
                expected_hash,

            prior_body=
                prior,

            manifest_sha256=
                "d" * 64,

            compiler_sha256=
                "e" * 64,
        )


def test_runtime_post_count_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        runtime_body(
            prior_hash=
                prior_hash
        )
    )

    body[
        "broker_post_request_count"
    ] = 1

    with pytest.raises(
        RuntimeError,
        match="not zero",
    ):

        lock.validate_runtime_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            manifest_sha256=
                "d" * 64,

            compiler_sha256=
                "e" * 64,
        )


def test_runtime_live_authorization_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        runtime_body(
            prior_hash=
                prior_hash
        )
    )

    body[
        "live_execution_authorized"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="not FALSE",
    ):

        lock.validate_runtime_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            manifest_sha256=
                "d" * 64,

            compiler_sha256=
                "e" * 64,
        )


def test_build_v1_5_marks_preconnect_complete():

    body = (
        prior_body()
    )

    package = (
        lock.build_lock_v1_5(
            prior_body=
                body,

            runtime=
                runtime_summary(),

            critical_hashes=
                critical_hashes(),

            source_git_sha=
                "abc123",
        )
    )

    result = (
        package[
            "release_lock"
        ]
    )

    assert (
        result[
            "release_lock_builder_version"
        ]
        == "1.5"
    )

    assert (
        result[
            "live_preconnect_runtime_check_required"
        ]
        is False
    )

    assert (
        result[
            "live_preconnect_runtime_check_completed"
        ]
        is True
    )

    assert (
        result[
            "live_preconnect_runtime_check_verified"
        ]
        is True
    )

    assert (
        result[
            "live_preconnect_runtime_check_artifact_locked"
        ]
        is True
    )

    assert (
        result[
            "static_audit_v1_13_source_locked"
        ]
        is True
    )


def test_build_v1_5_keeps_writer_hard_locked():

    package = (
        lock.build_lock_v1_5(
            prior_body=
                prior_body(),

            runtime=
                runtime_summary(),

            critical_hashes=
                critical_hashes(),

            source_git_sha=
                "abc123",
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


def test_build_v1_5_remains_non_authorizing():

    package = (
        lock.build_lock_v1_5(
            prior_body=
                prior_body(),

            runtime=
                runtime_summary(),

            critical_hashes=
                critical_hashes(),

            source_git_sha=
                "abc123",
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


def test_next_boundary_is_paper_transport_parity():

    package = (
        lock.build_lock_v1_5(
            prior_body=
                prior_body(),

            runtime=
                runtime_summary(),

            critical_hashes=
                critical_hashes(),

            source_git_sha=
                "abc123",
        )
    )

    body = (
        package[
            "release_lock"
        ]
    )

    assert (
        body[
            "paper_connected_writer_parity_required"
        ]
        is True
    )

    assert (
        body[
            "paper_connected_writer_parity_completed"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_release_still_required"
        ]
        is True
    )


def test_build_does_not_mutate_prior_body():

    original = (
        prior_body()
    )

    frozen = (
        copy.deepcopy(
            original
        )
    )

    lock.build_lock_v1_5(
        prior_body=
            original,

        runtime=
            runtime_summary(),

        critical_hashes=
            critical_hashes(),

        source_git_sha=
            "abc123",
    )

    assert (
        original
        == frozen
    )

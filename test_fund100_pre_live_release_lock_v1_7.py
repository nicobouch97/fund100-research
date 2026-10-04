from __future__ import annotations

import copy

import pytest

import fund100_pre_live_release_lock as root_lock
import fund100_pre_live_release_lock_v1_7 as lock


def prior_body():

    hashes = {
        "fund100_alpaca_live_writer_candidate_v1_0.py":
            "a" * 64,

        ".github/workflows/fund100-live-static-audit.yml":
            "b" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "c" * 64,
    }

    return {
        "schema":
            lock.LOCK_SCHEMA,

        "release_lock_builder_version":
            "1.6",

        "release_layer":
            "prior",

        "pre_live_evidence_sha256":
            "d" * 64,

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

        "connected_writer_candidate_version":
            "1.0",

        "offline_connected_writer_rehearsal_completed":
            True,

        "offline_connected_writer_rehearsal_verified":
            True,

        "live_preconnect_runtime_check_completed":
            True,

        "live_preconnect_runtime_check_verified":
            True,

        "paper_connected_writer_parity_required":
            False,

        "paper_connected_writer_parity_completed":
            True,

        "paper_connected_writer_parity_verified":
            True,

        "connected_writer_status_semantics_hardening_required":
            True,

        "connected_writer_status_semantics_hardening_completed":
            False,

        "connected_writer_cumulative_cap_recovery_required":
            True,

        "connected_writer_cumulative_cap_recovery_completed":
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


def rehearsal_body(
    *,
    prior_hash: str,
    candidate_hash: str,
):

    return {
        "schema":
            lock.STATUS_REHEARSAL_SCHEMA,

        "mode":
            "COMPLETELY_OFFLINE_FAKE_BROKER",

        "source_release_lock_builder_version":
            "1.6",

        "source_release_lock_sha256":
            prior_hash,

        "writer_candidate_version":
            "1.1",

        "writer_candidate_source_sha256":
            candidate_hash,

        "prior_writer_candidate_source_sha256":
            "a" * 64,

        "candidate_transport_constant_false_before_after":
            True,

        "candidate_public_execution_constant_false_before_after":
            True,

        "fake_transport_installed_before_guard_bypass":
            True,

        "real_alpaca_credentials_supplied":
            False,

        "real_broker_network_access":
            False,

        "real_broker_get_requests":
            0,

        "real_broker_post_requests":
            0,

        "orders_submitted_to_alpaca":
            0,

        "synthetic_permit_persisted":
            False,

        "synthetic_executable_intent_persisted":
            False,

        "filled_existing_order_recovery_verified":
            True,

        "filled_existing_order_posts":
            0,

        "no_resubmit_statuses_verified":
            [
                "accepted",
                "accepted_for_bidding",
                "calculated",
                "done_for_day",
                "new",
                "partially_filled",
                "pending_cancel",
                "pending_new",
                "stopped",
            ],

        "no_resubmit_status_count":
            9,

        "no_resubmit_status_posts":
            0,

        "terminal_failure_statuses_verified":
            [
                "canceled",
                "expired",
                "rejected",
            ],

        "terminal_failure_status_count":
            3,

        "terminal_failure_posts":
            0,

        "ambiguous_unsafe_statuses_verified":
            [
                "held",
                "pending_replace",
                "replaced",
                "suspended",
                "future_unknown_status",
            ],

        "missing_status_rejected":
            True,

        "unsafe_status_posts":
            0,

        "existing_order_structural_mismatch_rejected":
            True,

        "structural_mismatch_posts":
            0,

        "response_loss_restart_verified":
            True,

        "response_loss_initial_fake_posts":
            1,

        "response_loss_restart_new_posts":
            0,

        "response_loss_duplicate_suppression":
            True,

        "submitted_terminal_failure_rejected":
            True,

        "submitted_terminal_failure_restart_rejected":
            True,

        "submitted_terminal_failure_total_fake_posts":
            1,

        "submitted_unsafe_status_rejected":
            True,

        "submitted_unsafe_restart_rejected":
            True,

        "submitted_unsafe_total_fake_posts":
            1,

        "automatic_resubmission_after_failed_terminal_status":
            False,

        "automatic_resubmission_after_unsafe_status":
            False,

        "status_semantics_rehearsal_passed":
            True,

        "cumulative_cap_hardening_tested":
            False,

        "cumulative_cap_hardening_still_required":
            True,

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

        "activation_performed":
            False,
    }


def rehearsal_summary():

    return {
        "status_rehearsal_sha256":
            "1" * 64,

        "source_release_lock_sha256":
            "2" * 64,

        "writer_candidate_v1_1_sha256":
            "3" * 64,

        "prior_writer_candidate_v1_0_sha256":
            "a" * 64,

        "no_resubmit_status_count":
            9,

        "terminal_failure_status_count":
            3,

        "unsafe_status_count":
            5,
    }


def critical_hashes():

    return {
        "fund100_alpaca_live_writer_candidate_v1_0.py":
            "a" * 64,

        "fund100_alpaca_live_writer_candidate_v1_1.py":
            "3" * 64,

        "audit_fund100_live_boundary_v1_14.py":
            "4" * 64,

        "audit_fund100_live_boundary_v1_15.py":
            "5" * 64,

        "fund100_alpaca_live_writer_status_rehearsal_v1_0.py":
            "6" * 64,

        "test_fund100_alpaca_live_writer_status_rehearsal_v1_0.py":
            "7" * 64,

        ".github/workflows/fund100-live-writer-status-rehearsal.yml":
            "8" * 64,

        "live_dryrun_outputs/v5_002/"
        "live_writer_status_rehearsal_v1_0.json":
            "9" * 64,

        ".github/workflows/fund100-live-static-audit.yml":
            "0" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "b" * 64,
    }


def test_builder_version():

    assert (
        lock.BUILDER_VERSION
        == "1.7"
    )


def test_prior_v1_6_lock_verifies():

    body, digest = (
        lock.verify_prior_v1_6_lock(
            prior_package()
        )
    )

    assert (
        body[
            "release_lock_builder_version"
        ]
        == "1.6"
    )

    assert (
        digest
        == root_lock.sha256_json(
            body
        )
    )


def test_valid_status_rehearsal_body():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    candidate_hash = (
        "3" * 64
    )

    result = (
        lock.validate_status_rehearsal_body(
            body=
                rehearsal_body(
                    prior_hash=
                        prior_hash,

                    candidate_hash=
                        candidate_hash,
                ),

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            candidate_v1_1_sha256=
                candidate_hash,
        )
    )

    assert (
        result[
            "no_resubmit_status_count"
        ]
        == 9
    )

    assert (
        result[
            "terminal_failure_status_count"
        ]
        == 3
    )

    assert (
        result[
            "unsafe_status_count"
        ]
        == 5
    )


def test_duplicate_restart_post_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    candidate_hash = (
        "3" * 64
    )

    body = (
        rehearsal_body(
            prior_hash=
                prior_hash,

            candidate_hash=
                candidate_hash,
        )
    )

    body[
        "response_loss_restart_new_posts"
    ] = 1

    with pytest.raises(
        RuntimeError,
        match="not zero",
    ):

        lock.validate_status_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            candidate_v1_1_sha256=
                candidate_hash,
        )


def test_real_network_access_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    candidate_hash = (
        "3" * 64
    )

    body = (
        rehearsal_body(
            prior_hash=
                prior_hash,

            candidate_hash=
                candidate_hash,
        )
    )

    body[
        "real_broker_network_access"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="not FALSE",
    ):

        lock.validate_status_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            candidate_v1_1_sha256=
                candidate_hash,
        )


def test_build_marks_status_semantics_complete():

    package = (
        lock.build_lock_v1_7(
            prior_body=
                prior_body(),

            rehearsal=
                rehearsal_summary(),

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
            "release_lock_builder_version"
        ]
        == "1.7"
    )

    assert (
        body[
            "connected_writer_candidate_version"
        ]
        == "1.1"
    )

    assert (
        body[
            "connected_writer_status_semantics_hardening_required"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_status_semantics_hardening_completed"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_status_semantics_hardening_verified"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_response_loss_duplicate_suppression_verified"
        ]
        is True
    )


def test_cumulative_cap_remains_release_blocker():

    package = (
        lock.build_lock_v1_7(
            prior_body=
                prior_body(),

            rehearsal=
                rehearsal_summary(),

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
            "connected_writer_cumulative_cap_recovery_required"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_completed"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_release_blocker"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_release_still_required"
        ]
        is True
    )


def test_live_execution_remains_fully_locked():

    package = (
        lock.build_lock_v1_7(
            prior_body=
                prior_body(),

            rehearsal=
                rehearsal_summary(),

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


def test_builder_does_not_mutate_prior():

    original = (
        prior_body()
    )

    frozen = (
        copy.deepcopy(
            original
        )
    )

    lock.build_lock_v1_7(
        prior_body=
            original,

        rehearsal=
            rehearsal_summary(),

        critical_hashes=
            critical_hashes(),

        source_git_sha=
            "abc123",
    )

    assert (
        original
        == frozen
    )

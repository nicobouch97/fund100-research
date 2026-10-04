from __future__ import annotations

import copy

import pytest

import fund100_pre_live_release_lock as root_lock
import fund100_pre_live_release_lock_v1_8 as lock


def prior_body():

    hashes = {
        "fund100_alpaca_live_writer_candidate_v1_1.py":
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
            "1.7",

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

        "connected_writer_candidate_v1_1_source_locked":
            True,

        "connected_writer_candidate_v1_1_source_sha256":
            "a" * 64,

        "connected_writer_candidate_version":
            "1.1",

        "offline_connected_writer_rehearsal_completed":
            True,

        "live_preconnect_runtime_check_completed":
            True,

        "paper_connected_writer_parity_completed":
            True,

        "connected_writer_status_semantics_hardening_required":
            False,

        "connected_writer_status_semantics_hardening_completed":
            True,

        "connected_writer_status_semantics_hardening_verified":
            True,

        "connected_writer_cumulative_cap_recovery_required":
            True,

        "connected_writer_cumulative_cap_recovery_completed":
            False,

        "connected_writer_cumulative_cap_recovery_release_blocker":
            True,

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
    guard_hash: str,
):

    return {
        "schema":
            lock.REHEARSAL_SCHEMA,

        "mode":
            "COMPLETELY_OFFLINE_FAKE_BROKER",

        "source_release_lock_builder_version":
            "1.7",

        "source_release_lock_sha256":
            prior_hash,

        "writer_candidate_version":
            "1.1",

        "writer_candidate_source_sha256":
            candidate_hash,

        "cumulative_cap_guard_version":
            "1.0",

        "cumulative_cap_guard_source_sha256":
            guard_hash,

        "permit_cap_usd":
            100.0,

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

        "fake_broker_only":
            True,

        "writer_candidate_transport_released":
            False,

        "writer_candidate_public_execution_enabled":
            False,

        "complete_authorized_id_reconstruction_verified":
            True,

        "sell_restart_buy_exact_cap_verified":
            True,

        "sell_phase_projected_usd":
            60.0,

        "restart_consumed_before_buy_usd":
            60.0,

        "buy_phase_new_usd":
            40.0,

        "exact_cap_projected_final_usd":
            100.0,

        "exact_cap_remaining_after_buy_usd":
            0.0,

        "restart_replay_new_gross_usd":
            0.0,

        "restart_replay_new_posts":
            0,

        "over_cap_blocked_before_writer":
            True,

        "over_cap_attempted_projected_usd":
            100.01,

        "over_cap_writer_posts":
            0,

        "lost_response_recovery_verified":
            True,

        "lost_response_initial_fake_posts":
            1,

        "lost_response_restart_consumed_usd":
            60.0,

        "lost_response_restart_new_gross_usd":
            0.0,

        "lost_response_restart_new_posts":
            0,

        "partial_fill_full_original_notional_consumed":
            True,

        "partial_fill_consumed_usd":
            60.0,

        "terminal_failure_history_statuses":
            [
                "canceled",
                "expired",
                "rejected",
            ],

        "terminal_failure_history_consumed_usd":
            60.0,

        "terminal_failure_continuation_blocked":
            True,

        "terminal_failure_writer_posts":
            0,

        "unsafe_history_continuation_blocked":
            True,

        "incomplete_lookup_fails_closed":
            True,

        "historical_over_cap_fails_closed":
            True,

        "single_permit_ceiling_across_phases_verified":
            True,

        "restart_reconstruction_from_broker_verified":
            True,

        "previous_client_id_not_double_counted":
            True,

        "previous_client_id_not_resubmitted":
            True,

        "cumulative_cap_rehearsal_passed":
            True,

        "cumulative_cap_hardening_tested":
            True,

        "cumulative_cap_hardening_release_lock_completed":
            False,

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
        "candidate_sha256":
            "a" * 64,

        "cap_guard_sha256":
            "e" * 64,

        "permit_cap_usd":
            100.0,

        "exact_cap_usd":
            100.0,

        "over_cap_test_usd":
            100.01,

        "terminal_status_count":
            3,

        "rehearsal_sha256":
            "f" * 64,

        "source_release_lock_sha256":
            "1" * 64,
    }


def critical_hashes():

    return {
        "fund100_alpaca_live_writer_candidate_v1_1.py":
            "a" * 64,

        "fund100_alpaca_live_cumulative_cap_guard_v1_0.py":
            "e" * 64,

        "test_fund100_alpaca_live_cumulative_cap_guard_v1_0.py":
            "2" * 64,

        "audit_fund100_live_boundary_v1_16.py":
            "3" * 64,

        "audit_fund100_live_boundary_v1_17.py":
            "4" * 64,

        "fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py":
            "5" * 64,

        "test_fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py":
            "6" * 64,

        ".github/workflows/fund100-live-cumulative-cap-rehearsal.yml":
            "7" * 64,

        "live_dryrun_outputs/v5_002/"
        "live_cumulative_cap_rehearsal_v1_0.json":
            "8" * 64,

        ".github/workflows/fund100-live-static-audit.yml":
            "9" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "0" * 64,
    }


def test_builder_version():

    assert (
        lock.BUILDER_VERSION
        == "1.8"
    )


def test_prior_v1_7_verifies():

    body, digest = (
        lock.verify_prior_v1_7_lock(
            prior_package()
        )
    )

    assert (
        body[
            "release_lock_builder_version"
        ]
        == "1.7"
    )

    assert (
        digest
        == root_lock.sha256_json(
            body
        )
    )


def test_valid_rehearsal_body():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    result = (
        lock.validate_rehearsal_body(
            body=
                rehearsal_body(
                    prior_hash=
                        prior_hash,

                    candidate_hash=
                        "a" * 64,

                    guard_hash=
                        "e" * 64,
                ),

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            cap_guard_sha256=
                "e" * 64,

            candidate_sha256=
                "a" * 64,
        )
    )

    assert (
        result[
            "exact_cap_usd"
        ]
        == 100.0
    )

    assert (
        result[
            "over_cap_test_usd"
        ]
        == 100.01
    )


def test_over_cap_writer_post_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        rehearsal_body(
            prior_hash=
                prior_hash,

            candidate_hash=
                "a" * 64,

            guard_hash=
                "e" * 64,
        )
    )

    body[
        "over_cap_writer_posts"
    ] = 1

    with pytest.raises(
        RuntimeError,
        match="over_cap_writer_posts",
    ):

        lock.validate_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            cap_guard_sha256=
                "e" * 64,

            candidate_sha256=
                "a" * 64,
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

    body = (
        rehearsal_body(
            prior_hash=
                prior_hash,

            candidate_hash=
                "a" * 64,

            guard_hash=
                "e" * 64,
        )
    )

    body[
        "real_broker_network_access"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="not FALSE",
    ):

        lock.validate_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,

            cap_guard_sha256=
                "e" * 64,

            candidate_sha256=
                "a" * 64,
        )


def test_build_marks_cumulative_cap_complete():

    package = (
        lock.build_lock_v1_8(
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
        == "1.8"
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_required"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_completed"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_verified"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_cumulative_cap_recovery_release_blocker"
        ]
        is False
    )


def test_orchestrator_becomes_next_release_blocker():

    package = (
        lock.build_lock_v1_8(
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
            "connected_writer_execution_orchestrator_required"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_execution_orchestrator_completed"
        ]
        is False
    )

    assert (
        body[
            "connected_writer_execution_orchestrator_release_blocker"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_release_still_required"
        ]
        is True
    )


def test_live_remains_fully_locked():

    package = (
        lock.build_lock_v1_8(
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

    lock.build_lock_v1_8(
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

from __future__ import annotations

import copy

import pytest

import fund100_pre_live_release_lock as root_lock
import fund100_pre_live_release_lock_v1_6 as lock


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
            "1.5",

        "release_layer":
            "prior",

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

        "offline_connected_writer_rehearsal_required":
            False,

        "live_preconnect_runtime_check_completed":
            True,

        "live_preconnect_runtime_check_verified":
            True,

        "live_preconnect_runtime_check_required":
            False,

        "paper_connected_writer_parity_required":
            True,

        "paper_connected_writer_parity_completed":
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


def parity_body(
    prior_hash: str,
):

    return {
        "schema":
            lock.EXPECTED_PARITY_SCHEMA,

        "mode":
            "REAL_PAPER_TRANSPORT_PARITY",

        "source_release_lock_builder_version":
            "1.5",

        "source_release_lock_sha256":
            prior_hash,

        "writer_candidate_source_sha256":
            "a" * 64,

        "writer_candidate_version":
            "1.0",

        "paper_endpoint_verified":
            True,

        "live_endpoint_contacted":
            False,

        "live_credentials_supplied":
            False,

        "paper_credentials_supplied":
            True,

        "paper_credentials_persisted":
            False,

        "candidate_transport_source_flag_false_before_after":
            True,

        "candidate_public_execution_source_flag_false_before_after":
            True,

        "candidate_destination_redirected_in_memory_only":
            True,

        "paper_market_required_closed":
            True,

        "paper_test_notional_usd":
            1.0,

        "client_order_id_sha256":
            "d" * 64,

        "first_submission_status":
            "SUBMITTED",

        "restart_status":
            "EXISTING_MATCHING_ORDER",

        "candidate_get_requests":
            2,

        "candidate_post_requests":
            1,

        "candidate_non_paper_host_requests":
            0,

        "duplicate_post_requests":
            0,

        "paper_order_cleanup_verified":
            True,

        "paper_order_terminal_status":
            "CANCELED",

        "paper_order_zero_fill_verified":
            True,

        "paper_cancel_requested":
            True,

        "paper_cancel_response_code":
            204,

        "terminal_state_poll_count":
            1,

        "open_order_index_converged":
            True,

        "open_order_index_poll_count":
            2,

        "open_order_index_stale_observations":
            1,

        "final_genuinely_open_orders":
            0,

        "paper_position_created":
            False,

        "synthetic_permit_persisted":
            False,

        "synthetic_executable_intent_persisted":
            False,

        "live_execution_authorized":
            False,

        "live_permit_issued":
            False,

        "live_max_execution_notional_usd":
            0.0,

        "live_writer_connected":
            False,

        "live_orders_submitted":
            0,

        "paper_connected_writer_parity_passed":
            True,
    }


def parity_summary():

    return {
        "paper_parity_sha256":
            "e" * 64,

        "source_release_lock_sha256":
            "f" * 64,

        "writer_candidate_source_sha256":
            "a" * 64,

        "client_order_id_sha256":
            "d" * 64,

        "terminal_status":
            "CANCELED",

        "open_index_poll_count":
            2,

        "stale_observation_count":
            1,
    }


def critical_hashes():

    return {
        "fund100_alpaca_live_writer_candidate_v1_0.py":
            "a" * 64,

        ".github/workflows/fund100-pre-live-release-lock.yml":
            "1" * 64,

        "fund100_alpaca_paper_transport_v1_0.py":
            "2" * 64,

        "fund100_alpaca_paper_writer_parity_v1_0.py":
            "3" * 64,

        "test_fund100_alpaca_paper_writer_parity_v1_0.py":
            "4" * 64,

        ".github/workflows/fund100-alpaca-paper-writer-parity.yml":
            "5" * 64,

        "live_dryrun_outputs/v5_002/"
        "paper_connected_writer_parity_v1_0.json":
            "6" * 64,

        "fund100_pre_live_release_lock_v1_6.py":
            "7" * 64,

        "test_fund100_pre_live_release_lock_v1_6.py":
            "8" * 64,
    }


def test_builder_version():

    assert (
        lock.BUILDER_VERSION
        == "1.6"
    )


def test_prior_v1_5_verifies():

    body, digest = (
        lock.verify_prior_v1_5_lock(
            prior_package()
        )
    )

    assert (
        body[
            "release_lock_builder_version"
        ]
        == "1.5"
    )

    assert (
        digest
        == root_lock.sha256_json(
            body
        )
    )


def test_valid_paper_parity_body():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    result = (
        lock.validate_parity_body(
            body=
                parity_body(
                    prior_hash
                ),

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,
        )
    )

    assert (
        result[
            "terminal_status"
        ]
        == "CANCELED"
    )

    assert (
        result[
            "open_index_poll_count"
        ]
        == 2
    )


def test_duplicate_post_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        parity_body(
            prior_hash
        )
    )

    body[
        "duplicate_post_requests"
    ] = 1

    with pytest.raises(
        RuntimeError,
        match="duplicate_post_requests",
    ):

        lock.validate_parity_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,
        )


def test_live_endpoint_contact_fails_closed():

    prior = (
        prior_body()
    )

    prior_hash = (
        root_lock.sha256_json(
            prior
        )
    )

    body = (
        parity_body(
            prior_hash
        )
    )

    body[
        "live_endpoint_contacted"
    ] = True

    with pytest.raises(
        RuntimeError,
        match="not FALSE",
    ):

        lock.validate_parity_body(
            body=
                body,

            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior,
        )


def test_build_marks_paper_parity_complete():

    package = (
        lock.build_lock_v1_6(
            prior_body=
                prior_body(),

            parity=
                parity_summary(),

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
        == "1.6"
    )

    assert (
        body[
            "paper_connected_writer_parity_required"
        ]
        is False
    )

    assert (
        body[
            "paper_connected_writer_parity_completed"
        ]
        is True
    )

    assert (
        body[
            "paper_connected_writer_parity_verified"
        ]
        is True
    )

    assert (
        body[
            "paper_connected_writer_zero_fill_verified"
        ]
        is True
    )

    assert (
        body[
            "paper_connected_writer_duplicate_posts"
        ]
        == 0
    )


def test_next_hardening_boundaries_required():

    package = (
        lock.build_lock_v1_6(
            prior_body=
                prior_body(),

            parity=
                parity_summary(),

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
            "connected_writer_status_semantics_hardening_required"
        ]
        is True
    )

    assert (
        body[
            "connected_writer_status_semantics_hardening_completed"
        ]
        is False
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


def test_live_writer_stays_unreleased():

    package = (
        lock.build_lock_v1_6(
            prior_body=
                prior_body(),

            parity=
                parity_summary(),

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

    lock.build_lock_v1_6(
        prior_body=
            original,

        parity=
            parity_summary(),

        critical_hashes=
            critical_hashes(),

        source_git_sha=
            "abc123",
    )

    assert (
        original
        == frozen
    )

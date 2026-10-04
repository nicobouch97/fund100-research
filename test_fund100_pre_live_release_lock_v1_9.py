from __future__ import annotations

import copy

import pytest

import fund100_pre_live_release_lock_v1_9 as lock


def good_evidence():

    return {
        "schema":
            "FUND100_EXECUTION_ORCHESTRATOR_REHEARSAL_V1",

        "release_lock_v1_8_source_present":
            True,

        "writer_candidate_v1_1_transport_released":
            False,

        "writer_candidate_v1_1_public_execution_enabled":
            False,

        "orchestrator_released":
            False,

        "broker_mode":
            "COMPLETELY_OFFLINE",

        "real_broker_network_access":
            "NONE",

        "broker_credentials_accessed":
            False,

        "exact_cap_across_sell_restart_buy":
            True,

        "over_cap_blocked_before_writer":
            True,

        "lost_response_restart_reconstruction":
            True,

        "restart_duplicate_post_prevention":
            True,

        "partial_fill_full_notional_accounting":
            True,

        "unsafe_terminal_history_blocked":
            True,

        "incomplete_history_blocked":
            True,

        "orders_submitted_to_alpaca":
            0,
    }


def good_hashes():

    return {
        filename:
            "a" * 64
        for filename in (
            lock.CRITICAL_FILES
        )
    }


def build(
    evidence=None,
    **kwargs,
):

    return lock.build_lock(
        evidence=(
            good_evidence()
            if evidence is None
            else evidence
        ),
        critical_hashes=(
            good_hashes()
        ),
        writer_transport_released=(
            kwargs.get(
                "writer_transport_released",
                False,
            )
        ),
        writer_public_execution_enabled=(
            kwargs.get(
                "writer_public_execution_enabled",
                False,
            )
        ),
        orchestrator_released=(
            kwargs.get(
                "orchestrator_released",
                False,
            )
        ),
        orchestrator_public_execution_enabled=(
            kwargs.get(
                "orchestrator_public_execution_enabled",
                False,
            )
        ),
        kill_switch_state=(
            kwargs.get(
                "kill_switch_state",
                "ENGAGED",
            )
        ),
    )


def test_v1_9_closes_orchestrator_blocker():

    body = build()

    assert (
        body[
            "release_lock_version"
        ]
        == "1.9"
    )

    assert (
        body[
            "execution_orchestrator_integration_required"
        ]
        is False
    )

    assert (
        body[
            "execution_orchestrator_integration_completed"
        ]
        is True
    )

    assert (
        body[
            "execution_orchestrator_release_blocker"
        ]
        is False
    )


def test_v1_9_keeps_live_completely_locked():

    body = build()

    assert (
        body[
            "automatic_live_activation_allowed"
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
            "maximum_live_execution_notional_usd"
        ]
        == "0.00"
    )

    assert (
        body[
            "writer_connected"
        ]
        is False
    )

    assert (
        body[
            "live_orders_submitted"
        ]
        == 0
    )


def test_next_stage_is_connected_paper():

    body = build()

    assert (
        body[
            "connected_alpaca_paper_end_to_end_required"
        ]
        is True
    )

    assert (
        body[
            "connected_alpaca_paper_end_to_end_completed"
        ]
        is False
    )

    assert (
        body[
            "next_stage"
        ]
        == (
            "CONNECTED_ALPACA_PAPER_"
            "END_TO_END_ORCHESTRATOR"
        )
    )


def test_failed_orchestrator_evidence_is_rejected():

    evidence = good_evidence()

    evidence[
        "over_cap_blocked_before_writer"
    ] = False

    with pytest.raises(
        lock.ReleaseLockStop,
        match="over_cap_blocked_before_writer",
    ):

        build(
            evidence=evidence
        )


def test_real_broker_access_in_rehearsal_is_rejected():

    evidence = good_evidence()

    evidence[
        "real_broker_network_access"
    ] = "PRESENT"

    with pytest.raises(
        lock.ReleaseLockStop,
        match="broker network access",
    ):

        build(
            evidence=evidence
        )


def test_alpaca_submission_in_rehearsal_is_rejected():

    evidence = good_evidence()

    evidence[
        "orders_submitted_to_alpaca"
    ] = 1

    with pytest.raises(
        lock.ReleaseLockStop,
        match="order submission",
    ):

        build(
            evidence=evidence
        )


def test_writer_release_is_rejected():

    with pytest.raises(
        lock.ReleaseLockStop,
        match="writer transport",
    ):

        build(
            writer_transport_released=True
        )


def test_orchestrator_release_is_rejected():

    with pytest.raises(
        lock.ReleaseLockStop,
        match="orchestrator is released",
    ):

        build(
            orchestrator_released=True
        )


def test_disengaged_kill_switch_is_rejected():

    with pytest.raises(
        lock.ReleaseLockStop,
        match="kill switch",
    ):

        build(
            kill_switch_state="DISENGAGED"
        )

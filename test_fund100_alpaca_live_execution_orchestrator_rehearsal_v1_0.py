from __future__ import annotations

import fund100_alpaca_live_execution_orchestrator_rehearsal_v1_0 as rehearsal
import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


def test_writer_candidate_remains_hard_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_orchestrator_remains_unreleased():

    assert (
        orchestrator.ORCHESTRATOR_RELEASED
        is False
    )

    assert (
        orchestrator.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_exact_cap_case():

    assert (
        rehearsal.exact_cap_case()
        is True
    )


def test_over_cap_case():

    assert (
        rehearsal.over_cap_case()
        is True
    )


def test_lost_response_case():

    assert (
        rehearsal.lost_response_case()
        is True
    )


def test_partial_fill_case():

    assert (
        rehearsal.partial_fill_case()
        is True
    )


def test_unsafe_terminal_case():

    assert (
        rehearsal.unsafe_terminal_case()
        is True
    )


def test_incomplete_history_case():

    assert (
        rehearsal.incomplete_history_case()
        is True
    )

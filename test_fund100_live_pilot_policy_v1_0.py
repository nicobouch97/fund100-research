from __future__ import annotations

import pytest

import fund100_live_pilot_policy_v1_0 as policy


def hashes():

    return {
        filename:
            "a" * 64
        for filename
        in policy.REQUIRED_SOURCE_FILES
    }


def build(
    cap="100.00",
):

    return policy.build_policy(
        capital_ceiling_usd=cap,

        account_binding_sha256=(
            "b" * 64
        ),

        shadow_state_sha256=(
            "c" * 64
        ),

        source_hashes=hashes(),

        authorization_reference=(
            "TEST-AUTHORIZATION"
        ),
    )


def test_policy_is_long_only_no_leverage():

    body = build()

    assert (
        body[
            "leverage_allowed"
        ]
        is False
    )

    assert (
        body[
            "shorting_allowed"
        ]
        is False
    )


def test_additional_money_is_not_automatically_authorized():

    body = build()

    assert (
        body[
            "broker_equity_above_ceiling_is_usable"
        ]
        is False
    )

    assert (
        body[
            "additional_deposits_automatically_authorized"
        ]
        is False
    )


def test_bootstrap_then_genuine_events_only():

    body = build()

    assert (
        body[
            "bootstrap_alignment_allowed"
        ]
        is True
    )

    assert (
        body[
            "post_bootstrap_genuine_strategy_event_required"
        ]
        is True
    )

    assert (
        body[
            "ordinary_drift_rebalancing_allowed"
        ]
        is False
    )


def test_strategy_change_is_forbidden():

    body = build()

    assert (
        body[
            "strategy_parameter_changes_allowed"
        ]
        is False
    )

    assert (
        body[
            "research_agent_can_change_live_strategy"
        ]
        is False
    )


def test_negative_cap_is_rejected():

    with pytest.raises(
        policy.PilotPolicyStop
    ):

        build(
            "-1"
        )


def test_zero_cap_is_rejected():

    with pytest.raises(
        policy.PilotPolicyStop
    ):

        build(
            "0"
        )

from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_candidate_v1_0 as candidate
import fund100_alpaca_live_writer_transport_rehearsal_v1_0 as rehearsal


def inputs():

    return (
        rehearsal.build_synthetic_intents(),
        rehearsal.build_synthetic_permit(),
    )


def test_candidate_constants_remain_false():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_fresh_and_clean_restart():

    intents, permit = (
        inputs()
    )

    result = (
        rehearsal.rehearse_fresh_and_clean_restart(
            intents=
                intents,

            permit_package=
                permit,
        )
    )

    assert (
        result[
            "fresh_fake_posts"
        ]
        == 2
    )

    assert (
        result[
            "clean_restart_new_posts"
        ]
        == 0
    )

    assert (
        result[
            "clean_restart_duplicate_suppression"
        ]
        is True
    )


def test_partial_restart_submits_only_missing_order():

    intents, permit = (
        inputs()
    )

    result = (
        rehearsal.rehearse_partial_restart(
            intents=
                intents,

            permit_package=
                permit,
        )
    )

    assert (
        result[
            "partial_restart_existing_orders"
        ]
        == 1
    )

    assert (
        result[
            "partial_restart_new_posts"
        ]
        == 1
    )

    assert (
        result[
            "partial_restart_missing_only"
        ]
        is True
    )


def test_lost_response_restart_does_not_duplicate():

    intents, permit = (
        inputs()
    )

    result = (
        rehearsal.rehearse_response_loss_restart(
            intents=
                intents,

            permit_package=
                permit,
        )
    )

    assert (
        result[
            "response_loss_simulated"
        ]
        is True
    )

    assert (
        result[
            "orders_accepted_before_response_loss"
        ]
        == 2
    )

    assert (
        result[
            "response_loss_restart_new_posts"
        ]
        == 0
    )

    assert (
        result[
            "response_loss_restart_duplicate_suppression"
        ]
        is True
    )


def test_existing_order_mismatch_fails_closed():

    intents, permit = (
        inputs()
    )

    result = (
        rehearsal.rehearse_existing_order_mismatch(
            intents=
                intents,

            permit_package=
                permit,
        )
    )

    assert (
        result[
            "existing_order_mismatch_rejected"
        ]
        is True
    )

    assert (
        result[
            "posts_after_mismatch"
        ]
        == 0
    )


def test_fake_broker_rejects_duplicate_direct_post():

    intents, _permit = (
        inputs()
    )

    broker = (
        rehearsal.OfflineBroker()
    )

    broker.seed_matching_order(
        intents[
            0
        ]
    )

    payload = (
        candidate.build_order_payload(
            intents[
                0
            ]
        )
    )

    class RequestLike:

        data = (
            __import__(
                "json"
            )
            .dumps(
                payload
            )
            .encode(
                "utf-8"
            )
        )

        full_url = (
            "https://api.alpaca.markets/v2/orders"
        )

        @staticmethod
        def get_method():

            return "POST"

    with pytest.raises(
        AssertionError,
        match="Duplicate POST",
    ):

        broker.urlopen(
            RequestLike()
        )


def test_offline_patch_restores_candidate_guards():

    broker = (
        rehearsal.OfflineBroker()
    )

    original_urlopen = (
        candidate.urlopen
    )

    original_transport_guard = (
        candidate.require_transport_released
    )

    original_public_guard = (
        candidate.require_public_execution_released
    )

    with rehearsal.offline_candidate_transport(
        broker
    ):

        assert (
            candidate.urlopen
            == broker.urlopen
        )

    assert (
        candidate.urlopen
        is original_urlopen
    )

    assert (
        candidate.require_transport_released
        is original_transport_guard
    )

    assert (
        candidate.require_public_execution_released
        is original_public_guard
    )

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_safe_output_contains_no_usable_permit_or_orders():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            fresh_restart={
                "fresh_fake_posts":
                    2,

                "fresh_fake_accepts":
                    2,

                "clean_restart_new_posts":
                    0,

                "clean_restart_existing_orders":
                    2,

                "clean_restart_duplicate_suppression":
                    True,
            },

            partial_restart={
                "partial_restart_existing_orders":
                    1,

                "partial_restart_new_posts":
                    1,

                "partial_restart_missing_only":
                    True,
            },

            response_loss={
                "response_loss_simulated":
                    True,

                "orders_accepted_before_response_loss":
                    2,

                "response_loss_restart_new_posts":
                    0,

                "response_loss_restart_duplicate_suppression":
                    True,
            },

            mismatch={
                "existing_order_mismatch_rejected":
                    True,

                "posts_after_mismatch":
                    0,

                "mismatch_fail_closed":
                    True,
            },
        )
    )

    body = (
        package[
            "rehearsal"
        ]
    )

    rehearsal.assert_safe_output(
        body
    )

    forbidden = {
        "permit",
        "orders",
        "intents",
        "candidate_intents",
        "api_key",
        "api_secret",
        "approval_token",
    }

    assert (
        forbidden.intersection(
            body.keys()
        )
        == set()
    )


def test_real_network_counters_are_zero():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                "b" * 64,

            fresh_restart={
                "fresh_fake_posts":
                    2,

                "fresh_fake_accepts":
                    2,

                "clean_restart_new_posts":
                    0,

                "clean_restart_existing_orders":
                    2,

                "clean_restart_duplicate_suppression":
                    True,
            },

            partial_restart={
                "partial_restart_existing_orders":
                    1,

                "partial_restart_new_posts":
                    1,

                "partial_restart_missing_only":
                    True,
            },

            response_loss={
                "response_loss_simulated":
                    True,

                "orders_accepted_before_response_loss":
                    2,

                "response_loss_restart_new_posts":
                    0,

                "response_loss_restart_duplicate_suppression":
                    True,
            },

            mismatch={
                "existing_order_mismatch_rejected":
                    True,

                "posts_after_mismatch":
                    0,

                "mismatch_fail_closed":
                    True,
            },
        )
    )

    body = package["rehearsal"]

    assert (
        body[
            "real_broker_get_requests"
        ]
        == 0
    )

    assert (
        body[
            "real_broker_post_requests"
        ]
        == 0
    )

    assert (
        body[
            "orders_submitted_to_alpaca"
        ]
        == 0
    )

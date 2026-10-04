from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_candidate_v1_1 as candidate
import fund100_alpaca_live_writer_status_rehearsal_v1_0 as rehearsal


def permit():

    return (
        rehearsal.build_synthetic_permit()
    )


def intent():

    return (
        rehearsal.build_synthetic_intent()
    )


def test_candidate_still_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_filled_recovery_has_zero_posts():

    assert (
        rehearsal.rehearse_filled(
            intent=
                intent(),

            permit_package=
                permit(),
        )
        is True
    )


@pytest.mark.parametrize(
    "status",
    sorted(
        candidate.NO_RESUBMIT_STATUSES
    ),
)
def test_no_resubmit_status_has_zero_posts(
    status,
):

    broker = (
        rehearsal.OfflineStatusBroker()
    )

    item = (
        intent()
    )

    broker.seed_existing(
        intent=
            item,

        status=
            status,
    )

    result = (
        rehearsal.execute(
            broker=
                broker,

            intent=
                item,

            permit_package=
                permit(),
        )
    )

    assert (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        == "EXISTING_NO_RESUBMIT_ORDER"
    )

    assert (
        broker.post_attempt_count
        == 0
    )


@pytest.mark.parametrize(
    "status",
    [
        "canceled",
        "expired",
        "rejected",
    ],
)
def test_terminal_failure_has_zero_posts(
    status,
):

    broker = (
        rehearsal.OfflineStatusBroker()
    )

    item = (
        intent()
    )

    broker.seed_existing(
        intent=
            item,

        status=
            status,
    )

    with pytest.raises(
        candidate.ExistingOrderTerminalFailure,
    ):

        rehearsal.execute(
            broker=
                broker,

            intent=
                item,

            permit_package=
                permit(),
        )

    assert (
        broker.post_attempt_count
        == 0
    )


@pytest.mark.parametrize(
    "status",
    [
        "replaced",
        "pending_replace",
        "suspended",
        "held",
        "future_unknown_status",
    ],
)
def test_unsafe_status_has_zero_posts(
    status,
):

    broker = (
        rehearsal.OfflineStatusBroker()
    )

    item = (
        intent()
    )

    broker.seed_existing(
        intent=
            item,

        status=
            status,
    )

    with pytest.raises(
        candidate.ExistingOrderUnsafeStatus,
    ):

        rehearsal.execute(
            broker=
                broker,

            intent=
                item,

            permit_package=
                permit(),
        )

    assert (
        broker.post_attempt_count
        == 0
    )


def test_missing_status_has_zero_posts():

    broker = (
        rehearsal.OfflineStatusBroker()
    )

    item = (
        intent()
    )

    broker.seed_existing(
        intent=
            item,

        status=
            None,

        omit_status=
            True,
    )

    with pytest.raises(
        candidate.ExistingOrderUnsafeStatus,
    ):

        rehearsal.execute(
            broker=
                broker,

            intent=
                item,

            permit_package=
                permit(),
        )

    assert (
        broker.post_attempt_count
        == 0
    )


def test_response_loss_restart_suppresses_duplicate():

    result = (
        rehearsal.rehearse_response_loss_restart(
            intent=
                intent(),

            permit_package=
                permit(),
        )
    )

    assert (
        result[
            "initial_fake_posts"
        ]
        == 1
    )

    assert (
        result[
            "restart_new_posts"
        ]
        == 0
    )

    assert (
        result[
            "duplicate_suppression"
        ]
        is True
    )


def test_terminal_post_response_restart_does_not_post_again():

    assert (
        rehearsal.rehearse_submitted_terminal_failure(
            intent=
                intent(),

            permit_package=
                permit(),
        )
        is True
    )


def test_unsafe_post_response_restart_does_not_post_again():

    assert (
        rehearsal.rehearse_submitted_unsafe_status(
            intent=
                intent(),

            permit_package=
                permit(),
        )
        is True
    )


def test_safe_output_is_non_authorizing():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            candidate_sha256=
                "b" * 64,

            prior_candidate_sha256=
                "c" * 64,

            no_resubmit_statuses=
                sorted(
                    candidate.NO_RESUBMIT_STATUSES
                ),

            terminal_statuses=
                sorted(
                    candidate.TERMINAL_FAILURE_STATUSES
                ),

            unsafe_result={
                "statuses":
                    [
                        "held",
                        "pending_replace",
                        "replaced",
                        "suspended",
                        "future_unknown_status",
                    ],

                "missing_status_rejected":
                    True,
            },

            response_loss={
                "initial_fake_posts":
                    1,

                "restart_new_posts":
                    0,

                "duplicate_suppression":
                    True,
            },
        )
    )

    body = (
        package[
            "status_rehearsal"
        ]
    )

    assert (
        body[
            "status_semantics_rehearsal_passed"
        ]
        is True
    )

    assert (
        body[
            "real_broker_network_access"
        ]
        is False
    )

    assert (
        body[
            "orders_submitted_to_alpaca"
        ]
        == 0
    )

    assert (
        body[
            "automatic_resubmission_after_failed_terminal_status"
        ]
        is False
    )

    assert (
        body[
            "automatic_resubmission_after_unsafe_status"
        ]
        is False
    )

    assert (
        body[
            "cumulative_cap_hardening_tested"
        ]
        is False
    )

    assert (
        body[
            "cumulative_cap_hardening_still_required"
        ]
        is True
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "max_live_execution_notional_usd"
        ]
        == 0.0
    )


def test_rehearsal_uses_v1_1_candidate():

    assert (
        candidate.WRITER_CANDIDATE_VERSION
        == "1.1"
    )

    assert (
        rehearsal.candidate
        is candidate
    )

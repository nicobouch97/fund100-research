from __future__ import annotations

import fund100_alpaca_live_cumulative_cap_rehearsal_v1_0 as rehearsal
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


def test_candidate_remains_hard_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_exact_cap_across_phases():

    result = (
        rehearsal.rehearse_exact_cap_across_phases()
    )

    assert (
        result[
            "sell_phase_projected_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "restart_consumed_before_buy_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "buy_phase_new_usd"
        ]
        == 40.0
    )

    assert (
        result[
            "projected_final_usd"
        ]
        == 100.0
    )

    assert (
        result[
            "remaining_after_buy_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "restart_replay_new_gross_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "restart_replay_new_posts"
        ]
        == 0
    )


def test_over_cap_is_blocked_before_writer():

    result = (
        rehearsal.rehearse_over_cap_block()
    )

    assert (
        result[
            "historical_consumed_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "attempted_new_usd"
        ]
        == 40.01
    )

    assert (
        result[
            "attempted_projected_usd"
        ]
        == 100.01
    )

    assert (
        result[
            "blocked_before_writer"
        ]
        is True
    )

    assert (
        result[
            "writer_posts"
        ]
        == 0
    )


def test_lost_response_restart_recovers_consumption():

    result = (
        rehearsal.rehearse_lost_response_recovery()
    )

    assert (
        result[
            "initial_fake_posts"
        ]
        == 1
    )

    assert (
        result[
            "broker_accepted_orders"
        ]
        == 1
    )

    assert (
        result[
            "restart_reconstructed_consumed_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "restart_new_gross_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "restart_new_posts"
        ]
        == 0
    )


def test_partial_fill_consumes_full_original_notional():

    result = (
        rehearsal.rehearse_partial_fill_consumption()
    )

    assert (
        result[
            "partial_order_original_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "consumed_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "projected_with_buy_usd"
        ]
        == 100.0
    )


def test_terminal_failure_history_retains_budget_and_blocks():

    result = (
        rehearsal.rehearse_terminal_failure_history()
    )

    assert (
        result[
            "statuses"
        ]
        == [
            "canceled",
            "expired",
            "rejected",
        ]
    )

    assert (
        result[
            "consumed_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "continuation_blocked"
        ]
        is True
    )

    assert (
        result[
            "writer_posts"
        ]
        == 0
    )


def test_unsafe_history_blocks():

    assert (
        rehearsal.rehearse_unsafe_history()
        is True
    )


def test_incomplete_lookup_blocks():

    assert (
        rehearsal.rehearse_incomplete_lookup()
        is True
    )


def test_historical_over_cap_blocks():

    assert (
        rehearsal.rehearse_historical_over_cap()
        is True
    )


def test_safe_output_remains_non_authorizing():

    package = (
        rehearsal.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            candidate_sha256=
                "b" * 64,

            cap_guard_sha256=
                "c" * 64,

            exact_cap={
                "sell_phase_projected_usd":
                    60.0,

                "restart_consumed_before_buy_usd":
                    60.0,

                "buy_phase_new_usd":
                    40.0,

                "projected_final_usd":
                    100.0,

                "remaining_after_buy_usd":
                    0.0,

                "fake_posts_after_sell_and_buy":
                    2,

                "restart_replay_new_gross_usd":
                    0.0,

                "restart_replay_new_posts":
                    0,

                "passed":
                    True,
            },

            over_cap={
                "historical_consumed_usd":
                    60.0,

                "attempted_new_usd":
                    40.01,

                "attempted_projected_usd":
                    100.01,

                "writer_posts":
                    0,

                "blocked_before_writer":
                    True,
            },

            response_loss={
                "initial_fake_posts":
                    1,

                "broker_accepted_orders":
                    1,

                "restart_reconstructed_consumed_usd":
                    60.0,

                "restart_new_gross_usd":
                    0.0,

                "restart_new_posts":
                    0,

                "passed":
                    True,
            },

            partial_fill={
                "partial_order_original_notional_usd":
                    60.0,

                "consumed_notional_usd":
                    60.0,

                "projected_with_buy_usd":
                    100.0,

                "passed":
                    True,
            },

            terminal_history={
                "statuses":
                    [
                        "canceled",
                        "expired",
                        "rejected",
                    ],

                "consumed_notional_usd":
                    60.0,

                "continuation_blocked":
                    True,

                "writer_posts":
                    0,
            },
        )
    )

    body = (
        package[
            "cumulative_cap_rehearsal"
        ]
    )

    assert (
        body[
            "cumulative_cap_rehearsal_passed"
        ]
        is True
    )

    assert (
        body[
            "single_permit_ceiling_across_phases_verified"
        ]
        is True
    )

    assert (
        body[
            "restart_reconstruction_from_broker_verified"
        ]
        is True
    )

    assert (
        body[
            "previous_client_id_not_double_counted"
        ]
        is True
    )

    assert (
        body[
            "previous_client_id_not_resubmitted"
        ]
        is True
    )

    assert (
        body[
            "cumulative_cap_hardening_tested"
        ]
        is True
    )

    assert (
        body[
            "cumulative_cap_hardening_release_lock_completed"
        ]
        is False
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

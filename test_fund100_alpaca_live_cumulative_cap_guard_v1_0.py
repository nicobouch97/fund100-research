from __future__ import annotations

import pytest

import fund100_alpaca_live_cumulative_cap_guard_v1_0 as guard
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


SELL_ID = (
    "f100live-captest-s-acwi"
)


BUY_ID = (
    "f100live-captest-b-spy"
)


def compiler_body():

    return {
        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            True,

        "candidate_intents":
            [
                {
                    "symbol":
                        "ACWI",

                    "side":
                        "sell",

                    "target_weight":
                        0.40,

                    "client_order_id":
                        SELL_ID,

                    "notional_usd":
                        None,

                    "executable":
                        False,
                },
                {
                    "symbol":
                        "SPY",

                    "side":
                        "buy",

                    "target_weight":
                        0.60,

                    "client_order_id":
                        BUY_ID,

                    "notional_usd":
                        None,

                    "executable":
                        False,
                },
            ],
    }


def compiler_hash():

    return (
        candidate.sha256_json(
            compiler_body()
        )
    )


def permit_hash():

    return (
        "a" * 64
    )


def lookup(
    sell=None,
    buy=None,
):

    return {
        SELL_ID:
            sell,

        BUY_ID:
            buy,
    }


def order(
    *,
    client_order_id: str,
    symbol: str,
    side: str,
    notional,
    status: str = "filled",
):

    return {
        "id":
            (
                "broker-"
                + client_order_id
            ),

        "client_order_id":
            client_order_id,

        "symbol":
            symbol,

        "side":
            side,

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            str(
                notional
            ),

        "status":
            status,
    }


def sell_order(
    notional=60,
    status="filled",
):

    return order(
        client_order_id=
            SELL_ID,

        symbol=
            "ACWI",

        side=
            "sell",

        notional=
            notional,

        status=
            status,
    )


def buy_order(
    notional=40,
    status="new",
):

    return order(
        client_order_id=
            BUY_ID,

        symbol=
            "SPY",

        side=
            "buy",

        notional=
            notional,

        status=
            status,
    )


def sell_intent(
    notional=60,
):

    return {
        "symbol":
            "ACWI",

        "side":
            "sell",

        "notional_usd":
            float(
                notional
            ),

        "client_order_id":
            SELL_ID,

        "executable":
            True,
    }


def buy_intent(
    notional=40,
):

    return {
        "symbol":
            "SPY",

        "side":
            "buy",

        "notional_usd":
            float(
                notional
            ),

        "client_order_id":
            BUY_ID,

        "executable":
            True,
    }


def evaluate(
    *,
    observed,
    proposed,
    cap=100,
):

    body = (
        compiler_body()
    )

    return (
        guard.evaluate_cumulative_cap(
            compiler_body=
                body,

            compiler_sha256=
                candidate.sha256_json(
                    body
                ),

            permit_sha256=
                permit_hash(),

            permit_cap_usd=
                cap,

            observed_orders_by_client_id=
                observed,

            proposed_intents=
                proposed,
        )
    )


def test_guard_is_pure_and_non_writing():

    assert (
        guard.GUARD_VERSION
        == "1.0"
    )

    assert (
        guard.PERSISTENCE_POLICY
        == "EPHEMERAL_DO_NOT_COMMIT"
    )

    assert not hasattr(
        guard,
        "main",
    )


def test_first_sell_phase_passes():

    result = (
        evaluate(
            observed=
                lookup(),

            proposed=[
                sell_intent(
                    60
                )
            ],
        )
    )

    assert (
        result[
            "previously_consumed_gross_notional_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "new_gross_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "projected_cumulative_gross_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "remaining_cap_after_batch_usd"
        ]
        == 40.0
    )


def test_restart_recovers_sell_without_double_counting():

    result = (
        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "filled",
                        )
                ),

            proposed=[
                sell_intent(
                    60
                )
            ],
        )
    )

    assert (
        result[
            "previously_consumed_gross_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "recovered_existing_intent_count"
        ]
        == 1
    )

    assert (
        result[
            "new_gross_notional_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "projected_cumulative_gross_notional_usd"
        ]
        == 60.0
    )


def test_sell_60_then_buy_40_exact_cap_passes():

    result = (
        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "filled",
                        )
                ),

            proposed=[
                buy_intent(
                    40
                )
            ],
        )
    )

    assert (
        result[
            "previously_consumed_gross_notional_usd"
        ]
        == 60.0
    )

    assert (
        result[
            "new_gross_notional_usd"
        ]
        == 40.0
    )

    assert (
        result[
            "projected_cumulative_gross_notional_usd"
        ]
        == 100.0
    )

    assert (
        result[
            "remaining_cap_after_batch_usd"
        ]
        == 0.0
    )


def test_sell_60_then_buy_40_01_is_blocked():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="exceeds the single",
    ):

        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "filled",
                        )
                ),

            proposed=[
                buy_intent(
                    40.01
                )
            ],
        )


def test_restart_with_both_orders_does_not_double_count():

    result = (
        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "filled",
                        ),

                    buy=
                        buy_order(
                            40,
                            "new",
                        ),
                ),

            proposed=[
                buy_intent(
                    40
                )
            ],
        )
    )

    assert (
        result[
            "previously_consumed_gross_notional_usd"
        ]
        == 100.0
    )

    assert (
        result[
            "recovered_existing_intent_count"
        ]
        == 1
    )

    assert (
        result[
            "new_gross_notional_usd"
        ]
        == 0.0
    )

    assert (
        result[
            "projected_cumulative_gross_notional_usd"
        ]
        == 100.0
    )


def test_partial_order_consumes_full_original_notional():

    state = (
        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "partially_filled",
                        )
                ),

            permit_cap_usd=
                100,
        )
    )

    assert (
        float(
            state[
                "consumed_gross_notional_usd"
            ]
        )
        == 60.0
    )

    assert (
        state[
            "blocking_existing_orders"
        ]
        == []
    )


@pytest.mark.parametrize(
    "status",
    [
        "canceled",
        "expired",
        "rejected",
    ],
)
def test_failed_terminal_order_consumes_budget_and_blocks(
    status,
):

    state = (
        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id=
                lookup(
                    sell=
                        sell_order(
                            60,
                            status,
                        )
                ),

            permit_cap_usd=
                100,
        )
    )

    assert (
        float(
            state[
                "consumed_gross_notional_usd"
            ]
        )
        == 60.0
    )

    assert (
        len(
            state[
                "blocking_existing_orders"
            ]
        )
        == 1
    )

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="explicit reconciliation",
    ):

        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            status,
                        )
                ),

            proposed=[
                buy_intent(
                    40
                )
            ],
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
def test_unsafe_history_blocks_new_phase(
    status,
):

    with pytest.raises(
        guard.CumulativeCapGuardStop,
    ):

        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            status,
                        )
                ),

            proposed=[
                buy_intent(
                    40
                )
            ],
        )


def test_incomplete_broker_lookup_fails_closed():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="incomplete",
    ):

        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id={
                SELL_ID:
                    None,
            },

            permit_cap_usd=
                100,
        )


def test_extra_lookup_id_fails_closed():

    observed = (
        lookup()
    )

    observed[
        "f100live-unrelated-b-xlk"
    ] = None

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="unauthorized",
    ):

        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id=
                observed,

            permit_cap_usd=
                100,
        )


def test_observed_symbol_mismatch_fails_closed():

    bad = (
        sell_order(
            60,
            "filled",
        )
    )

    bad[
        "symbol"
    ] = "SPY"

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="symbol mismatch",
    ):

        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id=
                lookup(
                    sell=
                        bad
                ),

            permit_cap_usd=
                100,
        )


def test_same_client_id_different_notional_fails_closed():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="does not exactly match",
    ):

        evaluate(
            observed=
                lookup(
                    sell=
                        sell_order(
                            60,
                            "filled",
                        )
                ),

            proposed=[
                sell_intent(
                    20
                )
            ],
        )


def test_historical_consumption_over_cap_fails_closed():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="already exceeds",
    ):

        guard.reconstruct_consumed_state(
            compiler_body=
                compiler_body(),

            observed_orders_by_client_id=
                lookup(
                    sell=
                        sell_order(
                            101,
                            "filled",
                        )
                ),

            permit_cap_usd=
                100,
        )


def test_duplicate_proposed_id_fails_closed():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="duplicate proposed",
    ):

        evaluate(
            observed=
                lookup(),

            proposed=[
                sell_intent(
                    10
                ),

                sell_intent(
                    10
                ),
            ],
        )


def test_wrong_compiler_hash_fails_closed():

    with pytest.raises(
        guard.CumulativeCapGuardStop,
        match="compiler SHA256 binding failed",
    ):

        guard.evaluate_cumulative_cap(
            compiler_body=
                compiler_body(),

            compiler_sha256=
                "0" * 64,

            permit_sha256=
                permit_hash(),

            permit_cap_usd=
                100,

            observed_orders_by_client_id=
                lookup(),

            proposed_intents=
                [],
        )


def test_result_remains_ephemeral_and_non_writing():

    result = (
        evaluate(
            observed=
                lookup(),

            proposed=[],
        )
    )

    assert (
        result[
            "persistence_policy"
        ]
        == "EPHEMERAL_DO_NOT_COMMIT"
    )

    assert (
        result[
            "broker_network_access"
        ]
        is False
    )

    assert (
        result[
            "broker_write_capability"
        ]
        is False
    )

    assert (
        result[
            "orders_submitted"
        ]
        == 0
    )

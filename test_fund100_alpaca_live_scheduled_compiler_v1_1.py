from __future__ import annotations

import json

import pandas as pd
import pytest

import fund100_experiment_runner as research
import fund100_alpaca_live_scheduled_compiler as v10
import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler


def executed_target():

    satellites = pd.Series(
        0.0,
        index=
            research.EQUITY_UNIVERSE,
        dtype=float,
    )

    satellites[
        "EEM"
    ] = 0.083333333333

    satellites[
        "XLE"
    ] = 0.083333333333

    satellites[
        "XLV"
    ] = 0.083333333334

    return satellites


def reconciliation_rows(
    weights: dict,
):

    rows = []

    for symbol, weight in (
        weights.items()
    ):

        rows.append({
            "symbol":
                symbol,

            "target_weight":
                0.0,

            "current_weight":
                weight,

            "weight_delta":
                0.0,

            "current_market_value_usd":
                123.45,

            "target_market_value_usd":
                123.45,

            "diagnostic_delta_usd":
                0.0,

            "diagnostic_direction":
                "HOLD",

            "executable":
                False,
        })

    return rows


def fresh_reconciliation(
    weights: dict,
):

    return {
        "schema":
            "FUND100_LIVE_POSITION_RECONCILIATION_V1",

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            "2099-01-01",

        "strategy_state_sha256":
            "state-hash",

        "manifest_type":
            "PENDING_STRATEGY_EVENT",

        "event_source":
            "SCHEDULED",

        "strategy_event_present":
            True,

        "reconciliation_status":
            "POSITION_AWARE",

        "live_account_binding_sha256":
            "account-binding",

        "broker_snapshot_sha256":
            "private-volatile-hash",

        "position_count":
            len(
                [
                    weight
                    for weight
                    in weights.values()
                    if weight > 0
                ]
            ),

        "open_order_count":
            0,

        "target_weights":
            {},

        "cash_weight":
            max(
                0.0,
                1.0
                - sum(
                    weights.values()
                ),
            ),

        "reconciliation_rows":
            reconciliation_rows(
                weights
            ),

        "gross_diagnostic_delta_usd":
            999.0,

        "diagnostic_buy_total_usd":
            500.0,

        "diagnostic_sell_total_usd":
            499.0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_execution_authorized":
            False,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "orders_submitted":
            0,

        "persistence_policy":
            "EPHEMERAL_NOT_COMMITTED",
    }


def test_broker_current_weights_support_full_v5_universe():

    body = (
        fresh_reconciliation({
            "ACWI":
                0.70,

            "SPY":
                0.10,

            "EEM":
                0.10,
        })
    )

    weights = (
        compiler.broker_current_weights(
            body
        )
    )

    assert (
        weights[
            "SPY"
        ]
        == pytest.approx(
            0.10
        )
    )

    assert (
        weights[
            "XLK"
        ]
        == pytest.approx(
            0.0
        )
    )


def test_position_aware_intents_follow_actual_broker_state():

    body = (
        fresh_reconciliation({
            "ACWI":
                0.80,

            "EEM":
                0.05,

            "XLE":
                0.10,

            "XLV":
                0.05,
        })
    )

    intents = (
        compiler.compile_position_aware_intents(
            reconciliation_body=
                body,

            executed_satellites=
                executed_target(),

            seed=
                "a" * 64,
        )
    )

    by_symbol = {
        item[
            "symbol"
        ]:
            item
        for item
        in intents
    }

    # Final target:
    # ACWI 75%
    # EEM/XLE/XLV ~8.33% each

    assert (
        by_symbol[
            "ACWI"
        ][
            "side"
        ]
        == "sell"
    )

    assert (
        by_symbol[
            "EEM"
        ][
            "side"
        ]
        == "buy"
    )

    assert (
        by_symbol[
            "XLE"
        ][
            "side"
        ]
        == "sell"
    )

    assert (
        by_symbol[
            "XLV"
        ][
            "side"
        ]
        == "buy"
    )


def test_intents_persist_no_actual_broker_weights_or_values():

    body = (
        fresh_reconciliation({
            "ACWI":
                0.80,

            "EEM":
                0.05,

            "XLE":
                0.10,

            "XLV":
                0.05,
        })
    )

    intents = (
        compiler.compile_position_aware_intents(
            reconciliation_body=
                body,

            executed_satellites=
                executed_target(),

            seed=
                "b" * 64,
        )
    )

    serialized = (
        json.dumps(
            intents,
            sort_keys=True,
        )
    )

    forbidden = [
        "current_weight",
        "delta_weight",
        "current_market_value_usd",
        "target_market_value_usd",
        "diagnostic_delta_usd",
        "qty",
        "current_price",
        "broker_snapshot_sha256",
    ]

    for token in forbidden:

        assert (
            token
            not in serialized
        )

    assert all(
        item[
            "notional_usd"
        ]
        is None
        for item
        in intents
    )

    assert all(
        item[
            "executable"
        ]
        is False
        for item
        in intents
    )


def test_structural_output_does_not_persist_broker_snapshot():

    body = (
        fresh_reconciliation({
            "ACWI":
                0.75,

            "EEM":
                0.083333333333,

            "XLE":
                0.083333333333,

            "XLV":
                0.083333333334,
        })
    )

    result = (
        compiler.structural_reconciliation_from_fresh(
            body
        )
    )

    serialized = (
        json.dumps(
            result,
            sort_keys=True,
        )
    )

    assert (
        "broker_snapshot_sha256"
        not in serialized
    )

    assert (
        "reconciliation_rows"
        not in serialized
    )

    assert (
        "cash_weight"
        not in serialized
    )

    assert (
        result[
            "live_holdings_persisted"
        ]
        is False
    )

    assert (
        result[
            "live_dollar_values_persisted"
        ]
        is False
    )


def test_zero_equity_weights_fail_closed():

    body = (
        fresh_reconciliation({})
    )

    body[
        "reconciliation_status"
    ] = "EMPTY_ZERO_EQUITY"

    body[
        "reconciliation_rows"
    ] = [
        {
            "symbol":
                "ACWI",

            "current_weight":
                None,
        }
    ]

    with pytest.raises(
        RuntimeError,
        match="weights are unavailable",
    ):

        compiler.broker_current_weights(
            body
        )


def test_strategy_target_still_uses_frozen_trade_threshold():

    current = pd.Series(
        0.0,
        index=
            research.EQUITY_UNIVERSE,
        dtype=float,
    )

    desired = current.copy()

    current[
        "EEM"
    ] = 0.08

    desired[
        "EEM"
    ] = 0.09

    # 1 percentage point difference is below the frozen
    # 2.5 percentage point minimum trade threshold.
    executed = (
        research.apply_trade_threshold(
            current=
                current,

            desired=
                desired,
        )
    )

    assert (
        executed[
            "EEM"
        ]
        == pytest.approx(
            current[
                "EEM"
            ]
        )
    )


def test_client_ids_remain_fund100_namespaced():

    body = (
        fresh_reconciliation({
            "ACWI":
                1.0,
        })
    )

    intents = (
        compiler.compile_position_aware_intents(
            reconciliation_body=
                body,

            executed_satellites=
                executed_target(),

            seed=
                "c" * 64,
        )
    )

    assert intents

    assert all(
        item[
            "client_order_id"
        ].startswith(
            "f100live-"
        )
        for item
        in intents
    )

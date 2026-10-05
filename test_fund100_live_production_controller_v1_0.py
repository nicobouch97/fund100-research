from decimal import Decimal

import pytest

import fund100_live_production_controller_v1_0 as production


def no_event_body():

    return {
        "schema":
            production.EXPECTED_COMPILER_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "mode":
            "current",

        "status":
            "NO_SCHEDULED_EVENT",

        "genuine_strategy_event":
            False,

        "candidate_intents":
            [],
    }


def genuine_event_body():

    return {
        "schema":
            production.EXPECTED_COMPILER_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "mode":
            "current",

        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_strategy_event":
            True,

        "event_id":
            "test-event-001",

        "final_target_weights": {
            "ACWI":
                0.75,

            "EEM":
                0.10,

            "XLE":
                0.10,

            "XLV":
                0.05,
        },

        "candidate_intents": [
            {
                "symbol":
                    "EEM",

                "side":
                    "sell",

                "client_order_id":
                    "f100-test-s-eem",
            },
            {
                "symbol":
                    "XLV",

                "side":
                    "buy",

                "client_order_id":
                    "f100-test-b-xlv",
            },
        ],
    }


def test_no_event_is_not_genuine():

    body = (
        no_event_body()
    )

    result = (
        production.extract_compiler_view(
            body,
            compiler_sha256=(
                production.canonical_sha256(
                    body
                )
            ),
        )
    )

    assert (
        result[
            "genuine"
        ]
        is False
    )

    assert (
        result[
            "candidates"
        ]
        == {}
    )


def test_genuine_event_preserves_candidate_sides():

    body = (
        genuine_event_body()
    )

    result = (
        production.extract_compiler_view(
            body,
            compiler_sha256=(
                production.canonical_sha256(
                    body
                )
            ),
        )
    )

    assert (
        result[
            "genuine"
        ]
        is True
    )

    assert (
        result[
            "candidates"
        ][
            "EEM"
        ][
            "side"
        ]
        == "sell"
    )

    assert (
        result[
            "candidates"
        ][
            "XLV"
        ][
            "side"
        ]
        == "buy"
    )


def test_target_weights_normalize_acwi_core():

    weights = (
        production.normalize_target_weights(
            {
                "ACWI_CORE":
                    0.75,

                "EEM":
                    0.10,

                "XLE":
                    0.10,

                "XLV":
                    0.05,
            }
        )
    )

    assert (
        weights[
            "ACWI"
        ]
        == Decimal(
            "0.75"
        )
    )

    assert (
        sum(
            weights.values(),
            Decimal("0"),
        )
        == Decimal(
            "1.00"
        )
    )


def test_negative_target_rejected():

    with pytest.raises(
        production.ProductionStop
    ):

        production.normalize_target_weights(
            {
                "ACWI":
                    1.01,

                "EEM":
                    -0.01,
            }
        )


def test_materializer_respects_authorized_sell():

    snapshot = {
        "equity":
            Decimal("100"),

        "cash":
            Decimal("0"),

        "positions": {
            "ACWI": {
                "market_value":
                    Decimal("80"),
            },

            "EEM": {
                "market_value":
                    Decimal("20"),
            },
        },
    }

    target = {
        "ACWI":
            Decimal("0.90"),

        "EEM":
            Decimal("0.10"),
    }

    candidates = {
        "EEM": {
            "symbol":
                "EEM",

            "side":
                "sell",

            "client_order_id":
                "f100-test-s-eem",
        }
    }

    orders = (
        production.materialize_orders(
            snapshot=(
                snapshot
            ),

            target_weights=(
                target
            ),

            candidates=(
                candidates
            ),

            phase="SELL",

            capital_ceiling=(
                Decimal("100")
            ),
        )
    )

    assert len(
        orders
    ) == 1

    assert (
        orders[
            0
        ][
            "side"
        ]
        == "sell"
    )


def test_materializer_rejects_direction_reversal():

    snapshot = {
        "equity":
            Decimal("100"),

        "cash":
            Decimal("20"),

        "positions": {
            "EEM": {
                "market_value":
                    Decimal("5"),
            },
        },
    }

    target = {
        "EEM":
            Decimal("0.20"),

        "ACWI":
            Decimal("0.80"),
    }

    candidates = {
        "EEM": {
            "symbol":
                "EEM",

            "side":
                "sell",

            "client_order_id":
                "f100-test-s-eem",
        }
    }

    with pytest.raises(
        production.ProductionStop
    ):

        production.materialize_orders(
            snapshot=(
                snapshot
            ),

            target_weights=(
                target
            ),

            candidates=(
                candidates
            ),

            phase="SELL",

            capital_ceiling=(
                Decimal("100")
            ),
        )


def test_non_genuine_artifact_cannot_carry_trade_intent():

    body = no_event_body()

    body[
        "candidate_intents"
    ] = [
        {
            "symbol":
                "EEM",

            "side":
                "sell",
        }
    ]

    with pytest.raises(
        production.ProductionStop
    ):

        production.extract_compiler_view(
            body,
            compiler_sha256=(
                production.canonical_sha256(
                    body
                )
            ),
        )


def test_client_ids_are_deterministic_when_missing():

    body = genuine_event_body()

    for item in body[
        "candidate_intents"
    ]:

        item.pop(
            "client_order_id",
            None,
        )

    compiler_hash = (
        production.canonical_sha256(
            body
        )
    )

    first = (
        production.extract_compiler_view(
            body,
            compiler_sha256=(
                compiler_hash
            ),
        )
    )

    second = (
        production.extract_compiler_view(
            body,
            compiler_sha256=(
                compiler_hash
            ),
        )
    )

    assert (
        first[
            "candidates"
        ][
            "EEM"
        ][
            "client_order_id"
        ]
        == second[
            "candidates"
        ][
            "EEM"
        ][
            "client_order_id"
        ]
    )

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


def _synthetic_writer_intent():
    return {
        "client_order_id": "f100live-test-receipt-s-eem",
        "symbol": "EEM",
        "side": "sell",
        "notional_usd": "5.00",
    }


def _synthetic_broker_ack(intent):
    return {
        "id": "synthetic-broker-order-id",
        "client_order_id": intent["client_order_id"],
        "symbol": intent["symbol"],
        "side": intent["side"],
        "notional": intent["notional_usd"],
        "type": "market",
        "time_in_force": "day",
        "status": "accepted",
    }


def test_production_writer_returns_validated_receipt_not_a_fill(monkeypatch):
    intent = _synthetic_writer_intent()
    posts = []
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "DISENGAGED")
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: None
    )
    monkeypatch.setattr(
        production.operator_control, "require_operator_running", lambda: None
    )

    def fake_post(**kwargs):
        posts.append(kwargs)
        return _synthetic_broker_ack(intent)

    monkeypatch.setattr(production.live, "live_request", fake_post)
    result = production.submit_order_batch([intent])
    assert result["writer_schema"] == production.writer_candidate.WRITER_CANDIDATE_SCHEMA
    assert result["orders"][0]["status"] == "SUBMITTED"
    assert result["orders"][0]["broker_order"]["status"] == "accepted"
    assert len(posts) == 1


def test_production_writer_rejects_mismatched_existing_order_without_post(monkeypatch):
    intent = _synthetic_writer_intent()
    existing = {**_synthetic_broker_ack(intent), "symbol": "SPY", "status": "filled"}
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: existing
    )

    def forbidden_post(**kwargs):
        raise AssertionError("must not POST after mismatched broker history")

    monkeypatch.setattr(production.live, "live_request", forbidden_post)
    with pytest.raises(production.ProductionStop, match="not safely reconciled"):
        production.submit_order_batch([intent])


def test_production_writer_rejects_ambiguous_post_without_retry(monkeypatch):
    intent = _synthetic_writer_intent()
    posts = []
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "DISENGAGED")
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: None
    )
    monkeypatch.setattr(
        production.operator_control, "require_operator_running", lambda: None
    )

    def malformed_post(**kwargs):
        posts.append(kwargs)
        return {**_synthetic_broker_ack(intent), "notional": "8.00"}

    monkeypatch.setattr(production.live, "live_request", malformed_post)
    with pytest.raises(production.orchestrator.OrchestrationStop, match="notional"):
        production.submit_order_batch([intent])
    assert len(posts) == 1

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


def _synthetic_filled_broker_order(intent):
    return {
        **_synthetic_broker_ack(intent),
        "status": "filled",
        "filled_qty": "0.05",
        "filled_avg_price": "100.00",
    }


def test_production_fill_wait_accepts_matching_positive_broker_fill(monkeypatch):
    intent = _synthetic_writer_intent()
    filled = _synthetic_filled_broker_order(intent)
    calls = []
    monkeypatch.setattr(
        production.live, "get_order_by_client_id",
        lambda cid: (calls.append(cid) or filled),
    )
    assert production.wait_for_fill(intent) is filled
    assert calls == [intent["client_order_id"]]


@pytest.mark.parametrize("change", [
    {"client_order_id": "different-client-order"},
    {"symbol": "SPY"},
    {"side": "buy"},
    {"type": "limit"},
    {"time_in_force": "gtc"},
    {"notional": "8.00"},
    {"id": ""},
])
def test_production_fill_wait_rejects_wrong_broker_identity(monkeypatch, change):
    intent = _synthetic_writer_intent()
    broker = {**_synthetic_filled_broker_order(intent), **change}
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: broker,
    )
    with pytest.raises(production.ProductionStop, match="fill identity mismatch"):
        production.wait_for_fill(intent)


@pytest.mark.parametrize("change", [
    {"filled_qty": "0"},
    {"filled_avg_price": "0"},
    {"filled_qty": None},
    {"filled_avg_price": "NaN"},
    {"filled_qty": "0.001"},
    {"filled_qty": "0.20"},
])
def test_production_fill_wait_rejects_missing_or_implausible_economics(
    monkeypatch, change
):
    intent = _synthetic_writer_intent()
    broker = {**_synthetic_filled_broker_order(intent), **change}
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: broker,
    )
    with pytest.raises(production.ProductionStop):
        production.wait_for_fill(intent)


def test_production_fill_wait_does_not_promote_partial_to_completed(monkeypatch):
    intent = _synthetic_writer_intent()
    filled = _synthetic_filled_broker_order(intent)
    partial = {**filled, "status": "partially_filled", "filled_qty": "0.01"}
    observations = iter([partial, filled])
    sleeps = []
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: next(observations),
    )
    monkeypatch.setattr(production.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert production.wait_for_fill(intent) is filled
    assert sleeps == [2]


def test_production_fill_wait_rejects_mismatched_partial_before_buy(monkeypatch):
    intent = _synthetic_writer_intent()
    partial = {
        **_synthetic_filled_broker_order(intent),
        "status": "partially_filled",
        "symbol": "SPY",
    }
    monkeypatch.setattr(
        production.live, "get_order_by_client_id", lambda cid: partial,
    )
    monkeypatch.setattr(
        production.time, "sleep",
        lambda seconds: pytest.fail("mismatched partial must not be polled"),
    )
    with pytest.raises(production.ProductionStop, match="fill identity mismatch"):
        production.wait_for_fill(intent)


# Same-event SELL proceeds are NOT proof of settled or spendable BUY cash.
def _prefunded_buy(notional="15.00"):
    return [{"symbol": "XLV", "side": "buy",
             "notional_usd": notional, "client_order_id": "f100-test-b-xlv"}]


def test_prefunded_buy_passes_only_when_both_cash_snapshots_cover_batch():
    total = production.require_prefunded_buy_cash(
        orders=_prefunded_buy(),
        opening_cash=Decimal("20.00"),
        current_cash=Decimal("18.00"),
    )
    assert total == Decimal("15.00")


def test_prefunded_buy_rejects_same_event_sale_credit_even_when_fresh_cash_rises():
    with pytest.raises(production.ProductionStop, match="unverified sale"):
        production.require_prefunded_buy_cash(
            orders=_prefunded_buy(),
            opening_cash=Decimal("10.00"),
            current_cash=Decimal("80.00"),
        )


def test_prefunded_buy_rejects_fresh_cash_drain_despite_large_opening_balance():
    with pytest.raises(production.ProductionStop, match="pre-SELL/fresh"):
        production.require_prefunded_buy_cash(
            orders=_prefunded_buy(),
            opening_cash=Decimal("80.00"),
            current_cash=Decimal("10.00"),
        )


@pytest.mark.parametrize("opening,current", [
    (Decimal("-0.01"), Decimal("30")),
    (Decimal("30"), Decimal("-0.01")),
    (Decimal("NaN"), Decimal("30")),
    (Decimal("30"), Decimal("Infinity")),
    ("30.00", Decimal("30")),
])
def test_prefunded_buy_rejects_unverified_or_malformed_cash(opening, current):
    with pytest.raises(production.ProductionStop, match="invalid"):
        production.require_prefunded_buy_cash(
            orders=_prefunded_buy(),
            opening_cash=opening,
            current_cash=current,
        )


@pytest.mark.parametrize("orders", [
    [{"side": "sell", "notional_usd": "15.00"}],
    [{"side": "buy", "notional_usd": "NaN"}],
    [{"side": "buy", "notional_usd": "-1.00"}],
    [{"side": "buy"}],
])
def test_prefunded_buy_rejects_malformed_order_evidence(orders):
    with pytest.raises(production.ProductionStop):
        production.require_prefunded_buy_cash(
            orders=orders,
            opening_cash=Decimal("30"),
            current_cash=Decimal("30"),
        )


def test_actual_orchestrator_buy_materialization_rechecks_original_cash(monkeypatch):
    monkeypatch.setattr(
        production, "verify_live_portfolio_risk", lambda **kwargs: None
    )
    monkeypatch.setattr(
        production, "materialize_orders", lambda **kwargs: _prefunded_buy()
    )
    deps, last, _ = production.build_dependencies(
        policy_context={"capital_ceiling": Decimal("130.30")},
        target_weights={},
        candidates={},
        opening_cash=Decimal("10.00"),
    )
    with pytest.raises(production.ProductionStop, match="unverified sale"):
        deps.materialize_execution_phase(
            broker_snapshot={"cash": Decimal("80.00")},
            phase="BUY",
        )
    assert last["BUY"] == []


def test_actual_orchestrator_buy_materialization_accepts_prefunded_batch(monkeypatch):
    monkeypatch.setattr(
        production, "verify_live_portfolio_risk", lambda **kwargs: None
    )
    monkeypatch.setattr(
        production, "materialize_orders", lambda **kwargs: _prefunded_buy()
    )
    deps, last, _ = production.build_dependencies(
        policy_context={"capital_ceiling": Decimal("130.30")},
        target_weights={},
        candidates={},
        opening_cash=Decimal("20.00"),
    )
    result = deps.materialize_execution_phase(
        broker_snapshot={"cash": Decimal("18.00")},
        phase="BUY",
    )
    assert result["orders"] == _prefunded_buy()
    assert last["BUY"] == _prefunded_buy()


# LIVE snapshot parsing is a broker-safety boundary, not a trading release.
# These tests inject invented responses; no Alpaca credentials or HTTP.
def _fake_live_snapshot(monkeypatch, *, account=None, positions=None, orders=None):
    base_account = {
        "status": "ACTIVE", "account_blocked": False,
        "trading_blocked": False, "equity": "100.00", "cash": "20.00",
    }
    base_positions = [{"symbol": "ACWI", "qty": "1", "market_value": "80.00"}]
    monkeypatch.setattr(
        production.live, "get_account",
        lambda: base_account if account is None else account,
    )
    monkeypatch.setattr(
        production.live, "get_positions",
        lambda: base_positions if positions is None else positions,
    )
    monkeypatch.setattr(
        production.live, "get_open_orders",
        lambda: [] if orders is None else orders,
    )
    monkeypatch.setattr(production.live, "account_binding", lambda _: "test-binding")
    return production.fresh_snapshot(
        allowed_client_ids={"test-allowed-order"},
        universe={"ACWI"},
        expected_account_binding="test-binding",
    )


def test_live_snapshot_accepts_unique_explicitly_unblocked_broker_state(monkeypatch):
    snap = _fake_live_snapshot(monkeypatch)
    assert snap["cash"] == Decimal("20.00")
    assert snap["positions"]["ACWI"]["market_value"] == Decimal("80.00")


@pytest.mark.parametrize("field,bad_value", [
    ("trading_blocked", None),
    ("trading_blocked", "false"),
    ("trading_blocked", 0),
    ("trading_blocked", True),
    ("account_blocked", None),
    ("account_blocked", "false"),
    ("account_blocked", 0),
    ("account_blocked", True),
])
def test_live_snapshot_requires_exact_unblocked_account_flags(
    monkeypatch, field, bad_value
):
    account = {
        "status": "ACTIVE", "account_blocked": False,
        "trading_blocked": False, "equity": "100", "cash": "20",
    }
    account[field] = bad_value
    with pytest.raises(production.ProductionStop, match="block status"):
        _fake_live_snapshot(monkeypatch, account=account)


@pytest.mark.parametrize("field", ["account_blocked", "trading_blocked"])
def test_live_snapshot_missing_block_flags_fail_closed(monkeypatch, field):
    account = {
        "status": "ACTIVE", "account_blocked": False,
        "trading_blocked": False, "equity": "100", "cash": "20",
    }
    account.pop(field)
    with pytest.raises(production.ProductionStop, match="block status"):
        _fake_live_snapshot(monkeypatch, account=account)


def test_live_snapshot_rejects_non_object_account(monkeypatch):
    with pytest.raises(production.ProductionStop, match="malformed broker account"):
        _fake_live_snapshot(monkeypatch, account=[])


def test_live_snapshot_rejects_duplicate_positions_instead_of_understating_risk(
    monkeypatch,
):
    rows = [
        {"symbol": "ACWI", "qty": "1", "market_value": "80"},
        {"symbol": "ACWI", "qty": "2", "market_value": "160"},
    ]
    with pytest.raises(production.ProductionStop, match="duplicate broker position"):
        _fake_live_snapshot(monkeypatch, positions=rows)


def test_live_snapshot_rejects_negative_position_value(monkeypatch):
    rows = [{"symbol": "ACWI", "qty": "1", "market_value": "-5"}]
    with pytest.raises(production.ProductionStop, match="negative broker position"):
        _fake_live_snapshot(monkeypatch, positions=rows)


def test_live_snapshot_rejects_duplicate_open_order_ids(monkeypatch):
    rows = [{"client_order_id": "test-allowed-order"}] * 2
    with pytest.raises(production.ProductionStop, match="duplicate open broker"):
        _fake_live_snapshot(monkeypatch, orders=rows)


@pytest.mark.parametrize("bad_positions,bad_orders", [
    ([None], None),
    (None, [None]),
])
def test_live_snapshot_malformed_entries_fail_with_controlled_stop(
    monkeypatch, bad_positions, bad_orders
):
    with pytest.raises(production.ProductionStop, match="malformed broker"):
        _fake_live_snapshot(
            monkeypatch, positions=bad_positions, orders=bad_orders,
        )


def test_live_snapshot_rejects_negative_cash_before_any_writer(monkeypatch):
    account = {
        "status": "ACTIVE", "account_blocked": False,
        "trading_blocked": False, "equity": "100", "cash": "-1",
    }
    with pytest.raises(production.ProductionStop, match="negative cash"):
        _fake_live_snapshot(monkeypatch, account=account)

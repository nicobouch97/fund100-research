from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_candidate_v1_0 as candidate


def executable_intent():

    return {
        "symbol":
            "SPY",

        "side":
            "buy",

        "notional_usd":
            12.34,

        "client_order_id":
            "f100live-candidate-test-b-spy",

        "executable":
            True,
    }


def test_candidate_transport_is_hard_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
        match="transport has not been released",
    ):

        candidate.require_transport_released()


def test_candidate_public_execution_is_hard_locked():

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate.require_public_execution_released()


def test_candidate_uses_full_frozen_v5_universe():

    expected = {
        "ACWI",
        "SPY",
        "IWM",
        "EFA",
        "EEM",
        "VNQ",
        "XLK",
        "XLF",
        "XLI",
        "XLV",
        "XLP",
        "XLY",
        "XLE",
        "XLU",
    }

    assert (
        candidate.ALLOWED_SYMBOLS
        == expected
    )


def test_market_notional_payload_shape():

    payload = (
        candidate.build_order_payload(
            executable_intent()
        )
    )

    assert payload == {
        "symbol":
            "SPY",

        "notional":
            "12.34",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "extended_hours":
            False,

        "client_order_id":
            "f100live-candidate-test-b-spy",
    }

    assert (
        "qty"
        not in payload
    )


def test_money_payload_rounds_down_to_cents():

    intent = (
        executable_intent()
    )

    intent[
        "notional_usd"
    ] = 12.349

    payload = (
        candidate.build_order_payload(
            intent
        )
    )

    assert (
        payload[
            "notional"
        ]
        == "12.34"
    )


def test_matching_existing_order_is_accepted():

    intent = (
        executable_intent()
    )

    existing = {
        "id":
            "broker-order-123",

        "client_order_id":
            intent[
                "client_order_id"
            ],

        "symbol":
            "SPY",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            "12.34",

        "status":
            "new",
    }

    result = (
        candidate.validate_existing_order_matches_intent(
            existing=
                existing,

            intent=
                intent,
        )
    )

    assert (
        result
        is existing
    )


def test_existing_order_symbol_mismatch_fails_closed():

    intent = (
        executable_intent()
    )

    existing = {
        "id":
            "broker-order-123",

        "client_order_id":
            intent[
                "client_order_id"
            ],

        "symbol":
            "VNQ",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            "12.34",
    }

    with pytest.raises(
        candidate.ExistingOrderMismatch,
        match="symbol mismatch",
    ):

        candidate.validate_existing_order_matches_intent(
            existing=
                existing,

            intent=
                intent,
        )


def test_existing_order_side_mismatch_fails_closed():

    intent = (
        executable_intent()
    )

    existing = {
        "id":
            "broker-order-123",

        "client_order_id":
            intent[
                "client_order_id"
            ],

        "symbol":
            "SPY",

        "side":
            "sell",

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            "12.34",
    }

    with pytest.raises(
        candidate.ExistingOrderMismatch,
        match="side mismatch",
    ):

        candidate.validate_existing_order_matches_intent(
            existing=
                existing,

            intent=
                intent,
        )


def test_existing_order_notional_mismatch_fails_closed():

    intent = (
        executable_intent()
    )

    existing = {
        "id":
            "broker-order-123",

        "client_order_id":
            intent[
                "client_order_id"
            ],

        "symbol":
            "SPY",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            "13.34",
    }

    with pytest.raises(
        candidate.ExistingOrderMismatch,
        match="notional mismatch",
    ):

        candidate.validate_existing_order_matches_intent(
            existing=
                existing,

            intent=
                intent,
        )


def test_direct_get_stops_before_network(
    monkeypatch,
):

    network_called = {
        "value":
            False,
    }

    def forbidden_urlopen(
        *args,
        **kwargs,
    ):

        network_called[
            "value"
        ] = True

        raise AssertionError(
            "Network must not be reached."
        )

    monkeypatch.setattr(
        candidate,
        "urlopen",
        forbidden_urlopen,
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate._get_order_by_client_id(
            client_order_id=
                "f100live-candidate-get-test",

            key=
                "fake-key",

            secret=
                "fake-secret",
        )

    assert (
        network_called[
            "value"
        ]
        is False
    )


def test_direct_post_stops_before_network(
    monkeypatch,
):

    network_called = {
        "value":
            False,
    }

    def forbidden_urlopen(
        *args,
        **kwargs,
    ):

        network_called[
            "value"
        ] = True

        raise AssertionError(
            "Network must not be reached."
        )

    monkeypatch.setattr(
        candidate,
        "urlopen",
        forbidden_urlopen,
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate._post_live_market_order(
            intent=
                executable_intent(),

            key=
                "fake-key",

            secret=
                "fake-secret",
        )

    assert (
        network_called[
            "value"
        ]
        is False
    )


def test_public_entrypoint_stops_before_permit_parsing():

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate.submit_authorized_order_batch(
            intents=[
                executable_intent()
            ],

            permit_package={
                "deliberately":
                    "invalid",
            },

            key=
                "fake-key",

            secret=
                "fake-secret",
        )


def test_submitted_response_requires_matching_client_id():

    intent = (
        executable_intent()
    )

    response = {
        "id":
            "broker-order-123",

        "client_order_id":
            "different-client-id",

        "symbol":
            "SPY",

        "side":
            "buy",
    }

    with pytest.raises(
        RuntimeError,
        match="client_order_id mismatch",
    ):

        candidate.validate_submitted_order_response(
            response=
                response,

            intent=
                intent,
        )


def test_submitted_response_requires_broker_order_id():

    intent = (
        executable_intent()
    )

    response = {
        "client_order_id":
            intent[
                "client_order_id"
            ],

        "symbol":
            "SPY",

        "side":
            "buy",
    }

    with pytest.raises(
        RuntimeError,
        match="no order ID",
    ):

        candidate.validate_submitted_order_response(
            response=
                response,

            intent=
                intent,
        )


def test_candidate_has_no_main():

    assert not hasattr(
        candidate,
        "main",
    )

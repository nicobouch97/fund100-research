from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_disconnected as writer


def test_live_writer_is_declared_disconnected():

    assert (
        writer.LIVE_WRITER_CONNECTED
        is False
    )


def test_connection_gate_always_blocks():

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer.require_adapter_connected()


def test_public_submit_blocks_before_any_network(
    monkeypatch,
):

    network_called = {
        "value": False
    }

    def fake_urlopen(
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
        writer,
        "urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer.submit_authorized_order_batch(
            intents=[],
            permit_package={},
            key="test-key",
            secret="test-secret",
        )

    assert (
        network_called[
            "value"
        ]
        is False
    )


def test_private_post_blocks_before_any_network(
    monkeypatch,
):

    network_called = {
        "value": False
    }

    def fake_urlopen(
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
        writer,
        "urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer._post_live_market_order(
            intent={
                "symbol":
                    "ACWI",

                "side":
                    "buy",

                "notional_usd":
                    1.00,

                "client_order_id":
                    "f100live-test-b-acwi",

                "executable":
                    True,
            },
            key="test-key",
            secret="test-secret",
        )

    assert (
        network_called[
            "value"
        ]
        is False
    )


def test_current_v1_permit_can_never_authorize():

    permit_body = {
        "schema":
            "FUND100_LIVE_EXECUTION_PERMIT_V1",

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "genuine_scheduled_event":
            False,
    }

    package = {
        "permit_sha256":
            writer.sha256_json(
                permit_body
            ),

        "permit":
            permit_body,
    }

    with pytest.raises(
        writer.LivePermitRejected,
        match="required schema",
    ):

        writer.validate_permit_package(
            package
        )


def test_non_executable_intent_is_rejected():

    with pytest.raises(
        writer.LiveIntentRejected,
        match="non-executable",
    ):

        writer.validate_order_intent({
            "symbol":
                "ACWI",

            "side":
                "buy",

            "notional_usd":
                1.00,

            "client_order_id":
                "f100live-test-b-acwi",

            "executable":
                False,
        })


def test_client_order_id_limit():

    long_id = (
        "f100live-"
        + "x" * 130
    )

    with pytest.raises(
        writer.LiveIntentRejected,
        match="exceeds",
    ):

        writer.validate_order_intent({
            "symbol":
                "ACWI",

            "side":
                "buy",

            "notional_usd":
                1.00,

            "client_order_id":
                long_id,

            "executable":
                True,
        })


def test_batch_cannot_exceed_permit_cap():

    intents = [
        {
            "symbol":
                "ACWI",

            "side":
                "buy",

            "notional_usd":
                6.00,

            "client_order_id":
                "f100live-test-b-acwi",

            "executable":
                True,
        },
        {
            "symbol":
                "EEM",

            "side":
                "buy",

            "notional_usd":
                5.00,

            "client_order_id":
                "f100live-test-b-eem",

            "executable":
                True,
        },
    ]

    with pytest.raises(
        writer.LiveIntentRejected,
        match="exceeds",
    ):

        writer.validate_order_batch(
            intents=
                intents,

            permit_cap=
                10.00,
        )

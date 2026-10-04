from __future__ import annotations

from decimal import Decimal

import pytest

import fund100_alpaca_paper_orchestrator_connected_v1_0 as connected
import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


def test_endpoint_is_exactly_alpaca_paper():

    assert (
        connected.PAPER_BASE_URL
        == "https://paper-api.alpaca.markets"
    )

    assert (
        connected.EXPECTED_PAPER_HOST
        == "paper-api.alpaca.markets"
    )

    assert (
        connected.FORBIDDEN_LIVE_HOST
        == "api.alpaca.markets"
    )


def test_live_writer_candidate_remains_locked():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_orchestrator_remains_unreleased():

    assert (
        orchestrator.ORCHESTRATOR_RELEASED
        is False
    )

    assert (
        orchestrator.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_connected_test_notional_is_exactly_one_dollar():

    assert (
        connected.SYNTHETIC_NOTIONAL_USD
        == Decimal(
            "1.00"
        )
    )

    assert (
        connected.PAPER_CEILING_USD
        == Decimal(
            "1.00"
        )
    )


def test_new_order_fits_exact_cap():

    client_id = "f100-test"

    proof = (
        connected.evaluate_paper_cap(
            authorized_order_history={
                client_id:
                    None,
            },

            new_orders=[
                {
                    "client_order_id":
                        client_id,

                    "notional_usd":
                        "1.00",
                }
            ],

            ceiling_usd="1.00",
        )
    )

    assert (
        proof[
            "approved"
        ]
        is True
    )

    assert (
        proof[
            "historical_notional_usd"
        ]
        == "0"
    )

    assert (
        proof[
            "unseen_notional_usd"
        ]
        == "1.00"
    )

    assert (
        proof[
            "projected_notional_usd"
        ]
        == "1.00"
    )


def test_existing_order_is_not_double_counted():

    client_id = "f100-test"

    proof = (
        connected.evaluate_paper_cap(
            authorized_order_history={
                client_id: {
                    "client_order_id":
                        client_id,

                    "status":
                        "new",

                    "notional":
                        "1.00",
                }
            },

            new_orders=[
                {
                    "client_order_id":
                        client_id,

                    "notional_usd":
                        "1.00",
                }
            ],

            ceiling_usd="1.00",
        )
    )

    assert (
        proof[
            "historical_notional_usd"
        ]
        == "1.00"
    )

    assert (
        proof[
            "unseen_notional_usd"
        ]
        == "0"
    )

    assert (
        proof[
            "projected_notional_usd"
        ]
        == "1.00"
    )


def test_over_cap_is_rejected():

    with pytest.raises(
        connected.PaperOrchestratorStop,
        match="projected cumulative notional",
    ):

        connected.evaluate_paper_cap(
            authorized_order_history={
                "old": {
                    "client_order_id":
                        "old",

                    "status":
                        "filled",

                    "notional":
                        "0.75",
                },

                "new":
                    None,
            },

            new_orders=[
                {
                    "client_order_id":
                        "new",

                    "notional_usd":
                        "0.26",
                }
            ],

            ceiling_usd="1.00",
        )


def test_partial_fill_consumes_full_submitted_notional():

    proof = (
        connected.evaluate_paper_cap(
            authorized_order_history={
                "old": {
                    "client_order_id":
                        "old",

                    "status":
                        "partially_filled",

                    "notional":
                        "1.00",

                    "filled_qty":
                        "0.001",
                }
            },

            new_orders=[],

            ceiling_usd="1.00",
        )
    )

    assert (
        proof[
            "historical_notional_usd"
        ]
        == "1.00"
    )


def test_failed_terminal_history_is_rejected():

    with pytest.raises(
        connected.PaperOrchestratorStop,
        match="unsafe terminal history",
    ):

        connected.evaluate_paper_cap(
            authorized_order_history={
                "old": {
                    "client_order_id":
                        "old",

                    "status":
                        "rejected",

                    "notional":
                        "1.00",
                }
            },

            new_orders=[],

            ceiling_usd="1.00",
        )


def test_live_url_is_rejected():

    with pytest.raises(
        connected.PaperOrchestratorStop,
        match="non-PAPER host",
    ):

        connected._validate_url(
            "https://api.alpaca.markets/v2/account"
        )

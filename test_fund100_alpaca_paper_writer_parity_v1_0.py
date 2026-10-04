from __future__ import annotations

from pathlib import Path

import pytest

import fund100_alpaca_live_writer_candidate_v1_0 as candidate
import fund100_alpaca_paper_transport_v1_0 as paper
import fund100_alpaca_paper_writer_parity_v1_0 as parity


def test_paper_endpoint_is_exact():

    assert (
        paper.PAPER_BASE_URL
        == "https://paper-api.alpaca.markets"
    )

    assert (
        paper.EXPECTED_PAPER_HOST
        == "paper-api.alpaca.markets"
    )


def test_paper_validator_rejects_live_host():

    with pytest.raises(
        RuntimeError,
        match="unexpected broker hostname",
    ):

        paper.validate_paper_url(
            "https://api.alpaca.markets/v2/orders"
        )


def test_candidate_source_flags_remain_false():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_synthetic_notional_is_minimal_candidate_notional():

    assert (
        parity.TEST_NOTIONAL_USD
        == 1.00
    )

    assert (
        parity.TEST_NOTIONAL_USD
        >= candidate.MIN_NOTIONAL_USD
    )


def test_synthetic_permit_is_not_live_artifact():

    package = (
        parity.build_synthetic_permit()
    )

    body = (
        package[
            "permit"
        ]
    )

    assert (
        body[
            "paper_transport_parity_only"
        ]
        is True
    )

    assert (
        body[
            "persist_this_permit"
        ]
        is False
    )


def test_market_open_fails_closed():

    with pytest.raises(
        RuntimeError,
        match="must be CLOSED",
    ):

        parity.verify_market_closed({
            "is_open":
                True,
        })


def test_market_closed_is_accepted():

    parity.verify_market_closed({
        "is_open":
            False,
    })


def test_zero_fill_and_terminal_helpers():

    canceled = {
        "status":
            "canceled",

        "filled_qty":
            "0",
    }

    assert (
        parity.zero_filled_quantity(
            canceled
        )
        is True
    )

    assert (
        parity.is_safe_terminal_zero_fill(
            canceled
        )
        is True
    )

    pending = {
        "status":
            "pending_cancel",

        "filled_qty":
            "0",
    }

    assert (
        parity.is_safe_terminal_zero_fill(
            pending
        )
        is False
    )

    filled = {
        "status":
            "canceled",

        "filled_qty":
            "0.01",
    }

    assert (
        parity.is_safe_terminal_zero_fill(
            filled
        )
        is False
    )


def test_open_order_snapshot_ignores_stale_terminal_entry(
    monkeypatch,
):

    monkeypatch.setattr(
        paper,
        "get_order_by_id",
        lambda **kwargs: {
            "id":
                "order-1",

            "status":
                "canceled",

            "filled_qty":
                "0",
        },
    )

    result = (
        parity.classify_open_order_snapshot(
            open_orders=[
                {
                    "id":
                        "order-1",

                    "status":
                        "new",

                    "client_order_id":
                        "example",
                }
            ],

            key=
                "paper-key",

            secret=
                "paper-secret",
        )
    )

    assert (
        len(
            result[
                "stale_terminal"
            ]
        )
        == 1
    )

    assert (
        result[
            "genuinely_open"
        ]
        == []
    )

    assert (
        result[
            "indeterminate"
        ]
        == []
    )


def test_open_order_snapshot_keeps_pending_cancel_open(
    monkeypatch,
):

    monkeypatch.setattr(
        paper,
        "get_order_by_id",
        lambda **kwargs: {
            "id":
                "order-1",

            "status":
                "pending_cancel",

            "filled_qty":
                "0",
        },
    )

    result = (
        parity.classify_open_order_snapshot(
            open_orders=[
                {
                    "id":
                        "order-1",

                    "status":
                        "pending_cancel",

                    "client_order_id":
                        "example",
                }
            ],

            key=
                "paper-key",

            secret=
                "paper-secret",
        )
    )

    assert (
        len(
            result[
                "genuinely_open"
            ]
        )
        == 1
    )

    assert (
        result[
            "stale_terminal"
        ]
        == []
    )


def test_open_index_convergence_waits_through_stale_snapshot(
    monkeypatch,
):

    calls = {
        "count":
            0,
    }

    def fake_open_orders(
        *,
        key,
        secret,
    ):

        del key
        del secret

        calls[
            "count"
        ] += 1

        if (
            calls[
                "count"
            ]
            == 1
        ):

            return [
                {
                    "id":
                        "order-1",

                    "client_order_id":
                        "client-1",

                    "status":
                        "new",
                }
            ]

        return []

    monkeypatch.setattr(
        parity,
        "get_open_orders",
        fake_open_orders,
    )

    monkeypatch.setattr(
        paper,
        "get_order_by_id",
        lambda **kwargs: {
            "id":
                "order-1",

            "status":
                "canceled",

            "filled_qty":
                "0",
        },
    )

    monkeypatch.setattr(
        parity.time,
        "sleep",
        lambda seconds: None,
    )

    result = (
        parity.wait_for_test_order_absent_from_open_index(
            client_order_id=
                "client-1",

            order_id=
                "order-1",

            key=
                "paper-key",

            secret=
                "paper-secret",
        )
    )

    assert (
        result[
            "converged"
        ]
        is True
    )

    assert (
        result[
            "stale_open_index_observations"
        ]
        == 1
    )


def test_open_index_convergence_rejects_fill(
    monkeypatch,
):

    monkeypatch.setattr(
        parity,
        "get_open_orders",
        lambda **kwargs: [
            {
                "id":
                    "order-1",

                "client_order_id":
                    "client-1",

                "status":
                    "new",
            }
        ],
    )

    monkeypatch.setattr(
        paper,
        "get_order_by_id",
        lambda **kwargs: {
            "id":
                "order-1",

            "status":
                "partially_filled",

            "filled_qty":
                "0.01",
        },
    )

    with pytest.raises(
        RuntimeError,
        match="received a fill",
    ):

        parity.wait_for_test_order_absent_from_open_index(
            client_order_id=
                "client-1",

            order_id=
                "order-1",

            key=
                "paper-key",

            secret=
                "paper-secret",
        )


def test_safe_output_keeps_live_execution_false():

    package = (
        parity.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            candidate_sha256=
                "b" * 64,

            client_order_id=
                "f100live-paperparity-test",

            counters={
                "candidate_get_requests":
                    2,

                "candidate_post_requests":
                    1,

                "non_paper_host_requests":
                    0,
            },

            cleanup={
                "terminal_status":
                    "CANCELED",

                "zero_fill":
                    True,

                "cancel_requested":
                    True,

                "cancel_response_code":
                    204,

                "terminal_poll_count":
                    2,
            },

            open_index={
                "converged":
                    True,

                "poll_count":
                    3,

                "stale_open_index_observations":
                    2,
            },
        )
    )

    body = (
        package[
            "paper_parity"
        ]
    )

    assert (
        body[
            "candidate_post_requests"
        ]
        == 1
    )

    assert (
        body[
            "duplicate_post_requests"
        ]
        == 0
    )

    assert (
        body[
            "paper_order_zero_fill_verified"
        ]
        is True
    )

    assert (
        body[
            "open_order_index_converged"
        ]
        is True
    )

    assert (
        body[
            "final_genuinely_open_orders"
        ]
        == 0
    )

    assert (
        body[
            "paper_position_created"
        ]
        is False
    )

    assert (
        body[
            "live_endpoint_contacted"
        ]
        is False
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "live_orders_submitted"
        ]
        == 0
    )


def test_no_live_endpoint_literal_in_paper_transport_helper():

    source = (
        Path(
            paper.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        "https://api.alpaca.markets"
        not in source
    )


def test_parity_runner_loads_credentials_only_from_paper_helper():

    source = (
        Path(
            parity.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        "ALPACA_PAPER_KEY"
        not in source
    )

    assert (
        "ALPACA_PAPER_SECRET"
        not in source
    )

    assert (
        "paper.load_paper_credentials()"
        in source
    )

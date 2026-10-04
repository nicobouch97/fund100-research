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

    body = package[
        "permit"
    ]

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


def test_parity_runner_does_not_use_live_credentials():

    source = (
        Path(
            parity.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    # These names appear only inside the explicit rejection
    # function. There must be no secrets lookup intended for
    # normal use beyond rejecting their presence.
    assert (
        "ALPACA_PAPER_KEY"
        not in source
    )

    assert (
        "ALPACA_PAPER_SECRET"
        not in source
    )

    # Credentials are loaded exclusively through the
    # paper-only transport helper.
    assert (
        "paper.load_paper_credentials()"
        in source
    )


def test_cleanup_rejects_nonzero_fill():

    assert (
        parity.zero_filled_quantity({
            "filled_qty":
                "0"
        })
        is True
    )

    assert (
        parity.zero_filled_quantity({
            "filled_qty":
                "0.01"
        })
        is False
    )

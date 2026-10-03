from __future__ import annotations

import pytest

import fund100_experiment_runner as research
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


EXPECTED_SATELLITES = {
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


def make_intent(
    symbol: str,
):

    return {
        "symbol":
            symbol,

        "side":
            "buy",

        "notional_usd":
            1.00,

        "client_order_id":
            (
                "f100live-test-"
                + symbol.lower()
            ),

        "executable":
            True,
    }


def test_frozen_research_universe_matches_expected():

    assert set(
        research.EQUITY_UNIVERSE
    ) == EXPECTED_SATELLITES


def test_writer_universe_is_exact_research_plus_core():

    expected = (
        set(
            research.EQUITY_UNIVERSE
        )
        | {
            "ACWI",
        }
    )

    assert (
        writer.ALLOWED_SYMBOLS
        == expected
    )


def test_writer_universe_contract_passes():

    writer.validate_frozen_v5_execution_universe(
        research.EQUITY_UNIVERSE
    )


@pytest.mark.parametrize(
    "symbol",
    sorted(
        EXPECTED_SATELLITES
        | {
            "ACWI",
        }
    ),
)
def test_every_frozen_live_symbol_is_accepted(
    symbol,
):

    validated = (
        writer.validate_order_intent(
            make_intent(
                symbol
            )
        )
    )

    assert (
        validated[
            "symbol"
        ]
        == symbol
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "AAPL",
        "BTCUSD",
        "QQQ",
        "TLT",
        "GLD",
        "UNKNOWN",
    ],
)
def test_non_strategy_symbol_is_rejected(
    symbol,
):

    with pytest.raises(
        writer.LiveIntentRejected,
        match="Unsupported live symbol",
    ):

        writer.validate_order_intent(
            make_intent(
                symbol
            )
        )


def test_batch_cap_is_enforced():

    intents = [
        {
            **make_intent(
                "SPY"
            ),
            "notional_usd":
                6.00,
        },
        {
            **make_intent(
                "EEM"
            ),
            "notional_usd":
                5.00,
        },
    ]

    with pytest.raises(
        writer.LiveIntentRejected,
        match="exceeds the execution permit ceiling",
    ):

        writer.validate_order_batch(
            intents=
                intents,

            permit_cap=
                10.00,
        )


def test_writer_still_reports_disconnected():

    assert (
        writer.LIVE_WRITER_CONNECTED
        is False
    )


def test_disconnect_guard_has_no_success_path():

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer.require_adapter_connected()


def test_submit_entrypoint_stops_immediately():

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer.submit_authorized_order_batch(
            intents=[
                make_intent(
                    "SPY"
                )
            ],
            permit_package={},
            key="not-used",
            secret="not-used",
        )

from __future__ import annotations

import pytest

import fund100_alpaca_live_position_reconcile as reconcile


def state():

    return {
        "strategy":
            "V5-002_SHADOW",

        "last_date":
            "2099-01-01",

        "satellite_weights": {
            "EEM":
                0.083333333333,

            "XLE":
                0.083333333333,

            "XLV":
                0.083333333334,
        },

        "pending_target":
            None,

        "pending_source":
            None,
    }


def account(
    portfolio_value="100.00",
    cash="100.00",
    long_market_value="0.00",
    short_market_value="0.00",
):

    return {
        "id":
            "00000000-0000-0000-0000-000000000001",

        "status":
            "ACTIVE",

        "currency":
            "USD",

        "portfolio_value":
            portfolio_value,

        "cash":
            cash,

        "long_market_value":
            long_market_value,

        "short_market_value":
            short_market_value,

        "account_blocked":
            False,

        "trading_blocked":
            False,

        "trade_suspended_by_user":
            False,
    }


def position(
    symbol,
    market_value,
    qty="1.0",
    current_price=None,
    side="long",
):

    if current_price is None:

        current_price = market_value

    return {
        "symbol":
            symbol,

        "asset_class":
            "us_equity",

        "side":
            side,

        "qty":
            str(
                qty
            ),

        "market_value":
            str(
                market_value
            ),

        "current_price":
            str(
                current_price
            ),
    }


def test_empty_zero_equity_account_is_supported():

    package = (
        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="0",
                    cash="0",
                    long_market_value="0",
                ),

            positions=[],

            open_orders=[],
        )
    )

    body = (
        package[
            "reconciliation"
        ]
    )

    assert (
        body[
            "reconciliation_status"
        ]
        == "EMPTY_ZERO_EQUITY"
    )

    assert (
        body[
            "position_count"
        ]
        == 0
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "network_write_capability"
        ]
        is False
    )


def test_all_cash_account_can_be_reconciled():

    package = (
        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(),

            positions=[],

            open_orders=[],
        )
    )

    body = (
        package[
            "reconciliation"
        ]
    )

    assert (
        body[
            "reconciliation_status"
        ]
        == "POSITION_AWARE"
    )

    assert (
        body[
            "cash_weight"
        ]
        == pytest.approx(
            1.0
        )
    )

    assert (
        body[
            "diagnostic_buy_total_usd"
        ]
        == pytest.approx(
            100.0
        )
    )

    assert all(
        row[
            "executable"
        ]
        is False
        for row
        in body[
            "reconciliation_rows"
        ]
    )


def test_existing_fund100_positions_are_supported():

    positions = [
        position(
            "ACWI",
            "75.00",
        ),
        position(
            "EEM",
            "8.33",
        ),
        position(
            "XLE",
            "8.33",
        ),
        position(
            "XLV",
            "8.34",
        ),
    ]

    package = (
        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="0.00",
                    long_market_value="100.00",
                ),

            positions=
                positions,

            open_orders=[],
        )
    )

    body = (
        package[
            "reconciliation"
        ]
    )

    assert (
        body[
            "position_count"
        ]
        == 4
    )

    assert (
        body[
            "long_only_verified"
        ]
        is True
    )

    assert (
        body[
            "no_unmanaged_positions_verified"
        ]
        is True
    )


def test_full_frozen_universe_symbol_is_supported():

    package = (
        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="90.00",
                    long_market_value="10.00",
                ),

            positions=[
                position(
                    "SPY",
                    "10.00",
                ),
            ],

            open_orders=[],
        )
    )

    assert (
        package[
            "reconciliation"
        ][
            "position_count"
        ]
        == 1
    )


def test_unmanaged_position_is_rejected():

    with pytest.raises(
        RuntimeError,
        match="unmanaged position",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="90.00",
                    long_market_value="10.00",
                ),

            positions=[
                position(
                    "AAPL",
                    "10.00",
                ),
            ],

            open_orders=[],
        )


def test_short_position_is_rejected():

    with pytest.raises(
        RuntimeError,
        match="position is not long",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="90.00",
                    long_market_value="10.00",
                ),

            positions=[
                position(
                    "SPY",
                    "10.00",
                    side="short",
                ),
            ],

            open_orders=[],
        )


def test_account_short_market_value_is_rejected():

    with pytest.raises(
        RuntimeError,
        match="short exposure",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="100.00",
                    long_market_value="0.00",
                    short_market_value="-10.00",
                ),

            positions=[],

            open_orders=[],
        )


def test_negative_cash_is_rejected():

    with pytest.raises(
        RuntimeError,
        match="negative cash",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="-1.00",
                    long_market_value="101.00",
                ),

            positions=[
                position(
                    "ACWI",
                    "101.00",
                ),
            ],

            open_orders=[],
        )


def test_open_orders_are_rejected():

    with pytest.raises(
        RuntimeError,
        match="contains open orders",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(),

            positions=[],

            open_orders=[
                {
                    "id":
                        "order-test",
                }
            ],
        )


def test_material_position_account_mismatch_is_rejected():

    with pytest.raises(
        RuntimeError,
        match="materially disagree",
    ):

        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(
                    portfolio_value="100.00",
                    cash="50.00",
                    long_market_value="50.00",
                ),

            positions=[
                position(
                    "ACWI",
                    "20.00",
                ),
            ],

            open_orders=[],
        )


def test_reconciliation_never_creates_executable_rows():

    package = (
        reconcile.build_reconciliation(
            state=
                state(),

            account=
                account(),

            positions=[],

            open_orders=[],
        )
    )

    rows = (
        package[
            "reconciliation"
        ][
            "reconciliation_rows"
        ]
    )

    assert all(
        row[
            "executable"
        ]
        is False
        for row
        in rows
    )

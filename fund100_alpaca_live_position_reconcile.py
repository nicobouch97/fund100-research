from __future__ import annotations

import hashlib
import json
import os
import sys
from decimal import Decimal, InvalidOperation

import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_manifest as strategy
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_writer_disconnected_v1_1 as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE POSITION RECONCILIATION v1.0
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# Purpose:
#
# Make Fund-100 aware of existing LIVE positions without
# enabling any broker mutation.
#
# This is the bridge between:
#
#     "clean account bootstrap"
#
# and:
#
#     "repeatable rebalance lifecycle"
#
# This file:
#
# - GETs account state
# - GETs open positions
# - GETs open orders
# - validates the complete frozen V5 universe
# - rejects shorts
# - rejects foreign/unmanaged positions
# - rejects open orders
# - rejects leverage / materially negative cash
# - calculates current weights
# - compares them to the V5-002 strategy target
#
# It DOES NOT:
#
# - POST orders
# - PATCH orders
# - DELETE orders
# - cancel orders
# - persist live holdings
# - authorize live execution
#
# ============================================================


EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

RECONCILE_ARM_VALUE = (
    "YES_READ_ONLY_POSITION_RECONCILE"
)

SCHEMA = (
    "FUND100_LIVE_POSITION_RECONCILIATION_V1"
)

LIVE_EXECUTION_AUTHORIZED = False

NETWORK_WRITE_CAPABILITY = False

BROKER_WRITE_MODE = "DISABLED"

ORDERS_SUBMITTED = 0


# Account/position snapshots come from separate GET requests.
# Small mark-to-market movement between calls is therefore
# expected.
MIN_MARKET_VALUE_TOLERANCE_USD = (
    Decimal("0.50")
)

RELATIVE_MARKET_VALUE_TOLERANCE = (
    Decimal("0.01")
)

NEGATIVE_CASH_TOLERANCE_USD = (
    Decimal("0.01")
)

SHORT_VALUE_TOLERANCE_USD = (
    Decimal("0.01")
)

DIRECTION_TOLERANCE_USD = (
    Decimal("0.005")
)


# ============================================================
# HASHING
# ============================================================


def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# ARM
# ============================================================


def require_reconcile_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_POSITION_RECONCILE",
            "",
        )
        .strip()
    )

    if value != RECONCILE_ARM_VALUE:

        raise RuntimeError(
            "Live position reconciler is not "
            "explicitly armed."
        )


# ============================================================
# DECIMAL HELPERS
# ============================================================


def as_decimal(
    value,
    field_name: str,
) -> Decimal:

    try:

        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise RuntimeError(
            f"{field_name}: invalid numeric value."
        ) from exc

    if not result.is_finite():

        raise RuntimeError(
            f"{field_name}: value must be finite."
        )

    return result


def as_float(
    value: Decimal,
) -> float:

    return float(
        value
    )


# ============================================================
# ACCOUNT BINDING
# ============================================================


def account_binding_sha256(
    account: dict,
) -> str:

    account_id = str(
        account.get(
            "id",
            "",
        )
    ).strip()

    if not account_id:

        raise RuntimeError(
            "Live account ID is missing."
        )

    return sha256_text(
        "FUND100_ALPACA_LIVE_ACCOUNT_V1:"
        + account_id
    )


# ============================================================
# ACCOUNT VALIDATION
# ============================================================


def validate_account_for_reconciliation(
    account: dict,
):

    if not isinstance(
        account,
        dict,
    ):

        raise RuntimeError(
            "Invalid live account response."
        )

    status = str(
        account.get(
            "status",
            "",
        )
    ).upper()

    if status != "ACTIVE":

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "account is not ACTIVE."
        )

    if bool(
        account.get(
            "account_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "account is blocked."
        )

    if bool(
        account.get(
            "trading_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "trading is blocked."
        )

    if bool(
        account.get(
            "trade_suspended_by_user",
            False,
        )
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "trading is suspended by user."
        )

    currency = str(
        account.get(
            "currency",
            "",
        )
    ).upper()

    if currency != "USD":

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "account currency is not USD."
        )

    portfolio_value = (
        as_decimal(
            account.get(
                "portfolio_value",
                "0",
            ),
            "portfolio_value",
        )
    )

    cash = (
        as_decimal(
            account.get(
                "cash",
                "0",
            ),
            "cash",
        )
    )

    long_market_value = (
        as_decimal(
            account.get(
                "long_market_value",
                "0",
            ),
            "long_market_value",
        )
    )

    short_market_value = (
        as_decimal(
            account.get(
                "short_market_value",
                "0",
            ),
            "short_market_value",
        )
    )

    if portfolio_value < 0:

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "negative portfolio value."
        )

    if (
        cash
        < -NEGATIVE_CASH_TOLERANCE_USD
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "negative cash indicates leverage or "
            "an unsettled account state."
        )

    if (
        abs(
            short_market_value
        )
        > SHORT_VALUE_TOLERANCE_USD
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "account contains short exposure."
        )

    if long_market_value < 0:

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "negative long market value."
        )

    return {
        "portfolio_value":
            portfolio_value,

        "cash":
            cash,

        "long_market_value":
            long_market_value,

        "short_market_value":
            short_market_value,
    }


# ============================================================
# OPEN ORDERS
# ============================================================


def validate_open_orders(
    open_orders,
):

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid live open-order response."
        )

    if open_orders:

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "live account contains open orders."
        )


# ============================================================
# POSITION VALIDATION
# ============================================================


def parse_positions(
    positions,
):

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid live positions response."
        )

    parsed = {}

    for position in positions:

        if not isinstance(
            position,
            dict,
        ):

            raise RuntimeError(
                "Invalid live position object."
            )

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).upper()

        if not symbol:

            raise RuntimeError(
                "Live position has no symbol."
            )

        if symbol in parsed:

            raise RuntimeError(
                f"Duplicate live position: {symbol}."
            )

        if (
            symbol
            not in writer.ALLOWED_SYMBOLS
        ):

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"unmanaged position {symbol!r} "
                "exists outside the frozen Fund-100 universe."
            )

        asset_class = str(
            position.get(
                "asset_class",
                "",
            )
        ).lower()

        if asset_class != "us_equity":

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"{symbol}: unexpected asset class "
                f"{asset_class!r}."
            )

        side = str(
            position.get(
                "side",
                "",
            )
        ).lower()

        if side != "long":

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"{symbol}: position is not long."
            )

        qty = (
            as_decimal(
                position.get(
                    "qty",
                    "0",
                ),
                f"{symbol}.qty",
            )
        )

        market_value = (
            as_decimal(
                position.get(
                    "market_value",
                    "0",
                ),
                f"{symbol}.market_value",
            )
        )

        current_price = (
            as_decimal(
                position.get(
                    "current_price",
                    "0",
                ),
                f"{symbol}.current_price",
            )
        )

        if qty <= 0:

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"{symbol}: non-positive position quantity."
            )

        if market_value <= 0:

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"{symbol}: non-positive market value."
            )

        if current_price <= 0:

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                f"{symbol}: non-positive current price."
            )

        parsed[
            symbol
        ] = {
            "symbol":
                symbol,

            "qty":
                qty,

            "market_value":
                market_value,

            "current_price":
                current_price,
        }

    return parsed


# ============================================================
# STRATEGY TARGET
# ============================================================


def build_target(
    state: dict,
):

    if (
        state.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected V5-002 strategy identity."
        )

    context = (
        strategy.build_strategy_context(
            state
        )
    )

    target = {
        str(
            symbol
        ).upper():
            float(
                weight
            )
        for symbol, weight
        in context[
            "target_weights"
        ].items()
    }

    if not set(
        target
    ).issubset(
        writer.ALLOWED_SYMBOLS
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "strategy target contains a symbol outside "
            "the frozen live execution universe."
        )

    total = sum(
        target.values()
    )

    if abs(
        total
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "strategy target does not sum to 100%."
        )

    return (
        context,
        target,
    )


# ============================================================
# RECONCILIATION
# ============================================================


def build_reconciliation(
    state: dict,
    account: dict,
    positions,
    open_orders,
):

    validate_open_orders(
        open_orders
    )

    account_values = (
        validate_account_for_reconciliation(
            account
        )
    )

    parsed_positions = (
        parse_positions(
            positions
        )
    )

    (
        context,
        target,
    ) = (
        build_target(
            state
        )
    )

    portfolio_value = (
        account_values[
            "portfolio_value"
        ]
    )

    cash = (
        account_values[
            "cash"
        ]
    )

    broker_long_value = (
        account_values[
            "long_market_value"
        ]
    )

    position_market_value = sum(
        (
            item[
                "market_value"
            ]
            for item
            in parsed_positions.values()
        ),
        Decimal(
            "0"
        ),
    )

    tolerance = max(
        MIN_MARKET_VALUE_TOLERANCE_USD,
        (
            portfolio_value
            * RELATIVE_MARKET_VALUE_TOLERANCE
        ),
    )

    if (
        abs(
            position_market_value
            - broker_long_value
        )
        > tolerance
    ):

        raise RuntimeError(
            "LIVE RECONCILIATION STOP: "
            "position market values materially disagree "
            "with account long_market_value."
        )

    rows = []

    gross_diagnostic_delta = (
        Decimal(
            "0"
        )
    )

    diagnostic_buy_total = (
        Decimal(
            "0"
        )
    )

    diagnostic_sell_total = (
        Decimal(
            "0"
        )
    )

    symbols = sorted(
        set(
            target
        )
        | set(
            parsed_positions
        )
    )

    if portfolio_value == 0:

        if parsed_positions:

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                "zero-value account contains positions."
            )

        if (
            abs(
                cash
            )
            > NEGATIVE_CASH_TOLERANCE_USD
        ):

            raise RuntimeError(
                "LIVE RECONCILIATION STOP: "
                "zero portfolio value conflicts with "
                "non-zero cash."
            )

        status = (
            "EMPTY_ZERO_EQUITY"
        )

        cash_weight = None

        for symbol in symbols:

            rows.append({
                "symbol":
                    symbol,

                "target_weight":
                    float(
                        target.get(
                            symbol,
                            0.0,
                        )
                    ),

                "current_weight":
                    None,

                "weight_delta":
                    None,

                "current_market_value_usd":
                    None,

                "target_market_value_usd":
                    None,

                "diagnostic_delta_usd":
                    None,

                "diagnostic_direction":
                    "UNAVAILABLE_WITH_ZERO_EQUITY",

                "executable":
                    False,
            })

    else:

        status = (
            "POSITION_AWARE"
        )

        cash_weight = (
            cash
            / portfolio_value
        )

        for symbol in symbols:

            current_value = (
                parsed_positions.get(
                    symbol,
                    {},
                ).get(
                    "market_value",
                    Decimal(
                        "0"
                    ),
                )
            )

            target_weight = (
                Decimal(
                    str(
                        target.get(
                            symbol,
                            0.0,
                        )
                    )
                )
            )

            current_weight = (
                current_value
                / portfolio_value
            )

            target_value = (
                target_weight
                * portfolio_value
            )

            delta = (
                target_value
                - current_value
            )

            weight_delta = (
                target_weight
                - current_weight
            )

            gross_diagnostic_delta += (
                abs(
                    delta
                )
            )

            if (
                delta
                > DIRECTION_TOLERANCE_USD
            ):

                direction = "BUY"

                diagnostic_buy_total += (
                    delta
                )

            elif (
                delta
                < -DIRECTION_TOLERANCE_USD
            ):

                direction = "SELL"

                diagnostic_sell_total += (
                    abs(
                        delta
                    )
                )

            else:

                direction = "HOLD"

            rows.append({
                "symbol":
                    symbol,

                "target_weight":
                    as_float(
                        target_weight
                    ),

                "current_weight":
                    as_float(
                        current_weight
                    ),

                "weight_delta":
                    as_float(
                        weight_delta
                    ),

                "current_market_value_usd":
                    as_float(
                        current_value
                    ),

                "target_market_value_usd":
                    as_float(
                        target_value
                    ),

                "diagnostic_delta_usd":
                    as_float(
                        delta
                    ),

                "diagnostic_direction":
                    direction,

                "executable":
                    False,
            })

    state_hash = (
        strategy.sha256_json(
            state
        )
    )

    account_binding = (
        account_binding_sha256(
            account
        )
    )

    private_snapshot = {
        "portfolio_value":
            as_float(
                portfolio_value
            ),

        "cash":
            as_float(
                cash
            ),

        "long_market_value":
            as_float(
                broker_long_value
            ),

        "short_market_value":
            as_float(
                account_values[
                    "short_market_value"
                ]
            ),

        "positions":
            {
                symbol: {
                    "qty":
                        as_float(
                            item[
                                "qty"
                            ]
                        ),

                    "market_value":
                        as_float(
                            item[
                                "market_value"
                            ]
                        ),

                    "current_price":
                        as_float(
                            item[
                                "current_price"
                            ]
                        ),
                }
                for symbol, item
                in sorted(
                    parsed_positions.items()
                )
            },
    }

    body = {
        "schema":
            SCHEMA,

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            str(
                state.get(
                    "last_date"
                )
            ),

        "strategy_state_sha256":
            state_hash,

        "manifest_type":
            context[
                "manifest_type"
            ],

        "event_source":
            context[
                "event_source"
            ],

        "strategy_event_present":
            context[
                "strategy_event_present"
            ],

        "reconciliation_status":
            status,

        "live_account_binding_sha256":
            account_binding,

        "broker_snapshot_sha256":
            sha256_json(
                private_snapshot
            ),

        "position_count":
            len(
                parsed_positions
            ),

        "open_order_count":
            0,

        "target_weights":
            target,

        "cash_weight":
            (
                None
                if cash_weight is None
                else as_float(
                    cash_weight
                )
            ),

        "reconciliation_rows":
            rows,

        "gross_diagnostic_delta_usd":
            (
                None
                if portfolio_value == 0
                else as_float(
                    gross_diagnostic_delta
                )
            ),

        "diagnostic_buy_total_usd":
            (
                None
                if portfolio_value == 0
                else as_float(
                    diagnostic_buy_total
                )
            ),

        "diagnostic_sell_total_usd":
            (
                None
                if portfolio_value == 0
                else as_float(
                    diagnostic_sell_total
                )
            ),

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "network_write_capability":
            NETWORK_WRITE_CAPABILITY,

        "broker_write_mode":
            BROKER_WRITE_MODE,

        "orders_submitted":
            ORDERS_SUBMITTED,

        "persistence_policy":
            "EPHEMERAL_NOT_COMMITTED",
    }

    return {
        "reconciliation_sha256":
            sha256_json(
                body
            ),

        "reconciliation":
            body,
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE POSITION RECONCILIATION"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: READ ONLY"
    )

    print(
        "Broker HTTP methods: GET ONLY"
    )

    print(
        "Persistence of live holdings: NONE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Network write capability: ABSENT"
    )

    require_reconcile_arm()

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE RECONCILIATION SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    writer.validate_frozen_v5_execution_universe(
        writer.FROZEN_V5_SATELLITE_UNIVERSE
    )

    key, secret = (
        live.load_credentials()
    )

    state = (
        strategy.load_state()
    )

    account = (
        live.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    preflight.validate_account(
        account
    )

    positions = (
        live.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    open_orders = (
        live.get_json(
            path="/v2/orders",
            key=key,
            secret=secret,
            params={
                "status":
                    "open",

                "limit":
                    100,
            },
        )
    )

    package = (
        build_reconciliation(
            state=
                state,

            account=
                account,

            positions=
                positions,

            open_orders=
                open_orders,
        )
    )

    body = (
        package[
            "reconciliation"
        ]
    )

    print(
        "\n============================================"
    )

    print(
        "POSITION-AWARE BROKER STATE"
    )

    print(
        "============================================"
    )

    print(
        f"\nStrategy state date: "
        f"{body['strategy_state_date']}"
    )

    print(
        f"Strategy event present: "
        f"{body['strategy_event_present']}"
    )

    print(
        f"Reconciliation status: "
        f"{body['reconciliation_status']}"
    )

    print(
        f"Existing position count: "
        f"{body['position_count']}"
    )

    print(
        "Open orders: 0 — PASS"
    )

    print(
        "Frozen V5 execution universe: PASS"
    )

    print(
        "Long-only portfolio structure: PASS"
    )

    print(
        "Unmanaged positions: NONE"
    )

    print(
        "Broker snapshot hash: "
        + body[
            "broker_snapshot_sha256"
        ]
    )

    print(
        "Reconciliation SHA256: "
        + package[
            "reconciliation_sha256"
        ]
    )

    print(
        "\nLive account dollar values: NOT LOGGED"
    )

    print(
        "Individual live holdings: NOT LOGGED"
    )

    print(
        "Reconciliation artifact committed: NO"
    )

    print(
        "\nLive execution authorized: FALSE"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE POSITION RECONCILIATION: PASS"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "LIVE POSITION RECONCILIATION: FAILED",
            file=sys.stderr,
        )

        print(
            "============================================",
            file=sys.stderr,
        )

        print(
            str(
                exc
            ),
            file=sys.stderr,
        )

        raise

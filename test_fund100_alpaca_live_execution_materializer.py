from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import fund100_alpaca_live_execution_materializer as materializer
import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


def future_time():

    return (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            hours=1
        )
    )


def base_target():

    satellites = {
        symbol:
            0.0
        for symbol
        in writer.FROZEN_V5_SATELLITE_UNIVERSE
    }

    satellites[
        "SPY"
    ] = 0.10

    satellites[
        "VNQ"
    ] = 0.10

    return satellites


def compiler_package():

    body = {
        "schema":
            materializer.EXPECTED_COMPILER_SCHEMA,

        "strategy":
            materializer.EXPECTED_STRATEGY,

        "status":
            "GENUINE_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            True,

        "broker_delta_source":
            "FRESH_EPHEMERAL_RECONCILIATION",

        "broker_current_weights_persisted":
            False,

        "broker_dollar_values_persisted":
            False,

        "executed_satellite_weights":
            base_target(),

        "candidate_intents": [
            {
                "symbol":
                    "ACWI",

                "side":
                    "sell",

                "target_weight":
                    0.80,

                "client_order_id":
                    "f100live-test-s-acwi",

                "notional_usd":
                    None,

                "executable":
                    False,
            },

            {
                "symbol":
                    "SPY",

                "side":
                    "buy",

                "target_weight":
                    0.10,

                "client_order_id":
                    "f100live-test-b-spy",

                "notional_usd":
                    None,

                "executable":
                    False,
            },

            {
                "symbol":
                    "VNQ",

                "side":
                    "buy",

                "target_weight":
                    0.10,

                "client_order_id":
                    "f100live-test-b-vnq",

                "notional_usd":
                    None,

                "executable":
                    False,
            },
        ],
    }

    return {
        "compiler":
            body,

        "compiler_sha256":
            writer.sha256_json(
                body
            ),
    }


def lock_package():

    body = {
        "schema":
            materializer.EXPECTED_LOCK_SCHEMA,

        "position_aware_live_chain_verified":
            True,

        "v2_issuer_v1_1_compatibility_upgrade_required":
            False,

        "final_activation_lock_required_after_issuer_upgrade":
            False,

        "critical_file_sha256":
            {},
    }

    return {
        "release_lock":
            body,

        "release_lock_sha256":
            writer.sha256_json(
                body
            ),
    }


def permit_package(
    *,
    compiler_hash: str,
    lock_hash: str,
    cap=100.0,
):

    expiry = (
        future_time()
        .isoformat()
    )

    body = {
        "schema":
            materializer.EXPECTED_PERMIT_SCHEMA,

        "permit_issued":
            True,

        "live_execution_authorized":
            True,

        "network_write_capability":
            True,

        "broker_write_mode":
            "ENABLED",

        "genuine_scheduled_event":
            True,

        "max_live_execution_notional_usd":
            cap,

        "single_use":
            True,

        "event_previously_permitted":
            False,

        "execution_requires_separate_kill_switch_transition":
            True,

        "writer_connected_at_issuance":
            False,

        "issuer_broker_write_capability":
            False,

        "orders_submitted_by_issuer":
            0,

        "source_release_lock_sha256":
            lock_hash,

        "source_release_lock_schema":
            materializer.EXPECTED_LOCK_SCHEMA,

        "source_compiler_sha256":
            compiler_hash,

        "source_compiler_schema":
            materializer.EXPECTED_COMPILER_SCHEMA,

        "candidate_expiry":
            expiry,

        "live_account_binding_sha256":
            "account-binding-test",

        "candidate_symbols": [
            "ACWI",
            "SPY",
            "VNQ",
        ],
    }

    return {
        "permit":
            body,

        "permit_sha256":
            writer.sha256_json(
                body
            ),
    }


def account(
    *,
    cash="0",
):

    return {
        "id":
            "test-account",

        "status":
            "ACTIVE",

        "account_blocked":
            False,

        "trading_blocked":
            False,

        "trade_suspended_by_user":
            False,

        "currency":
            "USD",

        "portfolio_value":
            "100.00",

        "cash":
            cash,

        "long_market_value":
            str(
                100
                - float(
                    cash
                )
            ),

        "short_market_value":
            "0",
    }


def positions_before_sell():

    return [
        {
            "symbol":
                "ACWI",

            "asset_class":
                "us_equity",

            "side":
                "long",

            "qty":
                "1",

            "market_value":
                "100.00",

            "current_price":
                "100.00",
        }
    ]


def positions_after_sell():

    return [
        {
            "symbol":
                "ACWI",

            "asset_class":
                "us_equity",

            "side":
                "long",

            "qty":
                "0.8",

            "market_value":
                "80.00",

            "current_price":
                "100.00",
        }
    ]


def patch_final_lock_ready(
    monkeypatch,
):

    monkeypatch.setattr(
        issuer,
        "final_lock_is_ready",
        lambda body: True,
    )


def patch_account_binding(
    monkeypatch,
):

    import fund100_alpaca_live_position_reconcile as reconcile

    monkeypatch.setattr(
        reconcile,
        "account_binding_sha256",
        lambda account_obj:
            "account-binding-test",
    )


def packages():

    compiler = (
        compiler_package()
    )

    lock = (
        lock_package()
    )

    permit = (
        permit_package(
            compiler_hash=
                compiler[
                    "compiler_sha256"
                ],

            lock_hash=
                lock[
                    "release_lock_sha256"
                ],
        )
    )

    return (
        lock,
        compiler,
        permit,
    )


def test_final_target_reconstructs_acwi_core():

    compiler = (
        compiler_package()[
            "compiler"
        ]
    )

    target = (
        materializer.build_full_target_weights(
            compiler
        )
    )

    assert (
        float(
            target[
                "ACWI"
            ]
        )
        == pytest.approx(
            0.80
        )
    )

    assert (
        float(
            target[
                "SPY"
            ]
        )
        == pytest.approx(
            0.10
        )
    )

    assert (
        float(
            target[
                "VNQ"
            ]
        )
        == pytest.approx(
            0.10
        )
    )

    assert (
        float(
            sum(
                target.values()
            )
        )
        == pytest.approx(
            1.0
        )
    )


def test_sell_phase_materializes_from_fresh_portfolio(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    result = (
        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="0"
                ),

            positions=
                positions_before_sell(),

            open_orders=[],

            phase=
                "SELL",

            now=
                datetime.now(
                    timezone.utc
                ),
        )
    )

    assert (
        result[
            "phase"
        ]
        == "SELL"
    )

    assert (
        len(
            result[
                "executable_intents"
            ]
        )
        == 1
    )

    order = (
        result[
            "executable_intents"
        ][
            0
        ]
    )

    assert (
        order[
            "symbol"
        ]
        == "ACWI"
    )

    assert (
        order[
            "side"
        ]
        == "sell"
    )

    assert (
        order[
            "notional_usd"
        ]
        == pytest.approx(
            20.0
        )
    )

    assert (
        order[
            "executable"
        ]
        is True
    )


def test_buy_phase_requires_current_cash(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    with pytest.raises(
        RuntimeError,
        match="SELL phase must be filled",
    ):

        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="0"
                ),

            positions=
                positions_before_sell(),

            open_orders=[],

            phase=
                "BUY",

            now=
                datetime.now(
                    timezone.utc
                ),
        )


def test_buy_phase_materializes_after_sell_cash_exists(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    result = (
        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="20"
                ),

            positions=
                positions_after_sell(),

            open_orders=[],

            phase=
                "BUY",

            now=
                datetime.now(
                    timezone.utc
                ),
        )
    )

    orders = {
        item[
            "symbol"
        ]:
            item
        for item
        in result[
            "executable_intents"
        ]
    }

    assert (
        set(
            orders
        )
        == {
            "SPY",
            "VNQ",
        }
    )

    assert (
        orders[
            "SPY"
        ][
            "notional_usd"
        ]
        == pytest.approx(
            10.0
        )
    )

    assert (
        orders[
            "VNQ"
        ][
            "notional_usd"
        ]
        == pytest.approx(
            10.0
        )
    )


def test_fresh_direction_change_fails_closed(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    changed_positions = [
        {
            "symbol":
                "ACWI",

            "asset_class":
                "us_equity",

            "side":
                "long",

            "qty":
                "0.7",

            "market_value":
                "70.00",

            "current_price":
                "100.00",
        }
    ]

    changed_account = {
        **account(
            cash="30"
        ),

        "long_market_value":
            "70.00",
    }

    with pytest.raises(
        RuntimeError,
        match="changed direction",
    ):

        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                changed_account,

            positions=
                changed_positions,

            open_orders=[],

            phase=
                "SELL",

            now=
                datetime.now(
                    timezone.utc
                ),
        )


def test_permit_cap_is_enforced(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock = (
        lock_package()
    )

    compiler = (
        compiler_package()
    )

    permit = (
        permit_package(
            compiler_hash=
                compiler[
                    "compiler_sha256"
                ],

            lock_hash=
                lock[
                    "release_lock_sha256"
                ],

            cap=
                30.0,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="exceeds the V2 permit ceiling",
    ):

        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="0"
                ),

            positions=
                positions_before_sell(),

            open_orders=[],

            phase=
                "SELL",

            now=
                datetime.now(
                    timezone.utc
                ),
        )


def test_open_orders_fail_closed(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    with pytest.raises(
        RuntimeError,
        match="open orders",
    ):

        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="0"
                ),

            positions=
                positions_before_sell(),

            open_orders=[
                {
                    "id":
                        "existing-order"
                }
            ],

            phase=
                "SELL",

            now=
                datetime.now(
                    timezone.utc
                ),
        )


def test_expired_permit_fails_closed(
    monkeypatch,
):

    patch_final_lock_ready(
        monkeypatch
    )

    patch_account_binding(
        monkeypatch
    )

    lock, compiler, permit = (
        packages()
    )

    permit[
        "permit"
    ][
        "candidate_expiry"
    ] = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            minutes=1
        )
    ).isoformat()

    permit[
        "permit_sha256"
    ] = (
        writer.sha256_json(
            permit[
                "permit"
            ]
        )
    )

    with pytest.raises(
        RuntimeError,
        match="permit has expired",
    ):

        materializer.materialize_execution_phase(
            release_lock_package=
                lock,

            compiler_package=
                compiler,

            permit_package=
                permit,

            account=
                account(
                    cash="0"
                ),

            positions=
                positions_before_sell(),

            open_orders=[],

            phase=
                "SELL",

            now=
                datetime.now(
                    timezone.utc
                ),
        )


def test_candidate_symbol_set_must_match_permit():

    compiler = (
        compiler_package()
    )

    target = (
        materializer.build_full_target_weights(
            compiler[
                "compiler"
            ]
        )
    )

    permit = (
        permit_package(
            compiler_hash=
                compiler[
                    "compiler_sha256"
                ],

            lock_hash=
                "x" * 64,
        )[
            "permit"
        ]
    )

    permit[
        "candidate_symbols"
    ] = [
        "ACWI",
        "SPY",
    ]

    with pytest.raises(
        RuntimeError,
        match="exactly match",
    ):

        materializer.build_authorized_candidates(
            compiler=
                compiler[
                    "compiler"
                ],

            permit=
                permit,

            target=
                target,
        )


def test_module_has_no_live_network_api():

    assert not hasattr(
        materializer,
        "urlopen",
    )

    assert not hasattr(
        materializer,
        "Request",
    )

    assert not hasattr(
        materializer,
        "main",
    )

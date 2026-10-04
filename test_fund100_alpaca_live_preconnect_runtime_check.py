from __future__ import annotations

import ast

import pytest

import fund100_alpaca_live_preconnect_runtime_check as check


def structure():

    return {
        "schema":
            "FUND100_LIVE_POSITION_RECONCILIATION_V1",

        "policy":
            "EPHEMERAL_POSITION_AWARE_V1",

        "live_account_binding_sha256":
            "account-binding",

        "reconciliation_status":
            "POSITION_AWARE",

        "position_count":
            3,

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,
    }


def fresh():

    return {
        "live_account_binding_sha256":
            "account-binding",

        "reconciliation_status":
            "POSITION_AWARE",

        "position_count":
            3,

        "open_order_count":
            0,

        "strategy_state_sha256":
            "state-hash",

        "strategy_state_date":
            "2026-10-02",

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_execution_authorized":
            False,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "persistence_policy":
            "EPHEMERAL_NOT_COMMITTED",
    }


def manifest():

    return {
        "strategy_state_sha256":
            "state-hash",

        "strategy_state_date":
            "2026-10-02",
    }


def compiler():

    return {
        "strategy_state_sha256":
            "state-hash",
    }


def test_structural_binding_matches():

    left = structure()

    right = dict(
        left
    )

    right.pop(
        "schema"
    )

    assert (
        check.structural_binding_matches(
            left,
            right,
        )
        is True
    )


def test_structural_binding_detects_position_change():

    left = structure()

    right = dict(
        left
    )

    right.pop(
        "schema"
    )

    right[
        "position_count"
    ] = 2

    assert (
        check.structural_binding_matches(
            left,
            right,
        )
        is False
    )


def test_fresh_runtime_binding_accepts_matching_structure():

    manifest_structure = (
        structure()
    )

    compiler_structure = dict(
        manifest_structure
    )

    compiler_structure.pop(
        "schema"
    )

    assert (
        check.verify_fresh_runtime_binding(
            fresh=
                fresh(),

            manifest=
                manifest(),

            compiler=
                compiler(),

            manifest_structure=
                manifest_structure,

            compiler_structure=
                compiler_structure,
        )
        is True
    )


def test_fresh_runtime_binding_rejects_account_change():

    current = fresh()

    current[
        "live_account_binding_sha256"
    ] = "different-account"

    manifest_structure = (
        structure()
    )

    compiler_structure = dict(
        manifest_structure
    )

    compiler_structure.pop(
        "schema"
    )

    with pytest.raises(
        RuntimeError,
        match="account binding changed",
    ):

        check.verify_fresh_runtime_binding(
            fresh=
                current,

            manifest=
                manifest(),

            compiler=
                compiler(),

            manifest_structure=
                manifest_structure,

            compiler_structure=
                compiler_structure,
        )


def test_fresh_runtime_binding_rejects_position_change():

    current = fresh()

    current[
        "position_count"
    ] = 4

    manifest_structure = (
        structure()
    )

    compiler_structure = dict(
        manifest_structure
    )

    compiler_structure.pop(
        "schema"
    )

    with pytest.raises(
        RuntimeError,
        match="position count changed",
    ):

        check.verify_fresh_runtime_binding(
            fresh=
                current,

            manifest=
                manifest(),

            compiler=
                compiler(),

            manifest_structure=
                manifest_structure,

            compiler_structure=
                compiler_structure,
        )


def test_safe_output_is_non_authorizing():

    package = (
        check.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            candidate_sha256=
                "b" * 64,

            manifest_sha256=
                "c" * 64,

            compiler_sha256=
                "d" * 64,

            fresh=
                fresh(),
        )
    )

    body = (
        package[
            "runtime_check"
        ]
    )

    check.assert_safe_output(
        body
    )

    assert (
        body[
            "broker_http_methods"
        ]
        == "GET_ONLY"
    )

    assert (
        body[
            "broker_post_request_count"
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
            "permit_issued"
        ]
        is False
    )

    assert (
        body[
            "writer_connected"
        ]
        is False
    )

    assert (
        body[
            "orders_submitted"
        ]
        == 0
    )


def test_safe_output_persists_no_live_holdings_or_values():

    package = (
        check.build_safe_output(
            release_lock_sha256=
                "a" * 64,

            candidate_sha256=
                "b" * 64,

            manifest_sha256=
                "c" * 64,

            compiler_sha256=
                "d" * 64,

            fresh=
                fresh(),
        )
    )

    body = (
        package[
            "runtime_check"
        ]
    )

    assert (
        body[
            "live_holdings_persisted"
        ]
        is False
    )

    assert (
        body[
            "live_dollar_values_persisted"
        ]
        is False
    )

    assert (
        body[
            "broker_snapshot_hash_persisted"
        ]
        is False
    )

    forbidden = {
        "positions",
        "holdings",
        "reconciliation_rows",
        "portfolio_value",
        "cash",
        "market_value",
        "current_price",
        "broker_snapshot_sha256",
        "candidate_intents",
        "executable_intents",
        "api_key",
        "api_secret",
    }

    assert (
        forbidden.intersection(
            body.keys()
        )
        == set()
    )


def test_preconnect_module_does_not_import_writer_candidate():

    source = (
        check.Path(
            check.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    tree = ast.parse(
        source
    )

    imported = set()

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                imported.add(
                    alias.name
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):

            imported.add(
                str(
                    node.module
                    or ""
                )
            )

    assert (
        "fund100_alpaca_live_writer_candidate_v1_0"
        not in imported
    )


def test_actual_candidate_source_is_still_unreleased():

    values = (
        check.extract_candidate_release_constants()
    )

    assert (
        values[
            "TRANSPORT_RELEASED"
        ]
        is False
    )

    assert (
        values[
            "PUBLIC_EXECUTION_ENABLED"
        ]
        is False
    )

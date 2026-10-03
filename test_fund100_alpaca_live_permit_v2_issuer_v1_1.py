from __future__ import annotations

import pytest

import fund100_alpaca_live_permit_v2_issuer as base
import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


def interim_lock():

    return {
        "schema":
            issuer.RELEASE_LOCK_SCHEMA,

        "position_aware_live_chain_verified":
            True,

        "position_reconciliation_policy":
            issuer.POSITION_POLICY,

        "v2_issuer_v1_1_compatibility_upgrade_required":
            True,

        "final_activation_lock_required_after_issuer_upgrade":
            True,

        "critical_file_sha256":
            {},
    }


def safe_structure(
    *,
    schema=True,
):

    body = {
        "policy":
            issuer.POSITION_POLICY,

        "live_account_binding_sha256":
            "account-binding",

        "reconciliation_status":
            "POSITION_AWARE",

        "position_count":
            4,

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

    if schema:

        body[
            "schema"
        ] = (
            "FUND100_LIVE_POSITION_RECONCILIATION_V1"
        )

    return body


def test_schema_targets_are_v1_1():

    assert (
        issuer.RELEASE_LOCK_SCHEMA
        == "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
    )

    assert (
        issuer.MANIFEST_SCHEMA
        == "FUND100_LIVE_DRYRUN_MANIFEST_V1_1"
    )

    assert (
        issuer.COMPILER_SCHEMA
        == "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
    )


def test_apply_v1_1_uses_full_writer():

    issuer.apply_v1_1()

    assert (
        base.writer
        is writer
    )

    assert (
        base.RELEASE_LOCK_SCHEMA
        == issuer.RELEASE_LOCK_SCHEMA
    )

    assert (
        base.MANIFEST_SCHEMA
        == issuer.MANIFEST_SCHEMA
    )

    assert (
        base.COMPILER_SCHEMA
        == issuer.COMPILER_SCHEMA
    )

    assert (
        writer.LIVE_WRITER_CONNECTED
        is False
    )


def test_interim_lock_allows_check():

    issuer.require_action_allowed_by_lock(
        action=
            base.ACTION_CHECK,

        lock_body=
            interim_lock(),
    )


def test_interim_lock_blocks_preview():

    with pytest.raises(
        base.PermitIssuerStop,
        match="preview/issue is prohibited",
    ):

        issuer.require_action_allowed_by_lock(
            action=
                base.ACTION_PREVIEW,

            lock_body=
                interim_lock(),
        )


def test_interim_lock_blocks_issue():

    with pytest.raises(
        base.PermitIssuerStop,
        match="preview/issue is prohibited",
    ):

        issuer.require_action_allowed_by_lock(
            action=
                base.ACTION_ISSUE,

            lock_body=
                interim_lock(),
        )


def test_interim_lock_is_not_final_ready():

    assert (
        issuer.final_lock_is_ready(
            interim_lock()
        )
        is False
    )


def test_manifest_structural_proof_passes():

    assert (
        issuer.structural_proof_ok(
            safe_structure(
                schema=True
            ),
            require_schema=True,
        )
        is True
    )


def test_compiler_structural_proof_passes():

    assert (
        issuer.structural_proof_ok(
            safe_structure(
                schema=False
            ),
            require_schema=False,
        )
        is True
    )


def test_structural_proof_rejects_open_orders():

    structure = (
        safe_structure()
    )

    structure[
        "open_order_count"
    ] = 1

    assert (
        issuer.structural_proof_ok(
            structure,
            require_schema=True,
        )
        is False
    )


def test_structural_proof_rejects_unmanaged_positions():

    structure = (
        safe_structure()
    )

    structure[
        "no_unmanaged_positions_verified"
    ] = False

    assert (
        issuer.structural_proof_ok(
            structure,
            require_schema=True,
        )
        is False
    )


def test_manifest_and_compiler_structures_match():

    manifest = (
        safe_structure(
            schema=True
        )
    )

    compiler = (
        safe_structure(
            schema=False
        )
    )

    assert (
        issuer.structures_match(
            manifest,
            compiler,
        )
        is True
    )


def test_structure_change_is_detected():

    manifest = (
        safe_structure(
            schema=True
        )
    )

    compiler = (
        safe_structure(
            schema=False
        )
    )

    compiler[
        "position_count"
    ] = 3

    assert (
        issuer.structures_match(
            manifest,
            compiler,
        )
        is False
    )


def test_full_frozen_writer_universe_is_available():

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
        writer.ALLOWED_SYMBOLS
        == expected
    )

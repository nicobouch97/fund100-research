from __future__ import annotations

from decimal import Decimal

import pytest

import fund100_alpaca_live_permit_v2_issuer as issuer
import fund100_alpaca_live_writer_disconnected as writer


def fake_event():

    return {
        "state":
            {
                "last_date":
                    "2099-01-01",
            },

        "state_sha256":
            "state-hash",

        "manifest_package":
            {
                "manifest_id":
                    "manifest-test",
            },

        "manifest_sha256":
            "manifest-hash",

        "compiler_sha256":
            "compiler-hash",

        "compiler":
            {
                "market_snapshot_sha256":
                    "market-hash",
            },

        "candidate_symbols":
            [
                "ACWI",
                "EEM",
            ],

        "event_id":
            "f100-live-event-test",

        "event_binding_sha256":
            "event-binding-hash",
    }


def fake_lock():

    return {
        "release_lock_id":
            "f100-prelive-test",
    }


def fake_session():

    return {
        "session_binding_sha256":
            "session-hash",

        "candidate_expiry":
            "2099-01-01T16:00:00-05:00",
    }


def test_money_parser_accepts_cents():

    value = issuer.parse_money(
        "123.45",
        "test",
    )

    assert value == Decimal(
        "123.45"
    )


def test_money_parser_rejects_subcent():

    with pytest.raises(
        issuer.PermitIssuerStop,
        match="two decimals",
    ):

        issuer.parse_money(
            "1.001",
            "test",
        )


def test_approval_token_is_bound_to_cap():

    common = {
        "release_lock_id":
            "lock",

        "event_id":
            "event",

        "compiler_sha256":
            "compiler",

        "account_binding_sha256":
            "account",

        "candidate_expiry":
            "2099-01-01T16:00:00-05:00",
    }

    a = issuer.build_approval_token(
        **common,
        requested_cap=
            Decimal(
                "10.00"
            ),
    )

    b = issuer.build_approval_token(
        **common,
        requested_cap=
            Decimal(
                "11.00"
            ),
    )

    assert a != b


def test_issue_ledger_detects_duplicate_event():

    package = issuer.empty_issue_ledger()

    package = issuer.append_ledger_record(
        ledger_package=
            package,

        record={
            "event_id":
                "event-a",

            "permit_id":
                "permit-a",

            "permit_sha256":
                "hash",

            "source_compiler_sha256":
                "compiler",

            "issued_utc":
                "2099-01-01T00:00:00+00:00",
        },
    )

    assert issuer.event_already_permitted(
        ledger_package=
            package,

        event_id=
            "event-a",
    )

    assert not issuer.event_already_permitted(
        ledger_package=
            package,

        event_id=
            "event-b",
    )


def test_real_permit_is_writer_compatible_but_writer_stays_disconnected():

    permit_package = (
        issuer.build_real_permit(
            release_lock_body=
                fake_lock(),

            release_lock_sha256=
                "release-lock-hash",

            event=
                fake_event(),

            account_binding_sha256=
                "account-hash",

            session=
                fake_session(),

            requested_cap=
                Decimal(
                    "25.00"
                ),

            approval_token=
                "F100-APPROVE-test",

            previous_issue_ledger_sha256=
                "ledger-hash",
        )
    )

    permit, cap = (
        writer.validate_permit_package(
            permit_package
        )
    )

    assert (
        permit[
            "schema"
        ]
        == writer.REQUIRED_PERMIT_SCHEMA
    )

    assert (
        permit[
            "permit_issued"
        ]
        is True
    )

    assert (
        permit[
            "live_execution_authorized"
        ]
        is True
    )

    assert (
        permit[
            "network_write_capability"
        ]
        is True
    )

    assert (
        permit[
            "broker_write_mode"
        ]
        == "ENABLED"
    )

    assert cap == 25.0

    with pytest.raises(
        writer.LiveWriterDisconnected,
        match="LIVE WRITER DISCONNECTED",
    ):

        writer.require_adapter_connected()


def test_current_writer_remains_disconnected():

    assert (
        writer.LIVE_WRITER_CONNECTED
        is False
    )

    assert (
        issuer.writer_is_hard_disconnected()
        is True
    )

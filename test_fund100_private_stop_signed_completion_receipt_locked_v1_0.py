"""OFFLINE signed incident receipt: forged evidence never clears STOP journal."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import fund100_private_stop_controller_locked_v1_0 as ctl
import fund100_private_stop_signed_completion_receipt_locked_v1_0 as receipt

ACCOUNT_HASH = sha256(b"synthetic-account-not-from-broker").hexdigest()


@pytest.fixture
def stopped(monkeypatch, tmp_path):
    monkeypatch.setattr(ctl, "SOURCE_RELEASED", True)
    monkeypatch.setattr(ctl, "STOP_DISPATCH_RELEASED", True)
    monkeypatch.setattr(ctl, "JOURNAL_DIR", str(tmp_path))
    monkeypatch.setattr(ctl, "JOURNAL_PATH", str(tmp_path / "stop.sqlite"))
    monkeypatch.setattr(ctl.os.path, "ismount",
                        lambda path: path == str(tmp_path))
    monkeypatch.setenv("FUND100_STOP_CONTROLLER_MODE", "STOP_ONLY")
    monkeypatch.setenv("FUND100_GH_READ_TOKEN", "OFFLINE_READ_TOKEN_0123456789")
    monkeypatch.setenv("FUND100_GH_STOP_DISPATCH_TOKEN",
                       "OFFLINE_DIFFERENT_ACTIONS_TOKEN_0123456789")
    for name in ctl.BROKER_SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ctl, "_request",
                        lambda **kwargs: {
                            "workflow_run_id": 765432109,
                            "run_url": ctl.API + "/actions/runs/765432109",
                            "html_url": "https://github.com/" + ctl.REPO +
                                        "/actions/runs/765432109",
                        })
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    monkeypatch.setattr(receipt, "APPROVED_SIGNER_PUBLIC_KEY_HEX", public)
    monkeypatch.setattr(receipt, "EXPECTED_ACCOUNT_BINDING_SHA256",
                        ACCOUNT_HASH)
    assert ctl._dispatch_once(
        reason="STOP_LATCHES_WITHOUT_BROKER_CANCEL_PROOF",
    )["state"] == "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION"
    return private, tmp_path


def _sign(private, **change):
    ticket = ctl.read_original_dispatch_ticket()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = {
        "schema": receipt.SCHEMA,
        "repo": receipt.REPO,
        "alarm_key": ctl.ALARM_KEY,
        "alarm_detected_at_utc": ticket["alarm_detected_at_utc"],
        "dispatch_run_id": ticket["expected_dispatch_run_id"],
        "github_run_completed_at_utc": now,
        "stop_and_cancel_jobs_success": 3,
        "current_main_v5_stop": True,
        "current_main_v6_stop": True,
        "broker_observed_at_utc": now,
        "broker_fund100_open_orders": 0,
        "account_binding_sha256": ACCOUNT_HASH,
        "signed_at_utc": now,
        "trade_authorized": False,
        "fills_or_settlement_verified": False,
        "future_fill_absence_guaranteed": False,
    }
    r.update(change)
    sig = private.sign(receipt._canonical(r)).hex()
    return {"receipt": r, "ed25519_signature_hex": sig}


def _rows(folder):
    with sqlite3.connect(folder / "stop.sqlite") as db:
        first = db.execute(
            "SELECT state,dispatch_run_id FROM stop_attempts").fetchall()
        second = db.execute(
            "SELECT alarm_key,dispatch_run_id,receipt_sha256 "
            "FROM verified_stop_receipts").fetchall()
    return first, second


def test_unreleased_signer_untrusted_even_with_genuine_signature(stopped):
    private, folder = stopped
    assert receipt.SOURCE_RELEASED is False
    with pytest.raises(ctl.StopControllerHold, match="unavailable"):
        ctl.record_independently_signed_stop_completion(
            envelope=_sign(private))
    assert _rows(folder)[0] == [("ACK_ONLY_UNVERIFIED_STOP", 765432109)]
    assert _rows(folder)[1] == []


def test_authenticated_stop_stored_historically_only_no_rearm(
        stopped, monkeypatch):
    private, folder = stopped
    monkeypatch.setattr(receipt, "SOURCE_RELEASED", True)
    signed_original = _sign(private)
    out = ctl.record_independently_signed_stop_completion(
        envelope=signed_original)
    assert out == {
        "status": "HISTORICAL_STOP_SIGNED_AND_DURABLY_RECORDED",
        "dispatch_run_id": 765432109,
        "current_broker_risk_pass": False,
        "new_alarm_rearmed": False,
        "order_authorized": False,
    }
    initial, records = _rows(folder)
    assert initial == [("STOP_VERIFIED_HISTORICAL", 765432109)]
    assert len(records) == 1
    assert records[0][0:2] == (ctl.ALARM_KEY, 765432109)
    assert len(records[0][2]) == 64
    # The one-time incident is never reset for automatic new order release.
    monkeypatch.setattr(ctl, "_main_control", lambda path, *, token: (
        {"schema": "FUND100_OPERATOR_CONTROL_V1", "trading_enabled": False}
        if path == ctl.V5_PATH else
        {"schema": "FUND100_V6_S1_OPERATOR_CONTROL_V2",
         "risk_level": "HIGH", "pilot_capital_ceiling_usd": "130.30",
         "trading_enabled": False, "first_original_acwi_sell_enabled": False}
    ))
    result = ctl.once()
    assert result == {
        "state": "HISTORICAL_STOP_ONLY_FRESH_BROKER_RISK_REQUIRED",
        "stop_completed": False, "order_authorized": False}
    assert _rows(folder) == (initial, records)
    # A second signed receipt cannot overwrite original immutable evidence.
    with pytest.raises(ctl.StopControllerHold, match="unavailable"):
        ctl.record_independently_signed_stop_completion(
            envelope=signed_original)
    assert _rows(folder) == (initial, records)


@pytest.mark.parametrize("field,bad", [
    ("dispatch_run_id", 123),
    ("dispatch_run_id", True),
    ("repo", "other/other"),
    ("alarm_key", "REPLAYED_OTHER_ALARM"),
    ("alarm_detected_at_utc", "2026-01-01T00:00:00Z"),
    ("stop_and_cancel_jobs_success", 2),
    ("stop_and_cancel_jobs_success", True),
    ("current_main_v5_stop", False),
    ("current_main_v6_stop", "true"),
    ("broker_fund100_open_orders", 1),
    ("broker_fund100_open_orders", False),
    ("account_binding_sha256", "a" * 64),
    ("trade_authorized", True),
    ("fills_or_settlement_verified", True),
    ("future_fill_absence_guaranteed", True),
    ("schema", "FORGED_V2"),
    ("signed_at_utc", "2020-01-01T00:00:00Z"),
    ("broker_observed_at_utc", "2020-01-01T00:00:00Z"),
])
def test_signed_but_wrong_stop_or_broker_state_denied(
        stopped, monkeypatch, field, bad):
    private, folder = stopped
    monkeypatch.setattr(receipt, "SOURCE_RELEASED", True)
    with pytest.raises(ctl.StopControllerHold, match="unavailable"):
        ctl.record_independently_signed_stop_completion(
            envelope=_sign(private, **{field: bad}))
    assert _rows(folder) == ([("ACK_ONLY_UNVERIFIED_STOP", 765432109)], [])


def test_forged_signature_and_tampering_denied(stopped, monkeypatch):
    private, folder = stopped
    monkeypatch.setattr(receipt, "SOURCE_RELEASED", True)
    valid = _sign(private)
    invalid = copy.deepcopy(valid)
    invalid["ed25519_signature_hex"] = "00" * 64
    with pytest.raises(ctl.StopControllerHold, match="unavailable"):
        ctl.record_independently_signed_stop_completion(envelope=invalid)
    invalid = copy.deepcopy(valid)
    invalid["receipt"]["broker_fund100_open_orders"] = 1
    with pytest.raises(ctl.StopControllerHold, match="unavailable"):
        ctl.record_independently_signed_stop_completion(envelope=invalid)
    assert _rows(folder)[1] == []


def test_only_original_acknowledged_run_can_be_closed(stopped, monkeypatch):
    private, folder = stopped
    monkeypatch.setattr(receipt, "SOURCE_RELEASED", True)
    valid = _sign(private)
    with sqlite3.connect(folder / "stop.sqlite") as db:
        db.execute("UPDATE stop_attempts SET state='UNKNOWN_DISPATCH_OUTCOME'")
    with pytest.raises(ctl.StopControllerHold):
        ctl.record_independently_signed_stop_completion(envelope=valid)
    assert _rows(folder)[1] == []


def test_fresh_receipt_does_not_authorize_next_go(stopped, monkeypatch):
    private, folder = stopped
    monkeypatch.setattr(receipt, "SOURCE_RELEASED", True)
    ctl.record_independently_signed_stop_completion(envelope=_sign(private))
    monkeypatch.setattr(ctl, "_main_control", lambda path, *, token: (
        {"schema": "FUND100_OPERATOR_CONTROL_V1", "trading_enabled": False}
        if path == ctl.V5_PATH else
        {"schema": "FUND100_V6_S1_OPERATOR_CONTROL_V2",
         "risk_level": "HIGH", "pilot_capital_ceiling_usd": "130.30",
         "trading_enabled": True, "first_original_acwi_sell_enabled": True}
    ))
    with pytest.raises(ctl.StopControllerHold,
                       match="New GO/unknown after historical STOP"):
        ctl.once()
    assert _rows(folder)[0] == [("STOP_VERIFIED_HISTORICAL", 765432109)]


def test_verifier_import_is_inert_and_never_touches_broker():
    source = receipt.__file__
    text = open(source, encoding="utf-8").read()
    assert "SOURCE_RELEASED = False" in text
    assert "APPROVED_SIGNER_PUBLIC_KEY_HEX = None" in text
    assert "EXPECTED_ACCOUNT_BINDING_SHA256 = None" in text
    assert "NO_NETWORK = True" in text
    assert "NO_OPERATOR_REARM = True" in text
    assert "NO_ORDER_RELEASE = True" in text
    assert "api.alpaca.markets" not in text
    assert "urllib" not in text
    assert "def verify_signed_completion(" in text

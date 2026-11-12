"""Synthetic Ed25519 risk receipts; never a live Railway, Alpaca or order call."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as v

PRIVATE = Ed25519PrivateKey.generate()
PUB = PRIVATE.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
).hex()
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
SHA = "a" * 40
ACCOUNT = "b" * 64
POLICY = "c" * 64


def good_receipt():
    return {
        "schema": v.SCHEMA, "repo": v.REPO, "head_sha": SHA,
        "account_binding_sha256": ACCOUNT, "risk_policy_sha256": POLICY,
        "risk_outcome": v.EXPECTED_RISK_OUTCOME,
        "broker_get_count": 8, "broker_write_count": 0,
        "observed_start_utc": "2026-11-12T14:59:10Z",
        "broker_completed_utc": "2026-11-12T14:59:30Z",
        "signed_at_utc": "2026-11-12T14:59:31Z",
        "trade_authorized": False,
        "nonce": "d" * 64,
    }


def sign(r):
    return {"receipt": r, "ed25519_signature_hex":
            PRIVATE.sign(v._canonical(r)).hex()}


_UNSET = object()


def check(envelope=_UNSET, **kwargs):
    return v.verify_independent_risk_receipt(
        envelope=sign(good_receipt()) if envelope is _UNSET else envelope,
        expected_main_sha=kwargs.pop("main_sha", SHA),
        expected_account_binding_sha256=kwargs.pop("account", ACCOUNT),
        expected_risk_policy_sha256=kwargs.pop("policy", POLICY),
        now_utc=kwargs.pop("now", NOW),
    )


@pytest.fixture(autouse=True)
def pin_offline_fake_signer(monkeypatch):
    monkeypatch.setattr(v, "APPROVED_SIGNER_PUBLIC_KEY_HEX", PUB)


def test_source_is_hard_locked_with_no_signer_or_order():
    assert v.RECEIPT_VERIFICATION_RELEASED is False
    assert all((v.NO_NETWORK, v.NO_BROKER_ACCESS, v.NO_GITHUB_WRITES,
                v.NO_OPERATOR_WRITES, v.NO_TRADE_RELEASE))
    with pytest.raises(v.SignedRiskReceiptStop, match="HARD LOCKED"):
        check()


def test_valid_synthetic_signed_fresh_eight_get_pass_is_only_proof(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    assert check() is True
    assert v.NO_TRADE_RELEASE is True


@pytest.mark.parametrize("field,bad", [
    ("schema", "unknown"), ("repo", "someone/else"),
    ("head_sha", "e"*40), ("account_binding_sha256", "f"*64),
    ("risk_policy_sha256", "f"*64),
    ("risk_outcome", "ALREADY_STOPPED"), ("risk_outcome", "RISK_FAILURE"),
    ("broker_get_count", 7), ("broker_get_count", True),
    ("broker_write_count", 1), ("broker_write_count", False),
    ("trade_authorized", True), ("nonce", "bad"),
    ("observed_start_utc", "2026-11-12T14:58:00Z"),
    ("broker_completed_utc", "2026-11-12T14:58:30Z"),
    ("signed_at_utc", "2026-11-12T15:01:00Z"),
    ("broker_completed_utc", "invalid"),
])
def test_never_promote_invalid_or_mismatched_risk_report(monkeypatch, field, bad):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    receipt = good_receipt()
    receipt[field] = bad
    with pytest.raises(v.SignedRiskReceiptStop):
        check(sign(receipt))


def test_modified_signed_payload_or_signature_rejected(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    original = sign(good_receipt())
    tampered = deepcopy(original)
    tampered["receipt"]["nonce"] = "e"*64
    with pytest.raises(v.SignedRiskReceiptStop, match="signature"):
        check(tampered)
    badsig = deepcopy(original)
    badsig["ed25519_signature_hex"] = "f"*128
    with pytest.raises(v.SignedRiskReceiptStop, match="signature"):
        check(badsig)


@pytest.mark.parametrize("now", [
    NOW + timedelta(seconds=91),
    NOW - timedelta(minutes=2),
    datetime(2026, 11, 12, 15, 0),
])
def test_stale_future_or_naive_clock_rejected(monkeypatch, now):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    with pytest.raises(v.SignedRiskReceiptStop):
        check(now=now)


def test_exact_two_minute_completion_freshness_boundary(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    ended = datetime(2026,11,12,14,59,30,tzinfo=timezone.utc)
    assert check(now=ended+timedelta(seconds=120))
    with pytest.raises(v.SignedRiskReceiptStop, match="stale"):
        check(now=ended+timedelta(seconds=121))


def test_different_account_or_sha_or_policy_never_validates(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    for kwargs in (
        {"main_sha": "f"*40}, {"account": "f"*64},
        {"policy": "f"*64}, {"main_sha": "bad"},
        {"account": "bad"}, {"policy": "bad"},
    ):
        with pytest.raises(v.SignedRiskReceiptStop):
            check(**kwargs)


def test_missing_unknown_fields_or_bad_signature_shape_denied(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    for altered in (
        {}, None, [], {"receipt": good_receipt()},
        {"receipt": good_receipt(), "ed25519_signature_hex":"b"*127},
        {"receipt": good_receipt(), "ed25519_signature_hex":"b"*128, "extra":2},
    ):
        with pytest.raises(v.SignedRiskReceiptStop):
            check(altered)
    r = good_receipt()
    r["extra"] = "false"
    with pytest.raises(v.SignedRiskReceiptStop):
        check(sign(r))


def test_unknown_signer_is_not_independent_attestation(monkeypatch):
    monkeypatch.setattr(v, "RECEIPT_VERIFICATION_RELEASED", True)
    monkeypatch.setattr(v, "APPROVED_SIGNER_PUBLIC_KEY_HEX", None)
    with pytest.raises(v.SignedRiskReceiptStop, match="pin"):
        check()


def test_no_runtime_or_signing_private_key_in_code():
    src = Path(v.__file__).read_text()
    assert "RECEIPT_VERIFICATION_RELEASED = False" in src
    assert "APPROVED_SIGNER_PUBLIC_KEY_HEX = None" in src
    assert "Ed25519PrivateKey" not in src
    for forbidden in ("ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                      "urlopen(", "POST", "DELETE", "GITHUB_TOKEN"):
        assert forbidden not in src
    assert not Path(".github/workflows/fund100-v6-external-risk-receipt-live.yml").exists()

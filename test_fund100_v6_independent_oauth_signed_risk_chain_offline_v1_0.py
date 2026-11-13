"""One synthetic OAuth GET -> independent Ed25519 signer -> order receipt chain.

This cross-module integration exercises the ACTUAL read-only grant gate, eight
reviewed GET path, private risk witness contract, isolated signer cryptography
and final account/policy/main-bound verifier. It proves shape compatibility,
NOT true Alpaca token issuance, broker origin, protected isolation or live GO.

Every provider response and key here is synthetic, ephemeral, offline.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from test_fund100_v6_private_oauth_risk_witness_locked_v1_0 import (
    offline, capture, ACCOUNT, BINDING, POLICY, POLICY_SHA, MAIN, GRANT,
)

import fund100_v6_private_oauth_risk_witness_locked_v1_0 as observer
import fund100_v6_risk_receipt_signer_locked_v1_0 as signer
import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as verifier
import fund100_v6_s1_external_signed_risk_receipt_ingress_v1_0 as ingress

EXPECTED_PRIVATE_FIELDS = {
    "schema", "private_witness_not_signed", "checked", "account_id",
    "policy", "head_sha", "observed_start_utc", "broker_completed_utc",
    "trade_authorized", "broker_writes",
}


@pytest.fixture
def signed_offline(monkeypatch, offline):
    # Source separation: no signing key exists in the read-only broker
    # observer's process/environment. The synthetic OAuth token is checked
    # and exactly eight mocked Alpaca GET endpoints are touched.
    assert signer.KEY_ENV not in observer.os.environ
    private_witness = capture()
    assert len(offline) == 8
    assert set(private_witness) == EXPECTED_PRIVATE_FIELDS
    assert private_witness["private_witness_not_signed"] is True
    assert private_witness["trade_authorized"] is False
    assert private_witness["broker_writes"] == 0
    assert "ed25519_signature_hex" not in private_witness

    # Stage a DIFFERENT principal's environment. This is a mocked
    # compartment switch, not a claim of actual Railway isolation.
    signer_key = Ed25519PrivateKey.generate()
    privhex = signer_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    pubhex = signer_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    for key, val in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": signer.REPO,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_WORKFLOW_REF": signer.WATCH_REF,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": MAIN,
        "FUND100_RISK_LEVEL": "HIGH",
        "FUND100_ENABLE_LIVE_READONLY": "YES_READ_ONLY_LIVE",
        signer.KEY_ENV: privhex,
    }.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(signer, "SIGNER_SOURCE_RELEASED", True)
    monkeypatch.setattr(signer, "EXPECTED_ACCOUNT_BINDING_SHA256", BINDING)
    monkeypatch.setattr(signer, "EXPECTED_RISK_POLICY_SHA256", POLICY_SHA)
    monkeypatch.setattr(signer, "EXPECTED_SIGNER_PUBLIC_KEY_HEX", pubhex)
    monkeypatch.setattr(verifier, "RECEIPT_VERIFICATION_RELEASED", True)
    monkeypatch.setattr(verifier, "APPROVED_SIGNER_PUBLIC_KEY_HEX", pubhex)

    arguments = {
        "checked": private_witness["checked"],
        "account_id": private_witness["account_id"],
        "policy": private_witness["policy"],
        "head_sha": private_witness["head_sha"],
        "observed_start_utc": private_witness["observed_start_utc"],
        "broker_completed_utc": private_witness["broker_completed_utc"],
    }
    return private_witness, arguments, pubhex, privhex


def sign(arguments):
    return signer.sign_reviewed_eight_get_result(**arguments)


def verify(envelope, *, main=MAIN, account=BINDING, policy=POLICY_SHA,
           now=None):
    return verifier.verify_independent_risk_receipt(
        envelope=envelope, expected_main_sha=main,
        expected_account_binding_sha256=account,
        expected_risk_policy_sha256=policy, now_utc=now,
    )


def test_exact_private_oauth_eight_get_to_valid_signed_receipt(signed_offline):
    private, arguments, public, secret = signed_offline
    envelope = sign(arguments)
    assert verify(envelope) is True
    assert envelope["receipt"]["broker_get_count"] == 8
    assert envelope["receipt"]["broker_write_count"] == 0
    assert envelope["receipt"]["trade_authorized"] is False
    assert envelope["receipt"]["head_sha"] == MAIN
    assert envelope["receipt"]["account_binding_sha256"] == BINDING
    assert envelope["receipt"]["risk_policy_sha256"] == POLICY_SHA
    assert private["account_id"] == ACCOUNT
    assert secret not in str(envelope)
    assert ACCOUNT not in str(envelope)
    assert GRANT["access_token"] not in str(envelope)
    assert public not in str(private)


def test_independent_signer_key_cannot_be_colocated_with_oauth_reader(
        signed_offline):
    private, arguments, _, _ = signed_offline
    # Even if all other reader source checks remain test-released, putting
    # the signer key into that process makes the broker reader HOLD.
    with pytest.raises(observer.PrivateRiskWitnessHold, match="HARD LOCKED"):
        capture()
    # An already captured mock witness is not an order permit.
    assert private["trade_authorized"] is False
    assert ingress.RECEIPT_INGRESS_RELEASED is False


@pytest.mark.parametrize("field,bad", [
    ("account_id", "DIFFERENT-OWNER-ACCOUNT-999"),
    ("head_sha", "b"*40),
    ("policy", {"unapproved_policy": True}),
    ("checked", {}),
])
def test_signer_rejects_mutated_private_witness(
        signed_offline, field, bad):
    _, arguments, _, _ = signed_offline
    with pytest.raises(signer.RiskReceiptSignerStop):
        sign(dict(arguments, **{field: bad}))


@pytest.mark.parametrize("field,wrong", [
    ("head_sha", "c"*40),
    ("account_binding_sha256", "d"*64),
    ("risk_policy_sha256", "e"*64),
    ("broker_get_count", 7),
    ("broker_write_count", 1),
    ("trade_authorized", True),
    ("risk_outcome", "FAKE_GREEN"),
])
def test_synthetic_cryptographic_receipt_mutation_never_passes(
        signed_offline, field, wrong):
    _, arguments, _, _ = signed_offline
    envelope = sign(arguments)
    envelope["receipt"][field] = wrong
    with pytest.raises(verifier.SignedRiskReceiptStop):
        verify(envelope)


def test_expired_signed_receipt_cannot_enable_future_order(signed_offline):
    _, arguments, _, _ = signed_offline
    envelope = sign(arguments)
    signed_at = datetime.strptime(
        envelope["receipt"]["signed_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    with pytest.raises(verifier.SignedRiskReceiptStop, match="stale"):
        verify(envelope, now=signed_at + timedelta(seconds=121))


def test_different_actual_main_commit_requires_new_receipt(signed_offline):
    _, arguments, _, _ = signed_offline
    envelope = sign(arguments)
    with pytest.raises(verifier.SignedRiskReceiptStop):
        verify(envelope, main="f"*40)


def test_order_ingress_cannot_use_offline_receipt_without_live_source_release(
        signed_offline):
    _, arguments, _, _ = signed_offline
    envelope = sign(arguments)
    assert verify(envelope) is True
    assert ingress.RECEIPT_INGRESS_RELEASED is False
    assert ingress.EXPECTED_ACCOUNT_BINDING_SHA256 is None
    assert ingress.EXPECTED_RISK_POLICY_SHA256 is None


def test_offline_integration_never_changes_production_release_flags():
    observer_src = Path(observer.__file__).read_text()
    signer_src = Path(signer.__file__).read_text()
    verify_src = Path(verifier.__file__).read_text()
    ingress_src = Path(ingress.__file__).read_text()
    assert "SOURCE_RELEASED = False" in observer_src
    assert "SIGNER_SOURCE_RELEASED = False" in signer_src
    assert "RECEIPT_VERIFICATION_RELEASED = False" in verify_src
    assert "RECEIPT_INGRESS_RELEASED = False" in ingress_src
    assert "urlopen(" not in observer_src
    assert "NO_TRADE_RELEASE = True" in observer_src
    assert "NO_TRADE_RELEASE = True" in signer_src
    assert "NO_TRADE_RELEASE = True" in verify_src

"""Offline-only synthetic signing with ephemeral key, no Alpaca/GitHub network."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import fund100_v6_risk_receipt_signer_locked_v1_0 as signer
import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as verifier
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active

MAIN_SHA="a"*40
ACCOUNT_ID="synthetic-owner-account-0001"
POLICY={"fund100_policy":"original-high-6-20-35","cash_floor":0.05}
ACCOUNT_SHA=sha256(("FUND100-LIVE-ACCOUNT|"+ACCOUNT_ID).encode()).hexdigest()
POLICY_SHA=sha256(signer._canonical(POLICY)).hexdigest()


def verified_shape():
    return {
        "schema":active.SCHEMA,
        "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
        "same_process_real_broker_gets":8,
        "original_acwi_exact_fractional_holdings_verified":True,
        "original_strict_postfunding_6_20_35_risk_pass":True,
        "broker_post_attempts":0,
        "orders_submitted_here":0,
        "buy_authorized":False,
    }


@pytest.fixture
def reviewed_offline(monkeypatch):
    # All these flags/pins are hard-locked in the actual committed code.
    # This fixture NEVER modifies GitHub controls or receives live secrets.
    private=Ed25519PrivateKey.generate()
    key_hex=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()).hex()
    public=private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw).hex()
    for name,value in {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":signer.REPO,
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_EVENT_NAME":"schedule",
        "GITHUB_WORKFLOW_REF":signer.WATCH_REF,
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_SHA":MAIN_SHA,
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
        signer.KEY_ENV:key_hex,
    }.items():
        monkeypatch.setenv(name,value)
    monkeypatch.setattr(signer,"SIGNER_SOURCE_RELEASED",True)
    monkeypatch.setattr(signer,"EXPECTED_ACCOUNT_BINDING_SHA256",ACCOUNT_SHA)
    monkeypatch.setattr(signer,"EXPECTED_RISK_POLICY_SHA256",POLICY_SHA)
    monkeypatch.setattr(signer,"EXPECTED_SIGNER_PUBLIC_KEY_HEX",public)
    monkeypatch.setattr(verifier,"RECEIPT_VERIFICATION_RELEASED",True)
    monkeypatch.setattr(verifier,"APPROVED_SIGNER_PUBLIC_KEY_HEX",public)
    return key_hex,public


def now_times():
    signed=datetime.now(timezone.utc).replace(microsecond=0)
    start=signed-timedelta(seconds=10)
    completed=signed-timedelta(seconds=2)
    return tuple(x.strftime("%Y-%m-%dT%H:%M:%SZ")
                 for x in (start,completed,signed))


def proof_args(**overrides):
    start,completed,signed=now_times()
    kwargs={
        "checked":verified_shape(),
        "account_id":ACCOUNT_ID,
        "policy":POLICY,
        "head_sha":MAIN_SHA,
        "observed_start_utc":start,
        "broker_completed_utc":completed,
        "signed_at_utc":signed,
    }
    kwargs.update(overrides)
    return kwargs


def test_production_signer_refuses_before_loading_a_private_key(monkeypatch):
    assert signer.SIGNER_SOURCE_RELEASED is False
    assert signer.EXPECTED_ACCOUNT_BINDING_SHA256 is None
    assert signer.EXPECTED_RISK_POLICY_SHA256 is None
    assert signer.EXPECTED_SIGNER_PUBLIC_KEY_HEX is None
    assert all((signer.NO_NETWORK,signer.NO_BROKER_CREDENTIALS,
                signer.NO_GITHUB_WRITE,signer.NO_ORDER_WRITE,
                signer.NO_TRADE_RELEASE))
    with pytest.raises(signer.RiskReceiptSignerStop,match="HARD LOCKED"):
        signer.sign_reviewed_eight_get_result(**proof_args())


def test_ephemeral_signed_synthetic_eight_get_receipt_verifies_but_cannot_trade(
        reviewed_offline):
    key_hex,pub=reviewed_offline
    envelope=signer.sign_reviewed_eight_get_result(**proof_args())
    assert set(envelope)=={"receipt","ed25519_signature_hex"}
    r=envelope["receipt"]
    assert set(r)==verifier.RECEIPT_FIELDS
    assert r["broker_get_count"]==8 and r["broker_write_count"]==0
    assert r["trade_authorized"] is False
    assert r["account_binding_sha256"]==ACCOUNT_SHA
    assert r["risk_policy_sha256"]==POLICY_SHA
    assert ACCOUNT_ID not in str(envelope)
    assert key_hex not in str(envelope)
    assert verifier.verify_independent_risk_receipt(
        envelope=envelope,expected_main_sha=MAIN_SHA,
        expected_account_binding_sha256=ACCOUNT_SHA,
        expected_risk_policy_sha256=POLICY_SHA) is True


@pytest.mark.parametrize("field,bad",[
    ("schema","WRONG"),("status","HOLD"),
    ("same_process_real_broker_gets",7),
    ("same_process_real_broker_gets",True),
    ("original_acwi_exact_fractional_holdings_verified",False),
    ("original_strict_postfunding_6_20_35_risk_pass","true"),
    ("broker_post_attempts",1),
    ("broker_post_attempts",False),
    ("orders_submitted_here",2),("orders_submitted_here",False),
    ("buy_authorized",True),
])
def test_missing_or_malformed_broker_verdict_never_signs(
        reviewed_offline,field,bad):
    unsafe=verified_shape()
    unsafe[field]=bad
    with pytest.raises(signer.RiskReceiptSignerStop,match="eight-GET"):
        signer.sign_reviewed_eight_get_result(**proof_args(checked=unsafe))
    unsafe.pop(field)
    with pytest.raises(signer.RiskReceiptSignerStop,match="eight-GET"):
        signer.sign_reviewed_eight_get_result(**proof_args(checked=unsafe))


@pytest.mark.parametrize("change",[
    {"account_id":"fake-unapproved-account"},
    {"account_id":True},
    {"policy":{"cash_floor":0.01}},
    {"policy":{}},
    {"head_sha":"b"*40},
    {"head_sha":"a"*39},
])
def test_account_policy_main_identity_never_confused(reviewed_offline,change):
    with pytest.raises(signer.RiskReceiptSignerStop):
        signer.sign_reviewed_eight_get_result(**proof_args(**change))


@pytest.mark.parametrize("key,bad",[
    ("GITHUB_ACTIONS","false"),
    ("GITHUB_REPOSITORY","attacker/other"),
    ("GITHUB_REF","refs/heads/dev"),
    ("GITHUB_EVENT_NAME","workflow_dispatch"),
    ("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_WORKFLOW_REF","attacker/workflow@refs/heads/main"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_SHA","b"*40),
    ("FUND100_RISK_LEVEL","LOW"),
    ("FUND100_ENABLE_LIVE_READONLY","no"),
])
def test_wrong_signer_job_provenance_denied_before_crypto(
        reviewed_offline,monkeypatch,key,bad):
    monkeypatch.setenv(key,bad)
    with pytest.raises(signer.RiskReceiptSignerStop,match="HARD LOCKED"):
        signer.sign_reviewed_eight_get_result(**proof_args())


@pytest.mark.parametrize("off",[
    (-100,-95,-90),(-60,-5,0),(-3,-8,0),(-5,0,20),
    (-20,-6,-40),
])
def test_stale_reversed_or_future_evidence_refused(reviewed_offline,off):
    now=datetime.now(timezone.utc).replace(microsecond=0)
    start,complete,signed=(
        (now+timedelta(seconds=x)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for x in off)
    with pytest.raises(signer.RiskReceiptSignerStop):
        signer.sign_reviewed_eight_get_result(**proof_args(
            observed_start_utc=start,broker_completed_utc=complete,
            signed_at_utc=signed))


def test_signer_key_must_match_public_pin_and_never_equal_broker_secret(
        reviewed_offline,monkeypatch):
    key,pub=reviewed_offline
    monkeypatch.setattr(signer,"EXPECTED_SIGNER_PUBLIC_KEY_HEX","b"*64)
    with pytest.raises(signer.RiskReceiptSignerStop,match="signer identity"):
        signer.sign_reviewed_eight_get_result(**proof_args())
    monkeypatch.setattr(signer,"EXPECTED_SIGNER_PUBLIC_KEY_HEX",pub)
    monkeypatch.setenv("ALPACA_LIVE_SECRET",key)
    with pytest.raises(signer.RiskReceiptSignerStop,match="not isolated"):
        signer.sign_reviewed_eight_get_result(**proof_args())


def test_missing_or_noncanonical_signer_secret_denied(reviewed_offline,monkeypatch):
    for value in ("", "z"*64, "abcd", "0"*63):
        monkeypatch.setenv(signer.KEY_ENV,value)
        with pytest.raises(signer.RiskReceiptSignerStop,match="key unavailable"):
            signer.sign_reviewed_eight_get_result(**proof_args())


def test_signed_receipt_mutation_is_detected_by_existing_verifier(reviewed_offline):
    envelope=signer.sign_reviewed_eight_get_result(**proof_args())
    envelope["receipt"]["broker_get_count"]=1
    with pytest.raises(verifier.SignedRiskReceiptStop,match="risk report"):
        verifier.verify_independent_risk_receipt(
            envelope=envelope,expected_main_sha=MAIN_SHA,
            expected_account_binding_sha256=ACCOUNT_SHA,
            expected_risk_policy_sha256=POLICY_SHA)


def test_signing_module_is_nonnetworked_and_not_deployed():
    source=Path(signer.__file__).read_text()
    assert "SIGNER_SOURCE_RELEASED = False" in source
    assert "EXPECTED_SIGNER_PUBLIC_KEY_HEX = None" in source
    assert "EXPECTED_ACCOUNT_BINDING_SHA256 = None" in source
    assert "EXPECTED_RISK_POLICY_SHA256 = None" in source
    assert "from urllib" not in source
    assert "from requests" not in source
    assert 'method="POST"' not in source
    assert "api.alpaca.markets" not in source
    assert "paper-api.alpaca.markets" not in source
    assert "client_order_id" not in source
    assert "ALPACA_LIVE_KEY" in source  # only to reject credential reuse
    assert "NO_ORDER_WRITE = True" in source
    assert "NO_TRADE_RELEASE = True" in source
    docker=Path("Dockerfile").read_text()
    assert "fund100_v6_risk_receipt_signer_locked_v1_0.py" not in docker

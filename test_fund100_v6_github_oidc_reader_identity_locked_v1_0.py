"""Synthetic RSA JWT and trusted-JWKS tests only: no GitHub OIDC or Alpaca I/O."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import fund100_v6_github_oidc_reader_identity_locked_v1_0 as identity

SHA = "a" * 40
NOW = datetime(2026, 11, 13, 16, 10, tzinfo=timezone.utc)
UNIX = int(NOW.timestamp())
JTI = "synthetic-unique-jti-000001"


def encoded(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def key_number(value: int) -> str:
    return encoded(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def jwt_claims():
    return {
        "iss": identity.ISSUER, "aud": identity.AUDIENCE,
        "sub": identity.EXPECTED_SUBJECT,
        "repository": identity.REPO, "repository_id": identity.REPO_ID,
        "repository_owner_id": identity.OWNER_ID,
        "ref": "refs/heads/main", "ref_type": "branch",
        "sha": SHA, "workflow": identity.WORKFLOW_NAME,
        "workflow_ref": identity.WORKFLOW_REF, "workflow_sha": SHA,
        "event_name": "schedule", "environment": identity.ENVIRONMENT,
        "runner_environment": "github-hosted", "repository_visibility": "public",
        "run_id": "43457661311", "run_attempt": "1", "jti": JTI,
        "iat": UNIX - 5, "nbf": UNIX - 5, "exp": UNIX + 590,
    }


def sign(private_key, claims=None, header=None):
    headers = {"alg": "RS256", "typ": "JWT",
               "kid": "synthetic-pinned-github-jwk"}
    headers.update(header or {})
    head = encoded(json.dumps(headers, separators=(",", ":"), sort_keys=True).encode())
    body = encoded(json.dumps(claims or jwt_claims(),
                              separators=(",", ":"), sort_keys=True).encode())
    signing = (head + "." + body).encode("ascii")
    sig = private_key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return signing.decode() + "." + encoded(sig)


@pytest.fixture
def mock_valid_identity(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    trusted = {
        "keys": [{
            "kty": "RSA", "use": "sig", "alg": "RS256",
            "kid": "synthetic-pinned-github-jwk",
            "n": key_number(numbers.n), "e": key_number(numbers.e),
        }],
    }
    monkeypatch.setattr(identity, "OIDC_IDENTITY_SOURCE_RELEASED", True)
    monkeypatch.setattr(identity, "_now", lambda: NOW)
    monkeypatch.setattr(identity, "_fetch_github_oidc_keys",
                        lambda: trusted)
    return private, trusted


def check(token, main=SHA):
    return identity.verify_exact_scheduled_broker_reader_identity(
        token=token, expected_main_sha=main)


def test_production_contract_stays_unreleased_no_network_or_signer_key(
        monkeypatch):
    assert identity.OIDC_IDENTITY_SOURCE_RELEASED is False
    assert all((
        identity.NO_BROKER_CREDENTIALS,
        identity.NO_RISK_SIGNING_KEY,
        identity.NO_GITHUB_WRITES,
        identity.NO_BROKER_WRITES,
        identity.NO_ORDER_RELEASE,
        identity.NO_8GET_PROOF_FROM_JWT,
        identity.NO_DURABLE_REPLAY_STORE,
    ))
    monkeypatch.setattr(identity, "_fetch_github_oidc_keys",
                        lambda: pytest.fail("No OIDC fetch before release"))
    with pytest.raises(identity.BrokerWitnessIdentityStop, match="HARD LOCKED"):
        check("not-a-real-token")
    source = Path(identity.__file__).read_text()
    assert "https://api.alpaca.markets" not in source
    assert "SIGNER_SOURCE_RELEASED = True" not in source
    assert "NO_ORDER_RELEASE = True" in source


def test_valid_synthetic_github_signature_verifies_only_job_identity(
        mock_valid_identity):
    private, trusted = mock_valid_identity
    received = check(sign(private))
    assert received == {
        "schema": identity.SCHEMA,
        "status": "OIDC_JOB_IDENTITY_ONLY_NOT_BROKER_PROOF",
        "verified_main_sha": SHA,
        "verified_workflow_run_id": "43457661311",
        "verified_jwt_jti": JTI,
        "broker_eight_gets_proven": False,
        "broker_risk_pass_proven": False,
        "atomic_replay_ledger_required": True,
        "signing_key_access_granted": False,
        "trading_authorized": False,
    }
    assert private.private_numbers().d != 0
    assert identity.JWKS_URL == (
        "https://token.actions.githubusercontent.com/.well-known/jwks")


@pytest.mark.parametrize("field,bad", [
    ("iss", "https://attacker.invalid"),
    ("aud", "https://github.com/nicobouch97"),
    ("sub", "repo:nicobouch97/fund100-research:ref:refs/heads/main"),
    ("repository", "evil/forged"),
    ("repository_id", "00000"),
    ("repository_owner_id", "0"),
    ("workflow", "other"),
    ("workflow_ref", "evil/workflow@refs/heads/main"),
    ("workflow_sha", "b" * 40),
    ("event_name", "workflow_dispatch"),
    ("event_name", "pull_request"),
    ("ref", "refs/heads/dev"),
    ("ref_type", "tag"),
    ("sha", "b" * 40),
    ("environment", "development"),
    ("runner_environment", "self-hosted"),
    ("repository_visibility", "private"),
    ("run_attempt", "2"),
    ("run_attempt", True),
    ("run_id", "0"),
    ("jti", "short"),
])
def test_validly_signed_token_for_wrong_job_is_rejected(
        mock_valid_identity, field, bad):
    private, _ = mock_valid_identity
    payload = jwt_claims()
    payload[field] = bad
    with pytest.raises(identity.BrokerWitnessIdentityStop):
        check(sign(private, payload))


def test_wrong_expected_main_cannot_be_selected_by_remote_caller(
        mock_valid_identity):
    private, _ = mock_valid_identity
    with pytest.raises(identity.BrokerWitnessIdentityStop):
        check(sign(private), main="b" * 40)


@pytest.mark.parametrize("changes", [
    {"iat": UNIX - 130},
    {"iat": UNIX + 1},
    {"nbf": UNIX + 1},
    {"exp": UNIX - 1},
    {"iat": True},
    {"exp": "1763050000"},
    {"exp": UNIX + 601},
    {"iat": UNIX - 605},
])
def test_signed_stale_future_or_malformed_timestamps_are_denied(
        mock_valid_identity, changes):
    private, _ = mock_valid_identity
    claims = jwt_claims()
    claims.update(changes)
    with pytest.raises(identity.BrokerWitnessIdentityStop):
        check(sign(private, claims))


def test_modified_token_cannot_pass_issuer_signature(
        mock_valid_identity):
    private, _ = mock_valid_identity
    legit = sign(private)
    p = legit.split(".")
    forged = jwt_claims()
    forged["event_name"] = "workflow_dispatch"
    p[1] = encoded(json.dumps(forged).encode())
    with pytest.raises(identity.BrokerWitnessIdentityStop, match="signature"):
        check(".".join(p))


@pytest.mark.parametrize("bad_alg", ["none", "HS256", "RS512", "ES256"])
def test_algorithm_confusion_prevented(mock_valid_identity, bad_alg):
    private, _ = mock_valid_identity
    with pytest.raises(identity.BrokerWitnessIdentityStop, match="algorithm"):
        check(sign(private, header={"alg": bad_alg}))


def test_untrusted_or_duplicate_kid_cannot_admit_job(
        mock_valid_identity, monkeypatch):
    private, jwks = mock_valid_identity
    claims = sign(private)
    monkeypatch.setattr(identity, "_fetch_github_oidc_keys",
                        lambda: {"keys": []})
    with pytest.raises(identity.BrokerWitnessIdentityStop):
        check(claims)
    monkeypatch.setattr(identity, "_fetch_github_oidc_keys",
                        lambda: {"keys": jwks["keys"] * 2})
    with pytest.raises(identity.BrokerWitnessIdentityStop,
                       match="duplicate"):
        check(claims)


def test_verification_key_cannot_be_controlled_by_token_sender(
        mock_valid_identity, monkeypatch):
    private, _ = mock_valid_identity
    alternate = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = alternate.public_key().public_numbers()
    other_jwks = {"keys": [{
        "kty": "RSA", "use": "sig", "alg": "RS256",
        "kid": "synthetic-pinned-github-jwk",
        "n": key_number(numbers.n), "e": key_number(numbers.e),
    }]}
    monkeypatch.setattr(identity, "_fetch_github_oidc_keys",
                        lambda: other_jwks)
    with pytest.raises(identity.BrokerWitnessIdentityStop,
                       match="signature"):
        check(sign(private))


def test_jwks_transport_is_fixed_get_without_redirects(
        mock_valid_identity, monkeypatch):
    _, keys = mock_valid_identity

    class FakeResponse:
        status = 200

        def geturl(self):
            return identity.JWKS_URL

        def read(self, n):
            return json.dumps(keys).encode()[:n]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeOpener:
        def open(self, request, timeout):
            assert timeout == 5
            assert request.full_url == identity.JWKS_URL
            assert request.get_method() == "GET"
            return FakeResponse()

    def opener(handler):
        assert isinstance(handler, identity._NoRedirect)
        return FakeOpener()

    monkeypatch.setattr(identity, "build_opener", opener)
    assert identity._fetch_github_oidc_keys() == keys
    with pytest.raises(identity.BrokerWitnessIdentityStop,
                       match="redirected"):
        identity._NoRedirect().redirect_request(
            None, None, 302, "found", {},
            "https://forged.invalid/keys")

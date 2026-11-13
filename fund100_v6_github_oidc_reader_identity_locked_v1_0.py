"""Fail-closed GitHub OIDC IDENTITY verifier for a future isolated V6 signer.

Why: the genuine reviewed Alpaca eight-GET job and the Ed25519 signer must
NOT share a signing private key or broker credentials. GitHub-signed, very
short-lived OIDC identity can authenticate the EXACT scheduled protected
broker-reader job to an independent signer without a shared API secret.

STRICT LIMITATION: this verifies only GitHub's identity assertion for a job,
NOT that it performed any Alpaca GETs or reached a true risk PASS. The caller
must also verify original broker witness/policy, current main/STOP, and
atomically consume JWT jti using a durable external store. No such ingress,
replay cache, private signer or order authorizer is deployed by this module.

No broker credentials, network on import, trading write, signer secret,
GitHub write, risk PASS production release, or public Railway integration.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA = "FUND100_V6_S1_GITHUB_OIDC_READER_IDENTITY_V1"
OIDC_IDENTITY_SOURCE_RELEASED = False
NO_BROKER_CREDENTIALS = True
NO_RISK_SIGNING_KEY = True
NO_GITHUB_WRITES = True
NO_BROKER_WRITES = True
NO_ORDER_RELEASE = True
NO_8GET_PROOF_FROM_JWT = True
NO_DURABLE_REPLAY_STORE = True

REPO = "nicobouch97/fund100-research"
REPO_ID = "1374404370"
OWNER_ID = "312098945"
ENVIRONMENT = "fund100-live-broker"
WORKFLOW_REF = (
    REPO + "/.github/workflows/"
    "fund100-v6-s1-independent-risk-watch.yml@refs/heads/main"
)
WORKFLOW_NAME = "Fund-100 V6-S1 Independent First ACWI Risk Watch (NO TRADE)"
ISSUER = "https://token.actions.githubusercontent.com"
JWKS_URL = ISSUER + "/.well-known/jwks"
AUDIENCE = "fund100-v6-private-risk-signer-v1"
# This repository was created after the GitHub immutable subject rollout.
EXPECTED_SUBJECT = (
    "repo:nicobouch97@312098945/"
    "fund100-research@1374404370:environment:fund100-live-broker"
)
MAX_JWKS_BYTES = 65536
MAX_JWT_BYTES = 8192
MAX_TOKEN_AGE_SECONDS = 120
MAX_TOKEN_LIFETIME_SECONDS = 600
MAX_NBF_EARLY_SECONDS = 600  # GitHub may set nbf BEFORE iat


class BrokerWitnessIdentityStop(RuntimeError):
    """The remote worker identity cannot be admitted, even for risk checking."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BrokerWitnessIdentityStop("GitHub OIDC key endpoint redirected")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_part(encoded: str, *, max_bytes: int) -> dict:
    if (type(encoded) is not str or len(encoded) > max_bytes * 2
        or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None):
        raise BrokerWitnessIdentityStop("Invalid OIDC encoding")
    try:
        decoded = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4))
        if (len(decoded) > max_bytes
            or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != encoded):
            raise ValueError("Noncanonical encoding")
        obj = json.loads(decoded.decode("utf-8"))
        if type(obj) is not dict:
            raise ValueError("Invalid JSON shape")
        return obj
    except (ValueError, TypeError, UnicodeError):
        raise BrokerWitnessIdentityStop("Invalid OIDC JSON") from None


def _b64_int(encoded: object) -> int:
    if (type(encoded) is not str
        or not 1 <= len(encoded) <= 1400
        or re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None):
        raise BrokerWitnessIdentityStop("Invalid OIDC key encoding")
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    if not raw or raw[0] == 0 or base64.urlsafe_b64encode(
            raw).decode().rstrip("=") != encoded:
        raise BrokerWitnessIdentityStop("Noncanonical OIDC RSA key")
    return int.from_bytes(raw, "big")


def _fetch_github_oidc_keys() -> dict:
    """Only the GitHub issuer's fixed HTTPS JWKS; never caller-supplied URL."""
    req = Request(JWKS_URL, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "fund100-v6-oidc-provenance-locked",
        "Cache-Control": "no-store",
    })
    try:
        with build_opener(_NoRedirect()).open(req, timeout=5) as response:
            if response.status != 200 or response.geturl() != JWKS_URL:
                raise BrokerWitnessIdentityStop("GitHub OIDC key origin/status invalid")
            data = response.read(MAX_JWKS_BYTES + 1)
        if len(data) > MAX_JWKS_BYTES:
            raise BrokerWitnessIdentityStop("OIDC key set too large")
        result = json.loads(data.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError,
            ValueError, TypeError, UnicodeError):
        raise BrokerWitnessIdentityStop("Trusted GitHub OIDC keys unavailable") from None
    if (type(result) is not dict
        or set(result) != {"keys"}
        or type(result["keys"]) is not list
        or not 1 <= len(result["keys"]) <= 30):
        raise BrokerWitnessIdentityStop("Untrusted GitHub OIDC key set")
    return result


def _verify_rsa_signature(token: str, pieces: list[str],
                          header: dict, jwks: dict) -> None:
    kid = header["kid"]
    matches = [k for k in jwks["keys"]
               if type(k) is dict and k.get("kid") == kid]
    if len(matches) != 1:
        raise BrokerWitnessIdentityStop("Unknown or duplicate OIDC key")
    key = matches[0]
    if (key.get("kty") != "RSA" or key.get("use") != "sig"
        or key.get("alg") != "RS256"
        or ("key_ops" in key and key["key_ops"] != ["verify"])):
        raise BrokerWitnessIdentityStop("OIDC key is not RSA verify-only")
    n, exponent = _b64_int(key.get("n")), _b64_int(key.get("e"))
    if not 2048 <= n.bit_length() <= 8192 or exponent != 65537:
        raise BrokerWitnessIdentityStop("Unsafe OIDC verification public key")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
        signature = base64.urlsafe_b64decode(
            pieces[2] + "=" * (-len(pieces[2]) % 4))
        if base64.urlsafe_b64encode(signature).decode().rstrip("=") != pieces[2]:
            raise ValueError("Noncanonical signature")
        RSAPublicNumbers(exponent, n).public_key().verify(
            signature, (pieces[0] + "." + pieces[1]).encode("ascii"),
            padding.PKCS1v15(), hashes.SHA256())
    except (ImportError, ValueError, TypeError, InvalidSignature, OverflowError):
        raise BrokerWitnessIdentityStop("OIDC issuer signature invalid") from None


def verify_exact_scheduled_broker_reader_identity(
        *, token: object, expected_main_sha: object) -> dict:
    """Authenticates GitHub job ID only; never asserts broker risk, trade or STOP.

    This source deliberately does NOT accept a caller-supplied JWKS endpoint,
    crypto public key, clock, or test transport. If released later, an isolated
    external signer must independently obtain trusted current-main SHA,
    single-use durable jti, fixed environment/workflow, and reviewed witness.
    """
    if OIDC_IDENTITY_SOURCE_RELEASED is not True:
        raise BrokerWitnessIdentityStop("External OIDC identity source HARD LOCKED")
    if not all((NO_BROKER_CREDENTIALS, NO_RISK_SIGNING_KEY,
                NO_GITHUB_WRITES, NO_BROKER_WRITES, NO_ORDER_RELEASE,
                NO_8GET_PROOF_FROM_JWT, NO_DURABLE_REPLAY_STORE)):
        raise BrokerWitnessIdentityStop("OIDC boundary modified")
    if (type(expected_main_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}", expected_main_sha) is None
        or type(token) is not str or len(token) > MAX_JWT_BYTES
        or len(token.split(".")) != 3):
        raise BrokerWitnessIdentityStop("OIDC token/main SHA invalid")
    pieces = token.split(".")
    header = _json_part(pieces[0], max_bytes=1024)
    payload = _json_part(pieces[1], max_bytes=4096)
    if (header.get("typ") != "JWT" or header.get("alg") != "RS256"
        or type(header.get("kid")) is not str
        or re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", header["kid"]) is None
        or re.fullmatch(r"[A-Za-z0-9_-]+", pieces[2]) is None):
        raise BrokerWitnessIdentityStop("Unsupported OIDC JWT algorithm/header")
    # Only verified GitHub-issued public keys fetched through pinned TLS host.
    jwks = _fetch_github_oidc_keys()
    _verify_rsa_signature(token, pieces, header, jwks)
    exact_claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": EXPECTED_SUBJECT,
        "repository": REPO,
        "repository_id": REPO_ID,
        "repository_owner_id": OWNER_ID,
        "ref": "refs/heads/main",
        "ref_type": "branch",
        "sha": expected_main_sha,
        "workflow": WORKFLOW_NAME,
        "workflow_ref": WORKFLOW_REF,
        "workflow_sha": expected_main_sha,
        "event_name": "schedule",
        "environment": ENVIRONMENT,
        "runner_environment": "github-hosted",
        "repository_visibility": "public",
    }
    if any(payload.get(k) != v for k, v in exact_claims.items()):
        raise BrokerWitnessIdentityStop("OIDC job/repo/ref/actor context untrusted")
    attempt = payload.get("run_attempt")
    if not ((type(attempt) is str and attempt == "1")
            or (type(attempt) is int and attempt == 1)):
        raise BrokerWitnessIdentityStop("Retry/malformed OIDC job attempt")
    run_id = payload.get("run_id")
    jti = payload.get("jti")
    if (type(run_id) is not str
        or re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is None
        or type(jti) is not str
        or re.fullmatch(r"[A-Za-z0-9_.:-]{16,256}", jti) is None):
        raise BrokerWitnessIdentityStop("OIDC run identity unavailable")
    iat, nbf, exp = (payload.get("iat"), payload.get("nbf"),
                     payload.get("exp"))
    if (any(type(v) is not int for v in (iat, nbf, exp))
        or not iat - MAX_NBF_EARLY_SECONDS <= nbf <= iat <= exp
        or not 1 <= exp - iat <= MAX_TOKEN_LIFETIME_SECONDS):
        raise BrokerWitnessIdentityStop("OIDC token time claims invalid")
    now = _now()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise BrokerWitnessIdentityStop("OIDC verifier clock unavailable")
    seconds = now.astimezone(timezone.utc).timestamp()
    if (not iat <= seconds <= exp
        or nbf > seconds
        or seconds - iat > MAX_TOKEN_AGE_SECONDS):
        raise BrokerWitnessIdentityStop("Expired, future or replayable OIDC token")
    return {
        "schema": SCHEMA,
        "status": "OIDC_JOB_IDENTITY_ONLY_NOT_BROKER_PROOF",
        "verified_main_sha": expected_main_sha,
        "verified_workflow_run_id": run_id,
        "verified_jwt_jti": jti,
        "broker_eight_gets_proven": False,
        "broker_risk_pass_proven": False,
        "atomic_replay_ledger_required": True,
        "signing_key_access_granted": False,
        "trading_authorized": False,
    }

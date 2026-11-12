"""V6-S1 independent external risk receipt: STRICT offline verifier, not a trade GO.

Only a separately deployed, read-only broker-risk checker with an isolated
Ed25519 signing key may eventually sign a PASS. This code has no network,
broker credentials, secret key, GitHub writes, operator control or order I/O.
Failure, stale/missing evidence or unavailable cryptography means STOP.
Source and public-key pins remain unset until an independent runtime has
been proven and separately reviewed; no production entrypoint imports this.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

SCHEMA = "FUND100_V6_S1_EXTERNAL_EIGHT_GET_RISK_RECEIPT_V1"
REPO = "nicobouch97/fund100-research"
EXPECTED_RISK_OUTCOME = "WITHIN_V6_S1_ORIGINAL_ACWI_RISK_LIMITS"
RECEIPT_VERIFICATION_RELEASED = False
APPROVED_SIGNER_PUBLIC_KEY_HEX = None
MAX_RECEIPT_AGE_SECONDS = 120
MAX_BROKER_SNAPSHOT_SECONDS = 45
MAX_SIGN_DELAY_SECONDS = 15
NO_NETWORK = True
NO_BROKER_ACCESS = True
NO_GITHUB_WRITES = True
NO_OPERATOR_WRITES = True
NO_TRADE_RELEASE = True
RECEIPT_FIELDS = frozenset((
    "schema", "repo", "head_sha", "account_binding_sha256",
    "risk_policy_sha256", "risk_outcome", "broker_get_count",
    "broker_write_count", "observed_start_utc", "broker_completed_utc",
    "signed_at_utc", "trade_authorized", "nonce",
))


class SignedRiskReceiptStop(RuntimeError):
    pass


def _utc(value: object) -> datetime:
    if (type(value) is not str
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None):
        raise SignedRiskReceiptStop("Noncanonical independent receipt time")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise SignedRiskReceiptStop("Invalid independent receipt time") from None


def _sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _canonical(payload: dict) -> bytes:
    # Any non-JSON or noncanonical shape is rejected BEFORE signing checks.
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise SignedRiskReceiptStop("Invalid independent signed payload") from None


def verify_independent_risk_receipt(*, envelope: object,
                                    expected_main_sha: str,
                                    expected_account_binding_sha256: str,
                                    expected_risk_policy_sha256: str,
                                    now_utc: datetime | None = None) -> bool:
    """Fail-closed *proof verifier*, never a standalone order authorization.

    Current broker/STOP/cash/signed-ledger checks must still run at order time.
    This source does not fetch a receipt or provide a network transport.
    """
    if RECEIPT_VERIFICATION_RELEASED is not True:
        raise SignedRiskReceiptStop("Independent receipt source HARD LOCKED")
    pubkey = APPROVED_SIGNER_PUBLIC_KEY_HEX
    if (type(pubkey) is not str
        or re.fullmatch(r"[0-9a-f]{64}", pubkey) is None
        or type(expected_main_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}", expected_main_sha) is None
        or not _sha(expected_account_binding_sha256)
        or not _sha(expected_risk_policy_sha256)):
        raise SignedRiskReceiptStop("Signer/main/account/policy pin absent")
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise SignedRiskReceiptStop("Receipt verifier clock invalid")
    now = now.astimezone(timezone.utc)
    if (type(envelope) is not dict
        or set(envelope) != {"receipt", "ed25519_signature_hex"}
        or type(envelope["receipt"]) is not dict
        or set(envelope["receipt"]) != RECEIPT_FIELDS
        or type(envelope["ed25519_signature_hex"]) is not str
        or re.fullmatch(r"[0-9a-f]{128}",
                        envelope["ed25519_signature_hex"]) is None):
        raise SignedRiskReceiptStop("Untrusted independent receipt envelope")
    r = envelope["receipt"]
    if (r["schema"] != SCHEMA or r["repo"] != REPO
        or r["head_sha"] != expected_main_sha
        or r["account_binding_sha256"] != expected_account_binding_sha256
        or r["risk_policy_sha256"] != expected_risk_policy_sha256
        or r["risk_outcome"] != EXPECTED_RISK_OUTCOME
        or type(r["broker_get_count"]) is not int
        or r["broker_get_count"] != 8
        or type(r["broker_write_count"]) is not int
        or r["broker_write_count"] != 0
        or r["trade_authorized"] is not False
        or type(r["nonce"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", r["nonce"]) is None):
        raise SignedRiskReceiptStop("Independent broker-risk report not PASS")
    begin, completed, signed = (
        _utc(r["observed_start_utc"]),
        _utc(r["broker_completed_utc"]),
        _utc(r["signed_at_utc"]),
    )
    if (not begin <= completed <= signed <= now
        or (completed - begin).total_seconds() > MAX_BROKER_SNAPSHOT_SECONDS
        or (signed - completed).total_seconds() > MAX_SIGN_DELAY_SECONDS
        or (now - completed).total_seconds() > MAX_RECEIPT_AGE_SECONDS):
        raise SignedRiskReceiptStop("Independent broker evidence stale/delayed")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey)
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        raise SignedRiskReceiptStop("Independent cryptographic verification unavailable") from None
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey)).verify(
            bytes.fromhex(envelope["ed25519_signature_hex"]), _canonical(r))
    except (InvalidSignature, ValueError, TypeError):
        raise SignedRiskReceiptStop("Independent receipt signature invalid") from None
    return True

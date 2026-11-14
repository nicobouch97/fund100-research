"""Private STOP incident closure receipt: LOCKED independent Ed25519 verifier.

Only a separately isolated GET-only broker/GitHub witness may eventually sign
an authenticated completed-STOP receipt. This verification module has no
network, issuer credentials, GitHub token, STOP dispatch, trading or rearm.

A green GitHub workflow run alone is NOT signed broker observation.
Receipt source identity, approved account binding and signer's actual
isolation MUST be reviewed before unlocking either pin or source. Even a
valid receipt proves only historical open-order absence, not zero fills,
future fills, fresh ongoing risk safety or trading permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re

SCHEMA = "FUND100_PRIVATE_STOP_COMPLETION_RECEIPT_V1"
REPO = "nicobouch97/fund100-research"
SOURCE_RELEASED = False
APPROVED_SIGNER_PUBLIC_KEY_HEX = None
EXPECTED_ACCOUNT_BINDING_SHA256 = None
NO_NETWORK = True
NO_BROKER_CREDENTIALS = True
NO_GITHUB_CREDENTIALS = True
NO_STOP_DISPATCH = True
NO_ORDER_RELEASE = True
NO_OPERATOR_REARM = True
NO_FILLS_OR_FUTURE_SAFETY_CLAIM = True
MAX_INCIDENT_SECONDS = 240
MAX_RECEIPT_AGE_SECONDS = 30
MAX_BROKER_OBSERVATION_AGE_AT_SIGN_SECONDS = 20
RECEIPT_FIELDS = frozenset((
    "schema", "repo", "alarm_key", "alarm_detected_at_utc",
    "dispatch_run_id", "github_run_completed_at_utc",
    "stop_and_cancel_jobs_success", "current_main_v5_stop",
    "current_main_v6_stop", "broker_observed_at_utc",
    "broker_fund100_open_orders", "account_binding_sha256",
    "signed_at_utc", "trade_authorized",
    "fills_or_settlement_verified", "future_fill_absence_guaranteed",
))
ENVELOPE_FIELDS = frozenset(("receipt", "ed25519_signature_hex"))


class ReceiptNotVerified(RuntimeError):
    pass


def _utc(value: object) -> datetime:
    if type(value) is not str or re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is None:
        raise ReceiptNotVerified("Noncanonical STOP evidence UTC")
    try:
        t = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise ReceiptNotVerified("Invalid STOP evidence UTC") from None
    if t.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ReceiptNotVerified("Noncanonical STOP evidence UTC")
    return t


def _hash(value: object, size: int) -> bool:
    return (type(value) is str
            and re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", value) is not None)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise ReceiptNotVerified("Noncanonical STOP receipt") from None


def verify_signed_completion(
        *, envelope: object, alarm_key: str,
        expected_dispatch_run_id: int, alarm_detected_at_utc: str,
        now_utc: datetime | None = None) -> dict:
    """Validate independent signed historical evidence (NOT current GO).

    Expected incident fields must come from the *durable local journal*, not
    from the caller's envelope. This function does not fetch or generate
    broker data and cannot convert an untrusted caller dictionary into proof.
    """
    if (SOURCE_RELEASED is not True
        or not all((NO_NETWORK, NO_BROKER_CREDENTIALS,
                    NO_GITHUB_CREDENTIALS, NO_STOP_DISPATCH,
                    NO_ORDER_RELEASE, NO_OPERATOR_REARM,
                    NO_FILLS_OR_FUTURE_SAFETY_CLAIM))
        or not _hash(APPROVED_SIGNER_PUBLIC_KEY_HEX, 64)
        or not _hash(EXPECTED_ACCOUNT_BINDING_SHA256, 64)):
        raise ReceiptNotVerified("STOP receipt verifier HARD LOCKED")
    if (type(expected_dispatch_run_id) is not int
        or not 0 < expected_dispatch_run_id < 10**20
        or type(alarm_key) is not str
        or alarm_key != "FUND100_FIRST_UNVERIFIED_GO_OR_UNAVAILABLE_CONTROLS"):
        raise ReceiptNotVerified("Untrusted original STOP incident identity")
    alarm = _utc(alarm_detected_at_utc)
    if (type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS
        or type(envelope.get("receipt")) is not dict
        or set(envelope["receipt"]) != RECEIPT_FIELDS
        or not _hash(envelope.get("ed25519_signature_hex"), 128)):
        raise ReceiptNotVerified("Unknown signed STOP receipt format")
    r = envelope["receipt"]
    if (r.get("schema") != SCHEMA or r.get("repo") != REPO
        or r.get("alarm_key") != alarm_key
        or r.get("alarm_detected_at_utc") != alarm_detected_at_utc
        or type(r.get("dispatch_run_id")) is not int
        or r["dispatch_run_id"] != expected_dispatch_run_id
        or type(r.get("stop_and_cancel_jobs_success")) is not int
        or r["stop_and_cancel_jobs_success"] != 3
        or r.get("current_main_v5_stop") is not True
        or r.get("current_main_v6_stop") is not True
        or type(r.get("broker_fund100_open_orders")) is not int
        or r["broker_fund100_open_orders"] != 0
        or r.get("account_binding_sha256") !=
            EXPECTED_ACCOUNT_BINDING_SHA256
        or r.get("trade_authorized") is not False
        or r.get("fills_or_settlement_verified") is not False
        or r.get("future_fill_absence_guaranteed") is not False):
        raise ReceiptNotVerified("STOP receipt does not prove exact incident")
    finished = _utc(r["github_run_completed_at_utc"])
    observed = _utc(r["broker_observed_at_utc"])
    signed = _utc(r["signed_at_utc"])
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ReceiptNotVerified("Receipt verifier UTC clock unavailable")
    now = now.astimezone(timezone.utc)
    if (not alarm <= finished <= observed <= signed <= now
        or (finished - alarm).total_seconds() > MAX_INCIDENT_SECONDS
        or (signed - alarm).total_seconds() > MAX_INCIDENT_SECONDS
        or (signed - observed).total_seconds() >
             MAX_BROKER_OBSERVATION_AGE_AT_SIGN_SECONDS
        or (now - signed).total_seconds() > MAX_RECEIPT_AGE_SECONDS):
        raise ReceiptNotVerified("STOP evidence not bound to fresh incident")
    canonical = _canonical(r)
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey)
        from cryptography.exceptions import InvalidSignature
        verifier = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(APPROVED_SIGNER_PUBLIC_KEY_HEX))
        verifier.verify(bytes.fromhex(envelope["ed25519_signature_hex"]),
                        canonical)
    except (ImportError, ValueError, InvalidSignature):
        raise ReceiptNotVerified(
            "STOP signer public identity/signature unverified") from None
    return {
        "schema": SCHEMA,
        "status": "VERIFIED_HISTORICAL_STOP_NO_CURRENT_RISK_PASS",
        "receipt_sha256": sha256(canonical).hexdigest(),
        "dispatch_run_id": expected_dispatch_run_id,
        "verified_at_utc": r["signed_at_utc"],
        "new_orders_authorized": False,
        "new_alarm_rearm_authorized": False,
        "broker_fills_verified": False,
    }

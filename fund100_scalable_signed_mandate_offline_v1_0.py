"""Research-only signed draft of a future standing capital mandate.

A valid MAC proves only integrity under the supplied synthetic key, NOT
owner approval, production key custody or an independently anchored mandate.
No future cap can become LIVE merely because it is HMAC-signed here.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
import hmac
import json
import re

SCHEMA = "FUND100_SCALABLE_STANDING_MANDATE_DRAFT_V1"
MODE = "SYNTHETIC_UNSIGNED_OWNER_AUTHORITY_NEVER_LIVE"
DOMAIN = b"fund100-scalable-capital-offline-mandate-v1\x00"
ZERO_PARENT = "0" * 64
ORIGINAL_CAP = Decimal("130.30")
MAX_DRAFT_USD = Decimal("100000000.00")
MAX_BODY_BYTES = 4096
LIVE_MANDATE_RELEASED = False
NO_BROKER_TRANSPORT = NO_PRIVATE_STATE_WRITES = True

PAYLOAD_FIELDS = frozenset({
    "schema", "mode", "status", "revision", "previous_document_sha256",
    "account_binding_sha256", "capital_ceiling_usd", "currency",
    "risk_tiers", "additional_deposits_within_cap_allowed",
    "issued_utc", "expires_utc", "owner_approval_evidence",
    "broker_kill_switch", "operator_trading_enabled",
})


class MandateStop(ValueError):
    pass


def _key(raw):
    if type(raw) is not bytes or len(raw) < 32:
        raise MandateStop("Missing independent synthetic fixture signing key")
    return raw


def _hex(raw):
    if type(raw) is not str or re.fullmatch(r"[a-f0-9]{64}", raw) is None:
        raise MandateStop("Malformed digest")
    return raw


def _usd(raw):
    if type(raw) is not str or re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]{2})", raw) is None:
        raise MandateStop("Noncanonical USD mandate bound")
    val = Decimal(raw)
    if not (Decimal(0) < val <= MAX_DRAFT_USD):
        raise MandateStop("Draft mandate cap outside research bounds")
    return val


def _utc(raw):
    if type(raw) is not str or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None:
        raise MandateStop("Noncanonical UTC clock")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise MandateStop("Invalid UTC clock") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise MandateStop("Noncanonical UTC clock")
    return parsed


def _json_unique(pairs):
    doc = {}
    for key, value in pairs:
        if key in doc:
            raise MandateStop("Duplicate signed document key")
        doc[key] = value
    return doc


def _canon(doc):
    try:
        return json.dumps(doc, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise MandateStop("Malformed signed document") from None


def _seal(payload, key):
    return hmac.new(_key(key), DOMAIN + _canon(payload), sha256).hexdigest()


def _validate(payload, *, account_binding, expected_revision,
              expected_parent, now):
    if type(payload) is not dict or set(payload) != PAYLOAD_FIELDS:
        raise MandateStop("Draft schema or shape changed")
    if (payload["schema"] != SCHEMA
        or payload["mode"] != MODE
        or payload["status"] != "DRAFT_NOT_OWNER_AUTHORISED"
        or payload["owner_approval_evidence"] is not None
        or payload["broker_kill_switch"] != "ENGAGED"
        or payload["operator_trading_enabled"] is not False
        or payload["currency"] != "USD"
        or payload["additional_deposits_within_cap_allowed"] is not True):
        raise MandateStop("Signed draft is not a stopped, unapproved USD proposal")
    if (type(expected_revision) is not int or not 1 <= expected_revision <= 1000
        or type(payload["revision"]) is not int
        or payload["revision"] != expected_revision
        or payload["previous_document_sha256"] != _hex(expected_parent)
        or payload["account_binding_sha256"] != _hex(account_binding)):
        raise MandateStop("Stale/rolled back or wrong-account signed draft")
    if (expected_revision == 1 and expected_parent != ZERO_PARENT
        or expected_revision > 1 and expected_parent == ZERO_PARENT):
        raise MandateStop("Improper parent digest chain")
    if (type(payload["risk_tiers"]) is not list
        or payload["risk_tiers"] != ["LOW", "MEDIUM", "HIGH"]):
        raise MandateStop("Unreviewed draft risk-tier change")
    ceiling = _usd(payload["capital_ceiling_usd"])
    if type(now) is not str:
        raise MandateStop("Observation timestamp absent")
    issued = _utc(payload["issued_utc"])
    expiry = _utc(payload["expires_utc"])
    current = _utc(now)
    if not issued <= current < expiry or expiry - issued > timedelta(days=366):
        raise MandateStop("Draft expired, future dated or unbounded")
    return ceiling


def sign_synthetic_draft(*, account_binding, capital_ceiling_usd, revision,
                         previous_digest, issued_utc, expires_utc, key):
    """Build only a signed *unapproved* research fixture; never a release."""
    payload = {
        "schema": SCHEMA, "mode": MODE,
        "status": "DRAFT_NOT_OWNER_AUTHORISED",
        "revision": revision,
        "previous_document_sha256": previous_digest,
        "account_binding_sha256": account_binding,
        "capital_ceiling_usd": capital_ceiling_usd, "currency": "USD",
        "risk_tiers": ["LOW", "MEDIUM", "HIGH"],
        "additional_deposits_within_cap_allowed": True,
        "issued_utc": issued_utc, "expires_utc": expires_utc,
        "owner_approval_evidence": None,
        "broker_kill_switch": "ENGAGED",
        "operator_trading_enabled": False,
    }
    _validate(payload, account_binding=account_binding,
              expected_revision=revision, expected_parent=previous_digest,
              now=issued_utc)
    return _canon(dict(payload, mac=_seal(payload, key)))


def verify_synthetic_draft(*, raw, account_binding, expected_revision,
                           expected_parent, observed_utc, key):
    """MAC plus strict ancestry/source shapes, STILL NOT trading authority."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BODY_BYTES:
        raise MandateStop("Missing or oversized draft")
    try:
        doc = json.loads(raw.decode("utf8"), object_pairs_hook=_json_unique)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise MandateStop("Unreadable draft document") from None
    if type(doc) is not dict or set(doc) != PAYLOAD_FIELDS | {"mac"}:
        raise MandateStop("Signed draft keys changed")
    mac = doc.pop("mac")
    if type(mac) is not str or re.fullmatch(r"[a-f0-9]{64}", mac) is None:
        raise MandateStop("Missing signed draft MAC")
    if not hmac.compare_digest(mac, _seal(doc, key)):
        raise MandateStop("Draft integrity check failed")
    cap = _validate(doc, account_binding=account_binding,
                    expected_revision=expected_revision,
                    expected_parent=expected_parent,
                    now=observed_utc)
    return {
        "stage": "INTEGRITY_VERIFIED_UNAPPROVED_DRAFT_ONLY",
        "draft_capital_ceiling_usd": cap,
        "synthetic_document_sha256": sha256(raw).hexdigest(),
        "synthetic_account_bound": True,
        "synthetic_parent_and_revision_matched": True,
        "independent_immutable_anchor_verified": False,
        "owner_authority_verified": False,
        "production_signing_key_verified": False,
        "live_mandate_active": False,
        "live_trades_authorised": False,
        "broker_GETs": 0, "broker_POSTs": 0,
    }

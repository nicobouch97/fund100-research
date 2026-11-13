"""Locked V6 original 8-GET broker-risk receipt signer, NO trading capability.

Produces the exact Ed25519 envelope expected by the independent verifier
only after a separately reviewed V6 scheduled watcher has performed genuine
broker GETs, matched original account/inventory and checked HIGH 6/20/35.
THIS SIGNER IS NOT AN INDEPENDENT BROKER READER BY ITSELF: it accepts a
reviewed in-process risk verdict; caller provenance and credential isolation
must be audited before any runtime release or signer key provisioning.

The signer does not fetch broker data, use Trading API keys, write GitHub,
publish receipts, cancel orders, lift STOP or authorize a trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import secrets

import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as verifier

SCHEMA = verifier.SCHEMA
REPO = verifier.REPO
WATCH_REF = ("nicobouch97/fund100-research/.github/workflows/"
             "fund100-v6-s1-independent-risk-watch.yml@refs/heads/main")
SIGNER_SOURCE_RELEASED = False
EXPECTED_ACCOUNT_BINDING_SHA256 = None
EXPECTED_RISK_POLICY_SHA256 = None
MAX_BROKER_SNAPSHOT_SECONDS = verifier.MAX_BROKER_SNAPSHOT_SECONDS
MAX_SIGN_DELAY_SECONDS = verifier.MAX_SIGN_DELAY_SECONDS
NO_NETWORK = True
NO_BROKER_CREDENTIALS = True
NO_GITHUB_WRITE = True
NO_ORDER_WRITE = True
NO_TRADE_RELEASE = True
KEY_ENV = "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX"


class RiskReceiptSignerStop(RuntimeError):
    pass


def _utc(value: object) -> datetime:
    if type(value) is not str or re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",value) is None:
        raise RiskReceiptSignerStop("Noncanonical broker observation time")
    try:
        return datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise RiskReceiptSignerStop("Invalid broker observation time") from None


def _hash(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}",value) is not None


def _canonical(payload: object) -> bytes:
    try:
        return json.dumps(payload,sort_keys=True,separators=(",",":"),
                          ensure_ascii=True,allow_nan=False).encode("ascii")
    except (TypeError,ValueError,UnicodeError):
        raise RiskReceiptSignerStop("Noncanonical risk policy") from None


def _provenance(expected_head_sha: str) -> None:
    env=os.environ
    if (SIGNER_SOURCE_RELEASED is not True
        or not all((NO_NETWORK,NO_BROKER_CREDENTIALS,NO_GITHUB_WRITE,
                    NO_ORDER_WRITE,NO_TRADE_RELEASE))
        or env.get("GITHUB_ACTIONS")!="true"
        or env.get("GITHUB_REPOSITORY")!=REPO
        or env.get("GITHUB_REF")!="refs/heads/main"
        or env.get("GITHUB_EVENT_NAME")!="schedule"
        or env.get("GITHUB_WORKFLOW_REF")!=WATCH_REF
        or env.get("GITHUB_RUN_ATTEMPT")!="1"
        or env.get("FUND100_RISK_LEVEL")!="HIGH"
        or env.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or type(expected_head_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}",expected_head_sha) is None
        or env.get("GITHUB_SHA")!=expected_head_sha):
        raise RiskReceiptSignerStop("Independent signer source HARD LOCKED")


def _require_risk_pass(result: object) -> None:
    # This is a defense-in-depth cross-check, not proof that the caller
    # actually made network calls. Only an audited dedicated 8-GET watcher
    # may invoke the released signer; no other job may access its private key.
    if (type(result) is not dict
        or result.get("schema") !=
           "FUND100_V6_S1_ACTIVE_HIGH_FIRST_ACWI_SELL_ORDER_TIME_RISK_V2"
        or result.get("status") !=
           "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
        or result.get("same_process_real_broker_gets") != 8
        or type(result.get("same_process_real_broker_gets")) is not int
        or result.get("original_acwi_exact_fractional_holdings_verified") is not True
        or result.get("original_strict_postfunding_6_20_35_risk_pass") is not True
        or result.get("broker_post_attempts") != 0
        or type(result.get("broker_post_attempts")) is not int
        or result.get("orders_submitted_here") != 0
        or type(result.get("orders_submitted_here")) is not int
        or result.get("buy_authorized") is not False):
        raise RiskReceiptSignerStop("No genuine eight-GET source PASS")


def sign_reviewed_eight_get_result(*, checked: object, account_id: object,
                                   policy: object, head_sha: str,
                                   observed_start_utc: str,
                                   broker_completed_utc: str,
                                   signed_at_utc: str | None = None) -> dict:
    """Pure source-bound receipt: no broker access, publishing or trade GO.

    All inputs come only from the dedicated reviewed broker watcher, after
    it performed and checked eight authentic GETs. No event/synthetic
    caller is granted production runtime release by this module.
    """
    _provenance(head_sha)
    _require_risk_pass(checked)
    if type(account_id) is not str or re.fullmatch(
            r"[A-Za-z0-9-]{8,128}",account_id) is None:
        raise RiskReceiptSignerStop("Broker account ID invalid")
    if type(policy) is not dict or not policy:
        raise RiskReceiptSignerStop("Original policy unavailable")
    account_hash=sha256(("FUND100-LIVE-ACCOUNT|"+account_id).encode()).hexdigest()
    policy_hash=sha256(_canonical(policy)).hexdigest()
    if (not _hash(EXPECTED_ACCOUNT_BINDING_SHA256)
        or not _hash(EXPECTED_RISK_POLICY_SHA256)
        or account_hash!=EXPECTED_ACCOUNT_BINDING_SHA256
        or policy_hash!=EXPECTED_RISK_POLICY_SHA256):
        raise RiskReceiptSignerStop("Independent account/policy pins absent")
    started=_utc(observed_start_utc)
    completed=_utc(broker_completed_utc)
    if signed_at_utc is None:
        signed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signed=_utc(signed_at_utc)
    if (not started<=completed<=signed
        or (completed-started).total_seconds()>MAX_BROKER_SNAPSHOT_SECONDS
        or (signed-completed).total_seconds()>MAX_SIGN_DELAY_SECONDS):
        raise RiskReceiptSignerStop("Broker observations/signing delayed")
    # The signer cannot sign broker observations from the distant past,
    # including replays of formerly good risk verdicts.
    now=datetime.now(timezone.utc)
    if abs((now-signed).total_seconds())>MAX_SIGN_DELAY_SECONDS:
        raise RiskReceiptSignerStop("Signer wall-clock freshness unavailable")
    hexkey=os.environ.get(KEY_ENV,"")
    if type(hexkey) is not str or re.fullmatch(r"[0-9a-f]{64}",hexkey) is None:
        raise RiskReceiptSignerStop("Independent signer key unavailable")
    if hexkey in (os.environ.get("ALPACA_LIVE_KEY"),
                  os.environ.get("ALPACA_LIVE_SECRET"),
                  os.environ.get("GITHUB_TOKEN")):
        raise RiskReceiptSignerStop("Signer key is not isolated")
    receipt={
        "schema":SCHEMA, "repo":REPO, "head_sha":head_sha,
        "account_binding_sha256":account_hash,
        "risk_policy_sha256":policy_hash,
        "risk_outcome":verifier.EXPECTED_RISK_OUTCOME,
        "broker_get_count":8, "broker_write_count":0,
        "trade_authorized":False,
        "observed_start_utc":observed_start_utc,
        "broker_completed_utc":broker_completed_utc,
        "signed_at_utc":signed_at_utc,
        "nonce":secrets.token_hex(32),
    }
    if set(receipt)!=verifier.RECEIPT_FIELDS:
        raise RiskReceiptSignerStop("Signed receipt schema drift")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey)
        signature=Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(hexkey)).sign(_canonical(receipt)).hex()
    except (ImportError,ValueError,TypeError):
        raise RiskReceiptSignerStop("Signer cryptography unavailable") from None
    return {"receipt":receipt,"ed25519_signature_hex":signature}

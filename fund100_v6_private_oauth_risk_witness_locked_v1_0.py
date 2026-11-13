"""Source-locked private Alpaca Trading OAuth eight-GET risk witness.

Reuses the exact read-only OAuth eight-GET transport and the EXISTING
original-ACWI HIGH sell risk evaluator. Unlike the legacy live watcher it
never accepts or loads tradable Alpaca API-key/secret credentials.

IMPORTANT: this module cannot itself prove provider token issuance, signed
original bootstrap integrity, GitHub current-main identity or process
isolation. All of those are separate release gates and remain source-locked.
The private result is an in-process witness for a DIFFERENT signer principal;
it is NOT a signed receipt, order authorisation or tradable account access.
Never expose the result on a public endpoint or place the signer key here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import time

import fund100_v6_readonly_oauth_eight_get_transport_v1_0 as oauth
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as risk
import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as receipt

SCHEMA = "FUND100_V6_PRIVATE_OAUTH_EIGHT_GET_RISK_WITNESS_LOCKED_V1"
SOURCE_RELEASED = False
PROVIDER_READONLY_GRANT_CUSTODY_INDEPENDENTLY_VERIFIED = False
SIGNED_ORIGINAL_POLICY_SOURCE_INDEPENDENTLY_VERIFIED = False
APPROVED_ACCOUNT_BINDING_SHA256 = None
APPROVED_POLICY_SHA256 = None
APPROVED_MAIN_SHA = None
ENV_MODE = "FUND100_PRIVATE_RISK_MONITOR_MODE"
REQUIRED_MODE = "READONLY_OAUTH_BROKER_WITNESS_NO_ORDER_AUTHORITY"
NO_BROKER_WRITE = True
NO_GITHUB_WRITE = True
NO_STOP_DISPATCH = True
NO_SIGNER_KEY = True
NO_TRADE_RELEASE = True
NO_PUBLIC_OUTPUT = True
NO_TOKEN_EXCHANGE = True
MAX_SECONDS = receipt.MAX_BROKER_SNAPSHOT_SECONDS
FORBIDDEN_CREDENTIALS = (
    "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
    "ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET",
    "APCA_API_KEY_ID", "APCA_API_SECRET_KEY",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
    "FUND100_GH_STOP_DISPATCH_TOKEN", "GITHUB_TOKEN",
)


class PrivateRiskWitnessHold(RuntimeError):
    pass


def _hash(s: object) -> bool:
    return type(s) is str and re.fullmatch(r"[0-9a-f]{64}", s) is not None


def _scope() -> None:
    if (SOURCE_RELEASED is not True
        or PROVIDER_READONLY_GRANT_CUSTODY_INDEPENDENTLY_VERIFIED is not True
        or SIGNED_ORIGINAL_POLICY_SOURCE_INDEPENDENTLY_VERIFIED is not True
        or not all((NO_BROKER_WRITE, NO_GITHUB_WRITE, NO_STOP_DISPATCH,
                    NO_SIGNER_KEY, NO_TRADE_RELEASE, NO_PUBLIC_OUTPUT,
                    NO_TOKEN_EXCHANGE))
        or os.environ.get(ENV_MODE) != REQUIRED_MODE
        or any(x in os.environ for x in FORBIDDEN_CREDENTIALS)
        or not _hash(APPROVED_ACCOUNT_BINDING_SHA256)
        or not _hash(APPROVED_POLICY_SHA256)
        or type(APPROVED_MAIN_SHA) is not str
        or re.fullmatch(r"[0-9a-f]{40}", APPROVED_MAIN_SHA) is None
        or oauth.GET_TRANSPORT_RELEASED is not True):
        raise PrivateRiskWitnessHold("Independent read-only OAuth risk witness HARD LOCKED")


def _canonical_policy_sha256(policy: dict) -> str:
    try:
        return sha256(json.dumps(policy, sort_keys=True, separators=(",",":"),
                                 ensure_ascii=True, allow_nan=False).encode(
                                     "ascii")).hexdigest()
    except (ValueError, TypeError, UnicodeError):
        raise PrivateRiskWitnessHold("Untrusted original policy shape") from None


def capture_original_acwi_private_witness(*, verified_grant: dict,
                                          signed_bootstrap: dict,
                                          signed_policy: dict,
                                          original_qty: str,
                                          transport=None) -> dict:
    """One exact eight-GET read-only OAuth snapshot, NO signer or broker POST.

    The future caller must load the provider-issued no-write grant from a
    separately authenticated private vault, verify its scope and account
    against the actual Alpaca issuer, and load historical bootstrap/policy
    from pinned signed sources. Caller-supplied dicts alone are NOT proof.

    The returned private dict is never a risk receipt or trade permission.
    """
    _scope()
    try:
        if type(signed_policy) is not dict or type(signed_bootstrap) is not dict:
            raise PrivateRiskWitnessHold("Signed original documents not trusted")
        if _canonical_policy_sha256(signed_policy) != APPROVED_POLICY_SHA256:
            raise PrivateRiskWitnessHold("Original policy digest changed")
        if signed_policy.get("account_binding_sha256") != APPROVED_ACCOUNT_BINDING_SHA256:
            raise PrivateRiskWitnessHold("Original account binding changed")
        if not isinstance(original_qty, str) or not original_qty:
            raise PrivateRiskWitnessHold("Original inventory quantity absent")
        # Check grant scope before ANY broker GET; 'scope' must be empty.
        oauth._require_readonly_oauth_grant(verified_grant)
        _scope()
        started_monotonic = time.monotonic()
        started_at = datetime.now(timezone.utc)
        docs = oauth.original_eight_get_snapshot(
            verified_grant, transport=transport)
        completed_at = datetime.now(timezone.utc)
        if (type(docs) is not tuple or len(docs) != 8
            or not 0 <= time.monotonic() - started_monotonic <= MAX_SECONDS
            or not started_at <= completed_at
            or (completed_at - started_at).total_seconds() > MAX_SECONDS):
            raise PrivateRiskWitnessHold("OAuth broker snapshot unavailable or stale")
        account, positions, orders, clock, history, activities, native, extended = docs
        if (type(account) is not dict
            or type(account.get("id")) is not str
            or not re.fullmatch(r"[A-Za-z0-9-]{8,128}", account["id"])
            or sha256(("FUND100-LIVE-ACCOUNT|" + account["id"]).encode(
                "utf-8")).hexdigest() != APPROVED_ACCOUNT_BINDING_SHA256
            or type(clock) is not dict or clock.get("is_open") is not True):
            raise PrivateRiskWitnessHold("Live bound account/market not verified")
        _scope()
        observed = completed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        checked = risk.evaluate_original_sell_only(
            account=account, positions=positions, orders=orders, clock=clock,
            history=history, activities=activities,
            native_none_history=native, extended_history=extended,
            bootstrap=signed_bootstrap, original_policy=signed_policy,
            original_qty=original_qty, observed_at_utc=observed)
        if (type(checked) is not dict
            or checked.get("schema") != risk.SCHEMA
            or checked.get("status") !=
                "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
            or checked.get("same_process_real_broker_gets") != 8
            or type(checked.get("same_process_real_broker_gets")) is not int
            or checked.get("original_strict_postfunding_6_20_35_risk_pass") is not True
            or checked.get("original_acwi_exact_fractional_holdings_verified") is not True
            or checked.get("broker_post_attempts") != 0
            or type(checked.get("broker_post_attempts")) is not int
            or checked.get("orders_submitted_here") != 0
            or type(checked.get("orders_submitted_here")) is not int
            or checked.get("buy_authorized") is not False):
            raise PrivateRiskWitnessHold("Verified read-only broker risk did not PASS")
        if not 0 <= time.monotonic() - started_monotonic <= MAX_SECONDS:
            raise PrivateRiskWitnessHold("Private OAuth broker witness stale")
        _scope()
        # Returned ONLY to an isolated, separately authenticated signer
        # transport. Do not serialize to logs, public HTTP or GitHub Actions.
        return {
            "schema": SCHEMA, "private_witness_not_signed": True,
            "checked": checked, "account_id": account["id"],
            "policy": signed_policy, "head_sha": APPROVED_MAIN_SHA,
            "observed_start_utc": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "broker_completed_utc": observed,
            "trade_authorized": False, "broker_writes": 0,
        }
    except PrivateRiskWitnessHold:
        raise
    except Exception:
        # Never expose OAuth tokens, account data or provider error bodies.
        raise PrivateRiskWitnessHold(
            "Independent read-only broker risk unavailable; HOLD") from None

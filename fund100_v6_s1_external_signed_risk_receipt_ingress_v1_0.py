"""Source-locked HTTPS GET-only ingress for independently signed broker-risk receipts.

This is NOT installed on Railway, not imported by the trade entry, and NOT a
trade GO. The future sender is a separately isolated read-only broker watcher
with an independent Ed25519 signing key. GitHub scheduled green status and
the public Railway /healthz diagnostic cannot provide a PASS.

Source locks, signer pin, account binding and policy pin must remain blocked
until real read-only OAuth, account identity, policy and monitor uptime are
independently reviewed. Failure at any step means STOP and no order.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as signed

SCHEMA = "FUND100_V6_S1_INDEPENDENT_SIGNED_RISK_RECEIPT_INGRESS_V1"
RECEIPT_INGRESS_RELEASED = False
EXPECTED_ACCOUNT_BINDING_SHA256 = None
EXPECTED_RISK_POLICY_SHA256 = None
URL = "https://fund100-risk-observer-dryrun.up.railway.app/v6/risk/receipt"
EXPECTED_WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main"
)
MAX_BODY_BYTES = 8192
TIMEOUT_SECONDS = 6
NO_BROKER_REQUEST = True
NO_GITHUB_WRITE = True
NO_RAILWAY_WRITE = True
NO_TRADE_RELEASE = True


class ExternalReceiptIngressStop(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExternalReceiptIngressStop("External risk receipt redirected; STOP")


def _unique_pairs(pairs):
    value = {}
    for k, v in pairs:
        if k in value:
            raise ExternalReceiptIngressStop("Ambiguous duplicate receipt key")
        value[k] = v
    return value


def _scope(*, main_sha: object, readonly_token: object) -> None:
    if RECEIPT_INGRESS_RELEASED is not True:
        raise ExternalReceiptIngressStop("Independent receipt ingress HARD LOCKED")
    env = os.environ
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != signed.REPO
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "schedule"
        or env.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or type(main_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}", main_sha) is None
        or main_sha != env.get("GITHUB_SHA")):
        raise ExternalReceiptIngressStop("Untrusted signed-receipt workflow context")
    if (type(readonly_token) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{32,512}", readonly_token) is None):
        raise ExternalReceiptIngressStop("Independent receipt read credential invalid")
    if (type(EXPECTED_ACCOUNT_BINDING_SHA256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", EXPECTED_ACCOUNT_BINDING_SHA256) is None
        or type(EXPECTED_RISK_POLICY_SHA256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", EXPECTED_RISK_POLICY_SHA256) is None):
        raise ExternalReceiptIngressStop("Approved account/policy binding missing")


def require_fresh_signed_external_risk_pass(*, main_sha: str,
                                             readonly_token: str,
                                             now_utc: datetime | None = None,
                                             transport=None) -> bool:
    """One GET, one Ed25519+account+policy+age check, no other side effects.

    Offline tests may replace transport and clock. No production user input
    controls either; they belong to the protected first-ACWI process.
    Even an authenticated fresh receipt does not replace same-order broker
    checks, STOP, cash, signed owner fence or economic NO_TRADE.
    """
    _scope(main_sha=main_sha, readonly_token=readonly_token)
    req = Request(
        URL, method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + readonly_token,
            "Cache-Control": "no-store",
            "User-Agent": "fund100-external-risk-receipt-readonly",
        },
    )
    sender = build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with sender(req, timeout=TIMEOUT_SECONDS) as response:
            if (getattr(response, "status", None) != 200
                or response.headers.get_content_type() != "application/json"
                or (hasattr(response, "geturl") and response.geturl() != URL)):
                raise ExternalReceiptIngressStop("External risk response not trusted")
            raw = response.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise ExternalReceiptIngressStop("External risk receipt oversized")
        envelope = json.loads(raw, object_pairs_hook=_unique_pairs)
    except ExternalReceiptIngressStop:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError,
            TypeError, UnicodeError):
        # No raw response, account data, bearer secret or error body in logs.
        raise ExternalReceiptIngressStop("External risk evidence unavailable; STOP") from None
    try:
        return signed.verify_independent_risk_receipt(
            envelope=envelope,
            expected_main_sha=main_sha,
            expected_account_binding_sha256=EXPECTED_ACCOUNT_BINDING_SHA256,
            expected_risk_policy_sha256=EXPECTED_RISK_POLICY_SHA256,
            now_utc=now_utc,
        )
    except signed.SignedRiskReceiptStop:
        raise ExternalReceiptIngressStop("External risk signature/age/account invalid; STOP") from None

"""Authenticated GET-only bridge for the as-yet-uninitialised V6 recurring journal.

Uses both independently scoped private GitHub principals to authenticate the
original signed ACWI seq1 ledger before inspecting the exact new journal path.
No private Git PUT, broker call, release, standing GO or order authority.
A dual 404 establishes a qualified ABSENT/HOLD observation, NOT permission
to initialise private state or create a trading attempt.
"""
from __future__ import annotations

from hashlib import sha256
import os
import re
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original_cas
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as original_owner
import fund100_v6_s1_public_genesis_witness_v1_0 as original_witness

SCHEMA = "FUND100_V6_RECURRING_PROTECTED_DUAL_PRINCIPAL_GETONLY_V1"
RECURRING_URL = (
    "https://api.github.com/repos/"
    + journal.REPOSITORY + "/contents/" + journal.PATH + "?ref=main"
)
MAX_REPLY_BYTES = 150_000
NO_GIT_MUTATIONS = NO_BROKER_ACCESS = True
REAL_PRIVATE_WRITES = BROKER_GETS = BROKER_POSTS = 0
LIVE_ORDER_AUTHORIZED = False


class RecurringReadStop(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RecurringReadStop("Private GET redirected; HOLD")


def _get_recurring(*, token, transport=None):
    """Only exact recurring path; 404 allowed ONLY after separately proved access."""
    if (type(token) is not str or len(token) < 10
        or token.strip() != token or "\r" in token or "\n" in token):
        raise RecurringReadStop("Invalid scoped private GET principal")
    request = Request(
        RECURRING_URL, method="GET",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Cache-Control": "no-store",
            "User-Agent": "fund100-v6-recurring-dual-principal-getonly",
        },
    )
    sender = (build_opener(NoRedirect()).open
              if transport is None else transport)
    try:
        with sender(request, timeout=12) as response:
            if getattr(response, "status", None) != 200:
                raise RecurringReadStop("Private recurring GET status not 200")
            raw = response.read(MAX_REPLY_BYTES + 1)
        if len(raw) > MAX_REPLY_BYTES:
            raise RecurringReadStop("Private recurring GET response oversized")
        result = json.loads(raw)
        if type(result) is not dict:
            raise RecurringReadStop("Private recurring GET response malformed")
        return result
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise RecurringReadStop("Private recurring GET denied/unknown; HOLD") from None
    except RecurringReadStop:
        raise
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError, TypeError):
        raise RecurringReadStop("Private recurring GET uncertain; HOLD") from None


def _original_principal_authenticated(*, token, nonce, binding, key,
                                       original_transport=None):
    """Real same-repo signed seq1 GET distinguishes valid principal from 404."""
    try:
        source = original_owner._get_bounded_json(
            url=original_owner.ORIGINAL_ORDER_LEDGER_URL + "?ref=main",
            token=token, transport=original_transport)
        sha, doc = original_cas._read_source(
            source, private_genesis=nonce,
            account_binding_sha256=binding, key=key)
        if (doc.get("sequence") != 1
            or set(doc.get("entries", {})) != {"ACWI"}
            or doc["entries"]["ACWI"]["state"] != "RESERVED_NO_RETRY"):
            raise RecurringReadStop("Original signed ACWI seq1 not reserved")
        return sha
    except RecurringReadStop:
        raise
    except Exception:
        raise RecurringReadStop("Original private HMAC principal authentication failed") from None


def _recurring_genesis_candidate(nonce, binding):
    """Deterministic proposed namespace binding; NOT a published head anchor."""
    if (re.fullmatch(r"[a-f0-9]{64}", nonce or "") is None
        or re.fullmatch(r"[a-f0-9]{64}", binding or "") is None):
        raise RecurringReadStop("Original witnessed genesis/account missing")
    return sha256(
        b"fund100-v6-recurring-v2-derived-genesis-candidate\x00"
        + bytes.fromhex(nonce) + bytes.fromhex(binding)
    ).hexdigest()


def inspect(*, environ=None, recurring_transport=None,
            original_transport=None, witness=None):
    """Real verified dual-GET: absent holds, signed present still not released."""
    env = os.environ if environ is None else environ
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch")
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"):
        raise RecurringReadStop("Protected original main and STOP required")
    read = env.get("FUND100_PRIVATE_STATE_READ_TOKEN")
    candidate = env.get("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    key_hex = env.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX")
    if (type(read) is not str or type(candidate) is not str
        or read == candidate or min(len(read), len(candidate)) < 10
        or type(key_hex) is not str
        or re.fullmatch(r"[a-f0-9]{64}", key_hex) is None):
        raise RecurringReadStop("Distinct private principals/HMAC required")
    # The original independently pinned external witness proves the SAME
    # account binding and signed legacy seq1 for both credential identities.
    try:
        w = original_witness.verify() if witness is None else witness()
        nonce = w["original_public_genesis_nonce"]
        binding = w["original_live_account_binding_sha256"]
        genesis = _recurring_genesis_candidate(nonce, binding)
        key = bytes.fromhex(key_hex)
    except Exception:
        raise RecurringReadStop("Original account/genesis binding unverifiable") from None

    x = _original_principal_authenticated(
        token=read, nonce=nonce, binding=binding, key=key,
        original_transport=original_transport)
    y = _original_principal_authenticated(
        token=candidate, nonce=nonce, binding=binding, key=key,
        original_transport=original_transport)
    if x != y:
        raise RecurringReadStop("Read/production-write-candidate original heads disagree")

    left = _get_recurring(token=read, transport=recurring_transport)
    right = _get_recurring(token=candidate, transport=recurring_transport)
    if left is None and right is None:
        return {
            "schema": SCHEMA,
            "status": "AUTHENTICATED_DUAL_404_RECURRING_JOURNAL_ABSENT_HOLD",
            "original_signed_legacy_seq1_verified_with_both_principals": True,
            "recurring_genesis_production_initialized": False,
            "recurring_signed_head_verified": False,
            "external_immutable_recurring_head_anchor_verified": False,
            "private_git_puts": 0, "broker_gets": 0, "broker_posts": 0,
            "live_trading_authorized": False,
            "manual_approval_required_for_readonly_check": False,
        }
    if left is None or right is None:
        raise RecurringReadStop("Two authenticated principals disagree about recurring HEAD")
    if (not all(left.get(k) == right.get(k)
                for k in ("path", "sha", "type", "encoding", "content"))
        or left.get("path") != journal.PATH):
        raise RecurringReadStop("Recurring private HEAD diverged across principals")
    try:
        sha, doc = journal.read_github_source(
            left, genesis_sha256=genesis,
            account_binding_sha256=binding, key=key)
    except Exception:
        raise RecurringReadStop("Existing recurring journal not anchored to signed V2 candidate") from None
    # Even a valid HMAC cannot prove rollback resistance or a standing
    # signed production release: report evidence, ALWAYS HOLD orders.
    return {
        "schema": SCHEMA,
        "status": "HMAC_VERIFIED_CANDIDATE_RECURRING_HEAD_STILL_NO_IMMUTABLE_ANCHOR",
        "original_signed_legacy_seq1_verified_with_both_principals": True,
        "recurring_genesis_production_initialized": True,
        "recurring_signed_head_verified": True,
        "external_immutable_recurring_head_anchor_verified": False,
        "private_git_puts": 0, "broker_gets": 0, "broker_posts": 0,
        "live_trading_authorized": False,
        "manual_approval_required_for_readonly_check": False,
    }


def main():
    report = inspect()
    print(report["status"])
    print("Private recurring signed state: GET ONLY; NO Git PUT, no broker order.")
    print("Recurring immutable anchor/standing trading mandate not released.")


if __name__ == "__main__":
    main()

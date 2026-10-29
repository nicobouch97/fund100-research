"""At-most-one PRIVATE recurring signed journal CAS with injected OFFLINE IO.

Wires existing reviewed V2 HMAC plan -> exact old Git blob -> one PUT-shaped
callback -> independent new HMAC GET. NEVER performs HTTP/GitHub/Alpaca IO.
No production WRITE token, broker, active release or approval workflow.
A future authorised runtime must separately authenticate credential principals,
immutable head, mandate, cash, brokerage evidence, and STOP controls.
"""
from __future__ import annotations

from base64 import b64decode
from hashlib import sha1
import re

import fund100_v6_recurring_event_signed_journal_v1_0 as journal

SCHEMA = "FUND100_V6_RECURRING_SINGLE_ATTEMPT_PRIVATE_CAS_OFFLINE_V1"
OFFLINE_MODE = "OFFLINE_INJECTED_FAKE_GIT_ONLY"
PRODUCTION_REMOTE_TRANSPORT_RELEASED = False
LIVE_BROKER_ORDER_RELEASED = False
BROKER_GETS = BROKER_POSTS = PRIVATE_PRODUCTION_PUTS = 0
_ALLOWED = frozenset({
    "OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY",
    "OFFLINE_POSSIBLE_SEND_PREPOST_CAS_NO_RESEND",
    "OFFLINE_SYNTHETIC_RECONCILIATION_CAS_NO_ORDER_AUTHORITY",
})


class RecurringCasStop(ValueError):
    pass


def _source(source, *, genesis_sha256, account_binding_sha256, key):
    try:
        return journal.read_github_source(
            source, genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key)
    except (journal.JournalStop, KeyError, TypeError, ValueError):
        raise RecurringCasStop("Unsigned, corrupted or unavailable private HEAD; HOLD") from None


def _prepared(plan, *, genesis_sha256, account_binding_sha256, key):
    """Check exact expected signed bytes before any injected write."""
    if (type(plan) is not dict or plan.get("status") not in _ALLOWED
        or type(plan.get("commit")) is not dict
        or plan.get("broker_order_authorized") is not False
        or plan.get("real_git_writes") != 0
        or plan.get("real_broker_posts") != 0
        or plan.get("external_immutable_anchor_verified") is not False):
        raise RecurringCasStop("No source-checked offline plan; HOLD")
    commit = plan["commit"]
    if (set(commit) != {
            "repository", "path", "expected_current_sha", "content_base64"}
        or commit["repository"] != journal.REPOSITORY
        or commit["path"] != journal.PATH
        or commit["expected_current_sha"] != plan.get("old_blob_sha")
        or type(plan.get("new_blob_sha")) is not str
        or re.fullmatch(r"[a-f0-9]{40}", plan["new_blob_sha"]) is None):
        raise RecurringCasStop("Unapproved private path, CAS parent or signed plan")
    # A plan's candidate must itself be authentically HMAC signed, not
    # just a plausible SHA-shaped untrusted Contents payload.
    candidate = {
        "type": "file", "path": journal.PATH, "encoding": "base64",
        "sha": plan["new_blob_sha"], "content": commit["content_base64"],
    }
    next_sha, next_doc = _source(
        candidate, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    if (next_sha != plan["new_blob_sha"]
        or next_doc["prior_document_sha"] != plan["old_blob_sha"]):
        raise RecurringCasStop("Proposed signed new HEAD is not parent-bound")
    return candidate, next_doc


def apply_offline_once(*, plan, read_before, put_once, read_after,
                       genesis_sha256, account_binding_sha256, key,
                       mode=OFFLINE_MODE):
    """One PREGET, at most one injected PUT, independent POSTGET; no retries.

    Callback provenance is explicitly SYNTHETIC. This helper has no real
    HTTP implementation and no credential scope; success is NOT LIVE proof.
    """
    if (mode != OFFLINE_MODE
        or PRODUCTION_REMOTE_TRANSPORT_RELEASED is not False
        or LIVE_BROKER_ORDER_RELEASED is not False
        or not all(callable(x) for x in (read_before, put_once, read_after))
        or read_before is read_after):
        raise RecurringCasStop("Only separately injected offline CAS permitted")
    candidate, next_doc = _prepared(
        plan, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    before = read_before()
    old_sha, old_doc = _source(
        before, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    if (old_sha != plan["old_blob_sha"]
        or next_doc["sequence"] != old_doc["sequence"] + 1):
        raise RecurringCasStop("Concurrent private HEAD or signed sequence drift; zero PUT")
    # Callback receives only the exact GitHub Contents expected-SHA
    # mutation. No loop, retry, POST, second path or live execution.
    request = {
        "repository": journal.REPOSITORY, "path": journal.PATH,
        "branch": "main", "sha": old_sha,
        "content": candidate["content"],
        "message": "Fund-100 recurring signed event exact single CAS (offline fixture)",
    }
    try:
        ack = put_once(request)
    except Exception:
        raise RecurringCasStop("Private CAS outcome ambiguous; never resubmit") from None
    if (type(ack) is not dict
        or type(ack.get("content")) is not dict
        or ack["content"].get("path") != journal.PATH
        or ack["content"].get("sha") != plan["new_blob_sha"]
        or type(ack.get("commit")) is not dict
        or type(ack["commit"].get("sha")) is not str
        or re.fullmatch(r"[a-f0-9]{40}", ack["commit"]["sha"]) is None):
        raise RecurringCasStop("Private CAS acknowledgement incomplete; no retry")
    # Independent callback reads exact remote source again. A confirmed
    # Git blob does NOT prove immutable rollback anchor or broker readiness.
    try:
        after = read_after()
        confirmed = journal.verify_remote_cas(
            plan, after, genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key)
    except Exception:
        raise RecurringCasStop("Independent signed CAS readback unavailable; HOLD") from None
    if confirmed.get("broker_order_authorized") is not False:
        raise RecurringCasStop("Unexpected live release from offline CAS")
    return {
        "schema": SCHEMA,
        "status": "INJECTED_OFFLINE_ONE_CAS_AND_INDEPENDENT_HMAC_READBACK",
        "synthetic_only_no_authentic_private_write": True,
        "verified_new_blob_sha": plan["new_blob_sha"],
        "verified_sequence": next_doc["sequence"],
        "expected_parent_blob_sha": old_sha,
        "injected_put_calls": 1,
        "production_private_puts": 0,
        "broker_gets": 0, "broker_posts": 0,
        "external_immutable_anchor_verified": False,
        "standing_mandate_authenticated": False,
        "live_order_authorized": False,
        "manual_per_trade_approval_required": False,
    }


def classify_uncertain_outcome(*, plan, independently_observed_source,
                               genesis_sha256, account_binding_sha256, key):
    """GET-only recovery judgement after lost PUT acknowledgement.

    Never performs another PUT or allows an order. Even an exact observed
    candidate cannot prove unique off-chain immutable history.
    """
    candidate, _ = _prepared(
        plan, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    try:
        observed_sha, _ = _source(
            independently_observed_source,
            genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key)
    except RecurringCasStop:
        return "HOLD_UNCERTAIN_PRIVATE_HEAD_NEVER_RETRY"
    return (
        "EXACT_INTENDED_SIGNED_HEAD_OBSERVED_BUT_NO_ORDER_PERMISSION"
        if observed_sha == candidate["sha"]
        else "HOLD_OTHER_PRIVATE_HEAD_NEVER_RETRY"
    )

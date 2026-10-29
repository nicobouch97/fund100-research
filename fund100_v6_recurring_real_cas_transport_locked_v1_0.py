"""Real GitHub Contents CAS transport for the FUTURE genuine recurring event.

The first V6 recurring journal exists with signed seq0 and an actual
GitHub-provider-immutable published commitment. The offline event planner
already signs original intent and exact old/new Git blobs. This module fills
the missing REAL single-conditional-PUT transport boundary.

The real writer is HARD-LOCKED until a reviewed strategy-signal producer,
standing HIGH mandate, independent broker reconciliation, and automatic
per-head immutable release protocol have been integrated. No fake event
may be sent to production and no live broker order is ever sent here.
Synthetic regression tests inject all IO and may explicitly enable ONLY
the synthetic test gate. No push/schedule/dispatch writer workflow exists.
"""
from __future__ import annotations

from base64 import b64decode
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_cas_once_offline_v1_0 as offline
import fund100_v6_recurring_private_protected_getonly_v1_0 as private
import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as anchored

SCHEMA = "FUND100_V6_RECURRING_EXACT_PRIVATE_SIGNED_CAS_TRANSPORT_V1"
URL = "https://api.github.com/repos/" + journal.REPOSITORY + "/contents/" + journal.PATH
READ_URL = URL + "?ref=main"
MAX_PUT_BYTES = 125000
MAX_ACK_BYTES = 16000
PRODUCTION_EVENT_CAS_RELEASED = False
AUTOMATIC_IMMUTABLE_NEXT_HEAD_RELEASED = False
REAL_STRATEGY_EVENT_SOURCE_AUTHENTICATED = False
LIVE_BROKER_ORDER_RELEASED = False
NO_AUTOMATIC_CAS_RETRY = True
ALLOWED_STAGE = "OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"
NEXT_HEAD_IMMUTABLE_BY_THIS_TRANSPORT = False


class PrivateCasHold(RuntimeError):
    pass


def _exact_put_request(*, commit, old_sha, new_sha):
    """Construct only a signed old-SHA-conditional GitHub Contents PUT."""
    if (type(commit) is not dict
        or set(commit) != {"repository", "path",
                           "expected_current_sha", "content_base64"}
        or commit["repository"] != journal.REPOSITORY
        or commit["path"] != journal.PATH
        or commit["expected_current_sha"] != old_sha
        or type(new_sha) is not str
        or re.fullmatch(r"[a-f0-9]{40}", new_sha) is None
        or type(old_sha) is not str
        or re.fullmatch(r"[a-f0-9]{40}", old_sha) is None):
        raise PrivateCasHold("Unapproved signed private HEAD CAS")
    encoded = commit["content_base64"]
    if type(encoded) is not str or len(encoded) > 120000:
        raise PrivateCasHold("Unsigned or oversized candidate body")
    try:
        raw = b64decode(encoded, validate=True)
        if journal.original.blob_sha(raw) != new_sha:
            raise ValueError("candidate Git blob")
    except Exception:
        raise PrivateCasHold("Expected signed new Git blob mismatch") from None
    data = {
        "message": "Fund-100 signed recurring event reserve; NO BROKER ORDER",
        "branch": "main",
        "sha": old_sha,
        "content": encoded,
    }
    body = json.dumps(
        data, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).encode("ascii")
    if len(body) > MAX_PUT_BYTES:
        raise PrivateCasHold("GitHub CAS payload too large")
    return body


def _one_conditional_put(*, writer_token, expected_old, expected_new,
                         commit, transport=None):
    """One private Contents PUT; lost ACK remains terminal with NO retry.

    This primitive is callable by tests using an injected fake transport.
    A real network attempt requires the internal production release switch
    and the separate reviewed caller to have verified a genuine event.
    """
    if transport is None:
        if (PRODUCTION_EVENT_CAS_RELEASED is not True
            or AUTOMATIC_IMMUTABLE_NEXT_HEAD_RELEASED is not True
            or REAL_STRATEGY_EVENT_SOURCE_AUTHENTICATED is not True):
            raise PrivateCasHold("Genuine recurring event production CAS HARD LOCKED")
    elif getattr(transport, "synthetic_only", None) is not True:
        raise PrivateCasHold("Only explicitly synthetic fake transport may be injected")
    if (type(writer_token) is not str or len(writer_token) < 10
        or writer_token.strip() != writer_token
        or "\r" in writer_token or "\n" in writer_token):
        raise PrivateCasHold("Missing scoped Contents-write principal")
    body = _exact_put_request(
        commit=commit, old_sha=expected_old, new_sha=expected_new)
    req = Request(URL, method="PUT", data=body, headers={
        "Authorization": "Bearer " + writer_token,
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-v6-one-signed-event-exact-private-cas",
    })
    sender = (build_opener(private.NoRedirect()).open
              if transport is None else transport)
    try:
        with sender(req, timeout=12) as res:
            status = getattr(res, "status", None)
            raw = res.read(MAX_ACK_BYTES + 1)
        if status != 200 or len(raw) > MAX_ACK_BYTES:
            raise ValueError("CAS acknowledgement status/size")
        data = json.loads(raw, object_pairs_hook=journal._json_unique)
        if (type(data) is not dict or type(data.get("content")) is not dict
            or data["content"].get("path") != journal.PATH
            or data["content"].get("sha") != expected_new
            or type(data.get("commit")) is not dict
            or type(data["commit"].get("sha")) is not str
            or re.fullmatch(r"[a-f0-9]{40}", data["commit"]["sha"]) is None):
            raise ValueError("CAS ack not exact new signed Git blob")
        return data["content"]["sha"]
    except Exception:
        # Never second PUT after 401/403/409/422/timeout/redirection/lost ACK.
        raise PrivateCasHold("Private signed CAS outcome uncertain; NEVER RETRY") from None


def _verify_plan(plan, *, genesis, account, key, expected_old):
    try:
        candidate, next_doc = offline._prepared(
            plan, genesis_sha256=genesis,
            account_binding_sha256=account, key=key)
        if (plan["status"] != ALLOWED_STAGE
            or plan["old_blob_sha"] != expected_old
            or next_doc["sequence"] != 1
            or next_doc["prior_document_sha"] != expected_old
            or len(next_doc["events"]) != 1
            or next(iter(next_doc["events"].values()))["stage"] != "RESERVED_NO_ORDER"
            or not NO_AUTOMATIC_CAS_RETRY
            or NEXT_HEAD_IMMUTABLE_BY_THIS_TRANSPORT):
            raise ValueError("not exact first signed reservation")
        return candidate
    except Exception:
        raise PrivateCasHold("No authentic first reserved event plan; HOLD") from None


def simulate_one_existing_genesis_transition(*, plan, original_source,
                                             read_before, put_once,
                                             read_after, genesis, account, key):
    """Integration seam for synthetic replay, NO live network.

    Callbacks read independent old and new Git views. A single conditional
    PUT is allowed only when initial signed source is the IMMUTABLE-genesis
    private Git blob, and proposed signed seq1 holds a real-format order
    intent. This does not pretend that the event itself is authentic or
    that its new HEAD has been immutably anchored.
    """
    if (not all(callable(f) for f in (read_before,put_once,read_after))
        or read_before is read_after or put_once is read_before
        or PRODUCTION_EVENT_CAS_RELEASED is not False
        or LIVE_BROKER_ORDER_RELEASED is not False):
        raise PrivateCasHold("Synthetic integration only; production writer locked")
    sha, doc = journal.read_github_source(
        original_source, genesis_sha256=genesis,
        account_binding_sha256=account, key=key)
    if (sha != anchored.source.PINNED_INITIAL_BLOB_SHA
        or doc["sequence"] != 0 or doc["events"]):
        raise PrivateCasHold("Original signed genesis HEAD not pinned")
    _verify_plan(plan, genesis=genesis,account=account,
                 key=key,expected_old=sha)
    before = read_before()
    if before != original_source:
        raise PrivateCasHold("Independent pre-CAS HEAD does not match original")
    try:
        # An injected callback handles request transport; there is NO
        # opportunity to create a real broker order in this module.
        new = put_once({
            "repository": journal.REPOSITORY, "path": journal.PATH,
            "branch": "main", "sha": sha,
            "content": plan["commit"]["content_base64"],
        })
    except Exception:
        raise PrivateCasHold("CAS uncertain; NEVER RETRY") from None
    if new != plan["new_blob_sha"]:
        raise PrivateCasHold("Single CAS acknowledgement ambiguous; NEVER RETRY")
    after = read_after()
    verified = journal.verify_remote_cas(
        plan, after, genesis_sha256=genesis,
        account_binding_sha256=account, key=key)
    if verified.get("broker_order_authorized") is not False:
        raise PrivateCasHold("Offline signed journal unexpectedly authorizes order")
    return {
        "schema":SCHEMA,
        "status":"INJECTED_SIGNED_PRIVATE_FIRST_RESERVATION_CAS_NO_TRADING",
        "signed_new_blob_sha":plan["new_blob_sha"],
        "signed_sequence":1,
        "synthetic_only":True,
        "new_head_provider_immutable":False,
        "real_private_puts":0,
        "injected_private_puts":1,
        "broker_orders":0,
        "live_orders_authorized":False,
        "manual_per_trade_approval_required":False,
    }


def main():
    # NEVER attempt a remote PUT simply because this file ran on Actions.
    assert PRODUCTION_EVENT_CAS_RELEASED is False
    assert AUTOMATIC_IMMUTABLE_NEXT_HEAD_RELEASED is False
    assert REAL_STRATEGY_EVENT_SOURCE_AUTHENTICATED is False
    assert LIVE_BROKER_ORDER_RELEASED is False
    print("SIGNED RECURRING CAS TRANSPORT IMPLEMENTED BUT HARD LOCKED: NO EVENT, NO PUT, NO ORDER")


if __name__ == "__main__":
    main()

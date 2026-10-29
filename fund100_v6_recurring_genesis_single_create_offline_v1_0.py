"""Offline-only, at-most-once creation of the first signed recurring private journal.

This closes the EMPTY->GENESIS state transition in testable code without
adding a production GitHub writer, broker connection, new owner approval,
or any LIVE trading permission. All callbacks are injected synthetic fakes.
An actual production adapter must establish authenticated dual-principal
private 404s, a scoped writer, independent persistent readback, an external
immutable anti-rollback anchor, a standing mandate, and brokerage eligibility.
"""
from __future__ import annotations

from base64 import b64encode
import re

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original

SCHEMA = "FUND100_V6_RECURRING_FIRST_GENESIS_ONE_CREATE_OFFLINE_V1"
MODE = "INJECTED_OFFLINE_FAKE_PRIVATE_GIT_ONLY"
PRODUCTION_GITHUB_TRANSPORT_RELEASED = False
LIVE_BROKER_ORDER_RELEASED = False
REAL_PRIVATE_PUTS = BROKER_GETS = BROKER_POSTS = 0


class GenesisCreateStop(ValueError):
    pass


def _source(raw):
    return {
        "type": "file", "path": journal.PATH, "encoding": "base64",
        "content": b64encode(raw).decode("ascii"),
        "sha": original.blob_sha(raw),
    }


def prepare_offline_genesis(*, genesis_sha256, account_binding_sha256, key):
    """Return a signed in-memory candidate, not permission to create remotely."""
    try:
        raw = journal.initial_bytes(
            genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key,
        )
        candidate = _source(raw)
        signed_sha, doc = journal.read_github_source(
            candidate, genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key,
        )
    except (journal.JournalStop, original.CasStop, TypeError, ValueError):
        raise GenesisCreateStop("Cannot prepare signed recurring genesis") from None
    if (signed_sha != candidate["sha"] or doc["sequence"] != 0
        or doc["prior_document_sha"] is not None or doc["events"] != {}):
        raise GenesisCreateStop("Candidate is not an empty signed genesis")
    return candidate


def create_offline_once(*, read_before_primary, read_before_independent,
                        create_once, read_after_independent,
                        genesis_sha256, account_binding_sha256, key,
                        mode=MODE):
    """Two fake initial ABSENT observations, one fake CREATE, one signed readback.

    A lost response, pre-existing state, differing reads, or missing readback
    permanently HOLD this attempt; there is no retry or implicit overwrite.
    Callback outputs are synthetic and DO NOT establish real authentication.
    """
    callbacks = (read_before_primary, read_before_independent,
                 create_once, read_after_independent)
    if (mode != MODE or PRODUCTION_GITHUB_TRANSPORT_RELEASED is not False
        or LIVE_BROKER_ORDER_RELEASED is not False
        or not all(callable(fn) for fn in callbacks)
        or len({(id(getattr(fn, '__self__', None)),
                 id(getattr(fn, '__func__', fn))) for fn in callbacks})
                 != len(callbacks)):
        raise GenesisCreateStop("Offline injection only; distinct callbacks required")
    candidate = prepare_offline_genesis(
        genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    try:
        first = read_before_primary()
        second = read_before_independent()
    except Exception:
        raise GenesisCreateStop("First private genesis source uncertain; HOLD") from None
    # In an actual adapter, both ABSENT observations need independent
    # authenticated permission proofs. This fake cannot provide those proofs.
    if first is not None or second is not None:
        raise GenesisCreateStop("Existing or divergent recurring HEAD; zero CREATE")

    request = {
        "repository": journal.REPOSITORY,
        "path": journal.PATH,
        "branch": "main",
        "content": candidate["content"],
        "message": "Fund-100 recurring signed genesis (offline fixture only)",
    }
    # GitHub Contents create requires NO SHA. Never attempt a second create.
    try:
        acknowledgement = create_once(request)
    except Exception:
        raise GenesisCreateStop("First private CREATE acknowledgement uncertain; never retry") from None
    if (type(acknowledgement) is not dict
        or acknowledgement.get("status_code") != 201
        or type(acknowledgement.get("content")) is not dict
        or acknowledgement["content"].get("path") != journal.PATH
        or acknowledgement["content"].get("sha") != candidate["sha"]
        or type(acknowledgement.get("commit")) is not dict
        or type(acknowledgement["commit"].get("sha")) is not str
        or re.fullmatch(r"[0-9a-f]{40}", acknowledgement["commit"]["sha"]) is None):
        raise GenesisCreateStop("First private CREATE acknowledgement incomplete; HOLD")

    try:
        observed = read_after_independent()
        verified_sha, doc = journal.read_github_source(
            observed, genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key)
    except Exception:
        raise GenesisCreateStop("Independent signed genesis readback unavailable; HOLD") from None
    if (verified_sha != candidate["sha"] or doc["sequence"] != 0
        or doc["prior_document_sha"] is not None or doc["events"] != {}):
        raise GenesisCreateStop("Independent signed genesis readback diverged; HOLD")
    return {
        "schema": SCHEMA,
        "status": "OFFLINE_ONE_FAKE_CREATE_AND_SIGNED_GENESIS_READBACK_ONLY",
        "verified_genesis_blob_sha": verified_sha,
        "verified_sequence": 0,
        "injected_create_calls": 1,
        "synthetic_only_no_authentic_private_write": True,
        "production_private_puts": 0,
        "broker_gets": 0, "broker_posts": 0,
        "external_immutable_anchor_verified": False,
        "standing_mandate_authenticated": False,
        "live_order_authorized": False,
        "manual_per_trade_approval_required": False,
    }

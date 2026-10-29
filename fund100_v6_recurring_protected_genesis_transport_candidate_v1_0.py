"""Protected V6 recurring genesis: exact HTTP create protocol, not yet released.

This composes the EXISTING authentic signed original ACWI dual-principal
preflight with the signed empty V2 journal and a single GitHub Contents create.
The live entrypoint is HARD LOCKED. A rehearsal requires *injected transport*
and never constructs a GitHub network client. No broker imports, orders,
trading activation, or new operator approval. A later release must be made
only in a narrowly scoped protected main-only state writer, after review.
"""
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
from io import BytesIO
import json
import os
import re
from urllib.error import HTTPError

import fund100_v6_recurring_genesis_single_create_offline_v1_0 as offline
import fund100_v6_recurring_private_protected_getonly_v1_0 as private
import fund100_v6_recurring_event_signed_journal_v1_0 as journal

SCHEMA = "FUND100_V6_RECURRING_PROTECTED_GENESIS_HTTP_CANDIDATE_V1"
PRODUCTION_PRIVATE_GENESIS_CREATE_RELEASED = False
LIVE_BROKER_ORDERS_RELEASED = False
NO_AUTOMATIC_RETRY = True
REAL_PRIVATE_PUTS = REAL_BROKER_GETS = REAL_BROKER_POSTS = 0
CREATE_URL = "https://api.github.com/repos/" + journal.REPOSITORY + "/contents/" + journal.PATH
READ_URL = CREATE_URL + "?ref=main"
MAX_ACK_BYTES = 8192


class ProtectedGenesisStop(RuntimeError):
    pass


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch")
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"):
        raise ProtectedGenesisStop("Protected main HIGH/STOP context required")


def _tokens(env):
    names = ("FUND100_PRIVATE_STATE_READ_TOKEN",
             "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    tokens = []
    for name in names:
        value = env.get(name)
        if (type(value) is not str or len(value) < 10 or value != value.strip()
            or "\r" in value or "\n" in value):
            raise ProtectedGenesisStop("Protected private principal unavailable")
        tokens.append(value)
    if tokens[0] == tokens[1]:
        raise ProtectedGenesisStop("Independent private principals required")
    key_hex = env.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX")
    if type(key_hex) is not str or re.fullmatch(r"[0-9a-f]{64}", key_hex) is None:
        raise ProtectedGenesisStop("Original protected HMAC key unavailable")
    return tokens[0], tokens[1], bytes.fromhex(key_hex)


def _genesis_inputs(witness):
    if type(witness) is not dict:
        raise ProtectedGenesisStop("Authenticated original witness required")
    nonce = witness.get("original_public_genesis_nonce")
    account = witness.get("original_live_account_binding_sha256")
    if (type(nonce) is not str or type(account) is not str
        or re.fullmatch("[0-9a-f]{64}", nonce) is None
        or re.fullmatch("[0-9a-f]{64}", account) is None):
        raise ProtectedGenesisStop("Original signed account/genesis binding missing")
    genesis = private._recurring_genesis_candidate(nonce, account)
    return genesis, account


def _create_payload(candidate):
    """Bound GitHub Contents CREATE exactly, with no sha or overwrite path."""
    if (type(candidate) is not dict
        or set(candidate) != {"type", "path", "encoding", "sha", "content"}
        or candidate.get("path") != journal.PATH
        or candidate.get("type") != "file"
        or candidate.get("encoding") != "base64"
        or type(candidate.get("content")) is not str):
        raise ProtectedGenesisStop("Invalid exact signed candidate")
    return {
        "message": "Fund-100 signed recurring production genesis seq0 (never trade)",
        "content": candidate["content"],
        "branch": "main",
    }


def _one_response(ack, expected_sha):
    """Parse one injected 201 response, never trusting it as a trade permit."""
    if (type(ack) is not dict or set(ack) != {"status_code", "body"}
        or ack.get("status_code") != 201
        or type(ack.get("body")) is not dict):
        raise ProtectedGenesisStop("Private create acknowledgement unverified; never retry")
    data = ack["body"]
    if (type(data.get("content")) is not dict
        or type(data.get("commit")) is not dict
        or data["content"].get("path") != journal.PATH
        or data["content"].get("sha") != expected_sha
        or type(data["commit"].get("sha")) is not str
        or re.fullmatch("[0-9a-f]{40}", data["commit"]["sha"]) is None):
        raise ProtectedGenesisStop("Private create response incomplete; never retry")


def _read_post(*, reader_token, transport, genesis, account, key, expected_sha):
    try:
        remote = transport.get_after(reader_token, READ_URL)
        sha, doc = journal.read_github_source(
            remote, genesis_sha256=genesis,
            account_binding_sha256=account, key=key)
    except Exception:
        raise ProtectedGenesisStop("Independent signed post-create readback unknown; HOLD") from None
    if (sha != expected_sha or doc["sequence"] != 0
        or doc["prior_document_sha"] is not None or doc["events"] != {}):
        raise ProtectedGenesisStop("Independent signed post-create head mismatched; HOLD")
    return sha


def rehearse_with_injected_transport(*, environ, witness, transport):
    """Full transport-shaped sequence using an explicit FAKE only.

    The original proof calls the reviewed signed seq1/dual-404 implementation;
    'transport' supplies synthetic GETs and PUT. No implicit HTTP fallback,
    no production writer permission or LIVE order authority.
    """
    _context(environ)
    if (PRODUCTION_PRIVATE_GENESIS_CREATE_RELEASED is not False
        or LIVE_BROKER_ORDERS_RELEASED is not False
        or transport is None
        or getattr(transport, "synthetic_only", None) is not True):
        raise ProtectedGenesisStop("Only isolated synthetic rehearsal is released")
    reader, writer, key = _tokens(environ)
    if not all(callable(getattr(transport, n, None)) for n in (
        "original_get", "recurring_get", "create_once", "get_after")):
        raise ProtectedGenesisStop("Missing test-only transport methods")
    try:
        proof = private.inspect(
            environ=environ, witness=lambda: witness,
            original_transport=transport.original_get,
            recurring_transport=transport.recurring_get,
        )
        if (proof.get("status") != "AUTHENTICATED_DUAL_404_RECURRING_JOURNAL_ABSENT_HOLD"
            or proof.get("original_signed_legacy_seq1_verified_with_both_principals") is not True
            or proof.get("private_git_puts") != 0
            or proof.get("broker_posts") != 0):
            raise ProtectedGenesisStop("Real-schema original signed dual-principal proof absent")
        genesis, account = _genesis_inputs(witness)
        signed = offline.prepare_offline_genesis(
            genesis_sha256=genesis, account_binding_sha256=account, key=key)
    except ProtectedGenesisStop:
        raise
    except Exception:
        raise ProtectedGenesisStop("Original signed preflight uncertain; zero create") from None

    # A second pair of GETs narrows the TOCTOU window; the Contents CREATE
    # deliberately has no sha, so a concurrent existing file must be refused
    # by the provider rather than overwritten.
    try:
        a = transport.recurring_get_again(reader, READ_URL)
        b = transport.recurring_get_again(writer, READ_URL)
    except Exception:
        raise ProtectedGenesisStop("Immediate dual-principal pre-create GET unknown") from None
    if a is not None or b is not None:
        raise ProtectedGenesisStop("Recurring HEAD already present; zero create")

    payload = _create_payload(signed)
    if "sha" in payload or set(payload) != {"message", "content", "branch"}:
        raise ProtectedGenesisStop("Must be one create, never an overwrite")
    try:
        ack = transport.create_once(writer, CREATE_URL, payload)
    except Exception:
        raise ProtectedGenesisStop("Private create outcome ambiguous; never retry") from None
    _one_response(ack, signed["sha"])
    observed_sha = _read_post(
        reader_token=reader, transport=transport, genesis=genesis,
        account=account, key=key, expected_sha=signed["sha"])
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_AUTHENTICATED_SHAPED_FIRST_GENESIS_ONCE_NO_TRADE",
        "verified_genesis_blob_sha": observed_sha,
        "verified_sequence": 0,
        "synthetic_only": True,
        "fake_create_calls": 1,
        "production_private_puts": 0,
        "broker_posts": 0,
        "external_immutable_anchor_verified": False,
        "standing_live_mandate_released": False,
        "live_orders_authorized": False,
        "manual_per_trade_approval_required": False,
    }


def main():
    # No amount of environment secrets or workflows releases production
    # mutation merely by importing or executing this review-only candidate.
    raise ProtectedGenesisStop("Protected recurring production create NOT RELEASED")


if __name__ == "__main__":
    main()

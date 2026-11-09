"""Offline independently checked HEAD for Fund-100 private principal CAS.

Only a synthetic signed *index copy* is modeled. This is NOT a real
provider-immutable head, not separate production key custody and never
authorizes brokerage orders or deployment of excess deposits. Future
production must fetch the latest anchor from an independently trusted,
anti-rollback provider rather than taking its 'expected' SHA from a caller.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import re

import fund100_scalable_private_principal_cas_offline_v1_0 as principal

SCHEMA = "FUND100_SCALABLE_INDEPENDENT_HEAD_FIXTURE_V1"
MODE = "SYNTHETIC_SEPARATE_ANCHOR_NOT_PRODUCTION_IMMUTABLE"
DOMAIN = b"fund100-scalable-anchor-research-only-v1\x00"
ZERO_PREV = "0" * 64
MAX_SIZE = 4096
LIVE_HEAD_RELEASED = False
OWNER_AUTHORITY_RELEASED = False
ACTUAL_EXTERNAL_HEAD_QUERIES = ACTUAL_GITHUB_WRITES = BROKER_POSTS = 0
FIELDS = frozenset({
    "schema", "mode", "revision", "prior_anchor_sha256",
    "genesis_sha256", "account_binding_sha256", "principal_git_blob_sha",
    "principal_sequence", "issued_utc", "expires_utc",
    "owner_capital_mandate_authorized", "broker_kill_switch",
})


class AnchorStop(ValueError):
    pass


def _hex(raw, size):
    if type(raw) is not str or re.fullmatch(r"[0-9a-f]{" + str(size) + r"}", raw) is None:
        raise AnchorStop("Invalid synthetic SHA")
    return raw


def _instant(raw):
    return principal._instant(raw)


def _canon(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise AnchorStop("Noncanonical anchor state") from None


def _hmac(payload, key):
    if type(key) is not bytes or len(key) < 32:
        raise AnchorStop("Separate synthetic anchor fixture key required")
    return hmac.new(key, DOMAIN + _canon(payload), sha256).hexdigest()


def _pairs(pairs):
    out = {}
    for field, value in pairs:
        if field in out:
            raise AnchorStop("Duplicate anchor JSON key")
        out[field] = value
    return out


def _shape(payload, *, account_binding_sha256, genesis_sha256,
           expected_revision, expected_parent, checked_at_utc):
    if type(payload) is not dict or set(payload) != FIELDS:
        raise AnchorStop("Missing signed anchor fields")
    if (payload["schema"] != SCHEMA
        or payload["mode"] != MODE
        or payload["owner_capital_mandate_authorized"] is not False
        or payload["broker_kill_switch"] != "ENGAGED"):
        raise AnchorStop("Synthetic-only stopped anchor boundary changed")
    if (type(expected_revision) is not int or not 1 <= expected_revision <= 999999
        or type(payload["revision"]) is not int
        or payload["revision"] != expected_revision
        or payload["prior_anchor_sha256"] != _hex(expected_parent, 64)
        or (expected_revision == 1 and expected_parent != ZERO_PREV)
        or (expected_revision > 1 and expected_parent == ZERO_PREV)):
        raise AnchorStop("Unanchored, stale or rolled-back revision")
    if (payload["genesis_sha256"] != _hex(genesis_sha256, 64)
        or payload["account_binding_sha256"] != _hex(account_binding_sha256, 64)
        or _hex(payload["principal_git_blob_sha"], 40) is None
        or type(payload["principal_sequence"]) is not int
        or payload["principal_sequence"] < 0):
        raise AnchorStop("Wrong private capital account, genesis or blob")
    start = _instant(payload["issued_utc"])
    end = _instant(payload["expires_utc"])
    observed = _instant(checked_at_utc)
    if (not start <= observed < end or end - start > timedelta(days=7)
        or observed - start > timedelta(minutes=30)):
        raise AnchorStop("Stale, future or unbounded source head")
    return payload


def sign_fixture(*, key, genesis_sha256, account_binding_sha256,
                 principal_git_blob_sha, principal_sequence,
                 revision, prior_anchor_sha256, issued_utc, expires_utc):
    """Synthetic fixture only. This signature conveys ZERO owner authority."""
    payload = {
        "schema": SCHEMA, "mode": MODE,
        "revision": revision, "prior_anchor_sha256": prior_anchor_sha256,
        "genesis_sha256": genesis_sha256,
        "account_binding_sha256": account_binding_sha256,
        "principal_git_blob_sha": principal_git_blob_sha,
        "principal_sequence": principal_sequence,
        "issued_utc": issued_utc, "expires_utc": expires_utc,
        "owner_capital_mandate_authorized": False,
        "broker_kill_switch": "ENGAGED",
    }
    _shape(payload, account_binding_sha256=account_binding_sha256,
           genesis_sha256=genesis_sha256, expected_revision=revision,
           expected_parent=prior_anchor_sha256, checked_at_utc=issued_utc)
    return _canon(dict(payload, mac=_hmac(payload, key)))


def verify_fixture(*, raw, key, expected_anchor_sha256,
                   expected_revision, expected_parent,
                   genesis_sha256, account_binding_sha256,
                   checked_at_utc):
    """Compare HMAC plus externally SUPPLIED exact latest anchor digest.

    Passing an arbitrary caller-derived expected digest is NOT proof of an
    independently immutable or latest provider head. The return stays OFF.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SIZE:
        raise AnchorStop("Missing or oversized signed anchor source")
    if sha256(raw).hexdigest() != _hex(expected_anchor_sha256, 64):
        raise AnchorStop("Independent expected latest anchor digest mismatch")
    try:
        obj = json.loads(raw.decode("utf8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, TypeError):
        raise AnchorStop("Invalid synthetic anchor JSON") from None
    if type(obj) is not dict or set(obj) != FIELDS | {"mac"}:
        raise AnchorStop("Unknown signed anchor shape")
    signature = obj.pop("mac")
    if type(signature) is not str or re.fullmatch(r"[0-9a-f]{64}", signature) is None:
        raise AnchorStop("Missing synthetic anchor signature")
    if not hmac.compare_digest(signature, _hmac(obj, key)):
        raise AnchorStop("Synthetic anchor signature mismatch")
    _shape(obj, genesis_sha256=genesis_sha256,
           account_binding_sha256=account_binding_sha256,
           expected_revision=expected_revision, expected_parent=expected_parent,
           checked_at_utc=checked_at_utc)
    return {
        "stage": "SIGNED_SYNTHETIC_ANCHOR_INTEGRITY_ONLY",
        "private_git_blob_sha": obj["principal_git_blob_sha"],
        "private_sequence": obj["principal_sequence"],
        "synthetic_latest_anchor_digest_matched": True,
        "independent_provider_immutability_proved": False,
        "production_current_head_proved": False,
        "owner_capital_mandate_released": False,
        "trade_or_buy_authorized": False,
    }


def gated_principal_proposal(*, anchor_raw, separate_fixture_key,
                             expected_anchor_sha256, expected_anchor_revision,
                             expected_anchor_parent, checked_at_utc,
                             private_source, genesis_sha256,
                             account_binding_sha256, source, principal_fixture_key):
    """Strictly combine a synthetic latest-head fixture with private CAS.

    The production caller must later replace BOTH test fixture key sources,
    trust-anchor acquisition and synthetic broker source. No real writes.
    """
    head = verify_fixture(
        raw=anchor_raw, key=separate_fixture_key,
        expected_anchor_sha256=expected_anchor_sha256,
        expected_revision=expected_anchor_revision,
        expected_parent=expected_anchor_parent,
        checked_at_utc=checked_at_utc,
        genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256)
    if (type(private_source) is not dict
        or private_source.get("sha") != head["private_git_blob_sha"]):
        raise AnchorStop("Private CAS state does not equal anchored Git head")
    plan = principal.proposed_full_reconciliation(
        private_source=private_source,
        expected_current_sha=head["private_git_blob_sha"],
        expected_sequence=head["private_sequence"],
        genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256,
        source=source, key=principal_fixture_key)
    status = principal.public_status(plan)
    # PRIVATE plan contains signed contribution totals and must never be
    # printed or submitted to public CI artifacts. This API returns it only
    # to in-memory synthetic tests in this first offline version.
    return {
        "stage": "RESEARCH_ONLY_ANCHORED_PRIVATE_PRINCIPAL_CAS_PROPOSAL",
        "private_cas_proposal_for_fixture": plan.get("cas_private_proposal"),
        "safe_public_status": status,
        "real_head_anchor_authenticated": False,
        "actual_private_repo_written": False,
        "real_broker_source_authenticated": False,
        "real_settlement_verified": False,
        "owner_standing_mandate_released": False,
        "live_orders_authorized": False,
        "broker_POSTs": 0,
    }


def public_status(result):
    if (type(result) is not dict
        or result.get("stage") !=
           "RESEARCH_ONLY_ANCHORED_PRIVATE_PRINCIPAL_CAS_PROPOSAL"
        or result.get("live_orders_authorized") is not False
        or result.get("actual_private_repo_written") is not False):
        raise AnchorStop("No public result from unverified anchored proposal")
    return {
        "stage": result["stage"],
        "signed_source_integrity_only": True,
        "trusted_provider_anchor_present": False,
        "private_ledger_written": False,
        "owner_standing_mandate_released": False,
        "live_orders_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0,
    }

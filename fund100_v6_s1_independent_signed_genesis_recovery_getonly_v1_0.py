"""V6-S1 independent POST-bootstrap signed empty genesis recovery, GET ONLY.

This verifier is a separate process from one-time initial private Git PUT.
It requires the stored original HMAC, public nonce, Git blob SHA and a
separately retrieved original public issue comment to agree. This does NOT
prove an immutable head anchor or permit LIVE trades.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap

SCHEMA = "FUND100_V6_S1_INDEPENDENT_SIGNED_GENESIS_RECOVERY_GETONLY_V1"
ORIGINAL_PRIVATE_URL = bootstrap.PRODUCTION_READ_URL
ORIGINAL_PUBLIC_ISSUE_URL = (
    "https://api.github.com/repos/nicobouch97/fund100-research/issues/8"
)
PUBLIC_COMMENT_PREFIX = bootstrap.PUBLIC_COMMENT_URL
USER_BOT = "github-actions[bot]"
MAX_RESPONSE_BYTES = 40_000
NO_PRIVATE_GIT_WRITE = True
NO_ALPACA_NETWORK = True
NO_LIVE_ORDER_RELEASE = True


class RecoveryStop(RuntimeError):
    pass


def _number(x: object, label: str) -> int:
    if type(x) is not str or not re.fullmatch("[1-9][0-9]{0,18}", x):
        raise RecoveryStop("Invalid " + label)
    return int(x)


def _secret(value: object, label: str) -> str:
    if type(value) is not str or len(value) < 12 or value.strip() != value:
        raise RecoveryStop("Protected " + label + " missing")
    return value


def validate_sources(*, private_source: object, issue_comment: object,
                     public_comment_id: str, bootstrap_run_id: str,
                     hmac_hex: str, original_witness=None) -> dict:
    """Pure validation of original source bytes, no network or secret output."""
    comment_id = _number(public_comment_id, "public issue comment ID")
    run_id = _number(bootstrap_run_id, "original genesis workflow run ID")
    try:
        key = bootstrap._key(hmac_hex)
    except bootstrap.GenesisBootstrapStop:
        raise RecoveryStop("Private HMAC material unavailable/invalid") from None
    observed = witness.verify() if original_witness is None else original_witness
    if (type(observed) is not dict
        or observed.get("status") !=
            "PUBLIC_INDEPENDENT_INITIAL_GENESIS_NONCE_COMMITTED_NO_PRIVATE_LEDGER"
        or observed.get("private_state_genesis_created") is not False
        or observed.get("live_orders_authorized") is not False):
        raise RecoveryStop("Original independent public genesis witness changed")
    try:
        head_sha, content = cas._read_source(
            private_source,
            private_genesis=observed["original_public_genesis_nonce"],
            account_binding_sha256=observed["original_live_account_binding_sha256"],
            key=key)
    except (cas.CasStop, ValueError, TypeError):
        raise RecoveryStop("Private original signed Git genesis invalid") from None
    if (content.get("sequence") != 0
        or content.get("entries") != {}
        or content.get("prior_document_sha") is not None
        or content.get("migration") != cas.MIGRATION):
        raise RecoveryStop("Private state no longer initial empty genesis")
    digest = bootstrap.public_head_commitment(
        nonce=observed["original_public_genesis_nonce"],
        private_blob_sha=head_sha)
    expected_body = bootstrap.public_comment(
        digest=digest,
        run_url=(
            "https://github.com/nicobouch97/fund100-research/"
            "actions/runs/" + str(run_id)))
    if (type(issue_comment) is not dict
        or issue_comment.get("id") != comment_id
        or issue_comment.get("body") != expected_body
        or issue_comment.get("issue_url") != ORIGINAL_PUBLIC_ISSUE_URL
        or type(issue_comment.get("user")) is not dict
        or issue_comment["user"].get("login") != USER_BOT):
        raise RecoveryStop("External issue-8 commitment not authenticated")
    return {
        "schema": SCHEMA,
        "status": "GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY",
        "source_original_public_witness_proven": True,
        "private_genesis_HMAC_signature_and_original_account_binding_verified": True,
        "original_git_content_blob_SHA_matches_bytes": True,
        "independent_public_issue8_comment_digest_and_identity_verified": True,
        "private_ledger_sequence": 0,
        "original_empty_entries_count": 0,
        "independent_public_issue_comment_id": comment_id,
        "independently_immutable_rollback_anchor_proven": False,
        "future_private_head_progression_recovery_authorized": False,
        "production_trade_order_submission_authorized": False,
        "read_only_private_gets": 3,
        "read_only_public_gets": 1,
        "private_git_writes": 0,
        "broker_requests": 0,
        "broker_orders": 0,
        "private_raw_bytes": None,
        "private_git_blob_sha": None,
        "hmac_key_or_signature": None,
        "account_binding_or_account_id": None,
    }


def _get(*, url: str, token: str, transport=None) -> dict:
    allowed = (
        url == ORIGINAL_PRIVATE_URL or (
            url.startswith(PUBLIC_COMMENT_PREFIX)
            and re.fullmatch("[1-9][0-9]{0,18}",
                url[len(PUBLIC_COMMENT_PREFIX):]) is not None)
    )
    if not allowed:
        raise RecoveryStop("Unapproved recovery GET URL")
    request = Request(url, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + _secret(token, "GET token"),
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-independent-genesis-readonly-recovery",
    })
    if request.get_method() != "GET":
        raise RecoveryStop("Unapproved recovery HTTP method")
    transport = urlopen if transport is None else transport
    try:
        with transport(request, timeout=12) as res:
            if getattr(res, "status", None) != 200:
                raise RecoveryStop("Recovery GET missing/denied")
            raw = res.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RecoveryStop("Recovery GET source oversized")
        result = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeError):
        raise RecoveryStop("Original private/public recovery GET unavailable; redacted") from None
    if type(result) is not dict:
        raise RecoveryStop("Original GitHub response malformed")
    return result


def runtime(*, public_comment_id: str, bootstrap_run_id: str, read_token: str,
            hmac_hex: str, public_token: str, private_transport=None,
            public_transport=None, identity_fetch=identity.safe_get) -> dict:
    # Refuse all private-source GETs if original frozen account control/STOP
    # differs. Reviewable before any protected credentials are read.
    original = witness.verify()
    _secret(read_token, "existing private READ token")
    _secret(public_token, "public metadata token")
    _number(public_comment_id, "public issue comment ID")
    _number(bootstrap_run_id, "original bootstrap run ID")
    first = identity_fetch(url=identity.BASE, token=read_token)
    second = identity_fetch(
        url=identity.BASE + "/contents/README.md?ref=main", token=read_token)
    try:
        identity.classify(repo=first, readme=second)
    except identity.PrivateRepoProbeStop:
        raise RecoveryStop("Original private repository identity rejected") from None
    private = _get(
        url=ORIGINAL_PRIVATE_URL, token=read_token,
        transport=private_transport)
    comment = _get(
        url=PUBLIC_COMMENT_PREFIX + public_comment_id, token=public_token,
        transport=public_transport)
    return validate_sources(
        private_source=private, issue_comment=comment,
        public_comment_id=public_comment_id, bootstrap_run_id=bootstrap_run_id,
        hmac_hex=hmac_hex, original_witness=original)


def main() -> None:
    if (os.environ.get("GITHUB_REPOSITORY") !=
            "nicobouch97/fund100-research"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.environ.get("FUND100_RISK_LEVEL") != "HIGH"):
        raise RecoveryStop("Stopped protected main-only recovery validation")
    verified = runtime(
        public_comment_id=os.environ.get("FUND100_GENESIS_COMMENT_ID", ""),
        bootstrap_run_id=os.environ.get("FUND100_GENESIS_RUN_ID", ""),
        read_token=os.environ.get("FUND100_PRIVATE_STATE_READ_TOKEN", ""),
        hmac_hex=os.environ.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX", ""),
        public_token=os.environ.get("GITHUB_TOKEN", ""))
    for key in (
        "schema", "status",
        "source_original_public_witness_proven",
        "private_genesis_HMAC_signature_and_original_account_binding_verified",
        "independent_public_issue8_comment_digest_and_identity_verified",
        "private_ledger_sequence", "original_empty_entries_count",
        "independently_immutable_rollback_anchor_proven",
        "future_private_head_progression_recovery_authorized",
        "production_trade_order_submission_authorized",
        "private_git_writes", "broker_requests", "broker_orders",
    ):
        print(key + ": " + str(verified[key]))


if __name__ == "__main__":
    main()

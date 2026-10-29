"""Authenticate the FIRST current signed private recurring head AND immutable seq0.

This is the production read-only starting-head gate for the future event CAS.
Neither HMAC alone nor a public GitHub release alone can stop rollback.
Require BOTH independently authenticated private READ/WRITE-candidate principals
to see the exact sequence-0 original signed private journal AND provider-
immutable public release metadata AND the actual public asset bytes. Do not
return a write permit, standing mandate, broker request or event transition.

For any seq1+ HEAD, this GENESIS-ONLY verifier permanently HOLDs: future
controllers must verify separate immutable event-head continuity, NEVER
pretend that a seq0 anchor approves later state.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
import re
from urllib.request import Request, build_opener, urlopen
from urllib.error import HTTPError, URLError

import fund100_v6_recurring_immutable_genesis_v2_once_v1_0 as source
import fund100_v6_recurring_immutable_genesis_anchor_once_v1_0 as original
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as locked

SCHEMA = "FUND100_V6_RECURRING_IMMUTABLE_GENESIS_REAL_CURRENT_HEAD_GETONLY_V1"
WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-recurring-immutable-genesis-current-head-getonly.yml@refs/heads/main"
)
EXPECTED_RELEASE_ID = 427978301
EXPECTED_ASSET_ID = 688837795
EXPECTED_ASSET_SIZE = 680
EXPECTED_ASSET_SHA256 = "6aa37278f20e6393d1f33c0a7004377285f53094bd78b046fc3bc574258f0af1"
EXPECTED_MAIN_CREATE_SHA = "2542cf4521b32564c9b5442c9210f73c8267fd15"
RELEASE_URL = source.TAG_URL
DOWNLOAD_URL = source.DOWNLOAD_URL
MAX_META_BYTES = 35000
MAX_ASSET_BYTES = 4096
NO_PUBLIC_MUTATIONS = True
NO_PRIVATE_MUTATIONS = True
NO_BROKER_HTTP = True
NO_TRADE_PERMIT = True
GENESIS_SEQ0_ONLY = True

class HeadStop(RuntimeError):
    pass


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != source.PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"
        or not (NO_PUBLIC_MUTATIONS and NO_PRIVATE_MUTATIONS and
                NO_BROKER_HTTP and NO_TRADE_PERMIT and GENESIS_SEQ0_ONLY)
        or source.TAG == original.TAG
        or source.NO_PRIVATE_MUTATIONS is not True
        or source.NO_BROKER_NETWORK_OR_TRADING is not True):
        raise HeadStop("Protected main HIGH/STOP immutable seq0 read required")


def _get(*, url, token=None, transport=None):
    if url not in (RELEASE_URL, DOWNLOAD_URL):
        raise HeadStop("Unapproved immutable source endpoint")
    if url == RELEASE_URL:
        if (type(token) is not str or len(token) < 10
            or token.strip() != token or "\r" in token or "\n" in token):
            raise HeadStop("Separate public immutable anchor READ credential needed")
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "fund100-v6-recurring-genesis-immutable-head-getonly",
            "Cache-Control": "no-store",
        }
        sender = build_opener(locked._NoRedirect()).open
        limit = MAX_META_BYTES
    else:
        if token is not None:
            raise HeadStop("No public asset CDN credentials may be forwarded")
        headers = {
            "Accept": "application/octet-stream",
            "User-Agent": "fund100-v6-recurring-genesis-immutable-asset-anonymous",
        }
        # GitHub release downloads can redirect to a public CDN. No token is
        # ever present in this Request, including redirect destination.
        sender = urlopen
        limit = MAX_ASSET_BYTES
    request = Request(url, method="GET", headers=headers)
    try:
        with (sender if transport is None else transport)(request, timeout=12) as resp:
            if getattr(resp, "status", None) != 200:
                raise HeadStop("Immutable public GET not 200")
            data = resp.read(limit + 1)
        if len(data) > limit:
            raise HeadStop("Immutable provider source oversized")
        return data
    except HeadStop:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError):
        raise HeadStop("Immutable provider GET uncertain; HOLD") from None


def _published_exact(meta, expected_bytes):
    if (type(meta) is not dict
        or meta.get("id") != EXPECTED_RELEASE_ID
        or meta.get("tag_name") != source.TAG
        or meta.get("target_commitish") != EXPECTED_MAIN_CREATE_SHA
        or meta.get("draft") is not False
        or meta.get("immutable") is not True
        or type(meta.get("published_at")) is not str
        or not meta["published_at"]
        or type(meta.get("author")) is not dict
        or meta["author"].get("login") != "github-actions[bot]"
        or type(meta.get("assets")) is not list or len(meta["assets"]) != 1):
        raise HeadStop("Provider immutable release identity NOT verified")
    asset = meta["assets"][0]
    if (type(asset) is not dict or asset.get("id") != EXPECTED_ASSET_ID
        or asset.get("name") != source.ASSET
        or asset.get("size") != EXPECTED_ASSET_SIZE
        or asset.get("state") != "uploaded"
        or asset.get("digest") != "sha256:" + EXPECTED_ASSET_SHA256
        or asset.get("browser_download_url") != DOWNLOAD_URL
        or len(expected_bytes) != EXPECTED_ASSET_SIZE
        or sha256(expected_bytes).hexdigest() != EXPECTED_ASSET_SHA256):
        raise HeadStop("Immutable public asset hash/identity NOT verified")


def inspect(*, environ=None, transport=None, private_inspect=None,
            private_get=None, witness_doc=None):
    env = dict(os.environ if environ is None else environ)
    _context(env)
    if transport is not None and (
        private_inspect is None or private_get is None or witness_doc is None):
        raise HeadStop("Injected regression sources must be exclusively synthetic")

    # _signed_current_head verifies both original private principal HMACs,
    # both recurring private HMAC views, sequence=0, no event, initial pinned
    # Git blob SHA, canonical exact namespace and original genesis witness.
    def private():
        try:
            return source._signed_current_head(
                env=env, witness_doc=witness_doc,
                inspect_fn=private_inspect, get_fn=private_get)
        except Exception:
            raise HeadStop("Current dual-principal original signed seq0 unverified; HOLD") from None
    before = private()
    expected = source._canon(before)
    if (before.get("private_signed_genesis_git_blob_sha1")
        != source.PINNED_INITIAL_BLOB_SHA
        or before.get("signed_sequence") != 0
        or before.get("future_signed_heads_anchored") is not False
        or before.get("broker_orders_authorized") is not False):
        raise HeadStop("Private current HEAD is not original signed seq0")

    # Distinct public admin READ token; no publisher credential is used
    # for public release mutation and no private broker endpoint is touched.
    admin = env.get("FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN")
    metadata_bytes = _get(
        url=RELEASE_URL, token=admin, transport=transport)
    try:
        meta = json.loads(metadata_bytes.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise HeadStop("Public immutable metadata malformed") from None
    _published_exact(meta, expected)
    downloaded = _get(
        url=DOWNLOAD_URL, token=None, transport=transport)
    if downloaded != expected:
        raise HeadStop("Anonymous public immutable asset != current signed seq0")
    if private() != before:
        raise HeadStop("Private signed journal changed during immutable verification")

    return {
        "schema": SCHEMA,
        "status": "ACTUAL_PRIVATE_SIGNED_GENESIS_SEQ0_MATCHES_PROVIDER_IMMUTABLE_PUBLIC_ASSET",
        "private_seq0_blob_sha1": before["private_signed_genesis_git_blob_sha1"],
        "private_sequence": 0,
        "immutable_release_id": EXPECTED_RELEASE_ID,
        "immutable_asset_id": EXPECTED_ASSET_ID,
        "immutable_asset_sha256": EXPECTED_ASSET_SHA256,
        "signed_current_genesis_and_immutable_public_asset_verified": True,
        "future_signed_event_head_anchored": False,
        "production_private_CAS_authorized": False,
        "live_broker_order_authorized": False,
        "private_git_puts": 0,
        "public_mutations": 0,
        "broker_calls": 0,
        "standing_manual_approval_per_trade_required": False,
    }


def main():
    report = inspect()
    print(report["status"])
    print("Authenticated immutable original seq0 Git blob:", report["private_seq0_blob_sha1"])
    print("Provider immutable release/asset verified:",
          report["immutable_release_id"], report["immutable_asset_id"])
    print("NO private mutation, no broker orders; future signed HEAD still HOLD.")


if __name__ == "__main__":
    main()

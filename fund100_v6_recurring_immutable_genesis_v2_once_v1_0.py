"""One NEW DISTINCT immutable public genesis fingerprint from signed V6 private seq0.

Public asset contains only signed-document hashes and repository path, never
the signed private HMAC document, key or broker account identity. The reviewed v2 protected main-push job may publish ONE new, uniquely tagged
release with correctly typed GitHub API fields and scoped github.token. Any uncertainty
permanently HOLDs; no retry, private mutation, broker credential or order.
This initial anchor DOES NOT cover future seq1+ updates; a head-by-head
anti-rollback protocol remains required before trading is released.
"""
from __future__ import annotations

from base64 import b64decode
from hashlib import sha256
import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_protected_getonly_v1_0 as private
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as existing

SCHEMA = "FUND100_V6_RECURRING_IMMUTABLE_GENESIS_ASSET_V2"
TAG = "fund100-v6-recurring-signed-genesis-head-v2-20261029"
ASSET = "fund100-v6-recurring-signed-genesis-head-v2.json"
PUBLIC_REPO = "nicobouch97/fund100-research"
BASE = "https://api.github.com/repos/" + PUBLIC_REPO
SETTING_URL = BASE + "/immutable-releases"
RELEASE_URL = BASE + "/releases"
TAG_URL = RELEASE_URL + "/tags/" + TAG
DOWNLOAD_URL = ("https://github.com/" + PUBLIC_REPO + "/releases/download/"
                + TAG + "/" + ASSET)
WORKFLOW_REF = (PUBLIC_REPO + "/.github/workflows/"
                "fund100-v6-recurring-immutable-genesis-v2-once.yml@refs/heads/main")
PINNED_INITIAL_BLOB_SHA = "a11f2b2e5fb971516914644d4e031f2eb5d80abf"
PINNED_REAL_CREATION_RUN = 40876805816
MAX_HTTP_BYTES = 25000
NO_PRIVATE_MUTATIONS = True
NO_BROKER_NETWORK_OR_TRADING = True
NO_RETRY_AFTER_ANY_PUBLIC_MUTATION = True
ORIGINAL_V1_RELEASE_POST_PERMANENTLY_RETIRED = True
V2_DISTINCT_TAG_FROM_CONSUMED_V1 = True
RELEASE_PUBLISHER_IS_SCOPED_MAIN_GITHUB_TOKEN = True


class AnchorStop(RuntimeError):
    pass


def _canon(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("ascii")


def _check_context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"
        or re.fullmatch(r"[a-f0-9]{40}", env.get("GITHUB_SHA", "")) is None):
        raise AnchorStop("Exact protected main push HIGH/STOP required")


def _credentials(env):
    names = ("FUND100_PRIVATE_STATE_READ_TOKEN",
             "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
             "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
             "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
    items = [env.get(k) for k in names]
    if (any(type(s) is not str or len(s) < 10 or s.strip() != s
            or "\r" in s or "\n" in s for s in items)
        or len(set(items)) != 4):
        raise AnchorStop("Four independently scoped protected principals required")
    key = env.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX")
    if type(key) is not str or re.fullmatch(r"[a-f0-9]{64}", key) is None:
        raise AnchorStop("Private signing key absent")
    return (*items, bytes.fromhex(key))


def _signed_current_head(*, env, witness_doc=None, inspect_fn=None, get_fn=None):
    """Require original signed legacy seq1 and current V2 seq0 read by both."""
    read, writer, _, _, key = _credentials(env)
    try:
        w = witness.verify() if witness_doc is None else witness_doc
        if type(w) is not dict:
            raise ValueError("witness")
        original = (private.inspect(environ=env)
                    if inspect_fn is None else inspect_fn(env))
        if (original.get("status")
            != "HMAC_VERIFIED_CANDIDATE_RECURRING_HEAD_STILL_NO_IMMUTABLE_ANCHOR"
            or original.get("original_signed_legacy_seq1_verified_with_both_principals")
            is not True or original.get("recurring_signed_head_verified") is not True
            or original.get("broker_posts") != 0):
            raise ValueError("two-principal original signed evidence")
        fetch = private._get_recurring if get_fn is None else get_fn
        left = fetch(token=read)
        right = fetch(token=writer)
        if (type(left) is not dict or type(right) is not dict
            or any(left.get(n) != right.get(n)
                   for n in ("sha", "path", "content", "encoding", "type"))):
            raise ValueError("private current head diverged")
        genesis = private._recurring_genesis_candidate(
            w["original_public_genesis_nonce"], w["original_live_account_binding_sha256"])
        blob, state = journal.read_github_source(
            left, genesis_sha256=genesis,
            account_binding_sha256=w["original_live_account_binding_sha256"], key=key)
        if (blob != PINNED_INITIAL_BLOB_SHA or state["sequence"] != 0
            or state["prior_document_sha"] is not None or state["events"]):
            raise ValueError("current private head is not original pinned seq0")
        raw = b64decode(left["content"].replace("\r", "").replace("\n", ""), validate=True)
    except Exception:
        raise AnchorStop("Authentic original signed seq0 current head missing or changed") from None
    return {
        "schema": SCHEMA,
        "subject": "FIRST_AUTHENTIC_V6_RECURRING_SIGNED_GENESIS_ONLY_NO_ORDERS",
        "private_repository": journal.REPOSITORY,
        "private_path": journal.PATH,
        "private_branch": "main",
        "signed_sequence": 0,
        "original_genesis_creation_workflow_run_id": PINNED_REAL_CREATION_RUN,
        "private_signed_genesis_git_blob_sha1": blob,
        "private_signed_document_sha256": sha256(raw).hexdigest(),
        "original_public_witness_git_blob_sha1":
            witness.WITNESS_BLOB_SHA1,
        "future_signed_heads_anchored": False,
        "broker_orders_authorized": False,
    }


def _request(*, method, url, token, data=None, transport=None, allow_absent=False):
    """Bound 5 exact GitHub endpoints, disable redirects and ALL retry."""
    allowed = (SETTING_URL, TAG_URL, RELEASE_URL)
    upload = re.fullmatch(
        r"https://uploads\.github\.com/repos/nicobouch97/fund100-research/"
        r"releases/([1-9][0-9]{0,18})/assets\?name=" + re.escape(ASSET), url)
    patch = re.fullmatch(
        re.escape(RELEASE_URL) + r"/([1-9][0-9]{0,18})", url)
    if (type(token) is not str or len(token) < 10
        or method not in ("GET", "POST", "PATCH")
        or (method == "GET" and url not in (SETTING_URL, TAG_URL))
        or (method == "POST" and url != RELEASE_URL and upload is None)
        or (method == "PATCH" and patch is None)
        or (method == "GET" and data is not None)
        or (method != "GET" and (type(data) is not bytes or
                                 len(data) > MAX_HTTP_BYTES))):
        raise AnchorStop("Unexpected immutable release endpoint/verb/payload")
    req = Request(url, method=method, data=data, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "Content-Type": ("application/json"
                         if url == RELEASE_URL or patch is not None
                         else "application/octet-stream"),
        "User-Agent": "fund100-v6-recurring-immutable-genesis-only",
    })
    sender = (build_opener(existing._NoRedirect()).open
              if transport is None else transport)
    try:
        with sender(req, timeout=12) as resp:
            status = getattr(resp, "status", None)
            raw = resp.read(MAX_HTTP_BYTES + 1)
        if (len(raw) > MAX_HTTP_BYTES
            or status != {("GET", SETTING_URL): 200,
                          ("GET", TAG_URL): 200,
                          ("POST", RELEASE_URL): 201}.get((method, url),
                               201 if upload is not None else 200)):
            raise AnchorStop("GitHub immutable release HTTP response ambiguous")
        obj = json.loads(raw.decode("utf-8"),
                         object_pairs_hook=journal._json_unique)
        if type(obj) is not dict:
            raise AnchorStop("Invalid immutable release metadata")
        return obj
    except HTTPError as exc:
        if allow_absent is True and url == TAG_URL and method == "GET" and exc.code == 404:
            return None
        raise AnchorStop("GitHub immutable release request failed; NEVER RETRY") from None
    except Exception:
        raise AnchorStop("GitHub immutable release outcome unknown; NEVER RETRY") from None


def publish_once(*, environ, transport=None, inspect_fn=None, get_fn=None,
                 witness_doc=None):
    """Retired V2 creator: only offline injected synthetic scenarios remain."""
    if transport is None:
        raise AnchorStop("Original V2 public draft/asset already exists; production RETIRED")
    env = dict(environ)
    _check_context(env)
    if (not ORIGINAL_V1_RELEASE_POST_PERMANENTLY_RETIRED
        or not V2_DISTINCT_TAG_FROM_CONSUMED_V1
        or not RELEASE_PUBLISHER_IS_SCOPED_MAIN_GITHUB_TOKEN):
        raise AnchorStop("Original release consumed or new scoped publisher not verified")
    read, writer, admin, publisher, _ = _credentials(env)
    if (transport is not None
        and (inspect_fn is None or get_fn is None or witness_doc is None)):
        raise AnchorStop("Injected test transport requires all synthetic original sources")
    manifest = _signed_current_head(
        env=env, witness_doc=witness_doc, inspect_fn=inspect_fn, get_fn=get_fn)
    asset = _canon(manifest)
    digest = "sha256:" + sha256(asset).hexdigest()

    send = (lambda **kwargs: _request(transport=transport, **kwargs))
    setting = send(method="GET", url=SETTING_URL, token=admin)
    if (setting.get("enabled") is not True
        or type(setting.get("enforced_by_owner")) is not bool):
        raise AnchorStop("Provider-immutable release mode absent")
    if send(method="GET", url=TAG_URL, token=publisher, allow_absent=True) is not None:
        raise AnchorStop("Original genesis immutable anchor already exists; no repeat")

    # Recheck original authenticated seq0 immediately BEFORE first release POST.
    if _signed_current_head(
        env=env, witness_doc=witness_doc, inspect_fn=inspect_fn, get_fn=get_fn
    ) != manifest:
        raise AnchorStop("Private current signed head changed; no publication")

    payload = _canon({
        "tag_name": TAG, "target_commitish": env["GITHUB_SHA"],
        "name": "Fund-100 V6 immutable signed recurring genesis V2 (NO TRADES)",
        "body": "Public genesis fingerprint only. No journal contents, credentials, trading mandate or authority.",
        "draft": True, "prerelease": False,
        "make_latest": "false", "generate_release_notes": False,
    })
    # No repeat, even if the first draft acknowledgement is lost.
    draft = send(method="POST", url=RELEASE_URL, token=publisher, data=payload)
    release_id = draft.get("id")
    if (type(release_id) is not int or release_id <= 0
        or draft.get("tag_name") != TAG or draft.get("draft") is not True
        or draft.get("target_commitish") != env["GITHUB_SHA"]
        or draft.get("assets") != []):
        raise AnchorStop("First release draft uncertain; NEVER RETRY")
    upload_url = ("https://uploads.github.com/repos/" + PUBLIC_REPO
                  + "/releases/" + str(release_id) + "/assets?name=" + ASSET)
    uploaded = send(method="POST", url=upload_url, token=publisher, data=asset)
    if (uploaded.get("name") != ASSET
        or uploaded.get("size") != len(asset)
        or uploaded.get("state") != "uploaded"
        or uploaded.get("digest") != digest
        or uploaded.get("browser_download_url") != DOWNLOAD_URL):
        raise AnchorStop("Uploaded immutable asset uncertain; NEVER RETRY")

    pub = send(method="PATCH", url=RELEASE_URL + "/" + str(release_id),
               token=publisher, data=b'{"draft":false}')
    if (pub.get("id") != release_id or pub.get("draft") is not False
        or pub.get("immutable") is not True
        or pub.get("tag_name") != TAG):
        raise AnchorStop("Published release immutability unverified; NEVER RETRY")
    # Independently re-fetch tag via distinct public read and verify digest.
    latest = send(method="GET", url=TAG_URL, token=admin)
    if (latest.get("id") != release_id or latest.get("draft") is not False
        or latest.get("immutable") is not True
        or latest.get("tag_name") != TAG
        or type(latest.get("assets")) is not list or len(latest["assets"]) != 1
        or latest["assets"][0].get("digest") != digest
        or latest["assets"][0].get("browser_download_url") != DOWNLOAD_URL):
        raise AnchorStop("Independent published immutable asset check failed; HOLD")
    if _signed_current_head(
        env=env, witness_doc=witness_doc, inspect_fn=inspect_fn, get_fn=get_fn
    ) != manifest:
        raise AnchorStop("Private signed genesis changed after public publish; HOLD")
    return {
        "status": "FIRST_AUTHENTIC_RECURRING_GENESIS_PROVIDER_IMMUTABLE_ANCHOR_VERIFIED",
        "tag": TAG,
        "asset": ASSET,
        "private_genesis_blob_sha": PINNED_INITIAL_BLOB_SHA,
        "public_asset_sha256": sha256(asset).hexdigest(),
        "provider_immutable": True,
        "future_sequence_heads_anchored": False,
        "live_broker_orders_authorized": False,
        "one_time": True,
    }


def main():
    result = publish_once(environ=os.environ)
    print(result["status"])
    print("Immutable public tag:", result["tag"])
    print("Public asset SHA256:", result["public_asset_sha256"])
    print("Only first signed seq0 anchored; NO LIVE ORDERS, future HEAD still HOLD.")


if __name__ == "__main__":
    main()

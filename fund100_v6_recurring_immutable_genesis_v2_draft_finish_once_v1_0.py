"""Complete exact existing GitHub release draft once; NO new release or upload.

Protected run 40892690151 actually created GitHub draft release 427978301 and
asset 688837795. The asset upload returned an *untagged temporary URL*,
which the initial v2 candidate treated as uncertain and HOLDed. Independent
provider GET proved a single 680-byte asset and SHA256 digest.

Only after authenticated signed private seq0 and TWO independent public
metadata reads prove the EXACT original asset may this reviewed new job send
ONE PATCH draft=false. It sends ZERO release/asset POSTs, private writes or
broker calls, and NEVER retries a failed/ambiguous PATCH acknowledgement.
"""
from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import fund100_v6_recurring_immutable_genesis_v2_once_v1_0 as base
import fund100_v6_recurring_immutable_genesis_anchor_once_v1_0 as old
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as existing

SCHEMA = "FUND100_V6_RECURRING_V2_IMMUTABLE_DRAFT_EXACT_RECOVERY_V1"
WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-recurring-immutable-genesis-v2-draft-finish-once.yml@refs/heads/main"
)
ORIGINAL_V2_CREATE_RUN_ID = 40892690151
ORIGINAL_V2_CREATE_MAIN_SHA = "2542cf4521b32564c9b5442c9210f73c8267fd15"
EXACT_DRAFT_ID = 427978301
EXACT_ASSET_ID = 688837795
EXACT_ASSET_SIZE = 680
EXACT_ASSET_DIGEST = "sha256:6aa37278f20e6393d1f33c0a7004377285f53094bd78b046fc3bc574258f0af1"
DRAFT_GET_URL = base.RELEASE_URL + "/" + str(EXACT_DRAFT_ID)
ASSET_GET_URL = base.RELEASE_URL + "/assets/" + str(EXACT_ASSET_ID)
DRAFT_PATCH_URL = DRAFT_GET_URL
MAX_BYTES = 50000
MAX_HEAD_ATTEMPTS = 1
NO_PUBLIC_POST = True
NO_PRIVATE_MUTATIONS = True
NO_BROKER_NETWORK = True
NO_AUTOMATIC_RETRY = True
ORIGINAL_V1_RELEASE_POST_RETIRED = True
NO_NEW_DRAFT_OR_ASSET = True


class DraftStop(RuntimeError):
    pass


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != base.PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"
        or re.fullmatch(r"[a-f0-9]{40}", env.get("GITHUB_SHA", "")) is None
        or not NO_PUBLIC_POST or not NO_PRIVATE_MUTATIONS or
        not NO_BROKER_NETWORK or not NO_AUTOMATIC_RETRY or
        not NO_NEW_DRAFT_OR_ASSET or
        old.TAG == base.TAG or
        not base.ORIGINAL_V1_RELEASE_POST_PERMANENTLY_RETIRED):
        raise DraftStop("Original exact protected HIGH/STOP draft-finish context required")


def _read(*, token, url, transport=None):
    if url not in (DRAFT_GET_URL, ASSET_GET_URL) or (
        type(token) is not str or len(token) < 10):
        raise DraftStop("Unexpected GitHub draft/asset read path")
    req = Request(url, method="GET", headers={
        "Authorization":"Bearer " + token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-v6-signed-v2-draft-finish-only",
    })
    sender = build_opener(existing._NoRedirect()).open if transport is None else transport
    try:
        with sender(req, timeout=12) as response:
            status = getattr(response, "status", None)
            raw = response.read(MAX_BYTES + 1)
        if status != 200 or len(raw) > MAX_BYTES:
            raise DraftStop("Bounded original release GET unverified")
        obj = json.loads(raw.decode("utf-8"))
        if type(obj) is not dict:
            raise DraftStop("GitHub release metadata schema invalid")
        return obj
    except DraftStop: raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError):
        raise DraftStop("Original release read unknown; zero PATCH") from None


def _verify_asset(m, *, expected_bytes):
    digest = "sha256:" + sha256(expected_bytes).hexdigest()
    if (digest != EXACT_ASSET_DIGEST or len(expected_bytes) != EXACT_ASSET_SIZE
        or type(m) is not dict
        or m.get("id") != EXACT_ASSET_ID
        or m.get("name") != base.ASSET
        or m.get("size") != EXACT_ASSET_SIZE
        or m.get("digest") != digest
        or m.get("state") != "uploaded"):
        raise DraftStop("Exact original uploaded asset identity/digest unknown")


def _verify_draft(*, draft, expected_bytes):
    if (type(draft) is not dict
        or draft.get("id") != EXACT_DRAFT_ID
        or draft.get("tag_name") != base.TAG
        or draft.get("target_commitish") != ORIGINAL_V2_CREATE_MAIN_SHA
        or draft.get("draft") is not True
        or draft.get("prerelease") is not False
        or type(draft.get("assets")) is not list or len(draft["assets"]) != 1):
        raise DraftStop("Exact unmodified original v2 draft unknown")
    _verify_asset(draft["assets"][0], expected_bytes=expected_bytes)


def run_once(*, environ=None, transport=None, private_inspect=None,
             private_get=None, witness_doc=None):
    """One strictly verified existing-draft PATCH, or permanent HOLD.

    Synthetic injected transport is only for regression tests; production
    always reauthenticates signed private source and GitHub release remotely.
    """
    env = dict(os.environ if environ is None else environ)
    _context(env)
    if transport is not None and (
        private_inspect is None or private_get is None or witness_doc is None):
        raise DraftStop("Synthetic transport requires entirely synthetic sources")
    # Original release/token contract: two distinct private principals,
    # one separate admin READ, one scoped Actions Contents(write).
    reader, writer, admin, publisher, key = base._credentials(env)
    def manifest():
        try:
            return base._signed_current_head(
                env=env, witness_doc=witness_doc,
                inspect_fn=private_inspect, get_fn=private_get)
        except Exception:
            raise DraftStop("Current original signed private seq0 unverified") from None
    first = manifest()
    asset = base._canon(first)
    _verify_asset({
        "id": EXACT_ASSET_ID, "name": base.ASSET,
        "size": len(asset), "digest": "sha256:" + sha256(asset).hexdigest(),
        "state":"uploaded",
    }, expected_bytes=asset)

    def request(**kwargs):
        return base._request(transport=transport, **kwargs)

    setting = request(method="GET", url=base.SETTING_URL, token=admin)
    if (setting.get("enabled") is not True
        or type(setting.get("enforced_by_owner")) is not bool):
        raise DraftStop("Provider immutable release protection unavailable; no PATCH")

    # Draft itself and its uploaded asset are two independent authenticated
    # provider GETs. Verify exact original IDs, tag, source main SHA, bytes
    # length and sha256. A temporary /untagged URL is normal BEFORE publish.
    draft = _read(token=publisher, url=DRAFT_GET_URL, transport=transport)
    _verify_draft(draft=draft, expected_bytes=asset)
    independent_asset = _read(
        token=publisher, url=ASSET_GET_URL, transport=transport)
    _verify_asset(independent_asset, expected_bytes=asset)

    # A published release already exists? This continuation must HOLD.
    existing_tag = request(
        method="GET", url=base.TAG_URL, token=admin, allow_absent=True)
    if existing_tag is not None:
        raise DraftStop("Original V2 tag already published, no PATCH")

    # Second authenticated recheck immediately before the irreversible PATCH.
    if manifest() != first:
        raise DraftStop("Original signed private seq0 changed; zero PATCH")
    _verify_draft(
        draft=_read(token=publisher, url=DRAFT_GET_URL, transport=transport),
        expected_bytes=asset)
    _verify_asset(
        _read(token=publisher, url=ASSET_GET_URL, transport=transport),
        expected_bytes=asset)

    try:
        # ONE MUTATION ONLY. There is NO release POST, asset POST, private PUT,
        # broker POST, automatic retry, deletion or duplicate creation.
        result = request(
            method="PATCH", url=DRAFT_PATCH_URL,
            token=publisher, data=b'{"draft":false}')
    except Exception:
        raise DraftStop("First and only release publish PATCH outcome unknown; NEVER RETRY") from None
    if (result.get("id") != EXACT_DRAFT_ID
        or result.get("draft") is not False
        or result.get("immutable") is not True
        or result.get("tag_name") != base.TAG):
        raise DraftStop("Original V2 release PATCH may have succeeded; NEVER RETRY")
    latest = request(method="GET", url=base.TAG_URL, token=admin)
    if (latest.get("id") != EXACT_DRAFT_ID
        or latest.get("draft") is not False
        or latest.get("immutable") is not True
        or latest.get("tag_name") != base.TAG
        or type(latest.get("assets")) is not list
        or len(latest["assets"]) != 1):
        raise DraftStop("Independent immutable public head not verified; HOLD")
    _verify_asset(latest["assets"][0], expected_bytes=asset)
    if latest["assets"][0].get("browser_download_url") != base.DOWNLOAD_URL:
        raise DraftStop("Published download URL not exact canonical tag")
    if manifest() != first:
        raise DraftStop("Signed private sequence changed after publication; HOLD")

    return {
        "schema":SCHEMA,
        "status":"PRODUCTION_V2_EXISTING_DRAFT_IMMUTABLE_GENESIS_VERIFIED",
        "immutable_release_tag":base.TAG,
        "published_release_id":EXACT_DRAFT_ID,
        "signed_private_sequence":0,
        "verified_private_genesis_blob_sha":base.PINNED_INITIAL_BLOB_SHA,
        "public_asset_sha256":sha256(asset).hexdigest(),
        "provider_immutable":True,
        "future_signed_head_events_anchored":False,
        "broker_orders_authorized":False,
        "private_mutations":0,
        "public_release_posts":0,
        "public_asset_posts":0,
        "public_release_patches":1,
        "original_v1_v2_create_attempts_retried":False,
    }


def main():
    result = run_once()
    print(result["status"])
    print("Original signed private seq0 Git blob:", result["verified_private_genesis_blob_sha"])
    print("Immutable release tag:", result["immutable_release_tag"])
    print("Public asset sha256:", result["public_asset_sha256"])
    print("Future signed heads still HOLD; NO LIVE BROKER ORDERS")


if __name__ == "__main__":
    main()

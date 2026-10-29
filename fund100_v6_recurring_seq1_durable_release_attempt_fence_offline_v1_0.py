"""HMAC-signed durable per-action attempt fence for future recurring seq1.

A future qualified first strategy-event reservation must be persisted in the
existing private recurring journal before any public immutable release work.
This distinct private document tracks the release CREATE, UPLOAD and PUBLISH
*attempts*, with an exact GitHub Contents old-SHA CAS on each transition.
Before an irreversible request, the controller must persist ATTEMPTED_UNCERTAIN
and independently read back its HMAC and exact Git blob. After an ambiguous
request, it MUST NOT retry the same action, even after restart.

This module only builds/verifies offline signed plans. It cannot create a
private fence remotely, submit GitHub PUT or publish a release. HMAC alone
does not prevent rollback. A future production worker must authenticate the
current signed seq1 HEAD, independent provider GETs and external anti-rollback
watermark before enabling any step.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from hashlib import sha256
import hmac
import json
import re

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 as chain
import fund100_v6_recurring_seq1_immutable_release_recovery_locked_v1_0 as release

SCHEMA = "FUND100_V6_RECURRING_SEQ1_RELEASE_ATTEMPTS_PRIVATE_HMAC_CAS_V1"
DOMAIN = b"fund100-v6-recurring-public-release-fences-v1\x00"
REPOSITORY = journal.REPOSITORY
PATH = "state/v6_recurring_seq1_release_attempts.json"
MODE = "OFFLINE_SIGNED_PLANS_ONLY_NO_EXTERNAL_ACTION"
STEPS = ("create", "upload", "publish")
STATUS = ("NEVER_ATTEMPTED", "ATTEMPTED_UNCERTAIN",
          "EXACT_REMOTE_SUCCESS_VERIFIED")
ACTION_TO_STEP = {
    "CREATE_DRAFT": "create",
    "UPLOAD_EXACT_ASSET": "upload",
    "PUBLISH_EXISTING_DRAFT": "publish",
}
NEXT_AFTER_VERIFIED = {
    "create": "UPLOAD_EXACT_ASSET",
    "upload": "PUBLISH_EXISTING_DRAFT",
    "publish": "COMPLETE_IMMUTABLE",
}
STATES = (
    ("NEVER_ATTEMPTED", "NEVER_ATTEMPTED", "NEVER_ATTEMPTED"),
    ("ATTEMPTED_UNCERTAIN", "NEVER_ATTEMPTED", "NEVER_ATTEMPTED"),
    ("EXACT_REMOTE_SUCCESS_VERIFIED", "NEVER_ATTEMPTED", "NEVER_ATTEMPTED"),
    ("EXACT_REMOTE_SUCCESS_VERIFIED", "ATTEMPTED_UNCERTAIN", "NEVER_ATTEMPTED"),
    ("EXACT_REMOTE_SUCCESS_VERIFIED", "EXACT_REMOTE_SUCCESS_VERIFIED", "NEVER_ATTEMPTED"),
    ("EXACT_REMOTE_SUCCESS_VERIFIED", "EXACT_REMOTE_SUCCESS_VERIFIED", "ATTEMPTED_UNCERTAIN"),
    ("EXACT_REMOTE_SUCCESS_VERIFIED", "EXACT_REMOTE_SUCCESS_VERIFIED",
     "EXACT_REMOTE_SUCCESS_VERIFIED"),
)
MAX_BYTES = 4096
PRODUCTION_FENCE_INITIALIZATION_RELEASED = False
PRODUCTION_SIGNED_CAS_FENCE_WRITES_RELEASED = False
PRODUCTION_RECOVERY_SOURCE_AUTHENTICATED = False
LIVE_BROKER_ORDER_RELEASED = False
NO_GITHUB_NETWORK = True
NO_PRIVATE_MUTATIONS = True
NO_BROKER_NETWORK = True
GENESIS_ROLLBACK_ANCHOR_SEQ0_ONLY = True


class FenceHold(ValueError):
    pass


def _key(secret):
    if type(secret) is not bytes or len(secret) < 32:
        raise FenceHold("Dedicated HMAC secret key must be at least 32 bytes")
    return secret


def _hex(v, n):
    if type(v) is not str or re.fullmatch("[a-f0-9]{" + str(n) + "}", v) is None:
        raise FenceHold("Invalid signed release SHA commitment")
    return v


def _canon(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False, ensure_ascii=True).encode("ascii")
    except Exception:
        raise FenceHold("Uncanonical release fence state") from None


def _signed_bytes(payload, *, key):
    signed = dict(payload, signature=hmac.new(_key(key), DOMAIN+_canon(payload),
                                              sha256).hexdigest())
    raw = _canon(signed)
    if len(raw) > MAX_BYTES:
        raise FenceHold("Release attempt fence exceeded bounded bytes")
    return raw


def _check_candidate(candidate):
    try:
        release._valid_candidate(candidate)
    except release.PublicationHold:
        raise FenceHold("Unsigned or inconsistent first event candidate") from None


def _expected(candidate, *, target_commit):
    _check_candidate(candidate)
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "candidate_head_sha": _hex(candidate["new_signed_seq1_blob_sha"], 40),
        "candidate_asset_sha256": _hex(candidate["asset_sha256"], 64),
        "candidate_release_tag": candidate["tag"],
        "immutable_parent_tag": chain.GENESIS_TAG,
        "immutable_parent_asset_sha256": chain.GENESIS_ASSET_SHA256,
        "target_commit_sha": _hex(target_commit, 40),
    }


def _steps_for_sequence(seq):
    if type(seq) is not int or seq < 0 or seq >= len(STATES):
        raise FenceHold("Signed release fence sequence invalid")
    return dict(zip(STEPS, STATES[seq]))


def initial_bytes(*, candidate, target_commit, key):
    """Prepare an in-memory new namespace ONLY after an authentic seq1 exists.

    No remote bootstrap or private file creation is authorized by this result.
    """
    base = _expected(candidate, target_commit=target_commit)
    return _signed_bytes({
        **base, "sequence": 0, "prior_document_git_blob_sha": None,
        "attempts": _steps_for_sequence(0),
    }, key=key)


def _verify_raw(raw, *, candidate, target_commit, key):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise FenceHold("Signed fence missing or oversized")
    def unique(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise FenceHold("Duplicate private signed JSON field")
            d[k] = v
        return d
    try:
        o = json.loads(raw.decode("ascii"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, TypeError):
        raise FenceHold("Malformed signed release fence JSON") from None
    expected = set(_expected(candidate, target_commit=target_commit)) | {
        "sequence", "prior_document_git_blob_sha", "attempts", "signature"}
    if type(o) is not dict or set(o) != expected:
        raise FenceHold("Unknown signed release fence fields")
    sig = o.pop("signature")
    if (type(sig) is not str
        or not hmac.compare_digest(
            sig, hmac.new(_key(key), DOMAIN+_canon(o), sha256).hexdigest())):
        raise FenceHold("Original private release attempt HMAC invalid")
    for k, v in _expected(candidate, target_commit=target_commit).items():
        if o.get(k) != v or type(o[k]) is not type(v):
            raise FenceHold("Signed attempt record not bound to exact seq1 head")
    seq = o["sequence"]
    if (type(o.get("attempts")) is not dict
        or o["attempts"] != _steps_for_sequence(seq)
        or any(type(v) is not str for v in o["attempts"].values())):
        raise FenceHold("Signed release attempt transition skipped or replayed")
    if seq == 0:
        if o.get("prior_document_git_blob_sha") is not None:
            raise FenceHold("Fake original release fence genesis parent")
    else:
        _hex(o.get("prior_document_git_blob_sha"), 40)
    return o


def read_github_source(source, *, candidate, target_commit, key):
    """Validate exact private path, Git blob SHA and HMAC before recovery.

    Missing (404) source is never interpreted as fresh stage. A stale signed
    state can still be rolled back until a separately reviewed anti-rollback
    watermark authenticates a known latest fence-head.
    """
    if (type(source) is not dict
        or source.get("type") != "file"
        or source.get("path") != PATH
        or source.get("encoding") != "base64"
        or type(source.get("content")) is not str):
        raise FenceHold("Missing exact authenticated private attempt fence")
    sha = _hex(source.get("sha"), 40)
    try:
        raw = b64decode(source["content"].replace("\n", "").replace("\r", ""),
                        validate=True)
    except Exception:
        raise FenceHold("Invalid encoded private attempt fence") from None
    if journal.original.blob_sha(raw) != sha:
        raise FenceHold("Private attempt fence Git blob SHA mismatch")
    return sha, _verify_raw(raw, candidate=candidate,
                            target_commit=target_commit, key=key)


def propose_transition(*, source, candidate, target_commit, key,
                       change, step, provider_setting, provider_release,
                       independently_get_asset=None, published_downloaded_bytes=None,
                       synthetic_remote_sources_authenticated=False):
    """Pure signed old-SHA CAS proposal; no private/public/broker I/O.

    The remote source input is deliberately SYNTHETIC. In production, a
    qualified caller must replace this synthetic provider boolean with
    authenticated actual private and provider source attestations, plus a
    provider-immutable anti-rollback fence watermark. It must NEVER call
    remote APIs from this module.
    """
    if (change not in ("CLAIM_BEFORE_MUTATION", "VERIFY_EXACT_REMOTE_SUCCESS")
        or step not in STEPS
        or synthetic_remote_sources_authenticated is not True
        or not all((NO_GITHUB_NETWORK, NO_PRIVATE_MUTATIONS,
                    NO_BROKER_NETWORK, GENESIS_ROLLBACK_ANCHOR_SEQ0_ONLY))
        or PRODUCTION_FENCE_INITIALIZATION_RELEASED
        or PRODUCTION_SIGNED_CAS_FENCE_WRITES_RELEASED
        or PRODUCTION_RECOVERY_SOURCE_AUTHENTICATED
        or LIVE_BROKER_ORDER_RELEASED):
        raise FenceHold("Only synthetic source-authenticated release transitions")
    old_sha, doc = read_github_source(
        source, candidate=candidate, target_commit=target_commit, key=key)
    existing = doc["sequence"]
    if existing >= len(STATES)-1:
        raise FenceHold("Already completed immutable release fence")
    if change == "CLAIM_BEFORE_MUTATION":
        expected_step = (0, 0, 1, 1, 2, 2)[existing]
        if (step != STEPS[expected_step] or existing % 2 != 0):
            raise FenceHold("Mutation already attempted or wrong signed stage")
        expected_action = tuple(ACTION_TO_STEP)[expected_step]
    else:
        expected_step = (0, 0, 0, 1, 1, 2)[existing]
        if (existing % 2 != 1 or step != STEPS[expected_step]):
            raise FenceHold("Cannot verify an unclaimed or different mutation")
        expected_action = NEXT_AFTER_VERIFIED[step]

    # Exact provider-source and signed fence observations are only synthetic
    # in this offline module. The next action NEVER includes broker authority.
    try:
        observed = release.plan_step(
            candidate=candidate, attempts=doc["attempts"],
            provider_setting=provider_setting,
            release=provider_release, target_commit=target_commit,
            independently_get_asset=independently_get_asset,
            published_downloaded_bytes=published_downloaded_bytes,
            remote_sources_independently_authenticated=True,
        )
    except release.PublicationHold:
        raise FenceHold("Provider source does not prove exact durable step") from None
    if observed["next_action"] != expected_action:
        raise FenceHold("Observed provider state cannot advance this signed fence")
    next_seq = existing+1
    new = {
        **_expected(candidate, target_commit=target_commit),
        "sequence": next_seq,
        "prior_document_git_blob_sha": old_sha,
        "attempts": _steps_for_sequence(next_seq),
    }
    raw = _signed_bytes(new, key=key)
    new_sha = journal.original.blob_sha(raw)
    return {
        "schema": SCHEMA,
        "status": "OFFLINE_SIGNED_PRIVATE_RELEASE_ATTEMPT_CAS_NOT_COMMITTED",
        "expected_prior_blob_sha": old_sha,
        "expected_new_blob_sha": new_sha,
        "new_sequence": next_seq,
        "next_step_state": new["attempts"][step],
        "observed_provider_next_action": observed["next_action"],
        "commit": {
            "repository": REPOSITORY, "path": PATH,
            "expected_current_sha": old_sha,
            "content_base64": b64encode(raw).decode("ascii"),
        },
        "protected_private_CAS_committed": False,
        "external_provider_mutation_performed": False,
        "immutable_fence_rollback_watermark_verified": False,
        "broker_orders_authorized": False,
    }


def verify_post_cas(*, plan, source, candidate, target_commit, key):
    if (type(plan) is not dict
        or plan.get("schema") != SCHEMA
        or plan.get("status") != "OFFLINE_SIGNED_PRIVATE_RELEASE_ATTEMPT_CAS_NOT_COMMITTED"
        or plan.get("protected_private_CAS_committed") is not False
        or plan.get("broker_orders_authorized") is not False):
        raise FenceHold("Untrusted or executable release attempt plan")
    sha, doc = read_github_source(
        source, candidate=candidate, target_commit=target_commit, key=key)
    if (sha != plan.get("expected_new_blob_sha")
        or doc["prior_document_git_blob_sha"] != plan.get("expected_prior_blob_sha")
        or doc["sequence"] != plan.get("new_sequence")
        or doc["attempts"] != _steps_for_sequence(doc["sequence"])):
        raise FenceHold("Private HMAC attempt CAS readback not the planned successor")
    return {
        "schema": SCHEMA,
        "status": "OFFLINE_OR_INJECTED_SIGNED_FENCE_CAS_READBACK_MATCHED",
        "signed_sequence": doc["sequence"],
        "signed_blob_sha": sha,
        "external_rollback_watermark_verified": False,
        "provider_release_mutation_authorized": False,
        "broker_order_authorized": False,
    }



def _one_synthetic_fence_contents_put(*, old_source, plan, candidate,
                                      target_commit, key, writer_token,
                                      transport=None):
    """Construct one exact GitHub Contents old-SHA PUT, but only in fake tests.

    An actual production writer requires a separate reviewed authenticated
    seq1/fence and protected-context controller; no such controller exists.
    Even a successful HTTP ACK is not an independently verified readback.
    """
    if transport is None or getattr(transport, "synthetic_only", None) is not True:
        raise FenceHold("Real release fence GitHub CAS transport HARD LOCKED")
    if (type(writer_token) is not str or len(writer_token) < 10
        or writer_token.strip() != writer_token
        or "\r" in writer_token or "\n" in writer_token):
        raise FenceHold("Invalid private fence writer")
    old_sha, old_doc = read_github_source(
        old_source,candidate=candidate,target_commit=target_commit,key=key)
    if (type(plan) is not dict
        or plan.get("schema") != SCHEMA
        or plan.get("status") != "OFFLINE_SIGNED_PRIVATE_RELEASE_ATTEMPT_CAS_NOT_COMMITTED"
        or plan.get("protected_private_CAS_committed") is not False
        or plan.get("broker_orders_authorized") is not False
        or plan.get("new_sequence") != old_doc["sequence"] + 1
        or plan.get("expected_prior_blob_sha") != old_sha
        or type(plan.get("commit")) is not dict
        or set(plan["commit"]) != {
            "repository", "path", "expected_current_sha", "content_base64"}
        or plan["commit"]["repository"] != REPOSITORY
        or plan["commit"]["path"] != PATH
        or plan["commit"]["expected_current_sha"] != old_sha):
        raise FenceHold("Unverified exact signed parent private CAS plan")
    try:
        raw=b64decode(plan["commit"]["content_base64"],validate=True)
        new_sha=journal.original.blob_sha(raw)
        if new_sha != plan.get("expected_new_blob_sha"):
            raise ValueError("unsigned new Git blob")
        new_doc=_verify_raw(raw,candidate=candidate,target_commit=target_commit,key=key)
        if (new_doc["prior_document_git_blob_sha"] != old_sha
            or new_doc["sequence"] != old_doc["sequence"] + 1
            or new_doc["attempts"] != _steps_for_sequence(new_doc["sequence"])):
            raise ValueError("unexpected release attempt transition")
    except Exception:
        raise FenceHold("Unverified next signed fence HMAC before PUT") from None
    from urllib.request import Request
    from urllib.error import HTTPError, URLError
    from base64 import b64encode as _enc
    url="https://api.github.com/repos/"+REPOSITORY+"/contents/"+PATH
    body=_canon({
        "message":"Fund-100 signed per-operation immutable release attempt fence",
        "branch":"main",
        "sha":old_sha,
        "content":_enc(raw).decode("ascii"),
    })
    if len(body)>MAX_BYTES*2:
        raise FenceHold("Signed attempt CAS HTTP request oversized")
    req=Request(url,method="PUT",data=body,headers={
        "Authorization":"Bearer "+writer_token,
        "Accept":"application/vnd.github+json",
        "Content-Type":"application/json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-synthetic-at-most-one-fence-CAS",
    })
    try:
        with transport(req,timeout=12) as response:
            status=getattr(response,"status",None)
            data=response.read(MAX_BYTES+1)
        if status!=200 or len(data)>MAX_BYTES:
            raise ValueError("uncertain private fence PUT ack")
        reply=json.loads(data.decode("utf-8"))
        if (type(reply) is not dict
            or type(reply.get("content")) is not dict
            or reply["content"].get("path") != PATH
            or reply["content"].get("sha") != new_sha
            or type(reply.get("commit")) is not dict
            or type(reply["commit"].get("sha")) is not str
            or re.fullmatch("[a-f0-9]{40}",reply["commit"]["sha"]) is None):
            raise ValueError("ambiguous GitHub CAS acknowledgement")
    except Exception:
        raise FenceHold("Private release fence CAS outcome unknown; NEVER RETRY") from None
    return {
        "schema":SCHEMA,
        "status":"SYNTHETIC_ONE_PRIVATE_FENCE_CAS_ACK_AWAIT_INDEPENDENT_READBACK",
        "new_private_fence_blob_sha":new_sha,
        "public_release_action_authorized":False,
        "private_CAS_readback_independently_verified":False,
        "retry_allowed":False,
        "broker_order_authorized":False,
    }

def main():
    print("First real signed seq1 release attempt fences: OFFLINE ONLY; NO PRIVATE WRITES/RELEASE/BROKER.")


if __name__ == "__main__":
    main()

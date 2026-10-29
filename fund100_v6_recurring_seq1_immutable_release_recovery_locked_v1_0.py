"""At-most-once GitHub immutable release steps for a genuine signed seq1 HEAD.

The real seq0 private signed HMAC has a provider-immutable external release.
This file is the *recoverable* remote publication protocol for the first
real signed reservation (seq1). It separates a durable intent/fence from the
single external CREATE/UPLOAD/PUBLISH action. Following an ambiguous HTTP
result: NEVER repeat that mutation. Authenticated GET of an exact remote
success can move to the *next* action; absence/partial/contradiction HOLDs.

No signed production attempt fence storage, qualified live strategy signal or
fully authenticated production seq1 currently exists: all production release
mutation paths are HARD LOCKED. Tests inject synthetic provider observations.
Neither this protocol nor its source data grants brokerage order authority.
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

import fund100_v6_recurring_seq1_immutable_event_asset_candidate_v1_0 as seq1
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as old_release

SCHEMA = "FUND100_V6_SEQ1_IMMUTABLE_RELEASE_AT_MOST_ONCE_RECOVERY_V1"
API = "https://api.github.com/repos/" + seq1.PUBLIC_REPO
UPLOAD = "https://uploads.github.com/repos/" + seq1.PUBLIC_REPO
IMMUTABLE_SETTING_URL = API + "/immutable-releases"
RELEASES_URL = API + "/releases"
FENCE_STATES = ("NEVER_ATTEMPTED", "ATTEMPTED_UNCERTAIN",
                "EXACT_REMOTE_SUCCESS_VERIFIED")
ACTIONS = ("CREATE_DRAFT", "UPLOAD_EXACT_ASSET", "PUBLISH_EXISTING_DRAFT",
           "COMPLETE_IMMUTABLE", "HOLD")
MAX_BODY_BYTES = 8192
PRODUCTION_PUBLIC_MUTATION_RELEASED = False
AUTHENTICATED_SEQ1_REMOTE_HEAD_RELEASED = False
DURABLE_PERSISTENT_ATTEMPT_FENCE_RELEASED = False
LIVE_BROKER_ORDER_RELEASED = False
NO_AUTOMATIC_MUTATION_RETRY = True
NO_PRIVATE_GITHUB_WRITES = True
NO_BROKER_HTTP = True


class PublicationHold(ValueError):
    pass


def _valid_candidate(candidate):
    if (type(candidate) is not dict
        or candidate.get("schema") != seq1.SCHEMA
        or candidate.get("status") != "OFFLINE_CANDIDATE_SEQ1_PUBLIC_IMMUTABLE_EVENT_EDGE_NOT_PUBLISHED"
        or candidate.get("live_order_authorized") is not False
        or candidate.get("parent_signed_seq0_blob_sha") != seq1.GENESIS_BLOB
        or candidate.get("prior_immutable_genesis_asset_sha256") != seq1.GENESIS_ASSET_SHA256
        or type(candidate.get("new_signed_seq1_blob_sha")) is not str
        or re.fullmatch("[a-f0-9]{40}", candidate["new_signed_seq1_blob_sha"]) is None
        or candidate.get("tag") != seq1.TAG_PREFIX + candidate["new_signed_seq1_blob_sha"]
        or candidate.get("asset_name") != seq1.ASSET
        or type(candidate.get("asset_bytes")) is not bytes
        or not 0 < len(candidate["asset_bytes"]) <= seq1.MAX_PUBLIC_ASSET_BYTES
        or candidate.get("asset_sha256") != sha256(candidate["asset_bytes"]).hexdigest()):
        raise PublicationHold("Untrusted signed recurring first event commitment")
    # Verify canonical bytes and the real genesis parent to reject an
    # otherwise self-consistent forged caller-supplied commitment.
    try:
        body = json.loads(candidate["asset_bytes"])
        if (type(body) is not dict or seq1._canon(body) != candidate["asset_bytes"]
            or body.get("schema") != seq1.SCHEMA
            or body.get("private_signed_sequence") != 1
            or body.get("private_previous_git_blob_sha1") != seq1.GENESIS_BLOB
            or body.get("private_new_git_blob_sha1") != candidate["new_signed_seq1_blob_sha"]
            or body.get("prior_immutable_release_tag") != seq1.GENESIS_TAG
            or body.get("prior_immutable_asset_sha256") != seq1.GENESIS_ASSET_SHA256
            or body.get("signed_stage") != "RESERVED_NO_ORDER"
            or body.get("broker_order_authorized") is not False
            or body.get("future_head_immutable_proven") is not False):
            raise ValueError("nonmatching asset")
    except Exception:
        raise PublicationHold("Untrusted public immutable event commitment bytes") from None


def _fence(attempts):
    if (type(attempts) is not dict
        or set(attempts) != {"create", "upload", "publish"}
        or any(attempts[k] not in FENCE_STATES
               or type(attempts[k]) is not str for k in attempts)):
        raise PublicationHold("Missing durable per-step attempt-fence evidence")
    if (attempts["upload"] != "NEVER_ATTEMPTED"
        and attempts["create"] == "NEVER_ATTEMPTED"):
        raise PublicationHold("Upload cannot precede fenced draft creation")
    if (attempts["publish"] != "NEVER_ATTEMPTED"
        and attempts["upload"] == "NEVER_ATTEMPTED"):
        raise PublicationHold("Publish cannot precede fenced exact asset")
    return attempts


def _metadata(candidate, release, *, target_commit):
    if (type(release) is not dict
        or type(target_commit) is not str
        or re.fullmatch("[a-f0-9]{40}", target_commit) is None
        or type(release.get("id")) is not int or release["id"] <= 0
        or release.get("tag_name") != candidate["tag"]
        or release.get("target_commitish") != target_commit
        or release.get("prerelease") is not False
        or type(release.get("assets")) is not list):
        raise PublicationHold("Existing remote release not exact signed event/target")
    # An existing release is only recoverable when its creation fingerprint
    # is *exactly* the non-secret public asset digest and previous parent.
    expected_body = _release_body(candidate)
    if (release.get("body") != expected_body["body"]
        or release.get("name") != expected_body["name"]):
        raise PublicationHold("Existing release does not attest intended seq1")
    return release["assets"]


def _release_body(candidate):
    return {
        "tag_name": candidate["tag"],
        "name": "Fund-100 V6 recurring seq1 signed HEAD (NO BROKER)",
        "body": ("Signed first reservation public commitment sha256:"
                 + candidate["asset_sha256"]
                 + " | parent immutable genesis sha256:"
                 + candidate["prior_immutable_genesis_asset_sha256"]
                 + " | NO BROKER ORDERS"),
        "draft": True,
        "prerelease": False,
        "make_latest": "false",
    }


def _asset_matches(candidate, asset):
    return (type(asset) is dict
            and type(asset.get("id")) is int and asset["id"] > 0
            and asset.get("name") == seq1.ASSET
            and asset.get("state") == "uploaded"
            and asset.get("size") == len(candidate["asset_bytes"])
            and asset.get("digest") == "sha256:" + candidate["asset_sha256"])


def plan_step(*, candidate, attempts, provider_setting,
              release, target_commit, independently_get_asset=None,
              published_downloaded_bytes=None,
              remote_sources_independently_authenticated=False):
    """Pure recovery decision; absolutely no external mutation by itself.

    'attempts' MUST be read from a separately authenticated *durable* fence,
    never an ordinary caller-made dictionary in a real trading controller.
    'release' MUST be publisher-authenticated, not public list omission.
    The production caller MUST recheck actual private signed current seq1.
    """
    _valid_candidate(candidate)
    _fence(attempts)
    if (provider_setting is not True
        or remote_sources_independently_authenticated is not True
        or type(target_commit) is not str
        or re.fullmatch("[a-f0-9]{40}", target_commit) is None):
        raise PublicationHold("Immutable provider, signed private HEAD or release source not verified")
    base = {"schema": SCHEMA,
            "signed_head": candidate["new_signed_seq1_blob_sha"],
            "broker_order_authorized": False,
            "private_git_writes": 0, "live_broker_posts": 0,
            "real_mutations_done": 0,
            "remote_provider_immutable_verified": False,
            "production_public_mutation_released": False}

    def respond(action, reason):
        return {**base, "next_action": action, "reason": reason,
                "requires_durable_attempt_record_before_action":
                    action in ACTIONS[:3]}

    if release is None:
        if all(attempts[k] == "NEVER_ATTEMPTED" for k in attempts):
            return respond("CREATE_DRAFT", "FRESH_EXACT_SIGNED_HEAD_ONLY")
        return respond("HOLD", "MISSING_RELEASE_AFTER_POSSIBLE_POST_NEVER_RETRY")

    assets = _metadata(candidate, release, target_commit=target_commit)
    if release.get("draft") is False:
        if (release.get("immutable") is not True
            or type(release.get("published_at")) is not str
            or type(release.get("author")) is not dict
            or release["author"].get("login") != "github-actions[bot]"
            or len(assets) != 1
            or not _asset_matches(candidate, assets[0])
            or assets[0].get("browser_download_url") != candidate["download_url"]
            or published_downloaded_bytes != candidate["asset_bytes"]):
            return respond("HOLD", "PUBLISHED_HEAD_NOT_VERIFIED_IMMUTABLE")
        # This confirms only public immutable matching to an *already*
        # independently authenticated PRIVATE head, not brokerage authority.
        result = respond("COMPLETE_IMMUTABLE", "EXACT_PROVIDER_IMMUTABLE_HEAD_AND_BYTES")
        result["remote_provider_immutable_verified"] = True
        return result
    if release.get("draft") is not True or release.get("immutable") is True:
        return respond("HOLD", "UNKNOWN_RELEASE_STATE")

    if len(assets) == 0:
        if (attempts["create"] not in
            ("ATTEMPTED_UNCERTAIN", "EXACT_REMOTE_SUCCESS_VERIFIED")
            or attempts["upload"] != "NEVER_ATTEMPTED"
            or attempts["publish"] != "NEVER_ATTEMPTED"):
            return respond("HOLD", "NO_VERIFIED_DRAFT_STAGE_ATTEMPT_FENCE")
        return respond("UPLOAD_EXACT_ASSET", "MATCHED_DRAFT_NO_UPLOADED_ASSET")

    if (len(assets) != 1 or not _asset_matches(candidate, assets[0])
        or not _asset_matches(candidate, independently_get_asset)):
        return respond("HOLD", "UPLOADED_ASSET_ID_DIGEST_OR_SOURCE_UNKNOWN")
    if assets[0]["id"] != independently_get_asset["id"]:
        return respond("HOLD", "TWO_INDEPENDENT_ASSET_VIEWS_DIVERGED")
    if (attempts["create"] == "NEVER_ATTEMPTED"
        or attempts["upload"] == "NEVER_ATTEMPTED"
        or attempts["publish"] != "NEVER_ATTEMPTED"):
        return respond("HOLD", "RELEASE_PUBLISH_FENCE_NOT_CLEAR")
    return respond("PUBLISH_EXISTING_DRAFT",
                   "MATCHED_DRAFT_EXACT_ASSET_AND_INDEPENDENT_GET")


def _one_mutation(*, step, candidate, token, target_commit, release_id=None,
                  transport=None):
    """Single REST mutation, never auto-retry; production HARD LOCKED.

    The only real token would be a per-run scoped GitHub Actions Contents-write
    token in a future reviewed production job; NEVER a broker credential.
    Synthetic transports must explicitly mark 'synthetic_only=True'.
    """
    if transport is not None and getattr(transport, "synthetic_only", None) is not True:
        raise PublicationHold("Injected release transports must be synthetic only")
    if transport is None:
        if not all((PRODUCTION_PUBLIC_MUTATION_RELEASED,
                    AUTHENTICATED_SEQ1_REMOTE_HEAD_RELEASED,
                    DURABLE_PERSISTENT_ATTEMPT_FENCE_RELEASED)):
            raise PublicationHold("Production recurring immutable release HARD LOCKED")
        # No such workflow is deployed. Any future production release must
        # add and review it alongside authenticated event/attempt provenance.
        import os
        env=os.environ
        required_ref=(seq1.PUBLIC_REPO
            + "/.github/workflows/fund100-v6-recurring-event-publisher-production-once.yml"
            + "@refs/heads/main")
        if (env.get("GITHUB_ACTIONS")!="true"
            or env.get("GITHUB_REPOSITORY")!=seq1.PUBLIC_REPO
            or env.get("GITHUB_REF")!="refs/heads/main"
            or env.get("GITHUB_EVENT_NAME")!="push"
            or env.get("GITHUB_RUN_ATTEMPT")!="1"
            or env.get("GITHUB_WORKFLOW_REF")!=required_ref
            or env.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
            or env.get("FUND100_RISK_LEVEL")!="HIGH"):
            raise PublicationHold("Unreviewed protected seq1 publisher context; HOLD")
    if (type(step) is not str or step not in ACTIONS[:3]
        or type(token) is not str or len(token) < 10
        or token.strip() != token or "\r" in token or "\n" in token):
        raise PublicationHold("Unapproved external immutable release mutation")
    _valid_candidate(candidate)
    if (type(target_commit) is not str or
        re.fullmatch("[a-f0-9]{40}",target_commit) is None):
        raise PublicationHold("Missing pinned main target commit SHA")

    if step == "CREATE_DRAFT":
        if release_id is not None:
            raise PublicationHold("Create may not overwrite existing release")
        payload = {**_release_body(candidate),
                   "target_commitish": target_commit}
        url, expected, raw = (RELEASES_URL, 201,
                              json.dumps(payload,sort_keys=True,
                                separators=(",",":")).encode("ascii"))
        kind = "application/json"
    elif step == "UPLOAD_EXACT_ASSET":
        if type(release_id) is not int or release_id <= 0:
            raise PublicationHold("Signed release draft ID absent")
        url = UPLOAD + "/releases/" + str(release_id) + "/assets?name=" + seq1.ASSET
        raw, expected, kind = candidate["asset_bytes"], 201, "application/octet-stream"
    else:
        if type(release_id) is not int or release_id <= 0:
            raise PublicationHold("Verified existing draft release ID absent")
        url = RELEASES_URL + "/" + str(release_id)
        raw, expected, kind = b'{"draft":false}', 200, "application/json"
    if len(raw) > MAX_BODY_BYTES:
        raise PublicationHold("Release request body exceeds reviewed bound")
    request=Request(url, method=("POST" if step!="PUBLISH_EXISTING_DRAFT" else "PATCH"),
        data=raw, headers={
            "Authorization":"Bearer "+token,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2026-03-10",
            "Content-Type":kind,
            "User-Agent":"fund100-v6-seq1-immutable-event-one-mutation",
        })
    sender=(build_opener(old_release._NoRedirect()).open
            if transport is None else transport)
    try:
        with sender(request,timeout=12) as response:
            status=getattr(response,"status",None)
            body=response.read(MAX_BODY_BYTES+1)
        if status != expected or len(body)>MAX_BODY_BYTES:
            raise ValueError("ambiguous release HTTP ack")
        obj=json.loads(body.decode("utf-8"))
        if type(obj) is not dict:
            raise ValueError("unknown release HTTP metadata")
        if step=="CREATE_DRAFT":
            if (type(obj.get("id")) is not int or obj["id"]<=0
                or obj.get("draft") is not True
                or obj.get("tag_name")!=candidate["tag"]
                or obj.get("target_commitish")!=target_commit):
                raise ValueError("draft create ack mismatch")
        elif step=="UPLOAD_EXACT_ASSET":
            if not _asset_matches(candidate,obj):
                raise ValueError("asset upload ack mismatch")
            # Draft asset URLs may legitimately be temporary /untagged-*/.
            # They are not required to equal final canonical URL until
            # provider-immutable published GET/bytes verification.
        elif (type(obj.get("id")) is not int or obj["id"]!=release_id
              or obj.get("draft") is not False
              or obj.get("tag_name") != candidate["tag"]):
            raise ValueError("publish ack mismatch")
        return {"schema":SCHEMA,
            "status":"SYNTHETIC_ONE_RELEASE_MUTATION_ACK_NOT_FINAL_IMMUTABILITY",
            "ack_step":step,"ack_release_id":obj.get("id"),
            "final_immutable_public_head_proven":False,
            "broker_order_authorized":False,
            "retry_allowed":False}
    except Exception:
        # Even a 201/200 with a lost ACK is terminal to THIS action.
        # Use independently authenticated GET and durable persisted attempt
        # fence to prove success before choosing any DIFFERENT next action.
        raise PublicationHold("Immutable signed seq1 release mutation ambiguous; NEVER RETRY") from None


def main():
    if (PRODUCTION_PUBLIC_MUTATION_RELEASED or
        AUTHENTICATED_SEQ1_REMOTE_HEAD_RELEASED or
        DURABLE_PERSISTENT_ATTEMPT_FENCE_RELEASED or LIVE_BROKER_ORDER_RELEASED):
        raise PublicationHold("Unreviewed live seq1 release switch changed")
    print("First signed seq1 immutable publication/recovery protocol ready; PRODUCTION LOCKED; NO BROKER.")


if __name__=="__main__":
    main()

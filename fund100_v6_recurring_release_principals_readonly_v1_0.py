"""Protected first recurring immutable-anchor GitHub release diagnosis, HTTP GET ONLY.

After run 40884760157 got a rejected first POST, the original one-time
release publisher was RETIRED and MUST NEVER be retried. The old payload's
make_latest boolean violated GitHub's string-enum contract (fixed in offline
tests by #407), but the original HTTP rejection code was deliberately not
logged, so cause and draft state are NOT established.

This one-shot diagnostic asks only whether distinct protected principals
authenticate and what they can SEE via GET. It neither proves permission
to POST a release nor establishes an immutable anchor. Any visible draft,
existing release or tag is a HOLD, never a mutation instruction.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

import fund100_v6_recurring_immutable_genesis_anchor_once_v1_0 as anchor

SCHEMA = "FUND100_V6_RECURRING_IMMUTABLE_RELEASE_GET_ONLY_DIAGNOSTIC_V1"
WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-recurring-release-principals-readonly.yml@refs/heads/main"
)
BASE = "https://api.github.com/repos/nicobouch97/fund100-research"
SELF = "https://api.github.com/user"
REPO = BASE
DRAFTS = BASE + "/releases?per_page=100&page=1"
TAG = BASE + "/releases/tags/" + anchor.TAG
GIT_TAG = BASE + "/git/ref/tags/" + anchor.TAG
SETTING = BASE + "/immutable-releases"
PATHS = (SELF, REPO, DRAFTS, TAG, GIT_TAG, SETTING)
MAX_BYTES = 300_000
MAX_ITEMS = 100
NO_HTTP_MUTATION = True
NO_BROKER_NETWORK = True
NO_PRIVATE_STATE_ACCESS = True
NO_SECRET_LOGGING = True
RELEASE_WRITE_PROVEN = False
ORIGINAL_RELEASE_RETRY_ALLOWED = False


class ReadOnlyStop(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ReadOnlyStop("Release diagnosis redirect HOLD")


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"
        or anchor.NO_PRIVATE_MUTATIONS is not True
        or anchor.NO_BROKER_NETWORK_OR_TRADING is not True):
        raise ReadOnlyStop("Protected original main HIGH and STOP required")


def _secrets(env):
    a = env.get("FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN")
    b = env.get("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
    if (any(type(s) is not str or len(s) < 10 or s.strip() != s
            or "\n" in s or "\r" in s for s in (a, b))
        or a == b):
        raise ReadOnlyStop("Two distinct release principals required")
    return a, b


def _get_only(*, url, token, transport=None):
    if (url not in PATHS or type(token) is not str or len(token) < 10):
        raise ReadOnlyStop("Unapproved read endpoint or credential")
    req = Request(url, method="GET", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-recurring-release-readonly-diagnosis",
    })
    sender = (build_opener(_NoRedirect()).open
              if transport is None else transport)
    try:
        with sender(req, timeout=12) as response:
            if getattr(response, "status", None) != 200:
                raise ReadOnlyStop("Unexpected GitHub release GET status")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ReadOnlyStop("Public release metadata too large")
        return 200, json.loads(raw.decode("utf-8"))
    except HTTPError as e:
        if e.code in (401, 403, 404, 422):
            # Never read or log an API error body (it may include private data).
            return e.code, None
        raise ReadOnlyStop("Unexpected release GET HTTP status") from None
    except ReadOnlyStop:
        raise
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        raise ReadOnlyStop("Release GET unknown; HOLD") from None


def inspect(*, environ=None, transport=None):
    env = dict(os.environ if environ is None else environ)
    _context(env)
    admin, publisher = _secrets(env)

    me_code, me = _get_only(url=SELF, token=publisher, transport=transport)
    if (me_code != 200 or type(me) is not dict
        or type(me.get("login")) is not str or not me["login"]):
        raise ReadOnlyStop("Publisher token authentication rejected; HOLD")
    repo_code, repo = _get_only(url=REPO, token=publisher, transport=transport)
    if (repo_code != 200 or type(repo) is not dict
        or repo.get("full_name") != "nicobouch97/fund100-research"):
        raise ReadOnlyStop("Release writer repository not accessible; HOLD")
    push = repo.get("permissions", {}).get("push") if type(
        repo.get("permissions")) is dict else None
    if type(push) is not bool:
        push = None

    setting_code, setting = _get_only(url=SETTING, token=admin, transport=transport)
    if (setting_code != 200 or type(setting) is not dict
        or setting.get("enabled") is not True
        or type(setting.get("enforced_by_owner")) is not bool):
        raise ReadOnlyStop("Provider immutable release setting not verified; HOLD")

    # GET /releases/tags cannot exclude a draft. Authenticated /releases
    # may expose draft releases, but even an empty list does not prove
    # that no invisible draft or other release state exists.
    releases_code, found = _get_only(url=DRAFTS, token=publisher, transport=transport)
    if (releases_code != 200 or type(found) is not list
        or len(found) >= MAX_ITEMS):
        raise ReadOnlyStop("Draft visibility missing or paginated; HOLD")
    draft_matches = []
    for release in found:
        if (type(release) is not dict or type(release.get("tag_name")) is not str
            or type(release.get("draft")) is not bool):
            raise ReadOnlyStop("Unrecognized release listing schema")
        if release["tag_name"] == anchor.TAG:
            draft_matches.append(release)
    if len(draft_matches) > 1:
        raise ReadOnlyStop("Conflicting original release draft metadata")
    bytag_code, bytag = _get_only(
        url=TAG, token=publisher, transport=transport)
    if bytag_code == 200:
        if (type(bytag) is not dict
            or bytag.get("tag_name") != anchor.TAG):
            raise ReadOnlyStop("Release tag details conflict")
    elif bytag_code != 404:
        raise ReadOnlyStop("Original tag release read unavailable")
    gitref_code, gitref = _get_only(
        url=GIT_TAG, token=publisher, transport=transport)
    if gitref_code == 200:
        if (type(gitref) is not dict
            or gitref.get("ref") != "refs/tags/" + anchor.TAG):
            raise ReadOnlyStop("Original Git tag ref inconsistent")
    elif gitref_code != 404:
        raise ReadOnlyStop("Original Git tag GET unavailable")

    visible_draft = bool(draft_matches and draft_matches[0]["draft"])
    visible_published = bool(
        (draft_matches and not draft_matches[0]["draft"])
        or bytag_code == 200)
    result = {
        "schema": SCHEMA,
        "status": (
            "ORIGINAL_RELEASE_DRAFT_VISIBLE_HOLD" if visible_draft
            else "ORIGINAL_RELEASE_VISIBLE_HOLD" if visible_published
            else "ORIGINAL_RELEASE_NOT_VISIBLE_BUT_POST_CONSUMED_HOLD"),
        "release_publisher_authenticated": True,
        "publisher_repo_get_authenticated": True,
        "publisher_coarse_push_metadata": (
            "INDICATED_NOT_WRITE_PROOF" if push is True else
            "DENIED" if push is False else "UNKNOWN"),
        "provider_immutable_setting_get_confirmed": True,
        "original_tag_draft_visible": visible_draft,
        "original_tag_published_visible": visible_published,
        "original_git_tag_ref_visible": gitref_code == 200,
        "exact_release_tag_get_http": bytag_code,
        "exact_tag_ref_get_http": gitref_code,
        "original_release_create_request_post_was_rejected": True,
        "original_release_post_rejection_http_code_proven": False,
        "github_release_write_permission_proven": False,
        "absence_of_hidden_draft_proven": False,
        "old_make_latest_boolean_schema_invalid": True,
        "new_original_release_retry_authorized": False,
        "private_mutations": 0,
        "public_mutations": 0,
        "broker_orders": 0,
        "trading_still_stopped": True,
    }
    return result


def main():
    result = inspect()
    # Public log only finite categorical assertions. Never print identity,
    # tokens, full metadata, SHA from private signed journal or HMAC key.
    for key in (
        "status", "publisher_coarse_push_metadata",
        "original_tag_draft_visible", "original_tag_published_visible",
        "original_git_tag_ref_visible", "exact_release_tag_get_http",
        "exact_tag_ref_get_http", "provider_immutable_setting_get_confirmed",
        "github_release_write_permission_proven", "new_original_release_retry_authorized",
    ):
        print(key + "=" + str(result[key]))
    print("NO RELEASE POST, NO PRIVATE WRITE, NO BROKER ORDERS, STOP ENGAGED")


if __name__ == "__main__":
    main()

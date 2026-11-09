"""Protected, REAL GitHub GET-only readiness for private capital genesis.

This is not genesis, a private ledger writer, a real immutable funding
release, live Alpaca funding, owner mandate approval, or a broker order.
The private funding state is never initialized from missing/404 sources.
A separate recurring-trade immutable release proves only that the GitHub
provider can host immutable releases; it CANNOT anchor this new namespace.

All private Contents bodies stay in memory and are never displayed, saved,
signed, downloaded as artifacts, or passed to the public status.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

REPO = "nicobouch97/fund100-state-private"
REPO_ID = 1426833955
PUBLIC_REPO = "nicobouch97/fund100-research"
PRIVATE_BASE = "https://api.github.com/repos/" + REPO
STATE_PATH = "state/scalable_contributed_principal.json"
STATE_URL = PRIVATE_BASE + "/contents/" + STATE_PATH + "?ref=main"
PUBLIC_RELEASE_URL = (
    "https://api.github.com/repos/" + PUBLIC_REPO +
    "/releases/tags/fund100-v6-recurring-signed-genesis-head-v2-20261029"
)
EXISTING_RECURRING_RELEASE_ID = 427978301
EXISTING_RECURRING_ASSET_ID = 688837795
EXISTING_RECURRING_SHA256 = (
    "6aa37278f20e6393d1f33c0a7004377285f53094bd78b046fc3bc574258f0af1"
)
WORKFLOW_REF = (PUBLIC_REPO +
    "/.github/workflows/fund100-scalable-private-genesis-readiness-getonly.yml@refs/heads/main")
MAX_BYTES = 240000
PRIVATE_GETS = 4
PUBLIC_GETS = 1
NO_RETRIES = True
NO_MUTATIONS = True
TRADING_AUTHORIZED = False
ALLOW_GENESIS_CREATE = False


class PreflightStop(ValueError):
    pass


class _NoRedirect:
    """A redirect from an authenticated REST endpoint cannot receive a PAT."""
    def __init__(self):
        from urllib.request import HTTPRedirectHandler
        self._handler = HTTPRedirectHandler()

    def handler(self):
        from urllib.request import HTTPRedirectHandler
        class NeverRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        return NeverRedirect()


def _get(url, *, token=None, transport=None, missing_ok=False):
    if url not in (PRIVATE_BASE, STATE_URL, PUBLIC_RELEASE_URL):
        raise PreflightStop("Unapproved GitHub read endpoint")
    if (url == PUBLIC_RELEASE_URL and token is not None
        or url != PUBLIC_RELEASE_URL and (
            type(token) is not str or len(token) < 10 or token.strip() != token
            or "\n" in token or "\r" in token)):
        raise PreflightStop("Missing or incorrectly scoped read principal")
    req = Request(url, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "fund100-capital-genesis-readonly-preflight",
        "X-GitHub-Api-Version": "2022-11-28",
        "Cache-Control": "no-store",
        **({"Authorization": "Bearer " + token} if token is not None else {}),
    })
    try:
        sender = build_opener(_NoRedirect().handler()).open if transport is None else transport
        with sender(req, timeout=12) as response:
            if response.status != 200:
                raise PreflightStop("GitHub GET did not return expected HTTP 200")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PreflightStop("Oversized private/provider metadata")
        value = json.loads(raw.decode("utf8"))
        if type(value) is not dict:
            raise PreflightStop("Malformed GitHub object")
        return value
    except HTTPError as e:
        if missing_ok and url == STATE_URL and e.code == 404:
            return None
        raise PreflightStop("Private/source GET failed; no retry") from None
    except (URLError, TimeoutError, OSError, TypeError,
            ValueError, UnicodeError):
        raise PreflightStop("Private/source GET uncertain; no retry") from None


def _repo_check(meta):
    if (type(meta) is not dict or meta.get("full_name") != REPO
        or meta.get("id") != REPO_ID or meta.get("private") is not True
        or meta.get("default_branch") != "main"
        or meta.get("archived") is True):
        raise PreflightStop("Wrong private repository identity")


def _state_description(val):
    if val is None:
        return "ABSENT_UNINITIALIZED_HOLD"
    if (type(val) is not dict or val.get("path") != STATE_PATH
        or val.get("type") != "file" or val.get("encoding") != "base64"
        or type(val.get("sha")) is not str
        or re.fullmatch(r"[a-f0-9]{40}", val["sha"]) is None
        or type(val.get("content")) is not str):
        raise PreflightStop("Invalid private funding source shape")
    return val["sha"]


def _release_check(meta):
    if (type(meta) is not dict
        or meta.get("id") != EXISTING_RECURRING_RELEASE_ID
        or meta.get("immutable") is not True
        or meta.get("draft") is not False
        or meta.get("prerelease") is not False
        or type(meta.get("assets")) is not list
        or len(meta["assets"]) != 1
        or type(meta["assets"][0]) is not dict
        or meta["assets"][0].get("id") != EXISTING_RECURRING_ASSET_ID
        or meta["assets"][0].get("digest") !=
            "sha256:" + EXISTING_RECURRING_SHA256
        or meta["assets"][0].get("size") != 680):
        raise PreflightStop("Existing provider-immutable OTHER-namespace release not verified")


def _stopped_original_policy(*, policy, operator_a, operator_b, env):
    if (type(policy) is not dict or type(operator_a) is not dict
        or type(operator_b) is not dict
        or policy.get("capital_ceiling_usd") != "130.30"
        or policy.get("additional_deposits_automatically_usable") is not False
        or policy.get("live_order_authorization_present") is not False
        or type(policy.get("account_binding_sha256")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", policy["account_binding_sha256"]) is None
        or operator_a.get("trading_enabled") is not False
        or operator_b.get("trading_enabled") is not False
        or operator_b.get("first_original_acwi_sell_enabled") is not False
        or operator_b.get("pilot_capital_ceiling_usd") != "130.30"
        or operator_b.get("risk_level") != "HIGH"
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"):
        raise PreflightStop("Original stopped $130.30 mandate no longer verified")


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != PUBLIC_REPO
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or not NO_RETRIES or not NO_MUTATIONS or TRADING_AUTHORIZED
        or ALLOW_GENESIS_CREATE):
        raise PreflightStop("Not in original protected main read-only scope")


def assess(*, private_read_repo, private_writer_repo,
           private_read_state, private_writer_state,
           immutable_other_namespace_release, policy,
           operator_a, operator_b, env):
    """Strictly no body returned, even if a private file exists."""
    _context(env)
    _stopped_original_policy(
        policy=policy, operator_a=operator_a, operator_b=operator_b, env=env)
    _repo_check(private_read_repo)
    _repo_check(private_writer_repo)
    left = _state_description(private_read_state)
    right = _state_description(private_writer_state)
    if left != right:
        raise PreflightStop("Two independently scoped private principals disagree")
    _release_check(immutable_other_namespace_release)
    return {
        "schema": "FUND100_SCALABLE_PRIVATE_GENESIS_REAL_READINESS_GETONLY_V1",
        "stage": ("PRIVATE_CAPITAL_LEDGER_NOT_INITIALIZED_HOLD"
                  if left == "ABSENT_UNINITIALIZED_HOLD" else
                  "PRIVATE_CAPITAL_LEDGER_PRESENT_NOT_FUNDING_ANCHORED_HOLD"),
        "separate_read_write_principals_private_repo_confirmed": True,
        "existing_other_namespace_immutable_release_confirmed": True,
        "this_capital_ledger_immutable_head_verified": False,
        "actual_private_funding_state_hmac_verified": False,
        "actual_broker_funding_or_cash_verified": False,
        "owner_capital_expansion_authorized": False,
        "live_orders_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0,
        "github_GETs": PRIVATE_GETS + PUBLIC_GETS,
        "github_write_requests": 0,
        "private_identity_or_contents_disclosed": False,
    }


def runtime(*, environ, get_fn=None):
    from pathlib import Path
    env = dict(environ)
    _context(env)
    root = Path(__file__).resolve().parent
    try:
        a = json.loads((root / "fund100_live_operator_control.json").read_text())
        b = json.loads((root / "fund100_v6_s1_operator_control.json").read_text())
        p = json.loads((root / "live_activation_outputs/v5_002/"
                        "live_micro_pilot_policy_v1_0.json").read_text())
    except (OSError, ValueError, TypeError):
        raise PreflightStop("Original immutable policy source missing") from None
    _stopped_original_policy(policy=p, operator_a=a, operator_b=b, env=env)
    read = env.get("FUND100_PRIVATE_STATE_READ_TOKEN")
    writer = env.get("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    if (type(read) is not str or type(writer) is not str
        or read == writer or len(read) < 10 or len(writer) < 10):
        raise PreflightStop("Separate original private principals unavailable")
    fetch = _get if get_fn is None else get_fn
    left_repo = fetch(PRIVATE_BASE, token=read)
    right_repo = fetch(PRIVATE_BASE, token=writer)
    left_state = fetch(STATE_URL, token=read, missing_ok=True)
    right_state = fetch(STATE_URL, token=writer, missing_ok=True)
    release = fetch(PUBLIC_RELEASE_URL)
    return assess(
        private_read_repo=left_repo, private_writer_repo=right_repo,
        private_read_state=left_state, private_writer_state=right_state,
        immutable_other_namespace_release=release, policy=p,
        operator_a=a, operator_b=b, env=env)


def main():
    try:
        result = runtime(environ=os.environ)
    except Exception:
        print("private_funding_genesis_status: HOLD_PROTECTED_SOURCE_UNAVAILABLE")
        print("live_orders_authorized: False")
        raise SystemExit(1) from None
    for key in (
        "schema", "stage", "separate_read_write_principals_private_repo_confirmed",
        "existing_other_namespace_immutable_release_confirmed",
        "this_capital_ledger_immutable_head_verified",
        "actual_private_funding_state_hmac_verified",
        "actual_broker_funding_or_cash_verified",
        "owner_capital_expansion_authorized",
        "live_orders_authorized", "broker_GETs", "broker_POSTs",
        "github_GETs", "github_write_requests"):
        print(key + ": " + str(result[key]))
    print("Private account/state/credentials and amounts never printed.")


if __name__ == "__main__":
    main()

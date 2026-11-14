"""One-time post-repository_dispatch STOP handoff acceptance (no trading).

NO Alpaca credentials. On a single trusted main push, while both existing
operator latches already read STOPPED, ask the existing protected STOP+cancel
workflow to execute. An acknowledgment NEVER proves broker cancellation.
The existing STOP workflow can cancel only Fund-100-tagged open orders; this
module cannot buy/sell, alter broker holdings, write GitHub Contents or rearm.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
EXPECTED_WORKFLOW = (
    REPO + "/.github/workflows/"
    "fund100-stop-bridge-integration-once.yml@refs/heads/main"
)
V5 = "fund100_live_operator_control.json"
V6 = "fund100_v6_s1_operator_control.json"
EVIDENCE = "research_lab/FUND100_PROTECTED_MAIN_STOP_WRITE_PROOF_2026_11_14.json"
STOP = "/actions/workflows/fund100-live-emergency-stop.yml/dispatches"
FIXED_BODY = b'{"ref":"main"}'  # GitHub v2026-03-10 returns HTTP 200+run details
READABLE = frozenset(("/branches/main", "/contents/" + V5,
                      "/contents/" + V6, "/contents/" + EVIDENCE))
EXPECTED = {
    V5: {"schema": "FUND100_OPERATOR_CONTROL_V1",
         "trading_enabled": False},
    V6: {"schema": "FUND100_V6_S1_OPERATOR_CONTROL_V2",
         "risk_level": "HIGH", "pilot_capital_ceiling_usd": "130.30",
         "trading_enabled": False,
         "first_original_acwi_sell_enabled": False},
}
PROOF = {
    "schema": "FUND100_PROTECTED_MAIN_STOP_ONLY_WRITE_PROOF_V1",
    "source_main_sha": "4a8a0279d39a4fab6ddde05489b64e47947ea3be",
    "origin_workflow_run_id": "43597082938",
    "trading_authorized": False, "broker_requests": 0,
    "operator_controls_changed": False, "diagnostic_only": True,
}
NO_ORDER_SUBMISSION = True
NO_GITHUB_CONTENTS_WRITE = True
NO_OPERATOR_REARM = True
NO_STOP_COMPLETION_CLAIM = True
NO_DISPATCH_RETRY = True
MAX_BYTES = 32768


class StopDispatchHold(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise StopDispatchHold("Unexpected GitHub redirect")


def _http(method: str, path: str, body: bytes | None = None) -> dict:
    """Only four fixed GitHub GETs or ONE exact emergency workflow POST."""
    if method == "GET" and path in READABLE and body is None:
        target = path + ("?ref=main&nonce=" + secrets.token_hex(8)
                         if path.startswith("/contents/") else "")
    elif method == "POST" and path == STOP and body == FIXED_BODY:
        target = path
    else:
        raise StopDispatchHold("Unapproved GitHub HTTP request")
    token = os.environ.get("GITHUB_TOKEN", "")
    if type(token) is not str or len(token.strip()) < 20 or token != token.strip():
        raise StopDispatchHold("GitHub Actions token untrusted")
    url = API + target
    req = Request(url, method=method, data=body, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2026-03-10",
        "Cache-Control": "no-store",
        "User-Agent": "fund100-once-stop-e2e-only",
    })
    try:
        with build_opener(_NoRedirect()).open(req, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise StopDispatchHold("Unverified GitHub status or origin")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise StopDispatchHold("GitHub request outcome unknown: no retry") from None
    if len(raw) > MAX_BYTES:
        raise StopDispatchHold("GitHub response oversized")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise StopDispatchHold("Invalid GitHub JSON response") from None
    if type(doc) is not dict:
        raise StopDispatchHold("GitHub response not a dictionary")
    return doc


def _file(path: str) -> dict:
    if path not in (V5, V6, EVIDENCE):
        raise StopDispatchHold("Untrusted main file path")
    doc = _http("GET", "/contents/" + path)
    if (doc.get("type") != "file" or doc.get("path") != path
        or doc.get("encoding") != "base64"
        or type(doc.get("sha")) is not str
        or type(doc.get("content")) is not str):
        raise StopDispatchHold("Untrusted main file metadata")
    try:
        raw = base64.b64decode(doc["content"].replace("\n", ""), validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, TypeError):
        raise StopDispatchHold("Untrusted main file contents") from None
    sha = hashlib.sha1(b"blob " + str(len(raw)).encode()
                       + b"\0" + raw).hexdigest()
    if (len(raw) > 4096 or sha != doc["sha"]
        or type(payload) is not dict):
        raise StopDispatchHold("Unverifiable Git blob")
    return payload


def _require_stopped() -> None:
    if _file(V5) != EXPECTED[V5] or _file(V6) != EXPECTED[V6]:
        raise StopDispatchHold("Current main controls not both STOPPED")


def _verify_source_context() -> str:
    if (os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPO
        or os.environ.get("GITHUB_EVENT_NAME") != "push"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
        or os.environ.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW
        or not os.environ.get("GITHUB_RUN_ID")
        or not all((NO_ORDER_SUBMISSION, NO_GITHUB_CONTENTS_WRITE,
                    NO_OPERATOR_REARM, NO_STOP_COMPLETION_CLAIM,
                    NO_DISPATCH_RETRY))):
        raise StopDispatchHold("Untrusted one-shot main STOP provenance")
    sha = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise StopDispatchHold("Untrusted main source SHA")
    return sha


def _branch(expected_sha: str) -> None:
    doc = _http("GET", "/branches/main")
    if (doc.get("name") != "main" or doc.get("protected") is not True
        or type(doc.get("commit")) is not dict
        or doc["commit"].get("sha") != expected_sha):
        raise StopDispatchHold("Protected main head changed/unknown")


def dispatch_once() -> int:
    """One fixed STOP dispatch. Caller MUST verify separate STOP run later."""
    sha = _verify_source_context()
    _branch(sha)
    _require_stopped()
    if _file(EVIDENCE) != PROOF:
        raise StopDispatchHold("Authenticated stopped-main write proof missing")
    _require_stopped()
    _branch(sha)
    # Absolute last step: exactly one GitHub POST, never retry if response lost.
    ack = _http("POST", STOP, FIXED_BODY)
    ident = ack.get("workflow_run_id")
    if (type(ident) is not int or not 0 < ident < 10**20
        or ack.get("run_url") != API + "/actions/runs/" + str(ident)
        or ack.get("html_url") != "https://github.com/" + REPO +
                                  "/actions/runs/" + str(ident)):
        raise StopDispatchHold("STOP dispatch ACK unverified; no retry")
    return ident


def main() -> None:
    try:
        run_id = dispatch_once()
    except (StopDispatchHold, KeyError, TypeError):
        print("EMERGENCY_STOP_E2E_UNVERIFIED; LIVE_TRADING_MUST_REMAIN_OFF")
        raise SystemExit(1) from None
    print("ACTUAL_STOP_WORKFLOW_RUN_ID=" + str(run_id))
    print("ONLY_DISPATCH_ACK; STOP_AND_BROKER_CANCEL_NOT_YET_VERIFIED")


if __name__ == "__main__":
    main()

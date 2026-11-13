"""Protected live GET-only evidence collector for existing emergency STOP.

Uses actual GitHub run/jobs/current-main controls plus TWO fresh authenticated
Alpaca Trading API GETs before calling the separately hard-locked completion
verifier. This is an executable source contract but is RELEASED = False and
has NO current workflow/production entrypoint. No broker POST/DELETE, no GitHub
PUT/dispatch, no Ed25519 key, no public Railway wiring, no trading GO.

Important: a completed workflow, accepted GitHub dispatch, or even one fresh
empty OPEN-orders snapshot does NOT prove no fills or future cancellation.
The original dispatch_run_id must come from a separately authenticated
dispatcher bound durably to the original alarm. An arbitrary caller-provided
integer is never accepted as independent dispatch provenance.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha1
import json
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import fund100_alpaca_live_readonly_smoke as broker
import fund100_v6_emergency_stop_completion_evidence_v1_0 as verifier
import fund100_live_operator_control_v1_0 as v5
import fund100_v6_s1_operator_control_v2_0 as v6

SOURCE_RELEASED = False
NO_GITHUB_WRITES = True
NO_BROKER_WRITES = True
NO_SIGNER_PRIVATE_KEY = True
NO_TRADE_RELEASE = True
NO_DISPATCH = True
NO_FILL_GUARANTEE = True
NO_PUBLIC_OUTPUT_OF_PRIVATE_ACCOUNT = True
NO_STANDALONE_DISPATCH_PROOF = True

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
RUN_PREFIX = API + "/actions/runs/"
V5_PATH = "fund100_live_operator_control.json"
V6_PATH = v6.PATH
MAX_RESPONSE_BYTES = 120000
MAX_PRIVATE_SOURCE_SECONDS = 30
BROKER_PATHS = ("/v2/account", "/v2/orders")
BROKER_OPEN_ORDER_PARAMS = {"status": "open", "limit": 500}


class StopSourceHold(RuntimeError):
    """Unverified STOP or broker open-order state; HOLD and escalate."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise StopSourceHold("GitHub STOP source redirected; HOLD")


def _source_scope():
    if (SOURCE_RELEASED is not True
        or not all((NO_GITHUB_WRITES, NO_BROKER_WRITES,
                    NO_SIGNER_PRIVATE_KEY, NO_TRADE_RELEASE,
                    NO_DISPATCH, NO_FILL_GUARANTEE,
                    NO_PUBLIC_OUTPUT_OF_PRIVATE_ACCOUNT,
                    NO_STANDALONE_DISPATCH_PROOF))
        or os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REPOSITORY") != REPO
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("FUND100_RISK_LEVEL") != "HIGH"
        or os.getenv("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE") != "DISABLED"):
        raise StopSourceHold("Protected STOP-completion reader HARD LOCKED")


def _github_token():
    token = os.environ.get("GITHUB_TOKEN", "")
    if (type(token) is not str or len(token) < 10
        or token != token.strip() or "\r" in token or "\n" in token):
        raise StopSourceHold("Trusted GitHub read-only token missing")
    # The actual job must grant contents:read and actions:read ONLY; a
    # token's effective permission scope cannot be inferred from its bytes.
    return token


def _get(url: str, *, token: str, transport=None) -> dict:
    if (type(url) is not str
        or not url.startswith(API + "/")
        or type(token) is not str or len(token) < 10
        or not (
            re.fullmatch(re.escape(RUN_PREFIX) + r"[1-9][0-9]{0,19}", url)
            or re.fullmatch(re.escape(RUN_PREFIX) +
                            r"[1-9][0-9]{0,19}/jobs\?per_page=100", url)
            or re.fullmatch(re.escape(API) +
                            r"/contents/fund100_live_operator_control\.json\?ref=main&nonce=[0-9a-f]{16}",url)
            or re.fullmatch(re.escape(API) +
                            r"/contents/fund100_v6_s1_operator_control\.json\?ref=main&nonce=[0-9a-f]{16}",url)
        )):
        raise StopSourceHold("Unapproved exact GitHub STOP read path")
    req = Request(url, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "Cache-Control": "no-store, no-cache",
        "User-Agent": "fund100-private-stop-completion-source",
    })
    sender = build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with sender(req, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise StopSourceHold("GitHub STOP response origin/status changed")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise StopSourceHold("GitHub STOP response oversized")
        doc = json.loads(raw)
        if type(doc) is not dict:
            raise StopSourceHold("GitHub STOP response invalid")
        return doc
    except (HTTPError, URLError, TimeoutError, OSError,
            ValueError, UnicodeError, TypeError):
        raise StopSourceHold("GitHub STOP evidence source unavailable") from None


def _current_main_control(path: str, *, token: str, transport=None) -> dict:
    if path not in (V5_PATH, V6_PATH):
        raise StopSourceHold("Unapproved STOP control path")
    url = (API + "/contents/" + path
           + "?ref=main&nonce=" + secrets.token_hex(8))
    source = _get(url, token=token, transport=transport)
    if (source.get("type") != "file" or source.get("path") != path
        or source.get("encoding") != "base64"
        or type(source.get("content")) is not str
        or type(source.get("sha")) is not str
        or re.fullmatch(r"[a-f0-9]{40}",source["sha"]) is None):
        raise StopSourceHold("Current main STOP source invalid")
    try:
        raw = base64.b64decode(
            source["content"].replace("\n", ""), validate=True)
        actual = sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()
        if actual != source["sha"] or len(raw) > 1000:
            raise StopSourceHold("Current main STOP Git blob mismatch")
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, KeyError):
        raise StopSourceHold("Current main STOP payload unreadable") from None
    if type(value) is not dict:
        raise StopSourceHold("Current main STOP payload malformed")
    try:
        if path == V5_PATH:
            if (value != {"schema": v5.CONTROL_SCHEMA,
                          "trading_enabled": False}
                or v5.validate_control(value) is not False):
                raise StopSourceHold("V5 main trading still ON or unknown")
        else:
            v6._validate(value)
            if (value.get("trading_enabled") is not False
                or value.get("first_original_acwi_sell_enabled") is not False):
                raise StopSourceHold("V6 main trading still ON or unknown")
    except (v5.OperatorControlStop, v6.V6OperatorStop):
        raise StopSourceHold("Main STOP operator invalid") from None
    return value


def _project_workflow_run(doc: object) -> dict:
    if type(doc) is not dict:
        raise StopSourceHold("STOP run JSON malformed")
    # Include only verifier-defined keys. No external prose/log content.
    fields = verifier.RUN_FIELDS
    if any(k not in doc for k in fields):
        raise StopSourceHold("STOP run missing evidence fields")
    return {k: doc[k] for k in fields}


def _project_workflow_jobs(doc: object, *, run_id: int) -> list:
    if (type(doc) is not dict
        or type(doc.get("total_count")) is not int
        or doc["total_count"] != len(verifier.REQUIRED_JOBS)
        or type(doc.get("jobs")) is not list
        or len(doc["jobs"]) != len(verifier.REQUIRED_JOBS)):
        raise StopSourceHold("STOP jobs missing/truncated/duplicated")
    projected = []
    for job in doc["jobs"]:
        if type(job) is not dict or type(job.get("steps")) is not list:
            raise StopSourceHold("STOP job shape unavailable")
        if any(k not in job for k in verifier.JOB_FIELDS):
            raise StopSourceHold("STOP job mandatory evidence missing")
        projected_steps = []
        for step in job["steps"]:
            if (type(step) is not dict
                or any(k not in step for k in verifier.STEP_FIELDS)):
                raise StopSourceHold("STOP step evidence unavailable")
            projected_steps.append({k: step[k] for k in verifier.STEP_FIELDS})
        projected.append({
            **{k: job[k] for k in verifier.JOB_FIELDS if k != "steps"},
            "steps": projected_steps,
        })
    return projected


def confirm_stop_from_authenticated_gets(
        *, expected_dispatch_run_id: object,
        alarm_detected_at_utc: str, transport=None) -> dict:
    """GET-only verification path. NEVER dispatch, cancel, sign or trade.

    Caller must bind a legitimate authenticated dispatch run id and alarm in
    a separate durable control-plane log. The code cannot infer that binding.
    Completion means the broker showed zero OPEN Fund-100 orders AT THAT
    observation, not that fills never occurred or future trading is blocked
    independently of current operator state.
    """
    _source_scope()
    if (type(expected_dispatch_run_id) is not int
        or expected_dispatch_run_id <= 0
        or expected_dispatch_run_id >= 10**20
        or type(alarm_detected_at_utc) is not str):
        raise StopSourceHold("Original STOP dispatch provenance absent")
    verifier._utc(alarm_detected_at_utc)
    token = _github_token()
    started = time.monotonic()
    run_id = expected_dispatch_run_id
    run = _project_workflow_run(
        _get(RUN_PREFIX + str(run_id),token=token,transport=transport))
    jobs = _project_workflow_jobs(
        _get(RUN_PREFIX+str(run_id)+"/jobs?per_page=100",
             token=token,transport=transport),
        run_id=run_id)
    # Independently verify current main STOP after the dispatch completed.
    v5_control = _current_main_control(V5_PATH,token=token,transport=transport)
    v6_control = _current_main_control(V6_PATH,token=token,transport=transport)
    controls_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    broker.require_readonly_arm()
    key, secret = broker.load_credentials()
    try:
        account = broker.get_json(path=BROKER_PATHS[0],params=None,
                                  key=key,secret=secret)
        orders = broker.get_json(path=BROKER_PATHS[1],
                                 params=dict(BROKER_OPEN_ORDER_PARAMS),
                                 key=key,secret=secret)
    except Exception:
        # Do not preserve raw broker exception messages, which may contain
        # private account numbers, request ids or financial information.
        raise StopSourceHold("Fresh broker STOP confirmation unavailable") from None
    broker_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if (not 0 <= time.monotonic() - started <= MAX_PRIVATE_SOURCE_SECONDS
        or type(account) is not dict or type(orders) is not list):
        raise StopSourceHold("STOP read was stale or malformed")
    # Verifier must be explicitly source-released independently and have an
    # exact account-identity pin. The default code ALWAYS fails closed.
    proof = verifier.verify_emergency_stop_completion(
        run=run, jobs=jobs,
        expected_dispatch_run_id=run_id,
        v5_control=v5_control, v6_control=v6_control,
        broker_account=account, broker_open_orders=orders,
        alarm_detected_at_utc=alarm_detected_at_utc,
        controls_observed_at_utc=controls_at,
        broker_observed_at_utc=broker_at,
        now_utc=datetime.now(timezone.utc))
    if (type(proof) is not dict
        or proof.get("status") !=
           "CURRENT_STOP_AND_OPEN_ORDER_ABSENCE_OBSERVED"
        or proof.get("new_trading_orders_authorized") is not False
        or proof.get("broker_fills_or_settlement_verified") is not False):
        raise StopSourceHold("Unqualified STOP completion evidence")
    return proof

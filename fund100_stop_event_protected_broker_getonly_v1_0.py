"""Protected post-STOP Alpaca GET-only reconciliation, no broker mutations.

This runner is a SEPARATE protected GitHub job AFTER the credentialless
original-STOP workflow_run verifier succeeds. Its ordinary Alpaca API
credentials are ISSUER-LEVEL TRADING-CAPABLE, even though this reviewed
source only performs two GETs and cannot submit, modify or cancel an order.
This is therefore NOT a separate broker-enforced read-only OAuth grant or
independent signed STOP receipt. It does not prove fills or future order absence.
No credentials, account IDs or broker response bodies are printed or persisted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import time
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as broker

SCHEMA="FUND100_STOP_PROTECTED_POSTFLIGHT_BROKER_GETONLY_V1"
REPO="nicobouch97/fund100-research"
WORKFLOW_REF=(REPO+"/.github/workflows/"
              "fund100-stop-exact-run-event-getonly.yml@refs/heads/main")
STOP_WORKFLOW="Fund-100 STOP TRADING (operator emergency)"
STOP_WORKFLOW_PATH=".github/workflows/fund100-live-emergency-stop.yml"
POLICY_PATH=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
EXPECTED_ACCOUNT_BINDING_SHA256="1739bb3720c916ccfc6732ecd24236ab0cdbbbc1915879e0296d15fb055f49bf"
EXPECTED_CAPITAL_CEILING_USD="130.30"
MAX_BROKER_GET_SECONDS=45
MAX_SOURCE_EVENT_AGE_SECONDS=240
NO_BROKER_WRITE=True
NO_GITHUB_WRITE=True
NO_GITHUB_TOKEN=True
NO_STOP_DISPATCH=True
NO_SIGNER_KEY=True
NO_STOP_COMPLETION_CLAIM=True
NO_TRADE_RELEASE=True
BROKER_PATHS=("/v2/account","/v2/orders")
OPEN_ORDER_PARAMS={"status":"open","limit":500}


class PostStopBrokerHold(RuntimeError):
    pass


def _utc(value: object) -> datetime:
    if (type(value) is not str
        or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",value) is None):
        raise PostStopBrokerHold("Unqualified STOP event UTC")
    try:
        t=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise PostStopBrokerHold("Unqualified STOP event UTC") from None
    if t.strftime("%Y-%m-%dT%H:%M:%SZ")!=value:
        raise PostStopBrokerHold("Unqualified STOP event UTC")
    return t


def _scope() -> None:
    e=os.environ
    if (not all((NO_BROKER_WRITE,NO_GITHUB_WRITE,NO_GITHUB_TOKEN,
                 NO_STOP_DISPATCH,NO_SIGNER_KEY,NO_STOP_COMPLETION_CLAIM,
                 NO_TRADE_RELEASE))
        or e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!=REPO
        or e.get("GITHUB_EVENT_NAME")!="workflow_run"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF")!=WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or re.fullmatch(r"[0-9a-f]{40}",e.get("GITHUB_SHA","")) is None
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or e.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or e.get("FUND100_LIVE_WRITE_MODE")!="DISABLED"
        or any(k in e for k in (
            "GITHUB_TOKEN","GH_TOKEN","FUND100_GH_STOP_DISPATCH_TOKEN",
            "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_ALPACA_READONLY_OAUTH_BEARER",
        ))):
        raise PostStopBrokerHold("Protected STOP broker GET source scope invalid")


def _event_id() -> int:
    path=os.environ.get("GITHUB_EVENT_PATH","")
    if (type(path) is not str
        or not path.startswith("/home/runner/work/")
        or not path.endswith("/event.json")):
        raise PostStopBrokerHold("GitHub-authored event file unavailable")
    try:
        with open(path,"rb") as f:
            raw=f.read(16001)
        if len(raw)>16000:
            raise PostStopBrokerHold("STOP event too large")
        obj=json.loads(raw)
    except (OSError,ValueError,TypeError,UnicodeError):
        raise PostStopBrokerHold("Malformed STOP event") from None
    run=obj.get("workflow_run") if type(obj) is dict else None
    source=run.get("head_repository") if type(run) is dict else None
    if (type(run) is not dict or type(source) is not dict
        or source.get("full_name")!=REPO
        or run.get("name")!=STOP_WORKFLOW
        or run.get("path")!=STOP_WORKFLOW_PATH
        or run.get("event")!="workflow_dispatch"
        or run.get("head_branch")!="main"
        or run.get("status")!="completed"
        or run.get("conclusion")!="success"
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"]!=1
        or type(run.get("id")) is not int
        or not 0<run["id"]<10**20
        or re.fullmatch(r"[0-9a-f]{40}",run.get("head_sha","")) is None):
        raise PostStopBrokerHold("Wrong STOP source event")
    updated=_utc(run.get("updated_at"))
    now=datetime.now(timezone.utc)
    if (not 0<=(now-updated).total_seconds()
        <=MAX_SOURCE_EVENT_AGE_SECONDS):
        raise PostStopBrokerHold("STOP broker GET event stale")
    return run["id"]


def _pinned_policy() -> None:
    try:
        raw=POLICY_PATH.read_bytes()
        if len(raw)>4000:
            raise PostStopBrokerHold("Oversized immutable broker account policy")
        policy=json.loads(raw)
    except (OSError,ValueError,TypeError):
        raise PostStopBrokerHold("Pinned live broker account policy unavailable") from None
    if (type(policy) is not dict
        or policy.get("account_binding_sha256") !=
            EXPECTED_ACCOUNT_BINDING_SHA256
        or policy.get("capital_ceiling_usd") !=
            EXPECTED_CAPITAL_CEILING_USD
        or policy.get("deployment_mode")!="LIVE_MICRO_PILOT"
        or policy.get("live_order_authorization_present") is not False
        or policy.get("leverage_allowed") is not False
        or policy.get("shorting_allowed") is not False):
        raise PostStopBrokerHold("Live broker account/capital policy changed")


def _read_no_open_targets(*, account: object, orders: object) -> None:
    if type(account) is not dict or type(account.get("id")) is not str:
        raise PostStopBrokerHold("Broker account identity missing")
    account_id=account["id"]
    if (not 8<=len(account_id)<=128
        or re.fullmatch(r"[A-Za-z0-9-]+",account_id) is None):
        raise PostStopBrokerHold("Broker account identity malformed")
    actual=sha256(("FUND100-LIVE-ACCOUNT|"+account_id).encode()).hexdigest()
    if actual!=EXPECTED_ACCOUNT_BINDING_SHA256:
        raise PostStopBrokerHold("Unexpected real broker account identity")
    if type(orders) is not list or len(orders)>=OPEN_ORDER_PARAMS["limit"]:
        raise PostStopBrokerHold("Broker open-order listing missing or truncated")
    candidate_count=0
    for order in orders:
        if type(order) is not dict:
            raise PostStopBrokerHold("Malformed open broker order")
        client=order.get("client_order_id")
        if type(client) is not str or not 1<=len(client)<=128:
            raise PostStopBrokerHold("Unattributable open broker order")
        # Conservative read-only SUPERSET of reviewed Fund-100 client IDs:
        # f100live-..., f100live-prod-..., f100-live-bootstrap-...,
        # f100v6s1-... and any future f100*/fund100* derivatives.
        # A false positive holds; no other customer's orders can be mutated.
        if client.lower().startswith(("f100","fund100")):
            candidate_count+=1
    if candidate_count:
        raise PostStopBrokerHold("Potential outstanding Fund-100 broker order")


def observe_broker_once() -> dict:
    _scope()
    original_run_id=_event_id()
    _pinned_policy()
    # The upstream separate credentialless job has to pass ALL exact original
    # GitHub run/jobs and current-main STOP checks before GitHub schedules this
    # broker-key job. Here there is NO GitHub token or signer private key.
    broker.require_readonly_arm()
    start=time.monotonic()
    try:
        key,secret=broker.load_credentials()
        account=broker.get_json(path=BROKER_PATHS[0],key=key,secret=secret)
        orders=broker.get_json(path=BROKER_PATHS[1],key=key,secret=secret,
                               params=dict(OPEN_ORDER_PARAMS))
    except Exception:
        # No raw account/broker exception may escape to Actions public logs.
        raise PostStopBrokerHold("Protected GET-only broker read unavailable") from None
    if not 0<=time.monotonic()-start<=MAX_BROKER_GET_SECONDS:
        raise PostStopBrokerHold("Post-STOP broker snapshot expired")
    _read_no_open_targets(account=account,orders=orders)
    return {
        "schema":SCHEMA,
        "status":"LIVE_BROKER_NO_OPEN_FUND100_AT_THIS_GET_ONLY",
        "original_stop_run_id":original_run_id,
        "live_broker_get_count":2,
        "issuer_level_credential_is_readonly":False,
        "new_broker_orders":0,
        "broker_orders_modified":0,
        "broker_fills_verified":False,
        "signed_stop_completion_receipt":False,
        "stop_completed":False,
        "order_authorized":False,
    }


if __name__=="__main__":
    try:
        print(json.dumps(observe_broker_once(),sort_keys=True))
    except Exception:
        # Avoid accidental exposure of provider/account text on unexpected errors.
        print('{"status":"PROTECTED_BROKER_GET_UNVERIFIED_HOLD",'
              '"stop_completed":false,"order_authorized":false}')
        raise SystemExit(1) from None

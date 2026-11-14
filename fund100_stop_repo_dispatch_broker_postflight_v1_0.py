"""Protected STOP -> independent two-GET Alpaca postflight, NO broker mutation.

The upstream separate credentialless job MUST independently validate the
original STOP 3/3 GitHub jobs and current V5/V6 controls before scheduling
this broker-key environment job. This runner has NO GitHub token or signer,
but the direct Alpaca account keys remain issuer-level TRADING-CAPABLE.
Only read the pinned account and list open orders once each via the existing
source-pinned GET-only transport. NO fills/settlement proof, no guarantee that
new orders can never appear and absolutely NO signed STOP completion.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import fund100_stop_event_protected_broker_getonly_v1_0 as core

REPO="nicobouch97/fund100-research"
WORKFLOW_REF=(REPO+"/.github/workflows/"
              "fund100-stop-explicit-original-getonly.yml@refs/heads/main")
EVENT_TYPE="fund100-original-stop-outcome-readonly-v1"
SCHEMA="FUND100_POSTSTOP_REPO_EVENT_PROTECTED_BROKER_GETONLY_V1"
MAX_EVENT_BYTES=16000
MAX_GET_SECONDS=45
NO_BROKER_MUTATION=True
NO_GITHUB_TOKEN=True
NO_GITHUB_WRITE=True
NO_SIGNER=True
NO_STOP_DISPATCH=True
NO_ORDER_RELEASE=True
NO_COMPLETION_CLAIM=True
NO_FILL_CLAIM=True


class BrokerPostflightHold(RuntimeError):
    pass


def _scope() -> None:
    e=os.environ
    if (not all((NO_BROKER_MUTATION,NO_GITHUB_TOKEN,NO_GITHUB_WRITE,
                 NO_SIGNER,NO_STOP_DISPATCH,NO_ORDER_RELEASE,
                 NO_COMPLETION_CLAIM,NO_FILL_CLAIM,
                 core.NO_BROKER_WRITE,core.NO_GITHUB_WRITE))
        or e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!=REPO
        or e.get("GITHUB_EVENT_NAME")!="repository_dispatch"
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
            "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_ALPACA_READONLY_OAUTH_BEARER",
        ))):
        raise BrokerPostflightHold("Wrong STOP broker postflight source scope")


def _original_id() -> int:
    filename=os.environ.get("GITHUB_EVENT_PATH","")
    if (type(filename) is not str
        or not filename.startswith("/home/runner/work/")
        or not filename.endswith("/event.json")):
        raise BrokerPostflightHold("GitHub original STOP event unavailable")
    try:
        with open(filename,"rb") as f:
            blob=f.read(MAX_EVENT_BYTES+1)
        if len(blob)>MAX_EVENT_BYTES:
            raise BrokerPostflightHold("Overlarge STOP event")
        event=json.loads(blob)
    except (OSError,ValueError,TypeError,UnicodeError):
        raise BrokerPostflightHold("Malformed original STOP event") from None
    if type(event) is not dict:
        raise BrokerPostflightHold("Malformed original STOP source")
    repository=event.get("repository")
    payload=event.get("client_payload")
    if (event.get("action")!=EVENT_TYPE
        or type(repository) is not dict
        or repository.get("full_name")!=REPO
        or type(payload) is not dict
        or set(payload)!={"original_stop_run_id"}):
        raise BrokerPostflightHold("Untrusted STOP postflight event")
    value=payload.get("original_stop_run_id")
    if (type(value) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",value) is None):
        raise BrokerPostflightHold("Untrusted STOP original run locator")
    return int(value)


def observe_once() -> dict:
    _scope()
    original_id=_original_id()
    try:
        # Source-pinned upstream GitHub observer is a strict dependency; no
        # new original-run GitHub token is present in this separate broker job.
        core._pinned_policy()
        core.broker.require_readonly_arm()
        start=time.monotonic()
        key,secret=core.broker.load_credentials()
        account=core.broker.get_json(
            path="/v2/account",key=key,secret=secret)
        open_orders=core.broker.get_json(
            path="/v2/orders",key=key,secret=secret,
            params={"status":"open","limit":500})
        duration=time.monotonic()-start
        if not 0<=duration<=MAX_GET_SECONDS:
            raise BrokerPostflightHold("Broker snapshot age failed")
        core._read_no_open_targets(account=account,orders=open_orders)
    except Exception:
        # Never leak raw broker errors, secrets, account IDs or order payloads.
        raise BrokerPostflightHold(
            "Protected issuer-level broker GET not independently verified") from None
    return {
        "schema":SCHEMA,
        "status":"TWO_AUTHENTIC_BROKER_GETS_NO_OPEN_FUND100_AT_SNAPSHOT",
        "original_stop_run_id":original_id,
        "broker_get_count":2,
        "issuer_level_credentials_are_readonly":False,
        "broker_orders_mutated":False,
        "broker_fills_verified":False,
        "signed_stop_receipt":False,
        "stop_completed":False,
        "order_authorized":False,
    }


if __name__=="__main__":
    try:
        print(json.dumps(observe_once(),sort_keys=True))
    except Exception:
        print('{"status":"REPO_EVENT_BROKER_GET_UNVERIFIED_HOLD",'
              '"stop_completed":false,"order_authorized":false}')
        raise SystemExit(1) from None

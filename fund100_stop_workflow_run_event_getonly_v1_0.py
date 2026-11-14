"""Credentialless, EVENT-DRIVEN GitHub-only emergency STOP observation.

GitHub Actions workflow_run on the exact completed emergency STOP triggers an
independent read of the actual original run/jobs and current protected-main
V5/V6 STOP files. The event payload alone is NEVER used as completion proof.

This is intentionally NOT signed STOP completion: no broker GET, no evidence
of zero open orders or fills, no trade order, no GitHub writes, no signer key.
A GitHub "success" and both STOP latches alone cannot confirm broker safety.

The next protected broker reader/signing job must independently observe Alpaca
and bind the *same original run ID* plus the actual chronological alarm.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha1
import json
import os
import re
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

import fund100_v6_emergency_stop_completion_evidence_v1_0 as contract
import fund100_live_operator_control_v1_0 as v5
import fund100_v6_s1_operator_control_v2_0 as v6

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
WORKFLOW_REF = (REPO + "/.github/workflows/"
                "fund100-stop-exact-run-event-getonly.yml@refs/heads/main")
STOP_PATH = ".github/workflows/fund100-live-emergency-stop.yml"
V5_PATH = "fund100_live_operator_control.json"
V6_PATH = "fund100_v6_s1_operator_control.json"
MAX_SOURCE_RESPONSE_BYTES = 120_000
MAX_EVENT_DELAY_SECONDS = 180
NO_BROKER_ACCESS = True
NO_BROKER_WRITE = True
NO_GITHUB_WRITE = True
NO_STOP_DISPATCH = True
NO_SIGNING = True
NO_TRADE_RELEASE = True
NO_STOP_COMPLETION_CLAIM = True


class StopEventHold(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise StopEventHold("GitHub event evidence redirect refused")


def _scope() -> None:
    e = os.environ
    if (not all((NO_BROKER_ACCESS, NO_BROKER_WRITE, NO_GITHUB_WRITE,
                 NO_STOP_DISPATCH, NO_SIGNING, NO_TRADE_RELEASE,
                 NO_STOP_COMPLETION_CLAIM))
        or e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != REPO
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_EVENT_NAME") != "workflow_run"
        or e.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or re.fullmatch(r"[0-9a-f]{40}", e.get("GITHUB_SHA","")) is None):
        raise StopEventHold("Untrusted event-only STOP observer scope")
    forbidden = (
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET", "FUND100_ALPACA_READONLY_OAUTH_BEARER",
        "FUND100_GH_STOP_DISPATCH_TOKEN",
        "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
        "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
    )
    if any(name in e for name in forbidden):
        raise StopEventHold("Broker, dispatch or signer credentials forbidden")


def _event() -> int:
    path = os.environ.get("GITHUB_EVENT_PATH","")
    if (type(path) is not str or not path.startswith("/home/runner/work/")
        or not path.endswith("/event.json")):
        raise StopEventHold("GitHub official event path unavailable")
    try:
        with open(path,"rb") as f:
            raw=f.read(16001)
        if len(raw)>16000:
            raise StopEventHold("Overlarge GitHub event")
        event=json.loads(raw)
    except (OSError,UnicodeError,ValueError,TypeError):
        raise StopEventHold("GitHub STOP event unavailable") from None
    wr=event.get("workflow_run") if type(event) is dict else None
    repo=wr.get("head_repository") if type(wr) is dict else None
    if (type(wr) is not dict or type(repo) is not dict
        or repo.get("full_name")!=REPO
        or wr.get("name")!=contract.WORKFLOW_NAME
        or wr.get("path")!=STOP_PATH
        or wr.get("event")!="workflow_dispatch"
        or wr.get("head_branch")!="main"
        or wr.get("status")!="completed"
        or wr.get("conclusion")!="success"
        or type(wr.get("run_attempt")) is not int
        or wr["run_attempt"]!=1
        or type(wr.get("id")) is not int or wr["id"] <= 0
        or wr["id"]>=10**20
        or re.fullmatch(r"[0-9a-f]{40}",wr.get("head_sha","")) is None):
        raise StopEventHold("Wrong STOP source event")
    return wr["id"]


def _token() -> str:
    tok=os.environ.get("GITHUB_TOKEN")
    if (type(tok) is not str or not 20 <= len(tok) <= 4096
        or re.search(r"\s",tok) is not None):
        raise StopEventHold("GitHub ephemeral read-only token missing")
    return tok


def _get(url: str, *, token: str) -> dict:
    run_prefix=API+"/actions/runs/"
    is_run=bool(re.fullmatch(re.escape(run_prefix)+r"[1-9][0-9]{0,19}",url))
    is_jobs=bool(re.fullmatch(re.escape(run_prefix)+r"[1-9][0-9]{0,19}/jobs\?per_page=100",url))
    is_control=bool(re.fullmatch(
        re.escape(API)+r"/contents/(fund100_live_operator_control\.json|"
        r"fund100_v6_s1_operator_control\.json)\?ref=main&nonce=[0-9a-f]{16}",
        url))
    if not (is_run or is_jobs or is_control):
        raise StopEventHold("Non-allowlisted GitHub GET")
    req=Request(url,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2026-03-10",
        "Cache-Control":"no-cache, no-store",
        "User-Agent":"fund100-brokerless-stop-event-proof",
    })
    try:
        with build_opener(NoRedirect()).open(req,timeout=8) as response:
            if response.status!=200 or response.geturl()!=url:
                raise StopEventHold("GitHub evidence response unverified")
            raw=response.read(MAX_SOURCE_RESPONSE_BYTES+1)
        if len(raw)>MAX_SOURCE_RESPONSE_BYTES:
            raise StopEventHold("GitHub evidence oversized")
        data=json.loads(raw)
        if type(data) is not dict:
            raise StopEventHold("Invalid GitHub evidence body")
        return data
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,
            UnicodeError):
        raise StopEventHold("GitHub evidence unavailable") from None


def _control(path: str, *, token: str) -> dict:
    if path not in (V5_PATH,V6_PATH):
        raise StopEventHold("Invalid main control path")
    info=_get(API+"/contents/"+path+"?ref=main&nonce="+secrets.token_hex(8),
              token=token)
    if (info.get("type")!="file" or info.get("path")!=path
        or info.get("encoding")!="base64"
        or re.fullmatch(r"[0-9a-f]{40}",info.get("sha","")) is None
        or type(info.get("content")) is not str):
        raise StopEventHold("Current-main STOP file unverified")
    try:
        raw=base64.b64decode(info["content"].replace("\n",""),validate=True)
        got=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        payload=json.loads(raw.decode("utf-8"))
    except (UnicodeError,TypeError,ValueError):
        raise StopEventHold("STOP main blob invalid") from None
    if got!=info["sha"] or len(raw)>1000 or type(payload) is not dict:
        raise StopEventHold("Current-main STOP blob hash invalid")
    try:
        if path==V5_PATH:
            if (payload!={"schema":v5.CONTROL_SCHEMA,"trading_enabled":False}
                or v5.validate_control(payload) is not False):
                raise StopEventHold("V5 main STOP not verified")
        else:
            v6._validate(payload)
            if (payload["trading_enabled"] is not False
                or payload["first_original_acwi_sell_enabled"] is not False):
                raise StopEventHold("V6 main STOP not verified")
    except (v5.OperatorControlStop,v6.V6OperatorStop):
        raise StopEventHold("Main control validator rejected source") from None
    return payload


def observe_once() -> dict:
    _scope()
    original_id=_event()
    token=_token()
    doc=_get(API+"/actions/runs/"+str(original_id),token=token)
    fields=contract.RUN_FIELDS
    if (not fields.issubset(doc)
        or doc["id"]!=original_id or type(doc["id"]) is not int
        or doc["name"]!=contract.WORKFLOW_NAME
        or doc["path"]!=STOP_PATH or doc["event"]!="workflow_dispatch"
        or doc["head_branch"]!="main" or doc["status"]!="completed"
        or doc["conclusion"]!="success" or doc["run_attempt"]!=1
        or type(doc["run_attempt"]) is not int
        or re.fullmatch(r"[0-9a-f]{40}",doc.get("head_sha","")) is None):
        raise StopEventHold("Authenticated original STOP run is not successful")
    try:
        created=contract._utc(doc["created_at"])
        started=contract._utc(doc["run_started_at"])
        finished=contract._utc(doc["updated_at"])
    except contract.StopCompletionStop:
        raise StopEventHold("Original STOP run chronology invalid") from None
    now=datetime.now(timezone.utc)
    if (not created<=started<=finished<=now
        or (finished-created).total_seconds()>contract.MAX_STOP_TOTAL_SECONDS
        or (now-finished).total_seconds()>MAX_EVENT_DELAY_SECONDS):
        raise StopEventHold("Original STOP evidence too old or delayed")
    jobsdoc=_get(API+"/actions/runs/"+str(original_id)+"/jobs?per_page=100",
                 token=token)
    rawjobs=jobsdoc.get("jobs")
    if (type(jobsdoc.get("total_count")) is not int
        or jobsdoc["total_count"]!=len(contract.REQUIRED_JOBS)
        or type(rawjobs) is not list
        or len(rawjobs)!=len(contract.REQUIRED_JOBS)):
        raise StopEventHold("Original STOP job list incomplete")
    projected=[]
    for job in rawjobs:
        if (type(job) is not dict or not contract.JOB_FIELDS.issubset(job)
            or type(job.get("steps")) is not list):
            raise StopEventHold("Original STOP job evidence invalid")
        steps=[]
        for step in job["steps"]:
            if type(step) is not dict or not contract.STEP_FIELDS.issubset(step):
                raise StopEventHold("STOP job step evidence incomplete")
            steps.append({k:step[k] for k in contract.STEP_FIELDS})
        projected.append({**{k:job[k] for k in contract.JOB_FIELDS if k!="steps"},
                          "steps":steps})
    try:
        contract._require_jobs(projected,run_id=original_id,
                               head_sha=doc["head_sha"],
                               earliest=started,latest=finished)
    except contract.StopCompletionStop:
        raise StopEventHold("Required STOP job or step did not succeed") from None
    _control(V5_PATH,token=token)
    _control(V6_PATH,token=token)
    # Read both controls twice around the observation boundary to reject
    # cross-GitHub changes during this job. Never report broker completion.
    _control(V5_PATH,token=token)
    _control(V6_PATH,token=token)
    return {
        "status":"STOP_WORKFLOW_AND_CONTROLS_ONLY_BROKER_NOT_OBSERVED",
        "original_dispatch_run_id":original_id,
        "required_jobs_verified":3,
        "both_current_controls_stop_observed":True,
        "broker_open_orders_observed":False,
        "broker_fills_verified":False,
        "signed_receipt_produced":False,
        "stop_completed":False,
        "new_order_authorized":False,
    }


if __name__=="__main__":
    try:
        print(json.dumps(observe_once(),sort_keys=True))
    except StopEventHold:
        print('{"status":"STOP_EVENT_EVIDENCE_HOLD",'
              '"stop_completed":false,"new_order_authorized":false}')
        raise SystemExit(1) from None

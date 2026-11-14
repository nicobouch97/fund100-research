"""Explicit, independent GitHub GET-only STOP-run recheck (NOT a STOP receipt).

This is a credentialless brokerless fallback for GitHub's suppressed
GITHUB_TOKEN -> workflow_dispatch -> workflow_run event cascade.
A workflow_dispatch string is only an *untrusted locator*: read original
GitHub run, exact three job/step records and protected-main STOP controls
from authenticated GitHub GETs, or fail red. This cannot dispatch STOP,
cancel an order, inspect Alpaca, sign a receipt, or authorize trading.
No historical run becomes a fresh broker risk PASS.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re

import fund100_stop_workflow_run_event_getonly_v1_0 as gh
import fund100_v6_emergency_stop_completion_evidence_v1_0 as contract

REPO = "nicobouch97/fund100-research"
WORKFLOW_REF = (REPO + "/.github/workflows/"
                "fund100-stop-explicit-original-getonly.yml@refs/heads/main")
NO_BROKER = True
NO_GITHUB_WRITE = True
NO_STOP_DISPATCH = True
NO_SIGNER = True
NO_TRADE = True
NO_STOP_COMPLETION_CLAIM = True
MAX_INPUT_BYTES = 20000
MAX_AGE_SECONDS = 180


class ExplicitStopHold(RuntimeError):
    pass


def _scope() -> None:
    e = os.environ
    if (not all((NO_BROKER, NO_GITHUB_WRITE, NO_STOP_DISPATCH,
                 NO_SIGNER, NO_TRADE, NO_STOP_COMPLETION_CLAIM))
        or e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != REPO
        or e.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or re.fullmatch(r"[0-9a-f]{40}", e.get("GITHUB_SHA","")) is None
        or any(k in e for k in (
            "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "ALPACA_PAPER_KEY",
            "ALPACA_PAPER_SECRET", "FUND100_GH_STOP_DISPATCH_TOKEN",
            "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
        ))):
        raise ExplicitStopHold("Explicit STOP observer scope is untrusted")


def _run_id() -> int:
    path = os.environ.get("GITHUB_EVENT_PATH","")
    if (type(path) is not str
        or not path.startswith("/home/runner/work/")
        or not path.endswith("/event.json")):
        raise ExplicitStopHold("GitHub-authored dispatch event unavailable")
    try:
        with open(path,"rb") as f:
            raw=f.read(MAX_INPUT_BYTES+1)
        if len(raw)>MAX_INPUT_BYTES:
            raise ExplicitStopHold("Oversized STOP input")
        data=json.loads(raw)
    except (OSError, UnicodeError, TypeError, ValueError):
        raise ExplicitStopHold("Malformed STOP input") from None
    if type(data) is not dict or type(data.get("inputs")) is not dict:
        raise ExplicitStopHold("No exact STOP-run input")
    inputs=data["inputs"]
    if set(inputs)!={"original_stop_run_id"}:
        raise ExplicitStopHold("Unexpected STOP dispatch inputs")
    value=inputs.get("original_stop_run_id")
    if (type(value) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",value) is None):
        raise ExplicitStopHold("Malformed STOP run locator")
    return int(value)


def _verify(original_id: int, token: str) -> dict:
    # The input is NEVER completion evidence: all results below must be
    # re-read from GitHub, and current protected-main STOP is checked twice.
    if (type(original_id) is not int or original_id<=0
        or original_id>=10**20):
        raise ExplicitStopHold("Untrusted original run ID")
    doc=gh._get(gh.API+"/actions/runs/"+str(original_id),token=token)
    if (not contract.RUN_FIELDS.issubset(doc)
        or type(doc.get("id")) is not int or doc["id"]!=original_id
        or doc.get("name")!=contract.WORKFLOW_NAME
        or doc.get("path")!=gh.STOP_PATH
        or doc.get("event")!="workflow_dispatch"
        or doc.get("head_branch")!="main"
        or doc.get("status")!="completed"
        or doc.get("conclusion")!="success"
        or type(doc.get("run_attempt")) is not int
        or doc["run_attempt"]!=1
        or re.fullmatch(r"[0-9a-f]{40}",doc.get("head_sha","")) is None):
        raise ExplicitStopHold("Original STOP run not independently verified")
    try:
        created=contract._utc(doc["created_at"])
        started=contract._utc(doc["run_started_at"])
        finished=contract._utc(doc["updated_at"])
    except contract.StopCompletionStop:
        raise ExplicitStopHold("Original STOP chronology invalid") from None
    now=datetime.now(timezone.utc)
    if (not created<=started<=finished<=now
        or (finished-created).total_seconds()>contract.MAX_STOP_TOTAL_SECONDS
        or not 0<=(now-finished).total_seconds()<=MAX_AGE_SECONDS):
        raise ExplicitStopHold("Original STOP too old or delayed")
    jobsdoc=gh._get(
        gh.API+"/actions/runs/"+str(original_id)+"/jobs?per_page=100",
        token=token)
    raw=jobsdoc.get("jobs")
    if (type(jobsdoc.get("total_count")) is not int
        or jobsdoc["total_count"]!=len(contract.REQUIRED_JOBS)
        or type(raw) is not list or len(raw)!=len(contract.REQUIRED_JOBS)):
        raise ExplicitStopHold("Exact original STOP jobs missing")
    projected=[]
    for j in raw:
        if (type(j) is not dict or not contract.JOB_FIELDS.issubset(j)
            or type(j.get("steps")) is not list):
            raise ExplicitStopHold("Malformed STOP job")
        steps=[]
        for s in j["steps"]:
            if type(s) is not dict or not contract.STEP_FIELDS.issubset(s):
                raise ExplicitStopHold("Malformed STOP job step")
            steps.append({k:s[k] for k in contract.STEP_FIELDS})
        projected.append({**{k:j[k] for k in contract.JOB_FIELDS
                             if k!="steps"},"steps":steps})
    try:
        contract._require_jobs(
            projected,run_id=original_id,head_sha=doc["head_sha"],
            earliest=started,latest=finished)
    except contract.StopCompletionStop:
        raise ExplicitStopHold("STOP jobs not independently successful") from None
    for path in (gh.V5_PATH,gh.V6_PATH,gh.V5_PATH,gh.V6_PATH):
        gh._control(path,token=token)
    return {
        "status":"EXPLICIT_ORIGINAL_STOP_AND_MAIN_ONLY_NO_BROKER",
        "original_dispatch_run_id":original_id,
        "required_jobs_verified":3,
        "both_controls_stop":True,
        "broker_observed":False,
        "broker_fills_verified":False,
        "signed_stop_receipt":False,
        "stop_completed":False,
        "order_authorized":False,
    }


def observe_once() -> dict:
    _scope()
    original_id=_run_id()
    token=gh._token()
    try:
        return _verify(original_id,token)
    except (gh.StopEventHold, contract.StopCompletionStop):
        raise ExplicitStopHold("Authenticated original STOP GET failed") from None


if __name__=="__main__":
    try:
        print(json.dumps(observe_once(),sort_keys=True))
    except Exception:
        print('{"status":"EXPLICIT_STOP_GET_UNVERIFIED_HOLD",'
              '"stop_completed":false,"order_authorized":false}')
        raise SystemExit(1) from None

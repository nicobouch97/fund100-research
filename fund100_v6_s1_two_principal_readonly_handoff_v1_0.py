"""Verify a trusted, successful original 7-GET workflow as a private-read handoff.

Pure metadata contract only. No imports of the writer, no broker or private
Git credential/network code. The source 7-GET job must itself have enforced
the original redacted no-matching-client-IDs output before concluding SUCCESS.

A successful handoff is NOT a LIVE order release: risk, one-writer CAS,
immutable anti-rollback head, spread, order-time quotes and separate GO remain
unverified. All checks are source and time bounded.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import re

SCHEMA="FUND100_V6_S1_TWO_PRINCIPAL_READONLY_HANDOFF_V1"
REPO="nicobouch97/fund100-research"
BROKER_WORKFLOW_ID=389825871
BROKER_WORKFLOW_PATH=".github/workflows/fund100-v6-s1-original-client-id-getonly.yml"
BROKER_WORKFLOW_NAME="Fund-100 V6-S1 REAL LIVE Original Client-ID GET only (NO ORDERS)"
BROKER_JOB="genuine-private-live-client-id-read"
OFFLINE_JOB="original-safety-and-credential-boundary-tests"
REQUIRED_BROKER_STEPS=(
    "Verify exact original Git blob pins and protected read-only approval",
    "Query three genuine original V6 migration client IDs (NO ORDER POST)",
    "Preserve original funded account STOP after source read",
)
MAX_SOURCE_AGE_SECONDS=300
SOURCE_CONTRACT_CATEGORICAL_404_IN_BROKER_JOB=True
PRIVATE_GIT_WRITER_INCLUDED=False
ALPACA_CREDENTIALS_INCLUDED=False
FUNDED_TRADING_ENABLED=False

class HandoffStop(ValueError):pass

def _utc(text):
    if type(text) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",text):
        raise HandoffStop("Source UTC timestamp malformed")
    try: return datetime.fromisoformat(text[:-1]+"+00:00")
    except ValueError:raise HandoffStop("Source UTC timestamp invalid") from None

def _source_job(j):
    if (type(j) is not dict or j.get("status")!="completed"
        or j.get("conclusion")!="success"
        or type(j.get("steps")) is not list):
        raise HandoffStop("Original protected job not fully successful")
    by_name={}
    for step in j["steps"]:
        if type(step) is not dict or type(step.get("name")) is not str:
            raise HandoffStop("Original broker job steps malformed")
        name=step["name"]
        if name in by_name: raise HandoffStop("Duplicate original step identity")
        by_name[name]=step
    for name in REQUIRED_BROKER_STEPS:
        if name not in by_name or (by_name[name].get("status")!="completed"
                                   or by_name[name].get("conclusion")!="success"):
            raise HandoffStop("Required original GET/STOP step was not successful")

def verify(*, run:dict,jobs:dict,checked_main_sha:str,
           observed_at_utc:str)->dict:
    """Verify GitHub-source metadata fresh on current trusted default main."""
    if (type(run) is not dict or type(jobs) is not dict
        or type(checked_main_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}",checked_main_sha) is None):
        raise HandoffStop("Authenticated current main SHA not supplied")
    if (run.get("repository",{}).get("full_name")!=REPO
        or run.get("head_repository",{}).get("full_name")!=REPO
        or run.get("workflow_id")!=BROKER_WORKFLOW_ID
        or run.get("path")!=BROKER_WORKFLOW_PATH
        or run.get("name")!=BROKER_WORKFLOW_NAME
        or run.get("head_branch")!="main"
        or run.get("event") not in ("push","workflow_dispatch")
        or run.get("head_sha")!=checked_main_sha
        or run.get("status")!="completed"
        or run.get("conclusion")!="success"
        or type(run.get("id")) is not int or run["id"]<=0
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"]<1):
        raise HandoffStop("Original verified protected main workflow source mismatch")
    created=_utc(run.get("created_at"))
    updated=_utc(run.get("updated_at"))
    observed=_utc(observed_at_utc)
    if (updated<created or observed<updated
        or observed-updated>timedelta(seconds=MAX_SOURCE_AGE_SECONDS)
        or updated-created>timedelta(minutes=20)):
        raise HandoffStop("Broker source stale, future or excessive run duration")
    if (type(jobs.get("jobs")) is not list
        or jobs.get("total_count")!=2 or len(jobs["jobs"])!=2):
        raise HandoffStop("Original workflow's two jobs not completely verified")
    by_name={}
    for j in jobs["jobs"]:
        if type(j) is not dict or type(j.get("name")) is not str:
            raise HandoffStop("Original GitHub job metadata malformed")
        if j["name"] in by_name:raise HandoffStop("Repeated GitHub job identity")
        by_name[j["name"]]=j
    if set(by_name)!={BROKER_JOB,OFFLINE_JOB}:
        raise HandoffStop("Expected original protected source job absent")
    offline=by_name[OFFLINE_JOB]
    if offline.get("status")!="completed" or offline.get("conclusion")!="success":
        raise HandoffStop("Original broker static credential pin tests not passed")
    _source_job(by_name[BROKER_JOB])
    return {
        "schema":SCHEMA,
        "status":"TWO_PRINCIPAL_SOURCE_HANDOFF_READY_FOR_SEPARATE_SIGNED_READ",
        "original_real_broker_job_authenticated_by_GitHub":True,
        "broker_source_current_main_commit_matched":True,
        "broker_source_within_five_minutes":True,
        "original_broker_redacted_three_404_condition_enforced_by_upstream_job":True,
        "broker_404_never_POST_guarantee":False,
        "external_witness_is_immutable_antirollback":False,
        "separate_private_HMAC_GET_still_required":True,
        "same_runner_has_broker_and_private_ledger_secrets":False,
        "real_broker_GETs_by_this_handoff":0,
        "real_private_Git_GETs_by_this_handoff":0,
        "real_private_Git_PUTs":0,
        "real_broker_POSTs":0,
        "orders_authorized":False,
        "private_head":None,"account_ID":None,
        "shares":None,"client_order_ids":None,"order_payload":None,
    }

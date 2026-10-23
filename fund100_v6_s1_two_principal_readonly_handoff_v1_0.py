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
RISK_WORKFLOW_ID=389731134
RISK_WORKFLOW_PATH=".github/workflows/fund100-v6-s1-live-flow-timing-native-none.yml"
RISK_WORKFLOW_NAME="Fund-100 V6-S1 LIVE Funding Timing and NONE History Seven GET (NO ORDERS)"
RISK_JOB="authentic-private-seven-get"
RISK_PASS_STEP="Confirm source-verified postfunding HIGH account risk (NO RELEASE)"
RISK_OFFLINE_JOB="nontrading-source-and-scope-fixtures"
REQUIRED_RISK_STEPS=(
    "Check credential eligibility only for reviewed exact seven-GET source",
    "Query actual private funding timing and native NONE series (SEVEN GET ONLY)",
    "Confirm original STOP remains disabled",
)
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

def _source_job(j,*,run_created,run_updated,observed,required_steps=REQUIRED_BROKER_STEPS):
    """Date-bound the original *GET step*, not only the GitHub run update."""
    if (type(j) is not dict or j.get("status")!="completed"
        or j.get("conclusion")!="success"
        or type(j.get("steps")) is not list):
        raise HandoffStop("Original protected job not fully successful")
    started=_utc(j.get("started_at"))
    completed=_utc(j.get("completed_at"))
    if (started<run_created or started>completed
        or completed>run_updated or observed<completed):
        raise HandoffStop("Protected broker job time inconsistent with original run")
    by_name={}
    for step in j["steps"]:
        if type(step) is not dict or type(step.get("name")) is not str:
            raise HandoffStop("Original broker job steps malformed")
        name=step["name"]
        if name in by_name: raise HandoffStop("Duplicate original step identity")
        by_name[name]=step
    timeline=[]
    for name in required_steps:
        if name not in by_name or (by_name[name].get("status")!="completed"
                                   or by_name[name].get("conclusion")!="success"):
            raise HandoffStop("Required original GET/STOP step was not successful")
        step=by_name[name]
        began=_utc(step.get("started_at"))
        ended=_utc(step.get("completed_at"))
        if began<started or ended>completed or began>ended:
            raise HandoffStop("Original brokerage step observed outside protected job")
        timeline.append((began,ended))
    if (timeline[0][1]>timeline[1][0]
        or timeline[1][1]>timeline[2][0]):
        raise HandoffStop("Original broker GET must follow source pin and precede STOP")
    if (observed<timeline[1][1] or
        observed-timeline[1][1]>timedelta(seconds=MAX_SOURCE_AGE_SECONDS)):
        raise HandoffStop("Actual original seven-GET completion is stale")

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
    _source_job(by_name[BROKER_JOB],run_created=created,run_updated=updated,observed=observed)
    return {
        "schema":SCHEMA,
        "status":"TWO_PRINCIPAL_SOURCE_HANDOFF_READY_FOR_SEPARATE_SIGNED_READ",
        "original_real_broker_job_authenticated_by_GitHub":True,
        "broker_source_current_main_commit_matched":True,
        "broker_source_within_five_minutes":True,
        "actual_original_seven_GET_step_freshness_verified":True,
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


def verify_current_risk_source(*, run:dict, jobs:dict,
                               checked_main_sha:str, observed_at_utc:str)->dict:
    """Authenticate protected original READ+controller STOP workflow metadata.

    Actual categorization is executed within the source-pinned broker job.
    This handoff cannot read/rededuce private broker raw return values; a
    successful upstream run proves only its required nontrading STOP, not
    independent cashflow-adjusted account risk or order authorization.
    """
    if (type(run) is not dict or type(jobs) is not dict
        or type(checked_main_sha) is not str
        or re.fullmatch(r"[a-f0-9]{40}",checked_main_sha) is None):
        raise HandoffStop("Original risk-source metadata malformed")
    if (run.get("repository",{}).get("full_name")!=REPO
        or run.get("head_repository",{}).get("full_name")!=REPO
        or run.get("workflow_id")!=RISK_WORKFLOW_ID
        or run.get("path")!=RISK_WORKFLOW_PATH
        or run.get("name")!=RISK_WORKFLOW_NAME
        or run.get("head_branch")!="main"
        or run.get("head_sha")!=checked_main_sha
        or run.get("event") not in ("push","workflow_dispatch")
        or run.get("status")!="completed" or run.get("conclusion")!="success"
        or type(run.get("id")) is not int or run["id"]<=0
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"]<1):
        raise HandoffStop("Wrong protected original seven-GET risk-source run")
    created=_utc(run.get("created_at"))
    updated=_utc(run.get("updated_at"))
    observed=_utc(observed_at_utc)
    if (updated<created or observed<updated
        or observed-updated>timedelta(seconds=MAX_SOURCE_AGE_SECONDS)
        or updated-created>timedelta(minutes=20)):
        raise HandoffStop("Broker risk-source stale or inconsistent")
    if (type(jobs.get("jobs")) is not list
        or jobs.get("total_count")!=2 or len(jobs["jobs"])!=2):
        raise HandoffStop("Original risk-source job set incomplete")
    by_name={}
    for j in jobs["jobs"]:
        if (type(j) is not dict or type(j.get("name")) is not str
            or j["name"] in by_name):
            raise HandoffStop("Original risk-source job identities invalid")
        by_name[j["name"]]=j
    if set(by_name)!={RISK_OFFLINE_JOB,RISK_JOB}:
        raise HandoffStop("Original risk-source expected jobs missing")
    offline=by_name[RISK_OFFLINE_JOB]
    if (offline.get("status")!="completed"
        or offline.get("conclusion")!="success"):
        raise HandoffStop("Original risk source had unsuccessful offline checks")
    # Reuse the original independently tested exact three-step timestamp
    # verifier while binding to the risk reader's different immutable steps.
    _source_job(by_name[RISK_JOB],run_created=created,
                run_updated=updated,observed=observed,
                required_steps=REQUIRED_RISK_STEPS)
    # The source reader writes a boolean into its own protected step output.
    # A conditional Actions step exposes only success vs skipped; validate
    # its exact identity and ordering, never parse unauthenticated logs.
    steps=by_name[RISK_JOB]["steps"]
    matches=[step for step in steps if (
        type(step) is dict and step.get("name")==RISK_PASS_STEP)]
    if len(matches)!=1:
        raise HandoffStop("Missing exact protected account-risk pass step")
    marker=matches[0]
    conclusion=marker.get("conclusion")
    if (marker.get("status")!="completed"
        or conclusion not in ("success","skipped")):
        raise HandoffStop("Original account-risk step not final")
    if conclusion=="success":
        begin=_utc(marker.get("started_at"))
        end=_utc(marker.get("completed_at"))
        if (begin>end or begin<_utc(next(step for step in steps
             if step["name"]==REQUIRED_RISK_STEPS[1])["completed_at"])
            or end>_utc(next(step for step in steps
             if step["name"]==REQUIRED_RISK_STEPS[2])["started_at"])):
            raise HandoffStop("Original account-risk pass step not between GET and STOP")
    return {
        "schema":SCHEMA,
        "status":"CURRENT_RISK_SOURCE_STOP_READY_FOR_PRIVATE_HMAC_READ",
        "original_broker_risk_controller_job_authenticated_by_GitHub":True,
        "same_main_SHA_and_fresh_GET_step_verified":True,
        "upstream_controller_stop_ran_successfully":True,
        "source_verified_postfunding_6_20_35":conclusion=="success",
        "complete_private_HMAC_verified":False,
        "cashflow_adjusted_1M_account_risk_approved":False,
        "separate_private_HMAC_GET_still_required":True,
        "signed_ledger_future_head_release_present":False,
        "real_broker_GETs_by_this_handoff":0,
        "real_broker_POSTs":0,"real_private_Git_PUTs":0,
        "orders_authorized":False,
        "private_head":None,"account_ID":None,"broker_order_payload":None,
    }


def verify_any_source(*, run:dict, jobs:dict, checked_main_sha:str,
                      observed_at_utc:str)->dict:
    """Accept either reviewed original broker evidence, never arbitrary jobs."""
    if type(run) is not dict:
        raise HandoffStop("Missing original source run")
    if run.get("workflow_id")==RISK_WORKFLOW_ID:
        return verify_current_risk_source(
            run=run,jobs=jobs,checked_main_sha=checked_main_sha,
            observed_at_utc=observed_at_utc)
    return verify(
        run=run,jobs=jobs,checked_main_sha=checked_main_sha,
        observed_at_utc=observed_at_utc)


def join_current_risk_and_signed_genesis(*, source:dict, genesis:dict)->dict:
    """Join metadata-authenticated stopped risk run and HMAC-signed seq0.

    Only the caller operating inside the protected two-principal workflow
    authenticates both sources. Caller-provided dicts elsewhere are NOT
    authenticated evidence. The signed genesis has no order reservation.
    """
    if (type(source) is not dict
        or source.get("schema")!=SCHEMA
        or source.get("status")!="CURRENT_RISK_SOURCE_STOP_READY_FOR_PRIVATE_HMAC_READ"
        or source.get("same_main_SHA_and_fresh_GET_step_verified") is not True
        or source.get("upstream_controller_stop_ran_successfully") is not True
        or type(source.get("source_verified_postfunding_6_20_35")) is not bool
        or source.get("orders_authorized") is not False
        or type(genesis) is not dict
        or genesis.get("status")!="GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY"
        or genesis.get("private_genesis_HMAC_signature_and_original_account_binding_verified") is not True
        or genesis.get("independent_public_issue8_comment_digest_and_identity_verified") is not True
        or genesis.get("private_ledger_sequence")!=0
        or genesis.get("original_empty_entries_count")!=0
        or genesis.get("private_git_writes")!=0
        or genesis.get("broker_orders")!=0
        or genesis.get("independently_immutable_rollback_anchor_proven") is not False):
        raise HandoffStop("Original source and HMAC genesis do not reconcile")
    return {
        "schema":SCHEMA,
        "status":"STOPPED_REAL_RISK_AND_SIGNED_EMPTY_LEDGER_READS_JOINED",
        "source_and_signed_genesis_proven_in_same_protected_workflow":True,
        "risk_source_approved_for_live_orders":False,
        "postfunding_account_6_20_35_read_evidence":
            source["source_verified_postfunding_6_20_35"],
        "signed_ledger_has_real_post_reservation":False,
        "immutable_future_rollback_anchor_verified":False,
        "source_to_ledger_order_identity_reconciled":False,
        "staged_controller_trade_release":False,
        "orders_authorized":False,
        "broker_POSTs":0,"private_Git_PUTs":0,
        "private_account_data":None,"private_signed_ledger":None,
    }

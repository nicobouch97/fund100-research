"""Offline-only completion evidence for Fund-100's existing emergency STOP.

GitHub workflow_dispatch API v2026-03-10 returns HTTP 200 and a workflow
run ID. This proves only which run was requested, NOT that the STOP latches
were committed or broker orders were cancelled. The verifier binds that
exact run ID to ALL three jobs and independent state/broker observations.

Caller-supplied dictionaries are not authenticated evidence: a FUTURE separately
reviewed reader must fetch GitHub run/jobs via authenticated read-only API and
V5/V6 current-main latches, plus fresh read-only OAuth broker account/orders.
No reader, bearer, broker secret or STOP dispatcher is deployed by this file.
It never proves absence of fills: an order can fill before cancellation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re

import fund100_live_emergency_stop_v1_0 as legacy_cancel
import fund100_v6_s1_first_acwi_signed_cancel_only_v1_0 as signed_cancel
import fund100_v6_s1_operator_control_v2_0 as v6

SCHEMA = "FUND100_V6_EMERGENCY_STOP_COMPLETION_EVIDENCE_V1"
STOP_COMPLETION_SOURCE_RELEASED = False
EXPECTED_BROKER_ACCOUNT_BINDING_SHA256 = None
NO_NETWORK = True
NO_BROKER_WRITE = True
NO_GITHUB_WRITE = True
NO_ORDER_RELEASE = True
NO_CLAIM_ABOUT_BROKER_FILLS = True

REPO = "nicobouch97/fund100-research"
WORKFLOW = ".github/workflows/fund100-live-emergency-stop.yml"
WORKFLOW_NAME = "Fund-100 STOP TRADING (operator emergency)"
MAX_DISPATCH_DELAY_SECONDS = 90
MAX_STOP_TOTAL_SECONDS = 180
MAX_OBSERVATION_AGE_SECONDS = 30
MAX_POST_ALARM_VERIFICATION_SECONDS = 240
RUN_FIELDS = frozenset((
    "id","name","path","event","status","conclusion","head_branch",
    "head_sha","run_attempt","created_at","run_started_at","updated_at",
))
JOB_FIELDS = frozenset((
    "run_id","name","status","conclusion","head_sha","started_at",
    "completed_at","steps",
))
STEP_FIELDS = frozenset(("name","status","conclusion"))
REQUIRED_JOBS = {
    "Immediately set the persistent STOP latch": (
        "Commit STOPPED to GitHub main",
        "Independently stop V6 first ACWI execution latch on current main",
    ),
    "Cancel only outstanding Fund-100 Alpaca orders": (
        "Cancel and verify only Fund-100 orders",
    ),
    "Independently cancel only signed original V6 ACWI SELL": (
        "Verify emergency workflow provenance before any broker secret",
        "Cancel only original signed V6 ACWI SELL and verify broker open orders",
    ),
}


class StopCompletionStop(RuntimeError):
    """Do not promote dispatch ACK or incomplete evidence to verified STOP."""


def _utc(value: object) -> datetime:
    if type(value) is not str or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise StopCompletionStop("Noncanonical emergency evidence timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise StopCompletionStop("Invalid emergency evidence time") from None


def _sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _require_jobs(jobs: object, *, run_id: int, head_sha: str,
                  earliest: datetime, latest: datetime) -> None:
    if type(jobs) is not list or len(jobs) != len(REQUIRED_JOBS):
        raise StopCompletionStop("Exact STOP and cancel job set unavailable")
    seen = set()
    for job in jobs:
        if (type(job) is not dict or set(job) != JOB_FIELDS
            or job.get("name") not in REQUIRED_JOBS
            or job["name"] in seen
            or type(job.get("run_id")) is not int
            or job["run_id"] != run_id
            or job.get("head_sha") != head_sha
            or job.get("status") != "completed"
            or job.get("conclusion") != "success"):
            raise StopCompletionStop("Unqualified emergency job completion")
        seen.add(job["name"])
        started, completed = _utc(job["started_at"]), _utc(job["completed_at"])
        if not earliest <= started <= completed <= latest:
            raise StopCompletionStop("Emergency job did not complete in time")
        steps = job["steps"]
        required = set(REQUIRED_JOBS[job["name"]])
        if type(steps) is not list or len(steps) < len(required):
            raise StopCompletionStop("Missing exact emergency STOP/cancel steps")
        actual = set()
        for step in steps:
            if (type(step) is not dict or set(step) != STEP_FIELDS
                or type(step["name"]) is not str
                or step["name"] in actual
                or step.get("status") != "completed"
                or step.get("conclusion") != "success"):
                raise StopCompletionStop("Untrusted emergency step completion")
            actual.add(step["name"])
        if not required.issubset(actual):
            raise StopCompletionStop("Mandatory STOP/cancel step not completed")
    if seen != set(REQUIRED_JOBS):
        raise StopCompletionStop("Emergency STOP/cancel workflow incomplete")


def verify_emergency_stop_completion(*, run: object, jobs: object,
                                     expected_dispatch_run_id: int,
                                     v5_control: object, v6_control: object,
                                     broker_account: object,
                                     broker_open_orders: object,
                                     alarm_detected_at_utc: str,
                                     controls_observed_at_utc: str,
                                     broker_observed_at_utc: str,
                                     now_utc: datetime | None = None) -> dict:
    """Check trusted-source-projected evidence only; no I/O or dispatch.

    This merely verifies zero OPEN Fund-100 orders at one observed point,
    NOT that no orders filled or that a future broker query cannot change.
    Even a verified STOP never grants permission to trade.
    """
    if STOP_COMPLETION_SOURCE_RELEASED is not True:
        raise StopCompletionStop("Independent STOP completion source HARD LOCKED")
    if (type(EXPECTED_BROKER_ACCOUNT_BINDING_SHA256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", EXPECTED_BROKER_ACCOUNT_BINDING_SHA256)
        is None or not all((NO_NETWORK is True, NO_BROKER_WRITE is True,
                            NO_GITHUB_WRITE is True, NO_ORDER_RELEASE is True,
                            NO_CLAIM_ABOUT_BROKER_FILLS is True))):
        raise StopCompletionStop("Approved independent account/policy unavailable")
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise StopCompletionStop("Independent UTC clock unavailable")
    now = now.astimezone(timezone.utc)
    alarm = _utc(alarm_detected_at_utc)
    if not alarm <= now or (now-alarm).total_seconds() > MAX_POST_ALARM_VERIFICATION_SECONDS:
        raise StopCompletionStop("Emergency alarm stale or in future")
    # The caller must bind the run ID returned by the actual authenticated
    # dispatch. An arbitrary recent manual STOP run cannot be substituted.
    if (type(expected_dispatch_run_id) is not int
        or expected_dispatch_run_id <= 0
        or type(run) is not dict or set(run) != RUN_FIELDS
        or type(run.get("id")) is not int
        or run["id"] != expected_dispatch_run_id
        or run.get("name") != WORKFLOW_NAME
        or run.get("path") != WORKFLOW
        or run.get("event") != "workflow_dispatch"
        or run.get("head_branch") != "main"
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or type(run.get("run_attempt")) is not int
        or run["run_attempt"] != 1
        or not _sha(run.get("head_sha"))):
        raise StopCompletionStop("Wrong emergency workflow provenance/conclusion")
    created, started, finished = (
        _utc(run["created_at"]), _utc(run["run_started_at"]),
        _utc(run["updated_at"]),
    )
    if (not alarm <= created <= started <= finished <= now
        or (created-alarm).total_seconds() > MAX_DISPATCH_DELAY_SECONDS
        or (finished-alarm).total_seconds() > MAX_STOP_TOTAL_SECONDS):
        raise StopCompletionStop("Emergency workflow started/finished too late")
    _require_jobs(jobs, run_id=run["id"], head_sha=run["head_sha"],
                  earliest=started, latest=finished)

    # Recheck BOTH independent persistent latches as observed on current main.
    if (type(v5_control) is not dict
        or v5_control != {"schema":"FUND100_OPERATOR_CONTROL_V1",
                         "trading_enabled":False}
        or type(v5_control.get("trading_enabled")) is not bool
        or type(v6_control) is not dict
        or set(v6_control) != {
            "schema","risk_level","pilot_capital_ceiling_usd",
            "trading_enabled","first_original_acwi_sell_enabled"
        }):
        raise StopCompletionStop("Current main operator STOP not independently proven")
    try:
        v6._validate(v6_control)
    except Exception:
        raise StopCompletionStop("V6 current operator policy invalid") from None
    if (v6_control["trading_enabled"] is not False
        or v6_control["first_original_acwi_sell_enabled"] is not False):
        raise StopCompletionStop("V6 current main STOP remains unconfirmed")

    # Distinct broker GETs AFTER workflow and fresh controls; no cancellation
    # acknowledgement or job success can substitute for an Alpaca read.
    observed_controls = _utc(controls_observed_at_utc)
    observed_broker = _utc(broker_observed_at_utc)
    for observed in (observed_controls, observed_broker):
        if (not finished <= observed <= now
            or (now-observed).total_seconds() > MAX_OBSERVATION_AGE_SECONDS):
            raise StopCompletionStop("Independent STOP/broker observation stale")
    if (type(broker_account) is not dict
        or type(broker_account.get("id")) is not str
        or not broker_account["id"].strip()):
        raise StopCompletionStop("Account identity not independently proven")
    bound = sha256(("FUND100-LIVE-ACCOUNT|" +
                    broker_account["id"].strip()).encode()).hexdigest()
    if bound != EXPECTED_BROKER_ACCOUNT_BINDING_SHA256:
        raise StopCompletionStop("Broker account binding changed")

    try:
        legacy_targets = legacy_cancel.select_fund100_open_orders(
            broker_open_orders)
        signed_targets = signed_cancel._targets(broker_open_orders)
    except Exception:
        raise StopCompletionStop("Broker open order listing untrusted") from None
    if legacy_targets or signed_targets:
        raise StopCompletionStop("Outstanding Fund-100 order remains OPEN")

    return {
        "schema": SCHEMA,
        "status": "CURRENT_STOP_AND_OPEN_ORDER_ABSENCE_OBSERVED",
        "current_main_v5_stop": True,
        "current_main_v6_stop": True,
        "required_stop_and_cancel_jobs_completed": 3,
        "open_fund100_orders_at_observation": 0,
        "new_trading_orders_authorized": False,
        "broker_fills_or_settlement_verified": False,
        "no_possible_future_fill_guarantee": False,
        "dispatch_http_200_alone_is_stop_proof": False,
    }

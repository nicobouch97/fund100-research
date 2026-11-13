"""Fund-100 independent Railway schedule observer: credential-free DRY RUN.

Does not inspect broker risk, submit/cancel orders, obtain account balances,
write GitHub, use API secrets, create permissions or attest a risk PASS.
This is *only* a prototype for identifying missing scheduled workflow runs.
Successful observations must NEVER be promoted to live trade permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA = "FUND100_RAILWAY_CREDENTIAL_FREE_SCHEDULE_OBSERVER_V1"
MODE = "DRY_RUN_NO_BROKER"
API = ("https://api.github.com/repos/nicobouch97/fund100-research/"
       "actions/workflows/fund100-live-risk-watch.yml/runs"
       "?event=schedule&per_page=1")
EXPECTED_WORKFLOW_PATH = ".github/workflows/fund100-live-risk-watch.yml"
V6_WORKFLOW_PATH = ".github/workflows/fund100-v6-s1-independent-risk-watch.yml"
V6_API = ("https://api.github.com/repos/nicobouch97/fund100-research/"
          "actions/workflows/fund100-v6-s1-independent-risk-watch.yml/runs"
          "?event=schedule&per_page=1")
# V6 cron starts at 13:09 UTC. Allow 20 minutes after the first slot for
# provider queuing; after 23:15 UTC a day is out of observation scope.
V6_FIRST_HEARTBEAT_DUE_HOUR = 13
V6_FIRST_HEARTBEAT_DUE_MINUTE = 29
V6_LAST_HEARTBEAT_DUE_HOUR = 23
V6_LAST_HEARTBEAT_DUE_MINUTE = 15
MAX_RESPONSE_BYTES = 16000
MAX_AGE_SECONDS = 45 * 60  # diagnostic only, not an order-time risk limit
POLL_SECONDS = 600         # 6 public GET requests/hr at most (per replica)
NO_BROKER = True
NO_AUTH = True
NO_WRITE = True
NO_TRADE = True


class ScheduleObservationError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ScheduleObservationError("GitHub schedule API redirected")


def _time(raw: object) -> datetime:
    if (type(raw) is not str
        or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", raw) is None):
        raise ScheduleObservationError("Noncanonical schedule time")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise ScheduleObservationError("Invalid schedule time") from None


def classify(doc: object, *, now: datetime,
             expected_path: str = EXPECTED_WORKFLOW_PATH) -> dict:
    """Classify source activity ONLY; no risk PASS or market-open inference."""
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ScheduleObservationError("Observation time must be aware")
    utc_now = now.astimezone(timezone.utc)
    if expected_path not in (EXPECTED_WORKFLOW_PATH,V6_WORKFLOW_PATH):
        raise ScheduleObservationError("Untrusted watched workflow")
    if type(doc) is not dict or type(doc.get("workflow_runs")) is not list:
        raise ScheduleObservationError("Invalid GitHub schedule response")
    runs = doc["workflow_runs"]
    if type(doc.get("total_count")) is not int or doc["total_count"] < 0:
        raise ScheduleObservationError("Invalid GitHub run count")
    if len(runs) > 1 or (not runs and doc["total_count"] != 0):
        raise ScheduleObservationError("Ambiguous GitHub run count")
    if not runs:
        return {"observation": "NO_RECORDED_SCHEDULE_RUN",
                "seconds_since_last_recorded_run": None}
    run = runs[0]
    if (type(run) is not dict
        or run.get("path") != expected_path
        or run.get("event") != "schedule"
        or run.get("head_branch") != "main"
        or type(run.get("id")) is not int
        or run["id"] <= 0):
        raise ScheduleObservationError("Unexpected watcher run identity")
    seen = _time(run.get("created_at"))
    age = int((utc_now - seen).total_seconds())
    if age < 0:
        raise ScheduleObservationError("Future-dated GitHub schedule run")
    return {
        "observation": ("SCHEDULE_RUN_RECORDED_NOT_RISK_PASS"
                        if age <= MAX_AGE_SECONDS
                        else "SCHEDULE_ACTIVITY_STALE"),
        "seconds_since_last_recorded_run": age,
    }


def _read_public_schedule(*, transport=None, api: str = API) -> object:
    """One bounded, unauthenticated, nonredirecting public REST GET."""
    if api not in (API, V6_API):
        raise ScheduleObservationError("Unapproved schedule source")
    req = Request(api, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-independent-schedule-observer-dryrun",
        "Cache-Control": "no-store",
    })
    if req.get_method() != "GET" or req.full_url != api:
        raise ScheduleObservationError("Unexpected network request")
    send = build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with send(req, timeout=12) as resp:
            if resp.status != 200:
                raise ScheduleObservationError("Public schedule API non-200")
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ScheduleObservationError("Public schedule response oversized")
        return json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError,
            ValueError, UnicodeError, TypeError):
        raise ScheduleObservationError("Public schedule data unavailable") from None


def _v6_schedule_due(now: datetime) -> bool:
    """Only expect a V6 cron after its first weekday due time UTC."""
    if now.weekday() >= 5:
        return False
    minute = now.hour * 60 + now.minute
    return (V6_FIRST_HEARTBEAT_DUE_HOUR * 60 + V6_FIRST_HEARTBEAT_DUE_MINUTE
            <= minute <
            V6_LAST_HEARTBEAT_DUE_HOUR * 60 + V6_LAST_HEARTBEAT_DUE_MINUTE)


def observe_once(*, now: datetime | None = None, transport=None) -> dict:
    """Always denies order authority, including on errors and missing source."""
    utc_now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(utc_now, datetime) or utc_now.tzinfo is None:
        raise ScheduleObservationError("Invalid observation clock")
    utc_now = utc_now.astimezone(timezone.utc)
    try:
        result = classify(_read_public_schedule(transport=transport), now=utc_now)
    except Exception:
        result = {"observation": "SOURCE_UNAVAILABLE",
                  "seconds_since_last_recorded_run": None}
    # Independently query the ACTUAL new V6 workflow, not merely the YAML
    # cron declaration. A V6 run can only establish schedule activity;
    # even a recent successful run cannot attest brokerage risk.
    due = _v6_schedule_due(utc_now)
    try:
        v6_result = classify(
            _read_public_schedule(transport=transport, api=V6_API),
            now=utc_now, expected_path=V6_WORKFLOW_PATH)
    except Exception:
        v6_result = {"observation":"SOURCE_UNAVAILABLE",
                     "seconds_since_last_recorded_run":None}
    v6_missing = (due and
        v6_result["observation"] != "SCHEDULE_RUN_RECORDED_NOT_RISK_PASS")
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "observed_at_utc": utc_now.isoformat().replace("+00:00", "Z"),
        "observation": result["observation"],
        "seconds_since_last_recorded_run":
            result["seconds_since_last_recorded_run"],
        "v6_schedule_due": due,
        "v6_observation": v6_result["observation"],
        "v6_seconds_since_last_recorded_run":
            v6_result["seconds_since_last_recorded_run"],
        "v6_schedule_heartbeat_missing_or_stale": bool(v6_missing),
        "github_read_only_requests_max": 2,
        "broker_requests": 0,
        "github_writes": 0,
        "order_posts": 0,
        "risk_pass_attested": False,
        "trading_authorized": False,
    }


def main() -> None:
    # This executable deliberately lacks all order/risk credentials. Its
    # Railway environment is explicitly non-production and must stay so.
    if os.environ.get("FUND100_MODE") != MODE:
        raise SystemExit("Dry-run mode missing; observer will not start")
    while True:
        print(json.dumps(observe_once(), sort_keys=True), flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

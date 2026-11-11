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


def classify(doc: object, *, now: datetime) -> dict:
    """Classify source activity ONLY; no risk PASS or market-open inference."""
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ScheduleObservationError("Observation time must be aware")
    utc_now = now.astimezone(timezone.utc)
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
        or run.get("path") != EXPECTED_WORKFLOW_PATH
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


def _read_public_schedule(*, transport=None) -> object:
    """One bounded, unauthenticated, nonredirecting public REST GET."""
    req = Request(API, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-independent-schedule-observer-dryrun",
        "Cache-Control": "no-store",
    })
    if req.get_method() != "GET" or req.full_url != API:
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
    return {
        "schema": SCHEMA,
        "mode": MODE,
        "observed_at_utc": utc_now.isoformat().replace("+00:00", "Z"),
        "observation": result["observation"],
        "seconds_since_last_recorded_run":
            result["seconds_since_last_recorded_run"],
        "github_read_only_requests_max": 1,
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

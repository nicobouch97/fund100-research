"""GET-only proof of a recent, scheduled, independently PASSED LIVE risk watch.

A successful GitHub Actions job by itself is NOT risk evidence: the existing
watcher also exits successfully when operator STOPPED, without broker GETs.
Require the exact separately named PASS-only step on the latest scheduled run.
This only adds a conservative admission veto; it NEVER authorizes an order.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
WATCH_PATH = ".github/workflows/fund100-live-risk-watch.yml"
WORKFLOW_RUNS = API + "/actions/workflows/fund100-live-risk-watch.yml/runs?event=schedule&per_page=20"
WATCH_JOB_NAME = "Independent LIVE account risk watch"
CHECK_STEP = "Check risk or trigger persistent STOP"
PASS_STEP = "Attest independent LIVE broker risk PASS"
MAX_AGE_SECONDS = 20 * 60
MAX_RUN_DURATION_SECONDS = 10 * 60
MAX_RESPONSE_BYTES = 300000
NO_BROKER_ACCESS = True
NO_GITHUB_WRITES = True
NO_TRADE_RELEASE = True


class RiskWatchAdmissionStop(RuntimeError):
    """No trustworthy recent scheduled independent risk PASS; no order."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RiskWatchAdmissionStop("Risk-watch API redirect; STOP")


def _get(url: str, token: str, *, transport=None) -> dict:
    if (not url.startswith(API + "/actions/")
        or type(token) is not str or len(token.strip()) < 10
        or token != token.strip() or "\r" in token or "\n" in token):
        raise RiskWatchAdmissionStop("Risk-watch API scope or credential invalid")
    req = Request(url, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-readonly-risk-pass-gate",
        "Cache-Control": "no-store",
    })
    send = build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with send(req, timeout=10) as response:
            if response.status != 200:
                raise RiskWatchAdmissionStop("Risk-watch API non-200; STOP")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RiskWatchAdmissionStop("Risk-watch API oversized; STOP")
        doc = json.loads(raw)
        if type(doc) is not dict:
            raise RiskWatchAdmissionStop("Risk-watch API wrong shape; STOP")
        return doc
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
            ValueError, TypeError):
        raise RiskWatchAdmissionStop("Risk-watch API unavailable; STOP") from None


def _time(value: object) -> datetime:
    if (type(value) is not str
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                        value) is None):
        raise RiskWatchAdmissionStop("Risk-watch timestamp not canonical")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise RiskWatchAdmissionStop("Risk-watch timestamp invalid") from None


def _one_step_ok(steps: object, name: str) -> bool:
    if type(steps) is not list:
        return False
    matches = [s for s in steps
               if type(s) is dict and s.get("name") == name]
    return (len(matches) == 1
            and matches[0].get("status") == "completed"
            and matches[0].get("conclusion") == "success")


def require_recent_scheduled_risk_pass(*, token: str, main_sha: str,
                                      now_utc: datetime | None = None,
                                      transport=None) -> bool:
    """Check latest scheduled run, latest actual job and PASS-only step.

    Missing, delayed, queued, failed, manually dispatched, stopped, wrong
    SHA, replayed, malformed, or unverifiable evidence always denies trade.
    Even PASS is not a substitute for fresh same-order broker risk, STOP,
    settled cash, economic NO_TRADE and signed order idempotency checks.
    """
    if (type(main_sha) is not str
        or re.fullmatch(r"[0-9a-f]{40}", main_sha) is None):
        raise RiskWatchAdmissionStop("Risk-watch expected main SHA invalid")
    now = datetime.now(timezone.utc) if now_utc is None else now_utc
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise RiskWatchAdmissionStop("Risk-watch observation clock invalid")
    now = now.astimezone(timezone.utc)
    listing = _get(WORKFLOW_RUNS, token, transport=transport)
    runs = listing.get("workflow_runs")
    if type(runs) is not list or not runs or len(runs) > 20:
        raise RiskWatchAdmissionStop("No complete scheduled watcher listing")
    if any(type(r) is not dict for r in runs):
        raise RiskWatchAdmissionStop("Malformed scheduled watcher listing")
    # Never fall back to an older PASS when a newer scheduled run FAILED.
    latest = max(runs, key=lambda r: _time(r.get("created_at")))
    run_id = latest.get("id")
    if (type(run_id) is not int or run_id <= 0
        or latest.get("name") != "Fund-100 LIVE Risk Watch (autonomous)"
        or latest.get("path") != WATCH_PATH
        or latest.get("event") != "schedule"
        or latest.get("head_branch") != "main"
        or latest.get("head_sha") != main_sha
        or latest.get("run_attempt") != 1
        or latest.get("status") != "completed"
        or latest.get("conclusion") != "success"):
        raise RiskWatchAdmissionStop("Latest scheduled watcher not a valid PASS")
    began = _time(latest.get("created_at"))
    ended = _time(latest.get("updated_at"))
    if (not 0 <= (ended - began).total_seconds() <= MAX_RUN_DURATION_SECONDS
        or not 0 <= (now - ended).total_seconds() <= MAX_AGE_SECONDS):
        raise RiskWatchAdmissionStop("Scheduled watcher stale, future or delayed")
    jobs_url = API + "/actions/runs/" + str(run_id) + "/jobs?per_page=100"
    jobs_doc = _get(jobs_url, token, transport=transport)
    jobs = jobs_doc.get("jobs")
    if (type(jobs_doc.get("total_count")) is not int
        or jobs_doc["total_count"] != 1 or type(jobs) is not list
        or len(jobs) != 1 or type(jobs[0]) is not dict):
        raise RiskWatchAdmissionStop("Watcher job evidence incomplete")
    job = jobs[0]
    if (job.get("name") != WATCH_JOB_NAME
        or job.get("run_id") != run_id
        or job.get("head_sha") != main_sha
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or not _one_step_ok(job.get("steps"), CHECK_STEP)
        or not _one_step_ok(job.get("steps"), PASS_STEP)):
        raise RiskWatchAdmissionStop("No verified scheduled broker-risk PASS step")
    return True

"""V6-S1: verify protected Actions private read proof from public GitHub metadata.

Never requests any private repository content, reads protected secrets, changes
GitHub state, or accesses Alpaca. Success proves ONLY protected Actions GET.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import os

SCHEMA = "FUND100_V6_PROTECTED_ACTIONS_READ_EVIDENCE_STATUS_V1"
REPO = "nicobouch97/fund100-research"
WORKFLOW = "fund100-v6-s1-protected-private-readonly-proof.yml"
WORKFLOW_PATH = ".github/workflows/" + WORKFLOW
ROOT = Path(__file__).resolve().parent
EARLIEST = datetime(2026, 10, 21, tzinfo=timezone.utc)
RUNS = (f"https://api.github.com/repos/{REPO}/actions/workflows/"
        f"{WORKFLOW}/runs?branch=main&event=workflow_dispatch&per_page=30")
PROTECTED_JOB = "protected-main-private-get-only"
OFFLINE_JOB = "offline-no-credential-source-contract"
PROTECTED_STEPS = frozenset((
    "Validate unchanged main, STOP, and immutable private two-GET probe",
    "Authenticate private repo identity and README only (redacted two GET)",
    "Confirm original operator STOP still applies",
))
BROKER_NETWORK_ALLOWED = False
PRIVATE_STATE_ACCESS_ALLOWED = False
TRADE_ALLOWED = False


class StatusStop(ValueError):
    pass


def timestamp(raw: object) -> datetime:
    if type(raw) is not str:
        raise StatusStop("Untrusted evidence timestamp")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise StatusStop("Untrusted evidence timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise StatusStop("Noncanonical evidence timestamp")
    return parsed


def original_stop(root: Path = ROOT) -> bool:
    control = json.loads((root / "fund100_live_operator_control.json").read_text())
    manifest = json.loads((
        root / "research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"
    ).read_text())
    return bool(
        control.get("schema") == "FUND100_OPERATOR_CONTROL_V1"
        and control.get("trading_enabled") is False
        and manifest.get("original_trial_max_capital_usd") == "130.30"
        and manifest.get("risk_tier") == "HIGH"
        and manifest.get("status") == "PROPOSED_NOT_LIVE"
        and manifest.get("investable_gross_fraction") == "0.95"
        and manifest.get("live_operator_trading_enabled") is False
        and manifest.get("live_environment_kill_switch") == "ENGAGED"
        and manifest.get("live_order_execution_released") is False
        and manifest.get("broker_order_permission_granted_by_this_file") is False
    )


def _run_identity(r: object) -> bool:
    if type(r) is not dict:
        return False
    repo = r.get("repository")
    return bool(
        isinstance(repo, dict)
        and repo.get("full_name") == REPO
        and r.get("path") == WORKFLOW_PATH
        and r.get("event") == "workflow_dispatch"
        and r.get("head_branch") == "main"
        and type(r.get("id")) is int
        and 0 < r["id"] < 2**63
        and r.get("status") in ("completed", "queued", "in_progress",
                                "requested", "waiting", "pending")
        and r.get("conclusion") in (None, "success", "failure",
                                    "cancelled", "timed_out", "skipped",
                                    "action_required", "startup_failure")
        and timestamp(r.get("created_at")) >= EARLIEST
    )


def select_latest_run(payload: object) -> dict | None:
    if type(payload) is not dict or type(payload.get("workflow_runs")) is not list:
        raise StatusStop("GitHub Actions run evidence absent")
    runs = payload["workflow_runs"]
    if len(runs) > 30:
        raise StatusStop("Unexpected run pagination")
    eligible = []
    for entry in runs:
        try:
            if _run_identity(entry):
                eligible.append(entry)
        except StatusStop:
            # A malformed entry cannot prove any source.
            continue
    return (max(eligible, key=lambda x: (timestamp(x["created_at"]), x["id"]))
            if eligible else None)


def verify_jobs(latest: dict, job_data: object) -> bool:
    if (latest.get("status") != "completed"
        or latest.get("conclusion") != "success"
        or type(job_data) is not dict
        or type(job_data.get("jobs")) is not list
        or len(job_data["jobs"]) > 100):
        return False
    jobs = job_data["jobs"]
    if len(jobs) != 2 or len(set(j.get("name") for j in jobs if isinstance(j, dict))) != 2:
        return False
    by_name = {
        job["name"]: job for job in jobs
        if type(job) is dict and type(job.get("name")) is str
    }
    if set(by_name) != {OFFLINE_JOB, PROTECTED_JOB}:
        return False
    if any(j.get("status") != "completed" or
           j.get("conclusion") != "success" for j in by_name.values()):
        return False
    protected = by_name[PROTECTED_JOB]
    steps = protected.get("steps")
    if type(steps) is not list:
        return False
    matching = [step for step in steps
                if type(step) is dict and step.get("name") in PROTECTED_STEPS]
    return (
        len(matching) == len(PROTECTED_STEPS)
        and {s["name"] for s in matching} == PROTECTED_STEPS
        and all(s.get("status") == "completed"
                and s.get("conclusion") == "success" for s in matching)
    )


def assess(*, run_data: object, job_data: object | None,
           stopped: bool = True) -> dict:
    if stopped is not True:
        raise StatusStop("Original operator STOP or V6 manifest changed")
    latest = select_latest_run(run_data)
    result = {
        "schema": SCHEMA,
        "source_github_repo": REPO,
        "source_workflow": WORKFLOW_PATH,
        "original_operator_stopped": True,
        "protected_private_actions_read_status": "NOT_PROVEN",
        "most_recent_manual_main_run_id": None,
        "most_recent_manual_main_run_conclusion": None,
        "missing_manual_main_run": latest is None,
        "eligible_successful_protected_main_run": False,
        "private_repo_read_proved_via_protected_GITHUB_ACTIONS": False,
        "connector_identity_is_not_actions_token_proof": True,
        "two_get_access_must_not_be_interpreted_as_write_permission": True,
        "private_state_CAS_write_permission_proven": False,
        "private_production_state_initialized": False,
        "broker_cash_settlement_or_buying_power_revalidated": False,
        "broker_positions_recently_revalidated_by_this_report": False,
        "s1_live_strategy_released": False,
        "paper_or_live_order_authorized": False,
        "account_original_ceiling_usd": "130.30",
        "pilot_risk_level": "HIGH",
        "original_s1_proposal_gross_entry_fraction": "0.95",
        "live_launch_ready": False,
        "live_broker_requests": 0,
        "live_orders": 0,
        "private_repository_reads": 0,
        "private_repository_writes": 0,
    }
    if latest is None:
        return result
    result["most_recent_manual_main_run_id"] = latest["id"]
    result["most_recent_manual_main_run_conclusion"] = latest["conclusion"]
    if latest["status"] != "completed" or latest["conclusion"] != "success":
        result["protected_private_actions_read_status"] = (
            "LATEST_MANUAL_MAIN_RUN_NOT_SUCCESSFUL")
        return result
    if not verify_jobs(latest, job_data):
        result["protected_private_actions_read_status"] = (
            "LATEST_RUN_PROTECTED_JOB_OR_STEP_NOT_PROVEN")
        return result
    result["protected_private_actions_read_status"] = (
        "VERIFIED_PROTECTED_ACTIONS_PRIVATE_READ")
    result["eligible_successful_protected_main_run"] = True
    result["private_repo_read_proved_via_protected_GITHUB_ACTIONS"] = True
    return result


def _get(url: str, token: str) -> dict:
    allowed = url == RUNS or (
        url.startswith(f"https://api.github.com/repos/{REPO}/actions/runs/")
        and url.endswith("/jobs?per_page=100")
        and url[len(f"https://api.github.com/repos/{REPO}/actions/runs/"):-len(
            "/jobs?per_page=100")].isdigit()
    )
    if not allowed:
        raise StatusStop("Unapproved GitHub public Actions metadata GET")
    if not token:
        raise StatusStop("Unprivileged Actions read token is unavailable")
    req = Request(url, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-v6-protected-read-proof-status",
    })
    try:
        with urlopen(req, timeout=12) as response:
            if response.status != 200:
                raise StatusStop("GitHub Actions source unavailable")
            raw = response.read(500_001)
        if len(raw) > 500_000:
            raise StatusStop("GitHub Actions metadata oversized")
        obj = json.loads(raw)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        raise StatusStop("GitHub Actions read-only source unavailable") from None
    if type(obj) is not dict:
        raise StatusStop("GitHub Actions source not structured")
    return obj


def retrieve(*, token: str, root: Path = ROOT) -> dict:
    if not original_stop(root):
        raise StatusStop("Original broker STOP/risk/cap manifest changed")
    try:
        run_data = _get(RUNS, token)
        latest = select_latest_run(run_data)
        job_data = None
        if latest is not None and latest.get("status") == "completed" and latest.get("conclusion") == "success":
            uri = f"https://api.github.com/repos/{REPO}/actions/runs/{latest['id']}/jobs?per_page=100"
            job_data = _get(uri, token)
        return assess(run_data=run_data, job_data=job_data, stopped=True)
    except StatusStop:
        report = assess(run_data={"workflow_runs": []}, job_data=None,
                        stopped=True)
        report["protected_private_actions_read_status"] = (
            "GITHUB_ACTIONS_PUBLIC_METADATA_EVIDENCE_UNAVAILABLE")
        return report


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN", "")
    report = retrieve(token=token)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

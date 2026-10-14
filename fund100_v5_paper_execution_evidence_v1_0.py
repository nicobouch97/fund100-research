"""Sanitized artifact for a completed genuine strategy -> Alpaca PAPER fill.

Does NOT touch a broker, issue permits, authorize orders, or change strategy
state. Evidence is only produced after a successfully reconciled real run.
A GitHub artifact is an audit record, not independent broker confirmation
or authority to activate LIVE trading.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

REPO = "nicobouch97/fund100-research"
STATUS = "PAPER_EVENT_FILLED_AND_RECONCILED"
REPORT = Path("/tmp/fund100-v5-paper-genuine-report.json")
STATE = Path("shadow_outputs/v5_002/shadow_state.json")
OUTPUT = Path("/tmp/fund100-v5-paper-execution-evidence.json")


class PaperEvidenceStop(ValueError):
    pass


def digest(body: dict) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _hex(value: object, length: int) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value)
    )


def build_evidence(*, report: object, shadow: object, run_id: object,
                   commit_sha: object, observed_utc: object) -> dict:
    if not isinstance(report, dict) or not isinstance(shadow, dict):
        raise PaperEvidenceStop("Runner and strategy state must be JSON objects.")
    if not (
        report.get("status") == STATUS
        and report.get("paper_execution_attempted") is True
        and report.get("reconciled") is True
        and type(report.get("paper_post_count")) is int
        and report["paper_post_count"] > 0
        and report.get("live_post_count") == 0
        and type(report.get("live_post_count")) is int
        and report.get("risk_level") in {"LOW", "MEDIUM", "HIGH"}
        and _hex(report.get("attested_compiler_sha256"), 64)
        and _hex(report.get("attested_event_sha256"), 64)
    ):
        raise PaperEvidenceStop("No verified genuine PAPER fill in runner report.")
    if (
        shadow.get("strategy") != "V5-002_SHADOW"
        or shadow.get("pending_source") != "SCHEDULED"
        or not isinstance(shadow.get("pending_target"), dict)
        or not shadow["pending_target"]
    ):
        raise PaperEvidenceStop("Source was not a real pending scheduled signal.")
    try:
        signal_date = shadow["last_date"]
        if date.fromisoformat(signal_date).isoformat() != signal_date:
            raise ValueError("noncanonical source date")
        timestamp = datetime.fromisoformat(observed_utc.replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("not UTC")
    except (ValueError, AttributeError, TypeError, KeyError) as exc:
        raise PaperEvidenceStop("Unverifiable source date or evidence clock.") from exc
    if type(run_id) is not int or run_id <= 0 or not _hex(commit_sha, 40):
        raise PaperEvidenceStop("Invalid GitHub run or exact source commit.")
    body = {
        "schema": "FUND100_GENUINE_V5_PAPER_FILL_EVIDENCE_V1",
        "result": "RECONCILED_PAPER_FILL_REPORTED",
        "strategy": "V5-002_SHADOW",
        "broker_environment": "ALPACA_PAPER_ONLY",
        "source_event": "GENUINE_SCHEDULED_SHADOW_EVENT",
        "signal_date": signal_date,
        "source_shadow_state_sha256": digest(shadow),
        "attested_compiler_sha256": report["attested_compiler_sha256"],
        "attested_event_sha256": report["attested_event_sha256"],
        "risk_level": report["risk_level"],
        "paper_order_submissions": report["paper_post_count"],
        "paper_fills_reconciled": True,
        "live_orders_submitted": 0,
        "live_order_authorized": False,
        "github_commit_sha": commit_sha,
        "github_run_id": run_id,
        "github_run_url": f"https://github.com/{REPO}/actions/runs/{run_id}",
        "generated_utc": timestamp.isoformat(),
        "note": "Sanitized runner attestation and broker-reconciliation result; "
                "not independent brokerage audit, LIVE permission, or proof of edge.",
    }
    return {**body, "evidence_sha256": digest(body)}


def main() -> None:
    if (
        os.getenv("GITHUB_REPOSITORY") != REPO
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("ALPACA_LIVE_KEY")
        or os.getenv("ALPACA_LIVE_SECRET")
    ):
        raise PaperEvidenceStop("Evidence workflow is not PAPER-only and STOPPED.")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    shadow = json.loads(STATE.read_text(encoding="utf-8"))
    try:
        run_id = int(os.environ["GITHUB_RUN_ID"])
    except (KeyError, ValueError) as exc:
        raise PaperEvidenceStop("Missing GitHub run identifier.") from exc
    body = build_evidence(
        report=report, shadow=shadow,
        run_id=run_id, commit_sha=os.getenv("GITHUB_SHA"),
        observed_utc=datetime.now(timezone.utc).isoformat(),
    )
    OUTPUT.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print("Genuine PAPER fill: sanitized evidence generated.")
    print("LIVE order authorization: NO; LIVE submissions: ZERO.")


if __name__ == "__main__":
    main()

"""V5 shadow-learning scorecard: offline, source-only, zero broker access.

Parses the existing append-only V5-002 shadow ledger and its latest report.
Does NOT execute strategy/broker code, infer broker fills, create orders,
modify artifacts, submit trades or change a funded model.

This is a descriptive SHADOW scorecard, not verified LIVE alpha evidence.
"""

from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path
import sys

STRATEGY = "V5-002_SHADOW"
COLUMNS = [
    "date", "row_type", "strategy", "previous_chain_hash",
    "chain_hash", "payload_json",
]
ROOT = Path(__file__).resolve().parent
SHADOW_DIR = ROOT / "shadow_outputs" / "v5_002"


class ScorecardStop(ValueError):
    """Unreliable or tampered shadow evidence: report nothing."""


def _finite_number(obj: dict, key: str) -> float:
    value = obj.get(key)
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ScorecardStop(f"Missing/nonfinite shadow metric: {key}")
    return float(value)


def _require_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(
        actual, expected, rel_tol=0.0, abs_tol=1e-8
    ):
        raise ScorecardStop(f"Shadow report / ledger mismatch: {label}")


def build_shadow_scorecard(
    ledger_text: str,
    report: dict,
    state: dict,
    manifest: dict,
    revision_text: str = "",
) -> dict:
    """Validate the chain and report before returning descriptive metrics."""
    if not all(isinstance(item, dict) for item in (report, state, manifest)):
        raise ScorecardStop("Malformed shadow report/state/manifest")
    if any(
        item.get("strategy") != STRATEGY
        for item in (report, state, manifest)
    ):
        raise ScorecardStop("Shadow strategy identity mismatch")
    manifest_hash = manifest.get("manifest_hash")
    if not isinstance(manifest_hash, str) or len(manifest_hash) != 64:
        raise ScorecardStop("Missing frozen manifest hash")
    if any(
        item.get("manifest_hash") != manifest_hash
        for item in (report, state)
    ):
        raise ScorecardStop("Shadow manifest lineage mismatch")

    reader = csv.DictReader(io.StringIO(ledger_text))
    if reader.fieldnames != COLUMNS:
        raise ScorecardStop("Unexpected shadow ledger schema")
    previous = "GENESIS"
    prior_date = None
    records: list[dict] = []
    last_cost = last_turnover = 0.0
    max_drawdown = 0.0
    peak = 0.0
    nonzero_turnover_sessions = 0
    positive_days = negative_days = flat_days = 0
    for idx, row in enumerate(reader):
        if None in row or any(row.get(key) is None for key in COLUMNS):
            raise ScorecardStop("Malformed ledger row")
        try:
            payload = json.loads(row["payload_json"])
        except (ValueError, TypeError) as exc:
            raise ScorecardStop("Invalid ledger payload") from exc
        if not isinstance(payload, dict):
            raise ScorecardStop("Invalid ledger payload type")
        if row["previous_chain_hash"] != previous:
            raise ScorecardStop("Broken shadow hash chain")
        expected = hashlib.sha256(
            (previous + "|" + row["payload_json"]).encode("utf-8")
        ).hexdigest()
        if row["chain_hash"] != expected:
            raise ScorecardStop("Invalid shadow ledger hash")
        previous = expected
        try:
            observation_day = date.fromisoformat(row["date"])
        except ValueError as exc:
            raise ScorecardStop("Invalid shadow date") from exc
        if prior_date is not None and observation_day <= prior_date:
            raise ScorecardStop("Non-ascending shadow date")
        prior_date = observation_day
        required_row_type = "BASELINE" if idx == 0 else "SHADOW_FORWARD"
        if any((
            row["row_type"] != required_row_type,
            row["strategy"] != STRATEGY,
            payload.get("row_type") != row["row_type"],
            payload.get("date") != row["date"],
            payload.get("strategy") != STRATEGY,
            payload.get("manifest_hash") != manifest_hash,
        )):
            raise ScorecardStop("Shadow row identity/baseline mismatch")
        nav = _finite_number(payload, "nav")
        benchmark_nav = _finite_number(payload, "benchmark_nav")
        daily_return = _finite_number(payload, "daily_return")
        turnover = _finite_number(payload, "turnover")
        transaction_cost = _finite_number(payload, "transaction_cost_gbp")
        cumulative_turnover = _finite_number(payload, "cumulative_turnover")
        cumulative_cost = _finite_number(payload, "cumulative_cost_gbp")
        if (
            nav <= 0 or benchmark_nav <= 0
            or turnover < 0 or transaction_cost < 0
            or cumulative_turnover < last_turnover - 1e-9
            or cumulative_cost < last_cost - 1e-9
        ):
            raise ScorecardStop("Invalid or decreasing shadow metric")
        if idx == 0 and (turnover != 0 or transaction_cost != 0):
            raise ScorecardStop("Baseline cannot book a trade")
        if idx:
            if daily_return > 1e-12:
                positive_days += 1
            elif daily_return < -1e-12:
                negative_days += 1
            else:
                flat_days += 1
            if turnover > 1e-12:
                nonzero_turnover_sessions += 1
        peak = max(peak, nav)
        max_drawdown = max(max_drawdown, 1.0 - nav / peak)
        records.append(payload)
        last_turnover, last_cost = cumulative_turnover, cumulative_cost

    if len(records) < 2:
        raise ScorecardStop("Insufficient observed shadow sessions")

    start, latest = records[0], records[-1]
    if (
        report.get("last_processed_date") != latest["date"]
        or state.get("last_date") != latest["date"]
    ):
        raise ScorecardStop("Shadow state/report lag or mismatch")
    for label, value in (
        ("paper_nav_gbp", latest["nav"]),
        ("benchmark_nav_gbp", latest["benchmark_nav"]),
        ("cumulative_cost_gbp", latest["cumulative_cost_gbp"]),
        ("cumulative_turnover", latest["cumulative_turnover"]),
    ):
        if label in report:
            _require_close(_finite_number(report, label), value, label)
    _require_close(
        _finite_number(state, "nav"), latest["nav"], "state.nav"
    )
    _require_close(
        _finite_number(state, "benchmark_nav"),
        latest["benchmark_nav"], "state.benchmark_nav",
    )
    if state.get("pending_target") != latest.get("pending_target"):
        raise ScorecardStop("Shadow pending target mismatch")
    if state.get("pending_source") != latest.get("pending_source"):
        raise ScorecardStop("Shadow pending source mismatch")
    for name in ("emergency_signals", "emergency_executions"):
        if state.get(name) != latest.get(name):
            raise ScorecardStop("Shadow risk-event count mismatch")

    # Revise counts are descriptive. Never use revised data to rewrite an
    # append-only historical observation or imply guaranteed returns.
    revision_rows = 0
    if revision_text:
        revisions = csv.DictReader(io.StringIO(revision_text))
        if revisions.fieldnames != [
            "detected_utc", "date", "stored_market_hash",
            "current_market_hash",
        ]:
            raise ScorecardStop("Unexpected market revision ledger schema")
        revision_rows = sum(1 for _ in revisions)
    if "market_revision_records_detected" in report:
        if report["market_revision_records_detected"] != revision_rows:
            raise ScorecardStop("Market revision count mismatch")

    start_nav = _finite_number(start, "nav")
    start_benchmark = _finite_number(start, "benchmark_nav")
    return {
        "mode": "SHADOW_SIMULATION_NOT_LIVE",
        "strategy": STRATEGY,
        "manifest_hash": manifest_hash,
        "evidence": "verified_append_only_shadow_ledger",
        "first_observation": start["date"],
        "last_observation": latest["date"],
        "completed_sessions": len(records) - 1,
        "nav_start": start_nav,
        "nav_latest": _finite_number(latest, "nav"),
        "shadow_return_pct": round(
            100 * (_finite_number(latest, "nav") / start_nav - 1), 5
        ),
        "benchmark_return_pct": round(
            100 * (
                _finite_number(latest, "benchmark_nav")
                / start_benchmark - 1
            ), 5
        ),
        "relative_wealth_pct": round(
            100 * (
                _finite_number(latest, "nav") / start_nav
                / (
                    _finite_number(latest, "benchmark_nav")
                    / start_benchmark
                ) - 1
            ), 5
        ),
        "max_shadow_drawdown_pct": round(100 * max_drawdown, 5),
        "positive_sessions": positive_days,
        "negative_sessions": negative_days,
        "flat_sessions": flat_days,
        "nonzero_turnover_sessions": nonzero_turnover_sessions,
        "cumulative_turnover": last_turnover,
        "cumulative_modeled_cost_gbp": last_cost,
        "pending_event": (
            latest.get("pending_target") is not None
            or latest.get("pending_source") is not None
        ),
        "emergency_signals": latest["emergency_signals"],
        "emergency_executions": latest["emergency_executions"],
        "market_revision_records": revision_rows,
        "live_fills": None,
        "live_net_pnl": None,
        "trade_count": None,
        "interpretation": (
            "Short shadow sample; not actual broker fills, expected alpha "
            "or authorization to promote strategy versions."
        ),
    }


def read_current_scorecard(root: Path = SHADOW_DIR) -> dict:
    """Load local redacted files, return only an analysis result."""
    def read_json(name: str) -> dict:
        return json.loads((root / name).read_text(encoding="utf-8"))

    return build_shadow_scorecard(
        (root / "shadow_ledger.csv").read_text(encoding="utf-8"),
        read_json("latest_shadow_report.json"),
        read_json("shadow_state.json"),
        read_json("shadow_manifest.json"),
        (root / "market_revision_log.csv").read_text(encoding="utf-8"),
    )


def main() -> int:
    try:
        card = read_current_scorecard()
    except (OSError, ValueError, TypeError) as exc:
        print(f"V5 SHADOW SCORECARD STOP: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(card, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

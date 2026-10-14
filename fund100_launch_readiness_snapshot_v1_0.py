"""Read-only V5-002 launch-status snapshot. NOT a LIVE execution gate.

Never fetches broker data, reads credentials, issues permits or changes controls.
Historical artifacts are informational and cannot authorize a future order.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BASE = Path("live_activation_outputs/v5_002")
INPUTS = {
    "live": BASE / "live_getonly_account_readiness_evidence_v1_0.json",
    "paper_fill": BASE / "paper_etf_fill_evidence_v1_0.json",
    "paper_readiness": BASE / "paper_readiness_evidence_v1_0.json",
    "policy": BASE / "live_micro_pilot_policy_v1_0.json",
    "release": BASE / "pre_live_release_lock_v1_9.json",
    "shadow": Path("shadow_outputs/v5_002/shadow_state.json"),
    "operator": Path("fund100_live_operator_control.json"),
}


def build_snapshot(data: dict[str, Any], *, report_date: str) -> dict[str, Any]:
    """Summarize evidence, but NEVER confer broker or execution authority."""
    datetime.strptime(report_date, "%Y-%m-%d")
    if set(data) != set(INPUTS) or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError("Required launch snapshot input missing or malformed")

    live, paper, readiness = data["live"], data["paper_fill"], data["paper_readiness"]
    policy, release, shadow, operator = (
        data["policy"], data["release"], data["shadow"], data["operator"]
    )

    schemas = {
        "live": "FUND100_LIVE_GETONLY_READINESS_V1",
        "paper_fill": "FUND100_ALPACA_PAPER_FILL_EVIDENCE_V1",
        "paper_readiness": "FUND100_PAPER_READINESS_EVIDENCE_V1",
        "policy": "FUND100_LIVE_MICRO_PILOT_POLICY_V1_1",
        "release": "FUND100_PRE_LIVE_RELEASE_LOCK_V1_9",
        "operator": "FUND100_OPERATOR_CONTROL_V1",
    }
    for key, expected in schemas.items():
        if data[key].get("schema") != expected:
            raise ValueError("Unexpected evidence schema: " + key)

    live_ok = all((
        live.get("mode") == "EXISTING_LIVE_ACCOUNT_GET_ONLY",
        live.get("risk_level") == "HIGH",
        live.get("account_active") is True,
        live.get("account_binding_matches") is True,
        live.get("all_holdings_approved") is True,
        live.get("no_open_orders") is True,
        live.get("existing_exposure_within_risk_limits") is True,
        live.get("account_history_within_risk_limits") is True,
        live.get("live_get_requests") == 4,
        live.get("live_orders_submitted") == 0,
    ))
    paper_mechanics_ok = all((
        paper.get("result") == "PASS",
        paper.get("broker_environment") == "ALPACA_PAPER_ONLY",
        paper.get("paper_buy_filled") is True,
        paper.get("paper_sell_filled") is True,
        paper.get("original_paper_share_quantity_restored") is True,
        paper.get("live_orders_submitted") == 0,
    ))
    paper_preflight_ok = all((
        readiness.get("mode") == "READ_ONLY_NO_ORDERS",
        readiness.get("paper_preflight_compatible") is True,
        readiness.get("paper_orders_submitted_by_this_check") == 0,
        readiness.get("live_orders_submitted_by_this_check") == 0,
    ))
    controls_stopped = all((
        operator.get("trading_enabled") is False,
        live.get("operator_stopped") is True,
        live.get("broker_kill_switch_engaged") is True,
    ))
    live_writer_locked = all((
        release.get("writer_connected") is False,
        release.get("writer_transport_released") is False,
        release.get("live_execution_authorized") is False,
        policy.get("live_order_authorization_present") is False,
        policy.get("autonomous_strategy_event_execution_enabled") is False,
        policy.get("capital_ceiling_usd") == "130.30",
    ))
    current_signal_pending = (
        shadow.get("strategy") == "V5-002_SHADOW"
        and shadow.get("pending_target") is not None
    )
    # A broker micro-fill is NOT a genuine strategy rebalance, even when both legs fill.
    genuine_strategy_paper_fill_proved = False
    live_snapshot_same_utc_date = (
        live.get("inspection_date_utc") == report_date
    )
    cash_for_new_1_usd_buy = live.get("cash_for_one_dollar_purchase") is True

    blockers = []
    if not live_ok:
        blockers.append("LIVE_ACCOUNT_EVIDENCE_INVALID_OR_INCOMPLETE")
    if not paper_mechanics_ok or not paper_preflight_ok:
        blockers.append("PAPER_MECHANICS_OR_PREFLIGHT_NOT_VERIFIED")
    if not genuine_strategy_paper_fill_proved:
        blockers.append("GENUINE_STRATEGY_PAPER_FILL_NOT_YET_EVIDENCED")
    if not current_signal_pending:
        blockers.append("NO_PENDING_SHADOW_STRATEGY_EVENT")
    if not cash_for_new_1_usd_buy:
        blockers.append("INSUFFICIENT_IDLE_CASH_FOR_NEW_1_USD_BUY")
    if not live_snapshot_same_utc_date:
        blockers.append("LIVE_ACCOUNT_SNAPSHOT_NOT_FROM_REPORT_DATE")
    if controls_stopped:
        blockers.append("OPERATOR_STOPPED_AND_KILL_SWITCH_ENGAGED")
    if live_writer_locked:
        blockers.append("LIVE_WRITER_LOCKED")
    if not controls_stopped or not live_writer_locked:
        blockers.append("CONTROL_STATE_REQUIRES_MANUAL_INVESTIGATION")

    return {
        "schema": "FUND100_NON_EXECUTABLE_LAUNCH_SNAPSHOT_V1",
        "report_date_utc": report_date,
        "strategy": "V5-002_SHADOW",
        "status": "NOT_READY_FOR_LIVE",
        "live_order_authorized": False,
        "paper_order_authorized": False,
        "broker_network_access": "NONE",
        "checks": {
            "historical_live_readonly_pass": live_ok,
            "historical_paper_micro_fill_pass": paper_mechanics_ok,
            "historical_paper_preflight_pass": paper_preflight_ok,
            "genuine_strategy_paper_fill_evidenced": genuine_strategy_paper_fill_proved,
            "pending_shadow_event": current_signal_pending,
            "operator_stopped": controls_stopped,
            "live_writer_locked": live_writer_locked,
            "cash_available_for_new_1_usd_buy_at_last_check": cash_for_new_1_usd_buy,
            "live_snapshot_same_utc_date": live_snapshot_same_utc_date,
        },
        "blockers": blockers,
        "next_step": "Wait for a genuine V5 PAPER event and verified reconciliation; "
                     "then obtain a fresh LIVE GET-only preflight and separate explicit "
                     "operator approval before any possible LIVE release.",
        "note": "Informational only. Same-day account evidence is not an execution "
                "permit; historical preparation, synthetic tests, and the USD 130.30 "
                "ceiling do not establish available buying power.",
    }


def load_snapshot(root: Path = ROOT, *, report_date: str | None = None) -> dict[str, Any]:
    if report_date is None:
        report_date = datetime.now(timezone.utc).date().isoformat()
    data = {}
    for key, relative in INPUTS.items():
        data[key] = json.loads((root / relative).read_text(encoding="utf-8"))
    return build_snapshot(data, report_date=report_date)


if __name__ == "__main__":
    print(json.dumps(load_snapshot(), sort_keys=True, indent=2))

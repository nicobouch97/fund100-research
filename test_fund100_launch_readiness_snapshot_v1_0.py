"""Deterministic, credential-free tests for the advisory launch snapshot."""
import copy
import json
from pathlib import Path

import pytest

from fund100_launch_readiness_snapshot_v1_0 import (
    INPUTS, build_snapshot, load_snapshot,
)

ROOT = Path(__file__).resolve().parent


def inputs():
    return {
        name: json.loads((ROOT / path).read_text(encoding="utf-8"))
        for name, path in INPUTS.items()
    }


def test_current_snapshot_is_not_live_authority():
    report = load_snapshot(ROOT, report_date="2026-10-14")
    assert report["status"] == "NOT_READY_FOR_LIVE"
    assert report["broker_network_access"] == "NONE"
    assert report["live_order_authorized"] is False
    assert report["paper_order_authorized"] is False
    assert report["checks"]["historical_live_readonly_pass"] is True
    assert report["checks"]["historical_paper_micro_fill_pass"] is True
    assert report["checks"]["genuine_strategy_paper_fill_evidenced"] is False
    assert "GENUINE_STRATEGY_PAPER_FILL_NOT_YET_EVIDENCED" in report["blockers"]


def test_old_account_snapshot_is_not_current_readiness():
    report = load_snapshot(ROOT, report_date="2026-10-15")
    assert report["checks"]["live_snapshot_same_utc_date"] is False
    assert "LIVE_ACCOUNT_SNAPSHOT_NOT_FROM_REPORT_DATE" in report["blockers"]


def test_snapshot_does_not_misread_capital_ceiling_as_cash():
    report = load_snapshot(ROOT, report_date="2026-10-14")
    assert report["checks"]["cash_available_for_new_1_usd_buy_at_last_check"] is False
    assert "INSUFFICIENT_IDLE_CASH_FOR_NEW_1_USD_BUY" in report["blockers"]


def test_corrupted_live_account_does_not_report_pass():
    data = inputs()
    data["live"]["account_binding_matches"] = False
    report = build_snapshot(data, report_date="2026-10-14")
    assert report["checks"]["historical_live_readonly_pass"] is False
    assert report["live_order_authorized"] is False


def test_probe_cannot_masquerade_as_genuine_strategy_fill():
    data = inputs()
    data["paper_fill"]["source_event"] = "GENUINE_V5_EVENT"
    data["shadow"]["pending_target"] = {"EEM": 0.1}
    report = build_snapshot(data, report_date="2026-10-14")
    assert report["checks"]["genuine_strategy_paper_fill_evidenced"] is False
    assert report["status"] == "NOT_READY_FOR_LIVE"


def test_unlocked_controls_require_investigation_not_approval():
    data = inputs()
    data["operator"]["trading_enabled"] = True
    data["release"]["writer_connected"] = True
    report = build_snapshot(data, report_date="2026-10-14")
    assert "CONTROL_STATE_REQUIRES_MANUAL_INVESTIGATION" in report["blockers"]
    assert report["live_order_authorized"] is False


def test_malformed_schemas_fail_closed():
    data = inputs()
    data["policy"]["schema"] = "UNKNOWN"
    with pytest.raises(ValueError, match="Unexpected evidence schema"):
        build_snapshot(data, report_date="2026-10-14")


def test_missing_artifact_fails_closed():
    data = inputs()
    del data["live"]
    with pytest.raises(ValueError, match="missing or malformed"):
        build_snapshot(data, report_date="2026-10-14")


def test_user_agreed_launch_first_no_forward_or_paper_profit_wait_gate():
    report = load_snapshot(ROOT, report_date="2026-10-14")
    # This report is deliberately V5-specific and does not gate the
    # initial funded V6 active experiment or authorize any order.
    assert report["strategy"] == "V5-002_SHADOW"
    assert report["legacy_v5_specific_blockers_not_a_v6_pilot_wait_gate"]
    assert not report["first_funded_active_experiment_requires_63_forward_sessions"]
    assert not report["first_funded_active_experiment_requires_months_of_paper_profit"]
    assert not report["repeat_verified_paper_order_mechanics_for_profit"]
    assert report["standing_mandate_intent_no_per_order_approval_loop"]
    assert report["project_launch_priority"] == (
        "VERIFY_V6_PROTECTED_ONE_ATTEMPT_LIVE_ORDER_AND_SETTLED_REPLACEMENT_PATH")
    assert "Do not wait" in report["next_step"]
    assert "63-session forward performance" in report["next_step"]
    assert report["live_order_authorized"] is False
    assert report["broker_network_access"] == "NONE"


def test_project_priority_correction_is_persisted_without_release_changes():
    record = (ROOT / "research_lab" /
              "FUND100_LAUNCH_FIRST_PARALLEL_RESEARCH_DECISION_2026_10_30.md")
    content = record.read_text(encoding="utf-8")
    roadmap = (ROOT / "FUND100_MULTI_ASSET_ROADMAP.md").read_text(
        encoding="utf-8")
    assert "63 sessions of V8-Q2 forward observation" in content
    assert "not launch gates" in content
    assert "LOW/MEDIUM/HIGH" in content
    assert "initial small funded active HIGH-risk experiment" in roadmap
    operator=json.loads((ROOT / "fund100_live_operator_control.json").read_text())
    v6=json.loads((ROOT / "fund100_v6_s1_operator_control.json").read_text())
    assert operator["trading_enabled"] is False
    assert v6["trading_enabled"] is False
    assert v6["first_original_acwi_sell_enabled"] is False
    assert v6["pilot_capital_ceiling_usd"] == "130.30"

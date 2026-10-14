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

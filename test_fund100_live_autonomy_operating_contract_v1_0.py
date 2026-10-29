"""Keep the owner's two-control autonomy requirement in standard pytest CI.

This does not arm trading or claim a production standing mandate exists.
It prevents recurrence of a third routine manual private audit gate and
checks the existing risk/STOP mechanism instead of inventing another UI.
"""
from pathlib import Path
import json

import fund100_live_portfolio_risk_v1_0 as risk
import fund100_v6_autonomous_event_identity_v1_0 as events
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_s1_operator_control_v2_0 as v6


ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "FUND100_AUTONOMY_OPERATING_CONTRACT.md"


def test_risk_is_an_owner_choice_in_existing_production_risk_monitor():
    assert set(risk.PROFILES) == {"LOW", "MEDIUM", "HIGH"}
    workflow = (ROOT / ".github/workflows/fund100-live-risk-watch.yml").read_text()
    assert "FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}" in workflow
    assert "schedule:" in workflow
    assert "environment: fund100-live-broker" in workflow


def test_emergency_stop_is_one_dispatch_without_trade_confirmation():
    workflow = (ROOT / ".github/workflows/fund100-live-emergency-stop.yml").read_text()
    assert "  workflow_dispatch:" in workflow
    assert "python fund100_live_operator_control_v1_0.py" in workflow
    assert "v6.commit_stop_signal()" in workflow
    assert "python fund100_live_emergency_stop_v1_0.py" in workflow
    assert "cancel-fund100-orders:" in workflow
    assert "inputs.confirmation" not in workflow
    assert "environment: fund100-live-broker" in workflow


def test_current_operator_controls_remain_stopped_not_implicitly_released():
    original = json.loads((ROOT / "fund100_live_operator_control.json").read_text())
    v6_state = json.loads((ROOT / "fund100_v6_s1_operator_control.json").read_text())
    assert operator.validate_control(original) is False
    assert v6._validate(v6_state)["trading_enabled"] is False
    assert v6_state["first_original_acwi_sell_enabled"] is False
    assert v6_state["pilot_capital_ceiling_usd"] == "130.30"


def test_recurring_event_logic_explicitly_needs_no_per_trade_approval():
    # Even without a manual approval, the event is HOLD pending authenticated
    # private journal/broker proof and a valid standing release.
    e = events.key(
        strategy_id="V6_S1_CONCENTRATED_ETF",
        signal_time_utc="2026-10-29T09:00:00Z",
        signal_sha256="a" * 64,
        deployed_strategy_release_sha256="b" * 64,
        standing_mandate_sha256="c" * 64,
    )
    checked = events.classify(current_event_id=e, observed_prior_event_ids=set())
    assert checked["manual_per_trade_approval_required"] is False
    assert checked["broker_order_authorized"] is False
    assert checked["automatic_order_submitted"] is False


def test_persisted_owner_contract_rejects_repeated_maintenance_approvals():
    policy = CONTRACT.read_text()
    for required in (
        "Exactly two routine owner controls",
        "LOW",
        "MEDIUM",
        "HIGH",
        "Emergency STOP",
        "zero owner approvals",
        "per-trade",
        "$130.30",
        "$65",
        "CLOSED UNMERGED",
        "fail-closed",
    ):
        assert required in policy

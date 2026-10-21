"""Cash-entry research alternatives must not alter existing LIVE release."""
import json
from pathlib import Path
import fund100_multi_asset_portfolio_arbiter_v1_0 as scenarios

def test_research_cash_policy_does_not_modify_original_s1_proposal():
    original=json.loads(Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json").read_text())
    assert original["status"]=="PROPOSED_NOT_LIVE"
    assert original["maximum_gross_exposure"]=="0.95"
    assert original["investable_gross_fraction"]=="0.95"
    assert original["cash_reserve_fraction"]=="0.05"
    assert original["live_order_execution_released"] is False
    assert original["live_operator_trading_enabled"] is False
    assert original["live_environment_kill_switch"]=="ENGAGED"

def test_multifund_stays_stopped_with_new_scenarios():
    state=json.loads(Path("fund100_live_operator_control.json").read_text())
    assert state["trading_enabled"] is False
    assert scenarios.LIVE_ORDERS_RELEASED is False
    assert scenarios.BROKER_NETWORK_ENABLED is False
    assert scenarios.PRIVATE_STATE_MUTATION_ENABLED is False

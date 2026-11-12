"""Pure STOP-only GitHub workflow dispatch plan; no network or credentials."""
import json
from pathlib import Path

import pytest
import fund100_v6_external_emergency_stop_dispatch_intent_v1_0 as stop

WORKFLOW = Path(".github/workflows/fund100-live-emergency-stop.yml")
DORMANT_TRADING = Path(
    ".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml")


def test_default_is_hard_locked_even_for_valid_risk_failure():
    assert stop.STOP_DISPATCH_PLANNING_RELEASED is False
    assert stop.HTTP_DISPATCH_TRANSPORT_RELEASED is False
    assert all((stop.NO_NETWORK, stop.NO_BROKER_CREDENTIAL,
                stop.NO_BROKER_POST_OR_DELETE, stop.NO_GITHUB_CONTENTS_WRITE,
                stop.NO_TRADE_RELEASE, stop.NEVER_RETRY_UNKNOWN_DISPATCH,
                stop.NEVER_REPORT_STOP_CONFIRMED))
    with pytest.raises(stop.StopDispatchIntentError, match="HARD LOCKED"):
        stop.plan_stop_only_dispatch(reason="BROKER_RISK_HOLD")


@pytest.mark.parametrize("reason", sorted(stop.OUTAGE_REASONS))
def test_offline_synthetic_failure_only_produces_exact_emergency_stop_plan(
        monkeypatch, reason):
    monkeypatch.setattr(stop, "STOP_DISPATCH_PLANNING_RELEASED", True)
    plan = stop.plan_stop_only_dispatch(reason=reason)
    assert plan == {
        "schema": stop.SCHEMA,
        "status": "STOP_DISPATCH_PLAN_NOT_SENT",
        "method_if_separately_released": "POST",
        "endpoint": (
            "https://api.github.com/repos/nicobouch97/fund100-research/"
            "actions/workflows/fund100-live-emergency-stop.yml/dispatches"),
        "json_body": '{"ref":"main"}',
        "expected_acceptance_status": 204,
        "permission_required_if_released": "Actions:write",
        "outage_category": reason,
        "dispatch_attempt_count": 0,
        "dispatch_acknowledged": False,
        "github_stop_verified": False,
        "broker_cancel_verified": False,
        "new_trading_orders_allowed": False,
        "retry_after_unknown_dispatch": False,
        "broker_credentials_included": False,
        "github_contents_write_included": False,
        "inputs": None,
    }
    assert json.loads(plan["json_body"]) == {"ref": "main"}


@pytest.mark.parametrize("reason", [
    "SUCCESS","RISK_PASS","ALREADY_STOPPED","READY_TO_TRADE",
    "broker_risk_hold","broker_risk_hold\n", "MANUAL_USER_GO",
    "any-other-workflow", "https://example.com", "", None, {}, 0, True,
])
def test_never_produce_dispatch_for_arbitrary_or_positive_input(monkeypatch,reason):
    monkeypatch.setattr(stop, "STOP_DISPATCH_PLANNING_RELEASED", True)
    with pytest.raises(stop.StopDispatchIntentError, match="risk HOLD"):
        stop.plan_stop_only_dispatch(reason=reason)


@pytest.mark.parametrize("name", [
    "HTTP_DISPATCH_TRANSPORT_RELEASED",
    "NO_NETWORK",
    "NO_BROKER_CREDENTIAL",
    "NO_BROKER_POST_OR_DELETE",
    "NO_GITHUB_CONTENTS_WRITE",
    "NO_TRADE_RELEASE",
    "NEVER_RETRY_UNKNOWN_DISPATCH",
    "NEVER_REPORT_STOP_CONFIRMED",
])
def test_contract_mutation_never_returns_intent(monkeypatch,name):
    monkeypatch.setattr(stop, "STOP_DISPATCH_PLANNING_RELEASED", True)
    monkeypatch.setattr(stop,name,
                        True if name == "HTTP_DISPATCH_TRANSPORT_RELEASED" else False)
    with pytest.raises(stop.StopDispatchIntentError, match="only-source contract"):
        stop.plan_stop_only_dispatch(reason="BROKER_RISK_HOLD")


def test_exact_existing_manual_workflow_has_stop_and_both_cancel_paths():
    assert WORKFLOW.is_file() and DORMANT_TRADING.is_file()
    w = WORKFLOW.read_text()
    assert "on:\n  workflow_dispatch:\n" in w
    assert "  schedule:" not in w
    assert "  push:" not in w
    assert "  pull_request:" not in w
    assert "  repository_dispatch:" not in w
    assert "python fund100_live_operator_control_v1_0.py" in w
    assert "v6.commit_stop_signal()" in w
    assert w.count("needs: stop-signal") == 2
    assert "python fund100_live_emergency_stop_v1_0.py" in w
    assert "python fund100_v6_s1_first_acwi_signed_cancel_only_v1_0.py" in w
    assert "if: always()" in w
    assert "cancel-in-progress: false" in w
    assert "group: fund100-operator-emergency-stop" in w
    assert "environment: fund100-live-broker" in w
    assert stop.ENDPOINT.endswith(
        "/actions/workflows/fund100-live-emergency-stop.yml/dispatches")
    assert "first-acwi-funded-once" not in stop.ENDPOINT


def test_creates_no_live_dispatch_or_credential_injection():
    code = Path(stop.__file__).read_text()
    assert "STOP_DISPATCH_PLANNING_RELEASED = False" in code
    assert "HTTP_DISPATCH_TRANSPORT_RELEASED = False" in code
    assert "method=\"POST\"" not in code
    assert "method='POST'" not in code
    assert "urlopen(" not in code
    assert "Request(" not in code
    assert "requests.post(" not in code
    assert "httpx.post(" not in code
    assert "subprocess" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "GITHUB_TOKEN" not in code
    assert "STOP_DISPATCH_PLAN_NOT_SENT" in code
    docker = Path("Dockerfile").read_text()
    assert "fund100_v6_external_emergency_stop_dispatch_intent_v1_0.py" not in docker
    actual_monitor = Path(
        "fund100_v6_s1_independent_risk_watch_v1_0.py").read_text()
    assert "fund100_v6_external_emergency_stop_dispatch_intent_v1_0" not in actual_monitor

"""Offline independent risk-watcher tests. All broker/GitHub calls mocked."""

from decimal import Decimal
from time import time

import pytest

import fund100_live_risk_monitor_v1_0 as monitor
import fund100_live_operator_control_v1_0 as operator
import fund100_live_risk_sizing_v1_0 as sizing


def account():
    return {
        "status": "ACTIVE", "trading_blocked": False,
        "equity": "102", "last_equity": "101.5",
    }


def positions():
    return [
        {"symbol": "ACWI", "qty": "1", "market_value": "76"},
        {"symbol": "EEM", "qty": "1", "market_value": "8.2"},
        {"symbol": "XLE", "qty": "1", "market_value": "8"},
        {"symbol": "XLV", "qty": "1", "market_value": "8"},
    ]


def history():
    values = [100, 101, 100.5, 101.5, 102, 101.5, 102]
    return {
        "timeframe": "1D",
        "timestamp": [
            int(time()) - (len(values) - i) * 86400
            for i in range(len(values))
        ],
        "equity": values,
    }


def policy():
    return {
        "deployment_mode": "LIVE_MICRO_PILOT",
        "capital_ceiling_usd": "130.30",
        "account_binding_sha256": "a" * 64,
        "execution_universe": ["ACWI", "EEM", "XLE", "XLV"],
        "leverage_allowed": False,
        "shorting_allowed": False,
        "additional_deposits_automatically_usable": False,
    }


def check(**kwargs):
    return monitor.inspect_live_risk(
        account=kwargs.get("account", account()),
        positions=kwargs.get("positions", positions()),
        history=kwargs.get("history", history()),
        policy=kwargs.get("policy", policy()),
        level=kwargs.get("level", "HIGH"),
        actual_account_binding=kwargs.get("binding", "a" * 64),
    )


def test_high_profile_monitor_within_limits():
    check()


def test_lower_risk_profile_triggers_on_existing_exposure():
    with pytest.raises(monitor.risks.PortfolioRiskStop):
        check(level="LOW")


def test_unexpected_account_never_accepted():
    with pytest.raises(monitor.RiskMonitorStop, match="account binding"):
        check(binding="b" * 64)


def test_short_and_unknown_positions_fail_closed():
    for invalid in [
        [{"symbol": "ACWI", "qty": "-1", "market_value": "-10"}],
        [{"symbol": "BTCUSD", "qty": "1", "market_value": "10"}],
        [{"symbol": "ACWI", "qty": "1", "market_value": "10"}] * 2,
    ]:
        with pytest.raises((monitor.RiskMonitorStop,
                            monitor.risks.PortfolioRiskStop)):
            check(positions=invalid)


def test_monitor_stop_mode_never_contacts_broker(monkeypatch):
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": False},
    )
    monkeypatch.setattr(
        monitor, "live_read_only_snapshot",
        lambda: pytest.fail("Stopped monitor contacted broker"),
    )
    assert monitor.monitor_once() == "ALREADY_STOPPED"


def test_monitor_healthy_uses_read_only_data_and_does_not_mutate(monkeypatch):
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    monkeypatch.setattr(
        monitor.operator, "commit_stop_signal",
        lambda: pytest.fail("Healthy monitor wrote STOP"),
    )
    assert monitor.monitor_once() == "WITHIN_RISK_LIMITS"


def test_auto_stop_on_risk_breach_and_cancel(monkeypatch):
    calls = []
    monkeypatch.setenv("FUND100_RISK_LEVEL", "LOW")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    monkeypatch.setattr(
        monitor.operator, "commit_stop_signal",
        lambda: calls.append("STOP"),
    )
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: calls.append("CANCEL"),
    )
    assert monitor.monitor_once() == "AUTO_STOP_CONFIRMED"
    assert calls == ["STOP", "CANCEL"]


def test_stop_commit_failure_does_not_claim_success(monkeypatch):
    monkeypatch.setenv("FUND100_RISK_LEVEL", "LOW")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    monkeypatch.setattr(
        monitor.operator, "commit_stop_signal",
        lambda: (_ for _ in ()).throw(RuntimeError("API outage")),
    )
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: pytest.fail("Cancellation before stop confirmation"),
    )
    with pytest.raises(monitor.RiskMonitorStop, match="persistent STOP"):
        monitor.monitor_once()


def test_cancel_error_cannot_claim_auto_stop_success(monkeypatch):
    monkeypatch.setenv("FUND100_RISK_LEVEL", "LOW")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    monkeypatch.setattr(monitor.operator, "commit_stop_signal", lambda: None)
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )
    with pytest.raises(monitor.RiskMonitorStop, match="cancellation"):
        monitor.monitor_once()

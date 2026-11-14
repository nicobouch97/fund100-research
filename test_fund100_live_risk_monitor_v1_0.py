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
        "account_blocked": False,
        "trade_suspended_by_user": False,
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



@pytest.mark.parametrize("flag,value",[
    ("trading_blocked", None),
    ("trading_blocked", "false"),
    ("trading_blocked", 0),
    ("trading_blocked", True),
    ("account_blocked", None),
    ("account_blocked", "false"),
    ("account_blocked", 0),
    ("account_blocked", True),
    ("trade_suspended_by_user", None),
    ("trade_suspended_by_user", "false"),
    ("trade_suspended_by_user", 0),
    ("trade_suspended_by_user", True),
])
def test_live_broker_account_unknown_or_blocked_flags_never_pass(flag,value):
    evidence=account()
    evidence[flag]=value
    with pytest.raises(monitor.RiskMonitorStop,match="unavailable"):
        check(account=evidence)


@pytest.mark.parametrize("field",[
    "trading_blocked","account_blocked","trade_suspended_by_user"])
def test_missing_broker_restriction_flag_never_passes(field):
    evidence=account()
    del evidence[field]
    with pytest.raises(monitor.RiskMonitorStop,match="unavailable"):
        check(account=evidence)


def test_ambiguous_account_flag_auto_stops_before_cancel(monkeypatch):
    events=[]
    monkeypatch.setenv("FUND100_RISK_LEVEL","HIGH")
    monkeypatch.setattr(monitor.operator,"read_current_control",lambda:{
        "schema":operator.CONTROL_SCHEMA,"trading_enabled":True
    })
    bad=account()
    bad.pop("trading_blocked")
    monkeypatch.setattr(monitor,"live_read_only_snapshot",lambda:(
        bad,positions(),history(),policy(),"a"*64
    ))
    monkeypatch.setattr(monitor.operator,"commit_stop_signal",
                        lambda:(events.append("STOP"),"STOPPED")[1])
    monkeypatch.setattr(monitor.emergency,"cancel_open_fund100_orders",
                        lambda:(events.append("CANCEL"),0)[1])
    assert monitor.monitor_once()=="AUTO_STOP_CONFIRMED"
    assert events==["STOP","CANCEL"]


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
        lambda: (calls.append("STOP"),"STOPPED")[1],
    )
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: (calls.append("CANCEL"),0)[1],
    )
    assert monitor.monitor_once() == "AUTO_STOP_CONFIRMED"
    assert calls == ["STOP", "CANCEL"]


def test_stop_commit_failure_still_attempts_cancellation(monkeypatch):
    events = []
    monkeypatch.setenv("FUND100_RISK_LEVEL", "LOW")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    def broken_stop():
        events.append("STOP_ATTEMPT")
        raise RuntimeError("synthetic GitHub outage")
    monkeypatch.setattr(monitor.operator, "commit_stop_signal", broken_stop)
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: (events.append("CANCEL_ATTEMPT"), 0)[1],
    )
    with pytest.raises(monitor.RiskMonitorStop, match="persistent STOP"):
        monitor.monitor_once()
    assert events == ["STOP_ATTEMPT", "CANCEL_ATTEMPT"]


def test_cancel_error_cannot_claim_auto_stop_success(monkeypatch):
    monkeypatch.setenv("FUND100_RISK_LEVEL", "LOW")
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(monitor, "live_read_only_snapshot", lambda: (
        account(), positions(), history(), policy(), "a" * 64
    ))
    monkeypatch.setattr(monitor.operator, "commit_stop_signal", lambda: "STOPPED")
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )
    with pytest.raises(monitor.RiskMonitorStop, match="cancellation"):
        monitor.monitor_once()


def test_unknown_operator_control_attempts_stop_and_cancel(monkeypatch):
    calls = []
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: (_ for _ in ()).throw(RuntimeError("synthetic GitHub 503")),
    )
    monkeypatch.setattr(
        monitor, "live_read_only_snapshot",
        lambda: pytest.fail("No broker risk PASS on unknown GitHub control"),
    )
    monkeypatch.setattr(monitor.operator, "commit_stop_signal",
                        lambda: (calls.append("STOP"), "STOPPED")[1])
    monkeypatch.setattr(monitor.emergency, "cancel_open_fund100_orders",
                        lambda: (calls.append("CANCEL"), 0)[1])
    assert monitor.monitor_once() == "AUTO_STOP_CONFIRMED"
    assert calls == ["STOP", "CANCEL"]


@pytest.mark.parametrize("stop_outcome", [None, "STARTED", "MAYBE", True])
def test_invalid_stop_result_holds_even_if_orders_cancelled(
        monkeypatch, stop_outcome):
    calls = []
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(
        monitor, "live_read_only_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("synthetic broker outage")),
    )
    monkeypatch.setattr(monitor.operator, "commit_stop_signal",
                        lambda: (calls.append("STOP"), stop_outcome)[1])
    monkeypatch.setattr(monitor.emergency, "cancel_open_fund100_orders",
                        lambda: (calls.append("CANCEL"), 0)[1])
    with pytest.raises(monitor.RiskMonitorStop, match="persistent STOP"):
        monitor.monitor_once()
    assert calls == ["STOP", "CANCEL"]


@pytest.mark.parametrize("cancel_return", [None, True, -1, "0"])
def test_invalid_cancel_response_never_claims_verified(
        monkeypatch, cancel_return):
    calls = []
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": True},
    )
    monkeypatch.setattr(
        monitor, "live_read_only_snapshot",
        lambda: (_ for _ in ()).throw(RuntimeError("synthetic broker outage")),
    )
    monkeypatch.setattr(monitor.operator, "commit_stop_signal",
                        lambda: (calls.append("STOP"), "STOPPED")[1])
    monkeypatch.setattr(monitor.emergency, "cancel_open_fund100_orders",
                        lambda: (calls.append("CANCEL"), cancel_return)[1])
    with pytest.raises(monitor.RiskMonitorStop, match="cancellation"):
        monitor.monitor_once()
    assert calls == ["STOP", "CANCEL"]


def test_both_stop_and_cancel_failure_report_unverified(monkeypatch):
    calls = []
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: (_ for _ in ()).throw(RuntimeError("synthetic control outage")),
    )
    def broken_stop():
        calls.append("STOP")
        raise RuntimeError("token outage")
    def broken_cancel():
        calls.append("CANCEL")
        raise RuntimeError("broker outage")
    monkeypatch.setattr(monitor.operator, "commit_stop_signal", broken_stop)
    monkeypatch.setattr(monitor.emergency, "cancel_open_fund100_orders",
                        broken_cancel)
    with pytest.raises(monitor.RiskMonitorStop, match="BOTH unverified"):
        monitor.monitor_once()
    assert calls == ["STOP", "CANCEL"]


def test_no_order_after_failclosed_unknown_state(monkeypatch):
    monkeypatch.setattr(
        monitor.operator, "read_current_control",
        lambda: {"schema": operator.CONTROL_SCHEMA, "trading_enabled": False},
    )
    monkeypatch.setattr(
        monitor.emergency, "cancel_open_fund100_orders",
        lambda: pytest.fail("Existing STOP-only probe must not write broker"),
    )
    assert monitor.monitor_once() == "ALREADY_STOPPED"


def test_risk_snapshot_never_imports_trade_bootstrap():
    """Risk observer must not depend on the bootstrap module's POST transport."""
    import inspect
    source = inspect.getsource(monitor)
    assert "import fund100_live_bootstrap_v1_0" not in source
    assert "broker.live_request" not in source
    assert "readonly.get_json(" in source
    assert "readonly.load_credentials()" in source


def test_protected_snapshot_exact_three_get_routes_and_account_binding(monkeypatch):
    """All HTTP is synthetic; a direct GET-only client is injected."""
    import hashlib

    account_value = account()
    account_value["id"] = "OFFLINE_ACCOUNT_ID"
    observations = {
        "/v2/account": account_value,
        "/v2/positions": positions(),
        "/v2/account/portfolio/history": history(),
    }
    calls = []

    def fake_get_json(*, path, key, secret, params=None):
        calls.append((path, params, key, secret))
        assert key == "SYNTHETIC_KEY"
        assert secret == "SYNTHETIC_SECRET"
        assert path in observations
        return observations[path]

    monkeypatch.setattr(monitor, "_policy", policy)
    monkeypatch.setattr(
        monitor.readonly, "load_credentials",
        lambda: ("SYNTHETIC_KEY", "SYNTHETIC_SECRET")
    )
    monkeypatch.setattr(monitor.readonly, "get_json", fake_get_json)

    result = monitor.live_read_only_snapshot()
    assert result[:4] == (
        observations["/v2/account"],
        observations["/v2/positions"],
        observations["/v2/account/portfolio/history"],
        policy(),
    )
    assert result[4] == hashlib.sha256(
        b"FUND100-LIVE-ACCOUNT|OFFLINE_ACCOUNT_ID"
    ).hexdigest()
    assert [(path, params) for path, params, _, _ in calls] == [
        ("/v2/account", None),
        ("/v2/positions", None),
        ("/v2/account/portfolio/history",
         {"period": "1M", "timeframe": "1D"}),
    ]


@pytest.mark.parametrize("invalid", [
    None, [], {}, {"id": None}, {"id": ""}, {"id": " "},
    {"id": 42}, {"id": ["synthetic"]},
])
def test_read_only_snapshot_rejects_unbound_account(invalid):
    with pytest.raises(monitor.RiskMonitorStop, match="account"):
        monitor._account_binding_from_read_only(invalid)


def test_protected_risk_http_uses_no_redirect_client():
    """Existing pinned live reader has a genuine credential-safe redirect stop."""
    from urllib.request import Request

    r = Request(
        "https://api.alpaca.markets/v2/account",
        method="GET",
        headers={
            "APCA-API-KEY-ID": "OFFLINE_KEY",
            "APCA-API-SECRET-KEY": "OFFLINE_SECRET",
        },
    )
    with pytest.raises(RuntimeError, match="redirect forbidden"):
        monitor.readonly._NoRedirect().redirect_request(
            r, None, 302, "Found", {}, "https://attacker.invalid/steal"
        )


def test_risk_watch_workflow_pins_exact_reviewed_sources_before_secret_step():
    """Source pins are checked before the GitHub job supplies broker secrets."""
    import hashlib
    from pathlib import Path

    workflow = Path(".github/workflows/fund100-live-risk-watch.yml").read_text()
    def git_blob_sha(path):
        data = Path(path).read_bytes()
        return hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\\0" + data
        ).hexdigest()

    for source in (
        "fund100_alpaca_live_readonly_smoke.py",
        "fund100_live_risk_monitor_v1_0.py",
    ):
        pin = (f'test "$(git hash-object {source})" = '
               f"'{git_blob_sha(source)}'")
        assert pin in workflow
        assert workflow.index(pin) < workflow.index(
            "- name: Check risk or trigger persistent STOP"
        )
    assert "persist-credentials: false" in workflow
    assert "environment: fund100-live-broker" in workflow

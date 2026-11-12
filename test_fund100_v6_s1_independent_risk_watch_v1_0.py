"""Credentialless V6 independent original ACWI risk watcher tests.

No external GitHub or Alpaca requests. STOP-only fake CAS and cancel actions.
"""
from datetime import datetime, timezone
import base64
import json
from pathlib import Path

import pytest

import fund100_v6_s1_independent_risk_watch_v1_0 as watch


STOPPED = {
    "schema": watch.v6.SCHEMA,
    "risk_level": "HIGH",
    "pilot_capital_ceiling_usd": "130.30",
    "trading_enabled": False,
    "first_original_acwi_sell_enabled": False,
}
RUNNING = dict(STOPPED, trading_enabled=True,
               first_original_acwi_sell_enabled=True)


@pytest.fixture(autouse=True)
def main_schedule(monkeypatch):
    # OFFLINE tests only: no scheduled job, credentials or production source release.
    monkeypatch.setattr(watch, "SCHEDULED_RUNTIME_RELEASED", True)
    for name, value in (
        ("GITHUB_ACTIONS", "true"),
        ("GITHUB_REPOSITORY", "nicobouch97/fund100-research"),
        ("GITHUB_REF", "refs/heads/main"),
        ("GITHUB_EVENT_NAME", "schedule"),
        ("GITHUB_WORKFLOW_REF", watch.WATCH_REF),
        ("GITHUB_RUN_ATTEMPT", "1"),
        ("GITHUB_SHA", "a" * 40),
        ("GITHUB_TOKEN", "mock-v6-public-github-token"),
        ("FUND100_RISK_LEVEL", "HIGH"),
        ("FUND100_ENABLE_LIVE_READONLY", "YES_READ_ONLY_LIVE"),
        ("FUND100_BROKER_KILL_SWITCH", "ENGAGED"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(watch.v6, "read_current_control",
                        lambda: dict(STOPPED))


def go(monkeypatch):
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "DISENGAGED")
    monkeypatch.setattr(watch.v6, "read_current_control",
                        lambda: dict(RUNNING))


def deny_side_effects(monkeypatch):
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: pytest.fail("Unwanted broker credentials"))
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: pytest.fail("Unwanted cancel"))
    monkeypatch.setattr(watch, "_stop_v6_first_only",
                        lambda: pytest.fail("Unwanted remote STOP"))


def test_original_v6_stop_is_success_without_broker_get_or_pass(monkeypatch, tmp_path):
    deny_side_effects(monkeypatch)
    output = tmp_path / "should-never-exist"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert watch.watch_once() == "ALREADY_STOPPED"
    assert not output.exists()
    assert watch.NO_TRADE_RELEASE is True
    assert watch.NO_BROKER_POST is True
    assert watch.NO_OPERATOR_GO_WRITE is True


@pytest.mark.parametrize("key,bad", [
    ("GITHUB_ACTIONS", "false"),
    ("GITHUB_REPOSITORY", "other/attacker"),
    ("GITHUB_REF", "refs/heads/test"),
    ("GITHUB_EVENT_NAME", "workflow_dispatch"),
    ("GITHUB_WORKFLOW_REF", "unrelated-scheduled-workflow"),
    ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_SHA", "malformed"),
    ("FUND100_RISK_LEVEL", "LOW"),
    ("FUND100_ENABLE_LIVE_READONLY", "NO"),
])
def test_wrong_workflow_or_risk_scope_blocks_before_operator_or_broker(
        monkeypatch, key, bad):
    monkeypatch.setenv(key, bad)
    monkeypatch.setattr(watch.v6, "read_current_control",
                        lambda: pytest.fail("Untrusted scope read operator"))
    with pytest.raises(watch.V6WatchStop, match="scope"):
        watch.watch_once()


def test_healthy_v6_running_emits_only_a_fixed_output(monkeypatch, tmp_path):
    go(monkeypatch)
    path = tmp_path / "safe-gh-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    monkeypatch.setattr(watch, "_risk_eight_get",
                        lambda: watch.EXPECTED_PASS)
    monkeypatch.setattr(watch, "_stop_v6_first_only",
                        lambda: pytest.fail("Healthy never writes STOP"))
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: pytest.fail("Healthy never cancels"))
    assert watch.watch_once() == watch.EXPECTED_PASS
    assert path.read_bytes() == (
        b"verified_v6_original_acwi_risk=YES" + bytes([10]))


def test_market_closed_is_hold_not_permanent_stop_or_pass(monkeypatch, tmp_path):
    go(monkeypatch)
    path = tmp_path / "safe-gh-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    monkeypatch.setattr(watch, "_risk_eight_get",
                        lambda: "MARKET_CLOSED_NO_PASS")
    monkeypatch.setattr(watch, "_stop_v6_first_only",
                        lambda: pytest.fail("Closed market should not set STOP"))
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: pytest.fail("Closed market should not cancel"))
    assert watch.watch_once() == "MARKET_CLOSED_NO_PASS"
    assert not path.exists()


def test_full_original_eight_get_source_reuses_actual_high_risk_validator(
        monkeypatch):
    go(monkeypatch)
    checked = []
    monkeypatch.setattr(watch, "_check_main_stopped_and_v6_go",
                        lambda: checked.append("operators"))
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: ("FAKE_KEY", "FAKE_SECRET"))
    sources = [{"type":"source", "is_open":True, "index":i}
               for i in range(8)]
    calls = []
    def fake_get(*, path, params, key, secret):
        assert key == "FAKE_KEY" and secret == "FAKE_SECRET"
        calls.append((path, params))
        return sources[len(calls)-1]
    monkeypatch.setattr(watch.broker, "get_json", fake_get)
    monkeypatch.setattr(watch.original, "original",
                        lambda filename: ({"original":str(filename)}, None))
    monkeypatch.setattr(watch.intent, "original_acwi_qty", lambda: "0.4")
    def fake_evaluate(**kw):
        assert kw["account"] is sources[0]
        assert kw["orders"] is sources[2]
        assert kw["native_none_history"] is sources[6]
        assert kw["extended_history"] is sources[7]
        assert kw["original_qty"] == "0.4"
        assert kw["observed_at_utc"].endswith("Z")
        return {
            "schema": watch.active.SCHEMA,
            "status": "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "same_process_real_broker_gets":8,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_post_attempts":0, "orders_submitted_here":0,
            "buy_authorized":False,
        }
    monkeypatch.setattr(watch.active, "evaluate_original_sell_only",
                        fake_evaluate)
    assert watch._risk_eight_get() == watch.EXPECTED_PASS
    assert len(calls) == 8
    assert [p for p,_ in calls[:7]] == list(watch.native.PATHS)
    assert calls[-1] == (watch.history.HISTORY_PATH,
                        {"period":"3M", "timeframe":"1D"})
    assert checked == ["operators", "operators", "operators"]


def test_true_closed_market_skips_last_four_gets_and_holds_without_pass(monkeypatch):
    go(monkeypatch)
    monkeypatch.setattr(watch, "_check_main_stopped_and_v6_go",
                        lambda: None)
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: ("FAKE_KEY", "FAKE_SECRET"))
    calls = []
    def fake_get(**kw):
        calls.append(kw["path"])
        return {"is_open":False} if len(calls) == 4 else {}
    monkeypatch.setattr(watch.broker, "get_json", fake_get)
    monkeypatch.setattr(watch.active, "evaluate_original_sell_only",
                        lambda **kw: pytest.fail("Closed market assessed as PASS"))
    assert watch._risk_eight_get() == "MARKET_CLOSED_NO_PASS"
    assert calls == ["/v2/account","/v2/positions","/v2/orders","/v2/clock"]


def test_v5_must_remain_historically_stopped_even_when_v6_is_go(monkeypatch):
    go(monkeypatch)
    monkeypatch.setattr(watch.v5, "read_current_control",
                        lambda: {"schema":watch.v5.CONTROL_SCHEMA,
                                 "trading_enabled":True})
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: pytest.fail("No GET when V5 GO"))
    with pytest.raises(watch.V6WatchStop, match="Historical V5"):
        watch._risk_eight_get()


def test_unavailable_initial_v6_operator_never_assumes_stopped_or_pass(
        monkeypatch, tmp_path):
    output = tmp_path / "not-a-risk-pass"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    actions = []
    def inaccessible():
        actions.append("V6_MAIN_CONTROL_GET_UNAVAILABLE")
        raise TimeoutError("synthetic GitHub read timeout")
    monkeypatch.setattr(watch.v6, "read_current_control", inaccessible)
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: pytest.fail("Eight risk GETs may not start"))
    monkeypatch.setattr(watch, "_stop_v6_first_only",
                        lambda: actions.append("STOP_ONLY_CAS") or "STOPPED")
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: actions.append("SIGNED_IDS_ONLY_CANCEL") or 0)
    assert watch.watch_once() == "AUTO_STOP_CONFIRMED"
    assert actions == [
        "V6_MAIN_CONTROL_GET_UNAVAILABLE", "STOP_ONLY_CAS",
        "SIGNED_IDS_ONLY_CANCEL",
    ]
    assert not output.exists()


def test_unavailable_initial_v6_operator_and_stop_ack_still_attempts_cancel(
        monkeypatch, tmp_path):
    output = tmp_path / "not-a-risk-pass"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    actions = []
    monkeypatch.setattr(watch.v6, "read_current_control",
        lambda: (_ for _ in ()).throw(TimeoutError("V6 unknown")))
    def stop_unknown():
        actions.append("STOP_CAS_UNKNOWN")
        raise TimeoutError("No acknowledgment")
    monkeypatch.setattr(watch, "_stop_v6_first_only", stop_unknown)
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: actions.append("SELECTIVE_CANCEL") or 0)
    with pytest.raises(watch.V6WatchStop, match="STOP unconfirmed"):
        watch.watch_once()
    assert actions == ["STOP_CAS_UNKNOWN", "SELECTIVE_CANCEL"]
    assert not output.exists()


def test_unverified_running_risk_stops_before_cancel_and_no_pass(monkeypatch,
                                                                 tmp_path):
    go(monkeypatch)
    output = tmp_path / "safe-gh-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    actions = []
    def failed():
        actions.append("broker_risk_HOLD")
        raise TimeoutError("synthetic broker outage")
    monkeypatch.setattr(watch, "_risk_eight_get", failed)
    monkeypatch.setattr(watch, "_stop_v6_first_only",
                        lambda: actions.append("PERSISTENT_STOP") or "STOPPED")
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: actions.append("SELECTIVE_CANCEL") or 0)
    assert watch.watch_once() == "AUTO_STOP_CONFIRMED"
    assert actions == ["broker_risk_HOLD","PERSISTENT_STOP","SELECTIVE_CANCEL"]
    assert not output.exists()


def test_stop_unknown_never_claims_success_but_attempts_independent_cancel(
        monkeypatch):
    go(monkeypatch)
    monkeypatch.setattr(watch, "_risk_eight_get",
                        lambda: (_ for _ in ()).throw(ValueError("data")))
    def unconfirmed():
        raise TimeoutError("unknown CAS ack")
    monkeypatch.setattr(watch, "_stop_v6_first_only", unconfirmed)
    attempted = []
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: attempted.append("CANCEL_ATTEMPTED") or 0)
    with pytest.raises(watch.V6WatchStop, match="STOP unconfirmed"):
        watch.watch_once()
    assert attempted == ["CANCEL_ATTEMPTED"]


def test_unknown_stop_and_failed_cancel_never_claim_success(monkeypatch):
    go(monkeypatch)
    monkeypatch.setattr(watch, "_risk_eight_get",
                        lambda: (_ for _ in ()).throw(ValueError("risk")))
    calls = []
    def uncertain_stop():
        calls.append("STOP_ATTEMPTED")
        raise TimeoutError("unknown stop ack")
    def uncertain_cancel():
        calls.append("CANCEL_ATTEMPTED")
        raise TimeoutError("unknown broker cancel")
    monkeypatch.setattr(watch, "_stop_v6_first_only", uncertain_stop)
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        uncertain_cancel)
    with pytest.raises(watch.V6WatchStop, match="STOP unconfirmed"):
        watch.watch_once()
    assert calls == ["STOP_ATTEMPTED", "CANCEL_ATTEMPTED"]


def test_cancel_error_not_claimed_as_auto_stop_success(monkeypatch):
    go(monkeypatch)
    monkeypatch.setattr(watch, "_risk_eight_get",
                        lambda: (_ for _ in ()).throw(ValueError("risk")))
    monkeypatch.setattr(watch, "_stop_v6_first_only", lambda: "STOPPED")
    monkeypatch.setattr(watch.cancel, "cancel_open_first_signed_acwi_orders",
                        lambda: (_ for _ in ()).throw(TimeoutError("cancel")))
    with pytest.raises(watch.V6WatchStop, match="cancel uncertain"):
        watch.watch_once()


def test_scheduled_watcher_cannot_bypass_manual_only_v6_put_authority(monkeypatch):
    # Future automated STOP must have a separately approved scoped
    # credential/path. For now the scheduled monitor cannot PUT to GitHub.
    go(monkeypatch)
    calls=[]
    monkeypatch.setattr(watch.v6, "_request",
        lambda **kwargs: calls.append(kwargs["method"]) or
            pytest.fail("Scheduled STOP must not reach GET or PUT"))
    with pytest.raises(watch.v6.V6OperatorStop, match="manual emergency workflow"):
        watch._stop_v6_first_only()
    assert calls == []


def test_scheduled_stop_denial_never_marks_risk_pass_or_auto_stop(monkeypatch,tmp_path):
    go(monkeypatch)
    output=tmp_path/"pass-never"
    monkeypatch.setenv("GITHUB_OUTPUT",str(output))
    monkeypatch.setattr(watch,"_risk_eight_get",
        lambda: (_ for _ in ()).throw(TimeoutError("synthetic risk outage")))
    attempts=[]
    monkeypatch.setattr(watch.cancel,"cancel_open_first_signed_acwi_orders",
        lambda: attempts.append("ATTEMPTED_SIGNED_CANCEL") or 0)
    # _stop_v6_first_only actually calls the protected manual scope, no mock.
    with pytest.raises(watch.V6WatchStop, match="STOP unconfirmed"):
        watch.watch_once()
    assert attempts==["ATTEMPTED_SIGNED_CANCEL"]
    assert not output.exists()


def test_source_dormant_lock_rejects_before_operator_or_broker(monkeypatch):
    monkeypatch.setattr(watch, "SCHEDULED_RUNTIME_RELEASED", False)
    monkeypatch.setattr(watch.v6, "read_current_control",
                        lambda: pytest.fail("Unreleased code read operator"))
    monkeypatch.setattr(watch.broker, "load_credentials",
                        lambda: pytest.fail("Unreleased code read broker"))
    with pytest.raises(watch.V6WatchStop, match="source remains unreleased"):
        watch.watch_once()


def test_source_only_has_no_order_post_and_cannot_resume_v5():
    s = Path(watch.__file__).read_text()
    assert "SCHEDULED_RUNTIME_RELEASED = False" in s
    assert "submit_order" not in s and 'method="POST"' not in s
    assert "first_original_acwi_sell_enabled=False" in s
    assert "NO_TRADE_RELEASE = True" in s
    assert "from fund100_live_operator_control" not in s
    # The installed schedule is a STOP-only heartbeat, not this broker-aware watcher.
    preflight = Path(".github/workflows/fund100-v6-s1-independent-risk-watch.yml")
    assert preflight.is_file()
    workflow = preflight.read_text(encoding="utf-8")
    assert "NO_BROKER_NO_RISK_PASS" in workflow
    assert "verified_v6_original_acwi_risk=YES" not in workflow
    assert "ALPACA_LIVE_SECRET" not in workflow

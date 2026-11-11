"""Offline emergency stop tests; never connect to Alpaca or GitHub."""

import base64
import json
from uuid import uuid4

import pytest

import fund100_live_emergency_stop_v1_0 as stop
import fund100_live_operator_control_v1_0 as operator
import fund100_live_production_controller_v1_0 as controller


def test_operator_state_stopped_default():
    assert operator.validate_control({
        "schema": operator.CONTROL_SCHEMA,
        "trading_enabled": False,
    }) is False


@pytest.mark.parametrize("invalid", [
    {}, None, [], {"schema": "unknown", "trading_enabled": True},
    {"schema": operator.CONTROL_SCHEMA, "trading_enabled": "false"},
    {"schema": operator.CONTROL_SCHEMA, "trading_enabled": 1},
])
def test_bad_operator_control_fails_closed(invalid):
    with pytest.raises(operator.OperatorControlStop):
        operator.validate_control(invalid)


def test_live_control_prevents_running_job_from_submitting(monkeypatch):
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "DISENGAGED")
    monkeypatch.setattr(
        controller.live,
        "get_order_by_client_id",
        lambda _cid: None,
    )
    monkeypatch.setattr(
        controller.live,
        "live_request",
        lambda **_kw: pytest.fail("Alpaca POST was attempted"),
    )
    def halted():
        raise operator.OperatorControlStop("STOP active")
    monkeypatch.setattr(controller.operator_control, "require_operator_running", halted)

    with pytest.raises(operator.OperatorControlStop):
        controller.submit_order_batch([{
            "client_order_id": "f100live-123456789abc-b-acwi",
            "side": "buy",
            "symbol": "ACWI",
            "notional_usd": "1.00",
        }])


def test_stop_latch_skips_compiler_and_broker(monkeypatch):
    monkeypatch.setattr(controller, "load_production_policy", lambda: {})
    monkeypatch.setattr(
        controller, "refresh_current_scheduled_compiler",
        lambda: pytest.fail("Compiler ran while operator stopped"),
    )
    monkeypatch.setattr(
        controller.operator_control, "require_operator_running",
        lambda: (_ for _ in ()).throw(operator.OperatorControlStop("STOP")),
    )
    captured = {}
    monkeypatch.setattr(
        controller, "write_status",
        lambda **kwargs: captured.update(kwargs),
    )
    controller.main()
    assert captured["status"] == "TRADING_STOPPED_BY_OPERATOR"
    assert captured["orders_submitted"] == 0


def test_stop_recognizes_only_fund100_generated_client_ids():
    for cid in [
        "f100live-123456789abc-b-acwi",
        "f100live-prod-1234567890abcdef-s-xle",
        "f100-live-bootstrap-1234567890abcdef-b-acwi",
    ]:
        assert stop.is_fund100_client_id(cid)
    for cid in [
        "f100-test-risk-guard",
        "f100live-123456789abc-b-../../evil",
        "f100live-notahash-b-acwi",
        "other-bot-123",
        None,
    ]:
        assert not stop.is_fund100_client_id(cid)


def test_stop_selects_just_bot_order_ids():
    a, b = str(uuid4()), str(uuid4())
    selected = stop.select_fund100_open_orders([
        {"id": a, "client_order_id": "f100live-123456789abc-b-acwi"},
        {"id": b, "client_order_id": "manual-test-123"},
    ])
    assert selected == [a]


def test_stop_rejects_truncated_order_page():
    with pytest.raises(stop.EmergencyStopError):
        stop.select_fund100_open_orders([{}] * 500)


def test_stop_cancels_only_our_orders_and_reconciles(monkeypatch):
    ours = str(uuid4())
    calls = []
    listings = iter([
        [{"id": ours, "client_order_id": "f100live-123456789abc-s-xle"}],
        [{"id": ours, "client_order_id": "f100live-123456789abc-s-xle"}],
        [],
    ])
    def fake_request(method, path):
        calls.append((method, path))
        if method == "GET":
            return next(listings)
        return None
    monkeypatch.setattr(stop, "_alpaca_request", fake_request)
    monkeypatch.setattr(stop.time, "sleep", lambda _n: None)
    assert stop.cancel_open_fund100_orders() == 1
    assert calls.count(("DELETE", "/v2/orders/" + ours)) == 1


def test_stop_does_not_touch_manual_orders(monkeypatch):
    manual = str(uuid4())
    calls = []
    def fake_request(method, path):
        calls.append((method, path))
        return [{"id": manual, "client_order_id": "manual-order-123"}]
    monkeypatch.setattr(stop, "_alpaca_request", fake_request)
    assert stop.cancel_open_fund100_orders() == 0
    assert all(method == "GET" for method, _path in calls)


def test_stop_refuses_success_if_orders_remain(monkeypatch):
    ours = str(uuid4())
    monkeypatch.setattr(
        stop, "_alpaca_request",
        lambda method, path: (
            [{"id": ours, "client_order_id": "f100live-123456789abc-s-xle"}]
            if method == "GET" else None
        ),
    )
    monkeypatch.setattr(stop.time, "sleep", lambda _n: None)
    with pytest.raises(stop.EmergencyStopError):
        stop.cancel_open_fund100_orders()

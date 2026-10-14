"""PAPER ETF fill probe unit tests: no live or paper network calls."""

from datetime import datetime, timezone
from decimal import Decimal
import os

import pytest

import fund100_v5_connected_paper_fill_probe_v1_0 as probe


def test_frozen_v5_targets_define_probe_universe():
    symbols, weights = probe.frozen_v5_selection()
    assert symbols == ["ACWI", "EEM", "XLE", "XLV"]
    assert Decimal(weights["ACWI"]) > Decimal("0.7")


def test_only_regular_us_mid_session_window_eligible():
    assert probe.allowed_session(
        {"is_open": True}, datetime(2026, 10, 14, 15, 15, tzinfo=timezone.utc)
    )
    assert not probe.allowed_session(
        {"is_open": False}, datetime(2026, 10, 14, 15, 15, tzinfo=timezone.utc)
    )
    assert not probe.allowed_session(
        {"is_open": True}, datetime(2026, 10, 14, 12, 15, tzinfo=timezone.utc)
    )


def test_asset_selection_never_interferes_with_existing_positions_orders():
    assert probe.select_empty_approved_asset(
        owned_positions=[{"symbol": "ACWI", "qty": "1"}],
        open_orders=[], approved_symbols=["ACWI", "EEM"],
    ) == "EEM"
    with pytest.raises(probe.PaperFillStop, match="open orders"):
        probe.select_empty_approved_asset(
            owned_positions=[], open_orders=[{"id": "unrelated"}],
            approved_symbols=["ACWI", "EEM"],
        )
    with pytest.raises(probe.PaperFillStop, match="already have"):
        probe.select_empty_approved_asset(
            owned_positions=[{"symbol": "ACWI"}, {"symbol": "EEM"}],
            open_orders=[], approved_symbols=["ACWI", "EEM"],
        )


@pytest.mark.parametrize("env", [
    {}, {"FUND100_PAPER_FILL_ARM": "PAPER_ONLY_2USD"},
])
def test_missing_or_wrong_execution_environment_blocks(monkeypatch, env):
    for key in (
        "FUND100_PAPER_FILL_ARM", "FUND100_BROKER_KILL_SWITCH",
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "GITHUB_REPOSITORY"
    ):
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(probe.PaperFillStop):
        probe.validate_arm()


def test_client_id_deterministic_and_side_separated(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "123456789")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    a = probe.client_id("b")
    assert a == probe.client_id("b")
    assert a != probe.client_id("s")
    assert len(a) < 128


def test_filled_paper_buy_and_exact_sell_reconciles(monkeypatch):
    monkeypatch.setattr(probe, "validate_arm", lambda: None)
    monkeypatch.setattr(probe, "allowed_session", lambda *args: True)
    monkeypatch.setenv("GITHUB_RUN_ID", "987654")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    state = {"position": Decimal("0"), "calls": [], "orders": {}}
    monkeypatch.setattr(probe.paper, "get_clock", lambda: {"is_open": True})
    monkeypatch.setattr(probe.paper, "get_account", lambda: {
        "status": "ACTIVE", "trading_blocked": False, "cash": "1000"
    })
    monkeypatch.setattr(probe.paper, "get_asset", lambda symbol: {
        "symbol": symbol, "tradable": True, "fractionable": True
    })
    monkeypatch.setattr(probe.paper, "get_open_orders", lambda: [])
    monkeypatch.setattr(
        probe.paper, "get_positions",
        lambda: ([] if state["position"] == 0 else [
            {"symbol": "ACWI", "qty": str(state["position"])}
        ]),
    )
    monkeypatch.setattr(
        probe.paper, "get_order_by_client_id", lambda cid: None
    )
    monkeypatch.setattr(
        probe.paper, "get_order_by_id", lambda oid: state["orders"][oid]
    )

    def fake_request(*, method, path, body):
        assert method == "POST" and path == "/v2/orders"
        state["calls"].append(dict(body))
        if body["side"] == "buy":
            assert body["symbol"] == "ACWI"
            assert body["notional"] == "2.00"
            state["position"] += Decimal("0.012345678")
            fill_qty = Decimal("0.012345678")
        else:
            assert body["symbol"] == "ACWI"
            assert body["qty"] == "0.012345678"
            fill_qty = state["position"]
            state["position"] = Decimal("0")
        oid = "order-" + body["side"]
        order = {
            "id": oid, "client_order_id": body["client_order_id"],
            "status": "filled", "filled_qty": str(fill_qty),
        }
        state["orders"][oid] = order
        return order

    monkeypatch.setattr(probe.paper, "paper_request", fake_request)
    output = probe.run_probe()
    assert output["status"] == "PASS"
    assert output["position_flat_after_exit"] is True
    assert output["live_orders_submitted"] == 0
    assert len(state["calls"]) == 2
    assert state["position"] == 0
    assert state["calls"][0]["side"] == "buy"
    assert state["calls"][1]["side"] == "sell"


def test_duplicate_paper_order_id_prevents_post(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "987654")
    monkeypatch.setattr(
        probe.paper, "get_order_by_client_id",
        lambda cid: {"id": "existing"},
    )
    monkeypatch.setattr(
        probe.paper, "paper_request",
        lambda **kwargs: pytest.fail("Duplicate POST"),
    )
    with pytest.raises(probe.PaperFillStop, match="already exists"):
        probe.submit_unique(symbol="ACWI", side="buy", notional=Decimal("2"))


def test_sell_failure_does_not_claim_paper_flat(monkeypatch):
    monkeypatch.setattr(probe, "validate_arm", lambda: None)
    monkeypatch.setattr(probe, "allowed_session", lambda *args: True)
    monkeypatch.setenv("GITHUB_RUN_ID", "987655")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    state = {"position": Decimal("0"), "orders": {}}
    monkeypatch.setattr(probe.paper, "get_clock", lambda: {"is_open": True})
    monkeypatch.setattr(probe.paper, "get_account", lambda: {
        "status": "ACTIVE", "trading_blocked": False, "cash": "1000"
    })
    monkeypatch.setattr(probe.paper, "get_asset", lambda symbol: {
        "symbol": symbol, "tradable": True, "fractionable": True
    })
    monkeypatch.setattr(probe.paper, "get_open_orders", lambda: [])
    monkeypatch.setattr(
        probe.paper, "get_positions",
        lambda: ([] if state["position"] == 0 else [
            {"symbol": "ACWI", "qty": str(state["position"])}
        ]),
    )
    monkeypatch.setattr(probe.paper, "get_order_by_client_id", lambda _: None)
    monkeypatch.setattr(
        probe.paper, "get_order_by_id", lambda oid: state["orders"][oid]
    )

    def post(*, method, path, body):
        if body["side"] == "sell":
            raise probe.PaperFillStop("synthetic paper sell rejected")
        state["position"] = Decimal("0.012")
        result = {
            "id": "buy-owned", "client_order_id": body["client_order_id"],
            "status": "filled", "filled_qty": ".012",
        }
        state["orders"]["buy-owned"] = result
        return result
    monkeypatch.setattr(probe.paper, "paper_request", post)
    with pytest.raises(probe.PaperFillStop, match="sell rejected"):
        probe.run_probe()
    assert state["position"] > 0

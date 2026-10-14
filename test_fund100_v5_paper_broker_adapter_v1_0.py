"""Offline Alpaca PAPER adapter tests: never contact a real API."""
from decimal import Decimal

import pytest

import fund100_v5_paper_broker_adapter_v1_0 as a
import fund100_live_operator_control_v1_0 as operator


def configured(monkeypatch):
    for key in ("ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET"):
        monkeypatch.delenv(key, raising=False)
    for key, val in {
        "FUND100_GENUINE_PAPER_ARM": "YES_ATTESTED_V5_PAPER_ONLY",
        "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
        "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
        "ALPACA_PAPER_KEY": "test-paper-key",
        "ALPACA_PAPER_SECRET": "test-paper-secret",
    }.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(a.operator, "read_current_control", lambda: {
        "schema": operator.CONTROL_SCHEMA, "trading_enabled": False,
    })
    return a.AlpacaPaperOnlyAdapter(approved_symbols={"ACWI", "EEM"})


def test_default_disarmed_and_absent_credentials_blocks(monkeypatch):
    for key in (
        "FUND100_GENUINE_PAPER_ARM", "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET", "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    broker = a.AlpacaPaperOnlyAdapter(approved_symbols={"ACWI"})
    with pytest.raises(a.PaperAdapterStop):
        broker.require_paper_only_arm()


def test_remote_operator_running_blocks_paper_writer(monkeypatch):
    broker = configured(monkeypatch)
    monkeypatch.setattr(a.operator, "read_current_control", lambda: {
        "schema": operator.CONTROL_SCHEMA, "trading_enabled": True,
    })
    with pytest.raises(a.PaperAdapterStop, match="operator"):
        broker.require_paper_only_arm()


def test_live_credentials_forbidden_in_paper_runner(monkeypatch):
    broker = configured(monkeypatch)
    monkeypatch.setenv("ALPACA_LIVE_KEY", "unexpected-live-key")
    with pytest.raises(a.PaperAdapterStop, match="LIVE credentials"):
        broker.require_paper_only_arm()


def test_explicit_paper_only_credentials_and_arm_allow_synthetic_boundary(monkeypatch):
    broker = configured(monkeypatch)
    broker.require_paper_only_arm()


def test_paper_broker_reads_have_no_post_or_delete(monkeypatch):
    broker = configured(monkeypatch)
    reads = []
    monkeypatch.setattr(a.paper, "get_account", lambda: {
        "status": "ACTIVE", "trading_blocked": False, "equity": "100",
        "cash": "20", "last_equity": "100",
    })
    monkeypatch.setattr(a.paper, "get_positions", lambda: [
        {"symbol": "ACWI", "qty": "1", "market_value": "80"},
    ])
    monkeypatch.setattr(a.paper, "get_open_orders", lambda: [])
    monkeypatch.setattr(a.paper, "get_clock", lambda: {"is_open": True})
    def fake_request(*, method, path):
        reads.append((method, path))
        assert method == "GET"
        return {"timeframe": "1D", "timestamp": [], "equity": []}
    monkeypatch.setattr(a.paper, "paper_request", fake_request)
    assert broker.snapshot()["positions"]["ACWI"]["market_value"] == "80"
    assert broker.market_open() is True
    assert broker.history()["timeframe"] == "1D"
    assert reads == [(
        "GET", "/v2/account/portfolio/history?period=1M&timeframe=1D"
    )]


@pytest.mark.parametrize("positions,orders", [
    ([{"symbol": "BTCUSD", "qty": "1", "market_value": "10"}], []),
    ([{"symbol": "ACWI", "qty": "1", "market_value": "10"}] * 2, []),
    ([], [{"id": str(i)} for i in range(500)]),
])
def test_foreign_or_ambiguous_paper_snapshot_refused(monkeypatch, positions, orders):
    broker = configured(monkeypatch)
    monkeypatch.setattr(a.paper, "get_account", lambda: {"status": "ACTIVE"})
    monkeypatch.setattr(a.paper, "get_positions", lambda: positions)
    monkeypatch.setattr(a.paper, "get_open_orders", lambda: orders)
    with pytest.raises(a.PaperAdapterStop):
        broker.snapshot()


def test_only_paper_post_with_approved_order_parameters(monkeypatch):
    broker = configured(monkeypatch)
    seen = []
    monkeypatch.setattr(a.paper, "get_order_by_client_id", lambda cid: None)
    def post_only(*, method, path, body):
        seen.append((method, path, dict(body)))
        return {
            **body, "status": "filled", "filled_qty": "0.01",
            "filled_avg_price": "100.00", "id": "paper-test",
        }
    monkeypatch.setattr(a.paper, "paper_request", post_only)
    response = broker.post_notional({
        "client_order_id": "f100paper-abc-b-acwi",
        "symbol": "ACWI", "side": "buy", "notional_usd": "2.00",
    })
    assert response["symbol"] == "ACWI"
    assert len(seen) == 1
    assert seen[0][0:2] == ("POST", "/v2/orders")
    assert seen[0][2]["extended_hours"] is False
    assert seen[0][2]["notional"] == "2.00"


@pytest.mark.parametrize("order", [
    {"symbol": "BTCUSD", "side": "buy", "notional_usd": "2",
     "client_order_id": "f100paper-aaa-b-btc"},
    {"symbol": "ACWI", "side": "sell", "notional_usd": "140",
     "client_order_id": "f100paper-aaa-s-acwi"},
    {"symbol": "ACWI", "side": "buy", "notional_usd": "NaN",
     "client_order_id": "f100paper-aaa-b-acwi"},
    {"symbol": "ACWI", "side": "buy", "notional_usd": "2",
     "client_order_id": "f100live-aaa-b-acwi"},
])
def test_adapter_rejects_unapproved_paper_order(monkeypatch, order):
    broker = configured(monkeypatch)
    monkeypatch.setattr(
        a.paper, "paper_request",
        lambda **kw: pytest.fail("Invalid PAPER intent sent to network"),
    )
    with pytest.raises((a.PaperAdapterStop, a.risk.PortfolioRiskStop)):
        broker.post_notional(order)


def test_adapter_cannot_whitelist_unreviewed_asset_class():
    with pytest.raises(a.PaperAdapterStop, match="non-V5"):
        a.AlpacaPaperOnlyAdapter(approved_symbols={"ACWI", "BTCUSD"})

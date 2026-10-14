"""Offline execution bridge acceptance: true compiler provenance + broker fills.

All broker calls are to an injected in-memory PAPER adapter; none can
reach Alpaca's LIVE or PAPER REST APIs.
"""
from decimal import Decimal

import pytest

import fund100_v5_paper_execution_bridge_v1_0 as bridge
from test_fund100_v5_compiler_attestation_v1_0 import scenario
from test_fund100_v5_genuine_paper_parity_v1_0 import (
    UNIVERSE, paper_history,
)


class FakePaper:
    def __init__(self):
        self.equity = Decimal("100")
        self.cash = Decimal("0")
        self.positions = {
            "ACWI": Decimal("75"),
            "EEM": Decimal("10"),
            "XLE": Decimal("10"),
            "XLV": Decimal("5"),
        }
        self.orders = {}
        self.posts = []
        self.armed = True
        self.open = True
        self.history_calls = 0

    def require_paper_only_arm(self):
        if not self.armed:
            raise bridge.PaperBridgeStop("PAPER-only arm missing")

    def market_open(self):
        return self.open

    def history(self):
        self.history_calls += 1
        return paper_history()

    def snapshot(self):
        return {
            "account": {
                "status": "ACTIVE", "trading_blocked": False,
                "equity": str(self.equity), "last_equity": str(self.equity),
                "cash": str(self.cash),
            },
            "positions": {
                sym: {"market_value": str(val), "qty": "1"}
                for sym, val in self.positions.items() if val > 0
            },
            "open_orders": [],
        }

    def lookup(self, cid):
        return self.orders.get(cid)

    def post_notional(self, order):
        cid = order["client_order_id"]
        if cid in self.orders:
            raise AssertionError("duplicate PAPER POST")
        amount = Decimal(order["notional_usd"])
        sym = order["symbol"]
        if order["side"] == "sell":
            if self.positions.get(sym, 0) < amount:
                raise AssertionError("PAPER short sell")
            self.positions[sym] -= amount
            self.cash += amount
        elif order["side"] == "buy":
            if self.cash < amount:
                raise AssertionError("PAPER buy exceeded settled cash")
            self.positions[sym] = self.positions.get(sym, 0) + amount
            self.cash -= amount
        else:
            raise AssertionError("unknown PAPER side")
        result = {
            "status": "filled", "side": order["side"], "symbol": sym,
            "client_order_id": cid, "notional": str(amount),
        }
        self.orders[cid] = result
        self.posts.append(result)
        return result

    def wait_terminal(self, cid):
        return self.orders[cid]


def execute(broker, **changes):
    pkg, manifest, state, now = scenario()
    params = {
        "compiler_package": pkg, "manifest_package": manifest,
        "shadow_state": state, "compiler_written_ns": now,
        "now_ns": now, "broker": broker,
        "execution_universe": UNIVERSE, "capital_ceiling": "130.30",
        "risk_level": "HIGH",
    }
    params.update(changes)
    return bridge.execute_attested_paper_event(**params)


def test_real_compiler_broker_injected_sell_then_buy_and_reconciliation():
    broker = FakePaper()
    report = execute(broker)
    assert report["status"] == "PAPER_EVENT_FILLED_AND_RECONCILED"
    assert report["paper_post_count"] == 3
    assert report["live_post_count"] == 0
    assert report["reconciled"] is True
    assert [(x["side"], x["symbol"], x["notional"]) for x in broker.posts] == [
        ("sell", "EEM", "2.00"),
        ("sell", "XLE", "1.00"),
        ("buy", "XLV", "3.00"),
    ]
    assert broker.positions == {
        "ACWI": Decimal("75"), "EEM": Decimal("8"),
        "XLE": Decimal("9"), "XLV": Decimal("8"),
    }
    assert broker.cash == 0


def test_no_genuine_compiler_event_cannot_contact_broker():
    broker = FakePaper()
    def bad():
        raise AssertionError("No genuine event consulted PAPER broker")
    broker.snapshot = bad
    broker.market_open = bad
    pkg, manifest, state, now = scenario()
    pkg["compiler"]["status"] = "NO_SCHEDULED_EVENT"
    pkg["compiler"]["genuine_scheduled_event"] = False
    pkg["compiler"]["candidate_intents"] = []
    pkg["compiler_sha256"] = bridge.production.canonical_sha256(pkg["compiler"])
    result = execute(
        broker, compiler_package=pkg, manifest_package=manifest,
        shadow_state=state, compiler_written_ns=now, now_ns=now,
    )
    assert result["status"] == "NO_GENUINE_EVENT"
    assert result["paper_post_count"] == 0


def test_stale_compiler_signal_blocks_all_paper_orders():
    broker = FakePaper()
    pkg, manifest, state, now = scenario()
    with pytest.raises(RuntimeError):
        execute(
            broker, compiler_package=pkg, manifest_package=manifest,
            shadow_state=state, compiler_written_ns=now-1000*10**9,
            now_ns=now,
        )
    assert broker.posts == []


def test_closed_market_blocks_before_any_account_order():
    broker = FakePaper()
    broker.open = False
    with pytest.raises(bridge.PaperBridgeStop, match="closed"):
        execute(broker)
    assert broker.posts == []


def test_paper_arm_missing_blocks_entire_event():
    broker = FakePaper()
    broker.armed = False
    with pytest.raises(bridge.PaperBridgeStop, match="arm"):
        execute(broker)
    assert broker.posts == []


def test_sell_fills_but_buy_rejected_when_fresh_cash_insufficient():
    broker = FakePaper()
    source = broker.snapshot
    count = {"n": 0}
    def evil_cash():
        result = source()
        count["n"] += 1
        if count["n"] >= 4:
            # PAPER broker cash unexpectedly moved away after SELL fills
            result["account"]["cash"] = "0"
        return result
    broker.snapshot = evil_cash
    with pytest.raises((bridge.PaperBridgeStop, bridge.production.ProductionStop)):
        execute(broker)
    assert [o["side"] for o in broker.posts] == ["sell", "sell"]
    assert broker.positions["XLV"] == Decimal("5")


def test_replay_cannot_duplicate_already_filled_paper_orders():
    broker = FakePaper()
    assert execute(broker)["paper_post_count"] == 3
    result = execute(broker)
    assert result["paper_post_count"] == 0
    assert result["status"] == "NO_PAPER_REBALANCE_NEEDED"
    assert len(broker.posts) == 3


def test_any_foreign_open_order_aborts_execution():
    broker = FakePaper()
    orig = broker.snapshot
    def dangerous():
        data = orig()
        data["open_orders"] = [{"client_order_id": "not-ours"}]
        return data
    broker.snapshot = dangerous
    with pytest.raises(bridge.PaperParityStop):
        execute(broker)
    assert broker.posts == []


def test_invalid_existing_order_identity_rejected_before_duplicate():
    broker = FakePaper()
    initial = execute(broker)
    # Rewind just the desired satellite while preserving one prior
    # broker client ID with a corrupted symbol.
    broker.positions["EEM"] = Decimal("10")
    broker.positions["XLE"] = Decimal("10")
    broker.positions["XLV"] = Decimal("5")
    broker.cash = Decimal("0")
    cid = next(k for k,v in broker.orders.items() if v["symbol"] == "EEM")
    broker.orders[cid]["symbol"] = "SPY"
    with pytest.raises(bridge.PaperBridgeStop, match="symbol"):
        execute(broker)
    assert len(broker.posts) == 3

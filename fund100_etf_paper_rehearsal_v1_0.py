"""ETF sell-then-buy PAPER REHEARSAL using REAL production logic.

Offline in-memory broker: no Alpaca, exchange, or GitHub network access.
Runs the V5 compiler adapter -> risk sizing -> portfolio guard ->
production order materializer -> two-phase orchestrator -> idempotent
ledger and final positions. Amounts are entirely synthetic.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from time import time
from unittest.mock import patch

import fund100_live_production_controller_v1_0 as production


SYNTHETIC_STRATEGY = {
    "ACWI": "0.75",
    "EEM": "0.10",
    "XLE": "0.10",
    "XLV": "0.05",
}
SIGNAL_ORDERS = [
    {"symbol": "EEM", "side": "sell",
     "client_order_id": "f100live-fedcba987654-s-eem"},
    {"symbol": "XLV", "side": "buy",
     "client_order_id": "f100live-fedcba987654-b-xlv"},
]


def synthetic_compiler(*, candidates=None) -> dict:
    return {
        "schema": production.EXPECTED_COMPILER_SCHEMA,
        "strategy": "V5-002_SHADOW",
        "compiler_mode": "current",
        "status": "GENUINE_SCHEDULED_EVENT",
        "genuine_scheduled_event": True,
        "event_id": "offline-etf-rebalance-001",
        # Match the LOCKED compiler v1.1 output, which contains
        # only satellite weights, not final_target_weights.
        "executed_satellite_weights": {
            symbol: SYNTHETIC_STRATEGY.get(symbol, "0")
            for symbol in (
                "SPY", "IWM", "EFA", "EEM", "VNQ", "XLK", "XLF",
                "XLI", "XLV", "XLP", "XLY", "XLE", "XLU",
            )
        },
        "candidate_intents": list(
            SIGNAL_ORDERS if candidates is None else candidates
        ),
    }


class PaperBroker:
    """Deterministic notional-value ledger; instant synthetic full fills."""

    def __init__(self) -> None:
        self.positions = {
            "ACWI": Decimal("75.00"),
            "EEM": Decimal("15.00"),
            "XLE": Decimal("10.00"),
        }
        self.cash = Decimal("0.00")
        self.filled: dict[str, dict] = {}
        self.actions: list[dict] = []
        self.running = True
        self.network_calls = 0

    @property
    def equity(self) -> Decimal:
        return self.cash + sum(self.positions.values(), Decimal("0"))

    def snapshot(self) -> dict:
        return {
            "account": {
                "status": "ACTIVE",
                "equity": str(self.equity),
                "last_equity": str(self.equity),
            },
            "positions": {
                s: {"market_value": v, "qty": Decimal("1")}
                for s, v in self.positions.items()
                if v > 0
            },
            "open_orders": [],
            "equity": self.equity,
            "cash": self.cash,
        }

    def history(self) -> dict:
        values = [99.8, 99.9, 100, 99.9, 100, 100]
        return {
            "timeframe": "1D",
            "timestamp": [
                int(time()) - (len(values) - i) * 86400
                for i in range(len(values))
            ],
            "equity": values,
        }

    def live_request(self, *, method, path, **kwargs):
        if (
            method == "GET"
            and path == "/v2/account/portfolio/history?period=1M&timeframe=1D"
        ):
            return self.history()
        self.network_calls += 1
        raise AssertionError("PAPER REHEARSAL attempted an unmocked broker request")

    def check_running(self):
        if not self.running:
            raise production.operator_control.OperatorControlStop(
                "Synthetic operator STOP"
            )

    def authorized_history(self, allowed_client_ids):
        return {
            client_id: self.filled.get(client_id)
            for client_id in allowed_client_ids
        }

    def submit(self, orders: list[dict]) -> dict:
        """Simulate production writer, but never call live HTTP transport."""
        actions = []
        for order in orders:
            self.check_running()
            cid = order["client_order_id"]
            if cid in self.filled:
                actions.append({"client_order_id": cid, "action": "RECOVERED"})
                continue
            amount = Decimal(str(order["notional_usd"]))
            symbol = order["symbol"]
            if amount <= 0:
                raise AssertionError("Non-positive synthetic order")
            current = self.positions.get(symbol, Decimal("0"))
            if order["side"] == "sell":
                if current < amount:
                    raise AssertionError("Synthetic short sell")
                self.positions[symbol] = current - amount
                self.cash += amount
            elif order["side"] == "buy":
                if self.cash < amount:
                    raise AssertionError("Synthetic insufficient actual cash")
                self.positions[symbol] = current + amount
                self.cash -= amount
            else:
                raise AssertionError("Invalid synthetic side")
            self.filled[cid] = {
                "status": "filled",
                "notional": str(amount),
                "client_order_id": cid,
            }
            action = {
                "client_order_id": cid, "side": order["side"],
                "symbol": symbol, "notional_usd": str(amount),
            }
            actions.append(action)
            self.actions.append(action)
        return {"results": actions}


def rehearse(*, stop_after_sell: bool = False, level: str = "HIGH",
             candidates=None) -> dict:
    """Run full dry-run execution through production dependency bindings."""
    broker = PaperBroker()
    body = synthetic_compiler(candidates=candidates)
    event = production.extract_compiler_view(
        body, compiler_sha256=production.canonical_sha256(body)
    )
    weights = production.extract_target_weights(body)
    policy = {
        "capital_ceiling": Decimal("130.30"),
        "risk_budget": production.risk_controls.resolve_risk_budget(
            level=level, pilot_capital_ceiling=Decimal("130.30")
        ),
        "universe": {"ACWI", "EEM", "XLE", "XLV"},
        "account_binding": "synthetic-paper-only",
    }
    with (
        patch.dict(os.environ, {"FUND100_RISK_LEVEL": level}),
        patch.object(production.live, "live_request", broker.live_request),
        patch.object(production, "fresh_snapshot",
                     side_effect=lambda **kwargs: broker.snapshot()),
        patch.object(production, "reconstruct_authorized_history",
                     side_effect=broker.authorized_history),
        patch.object(production, "submit_order_batch",
                     side_effect=broker.submit),
        patch.object(production.operator_control, "require_operator_running",
                     side_effect=broker.check_running),
    ):
        snapshot = broker.snapshot()
        adjusted = production.risk_size_authorized_event(
            snapshot=snapshot, target_weights=weights,
            candidates=event["candidates"], policy_context=policy,
        )
        sell_preview = production.materialize_orders(
            snapshot=snapshot, target_weights=adjusted,
            candidates=event["candidates"], phase="SELL",
            capital_ceiling=policy["capital_ceiling"],
        )
        credit = sum(
            (Decimal(o["notional_usd"]) for o in sell_preview),
            Decimal("0"),
        )
        buy_preview_snapshot = dict(snapshot)
        buy_preview_snapshot["cash"] = snapshot["cash"] + credit
        buy_preview = production.materialize_orders(
            snapshot=buy_preview_snapshot, target_weights=adjusted,
            candidates=event["candidates"], phase="BUY",
            capital_ceiling=policy["capital_ceiling"],
        )
        initial_orders = sell_preview + buy_preview
        production.risk_controls.enforce_event_budget(
            orders=initial_orders, risk_budget=policy["risk_budget"],
        )
        if sum((
            Decimal(o["notional_usd"]) for o in initial_orders
        ), Decimal("0")) > policy["capital_ceiling"]:
            raise production.ProductionStop("Synthetic event exceeds pilot ceiling")

        deps, phases, allowed = production.build_dependencies(
            policy_context=policy,
            target_weights=adjusted,
            candidates=event["candidates"],
        )
        traces = []
        for phase in ("SELL", "BUY"):
            if phase == "BUY" and stop_after_sell:
                broker.running = False
            result = production.orchestrator.run_execution_phase(
                release_lock_package={"release_lock_version": "1.9"},
                compiler_package={"schema": "PAPER_REHEARSAL"},
                permit_package={"capital_ceiling_usd": "130.30"},
                phase=phase,
                now=datetime.now(timezone.utc),
                deps=deps,
            )
            traces.append({"phase": phase, "trace": result["trace"]})

        # Re-run BOTH phases: every client ID is already filled, so
        # no further broker order is permitted/necessary.
        prior = len(broker.actions)
        for phase in ("SELL", "BUY"):
            production.orchestrator.run_execution_phase(
                release_lock_package={"release_lock_version": "1.9"},
                compiler_package={"schema": "PAPER_REHEARSAL"},
                permit_package={"capital_ceiling_usd": "130.30"},
                phase=phase,
                now=datetime.now(timezone.utc),
                deps=deps,
            )
        if len(broker.actions) != prior:
            raise AssertionError("Replay duplicated a synthetic fill")

    return {
        "mode": "OFFLINE_SYNTHETIC_PAPER",
        "strategy": "V5-002_SHADOW",
        "risk_level": level,
        "status": "SUCCESS",
        "synthetic_starting_equity_usd": "100.00",
        "synthetic_ending_equity_usd": str(broker.equity),
        "simulated_orders": broker.actions,
        "order_count": len(broker.actions),
        "replay_duplicate_orders": 0,
        "unmocked_broker_requests": broker.network_calls,
        "operator_control": "MOCKED",
        "phases": traces,
    }


if __name__ == "__main__":
    print(json.dumps(rehearse(), indent=2, sort_keys=True))

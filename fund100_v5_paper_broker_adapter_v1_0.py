"""Strict Alpaca PAPER broker adapter for the V5 attested execution bridge.

This is a reusable adapter, NOT a scheduled runner. The runtime arm is
absent by default. Every paper submission verifies environment, remote
operator STOP and fixed Alpaca paper host. No LIVE URL or key is used.
Broker equity, holdings and account identifiers stay in memory.

An adapter user must pass the compiler package to execute_attested_paper_event;
that function independently attests source freshness, risk and directions.
"""

from __future__ import annotations

import os
import time
from decimal import Decimal
from urllib.parse import quote

import fund100_alpaca_paper_orchestrator_connected_v1_0 as paper
import fund100_live_operator_control_v1_0 as operator
import fund100_live_portfolio_risk_v1_0 as risk


class PaperAdapterStop(RuntimeError):
    """A broker state or PAPER-only credential boundary failed."""


class AlpacaPaperOnlyAdapter:
    PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
    ARM_VALUE = "YES_ATTESTED_V5_PAPER_ONLY"

    def __init__(self, *, approved_symbols: set[str]):
        if not isinstance(approved_symbols, set) or not approved_symbols:
            raise PaperAdapterStop("Approved PAPER ETF universe required.")
        if any(not isinstance(s, str) or not s.isupper()
               for s in approved_symbols):
            raise PaperAdapterStop("Invalid approved PAPER ETF.")
        self.approved_symbols = frozenset(approved_symbols)

    def require_paper_only_arm(self):
        if paper.PAPER_BASE_URL != self.PAPER_ENDPOINT:
            raise PaperAdapterStop("PAPER host binding unexpected.")
        if os.environ.get("FUND100_GENUINE_PAPER_ARM") != self.ARM_VALUE:
            raise PaperAdapterStop("Genuine strategy PAPER test not armed.")
        if os.environ.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED":
            raise PaperAdapterStop("LIVE broker kill switch must remain ENGAGED.")
        if os.environ.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research":
            raise PaperAdapterStop("Repository identity mismatch.")
        if os.environ.get("ALPACA_LIVE_KEY") or os.environ.get(
            "ALPACA_LIVE_SECRET"
        ):
            raise PaperAdapterStop("LIVE credentials forbidden in PAPER runner.")
        if not os.environ.get("ALPACA_PAPER_KEY") or not os.environ.get(
            "ALPACA_PAPER_SECRET"
        ):
            raise PaperAdapterStop("Alpaca PAPER credentials unavailable.")
        try:
            remote = operator.read_current_control()
            if operator.validate_control(remote):
                raise PaperAdapterStop("LIVE operator is RUNNING.")
        except operator.OperatorControlStop as exc:
            raise PaperAdapterStop("Operator control unavailable.") from exc

    def market_open(self) -> bool:
        clock = paper.get_clock()
        if not isinstance(clock, dict):
            raise PaperAdapterStop("Malformed PAPER market clock.")
        return clock.get("is_open") is True

    def snapshot(self) -> dict:
        account = paper.get_account()
        raw_positions = paper.get_positions()
        orders = paper.get_open_orders()
        if not isinstance(account, dict):
            raise PaperAdapterStop("PAPER account missing.")
        if not isinstance(raw_positions, list) or not isinstance(orders, list):
            raise PaperAdapterStop("PAPER broker state malformed.")
        if len(orders) >= 500:
            raise PaperAdapterStop("PAPER open-order list may be truncated.")
        positions = {}
        for item in raw_positions:
            if not isinstance(item, dict):
                raise PaperAdapterStop("PAPER position malformed.")
            symbol = item.get("symbol")
            if symbol not in self.approved_symbols or symbol in positions:
                raise PaperAdapterStop("Unmanaged or duplicate PAPER position.")
            positions[symbol] = {
                "qty": item.get("qty"),
                "market_value": item.get("market_value"),
            }
        return {
            "account": account,
            "positions": positions,
            "open_orders": orders,
        }

    def history(self) -> dict:
        value = paper.paper_request(
            method="GET",
            path="/v2/account/portfolio/history?period=1M&timeframe=1D",
        )
        if not isinstance(value, dict):
            raise PaperAdapterStop("PAPER account performance history unavailable.")
        return value

    def lookup(self, client_order_id: str) -> dict | None:
        if not isinstance(client_order_id, str) or not client_order_id.startswith(
            "f100paper-"
        ):
            raise PaperAdapterStop("Unrecognised PAPER client ID.")
        return paper.get_order_by_client_id(client_order_id)

    def post_notional(self, order: dict) -> dict:
        self.require_paper_only_arm()
        if not isinstance(order, dict):
            raise PaperAdapterStop("PAPER order malformed.")
        symbol = order.get("symbol")
        side = order.get("side")
        cid = order.get("client_order_id")
        if symbol not in self.approved_symbols or side not in {"buy", "sell"}:
            raise PaperAdapterStop("Unapproved PAPER asset/direction.")
        if not isinstance(cid, str) or not cid.startswith("f100paper-"):
            raise PaperAdapterStop("Unapproved PAPER client ID.")
        notional = risk.finite_decimal(
            order.get("notional_usd"), "PAPER order notional"
        )
        if notional < Decimal("1") or notional > Decimal("130.30"):
            raise PaperAdapterStop("PAPER order outside micro-pilot bounds.")
        if self.lookup(cid) is not None:
            raise PaperAdapterStop("PAPER order already accepted by broker.")
        payload = {
            "symbol": symbol, "notional": str(notional), "side": side,
            "type": "market", "time_in_force": "day",
            "extended_hours": False, "client_order_id": cid,
        }
        response = paper.paper_request(
            method="POST", path="/v2/orders", body=payload,
        )
        if not isinstance(response, dict) or response.get(
            "client_order_id"
        ) != cid:
            raise PaperAdapterStop("PAPER order submission identity ambiguous.")
        if response.get("symbol") != symbol or str(
            response.get("side", "")
        ).lower() != side:
            raise PaperAdapterStop("PAPER broker order symbol/side mismatch.")
        return response

    def wait_terminal(self, client_order_id: str) -> dict:
        for _ in range(40):
            order = self.lookup(client_order_id)
            if not isinstance(order, dict):
                raise PaperAdapterStop("Submitted PAPER order not retrievable.")
            status = str(order.get("status", "")).lower()
            if status in {"filled", "rejected", "canceled", "cancelled", "expired"}:
                return order
            if status not in {"new", "pending_new", "accepted", "partially_filled",
                              "pending_cancel"}:
                raise PaperAdapterStop("Unknown PAPER order status.")
            time.sleep(1)
        # A timeout does not imply an order was canceled. Caller stops
        # and operator must inspect/cancel the specific PAPER order.
        raise PaperAdapterStop("PAPER order still pending; manual review required.")

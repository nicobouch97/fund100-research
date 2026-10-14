"""PAPER-only V5 execution bridge; production logic, injected broker.

NOT A SCHEDULED TRADING RUNNER. This module never loads credentials or
chooses a broker endpoint; callers supply a restricted PAPER broker
adapter. Execution requires an attested compiler event, a two-phase
preflight within the pilot ceiling, an explicit broker PAPER-only arm,
and renewed broker reconciliation before each phase.

Do not use this module as a LIVE writer. Any failure aborts further
submissions; automatic flattening is intentionally NOT attempted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

import fund100_live_production_controller_v1_0 as production
import fund100_live_portfolio_risk_v1_0 as portfolio
import fund100_v5_genuine_paper_parity_v1_0 as parity


class PaperBridgeStop(RuntimeError):
    pass


class PaperBroker(Protocol):
    def require_paper_only_arm(self) -> None: ...
    def snapshot(self) -> dict: ...
    def history(self) -> dict: ...
    def market_open(self) -> bool: ...
    def lookup(self, client_order_id: str) -> dict | None: ...
    def post_notional(self, order: dict) -> dict: ...
    def wait_terminal(self, client_order_id: str) -> dict: ...


PAPER_SUPPORTED_STATUSES = {"new", "accepted", "pending_new", "partially_filled", "filled"}
PAPER_FAILED_STATUSES = {"canceled", "cancelled", "expired", "rejected"}


def _validated_order(order: object, expected: dict) -> str:
    if not isinstance(order, dict):
        raise PaperBridgeStop("Broker PAPER order response is malformed.")
    if order.get("client_order_id") != expected["client_order_id"]:
        raise PaperBridgeStop("PAPER order client ID changed.")
    if order.get("symbol") != expected["symbol"]:
        raise PaperBridgeStop("PAPER order symbol changed.")
    if str(order.get("side", "")).lower() != expected["side"]:
        raise PaperBridgeStop("PAPER order side changed.")

    status = str(order.get("status", "")).lower()
    if status in PAPER_FAILED_STATUSES or status not in PAPER_SUPPORTED_STATUSES:
        raise PaperBridgeStop("PAPER order failed or status ambiguous.")
    original_notional = portfolio.finite_decimal(
        order.get("notional"), "PAPER order notional"
    )
    approved = portfolio.finite_decimal(
        expected["notional_usd"], "approved order notional"
    )
    if original_notional <= 0 or original_notional > approved:
        raise PaperBridgeStop("PAPER broker notional exceeds approved amount.")
    return status


def _phase_orders(
    *, broker_snapshot: dict, desired: dict, preapproved_orders: list,
    phase: str, cap: Decimal, universe: set[str],
) -> list:
    account_snapshot = parity._paper_snapshot(broker_snapshot, universe)
    by_symbol = {x["symbol"]: x for x in preapproved_orders}
    candidates = {
        symbol: {"side": item["side"], "client_order_id": item["client_order_id"]}
        for symbol, item in by_symbol.items()
    }
    raw_orders = production.materialize_orders(
        snapshot=account_snapshot, target_weights=desired,
        candidates=candidates, phase=phase, capital_ceiling=cap,
    )
    for order in raw_orders:
        candidate = by_symbol.get(order["symbol"])
        if not isinstance(candidate, dict) or (
            order["client_order_id"] != candidate["client_order_id"]
            or order["side"] != candidate["side"]
        ):
            raise PaperBridgeStop("Reconstructed order is not preapproved.")
        if Decimal(order["notional_usd"]) > Decimal(candidate["notional_usd"]):
            raise PaperBridgeStop("New broker exposure exceeds frozen preflight.")
    return raw_orders


def execute_attested_paper_event(
    *,
    compiler_package: dict,
    manifest_package: dict,
    shadow_state: dict,
    compiler_written_ns: int,
    now_ns: int,
    broker: PaperBroker,
    execution_universe: set[str],
    capital_ceiling: object,
    risk_level: str,
) -> dict:
    """Execute in PAPER ONLY with a broker implementation that refuses LIVE.

    The invoker must bind the compiler timestamps to this invocation, not
    a fabricated or copied historical artifact. The broker is responsible
    for securely enforcing PAPER-only host and credentials at every POST.
    """
    # A writer must remain OFF until a caller has bound a genuine event
    # provenance to an invocation, even for imaginary-money orders.
    broker.require_paper_only_arm()
    compiler_body = compiler_package.get("compiler")
    if not isinstance(compiler_body, dict):
        raise PaperBridgeStop("Missing compiler body.")

    # No-event short circuit: no broker account read or order.
    from fund100_v5_compiler_attestation_v1_0 import attest_compiler_event
    proof = attest_compiler_event(
        compiler_package=compiler_package, manifest_package=manifest_package,
        shadow_state=shadow_state, compiler_written_ns=compiler_written_ns,
        now_ns=now_ns,
    )
    if not proof["genuine_event"]:
        return {
            "status": "NO_GENUINE_EVENT", "paper_post_count": 0,
            "live_post_count": 0,
        }

    if not broker.market_open():
        raise PaperBridgeStop("PAPER market is closed.")
    initial = broker.snapshot()
    report = parity.plan_attested_paper_event(
        compiler_package=compiler_package, manifest_package=manifest_package,
        shadow_state=shadow_state, compiler_written_ns=compiler_written_ns,
        now_ns=now_ns, paper_snapshot=initial,
        paper_history=broker.history(), execution_universe=execution_universe,
        capital_ceiling=capital_ceiling, risk_level=risk_level,
    )
    if report["status"] == "GENUINE_EVENT_NO_COMPILER_INTENTS":
        return {
            "status": "NO_COMPILER_INTENTS", "paper_post_count": 0,
            "live_post_count": 0,
        }
    if report["status"] != "GENUINE_EVENT_PREFLIGHT_ONLY":
        raise PaperBridgeStop("No authorized strategy PAPER plan.")
    preflight = report["paper_orders"]
    if not preflight:
        return {
            "status": "NO_PAPER_REBALANCE_NEEDED", "paper_post_count": 0,
            "live_post_count": 0,
        }

    cap = portfolio.finite_decimal(capital_ceiling, "pilot ceiling")
    approved_gross = sum(
        (Decimal(o["notional_usd"]) for o in preflight), Decimal("0"),
    )
    if approved_gross > cap:
        raise PaperBridgeStop("PAPER event exceeds pilot ceiling.")
    by_id = {o["client_order_id"]: o for o in preflight}
    if len(by_id) != len(preflight):
        raise PaperBridgeStop("Duplicate approved PAPER client IDs.")
    for approved in preflight:
        if not approved["client_order_id"].startswith("f100paper-"):
            raise PaperBridgeStop("Unexpected PAPER order identity.")

    submissions = 0
    executed = set()
    for phase in ("SELL", "BUY"):
        if not broker.market_open():
            raise PaperBridgeStop("PAPER market closed before phase.")
        snapshot = broker.snapshot()
        if snapshot.get("open_orders"):
            raise PaperBridgeStop("Unsettled or foreign PAPER orders before phase.")
        normalized = parity._paper_snapshot(snapshot, execution_universe)
        # Do not place orders if account volatility/drawdown suddenly changed.
        portfolio.check_portfolio_risk(
            snapshot=normalized,
            target_weights=report["paper_target_weights"],
            capital_ceiling=cap, history=broker.history(), level=risk_level,
        )
        next_orders = _phase_orders(
            broker_snapshot=snapshot, desired=report["paper_target_weights"],
            preapproved_orders=preflight, phase=phase, cap=cap,
            universe=execution_universe,
        )
        for order in next_orders:
            cid = order["client_order_id"]
            if cid in executed:
                raise PaperBridgeStop("Duplicate planned PAPER order.")
            expected = by_id[cid]
            existing = broker.lookup(cid)
            if existing is None:
                # Re-evaluate cumulative original authorizations, including
                # orders from a prior attempt, before submitting a POST.
                historical = {}
                for known_id in by_id:
                    historical[known_id] = broker.lookup(known_id)
                consumed = sum((
                    portfolio.finite_decimal(
                        item["notional"], "historical PAPER notional"
                    )
                    for item in historical.values() if item is not None
                ), Decimal("0"))
                newly_committed = sum(
                    Decimal(x["notional_usd"]) for x in next_orders
                    if historical.get(x["client_order_id"]) is None
                )
                if consumed + newly_committed > cap:
                    raise PaperBridgeStop("Cumulative PAPER event budget exceeded.")
                # A fresh PAPER-only arm is required immediately before POST.
                broker.require_paper_only_arm()
                existing = broker.post_notional(order)
                submissions += 1
            _validated_order(existing, expected)
            settled = broker.wait_terminal(cid)
            if _validated_order(settled, expected) != "filled":
                raise PaperBridgeStop("PAPER event order did not fill completely.")
            executed.add(cid)

    latest = broker.snapshot()
    normalized = parity._paper_snapshot(latest, execution_universe)
    if latest.get("open_orders"):
        raise PaperBridgeStop("PAPER event left open orders.")
    nav = min(normalized["equity"], cap)
    for symbol in (
        set(report["paper_target_weights"]) | set(normalized["positions"])
    ):
        current = normalized["positions"].get(symbol, {}).get(
            "market_value", Decimal("0")
        )
        target = report["paper_target_weights"].get(symbol, Decimal("0"))
        if abs(current / nav - target) > production.FINAL_WEIGHT_TOLERANCE:
            raise PaperBridgeStop("Final PAPER target weight mismatch.")

    return {
        "status": "PAPER_EVENT_FILLED_AND_RECONCILED",
        "paper_post_count": submissions,
        "live_post_count": 0,
        "attested_event_sha256": report["attested_event_sha256"],
        "risk_level": risk_level,
        "reconciled": True,
    }

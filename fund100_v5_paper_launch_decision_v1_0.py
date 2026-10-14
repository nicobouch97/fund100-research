"""V5-002 strategy PAPER launch decision: explicit evidence, no order writes.

This gate deliberately separates completed broker-fill mechanics from
authority to execute the NEXT genuine scheduled strategy event. It is
not an Alpaca client and has no credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fund100_v5_compiler_attestation_v1_0 as attest


class LaunchDecisionStop(RuntimeError):
    pass


def decide(*, paper_fill_evidence: object, account_readiness: object,
           compiler_package: dict | None, manifest_package: dict | None,
           shadow_state: dict | None, compiler_written_ns: int | None,
           now_ns: int | None) -> dict[str, Any]:
    """No orders can be approved on historical PAPER evidence alone."""
    if not isinstance(paper_fill_evidence, dict) or (
        paper_fill_evidence.get("result") != "PASS"
        or paper_fill_evidence.get("broker_environment") != "ALPACA_PAPER_ONLY"
        or paper_fill_evidence.get("paper_buy_filled") is not True
        or paper_fill_evidence.get("paper_sell_filled") is not True
        or paper_fill_evidence.get("original_paper_share_quantity_restored") is not True
        or paper_fill_evidence.get("live_orders_submitted") != 0
    ):
        raise LaunchDecisionStop("Broker PAPER fill evidence is absent or inconsistent.")

    if not isinstance(account_readiness, dict) or (
        account_readiness.get("paper_preflight_compatible") is not True
        or account_readiness.get("mode") != "READ_ONLY_NO_ORDERS"
        or account_readiness.get("capital_ceiling_usd") != "130.30"
        or account_readiness.get("signal_gate") not in {
            "NO_PENDING_GENUINE_EVENT",
            "PENDING_STATE_NOT_YET_ATTESTED",
            "PENDING_STATE_MANIFEST_MATCH_NO_COMPILER_ATTESTATION",
        }
    ):
        raise LaunchDecisionStop("Current PAPER readiness evidence is not acceptable.")

    # Historical readiness is only a prerequisite: it must be refreshed
    # by the PAPER broker immediately before any execution.
    if compiler_package is None:
        return {
            "status": "WAITING_FOR_GENUINE_V5_EVENT",
            "paper_order_authorized": False,
            "live_order_authorized": False,
            "reason": "No fresh same-invocation attested compiler event",
            "next_gate": "Generate CURRENT v1.1 event, attest source, refresh PAPER broker state",
        }

    if not all((
        manifest_package is not None, shadow_state is not None,
        type(compiler_written_ns) is int, type(now_ns) is int,
    )):
        raise LaunchDecisionStop("A source compiler package lacks same-run evidence.")

    try:
        proof = attest.attest_compiler_event(
            compiler_package=compiler_package,
            manifest_package=manifest_package,
            shadow_state=shadow_state,
            compiler_written_ns=compiler_written_ns,
            now_ns=now_ns,
        )
    except (attest.CompilerAttestationStop, TypeError, KeyError) as exc:
        raise LaunchDecisionStop("Compiler attestation rejected event.") from exc

    if not proof["genuine_event"]:
        return {
            "status": "NO_GENUINE_STRATEGY_EVENT",
            "paper_order_authorized": False,
            "live_order_authorized": False,
            "reason": "Compiler explicitly reported no strategy event",
        }

    # This is only approval to ATTEMPT a new PAPER preflight, never
    # direct execution authority or approval for LIVE.
    return {
        "status": "ATTESTED_GENUINE_EVENT_REQUIRES_FRESH_PAPER_PREFLIGHT",
        "paper_order_authorized": False,
        "live_order_authorized": False,
        "attested_compiler_sha256": proof["compiler_sha256"],
        "attested_event_sha256": proof["event_sha256"],
        "next_gate": "Reconcile PAPER positions, recheck risk and compile broker-specific orders",
    }

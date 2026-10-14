"""READ-ONLY diagnostic for Fund-100's genuine V5 PAPER promotion gate.

Answers two separate questions without account details in public logs:
  (1) Is the current PAPER account compatible with the $130.30 pilot?
  (2) Has the frozen shadow strategy requested a scheduled rebalance?

This is NOT a compiler event and cannot authorize a trade.
No broker POST/DELETE and no LIVE credentials are used.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fund100_alpaca_paper_orchestrator_connected_v1_0 as broker
import fund100_live_operator_control_v1_0 as operator
import fund100_live_portfolio_risk_v1_0 as risk
import fund100_live_production_controller_v1_0 as controller


POLICY = Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
SHADOW = Path("shadow_outputs/v5_002/shadow_state.json")
MANIFEST = Path("live_dryrun_outputs/v5_002/live_execution_manifest.json")
HISTORY = "/v2/account/portfolio/history?period=1M&timeframe=1D"


class PaperReadinessStop(RuntimeError):
    pass


def signal_gate(state: object, manifest_pkg: object) -> str:
    """A pending strategy rebalance is NOT proof of an attested compiler event."""
    if not isinstance(state, dict) or state.get("strategy") != "V5-002_SHADOW":
        raise PaperReadinessStop("Unexpected shadow strategy state.")
    source = state.get("pending_source")
    pending = state.get("pending_target")
    if source is None and pending is None:
        return "NO_PENDING_GENUINE_EVENT"
    if source != "SCHEDULED" or not isinstance(pending, dict) or not pending:
        raise PaperReadinessStop("Ambiguous or unsupported pending strategy event.")
    if not isinstance(manifest_pkg, dict):
        raise PaperReadinessStop("Missing signed source manifest.")
    body = manifest_pkg.get("manifest")
    if not isinstance(body, dict):
        raise PaperReadinessStop("Malformed strategy manifest.")
    # Pending strategy state only makes compilation eligible, not executable.
    if (
        body.get("event_source") != "SCHEDULED"
        or body.get("strategy_event_present") is not True
        or body.get("strategy_state_sha256") != controller.canonical_sha256(state)
        or body.get("strategy_state_date") != state.get("last_date")
        or manifest_pkg.get("manifest_sha256") != controller.canonical_sha256(body)
    ):
        return "PENDING_STATE_NOT_YET_ATTESTED"
    return "PENDING_STATE_MANIFEST_MATCH_NO_COMPILER_ATTESTATION"


def assess_paper_account(
    *, account: object, positions: object, open_orders: object,
    history: object, policy: object,
) -> dict:
    if (
        not isinstance(policy, dict)
        or policy.get("deployment_mode") != "LIVE_MICRO_PILOT"
        or policy.get("capital_ceiling_usd") != "130.30"
    ):
        raise PaperReadinessStop("Unexpected pilot policy.")
    universe = policy.get("execution_universe")
    if not isinstance(universe, list) or len(universe) != 14:
        raise PaperReadinessStop("Unexpected approved ETF universe.")
    if not isinstance(account, dict) or not isinstance(positions, list):
        raise PaperReadinessStop("Malformed Alpaca PAPER account.")
    if not isinstance(open_orders, list) or len(open_orders) >= 500:
        raise PaperReadinessStop("Malformed or truncated PAPER open-order index.")

    approved = set(universe)
    clean_positions = {}
    symbols_approved = True
    for position in positions:
        if not isinstance(position, dict):
            raise PaperReadinessStop("Malformed PAPER position.")
        sym = position.get("symbol")
        if (
            not isinstance(sym, str) or sym in clean_positions
            or sym not in approved
        ):
            symbols_approved = False
        if sym in clean_positions:
            raise PaperReadinessStop("Duplicate PAPER broker position.")
        value = risk.finite_decimal(position.get("market_value"), "PAPER value")
        qty = risk.finite_decimal(position.get("qty"), "PAPER quantity")
        if value < 0 or qty < 0:
            symbols_approved = False
        clean_positions[sym] = {"market_value": value}

    account_eligible = (
        account.get("status") == "ACTIVE"
        and account.get("trading_blocked") is False
    )
    portfolio_limits = False
    history_eligible = False
    if account_eligible and symbols_approved:
        try:
            risk.check_actual_exposure(
                positions=clean_positions,
                equity=account.get("equity"),
                capital_ceiling=policy["capital_ceiling_usd"],
                profile=risk.get_profile("HIGH"),
            )
            portfolio_limits = True
        except risk.PortfolioRiskStop:
            pass
        try:
            risk.check_account_performance(
                account=account, history=history,
                profile=risk.get_profile("HIGH"),
            )
            history_eligible = True
        except risk.PortfolioRiskStop:
            pass

    no_open_orders = len(open_orders) == 0
    return {
        "paper_account_active": account_eligible,
        "approved_etf_holdings_only": symbols_approved,
        "paper_open_orders_clear": no_open_orders,
        "paper_exposure_within_130_30_ceiling": portfolio_limits,
        "paper_history_valid_under_high_profile": history_eligible,
        "paper_preflight_compatible": all((
            account_eligible, symbols_approved, no_open_orders,
            portfolio_limits, history_eligible,
        )),
        "paper_existing_position_count": len(positions),
        "paper_existing_open_order_count": len(open_orders),
    }


def main() -> None:
    # No LIVE secrets should ever be available in a PAPER diagnostics job.
    if (
        os.environ.get("ALPACA_LIVE_KEY")
        or os.environ.get("ALPACA_LIVE_SECRET")
        or broker.PAPER_BASE_URL != "https://paper-api.alpaca.markets"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.environ.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
    ):
        raise PaperReadinessStop("PAPER read-only job has unsafe environment.")
    try:
        if operator.validate_control(operator.read_current_control()):
            raise PaperReadinessStop("Operator STOP must remain engaged.")
    except operator.OperatorControlStop as exc:
        raise PaperReadinessStop("Operator state unavailable.") from exc

    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        shadow = json.loads(SHADOW.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PaperReadinessStop("Source state unavailable.") from exc

    signal = signal_gate(shadow, manifest)
    if not os.environ.get("ALPACA_PAPER_KEY") or not os.environ.get(
        "ALPACA_PAPER_SECRET"
    ):
        raise PaperReadinessStop("PAPER read-only credentials unavailable.")

    status = assess_paper_account(
        account=broker.get_account(),
        positions=broker.get_positions(),
        open_orders=broker.get_open_orders(),
        history=broker.paper_request(method="GET", path=HISTORY),
        policy=policy,
    )
    # Intentionally do NOT log portfolio balances, account number,
    # fills, market values, prices, IDs, or share quantities.
    status.update({
        "schema": "FUND100_V5_PAPER_READINESS_V1",
        "mode": "READ_ONLY_NO_ORDERS",
        "signal_gate": signal,
        "genuine_event_order_execution_approved": False,
        "live_order_execution_approved": False,
    })
    print(json.dumps(status, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

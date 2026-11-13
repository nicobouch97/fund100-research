"""Independent scheduled broker risk watcher for Fund-100 LIVE.

Runs only when the operator control is RUNNING, with no strategy compiler
or order-submission paths. A risk/data failure attempts to set persistent
STOP and selectively cancel outstanding Fund-100 orders.

This does not liquidate positions and cannot guarantee fills won't occur
during a cancellation race. No account data is saved to GitHub.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fund100_live_bootstrap_v1_0 as broker
import fund100_live_emergency_stop_v1_0 as emergency
import fund100_live_operator_control_v1_0 as operator
import fund100_live_portfolio_risk_v1_0 as risks


POLICY_PATH = Path(
    "live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"
)
HISTORY_PATH = "/v2/account/portfolio/history?period=1M&timeframe=1D"


class RiskMonitorStop(RuntimeError):
    """Monitoring cannot verify that the account is within limits."""


def _policy() -> dict:
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RiskMonitorStop("Unable to load authorized pilot policy.") from exc
    if not isinstance(value, dict):
        raise RiskMonitorStop("Malformed pilot policy.")
    if value.get("deployment_mode") != "LIVE_MICRO_PILOT":
        raise RiskMonitorStop("Unexpected pilot deployment mode.")
    if value.get("leverage_allowed") is not False:
        raise RiskMonitorStop("Leveraged pilot policy rejected.")
    if value.get("shorting_allowed") is not False:
        raise RiskMonitorStop("Short-selling pilot policy rejected.")
    if value.get("additional_deposits_automatically_usable") is not False:
        raise RiskMonitorStop("Unauthorized additional funding policy.")
    binding = value.get("account_binding_sha256")
    if not isinstance(binding, str) or len(binding) != 64:
        raise RiskMonitorStop("Account binding policy invalid.")
    return value


def inspect_live_risk(
    *,
    account: dict,
    positions: object,
    history: object,
    policy: dict,
    level: str,
    actual_account_binding: str,
) -> None:
    """Pure validation so the monitor can be tested without HTTP."""
    profile = risks.get_profile(level)
    if not isinstance(account, dict):
        raise RiskMonitorStop("Malformed Alpaca account.")
    # Alpaca flags must be authentic booleans. A missing/null/string flag
    # is UNKNOWN, never proof that this live account is unblocked.
    # Account-wide blocks and an owner-initiated trade suspension also deny trading.
    if (account.get("status") != "ACTIVE"
        or account.get("trading_blocked") is not False
        or account.get("account_blocked") is not False
        or account.get("trade_suspended_by_user") is not False):
        raise RiskMonitorStop("Alpaca account unavailable for LIVE trading.")
    if actual_account_binding != policy.get("account_binding_sha256"):
        raise RiskMonitorStop("Unexpected broker account binding.")
    if not isinstance(positions, list):
        raise RiskMonitorStop("Malformed Alpaca positions.")
    execution_universe = policy.get("execution_universe")
    if not isinstance(execution_universe, list) or not execution_universe:
        raise RiskMonitorStop("Missing approved universe.")
    allowed_symbols = set(execution_universe)
    if any(not isinstance(s, str) or not s.isupper() for s in allowed_symbols):
        raise RiskMonitorStop("Invalid execution universe.")

    projected_positions = {}
    for item in positions:
        if not isinstance(item, dict):
            raise RiskMonitorStop("Malformed broker position item.")
        symbol = item.get("symbol")
        if symbol not in allowed_symbols or symbol in projected_positions:
            raise RiskMonitorStop("Unexpected or duplicated broker position.")
        qty = risks.finite_decimal(item.get("qty"), "position quantity")
        if qty < 0:
            raise RiskMonitorStop("Short broker position.")
        projected_positions[symbol] = {
            "market_value": item.get("market_value"),
        }

    risks.check_actual_exposure(
        positions=projected_positions,
        equity=account.get("equity"),
        capital_ceiling=policy.get("capital_ceiling_usd"),
        profile=profile,
    )
    risks.check_account_performance(
        account=account, history=history, profile=profile
    )


def live_read_only_snapshot() -> tuple[dict, object, object, dict, str]:
    """Account, positions and history use only existing broker GET methods."""
    policy = _policy()
    account = broker.get_account()
    positions = broker.get_positions()
    history = broker.live_request(method="GET", path=HISTORY_PATH)
    binding = broker.account_binding(account)
    return account, positions, history, policy, binding


def _attempt_emergency_stop_and_cancel() -> str:
    """On uncertainty, attempt BOTH protective actions independently.

    The broker cancellation attempt MUST still run when GitHub cannot
    commit the operator STOP. A STOP latch alone does not prove that there
    are no OPEN Fund-100 broker orders. None of the exceptions/payloads
    from these privileged operations may reach public logs.
    """
    stop_confirmed = False
    cancellation_observed = False
    try:
        stop_outcome = operator.commit_stop_signal()
        stop_confirmed = stop_outcome in ("STOPPED", "ALREADY_STOPPED")
    except Exception:
        # Keep going. A GitHub outage must not suppress broker cancellation.
        pass
    try:
        cancelled = emergency.cancel_open_fund100_orders()
        cancellation_observed = type(cancelled) is int and cancelled >= 0
    except Exception:
        # Never infer cancellation from DELETE acceptance alone.
        pass
    if not stop_confirmed and not cancellation_observed:
        raise RiskMonitorStop(
            "Persistent STOP and broker open-order absence BOTH unverified; "
            "escalate immediately."
        )
    if not stop_confirmed:
        raise RiskMonitorStop(
            "Broker open-order absence was observed but persistent STOP "
            "is unverified; escalate immediately."
        )
    if not cancellation_observed:
        raise RiskMonitorStop(
            "Persistent STOP was observed but broker cancellation "
            "is unverified; escalate immediately."
        )
    # Only two point-in-time observations; this is NOT confirmation of no
    # preceding fills, settlement or any future/new broker order.
    return "AUTO_STOP_CONFIRMED"


def monitor_once() -> str:
    # STOPPED is the expected pre-launch state; this early return is NOT a
    # fresh broker open-order or cancellation receipt. A separate continuous
    # observer must verify broker state before any real autonomous release.
    try:
        control = operator.read_current_control()
        if not operator.validate_control(control):
            return "ALREADY_STOPPED"

        account, positions, history, policy, binding = live_read_only_snapshot()
        inspect_live_risk(
            account=account,
            positions=positions,
            history=history,
            policy=policy,
            level=os.environ.get("FUND100_RISK_LEVEL", ""),
            actual_account_binding=binding,
        )
    except Exception:
        # A failed operator read is itself unsafe and must not leave broker
        # cancellation unattempted. Never leak broker or GitHub errors.
        print("RISK MONITOR: account/control verification failed; requesting STOP.")
        return _attempt_emergency_stop_and_cancel()

    return "WITHIN_RISK_LIMITS"


if __name__ == "__main__":
    result = monitor_once()
    print("Fund-100 risk monitor:", result)

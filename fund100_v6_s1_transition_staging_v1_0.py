"""V6-S1 brokerless, read-only transition-stage classifier (NEVER an order engine).

Accepts a caller-supplied GET-only snapshot for structural validation. This
function cannot authenticate the caller's broker observations or prove US cash
settlement. It emits no amounts, quantities, client IDs or broker instructions.
All output is deliberately unfit to pass to a broker execution adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

SCHEMA = "FUND100_V6_S1_TRANSITION_STAGE_NO_ORDERS_V1"
SNAPSHOT_SCHEMA = "FUND100_V6_S1_CALLER_ASSERTED_LIVE_GET_ONLY_V1"
PROPOSAL_SCHEMA = "FUND100_V6_CONCENTRATED_HIGH_EXPERIMENTAL_PROPOSAL_V1"
CAP = Decimal("130.30")
OLD = frozenset({"ACWI", "EEM", "XLE", "XLV"})
NEW = frozenset({"XLK", "XLE", "IWM"})
EXPECTED_PATHS = frozenset({"/v2/account", "/v2/positions", "/v2/orders?status=open&limit=100", "/v2/clock"})
FRESHNESS_SECONDS = 300


class StageStop(ValueError):
    """Reject inconsistent evidence without emitting trade intents."""


def num(value: object, label: str, *, signed: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise StageStop("Invalid numeric field: " + label)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise StageStop("Unparseable numeric field: " + label) from exc
    if not amount.is_finite() or (not signed and amount < 0):
        raise StageStop("Nonfinite/out-of-range numeric field: " + label)
    return amount


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise StageStop("UTC source time is missing")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise StageStop("Source time must be canonical UTC") from exc
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise StageStop("Noncanonical source time")
    return dt


def review(*, snapshot: dict, proposal: dict, operator: dict,
           expected_account_binding_sha256: str, now_utc: str,
           paper_round_trip_verified: bool = False,
           independent_settlement_proof: bool = False,
           risk_measurements: dict | None = None) -> dict:
    """Classify the next engineering milestone, never authorise a trade.

    Inputs are caller assertions, NOT independently authenticated evidence.
    Any future executor must re-GET broker positions, orders and cash itself.
    """
    if (not isinstance(proposal, dict)
        or proposal.get("schema") != PROPOSAL_SCHEMA
        or proposal.get("status") != "PROPOSED_NOT_LIVE"
        or proposal.get("strategy_id") != "V6_S1_FIXED_SECTOR_RISK_PREMIUM"
        or proposal.get("original_trial_max_capital_usd") != "130.30"
        or proposal.get("target_weights") != {"XLK": "0.475", "XLE": "0.285", "IWM": "0.190"}
        or proposal.get("cash_reserve_fraction") != "0.05"
        or proposal.get("maximum_gross_exposure") != "0.95"
        or proposal.get("live_order_execution_released") is not False
        or proposal.get("live_operator_trading_enabled") is not False
        or proposal.get("live_environment_kill_switch") != "ENGAGED"
        or proposal.get("allow_margin") is not False
        or proposal.get("allow_leverage") is not False
        or proposal.get("allow_new_deposits") is not False):
        raise StageStop("Original S1 NO-LIVE proposal not verified")
    if operator != {"schema": "FUND100_OPERATOR_CONTROL_V1", "trading_enabled": False}:
        raise StageStop("LIVE operator STOP cannot be bypassed")
    if (not isinstance(expected_account_binding_sha256, str)
        or len(expected_account_binding_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_account_binding_sha256)):
        raise StageStop("Frozen LIVE account binding not provided")
    if (not isinstance(snapshot, dict)
        or snapshot.get("schema") != SNAPSHOT_SCHEMA
        or snapshot.get("mode") != "ALPACA_LIVE_GET_ONLY"
        or snapshot.get("request_methods") != ["GET"] * 4
        or not isinstance(snapshot.get("request_paths"), list)
        or set(snapshot["request_paths"]) != EXPECTED_PATHS
        or len(snapshot["request_paths"]) != 4
        or snapshot.get("orders_submitted") != 0
        or snapshot.get("account_binding_sha256") != expected_account_binding_sha256):
        raise StageStop("Missing GET-only source claim or account binding mismatch")
    elapsed = (utc(now_utc) - utc(snapshot.get("observed_at_utc"))).total_seconds()
    if not 0 <= elapsed <= FRESHNESS_SECONDS:
        raise StageStop("Stale/future live account observation")

    account = snapshot.get("account")
    clock = snapshot.get("clock")
    if (not isinstance(account, dict) or account.get("status") != "ACTIVE"
        or account.get("trading_blocked") is not False
        or not isinstance(clock, dict) or type(clock.get("is_open")) is not bool):
        raise StageStop("Invalid live account or market-clock read")
    equity = num(account.get("equity"), "equity")
    cash = num(account.get("cash"), "cash")
    buying_power = num(account.get("buying_power"), "buying_power")
    if equity <= 0 or cash > equity or buying_power < cash:
        raise StageStop("Live account cash/buying-power reconciliation failed")

    rows = snapshot.get("positions")
    orders = snapshot.get("open_orders")
    if not isinstance(rows, list) or len(rows) > 20 or not isinstance(orders, list):
        raise StageStop("Missing broker position/order set")
    held = set()
    for row in rows:
        if not isinstance(row, dict):
            raise StageStop("Malformed position")
        symbol = row.get("symbol")
        if symbol not in OLD or symbol in held:
            raise StageStop("Unknown, new-strategy or duplicated LIVE holding")
        if num(row.get("qty"), "position qty") <= 0:
            raise StageStop("No short/empty LIVE position allowed")
        if num(row.get("market_value"), "position value") <= 0:
            raise StageStop("Invalid LIVE asset market value")
        held.add(symbol)
    if orders:
        stage = "BLOCKED_OPEN_BROKER_ORDERS"
    elif held == OLD:
        stage = "LEGACY_FOUR_STILL_HELD_NO_SELL"
    elif held:
        stage = "PARTIAL_LEGACY_EXIT_MANUAL_RECONCILIATION"
    elif paper_round_trip_verified is not True:
        stage = "AWAIT_S1_REAL_PAPER_FILL_MECHANICS"
    elif independent_settlement_proof is not True:
        stage = "AWAIT_INDEPENDENT_T_PLUS_ONE_SETTLEMENT_PROOF"
    elif not isinstance(risk_measurements, dict):
        stage = "AWAIT_FRESH_ACCOUNT_RISK_MEASUREMENTS"
    else:
        daily = num(risk_measurements.get("daily_return"), "daily return", signed=True)
        drawdown = num(risk_measurements.get("peak_drawdown"), "peak drawdown", signed=True)
        vol = num(risk_measurements.get("annualized_volatility"), "annualized volatility")
        if daily <= Decimal("-0.06") or drawdown <= Decimal("-0.20") or vol > Decimal("0.35"):
            stage = "BLOCKED_ACCOUNT_LOSS_OR_VOLATILITY_STOP"
        elif cash < min(equity, CAP) or buying_power < min(equity, CAP):
            stage = "BLOCKED_UNFUNDED_SETTLED_CASH_TARGET"
        elif not clock["is_open"]:
            stage = "AWAIT_REGULAR_MARKET_SESSION"
        else:
            stage = "MECHANICALLY_PLAUSIBLE_NO_ORDER_RELEASE"
    return {
        "schema": SCHEMA,
        "stage": stage,
        "strategy_id": "V6_S1_FIXED_SECTOR_RISK_PREMIUM",
        "legacy_positions_present": len(held),
        "s1_paper_round_trip_claimed": paper_round_trip_verified is True,
        "settlement_independently_proven_by_this_module": False,
        "broker_snapshot_independently_authenticated_by_this_module": False,
        "strategy_alpha_established": False,
        "portfolio_targets_are_hypothetical": True,
        "original_cap_usd": "130.30",
        "original_stop_preserved": True,
        "new_live_orders_authorized": False,
        "sell_orders": 0,
        "buy_orders": 0,
        "broker_requests": 0,
        "executable_order_payload": None,
        "next_action_requires_new_versioned_live_policy": True,
    }

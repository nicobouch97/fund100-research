"""LIVE GET-only funding preview for V5-002. NEVER an order plan or permit.

A historical shadow allocation is used for hypothetical comparison, NOT as
a genuine strategy event. No market prices, balances, positions, broker IDs,
or raw orders are persisted or printed.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import fund100_live_bootstrap_v1_0 as live
import fund100_live_operator_control_v1_0 as operator
import fund100_live_portfolio_risk_v1_0 as risk
import fund100_live_risk_sizing_v1_0 as sizing

POLICY_PATH = Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
LOCK_PATH = Path("live_activation_outputs/v5_002/pre_live_release_lock_v1_9.json")
SHADOW_PATH = Path("shadow_outputs/v5_002/shadow_state.json")
HISTORY_PATH = "/v2/account/portfolio/history?period=1M&timeframe=1D"
OPEN_PATH = "/v2/orders?status=open&limit=500"
GET_ENDPOINTS = frozenset({"/v2/account", "/v2/positions", OPEN_PATH, HISTORY_PATH})
FROZEN_ETFS = frozenset((
    "ACWI", "SPY", "IWM", "EFA", "EEM", "VNQ", "XLK", "XLF",
    "XLI", "XLV", "XLP", "XLY", "XLE", "XLU",
))
CAP = Decimal("130.30")
MIN_ORDER = Decimal("1.00")
DIRECTION_TOLERANCE = Decimal("0.50")
# Hypothetical discount for price drift, expenses and slippage.
# Not a claim about exchange prices or settled proceeds.
SELL_PROCEEDS_HAIRCUT = Decimal("0.99")


class FundingPreviewStop(RuntimeError):
    pass


def money_floor(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def preview(*, account: object, positions: object, open_orders: object,
            history: object, shadow: object, policy: object,
            binding: str, risk_level: str) -> dict:
    """Pure reference comparison; never constructs or authorizes orders."""
    if not isinstance(policy, dict) or not isinstance(shadow, dict):
        raise FundingPreviewStop("Missing policy or strategy reference.")
    if not (
        policy.get("deployment_mode") == "LIVE_MICRO_PILOT"
        and policy.get("strategy") == "V5-002_SHADOW"
        and policy.get("capital_ceiling_usd") == "130.30"
        and policy.get("live_order_authorization_present") is False
        and policy.get("autonomous_strategy_event_execution_enabled") is False
        and policy.get("leverage_allowed") is False
        and policy.get("shorting_allowed") is False
        and policy.get("crypto_allowed") is False
        and policy.get("additional_deposits_automatically_usable") is False
        and isinstance(policy.get("execution_universe"), list)
        and len(policy["execution_universe"]) == 14
        and set(policy["execution_universe"]) == FROZEN_ETFS
        and binding == policy.get("account_binding_sha256")
    ):
        raise FundingPreviewStop("Frozen capital, universe or binding mismatch.")
    if not (
        shadow.get("strategy") == "V5-002_SHADOW"
        and shadow.get("pending_target") is None
        and shadow.get("pending_source") is None
        and isinstance(shadow.get("satellite_weights"), dict)
        and shadow.get("last_date")
    ):
        raise FundingPreviewStop("Pending event or invalid reference: no preview.")
    if not (
        isinstance(account, dict)
        and account.get("status") == "ACTIVE"
        and account.get("trading_blocked") is False
        and isinstance(positions, list)
        and isinstance(open_orders, list)
        and len(open_orders) == 0
    ):
        raise FundingPreviewStop("Broker account is not clean and active.")

    profile = risk.get_profile(risk_level)
    equity = risk.finite_decimal(account.get("equity"), "LIVE account equity")
    cash = risk.finite_decimal(account.get("cash"), "LIVE available cash")
    if equity <= 0 or cash < 0:
        raise FundingPreviewStop("Invalid account equity or cash.")
    holdings: dict[str, dict] = {}
    for position in positions:
        if not isinstance(position, dict):
            raise FundingPreviewStop("Malformed LIVE broker position.")
        symbol = position.get("symbol")
        if symbol not in FROZEN_ETFS or symbol in holdings:
            raise FundingPreviewStop("Unapproved or duplicated LIVE position.")
        qty = risk.finite_decimal(position.get("qty"), "LIVE position quantity")
        market_value = risk.finite_decimal(position.get("market_value"), "LIVE market value")
        if qty <= 0 or market_value <= 0:
            raise FundingPreviewStop("Short, empty or malformed position.")
        holdings[symbol] = {"market_value": market_value}

    risk.check_actual_exposure(
        positions=holdings, equity=equity,
        capital_ceiling=CAP, profile=profile,
    )
    risk.check_account_performance(account=account, history=history, profile=profile)

    satellites = shadow["satellite_weights"]
    if set(satellites) != FROZEN_ETFS - {"ACWI"}:
        raise FundingPreviewStop("Shadow ETF reference is incomplete.")
    weights = {}
    for symbol, raw in satellites.items():
        weight = risk.finite_decimal(raw, "shadow satellite weight")
        if weight < 0 or weight > Decimal("0.15"):
            raise FundingPreviewStop("Invalid frozen satellite weight.")
        weights[symbol] = weight
    total = sum(weights.values(), Decimal(0))
    if total > Decimal("0.275"):
        raise FundingPreviewStop("Unacceptable frozen satellite total.")
    weights["ACWI"] = Decimal(1) - total
    observed_vol = sizing.estimate_observed_volatility(history=history, equity=equity)
    sized = sizing.size_strategy_targets(
        strategy_targets=weights, risk_level=risk_level,
        observed_annualized_volatility=observed_vol,
    )
    deployable_nav = min(equity, CAP)
    sells = []
    buys = []
    # Reference deltas are NOT compiler-authorized trade candidates.
    for symbol in sorted(FROZEN_ETFS):
        current = holdings.get(symbol, {}).get("market_value", Decimal(0))
        target = sized.weights.get(symbol, Decimal(0)) * deployable_nav
        delta = target - current
        if delta < -DIRECTION_TOLERANCE:
            amount = money_floor(-delta)
            if current - amount < Decimal("0.10"):
                amount = money_floor(current * Decimal("0.995"))
            if amount >= MIN_ORDER:
                sells.append(amount)
        elif delta > DIRECTION_TOLERANCE:
            amount = money_floor(delta)
            if amount >= MIN_ORDER:
                buys.append(amount)

    buy_total = sum(buys, Decimal(0))
    sell_total = sum(sells, Decimal(0))
    cash_alone_covers = cash >= buy_total
    discounted_proceeds_could_cover = (
        buy_total > 0 and not cash_alone_covers
        and cash + sell_total * SELL_PROCEEDS_HAIRCUT >= buy_total
    )
    if not buys and not sells:
        classification = "NO_ACTIONABLE_REFERENCE_DELTAS"
    elif not buys:
        classification = "REFERENCE_SELL_ONLY"
    elif cash_alone_covers:
        classification = "CURRENT_CASH_COULD_COVER_REFERENCE_BUYS"
    elif discounted_proceeds_could_cover:
        classification = "HYPOTHETICAL_SELL_PROCEEDS_MIGHT_COVER_REFERENCE_BUYS"
    else:
        classification = "REFERENCE_BUYS_NOT_COVERED_BY_CASH_OR_DISCOUNTED_SELLS"
    return {
        "schema": "FUND100_LIVE_FUNDING_PREVIEW_V1",
        "broker_mode": "LIVE_GET_ONLY",
        "strategy": "V5-002_SHADOW",
        "risk_level": risk_level,
        "capital_ceiling_usd": "130.30",
        "reference_only_no_strategy_signal": True,
        "live_execution_authorized": False,
        "paper_execution_authorized": False,
        "broker_mutations": 0,
        "reference_sell_count": len(sells),
        "reference_buy_count": len(buys),
        "cash_alone_covers_reference_buys": cash_alone_covers,
        "hypothetical_discounted_sell_proceeds_might_cover_buys":
            discounted_proceeds_could_cover,
        "funding_classification": classification,
        "fresh_post_sell_cash_recheck_required": True,
        "source_shadow_date": str(shadow["last_date"]),
        "warning": "Not an executable order plan. Cash and settlement/buying-power "
                   "availability must be independently rechecked after actual sells. "
                   "Market moves, broker restrictions and execution costs can change results.",
    }


def main() -> None:
    if (
        os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("ALPACA_PAPER_KEY")
        or os.getenv("ALPACA_PAPER_SECRET")
    ):
        raise FundingPreviewStop("Unexpected LIVE GET-only execution boundary.")
    if operator.validate_control(operator.read_current_control()):
        raise FundingPreviewStop("Operator STOP must stay engaged.")
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    shadow = json.loads(SHADOW_PATH.read_text(encoding="utf-8"))
    if not (
        lock.get("writer_connected") is False
        and lock.get("writer_transport_released") is False
        and lock.get("live_execution_authorized") is False
    ):
        raise FundingPreviewStop("LIVE writer or release state unexpectedly changed.")
    if not os.getenv("ALPACA_LIVE_KEY") or not os.getenv("ALPACA_LIVE_SECRET"):
        raise FundingPreviewStop("Protected LIVE GET-only credentials unavailable.")

    original = live.live_request
    calls = []
    def guarded_get(*, method: str, path: str, **kwargs):
        if method != "GET" or path not in GET_ENDPOINTS or kwargs.get("body") is not None:
            raise FundingPreviewStop("Broker operation not explicitly GET-allowlisted.")
        if path in calls:
            raise FundingPreviewStop("Unexpected repeated broker request.")
        calls.append(path)
        return original(method="GET", path=path, **kwargs)
    live.live_request = guarded_get
    try:
        account = live.get_account()
        positions = live.get_positions()
        open_orders = live.get_open_orders()
        history = live.live_request(method="GET", path=HISTORY_PATH)
    finally:
        live.live_request = original
    if len(calls) != 4 or set(calls) != GET_ENDPOINTS:
        raise FundingPreviewStop("Incorrect LIVE GET-only broker request coverage.")
    report = preview(
        account=account, positions=positions,
        open_orders=open_orders, history=history,
        shadow=shadow, policy=policy, binding=live.account_binding(account),
        risk_level=os.environ.get("FUND100_RISK_LEVEL", ""),
    )
    # Only sanitized flags and counts leave the protected runner.
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

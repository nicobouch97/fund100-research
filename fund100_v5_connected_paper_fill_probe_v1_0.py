"""One-run, tiny broker-connected ETF PAPER fill/reconciliation probe.

Proof purpose: verify a filled PAPER market/day order and a return to
the pre-test position state, using an ETF selected from the frozen V5
allocation. This is NOT a genuine compiler-generated strategy event,
and it neither promotes nor enables autonomous LIVE trading.

A failure after entry can leave a PAPER position: the workflow fails
rather than falsely claiming a flat account. Retry recovery is limited
to the exact owned order IDs and a symbol initially held at zero.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import fund100_alpaca_paper_orchestrator_connected_v1_0 as paper
import fund100_live_operator_control_v1_0 as operator
import fund100_live_risk_sizing_v1_0 as sizing


TEST_NOTIONAL = Decimal("2.00")
TARGET_PATH = Path(
    "live_activation_outputs/v5_002/live_bootstrap_v1_0.json"
)
TERMINAL = {"filled", "canceled", "cancelled", "expired", "rejected"}
POLL_SECONDS = 1.0
POLL_ATTEMPTS = 90


class PaperFillStop(RuntimeError):
    pass


def validate_arm() -> None:
    if os.getenv("FUND100_PAPER_FILL_ARM") != "PAPER_ONLY_2USD":
        raise PaperFillStop("Explicit $2 PAPER probe arm missing.")
    if os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED":
        raise PaperFillStop("Broker kill switch must remain ENGAGED.")
    if os.getenv("ALPACA_LIVE_KEY") or os.getenv("ALPACA_LIVE_SECRET"):
        raise PaperFillStop("LIVE credentials are forbidden.")
    if os.getenv("FUND100_RISK_LEVEL") != "HIGH":
        raise PaperFillStop("HIGH risk profile required for this frozen one-time probe.")
    if not os.getenv("ALPACA_PAPER_KEY") or not os.getenv("ALPACA_PAPER_SECRET"):
        raise PaperFillStop("Paper credentials missing.")
    if os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research":
        raise PaperFillStop("Unexpected repository.")
    if os.getenv("FUND100_PAPER_FILL_TEST_DATE") != datetime.now(timezone.utc).date().isoformat():
        raise PaperFillStop("This is not the authorised one-time PAPER test date.")

    # The LIVE operator switch must be STOPPED, not just the checkout copy.
    control = operator.read_current_control()
    if operator.validate_control(control):
        raise PaperFillStop("LIVE operator state is RUNNING; test refused.")


def allowed_session(clock: object, when: datetime) -> bool:
    if not isinstance(clock, dict) or clock.get("is_open") is not True:
        return False
    et = when.astimezone(ZoneInfo("America/New_York"))
    return et.weekday() < 5 and (9, 35) <= (et.hour, et.minute) <= (14, 0)


def frozen_v5_selection() -> tuple[list[str], dict]:
    try:
        artifact = json.loads(TARGET_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise PaperFillStop("V5 frozen allocation unavailable.") from exc
    if (
        not isinstance(artifact, dict)
        or artifact.get("strategy") != "V5-002_SHADOW"
        or artifact.get("bootstrap_complete") is not True
        or artifact.get("broker_environment") != "ALPACA_LIVE"
        or artifact.get("pilot_ceiling_usd") != "130.30"
    ):
        raise PaperFillStop("V5 bootstrap artifact mismatch.")

    targets = artifact.get("target_weights")
    if not isinstance(targets, dict):
        raise PaperFillStop("Frozen V5 targets missing.")
    expected = {"ACWI", "EEM", "XLE", "XLV"}
    if set(targets) != expected:
        raise PaperFillStop("Frozen V5 target symbols unexpected.")
    plan = sizing.size_strategy_targets(
        strategy_targets=targets,
        risk_level="HIGH",
        observed_annualized_volatility="0.10",
    )
    if plan.scale_factor != Decimal("1"):
        raise PaperFillStop("V5 pilot targets unexpectedly scaled.")
    symbols = [
        symbol for symbol in ("ACWI", "EEM", "XLE", "XLV")
        if plan.weights[symbol] >= Decimal("0.01")
    ]
    if not symbols:
        raise PaperFillStop("No approved V5 ETF available.")
    return symbols, {s: str(w) for s, w in plan.weights.items()}


QTY_TOLERANCE = Decimal("0.00000001")


def select_approved_test_asset(
    *, owned_positions: object, open_orders: object,
    approved_symbols: list[str],
) -> tuple[str, Decimal]:
    """Prefer an empty V5 asset; preserve baseline shares if all are held."""
    if not isinstance(owned_positions, list) or not isinstance(open_orders, list):
        raise PaperFillStop("Invalid paper broker portfolio response.")
    if len(open_orders) >= 500:
        raise PaperFillStop("Broker open order listing might be truncated.")
    if open_orders:
        raise PaperFillStop("Existing paper open orders: refusing to interfere.")
    if not approved_symbols or len(set(approved_symbols)) != len(approved_symbols):
        raise PaperFillStop("Approved PAPER ETF list invalid.")
    existing = {}
    for item in owned_positions:
        if not isinstance(item, dict) or not isinstance(item.get("symbol"), str):
            raise PaperFillStop("Malformed existing paper position.")
        symbol = item["symbol"]
        if symbol not in approved_symbols or symbol in existing:
            raise PaperFillStop("Unmanaged or duplicate PAPER holdings present.")
        try:
            qty = Decimal(str(item["qty"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise PaperFillStop("Malformed pre-existing share quantity.") from exc
        if not qty.is_finite() or qty <= 0:
            raise PaperFillStop("Non-positive or short PAPER position.")
        existing[symbol] = qty
    for symbol in approved_symbols:
        if symbol not in existing:
            return symbol, Decimal("0")
    # The account holds all frozen V5 ETFs. Never liquidate them.
    return approved_symbols[0], existing[approved_symbols[0]]


def client_id(side: str) -> str:
    if side not in {"b", "s"}:
        raise PaperFillStop("Invalid paper order direction.")
    run = os.environ.get("GITHUB_RUN_ID", "").strip()
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1").strip()
    if not run.isdecimal() or not attempt.isdecimal():
        raise PaperFillStop("GitHub run identity not available.")
    digest = hashlib.sha256(
        f"F100-V5-PAPER-FILL|{run}|{attempt}".encode("ascii")
    ).hexdigest()[:16]
    return f"f100-v5-paper-fill-{digest}-{side}"


def validated_qty(order: object) -> Decimal:
    if not isinstance(order, dict):
        raise PaperFillStop("Malformed paper order response.")
    raw = order.get("filled_qty", "0")
    try:
        result = Decimal(str(raw))
    except Exception as exc:
        raise PaperFillStop("Invalid paper fill quantity.") from exc
    if not result.is_finite() or result < 0:
        raise PaperFillStop("Non-finite or negative paper fill.")
    return result


def poll_terminal(order_id: str) -> dict:
    for _ in range(POLL_ATTEMPTS):
        order = paper.get_order_by_id(order_id)
        if not isinstance(order, dict):
            raise PaperFillStop("Malformed paper order status.")
        if str(order.get("status", "")).lower() in TERMINAL:
            return order
        time.sleep(POLL_SECONDS)
    raise PaperFillStop("Paper order did not become terminal before timeout.")


def owned_position_qty(symbol: str) -> Decimal:
    positions = paper.get_positions()
    if not isinstance(positions, list):
        raise PaperFillStop("Paper broker positions unavailable.")
    matches = [
        p for p in positions
        if isinstance(p, dict) and p.get("symbol") == symbol
    ]
    if len(matches) > 1:
        raise PaperFillStop("Duplicate paper position for test ETF.")
    if not matches:
        return Decimal("0")
    try:
        qty = Decimal(str(matches[0]["qty"]))
    except Exception as exc:
        raise PaperFillStop("Malformed paper position quantity.") from exc
    if not qty.is_finite() or qty < 0:
        raise PaperFillStop("Unexpected short/invalid paper position.")
    return qty


def submit_unique(*, symbol: str, side: str, notional=None, qty=None):
    code = "b" if side == "buy" else "s"
    cid = client_id(code)
    if paper.get_order_by_client_id(cid) is not None:
        raise PaperFillStop("This PAPER test client ID already exists; no duplicate.")
    body = {
        "symbol": symbol, "side": side, "type": "market",
        "time_in_force": "day", "extended_hours": False,
        "client_order_id": cid,
    }
    if (notional is None) == (qty is None):
        raise PaperFillStop("Specify exactly one of notional and qty.")
    if notional is not None:
        body["notional"] = str(notional)
    else:
        body["qty"] = str(qty)
    result = paper.paper_request(
        method="POST", path="/v2/orders", body=body,
    )
    if not isinstance(result, dict) or result.get("client_order_id") != cid:
        raise PaperFillStop("Alpaca PAPER order identity did not match.")
    if not isinstance(result.get("id"), str) or not result["id"]:
        raise PaperFillStop("Alpaca PAPER order ID absent.")
    return result


def run_probe() -> dict:
    validate_arm()
    symbols, frozen_weights = frozen_v5_selection()
    clock = paper.get_clock()
    if not allowed_session(clock, datetime.now(timezone.utc)):
        raise PaperFillStop("Market is not within safe regular PAPER test hours.")
    account = paper.get_account()
    if (
        not isinstance(account, dict)
        or account.get("status") != "ACTIVE"
        or account.get("trading_blocked") is not False
    ):
        raise PaperFillStop("PAPER account is not active.")
    if Decimal(str(account.get("cash", "0"))) < TEST_NOTIONAL * 2:
        raise PaperFillStop("Insufficient uncommitted PAPER cash.")

    symbol, baseline_qty = select_approved_test_asset(
        owned_positions=paper.get_positions(),
        open_orders=paper.get_open_orders(),
        approved_symbols=symbols,
    )
    asset = paper.get_asset(symbol)
    if not isinstance(asset, dict) or (
        asset.get("tradable") is not True
        or asset.get("fractionable") is not True
    ):
        raise PaperFillStop("V5 ETF is not eligible for fractional PAPER trading.")

    buy_id = None
    sell_id = None
    buy_order = None
    sell_order = None
    try:
        buy = submit_unique(
            symbol=symbol, side="buy", notional=TEST_NOTIONAL,
        )
        buy_id = buy["id"]
        try:
            buy_order = poll_terminal(buy_id)
        except PaperFillStop:
            # A timeout is NOT proof of a failed order: broker cancel first.
            paper.cancel_order(buy_id)
            buy_order = poll_terminal(buy_id)

        acquired = validated_qty(buy_order)
        if acquired <= 0:
            raise PaperFillStop("PAPER buy received no fill.")
        held = owned_position_qty(symbol)
        # Never sell existing PAPER holdings. The order's filled quantity
        # and the account's share increase must agree before an exit.
        delta = held - baseline_qty
        if acquired <= 0 or abs(delta - acquired) > QTY_TOLERANCE:
            raise PaperFillStop("PAPER buy fill did not reconcile with baseline.")
        if delta <= 0:
            raise PaperFillStop("PAPER buy added no reconciled shares.")

        sell = submit_unique(symbol=symbol, side="sell", qty=acquired)
        sell_id = sell["id"]
        sell_order = poll_terminal(sell_id)
        if str(sell_order.get("status", "")).lower() != "filled":
            raise PaperFillStop("PAPER clean-up sell did not fully fill.")
        if abs(validated_qty(sell_order) - acquired) > QTY_TOLERANCE:
            raise PaperFillStop("Paper sell quantity mismatch.")
        for _ in range(20):
            if abs(owned_position_qty(symbol) - baseline_qty) <= QTY_TOLERANCE:
                break
            time.sleep(POLL_SECONDS)
        if abs(owned_position_qty(symbol) - baseline_qty) > QTY_TOLERANCE:
            raise PaperFillStop("PAPER baseline shares not restored after exit.")

        return {
            "mode": "REAL_ALPACA_PAPER_ONLY",
            "source": "FROZEN_V5_BOOTSTRAP_TARGETS_NOT_GENUINE_EVENT",
            "status": "PASS",
            "risk_level": "HIGH",
            "paper_etf_symbol": symbol,
            "buy_order_filled": True,
            "sell_order_filled": True,
            "simulated_order_count": 2,
            "paper_entry_notional_usd": str(TEST_NOTIONAL),
            "original_position_restored": True,
            "position_flat_after_exit": baseline_qty == 0,
            "live_orders_submitted": 0,
            "live_credentials_supplied": False,
        }
    finally:
        # Recover by deterministic client IDs, not just returned IDs:
        # a timeout after Alpaca accepted a POST must not hide an order.
        # Never cancel another bot's order.
        for code in ("b", "s"):
            try:
                owned = paper.get_order_by_client_id(client_id(code))
                if owned is not None:
                    if not isinstance(owned, dict):
                        raise PaperFillStop("Malformed owned order on recovery.")
                    owned_id = owned.get("id")
                    if not isinstance(owned_id, str) or not owned_id:
                        raise PaperFillStop("Missing owned order ID on recovery.")
                    if str(owned.get("status", "")).lower() not in TERMINAL:
                        paper.cancel_order(owned_id)
            except Exception:
                print("WARNING: PAPER owned-order cancellation unconfirmed.")
        # Verify the exact original share count, NOT a zero baseline:
        # user/PAPER positions must remain untouched by the probe.
        try:
            if abs(owned_position_qty(symbol) - baseline_qty) > QTY_TOLERANCE:
                print("WARNING: PAPER baseline not restored. Cleanup required.")
        except Exception:
            print("WARNING: PAPER position reconciliation unavailable.")


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2, sort_keys=True))

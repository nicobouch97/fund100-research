"""PAPER-only V5-002 genuine signal compiler using frozen V5 model rules.

Separates source market data from execution: build_paper_compiler(...) is a
pure in-memory function taking a frozen shadow state and PAPER broker
market observations. It never fabricates a strategy event, never uses a
LIVE credential, and never submits or cancels orders.

A workflow must source the state from checked-out main, fetch market
data with PAPER credentials from data.alpaca.markets (GET only), use
Alpaca PAPER clock/calendar, and pass the result to the separately
locked PAPER broker execution bridge.
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

import fund100_alpaca_live_scheduled_compiler as frozen
import fund100_alpaca_live_scheduled_compiler_v1_1 as v11
import fund100_live_production_controller_v1_0 as production
import fund100_v5_paper_broker_adapter_v1_0 as paper_adapter


class PaperCompilerStop(RuntimeError):
    pass


def _source_manifest(state: dict) -> dict:
    sh = production.canonical_sha256(state)
    body = {
        "schema": v11.manifest_v11.MANIFEST_SCHEMA,
        "strategy": "V5-002_SHADOW",
        "manifest_type": "PENDING_STRATEGY_EVENT",
        "event_source": "SCHEDULED",
        "strategy_event_present": True,
        "strategy_state_date": state["last_date"],
        "strategy_state_sha256": sh,
    }
    mh = production.canonical_sha256(body)
    return {
        "manifest": body,
        "manifest_sha256": mh,
        "manifest_id": "f100-paper-" + state["last_date"].replace("-", "")
        + "-" + mh[:16],
    }


def _require_first_session(clock: dict, calendar: list, signal_day: str):
    if not isinstance(clock, dict) or clock.get("is_open") is not True:
        raise PaperCompilerStop("PAPER US equity market must be open.")
    now = frozen.parse_timestamp(clock.get("timestamp", ""))
    if now.tzinfo is None:
        raise PaperCompilerStop("PAPER market clock missing time zone.")
    signal_date = date.fromisoformat(signal_day)
    if now.date() <= signal_date:
        raise PaperCompilerStop("Cannot trade in signal's own session.")
    if not isinstance(calendar, list) or not calendar:
        raise PaperCompilerStop("PAPER trading calendar unavailable.")
    days = []
    for row in calendar:
        if not isinstance(row, dict):
            raise PaperCompilerStop("Malformed PAPER trading calendar.")
        current = date.fromisoformat(str(row.get("date", "")))
        if signal_date < current <= now.date():
            days.append(current)
    if not days or min(days) != now.date():
        raise PaperCompilerStop("Not next US trading session after signal.")

    eligible, minutes_to_close = frozen.execution_window(clock)
    if not eligible:
        raise PaperCompilerStop("Outside V5 frozen near-close session window.")
    return minutes_to_close


def build_paper_compiler(
    *, state: dict, paper_snapshot: dict | None = None,
    paper_clock: dict | None = None, paper_calendar: list | None = None,
    signal_closes: dict | None = None, latest_bars: dict | None = None,
) -> tuple[dict, dict]:
    """Return (signed compiler package, signed manifest package).

    No-event short circuit needs no broker or data observations.
    Event compilation requires caller-provided PAPER-only observations.
    """
    if not isinstance(state, dict) or state.get("strategy") != "V5-002_SHADOW":
        raise PaperCompilerStop("Frozen V5 shadow strategy missing.")
    signal_date = state.get("last_date")
    if not isinstance(signal_date, str):
        raise PaperCompilerStop("Frozen V5 signal date missing.")
    date.fromisoformat(signal_date)
    source = state.get("pending_source")
    pending = state.get("pending_target")
    if source is None and pending is None:
        # No event => no broker or data reads. This does not authorise
        # execution, even if the account is misconfigured.
        manifest = {
            "manifest": {}, "manifest_sha256": production.canonical_sha256({}),
            "manifest_id": "f100-paper-no-event",
        }
        compiler = {
            "schema": v11.COMPILER_SCHEMA,
            "strategy": "V5-002_SHADOW",
            "compiler_mode": "current",
            "status": "NO_SCHEDULED_EVENT",
            "genuine_scheduled_event": False,
            "candidate_intents": [],
            "live_execution_authorized": False,
            "network_write_capability": False,
            "broker_write_mode": "DISABLED",
            "orders_submitted": 0,
        }
        return {
            "compiler": compiler,
            "compiler_sha256": production.canonical_sha256(compiler),
        }, manifest
    if source != "SCHEDULED" or not isinstance(pending, dict) or not pending:
        raise PaperCompilerStop("No genuine scheduled V5 rebalance.")
    desired = frozen.genuine_scheduled_target(state)
    if desired is None:
        raise PaperCompilerStop("Scheduled shadow target could not be verified.")
    if not isinstance(paper_snapshot, dict):
        raise PaperCompilerStop("Fresh PAPER broker snapshot required.")
    account = paper_snapshot.get("account")
    positions = paper_snapshot.get("positions")
    open_orders = paper_snapshot.get("open_orders")
    if not isinstance(account, dict) or not isinstance(positions, dict):
        raise PaperCompilerStop("Malformed PAPER account/holdings.")
    if not isinstance(open_orders, list) or open_orders:
        raise PaperCompilerStop("Existing PAPER orders prevent compilation.")
    if account.get("status") != "ACTIVE" or account.get("trading_blocked") is not False:
        raise PaperCompilerStop("PAPER account unavailable for reconciliation.")
    nav = min(
        Decimal(str(account.get("equity", "0"))),
        Decimal("130.30"),
    )
    if not nav.is_finite() or nav <= 0:
        raise PaperCompilerStop("No deployable PAPER pilot NAV.")
    rows = []
    for symbol, position in sorted(positions.items()):
        if symbol not in paper_adapter.FROZEN_V5_ETFS or not isinstance(position, dict):
            raise PaperCompilerStop("Unreviewed PAPER position.")
        qty = Decimal(str(position.get("qty", "0")))
        value = Decimal(str(position.get("market_value", "0")))
        if not qty.is_finite() or qty < 0 or not value.is_finite() or value < 0:
            raise PaperCompilerStop("Short, non-finite or invalid PAPER holdings.")
        rows.append({
            "symbol": symbol,
            "current_weight": float(value / nav),
        })
    minutes_to_close = _require_first_session(
        paper_clock, paper_calendar, signal_date
    )
    if not isinstance(signal_closes, dict) or not isinstance(latest_bars, dict):
        raise PaperCompilerStop("Fresh IEX PAPER observations missing.")
    expected_symbols = set(frozen.required_market_symbols())
    if set(signal_closes) != expected_symbols or set(latest_bars) != expected_symbols:
        raise PaperCompilerStop("PAPER observations have wrong ETF universe.")
    market = frozen.build_market_snapshot(
        signal_closes=signal_closes, latest_bars=latest_bars,
    )
    market_sha = production.canonical_sha256(market)
    drifted, _, _, _ = frozen.calculate_reference_drift(
        state=state, signal_closes=signal_closes, latest_bars=latest_bars
    )
    frozen.validate_threshold_margin(current=drifted, desired=desired)
    executed = frozen.research_base.apply_trade_threshold(
        current=drifted, desired=desired,
    )
    frozen.decision_signature(current=drifted, executed=executed)
    manifest = _source_manifest(state)
    seed = frozen.event_seed(
        signal_date=signal_date, desired=desired,
        market_snapshot_hash=market_sha,
    )
    # Fresh PAPER positions, NOT LIVE compiler positions. The bridge
    # independently rebuilds PAPER directions before any trade.
    candidates = v11.compile_position_aware_intents(
        reconciliation_body={"reconciliation_rows": rows},
        executed_satellites=executed, seed=seed,
    )
    body = {
        "schema": v11.COMPILER_SCHEMA,
        "strategy": "V5-002_SHADOW",
        "strategy_state_date": signal_date,
        "strategy_state_sha256": manifest["manifest"]["strategy_state_sha256"],
        "source_manifest_id": manifest["manifest_id"],
        "source_manifest_sha256": manifest["manifest_sha256"],
        "compiler_mode": "current",
        "status": "GENUINE_SCHEDULED_EVENT",
        "genuine_scheduled_event": True,
        "market_data_feed": frozen.DATA_FEED,
        "market_snapshot": market,
        "market_snapshot_sha256": market_sha,
        "executed_satellite_weights": {
            symbol: round(float(executed[symbol]), 12)
            for symbol in frozen.research_base.EQUITY_UNIVERSE
        },
        "candidate_intents": candidates,
        "broker_delta_source": "FRESH_EPHEMERAL_RECONCILIATION",
        "broker_current_weights_persisted": False,
        "broker_dollar_values_persisted": False,
        "execution_window_eligible": True,
        "minutes_to_close": round(float(minutes_to_close), 4),
        "live_execution_authorized": False,
        "max_live_execution_notional_usd": 0.0,
        "network_write_capability": False,
        "broker_write_mode": "DISABLED",
        "orders_submitted": 0,
    }
    return {
        "compiler": body,
        "compiler_sha256": production.canonical_sha256(body),
    }, manifest

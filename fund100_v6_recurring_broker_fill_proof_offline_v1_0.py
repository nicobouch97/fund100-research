"""G2: broker-shaped recurring filled-order evidence, OFFLINE validation only.

Caller-provided dictionaries are NEVER authenticated Alpaca receipts. This
pure validation primitive verifies signed attempted-event identity, a filled
closed order, a complete chronological FILL sequence and post-order inventory.
It cannot prove private-state persistence, real API provenance, settlement,
current buying power, funded risk eligibility or permission to send next order.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
import re
from uuid import UUID

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_autonomous_event_identity_v1_0 as identity

SCHEMA = "FUND100_V6_G2_RECURRING_BROKER_RECEIPT_FILL_FLAT_OFFLINE_V1"
MAX_PAGE = 100
MAX_PAGES = 16
MAX_ORIGINAL_PILOT_ORDER_USD = Decimal("65")
BROKER_GETS = BROKER_POSTS = PRIVATE_WRITES = 0
TRADING_AUTHORIZED = False


class BrokerProofStop(ValueError):
    pass


def _number(value, label, *, zero=False):
    if type(value) is not str or re.fullmatch(
            r"(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,9})?", value) is None:
        raise BrokerProofStop("Invalid broker-shaped " + label)
    try:
        x = Decimal(value)
    except InvalidOperation:
        raise BrokerProofStop("Invalid amount " + label) from None
    if not x.is_finite() or (x < 0 if zero else x <= 0):
        raise BrokerProofStop("Nonpositive broker-shaped " + label)
    return x


def _time(value):
    if type(value) is not str or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z",
            value) is None:
        raise BrokerProofStop("Missing canonical UTC timestamp")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise BrokerProofStop("Impossible broker timestamp") from None
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise BrokerProofStop("Broker timestamp not UTC")
    return dt


def _now_utc():
    """Independent observation clock; test seam, not a caller receipt."""
    return datetime.now(timezone.utc)


def _uuid(value):
    if type(value) is not str:
        raise BrokerProofStop("Broker order UUID missing")
    try:
        obj = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise BrokerProofStop("Invalid broker order UUID") from None
    if str(obj) != value.lower():
        raise BrokerProofStop("Noncanonical order UUID")
    return value.lower()


def _positions(raw):
    if type(raw) is not dict:
        raise BrokerProofStop("Missing complete portfolio position snapshot")
    result = {}
    for symbol, qty in raw.items():
        if type(symbol) is not str or re.fullmatch(r"[A-Z][A-Z0-9.]{0,10}", symbol) is None:
            raise BrokerProofStop("Unsupported position ticker")
        value = _number(qty, "held quantity", zero=True)
        if value:
            result[symbol] = value
    return result


INTENT_SCHEMA = "FUND100_V6_RECURRING_EXACT_ORDER_INTENT_V1"
INTENT_FIELDS = frozenset({
    "schema", "client_order_id", "symbol", "side", "type",
    "time_in_force", "qty", "notional",
})


def _verify_frozen_intent(intent, signed_sha256, client_order_id, receipt):
    """Bind original signed intent preimage to the exact completed order.

    The HMAC journal authenticates only a digest of the original order
    intent. A client_order_id match alone cannot prove what asset, side or
    dollar/quantity was authorised in that recorded attempt.
    """
    if type(intent) is not dict or set(intent) != INTENT_FIELDS:
        raise BrokerProofStop("Missing exact original order intent preimage")
    if (intent["schema"] != INTENT_SCHEMA
        or intent["client_order_id"] != client_order_id
        or intent["symbol"] != receipt.get("symbol")
        or intent["side"] != receipt.get("side")
        or intent["type"] != "market"
        or intent["time_in_force"] != "day"
        or intent["side"] not in ("buy", "sell")):
        raise BrokerProofStop("Order intent identity or trade direction mismatch")
    q, n = intent["qty"], intent["notional"]
    if (q is None) == (n is None):
        raise BrokerProofStop("Original order intent has conflicting sizing modes")
    if n is not None:
        if intent["side"] != "buy":
            raise BrokerProofStop("Notional SELL intent lacks share quantity proof")
        if _number(n, "signed USD order notional") > MAX_ORIGINAL_PILOT_ORDER_USD:
            raise BrokerProofStop("Original signed order exceeds $65 investment limit")
    else:
        _number(q, "signed share order quantity")
    try:
        raw = json.dumps(
            intent, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise BrokerProofStop("Uncanonical original order intent") from None
    if not hmac.compare_digest(sha256(raw).hexdigest(), signed_sha256):
        raise BrokerProofStop("Original order intent preimage disagrees with signed journal")
    if receipt.get("qty") != q or receipt.get("notional") != n:
        raise BrokerProofStop("Broker order sizing differs from signed intent")
    return n is not None


def assess(*, private_signed_journal_source, genesis_sha256, account_binding_sha256,
           key, event_id, strategy_id, signal_time_utc, signal_sha256,
           strategy_release_sha256, standing_mandate_sha256, intent_sha256,
           original_intent, closed_order, fill_pages, before_positions, after_positions,
           open_orders, observed_at_utc):
    """Validate ONE synthetic replay; never turn dicts into LIVE authority."""
    try:
        expected = identity.key(
            strategy_id=strategy_id, signal_time_utc=signal_time_utc,
            signal_sha256=signal_sha256,
            deployed_strategy_release_sha256=strategy_release_sha256,
            standing_mandate_sha256=standing_mandate_sha256,
        )
        _, doc = journal.read_github_source(
            private_signed_journal_source, genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256, key=key)
    except (identity.IdentityStop, journal.JournalStop):
        raise BrokerProofStop("Unverified original signed recurring event") from None
    if event_id != expected:
        raise BrokerProofStop("Recurring event identity drift")
    record = doc["events"].get(event_id)
    if (type(record) is not dict or record["stage"] != "POST_MAY_HAVE_BEEN_SENT"
        or record["client_order_id"] != journal.client_id(event_id)
        or any(record[name] != value for name, value in (
            ("signal_sha256", signal_sha256),
            ("strategy_release_sha256", strategy_release_sha256),
            ("mandate_sha256", standing_mandate_sha256),
            ("intent_sha256", intent_sha256)))):
        raise BrokerProofStop("Event not at signed one-attempt possible-send boundary")
    if type(closed_order) is not dict or type(open_orders) is not list or open_orders:
        raise BrokerProofStop("Broker order source incomplete or has open orders")
    if (closed_order.get("client_order_id") != record["client_order_id"]
        or closed_order.get("status") != "filled"
        or closed_order.get("side") not in ("buy", "sell")
        or closed_order.get("type") != "market"
        or closed_order.get("time_in_force") != "day"
        or type(closed_order.get("symbol")) is not str
        or re.fullmatch(r"[A-Z][A-Z0-9.]{0,10}", closed_order["symbol"]) is None):
        raise BrokerProofStop("Unlinked or non-final recurring broker receipt")
    # The signed HMAC event stores ONLY the original intent commitment:
    # require its exact immutable preimage and compare every submitted order
    # field before trusting any broker-shaped fill math (still offline).
    intent_is_notional = _verify_frozen_intent(
        original_intent, intent_sha256, record["client_order_id"], closed_order
    )
    order_id = _uuid(closed_order.get("id"))
    # Alpaca dollar-notional fractional orders return qty=null even when
    # status=filled. Their *filled_qty* is the realized share quantity.
    # Accept ONLY an actual USD-notional BUY with exactly one sizing mode:
    # notional BUY or quantity BUY/SELL. Keep all source data UNTRUSTED.
    filled_qty = _number(closed_order.get("filled_qty"), "filled order quantity")
    raw_qty = closed_order.get("qty")
    raw_notional = closed_order.get("notional")
    is_notional_buy = raw_qty is None and raw_notional is not None
    if is_notional_buy != intent_is_notional:
        raise BrokerProofStop("Broker order mode drift from signed intent")
    if is_notional_buy:
        if closed_order["side"] != "buy":
            raise BrokerProofStop("Notional SELL requires independent quantity proof")
        requested_notional = _number(raw_notional, "requested USD notional")
        if requested_notional > MAX_ORIGINAL_PILOT_ORDER_USD:
            raise BrokerProofStop("Original pilot $65 notional order ceiling exceeded")
        qty = filled_qty
    else:
        if raw_qty is None or raw_notional is not None:
            raise BrokerProofStop("Order has missing or conflicting sizing modes")
        qty = _number(raw_qty, "order quantity")
        if filled_qty != qty:
            raise BrokerProofStop("Partial or inconsistent order")
        requested_notional = None
    submitted = _time(closed_order.get("submitted_at"))
    finished = _time(closed_order.get("filled_at"))
    observed = _time(observed_at_utc)
    if not submitted <= finished <= observed:
        raise BrokerProofStop("Source observation precedes order completion")
    # A signed event cannot explain an order already sent before its signal.
    # Nor can a caller-provided future observation prove a completed fill.
    if submitted < _time(signal_time_utc):
        raise BrokerProofStop("Broker order predates signed signal")
    if observed > _now_utc():
        raise BrokerProofStop("Future-dated broker observation is not yet evidence")
    if (type(fill_pages) is not list or not 1 <= len(fill_pages) <= MAX_PAGES
        or any(type(page) is not list for page in fill_pages)
        or any(len(page) != MAX_PAGE for page in fill_pages[:-1])
        or len(fill_pages[-1]) >= MAX_PAGE):
        raise BrokerProofStop("Incomplete or unbounded FILL pagination")
    seen = set()
    previous = submitted
    cumulative = Decimal(0)
    notional = Decimal(0)
    final_seen = False
    for page in fill_pages:
        for row in page:
            if type(row) is not dict:
                raise BrokerProofStop("Malformed recurring FILL activity")
            fid = row.get("id")
            if (type(fid) is not str or not fid or fid in seen
                or row.get("activity_type") != "FILL"
                or _uuid(row.get("order_id")) != order_id
                or row.get("symbol") != closed_order["symbol"]
                or row.get("side") != closed_order["side"]
                or row.get("type") not in ("partial_fill", "fill")
                or final_seen):
                raise BrokerProofStop("Duplicate, unrelated or late FILL activity")
            seen.add(fid)
            when = _time(row.get("transaction_time"))
            if not previous <= when <= finished:
                raise BrokerProofStop("Unordered or impossible FILL time")
            previous = when
            part = _number(row.get("qty"), "FILL shares")
            cumulative += part
            price = _number(row.get("price"), "FILL price")
            notional += part * price
            if (_number(row.get("cum_qty"), "cumulative shares") != cumulative
                or _number(row.get("leaves_qty"), "remaining shares", zero=True)
                     != qty-cumulative
                or cumulative > qty):
                raise BrokerProofStop("FILL share sum disagrees with receipt")
            final_seen = row["type"] == "fill"
            if final_seen and cumulative != qty:
                raise BrokerProofStop("Final FILL not the complete order")
    if not final_seen or cumulative != qty or not seen:
        raise BrokerProofStop("Missing final complete order FILL")
    # A notional BUY must not consume more than the requested dollars
    # beyond one cent of possible price/quantity representation rounding.
    # The actual filled notional is still independently capped at $65.
    if requested_notional is not None and notional > requested_notional + Decimal("0.01"):
        raise BrokerProofStop("Notional BUY fill exceeds submitted dollar order")
    before = _positions(before_positions)
    after = _positions(after_positions)
    ticker = closed_order["symbol"]
    old = before.get(ticker, Decimal(0))
    new = after.get(ticker, Decimal(0))
    effect = qty if closed_order["side"] == "buy" else -qty
    if (new-old != effect
        or {k:v for k,v in before.items() if k != ticker}
           != {k:v for k,v in after.items() if k != ticker}):
        raise BrokerProofStop("Changed or unreconciled post-fill portfolio holdings")
    # The $65 limit is a maximum NEW investment order, not a prohibition
    # against reducing risk by closing an already-owned >$65 position.
    # Preserve the conservative $65 ceiling for all buys and partial sells;
    # a larger sell is structurally admissible ONLY when it liquidates
    # the entire pre-existing quantity and leaves no residual inventory.
    # This is still synthetic reconciliation, NEVER a trade permit.
    full_inventory_exit = (
        closed_order["side"] == "sell" and old == qty and new == 0
    )
    if notional > MAX_ORIGINAL_PILOT_ORDER_USD and not full_inventory_exit:
        raise BrokerProofStop(
            "New order or partial sell exceeds original pilot $65 limit"
        )
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_RECEIPT_FILL_AND_PORTFOLIO_REPLAY_MATCH_ONLY",
        "signed_possible_send_source_structurally_verified": True,
        "synthetic_order_fields_bound_to_signed_intent_preimage": True,
        "filled_order_and_complete_FILLS_structurally_matched": True,
        "all_remaining_positions_unchanged_in_fixture": True,
        "original_65usd_order_notional_ceiling_checked": True,
        "synthetic_alpaca_notional_buy_with_null_qty_validated": is_notional_buy,
        "synthetic_full_existing_position_exit_exception_applied":
            full_inventory_exit and notional > MAX_ORIGINAL_PILOT_ORDER_USD,
        "real_broker_receipt_source_authenticated": False,
        "real_private_journal_antirollback_verified": False,
        "broker_cash_and_settlement_verified": False,
        "live_broker_client_authenticated": False,
        "future_order_authorized": False,
        "next_live_order_authorized": False,
        "broker_gets": 0, "broker_posts": 0, "private_writes": 0,
        "broker_order_id": None, "trade_quantities": None,
        "account_id": None, "fill_price": None,
    }
